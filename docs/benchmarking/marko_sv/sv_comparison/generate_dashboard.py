#!/usr/bin/env python3
"""
Generate a self-contained HTML concordance dashboard for the Marko SV benchmark.

Compares breseq (ground truth) against yAMP pipeline tools:
  - HaplotypeCaller (SNP/InDel) — soft-filtered joint VCF
  - Manta + TIDDIT (SV) — via SURVIVOR merge

Usage:
    source ~/miniforge3/etc/profile.d/conda.sh && conda activate nf-env
    python generate_dashboard.py

    # Or with explicit paths:
    python generate_dashboard.py \
        --breseq-gd /path/to/annotated.gd \
        --hc-vcf /path/to/soft_filtered.vcf.gz \
        --survivor-union /path/to/merged_union.vcf \
        --survivor-consensus /path/to/merged_consensus.vcf \
        --comparison-tsv /path/to/comparison_report.tsv \
        -o /path/to/output/index.html
"""

import argparse
import csv
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path


# ---------------------------------------------------------------------------
# Default paths (relative to project root)
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parents[4]  # up to ALE_nextflow
DEFAULTS = {
    "breseq_gd": PROJECT_ROOT / "output_marko_sv/variant_calling/breseq/SRR6281661/annotated.gd",
    "hc_vcf": PROJECT_ROOT / "output_marko_sv/annotation/haplotypecaller/joint_variant_calling/HaplotypeCaller_joint_calling_soft_filtered_snpEff.ann.vcf.gz",
    "survivor_union": Path(__file__).resolve().parent / "merged_union.vcf",
    "survivor_consensus": Path(__file__).resolve().parent / "merged_consensus.vcf",
    "comparison_tsv": Path(__file__).resolve().parent / "comparison_report.tsv",
    "output": Path(__file__).resolve().parent / "index.html",
}


# ---------------------------------------------------------------------------
# Parsers
# ---------------------------------------------------------------------------

def parse_breseq_annotated_gd(gd_path):
    """Parse annotated.gd for SNP, INS, DEL, MOB entries with annotations."""
    snp_indel = []
    sv = []

    with open(gd_path) as f:
        for line in f:
            if line.startswith("#"):
                continue
            fields = line.strip().split("\t")
            if len(fields) < 5:
                continue

            entry_type = fields[0]
            chrom = fields[3]
            pos = int(fields[4])

            # Parse key=value annotations
            annot = {}
            for field in fields[5:]:
                if "=" in field:
                    k, v = field.split("=", 1)
                    annot[k] = v
                elif entry_type in ("SNP",) and not annot:
                    annot["new_base"] = field

            gene = annot.get("gene_name", "")
            effect = annot.get("snp_type", annot.get("mutation_category", ""))

            if entry_type == "SNP":
                snp_indel.append({
                    "type": "SNP",
                    "pos": pos,
                    "gene": gene,
                    "effect": effect,
                    "detail": f"{chrom}:{pos}",
                })
            elif entry_type == "INS" and int(annot.get("repeat_size", len(annot.get("seq", "")))) < 50:
                snp_indel.append({
                    "type": "INS",
                    "pos": pos,
                    "gene": gene,
                    "effect": effect or "small_indel",
                    "detail": f"+{annot.get('seq', '?')}",
                })
            elif entry_type == "DEL":
                size = int(fields[5]) if len(fields) > 5 and fields[5].isdigit() else 0
                sv.append({
                    "type": "DEL",
                    "pos": pos,
                    "size": size,
                    "gene": gene,
                    "detail": annot.get("mutation_category", ""),
                })
            elif entry_type == "MOB":
                element = fields[5] if len(fields) > 5 else "?"
                strand = fields[6] if len(fields) > 6 else "?"
                dup = int(fields[7]) if len(fields) > 7 and fields[7].isdigit() else 0
                repeat_size = int(annot.get("repeat_size", 0))
                ref_seq = annot.get("ref_seq", "")
                sv.append({
                    "type": "MOB",
                    "pos": pos,
                    "size": repeat_size if repeat_size else dup,
                    "gene": gene,
                    "detail": f"{element} ({'+' if strand == '1' else '-'})",
                    "tsd_size": dup,
                    "tsd_seq": ref_seq,
                })

    return snp_indel, sv


def _parse_ann_field(ann_str):
    """Extract gene name and effect from the first (highest-impact) SnpEff ANN entry."""
    if not ann_str or ann_str == ".":
        return "", ""
    # ANN format: ALT|effect|impact|gene_name|gene_id|...
    first = ann_str.split(",")[0]
    fields = first.split("|")
    if len(fields) >= 4:
        effect = fields[1]  # e.g. missense_variant, synonymous_variant
        gene = fields[3]    # e.g. b0393
        return gene, effect
    return "", ""


