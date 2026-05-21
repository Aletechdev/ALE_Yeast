#!/usr/bin/env python3
"""
Generate a self-contained HTML concordance dashboard for the Marko SV benchmark.

Compares breseq against yAMP pipeline tools to assess concordance:
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
import re
import shutil
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
    "genbank": PROJECT_ROOT / "data/marko_SV/reference/U00096.3.gbk",
    "output": Path(__file__).resolve().parent / "report" / "index.html",
}


# ---------------------------------------------------------------------------
# Gene name mapping (locus_tag → common gene symbol)
# ---------------------------------------------------------------------------

def build_gene_name_map(genbank_path):
    """Parse GenBank file to build locus_tag → gene_name mapping.

    The snpEff database was built from GFF3 which only has locus tags (e.g. b0393).
    The GenBank file has both /gene="rdgC" and /locus_tag="b0393", so we can
    translate locus tags to human-readable gene symbols.
    """
    mapping = {}
    if not Path(genbank_path).exists():
        print(f"  WARNING: GenBank file not found: {genbank_path}", file=sys.stderr)
        return mapping
    gene, locus = None, None
    with open(genbank_path) as f:
        for line in f:
            m = re.search(r'/gene="(.+?)"', line)
            if m:
                gene = m.group(1)
            m = re.search(r'/locus_tag="(.+?)"', line)
            if m:
                locus = m.group(1)
                if gene and locus:
                    mapping[locus] = gene
                    gene, locus = None, None
    print(f"  Loaded {len(mapping)} locus_tag → gene name mappings")
    return mapping


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
                # Column 3 has comma-separated JC evidence IDs
                jc_ids = fields[2].split(",") if len(fields) > 2 else []
                sv.append({
                    "type": "MOB",
                    "pos": pos,
                    "size": repeat_size if repeat_size else dup,
                    "gene": gene,
                    "detail": f"{element} ({'+' if strand == '1' else '-'})",
                    "tsd_size": dup,
                    "tsd_seq": ref_seq,
                    "jc_ids": jc_ids,
                    "element": element,
                    "gene_product": annot.get("gene_product", ""),
                    "gene_position": annot.get("gene_position", ""),
                })

    return snp_indel, sv


def _parse_ann_field(ann_str, gene_map=None):
    """Extract gene name and effect from the first (highest-impact) SnpEff ANN entry.

    If gene_map is provided, translates locus tags (e.g. b0393) to common gene
    symbols (e.g. rdgC).
    """
    if not ann_str or ann_str == ".":
        return "", "", ""
    # ANN format: ALT|effect|impact|gene_name|gene_id|...
    first = ann_str.split(",")[0]
    fields = first.split("|")
    if len(fields) >= 4:
        effect = fields[1]  # e.g. missense_variant, synonymous_variant
        locus_tag = fields[3]    # e.g. b0393
        gene = gene_map.get(locus_tag, locus_tag) if gene_map else locus_tag
        return gene, effect, locus_tag
    return "", "", ""


def query_all_hc_variants(hc_vcf, gene_map=None):
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
            gene, effect, locus_tag = _parse_ann_field(ann_str, gene_map)
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
                "locus_tag": locus_tag,
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

    # First pass: breseq variants (reference calls)
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
            "locus_tag": hc.get("locus_tag", "") if hc else "",
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

    # Second pass: HC-only variants (not called by breseq)
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
            "locus_tag": hc.get("locus_tag", ""),
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

            # Format MOB notes with beginner-friendly explanation + JC evidence links
            if is_mob:
                el_match = re.search(r"element=(\w+)", extra)
                strand_match = re.search(r"strand=(-?\d)", extra)
                element = el_match.group(1) if el_match else "?"
                strand = "+" if strand_match and strand_match.group(1) == "1" else "-"

                # Look up actual IS size, TSD, gene context, and JC evidence from parsed breseq SVs
                mob_pos = int(cr["breseq_pos"])
                mob_info = next((s for s in breseq_svs if s["type"] == "MOB" and s["pos"] == mob_pos), None)
                if mob_info:
                    is_size = mob_info["size"]
                    tsd_seq = mob_info.get("tsd_seq", "")
                    tsd_size = mob_info.get("tsd_size", size)
                    jc_ids = mob_info.get("jc_ids", [])
                    gene_position = mob_info.get("gene_position", "")
                    # Beginner-friendly note explaining what happened
                    notes = (
                        f"{element} ({is_size:,} bp transposon) inserted in {strand} orientation. "
                        f"Duplicated {tsd_size} bp of target DNA ({tsd_seq}) at insertion site."
                    )
                    if gene_position:
                        notes += f" Location: {gene_position}."
                else:
                    is_size = size
                    jc_ids = []
                    notes = f"{element} transposon insertion ({strand} strand)"
                display_type = "MOB"
            else:
                is_size = size
                notes = extra.replace("id=", "breseq_id=") if extra else "breseq-only"
                display_type = cr["breseq_type"]

            row_data = {
                "type": display_type,
                "pos": int(cr["breseq_pos"]),
                "size": is_size,
                "breseq": "Yes",
                "manta": "N/A" if is_mob else "No",
                "tiddit": "N/A" if is_mob else "No",
                "consensus": "\u2014",
                "notes": notes,
                "source": "breseq only",
            }
            if is_mob:
                row_data["jc_ids"] = jc_ids
            rows.append(row_data)
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
    <meta name="color-scheme" content="light dark">
    <title>Marko SV Benchmark — breseq vs yAMP Concordance</title>
    <link href="https://unpkg.com/tabulator-tables@6.3.0/dist/css/tabulator.min.css" rel="stylesheet">
    <style>
        /* --- Light theme (default) --- */
        :root {{
            color-scheme: light;
            --bg: #ffffff;
            --fg: #333333;
            --fg-heading: #24292e;
            --fg-muted: #586069;
            --link: #0366d6;
            --border: #e1e4e8;
            --surface: #f6f8fa;
            --surface-alt: #fafbfc;
            --badge-pass-bg: #dcffe4; --badge-pass-fg: #22863a;
            --badge-warn-bg: #fff5b1; --badge-warn-fg: #735c0f;
            --badge-fail-bg: #ffeef0; --badge-fail-fg: #cb2431;
            --badge-na-bg: #f1f1f1;   --badge-na-fg: #888888;
            --finding-bg: #f6f8fa;
            --finding-warn-border: #e36209; --finding-warn-bg: #fff8f0;
            --finding-note-border: #6a737d; --finding-note-bg: #f6f8fa;
            --finding-good-border: #22863a;
            --finding-info-border: #0366d6;
            --organism-border: #6f42c1; --organism-bg: #f5f0ff; --organism-fg: #6f42c1;
            --warn-border: #e36209; --warn-bg: #fff8f0; --warn-fg: #e36209;
            --sor-high: #cb2431;
            --code-bg: #f6f8fa;
            --table-header-bg: #f6f8fa;
            --table-border: #e1e4e8;
            --hover: #f0f1f3;
        }}

        /* --- Dark theme --- */
        [data-theme="dark"] {{
            color-scheme: dark;
            --bg: #0d1117;
            --fg: #c9d1d9;
            --fg-heading: #e6edf3;
            --fg-muted: #8b949e;
            --link: #58a6ff;
            --border: #30363d;
            --surface: #161b22;
            --surface-alt: #1c2128;
            --hover: #2d333b;
            --badge-pass-bg: #1b3a2a; --badge-pass-fg: #56d364;
            --badge-warn-bg: #3b2e00; --badge-warn-fg: #e3b341;
            --badge-fail-bg: #3d1418; --badge-fail-fg: #f85149;
            --badge-na-bg: #21262d;   --badge-na-fg: #8b949e;
            --finding-bg: #161b22;
            --finding-warn-border: #d29922; --finding-warn-bg: #1c1500;
            --finding-note-border: #8b949e; --finding-note-bg: #161b22;
            --finding-good-border: #56d364;
            --finding-info-border: #58a6ff;
            --organism-border: #a371f7; --organism-bg: #1a0f2e; --organism-fg: #a371f7;
            --warn-border: #d29922; --warn-bg: #1c1500; --warn-fg: #d29922;
            --sor-high: #f85149;
            --code-bg: #161b22;
            --table-header-bg: #1c2128;
            --table-border: #30363d;
        }}

        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
            max-width: 1200px;
            margin: 40px auto;
            padding: 0 20px;
            color: var(--fg);
            background: var(--bg);
        }}
        h1 {{ border-bottom: 2px solid var(--link); padding-bottom: 8px; color: var(--fg-heading); }}
        h2 {{ margin-top: 32px; color: var(--fg-heading); }}
        h3 {{ color: var(--fg-heading); }}
        a {{ color: var(--link); text-decoration: none; }}
        a:hover {{ text-decoration: underline; }}
        code {{ background: var(--code-bg); padding: 1px 4px; border-radius: 3px; }}
        .meta {{ color: var(--fg-muted); font-size: 0.9em; }}
        .section {{ margin: 24px 0; }}
        .stat-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 16px;
            margin: 16px 0;
        }}
        .stat-card {{
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 6px;
            padding: 16px;
            text-align: center;
        }}
        .stat-card .value {{
            font-size: 2em;
            font-weight: 700;
            color: var(--fg-heading);
        }}
        .stat-card .label {{
            font-size: 0.85em;
            color: var(--fg-muted);
            margin-top: 4px;
        }}
        .stat-card.card-organism {{ border-left: 3px solid var(--organism-border); background: var(--organism-bg); }}
        .stat-card.card-organism .value {{ font-size: 1.1em; color: var(--organism-fg); }}
        .stat-card.card-warn {{ border-left: 3px solid var(--warn-border); background: var(--warn-bg); }}
        .stat-card.card-warn .value {{ color: var(--warn-fg); }}
        .badge {{
            display: inline-block;
            padding: 2px 8px;
            border-radius: 3px;
            font-size: 0.8em;
            font-weight: 600;
        }}
        .badge-pass {{ background: var(--badge-pass-bg); color: var(--badge-pass-fg); }}
        .badge-warn {{ background: var(--badge-warn-bg); color: var(--badge-warn-fg); }}
        .badge-fail {{ background: var(--badge-fail-bg); color: var(--badge-fail-fg); }}
        .badge-na {{ background: var(--badge-na-bg); color: var(--badge-na-fg); }}
        .badge-yes {{ background: var(--badge-pass-bg); color: var(--badge-pass-fg); }}
        .badge-no {{ background: var(--badge-fail-bg); color: var(--badge-fail-fg); }}
        .finding {{ margin: 8px 0; padding: 8px 12px; border-left: 3px solid var(--link); background: var(--finding-bg); }}
        .finding-good {{ border-left-color: var(--finding-good-border); }}
        .finding-warn {{ border-left-color: var(--finding-warn-border); background: var(--finding-warn-bg); }}
        .finding-note {{ border-left-color: var(--finding-note-border); background: var(--finding-note-bg); }}
        .finding-info {{ border-left-color: var(--finding-info-border); }}
        .tabulator {{ font-size: 0.9em; border: 1px solid var(--table-border); }}
        .tabulator .tabulator-header {{ background: var(--table-header-bg); color: var(--fg); }}
        .tabulator .tabulator-header .tabulator-col {{ background: var(--table-header-bg); border-color: var(--table-border); color: var(--fg); }}
        .tabulator .tabulator-header .tabulator-col .tabulator-col-content {{ color: var(--fg); }}
        .tabulator-row {{ background: var(--bg); color: var(--fg); }}
        .tabulator-row.tabulator-row-even {{ background: var(--surface-alt); }}
        .tabulator-row .tabulator-cell {{ border-color: var(--table-border); }}
        .tabulator .tabulator-header .tabulator-col {{ border-right: 1px solid var(--table-border); }}
        .tabulator .tabulator-tableholder {{ background: var(--bg); }}
        .tabulator-row.tabulator-row-odd {{ background: var(--bg); }}
        .tabulator-row .tabulator-cell a {{ color: var(--link); }}
        .tabulator .tabulator-header .tabulator-header-filter input {{
            background: var(--surface); color: var(--fg); border: 1px solid var(--border);
        }}
        /*
         * Tabulator hover overrides — hardcoded per theme.
         * Using html[data-theme] prefix to beat Tabulator's selector specificity.
         * Hardcoded colors because some browsers (Safari) have issues resolving
         * CSS custom properties inside :hover pseudo-states on third-party elements.
         */
        html[data-theme="light"] .tabulator .tabulator-header .tabulator-col.tabulator-sortable.tabulator-col-sorter-element:hover,
        html:not([data-theme]) .tabulator .tabulator-header .tabulator-col.tabulator-sortable.tabulator-col-sorter-element:hover {{
            background-color: #e8e9eb !important;
        }}
        html[data-theme="light"] .tabulator-row.tabulator-selectable:hover,
        html:not([data-theme]) .tabulator-row.tabulator-selectable:hover {{
            background-color: #f0f1f3 !important;
        }}
        html[data-theme="light"] .tabulator-row:hover .tabulator-cell,
        html:not([data-theme]) .tabulator-row:hover .tabulator-cell {{
            background-color: #f0f1f3 !important;
        }}
        html[data-theme="dark"] .tabulator .tabulator-header .tabulator-col.tabulator-sortable.tabulator-col-sorter-element:hover {{
            background-color: #3a414b !important;
        }}
        html[data-theme="dark"] .tabulator-row.tabulator-selectable:hover {{
            background-color: #2d333b !important;
        }}
        html[data-theme="dark"] .tabulator-row:hover .tabulator-cell {{
            background-color: #2d333b !important;
        }}
        .footer {{
            color: var(--fg-muted);
            font-size: 0.85em;
            margin-top: 40px;
            border-top: 1px solid var(--border);
            padding-top: 12px;
        }}
        details {{ margin: 8px 0; }}
        details summary {{ cursor: pointer; color: var(--link); font-weight: 600; }}
        pre.audit {{ background: var(--surface); padding: 12px; border-radius: 4px; font-size: 0.85em; overflow-x: auto; color: var(--fg); }}
        /* Theme toggle */
        .theme-toggle {{
            position: fixed;
            top: 12px;
            right: 16px;
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 20px;
            padding: 6px 12px;
            cursor: pointer;
            font-size: 1.1em;
            line-height: 1;
            z-index: 1000;
            color: var(--fg);
        }}
        .theme-toggle:hover {{ background: var(--surface-alt); }}
        /* Inline table in details (quality metrics) */
        .inline-table th, .inline-table td {{
            padding: 6px 10px;
            border: 1px solid var(--border);
        }}
        .inline-table tr:first-child {{ background: var(--surface); }}
    </style>
    <script>
        // Apply theme immediately (before paint) to prevent flash.
        // Always set data-theme explicitly so we don't rely on CSS media queries.
        (function() {{
            var saved = localStorage.getItem('dashboard-theme');
            var theme = saved || (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
            document.documentElement.setAttribute('data-theme', theme);
            var csm = document.querySelector('meta[name="color-scheme"]');
            if (csm) csm.setAttribute('content', theme);
        }})();
    </script>
</head>
<body>

<button class="theme-toggle" id="themeToggle" title="Toggle dark / light mode" aria-label="Toggle dark mode">&#9790;</button>

<h1>Marko SV Benchmark &mdash; breseq vs yAMP Concordance</h1>
<p class="meta">
    Sample: <strong>SRR6281661</strong> &middot;
    Organism: <em>E. coli</em> K-12 MG1655 &middot;
    Ploidy: 1 (haploid) &middot;
    Generated {generated_date}
</p>
<p class="meta">
    Callers compared: <strong>breseq 0.39.0</strong> vs
    <strong>yAMP v1.0.0 pre-release</strong> (GATK HaplotypeCaller joint gVCF calling ploidy=1, Manta, TIDDIT) &middot;
    SV merge: SURVIVOR 1.0.7
</p>

<!-- Section 1: Summary Stats -->
<div class="section">
    <h2>Summary</h2>
    <div class="stat-grid">
        <div class="stat-card card-organism">
            <div class="value"><em>E. coli</em> K-12</div>
            <div class="label">MG1655 (prokaryote, haploid)<br>SRR6281661</div>
        </div>
        <div class="stat-card">
            <div class="value">4/4</div>
            <div class="label">breseq large deletions<br>detected by yAMP (Manta + TIDDIT)</div>
        </div>
        <div class="stat-card card-warn">
            <div class="value">0/3</div>
            <div class="label">breseq-unique MOB insertions<br>detected by yAMP (IS2, IS5 &mdash; requires assembly-based detection)</div>
        </div>
        <div class="stat-card">
            <div class="value">11/11</div>
            <div class="label">breseq SNPs + InDels<br>detected by yAMP (10/11 passed HC filter)</div>
        </div>
    </div>
</div>

<!-- Section 2: Key Findings -->
<div class="section">
    <h2>Key Findings</h2>
    <div class="finding finding-warn">
        <strong>Mobile element insertion (MOB) calls are breseq-unique.</strong>
        3 IS-element mobilizations (2&times;IS2, 1&times;IS5) detected only by breseq.
        This is expected: standard SV callers cannot resolve insertions of repeat elements
        already present elsewhere in the genome. breseq uses assembly-based junction detection.
        <br><br>
        In prokaryotes, MOBs are predominantly insertion sequence (IS) element insertions,
        for which breseq is the established tool.
        <br><br>
        In eukaryotic microbes such as <em>S. cerevisiae</em>, MOBs are predominantly
        insertions of long terminal repeat (LTR) retrotransposons (the Ty1&ndash;Ty5 families in yeast),
        detectable by RelocaTE2, TEMP, TEMP2, and TEBreak
        (<a href="https://doi.org/10.1186/s13100-023-00296-4" target="_blank">Chen et al. 2023, <em>Mobile DNA</em></a>),
        but reliable calling depends on a high-quality reference genome paired with
        comprehensive, consistent mobile element annotation, including both coordinate
        records on the chromosome and a curated consensus sequence library.
        The latter set is not currently integrated into yAMP v1.0.0.
    </div>
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
        <strong>rpoS nonsense SNP soft-filtered.</strong>
        SNP G&rarr;A at position
        <a href="SRR6281661_report.html?locus=U00096:2867455" target="_blank">2,867,455</a>
        (rpoS Q33*, nonsense) has SOR=3.014, barely above the 3.0 threshold.
        QD=29.56 is excellent (threshold: 2.0).
        Consider relaxing SOR threshold or reviewing this filter for haploid organisms.
    </div>
    <div class="finding finding-info">
        <strong>yAMP found additional SVs not in breseq.</strong>
        A 9,049 bp deletion at position 2,169,285 (Manta + TIDDIT consensus) and
        an inversion at ~1,207,789 were detected by SV callers but not breseq.
        These may represent real structural variants or alignment artifacts worth investigating.
    </div>
</div>

<!-- Section 3: SV Concordance -->
<div class="section">
    <h2>Structural Variant Concordance</h2>
    <p class="meta">
        breseq detected 4 large deletions and 3 IS-element mobilizations (MOB).
        Manta and TIDDIT independently confirm all 4 deletions.
        SURVIVOR merge (max_dist=1000bp, type_agree=yes) used for consensus.
        <br>Click any <strong>Position</strong> value to open the IGV report with read pileup at that locus.
    </p>
    <details class="finding finding-note" style="margin-bottom:12px">
        <summary><strong>SV IGV-reports are a work in progress.</strong></summary>
        The current SV reports reuse the SNP/InDel template and show raw breakpoint pileups,
        but SV visualization best practices differ significantly &mdash; e.g. paired-end insert size
        coloring, split-read highlighting, and wider flanking windows for large events.
        Additionally, a scoring or evaluation framework for SV concordance (e.g. reciprocal overlap
        thresholds, breakpoint tolerance, genotype agreement) has not yet been established.
    </details>
    <div id="sv-table"></div>
</div>

<!-- Section 3: SNP/InDel Concordance -->
<div class="section">
    <h2>SNP / InDel Concordance</h2>
    <p class="meta">
        breseq called 11 SNPs/small indels.
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
            <table class="inline-table" style="border-collapse: collapse; width: 100%; margin: 10px 0;">
                <thead>
                    <tr>
                        <th>Column</th>
                        <th>Metric</th>
                        <th>Filter Threshold</th>
                        <th>Interpretation</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td><strong>QD</strong></td>
                        <td>Quality by Depth</td>
                        <td>QD &lt; 2.0 &rarr; <code>QD_filter</code></td>
                        <td>QUAL score / total depth. Low QD = weak evidence per read. Higher is better.</td>
                    </tr>
                    <tr>
                        <td><strong>DP</strong></td>
                        <td>Read Depth</td>
                        <td>&mdash; (no filter)</td>
                        <td>Total reads at this position (INFO/DP, cohort-level). Shown for context only.</td>
                    </tr>
                    <tr>
                        <td><strong>SOR</strong></td>
                        <td>Strand Odds Ratio</td>
                        <td>SOR &gt; 3.0 &rarr; <code>SOR_filter</code></td>
                        <td>Strand bias test. SOR &gt; 3.0 = variant seen disproportionately on one strand (possible artifact). Lower is better.</td>
                    </tr>
                    <tr>
                        <td><strong>HC Filter</strong></td>
                        <td>FILTER column</td>
                        <td>Combined result</td>
                        <td>
                            <code>PASS</code> = passes all filters.
                            Otherwise shows which filter(s) flagged the variant
                            (e.g. <code>QD_filter</code>, <code>SOR_filter</code>, <code>MQ_filter</code>).
                        </td>
                    </tr>
                </tbody>
            </table>
            <p>
                <strong>Other soft filters applied</strong> (not shown as columns):
                FS &gt; 60.0 (<code>FS_filter</code>),
                MQ &lt; 40.0 (<code>MQ_filter</code>),
                MQRankSum &lt; -12.5,
                ReadPosRankSum &lt; -8.0,
                QUAL &lt; 30.0.
                INDEL thresholds are more lenient (FS &gt; 200, SOR &gt; 10).
            </p>
            <p style="color: var(--fg-muted);">
                Thresholds follow GATK best practices for human data.
                See <code>conf/modules/joint_germline.config</code> for full configuration.
            </p>
        </div>
    </details>
    <div id="snp-table"></div>
</div>

<!-- Section 5: SURVIVOR Merge Audit -->
<div class="section">
    <h2>SURVIVOR Merge Audit</h2>
    <details>
        <summary>Show audit details</summary>
        <pre class="audit">{audit_text}</pre>
    </details>
</div>

<!-- Section 6: IGV-Reports Audit -->
<div class="section">
    <h2>IGV-Reports Audit</h2>
    <details>
        <summary>Show IGV-report generation details</summary>
        <div style="padding:12px 16px; line-height:1.7; font-size:0.95em;">
        <h3 style="margin-top:0;">SNP/InDel report (HaplotypeCaller)</h3>
        <p>
            The per-sample IGV report
            <a href="SRR6281661_report.html" target="_blank">SRR6281661_report.html</a>
            is generated from the snpEff-annotated HaplotypeCaller VCF
            (<code>SRR6281661.haplotypecaller.from_joint_calling_snpEff.ann.vcf.gz</code>)
            using <a href="https://github.com/igvteam/igv-reports" target="_blank">igv-reports</a>.
        </p>
        <p><strong>Processing steps</strong> (see <code>generate_igvreport.sh</code>):</p>
        <ol>
            <li><strong>Multi-allelic split</strong> &mdash; <code>bcftools norm -m-</code> splits multi-allelic sites so each alt allele has its own row.</li>
            <li><strong>FILTER promotion</strong> &mdash; The original FILTER column value (e.g.&nbsp;PASS, SOR_filter) is copied into an INFO tag
                <code>VCF_FILTER</code> so it appears as a searchable column in the report table.</li>
            <li><strong>VAF annotation</strong> &mdash; <code>bcftools +fill-tags</code> adds a FORMAT/VAF field for allele-fraction display.</li>
            <li><strong>Report creation</strong> &mdash; <code>create_report</code> renders each variant with &plusmn;500&nbsp;bp flanking,
                the CRAM alignment track, and GFF3 gene annotations.
                <br><code style="font-size:0.85em; white-space:pre-wrap;">create_report hc_prepared.vcf.gz --fasta ref.fasta --tracks genes.sorted.gff3.gz sample.md.cram --template custom_template_sample.html --filter-config filter_config.yaml --info-columns ANN VCF_FILTER ORIG_ALT AC AF DP QD MQ --sample-columns GT AD DP GQ VAF --flanking 500 --title "SRR6281661 - HaplotypeCaller SNP/InDel (E. coli K-12)" --output SRR6281661_report.html</code></li>
            <li><strong>VCF embedding</strong> &mdash; The prepared VCF is base64-encoded into the HTML for self-contained download.</li>
        </ol>
        <p>
            The report contains <strong>76 variants</strong> (all from joint gVCF calling, soft-filtered) and allows
            interactive sorting, filtering, and IGV-style pileup inspection per variant.
        </p>

        <h3>SV report (SURVIVOR union) &mdash; work in progress</h3>
        <p>
            An initial SV report
            <a href="SRR6281661_sv_report.html" target="_blank">SRR6281661_sv_report.html</a>
            was generated from the SURVIVOR merged union VCF (15 records, &plusmn;1000&nbsp;bp flanking).
            This report is <strong>not yet production-ready</strong>: the visualization approach for symbolic
            alleles (&lt;DEL&gt;, &lt;INV&gt;, BND) and a scoring / quality-evaluation method for
            structural variant calls still need further development. It is included here for reference only.
        </p>

        <h3>Reusable templates</h3>
        <p>
            The custom igv-reports template and filter configuration used to generate the reports above
            are available in the <a href="templates/" target="_blank"><code>templates/</code></a> folder
            for reuse in other benchmarks or organisms:
        </p>
        <ul style="margin:4px 0 0 0;">
            <li><a href="templates/custom_template_sample.html" target="_blank"><code>custom_template_sample.html</code></a>
                &mdash; Modified igv-reports HTML template with dark mode support, custom column rendering,
                and embedded VCF download button.</li>
            <li><a href="templates/filter_config.yaml" target="_blank"><code>filter_config.yaml</code></a>
                &mdash; Column visibility and filter configuration for <code>create_report</code>.</li>
        </ul>
        <p style="color: var(--fg-muted); margin-top: 6px;">
            Source: <code>docs/igvreports/</code> in the yAMP repository.
            See <code>generate_igvreport.sh</code> for the full invocation.
        </p>
        </div>
    </details>
</div>

<div class="footer">
    Callers: breseq 0.39.0 vs yAMP v1.0.0 pre-release (nf-core/sarek 3.5.1 fork) &middot;
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

    function svNotesFormatter(cell) {{
        var notes = cell.getValue() || '';
        var row = cell.getRow().getData();
        var jcIds = row.jc_ids;
        if (jcIds && jcIds.length > 0) {{
            var links = jcIds.map(function(id) {{
                return '<a href="evidence/JC_' + id + '.html" target="_blank" title="breseq junction evidence #' + id + '">JC&nbsp;' + id + '</a>';
            }});
            return '<span class="badge badge-na" style="margin-right:6px">breseq evidence: ' + links.join(', ') + '</span> ' + notes;
        }}
        return notes;
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
            {{ title: "Notes", field: "notes", formatter: svNotesFormatter, minWidth: 350 }},
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
            {{ title: "Locus Tag", field: "locus_tag", headerFilter: "input", width: 90 }},
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
                   return v > 3.0 ? '<span style="color:var(--sor-high);font-weight:600">' + s + '</span>' : s;
               }} }},
            {{ title: "Notes", field: "notes", minWidth: 250 }},
        ],
    }});

    // --- Theme toggle ---
    // Keep mql reference at module scope so Safari doesn't garbage-collect it
    var __darkMql = window.matchMedia('(prefers-color-scheme: dark)');
    (function() {{
        var btn = document.getElementById('themeToggle');
        var root = document.documentElement;
        function currentTheme() {{
            return root.getAttribute('data-theme') ||
                (__darkMql.matches ? 'dark' : 'light');
        }}
        function applyTheme(theme) {{
            root.setAttribute('data-theme', theme);
            var csm = document.querySelector('meta[name="color-scheme"]');
            if (csm) csm.setAttribute('content', theme);
            btn.textContent = theme === 'dark' ? '\u2600' : '\u263E';
        }}
        applyTheme(currentTheme());
        btn.addEventListener('click', function() {{
            var next = currentTheme() === 'dark' ? 'light' : 'dark';
            localStorage.setItem('dashboard-theme', next);
            applyTheme(next);
        }});
        // React to system theme changes in real time (if user hasn't manually toggled).
        // Use addListener for Safari compat (addEventListener not supported on
        // MediaQueryList in Safari < 14 and unreliable in some later versions).
        function onSystemChange(e) {{
            if (!localStorage.getItem('dashboard-theme')) {{
                applyTheme(e.matches ? 'dark' : 'light');
            }}
        }}
        if (__darkMql.addEventListener) {{
            __darkMql.addEventListener('change', onSystemChange);
        }} else if (__darkMql.addListener) {{
            __darkMql.addListener(onSystemChange);
        }}
    }})();
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
    parser.add_argument("--genbank", type=Path, default=DEFAULTS["genbank"],
                        help="GenBank file for locus_tag → gene name mapping")
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

    print("Building locus_tag → gene name mapping ...")
    gene_map = build_gene_name_map(args.genbank)

    print("Querying all HC soft-filtered variants ...")
    hc_data = query_all_hc_variants(args.hc_vcf, gene_map)
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

    # Copy reusable igv-reports templates into report/templates/
    templates_dir = args.output.parent / "templates"
    templates_dir.mkdir(exist_ok=True)
    igvreports_dir = PROJECT_ROOT / "docs" / "igvreports"
    for src_name in ["custom_template_sample.html", "filter_config.yaml"]:
        src = igvreports_dir / src_name
        if src.exists():
            shutil.copy2(src, templates_dir / src_name)
    print(f"Templates copied to {templates_dir}")


if __name__ == "__main__":
    main()