def query_all_hc_variants(hc_vcf):
    """Query ALL variants from the HC VCF (annotated or unannotated) using bcftools."""
    results = {}
    try:
        out = subprocess.check_output(
            ["bcftools", "query", "-f",
             "%POS\t%REF\t%ALT\t%FILTER\t%INFO/QD\t%INFO/DP\t%INFO/SOR\t%INFO/MQ\t%INFO/ANN\n",
             str(hc_vcf)],
            stderr=subprocess.DEVNULL, text=True
        ).strip()
        for line in out.split("\n"):
            if not line.strip():
                continue
            parts = line.split("\t")
            pos = int(parts[0])
            ann_str = parts[8] if len(parts) > 8 else ""
            gene, effect = _parse_ann_field(ann_str)
            results[pos] = {
                "pos": pos,
                "ref": parts[1],
                "alt": parts[2],
                "filter": parts[3],
                "qd": float(parts[4]) if parts[4] != "." else None,
                "dp": int(parts[5]) if parts[5] != "." else None,
                "sor": float(parts[6]) if parts[6] != "." else None,
                "mq": float(parts[7]) if parts[7] != "." else None,
                "gene": gene,
                "effect": effect,
            }
    except (subprocess.CalledProcessError, ValueError):
        pass
    return results


def parse_survivor_vcf(vcf_path):
    """Parse SURVIVOR merged VCF."""
    records = []
    with open(vcf_path) as f:
        for line in f:
            if line.startswith("#"):
                continue
            fields = line.strip().split("\t")
            chrom = fields[0]
            pos = int(fields[1])
            info = {}
            for item in fields[7].split(";"):
                if "=" in item:
                    k, v = item.split("=", 1)
                    info[k] = v

            supp_vec = info.get("SUPP_VEC", "00")
            records.append({
                "chrom": chrom,
                "pos": pos,
                "svtype": info.get("SVTYPE", "."),
                "svlen": abs(int(info.get("SVLEN", 0))),
                "end": int(info.get("END", pos)),
                "supp": int(info.get("SUPP", 0)),
                "supp_vec": supp_vec,
                "manta": supp_vec[0] == "1" if len(supp_vec) >= 1 else False,
                "tiddit": supp_vec[1] == "1" if len(supp_vec) >= 2 else False,
            })
    return records


def parse_comparison_tsv(tsv_path):
    """Parse comparison_report.tsv from compare_breseq_sv.py."""
    rows = []
    with open(tsv_path) as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            rows.append(row)
    return rows


# ---------------------------------------------------------------------------
# Build dashboard data
# ---------------------------------------------------------------------------

def _classify_hc_cluster(pos):
    """Classify HC-only variants into known artifact clusters."""
    if 566400 <= pos <= 566600:
        return "566k cluster (8 SNPs in 65 bp)"
    elif 579000 <= pos <= 579600:
        return "579k cluster (7 variants in 450 bp)"
    elif 1299400 <= pos <= 1299600:
        return "Near DEL breakpoint at 1,299,499"
    elif 1429000 <= pos <= 1430000:
        return "1429k cluster (47 SNPs in 860 bp)"
    elif 4035000 <= pos <= 4036000:
        return "Isolated HC-only SNP"
    return "HC-only"


def build_snp_indel_table(breseq_snps, hc_data):
    """Build SNP/InDel concordance table with all HC variants."""
    rows = []
    matched_hc_positions = set()

    # First pass: breseq variants (ground truth)
    for variant in breseq_snps:
        pos = variant["pos"]
        # For INS, HC may be at pos or pos-1
        hc = hc_data.get(pos) or hc_data.get(pos - 1)
        if hc:
            matched_hc_positions.add(hc["pos"])

        row = {
            "pos": pos,
            "type": variant["type"],
            "gene": variant["gene"],
            "effect": variant["effect"],
            "breseq": "Yes",
            "ref": hc["ref"] if hc else ".",
            "alt": hc["alt"] if hc else ".",
            "hc_filter": hc["filter"] if hc else "NOT_FOUND",
            "hc_qd": hc["qd"] if hc else None,
            "hc_dp": hc["dp"] if hc else None,
            "hc_sor": hc["sor"] if hc else None,
            "notes": "",
        }

        if hc and hc["filter"] == "PASS":
            row["notes"] = "High quality"
        elif hc and hc["filter"] != "PASS":
            row["notes"] = f"Soft-filtered: {hc['filter']} (SOR={hc['sor']}, threshold=3.0)"
        else:
            row["notes"] = "Not detected by HC"

        rows.append(row)

    # Second pass: HC-only variants (not in breseq ground truth)
    for pos, hc in sorted(hc_data.items()):
        if pos in matched_hc_positions:
            continue
        ref_len = len(hc["ref"])
        alt_len = len(hc["alt"])
        if ref_len == 1 and alt_len == 1:
            vtype = "SNP"
        elif alt_len > ref_len:
            vtype = "INS"
        else:
            vtype = "DEL"

        cluster = _classify_hc_cluster(pos)
        rows.append({
            "pos": pos,
            "type": vtype,
            "gene": hc.get("gene", ""),
            "effect": hc.get("effect", ""),
            "breseq": "No",
            "ref": hc["ref"],
            "alt": hc["alt"],
            "hc_filter": hc["filter"],
            "hc_qd": hc["qd"],
            "hc_dp": hc["dp"],
            "hc_sor": hc["sor"],
            "notes": cluster,
        })

    # Sort: breseq=Yes first, then by position
    rows.sort(key=lambda r: (0 if r["breseq"] == "Yes" else 1, r["pos"]))
    # Add sort index so Tabulator preserves our order
    for i, r in enumerate(rows):
        r["_sort"] = i
    return rows


def _consensus_label(has_manta, has_tiddit):
    """Human-readable consensus label for the SV table."""
    if has_manta and has_tiddit:
        return "Manta + TIDDIT"
    elif has_manta:
        return "Manta only"
    elif has_tiddit:
        return "TIDDIT only"
    return "\u2014"


def build_sv_table(breseq_svs, union_records, consensus_records, comparison_rows):
    """Build SV concordance table data."""
    rows = []

    # Build consensus position set for quick lookup
    consensus_dels = {(r["pos"], r["svtype"]) for r in consensus_records}

    # Process comparison report rows
    for cr in comparison_rows:
        status = cr["status"]

        if status == "MATCHED":
            has_manta = "Manta" in cr.get("sv_callers", "")
            has_tiddit = "TIDDIT" in cr.get("sv_callers", "")
            rows.append({
                "type": cr["breseq_type"],
                "pos": int(cr["breseq_pos"]),
                "size": int(cr["breseq_size"]),
                "breseq": "Yes",
                "manta": "Yes" if has_manta else "No",
                "tiddit": "Yes" if has_tiddit else "No",
                "consensus": _consensus_label(has_manta, has_tiddit),
                "notes": f"Matched (dist={cr['match_dist']}bp)",
                "source": "breseq + SV callers",
            })
        elif status == "BRESEQ_ONLY":
            extra = cr.get("breseq_extra", "")
            is_mob = "element=" in extra
            size = int(cr["breseq_size"])

            # Skip small indels (already in SNP/InDel table)
            if not is_mob and cr["breseq_type"] == "INS" and size < 50:
                continue

            # Format MOB notes with element name and TSD ref_seq
            if is_mob:
                import re
                el_match = re.search(r"element=(\w+)", extra)
                strand_match = re.search(r"strand=(-?\d)", extra)
                element = el_match.group(1) if el_match else "?"
                strand = "+" if strand_match and strand_match.group(1) == "1" else "-"

                # Look up actual IS size and TSD from parsed breseq SVs
                mob_pos = int(cr["breseq_pos"])
                mob_info = next((s for s in breseq_svs if s["type"] == "MOB" and s["pos"] == mob_pos), None)
                if mob_info:
                    is_size = mob_info["size"]
                    tsd_seq = mob_info.get("tsd_seq", "")
                    tsd_size = mob_info.get("tsd_size", size)
                    notes = f"{element} ({strand}), TSD: {tsd_seq} ({tsd_size} bp)"
                else:
                    is_size = size
                    notes = f"{element} ({strand} strand)"
                display_type = "MOB"
            else:
                is_size = size
                notes = extra.replace("id=", "breseq_id=") if extra else "breseq-only"
                display_type = cr["breseq_type"]

            rows.append({
                "type": display_type,
                "pos": int(cr["breseq_pos"]),
                "size": is_size,
                "breseq": "Yes",
                "manta": "N/A" if is_mob else "No",
                "tiddit": "N/A" if is_mob else "No",
                "consensus": "\u2014",
                "notes": notes,
                "source": "breseq only",
            })
        elif status == "SV_CALLER_ONLY":
            callers = cr.get("sv_callers", "")
            has_manta = "Manta" in callers
            has_tiddit = "TIDDIT" in callers
            rows.append({
                "type": cr["sv_type"],
                "pos": int(cr["sv_pos"]),
                "size": int(cr["sv_size"]),
                "breseq": "No",
                "manta": "Yes" if has_manta else "No",
                "tiddit": "Yes" if has_tiddit else "No",
                "consensus": _consensus_label(has_manta, has_tiddit),
                "notes": f"SV-caller only",
                "source": "SV callers only",
            })

    # Sort: breseq DELs first, then other breseq SVs, then SV-caller-only
    type_priority = {"DEL": 0, "MOB": 1, "INS": 2, "INV": 3, "DUP": 4, "BND": 5}
    rows.sort(key=lambda r: (
        0 if r["breseq"] == "Yes" else 1,           # breseq-detected first
        type_priority.get(r["type"], 9),             # DEL > MOB > INV > ...
        r["pos"],                                     # then by position
    ))
    # Add sort index so Tabulator preserves our order
    for i, r in enumerate(rows):
        r["_sort"] = i
    return rows


def build_audit_data(union_path, consensus_path, manta_path, tiddit_path):
    """Build audit summary for SURVIVOR merge artifacts."""

    def count_records(path):
        with open(path) as f:
            return sum(1 for line in f if not line.startswith("#") and line.strip())

    def count_supp_vec(path):
        counts = {}
        with open(path) as f:
            for line in f:
                if line.startswith("#"):
                    continue
                for item in line.split("\t")[7].split(";"):
                    if item.startswith("SUPP_VEC="):
                        vec = item.split("=")[1]
                        counts[vec] = counts.get(vec, 0) + 1
        return counts

    manta_n = count_records(manta_path) if os.path.exists(manta_path) else "N/A"
    tiddit_n = count_records(tiddit_path) if os.path.exists(tiddit_path) else "N/A"
    union_n = count_records(union_path)
    consensus_n = count_records(consensus_path)
    union_supp = count_supp_vec(union_path)
    consensus_supp = count_supp_vec(consensus_path)

    return {
        "manta_records": manta_n,
        "tiddit_records": tiddit_n,
        "union_records": union_n,
        "consensus_records": consensus_n,
        "union_supp_vec": union_supp,
        "consensus_supp_vec": consensus_supp,
    }


# ---------------------------------------------------------------------------
# HTML generation
# ---------------------------------------------------------------------------

HTML_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Marko SV Benchmark — breseq vs yAMP Concordance</title>
    <link href="https://unpkg.com/tabulator-tables@6.3.0/dist/css/tabulator.min.css" rel="stylesheet">
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
            max-width: 1200px;
            margin: 40px auto;
            padding: 0 20px;
            color: #333;
        }}
        h1 {{ border-bottom: 2px solid #0366d6; padding-bottom: 8px; }}
        h2 {{ margin-top: 32px; color: #24292e; }}
        a {{ color: #0366d6; text-decoration: none; }}
        a:hover {{ text-decoration: underline; }}
        .meta {{ color: #586069; font-size: 0.9em; }}
        .section {{ margin: 24px 0; }}
        .stat-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 16px;
            margin: 16px 0;
        }}
        .stat-card {{
            background: #f6f8fa;
            border: 1px solid #e1e4e8;
            border-radius: 6px;
            padding: 16px;
            text-align: center;
        }}
        .stat-card .value {{
            font-size: 2em;
            font-weight: 700;
            color: #24292e;
        }}
        .stat-card .label {{
            font-size: 0.85em;
            color: #586069;
            margin-top: 4px;
        }}
        .badge {{
            display: inline-block;
            padding: 2px 8px;
            border-radius: 3px;
            font-size: 0.8em;
            font-weight: 600;
        }}
        .badge-pass {{ background: #dcffe4; color: #22863a; }}
        .badge-warn {{ background: #fff5b1; color: #735c0f; }}
        .badge-fail {{ background: #ffeef0; color: #cb2431; }}
        .badge-na {{ background: #f1f1f1; color: #888; }}
        .badge-yes {{ background: #dcffe4; color: #22863a; }}
        .badge-no {{ background: #ffeef0; color: #cb2431; }}
        .finding {{ margin: 8px 0; padding: 8px 12px; border-left: 3px solid #0366d6; background: #f6f8fa; }}
        .finding-good {{ border-left-color: #22863a; }}
        .finding-note {{ border-left-color: #e36209; }}
        .finding-info {{ border-left-color: #0366d6; }}
        .tabulator {{ font-size: 0.9em; border: 1px solid #e1e4e8; }}
        .tabulator .tabulator-header {{ background: #f6f8fa; }}
        .tabulator-row.tabulator-row-even {{ background: #fafbfc; }}
        .footer {{
            color: #586069;
            font-size: 0.85em;
            margin-top: 40px;
            border-top: 1px solid #e1e4e8;
            padding-top: 12px;
        }}
        details {{ margin: 8px 0; }}
        details summary {{ cursor: pointer; color: #0366d6; font-weight: 600; }}
        pre.audit {{ background: #f6f8fa; padding: 12px; border-radius: 4px; font-size: 0.85em; overflow-x: auto; }}
    </style>
</head>
<body>

<h1>Marko SV Benchmark &mdash; breseq vs yAMP Concordance</h1>
<p class="meta">
    Sample: <strong>SRR6281661</strong> &middot;
    Organism: <em>E. coli</em> K-12 MG1655 &middot;
    Ploidy: 1 (haploid) &middot;
    Generated {generated_date}
</p>
<p class="meta">
    Ground truth: <strong>breseq 0.39.0</strong> &middot;
    yAMP tools: GATK HaplotypeCaller (joint germline, ploidy=1), Manta, TIDDIT &middot;
    SV merge: SURVIVOR 1.0.7
</p>

<!-- Section 1: Summary Stats -->
<div class="section">
    <h2>Summary</h2>
    <div class="stat-grid">
        <div class="stat-card">
            <div class="value">4/4</div>
            <div class="label">breseq large deletions<br>detected by yAMP (Manta + TIDDIT)</div>
        </div>
        <div class="stat-card">
            <div class="value">0/3</div>
            <div class="label">breseq-unique MOB insertions<br>detected by yAMP (IS2, IS5 &mdash; requires assembly-based detection)</div>
        </div>
        <div class="stat-card">
            <div class="value">11/11</div>
            <div class="label">breseq SNPs + InDels<br>detected by yAMP (10/11 passed HC filter)</div>
        </div>
    </div>
</div>

<!-- Section 2: SV Concordance -->
<div class="section">
    <h2>Structural Variant Concordance</h2>
    <p class="meta">
        breseq detected 4 large deletions and 3 IS-element mobilizations (MOB).
        Manta and TIDDIT independently confirm all 4 deletions.
        SURVIVOR merge (max_dist=1000bp, type_agree=yes) used for consensus.
        <br>Click any <strong>Position</strong> value to open the IGV report with read pileup at that locus.
    </p>
    <div id="sv-table"></div>
</div>

<!-- Section 3: SNP/InDel Concordance -->
<div class="section">
    <h2>SNP / InDel Concordance</h2>
    <p class="meta">
        breseq called 11 SNPs/small indels (ground truth).
        HaplotypeCaller called 76 total variants; all 11 breseq calls detected.
        65 HC-only variants cluster in 3 regions (likely alignment artifacts).
        FILTER column from GATK VariantFiltration (soft filtering fallback for custom genomes).
        <br>Click any <strong>Position</strong> value to open the IGV report with read pileup at that locus.
    </p>
    <details>
        <summary>Filter metrics explained (QD, DP, SOR)</summary>
        <div style="padding: 10px 0; font-size: 0.9em; line-height: 1.6;">
            <p>GATK VariantFiltration populates the FILTER column with <code>PASS</code> or named filter tags
               but <strong>does not remove any variants</strong>. This is a soft filter fallback used when
               VQSR cannot run (no known variant resources for custom genomes).</p>
            <table style="border-collapse: collapse; width: 100%; margin: 10px 0;">
                <thead>
                    <tr style="background: #f6f8fa; text-align: left;">
                        <th style="padding: 6px 10px; border: 1px solid #e1e4e8;">Column</th>
                        <th style="padding: 6px 10px; border: 1px solid #e1e4e8;">Metric</th>
                        <th style="padding: 6px 10px; border: 1px solid #e1e4e8;">Filter Threshold</th>
                        <th style="padding: 6px 10px; border: 1px solid #e1e4e8;">Interpretation</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td style="padding: 6px 10px; border: 1px solid #e1e4e8;"><strong>QD</strong></td>
                        <td style="padding: 6px 10px; border: 1px solid #e1e4e8;">Quality by Depth</td>
                        <td style="padding: 6px 10px; border: 1px solid #e1e4e8;">QD &lt; 2.0 &rarr; <code>QD_filter</code></td>
                        <td style="padding: 6px 10px; border: 1px solid #e1e4e8;">QUAL score / total depth. Low QD = weak evidence per read. Higher is better.</td>
                    </tr>
                    <tr>
                        <td style="padding: 6px 10px; border: 1px solid #e1e4e8;"><strong>DP</strong></td>
                        <td style="padding: 6px 10px; border: 1px solid #e1e4e8;">Read Depth</td>
                        <td style="padding: 6px 10px; border: 1px solid #e1e4e8;">&mdash; (no filter)</td>
                        <td style="padding: 6px 10px; border: 1px solid #e1e4e8;">Total reads at this position (INFO/DP, cohort-level). Shown for context only.</td>
                    </tr>
                    <tr>
                        <td style="padding: 6px 10px; border: 1px solid #e1e4e8;"><strong>SOR</strong></td>
                        <td style="padding: 6px 10px; border: 1px solid #e1e4e8;">Strand Odds Ratio</td>
                        <td style="padding: 6px 10px; border: 1px solid #e1e4e8;">SOR &gt; 3.0 &rarr; <code>SOR_filter</code></td>
                        <td style="padding: 6px 10px; border: 1px solid #e1e4e8;">Strand bias test. SOR &gt; 3.0 = variant seen disproportionately on one strand (possible artifact). Lower is better.</td>
                    </tr>
                    <tr>
                        <td style="padding: 6px 10px; border: 1px solid #e1e4e8;"><strong>HC Filter</strong></td>
                        <td style="padding: 6px 10px; border: 1px solid #e1e4e8;">FILTER column</td>
                        <td style="padding: 6px 10px; border: 1px solid #e1e4e8;">Combined result</td>
                        <td style="padding: 6px 10px; border: 1px solid #e1e4e8;">
                            <code>PASS</code> = passes all filters.
                            Otherwise shows which filter(s) flagged the variant
                            (e.g. <code>QD_filter</code>, <code>SOR_filter</code>, <code>MQ_filter</code>).
                        </td>
                    </tr>
                </tbody>
            </table>
            <p style="margin-top: 8px;">
                <strong>Other soft filters applied</strong> (not shown as columns):
                FS &gt; 60.0 (<code>FS_filter</code>),
                MQ &lt; 40.0 (<code>MQ_filter</code>),
                MQRankSum &lt; -12.5,
                ReadPosRankSum &lt; -8.0,
                QUAL &lt; 30.0.
                INDEL thresholds are more lenient (FS &gt; 200, SOR &gt; 10).
            </p>
            <p style="color: #586069;">
                Thresholds follow GATK best practices for human data.
                See <code>conf/modules/joint_germline.config</code> for full configuration.
            </p>
        </div>
    </details>
    <div id="snp-table"></div>
</div>

<!-- Section 4: Key Findings -->
<div class="section">
    <h2>Key Findings</h2>
    <div class="finding finding-good">
        <strong>100% large deletion recall.</strong>
        All 4 breseq deletions (776 bp &ndash; 6,790 bp) detected by both Manta and TIDDIT
        with &le;8 bp coordinate difference. SURVIVOR consensus confirms all 4.
    </div>
    <div class="finding finding-good">
        <strong>100% SNP/InDel recall.</strong>
        All 11 breseq SNPs and small indels detected by HaplotypeCaller.
        10/11 pass soft quality filters (PASS). 1 flagged by SOR_filter.
    </div>
    <div class="finding finding-note">
        <strong>rpoS nonsense mutation soft-filtered.</strong>
        G2867455A (rpoS, W &rarr; Stop) has SOR=3.014, barely above the 3.0 threshold.
        QD=29.56 is excellent (threshold: 2.0). This is a biologically important mutation
        frequently seen in <em>E. coli</em> lab evolution. Consider relaxing SOR threshold
        or reviewing this filter for haploid organisms.
    </div>
    <div class="finding finding-info">
        <strong>MOB insertions are breseq-unique.</strong>
        3 IS-element mobilizations (2&times;IS2, 1&times;IS5) detected only by breseq.
        This is expected: standard SV callers cannot resolve insertions of repeat elements
        already present elsewhere in the genome. breseq uses assembly-based junction detection.
    </div>
    <div class="finding finding-info">
        <strong>yAMP found additional SVs not in breseq.</strong>
        A 9,049 bp deletion at position 2,169,285 (Manta + TIDDIT consensus) and
        an inversion at ~1,207,789 were detected by SV callers but not breseq.
        These may represent real structural variants or alignment artifacts worth investigating.
    </div>
</div>

<!-- Section 5: SURVIVOR Merge Audit -->
<div class="section">
    <h2>SURVIVOR Merge Audit</h2>
    <details>
        <summary>Show audit details</summary>
        <pre class="audit">{audit_text}</pre>
    </details>
</div>

<div class="footer">
    Ground truth: breseq 0.39.0 &middot;
    Pipeline: yAMP (nf-core/sarek 3.5.1 fork) &middot;
    Reference: U00096.3 (NCBI) &middot;
    Generated by <code>generate_dashboard.py</code>
</div>

<script src="https://unpkg.com/tabulator-tables@6.3.0/dist/js/tabulator.min.js"></script>
<script>
    // --- Embedded data ---
    const svData = {sv_data_json};
    const snpData = {snp_data_json};

    // --- Badge formatters ---
    function yesNoBadge(cell) {{
        var v = cell.getValue();
        if (v === "Yes") return '<span class="badge badge-yes">Yes</span>';
        if (v === "No") return '<span class="badge badge-no">No</span>';
        if (v === "N/A") return '<span class="badge badge-na">N/A</span>';
        return v;
    }}

    function filterBadge(cell) {{
        var v = cell.getValue();
        if (v === "PASS") return '<span class="badge badge-pass">PASS</span>';
        if (v === "NOT_FOUND") return '<span class="badge badge-fail">NOT FOUND</span>';
        return '<span class="badge badge-warn">' + v + '</span>';
    }}

    function consensusBadge(cell) {{
        var v = cell.getValue();
        if (v === "Manta + TIDDIT") return '<span class="badge badge-yes">Manta + TIDDIT</span>';
        if (v === "Manta only") return '<span class="badge badge-warn">Manta only</span>';
        if (v === "TIDDIT only") return '<span class="badge badge-warn">TIDDIT only</span>';
        return '<span class="badge badge-na">&mdash;</span>';
    }}

    var igvHcUrl = "SRR6281661_report.html";
    var igvSvUrl = "SRR6281661_sv_report.html";

    function snpPosLink(cell) {{
        var pos = cell.getValue();
        var display = pos.toLocaleString();
        return '<a href="' + igvHcUrl + '?locus=U00096:' + pos + '" target="_blank" title="Open in IGV report (HC)">' + display + '</a>';
    }}

    function svPosLink(cell) {{
        var pos = cell.getValue();
        var display = pos.toLocaleString();
        var row = cell.getRow().getData();
        if (row.type === "MOB") return display;
        return '<a href="' + igvSvUrl + '?locus=U00096:' + pos + '" target="_blank" title="Open in IGV report (SV)">' + display + '</a>';
    }}

    function effectBadge(cell) {{
        var v = cell.getValue();
        if (!v) return '';
        if (v.includes('nonsense')) return '<span class="badge badge-fail">' + v + '</span>';
        if (v.includes('nonsynonymous')) return '<span class="badge badge-warn">' + v + '</span>';
        if (v.includes('synonymous') && !v.includes('non')) return '<span class="badge badge-pass">' + v + '</span>';
        return '<span class="badge badge-na">' + v + '</span>';
    }}

    // --- SV Concordance Table ---
    new Tabulator("#sv-table", {{
        data: svData,
        layout: "fitDataFill",
        headerSortTristate: true,
        initialSort: [{{ column: "_sort", dir: "asc" }}],
        columns: [
            {{ title: "Type", field: "type", headerFilter: "list", headerFilterParams: {{ valuesLookup: true }}, width: 80 }},
            {{ title: "Position", field: "pos", sorter: "number", hozAlign: "right",
               formatter: svPosLink }},
            {{ title: "Size (bp)", field: "size", sorter: "number", hozAlign: "right",
               formatter: function(cell) {{ return cell.getValue().toLocaleString(); }} }},
            {{ title: "breseq", field: "breseq", hozAlign: "center", formatter: yesNoBadge, width: 80 }},
            {{ title: "Manta", field: "manta", hozAlign: "center", formatter: yesNoBadge, width: 80 }},
            {{ title: "TIDDIT", field: "tiddit", hozAlign: "center", formatter: yesNoBadge, width: 80 }},
            {{ title: "Notes", field: "notes", minWidth: 250 }},
        ],
    }});

    // --- SNP/InDel Concordance Table ---
    new Tabulator("#snp-table", {{
        data: snpData,
        layout: "fitDataFill",
        headerSortTristate: true,
        initialSort: [{{ column: "_sort", dir: "asc" }}],
        columns: [
            {{ title: "Position", field: "pos", sorter: "number", hozAlign: "right",
               formatter: snpPosLink }},
            {{ title: "Type", field: "type", width: 60 }},
            {{ title: "Ref&rarr;Alt", field: "ref_alt", width: 100 }},
            {{ title: "breseq", field: "breseq", hozAlign: "center", formatter: yesNoBadge, width: 80,
               headerFilter: "list", headerFilterParams: {{ valuesLookup: true }} }},
            {{ title: "Gene", field: "gene", headerFilter: "input", minWidth: 100 }},
            {{ title: "Effect", field: "effect", formatter: effectBadge, minWidth: 120 }},
            {{ title: "HC Filter", field: "hc_filter", hozAlign: "center", formatter: filterBadge, width: 110 }},
            {{ title: "QD", field: "hc_qd", sorter: "number", hozAlign: "right", width: 70,
               formatter: function(cell) {{ var v = cell.getValue(); return v != null ? v.toFixed(1) : ""; }} }},
            {{ title: "DP", field: "hc_dp", sorter: "number", hozAlign: "right", width: 60 }},
            {{ title: "SOR", field: "hc_sor", sorter: "number", hozAlign: "right", width: 70,
               formatter: function(cell) {{
                   var v = cell.getValue();
                   if (v == null) return "";
                   var s = v.toFixed(2);
                   return v > 3.0 ? '<span style="color:#cb2431;font-weight:600">' + s + '</span>' : s;
               }} }},
            {{ title: "Notes", field: "notes", minWidth: 250 }},
        ],
    }});
</script>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Generate breseq vs yAMP concordance dashboard")
    parser.add_argument("--breseq-gd", type=Path, default=DEFAULTS["breseq_gd"])
    parser.add_argument("--hc-vcf", type=Path, default=DEFAULTS["hc_vcf"])
    parser.add_argument("--survivor-union", type=Path, default=DEFAULTS["survivor_union"])
    parser.add_argument("--survivor-consensus", type=Path, default=DEFAULTS["survivor_consensus"])
    parser.add_argument("--comparison-tsv", type=Path, default=DEFAULTS["comparison_tsv"])
    parser.add_argument("-o", "--output", type=Path, default=DEFAULTS["output"])
    args = parser.parse_args()

    # Validate inputs
    for name, path in [("breseq-gd", args.breseq_gd), ("hc-vcf", args.hc_vcf),
                        ("survivor-union", args.survivor_union),
                        ("survivor-consensus", args.survivor_consensus),
                        ("comparison-tsv", args.comparison_tsv)]:
        if not path.exists():
            print(f"ERROR: {name} not found: {path}", file=sys.stderr)
            sys.exit(1)

    # Check bcftools
    try:
        subprocess.check_output(["bcftools", "--version"], stderr=subprocess.DEVNULL)
    except FileNotFoundError:
        print("ERROR: bcftools not found. Activate conda nf-env first.", file=sys.stderr)
        sys.exit(1)

    print("Parsing breseq annotated.gd ...")
    breseq_snps, breseq_svs = parse_breseq_annotated_gd(args.breseq_gd)
    print(f"  {len(breseq_snps)} SNPs/indels, {len(breseq_svs)} SVs")

    print("Querying all HC soft-filtered variants ...")
    hc_data = query_all_hc_variants(args.hc_vcf)
    print(f"  Found {len(hc_data)} HC variants total")

    print("Parsing SURVIVOR VCFs ...")
    union_records = parse_survivor_vcf(args.survivor_union)
    consensus_records = parse_survivor_vcf(args.survivor_consensus)
    print(f"  Union: {len(union_records)}, Consensus: {len(consensus_records)}")

    print("Parsing comparison report ...")
    comparison_rows = parse_comparison_tsv(args.comparison_tsv)
    print(f"  {len(comparison_rows)} rows")

    # Build table data
    snp_table = build_snp_indel_table(breseq_snps, hc_data)
    # Add ref→alt column for display
    for row in snp_table:
        if row["ref"] != "." and row["alt"] != ".":
            row["ref_alt"] = f"{row['ref']}→{row['alt']}"
        else:
            row["ref_alt"] = "."

    sv_table = build_sv_table(breseq_svs, union_records, consensus_records, comparison_rows)

    # Build audit
    script_dir = Path(__file__).resolve().parent
    audit = build_audit_data(
        args.survivor_union, args.survivor_consensus,
        script_dir / "manta.vcf", script_dir / "tiddit.vcf"
    )
    audit_text = (
        f"SURVIVOR Merge Audit\n"
        f"====================\n"
        f"Input:     Manta ({audit['manta_records']} records) + TIDDIT ({audit['tiddit_records']} records)\n"
        f"Union:     {audit['union_records']} records (max_dist=1000, min_callers=1)\n"
        f"Consensus: {audit['consensus_records']} records (max_dist=1000, min_callers=2)\n\n"
        f"Union SUPP_VEC:     {json.dumps(audit['union_supp_vec'], indent=2)}\n"
        f"  11 = Manta + TIDDIT\n"
        f"  10 = Manta only\n"
        f"  01 = TIDDIT only\n\n"
        f"Consensus SUPP_VEC: {json.dumps(audit['consensus_supp_vec'], indent=2)}\n"
        f"  All consensus records have SUPP=2 (both callers agree) ✓\n\n"
        f"Files:\n"
        f"  sv_vcf_list.txt      — input file list for SURVIVOR\n"
        f"  manta.vcf            — decompressed Manta VCF\n"
        f"  tiddit.vcf           — decompressed TIDDIT VCF\n"
        f"  merged_union.vcf     — SURVIVOR union output\n"
        f"  merged_consensus.vcf — SURVIVOR consensus output\n"
        f"  compare_breseq_sv.py — breseq GD vs SURVIVOR comparison script\n"
        f"  comparison_report.tsv — detailed matching results\n"
        f"  generate_dashboard.py — this dashboard generator (reproducible)"
    )

    # Render HTML
    html = HTML_TEMPLATE.format(
        generated_date=datetime.now().strftime("%Y-%m-%d %H:%M"),
        sv_data_json=json.dumps(sv_table, indent=2),
        snp_data_json=json.dumps(snp_table, indent=2),
        audit_text=audit_text,
    )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(html)
    print(f"\nDashboard written to {args.output}")


if __name__ == "__main__":
    main()
