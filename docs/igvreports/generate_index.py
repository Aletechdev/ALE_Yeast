#!/usr/bin/env python3
"""
Multi-Caller Mutation Report Index Generator

Reads MultiQC summary TSVs and generates a rich static HTML dashboard
using Jinja2 templates with Tabulator.js tables. Links to existing
igv-reports HTML files for alignment drill-down.

Optionally includes CN heatmaps and SV cohort matrices when
--cnv-sv-data-dir is provided (expects CSV files from cn_cohort_matrix.py
and sv_cohort_matrix.py).

Usage (standalone):
    python generate_index.py \
        --multiqc-dir output_all/multiqc/multiqc_data \
        --output docs/igvreports/demo/index.html \
        --sample-reports-dir docs/igvreports/demo/samples \
        --cohort-report docs/igvreports/demo/cohort_report.html

Usage with CN/SV data:
    python generate_index.py \
        --multiqc-dir output_ottilie/multiqc/multiqc_data \
        --output docs/igvreports/ottilie_4samples/index.html \
        --cnv-sv-data-dir docs/igvreports/ottilie_4samples/data

Usage (from Nextflow GENERATE_INDEX process):
    Called with paths resolved by the workflow.
"""

import argparse
import csv
import json
import re
from datetime import datetime
from pathlib import Path

import pandas as pd
from jinja2 import Environment, FileSystemLoader

# ---------------------------------------------------------------------------
# Caller suffix mapping: MultiQC sample name suffix -> display name
# Longest suffixes first so greedy matching works correctly.
# ---------------------------------------------------------------------------
CALLER_SUFFIXES = [
    ("haplotypecaller.from_joint_calling.hard_filtered", None),  # skip hard-filtered rows
    ("haplotypecaller.from_joint_calling", "HaplotypeCaller"),  # soft-filtered (all non-ref variants)
    ("freebayes.quality_filtered.normal", None),  # skip filtered rows
    ("manta.diploid_sv", "Manta"),
    ("deepvariant", "DeepVariant"),
    ("freebayes", "FreeBayes"),
    ("cnvcall", "CNVKit"),
    ("tiddit", "TIDDIT"),
]

# Which callers to include in the POC dashboard
TARGET_CALLERS = {"HaplotypeCaller", "CNVKit", "TIDDIT", "Manta"}


def parse_sample_caller(name: str) -> tuple[str | None, str | None]:
    """Extract (sample_id, caller_display_name) from a MultiQC sample name.

    Examples:
        'A0-F0-I1-R1.cnvcall' -> ('A0-F0-I1-R1', 'CNVKit')
        'A0-F0-I1-R1.haplotypecaller.from_joint_calling' -> ('A0-F0-I1-R1', 'HaplotypeCaller')
        'HaplotypeCaller_joint_calling_soft_filtered' -> (None, None)  # not a per-sample row
    """
    for suffix, display in CALLER_SUFFIXES:
        if name.endswith("." + suffix):
            sample_id = name[: -(len(suffix) + 1)]
            return sample_id, display
    return None, None


def classify_sample(sample_id: str) -> dict:
    """Classify a sample as Ancestral or Evolved and extract ALE lineage.

    Supports both CEN.PK naming (A0-F0-I1-R1) and Ottilie naming
    (CBR110-15-R3a, Carmaphycin-R9-2, NODRUG-GM2, etc.).
    """
    # CEN.PK ALE naming
    if sample_id.startswith("A0-"):
        return {"type": "Ancestral", "lineage": "CEN.PK parent"}
    m = re.match(r"^(A\d+)-F(\d+)", sample_id)
    if m:
        return {"type": "Evolved", "lineage": f"{m.group(1)} (Flask {m.group(2)})"}
    # Ottilie / generic naming: no-drug control vs evolved
    if "NODRUG" in sample_id.upper():
        return {"type": "Ancestral", "lineage": sample_id}
    return {"type": "Evolved", "lineage": sample_id}


# ---------------------------------------------------------------------------
# Data loading from MultiQC TSVs
# ---------------------------------------------------------------------------

def load_bcftools_stats(multiqc_dir: Path) -> pd.DataFrame:
    """Load and parse multiqc_bcftools_stats.txt.

    Returns DataFrame with columns:
        sample, caller, n_records, n_snps, n_indels, tstv
    """
    path = multiqc_dir / "multiqc_bcftools_stats.txt"
    df = pd.read_csv(path, sep="\t")

    rows = []
    for _, row in df.iterrows():
        sample_id, caller = parse_sample_caller(row["Sample"])
        if sample_id is None or caller is None:
            continue
        if caller not in TARGET_CALLERS:
            continue
        rows.append({
            "sample": sample_id,
            "caller": caller,
            "n_records": int(row.get("number_of_records", 0)),
            "n_snps": int(row.get("number_of_SNPs", 0)),
            "n_indels": int(row.get("number_of_indels", 0)),
            "tstv": float(row.get("tstv", 0)),
        })
    return pd.DataFrame(rows)


def get_joint_vcf_variant_count(multiqc_dir: Path) -> int | None:
    """Extract variant count from the joint HaplotypeCaller VCF in MultiQC.

    Looks for 'HaplotypeCaller_joint_calling_soft_filtered' in bcftools stats.
    Returns the number_of_records, or None if not found.
    """
    path = multiqc_dir / "multiqc_bcftools_stats.txt"
    if not path.exists():
        return None
    df = pd.read_csv(path, sep="\t")
    joint_rows = df[df["Sample"].str.contains("joint_calling_soft_filtered", na=False)]
    if joint_rows.empty:
        return None
    return int(joint_rows.iloc[0].get("number_of_records", 0))


def get_joint_vcf_pass_count(joint_vcf: Path | None) -> int | None:
    """Count PASS variants in the joint VCF using bcftools."""
    if joint_vcf is None or not joint_vcf.exists():
        return None
    import subprocess
    try:
        result = subprocess.run(
            ["bcftools", "view", "-f", "PASS", "-H", str(joint_vcf)],
            capture_output=True, text=True, timeout=60,
        )
        return result.stdout.count("\n")
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return None


def get_prepared_vcf_counts(prepared_vcf: Path | None) -> tuple[int | None, int | None]:
    """Count total and PASS variants in the prepared (post-norm) VCF.

    Returns (total, pass_count) or (None, None) if unavailable.
    """
    if prepared_vcf is None or not prepared_vcf.exists():
        return None, None
    import subprocess
    try:
        total_result = subprocess.run(
            ["bcftools", "view", "-H", str(prepared_vcf)],
            capture_output=True, text=True, timeout=60,
        )
        total = total_result.stdout.count("\n")
        pass_result = subprocess.run(
            ["bcftools", "view", "-f", "PASS", "-H", str(prepared_vcf)],
            capture_output=True, text=True, timeout=60,
        )
        pass_count = pass_result.stdout.count("\n")
        return total, pass_count
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return None, None


def load_pass_stats(pass_stats_files: list[Path] | None) -> dict[tuple[str, str], dict]:
    """Load PASS filter stats TSVs into a lookup dict.

    Returns {(sample, caller): {"total": int, "pass": int}}
    """
    if not pass_stats_files:
        return {}
    import csv
    lookup = {}
    for path in pass_stats_files:
        if not path.exists():
            continue
        with open(path) as f:
            reader = csv.DictReader(f, delimiter="\t")
            for row in reader:
                key = (row["sample"], row["caller"])
                lookup[key] = {"total": int(row["total"]), "pass": int(row["pass"])}
    return lookup


def load_snpeff_stats(multiqc_dir: Path) -> pd.DataFrame:
    """Load and parse multiqc_snpeff.txt.

    Returns DataFrame with columns:
        sample, caller, n_variants, high, moderate, low
    """
    path = multiqc_dir / "multiqc_snpeff.txt"
    df = pd.read_csv(path, sep="\t")

    # SnpEff uses _snpEff suffix appended to the bcftools-style name
    rows = []
    for _, row in df.iterrows():
        name = row["Sample"]
        # Strip _snpEff suffix if present
        if name.endswith("_snpEff"):
            name = name[: -len("_snpEff")]

        sample_id, caller = parse_sample_caller(name)
        if sample_id is None or caller is None:
            continue
        if caller not in TARGET_CALLERS:
            continue
        def safe_int(val, default=0):
            try:
                return int(val) if pd.notna(val) else default
            except (ValueError, TypeError):
                return default

        rows.append({
            "sample": sample_id,
            "caller": caller,
            "n_variants": safe_int(row.get("Number_of_variants_before_filter")),
            "high": safe_int(row.get("HIGH")),
            "moderate": safe_int(row.get("MODERATE")),
            "low": safe_int(row.get("LOW")),
        })
    return pd.DataFrame(rows)


def load_general_stats(multiqc_dir: Path, known_samples: set[str] | None = None) -> pd.DataFrame:
    """Load multiqc_general_stats.txt, keeping only sample-level rows.

    Sample-level rows have no space+dot suffix (e.g., 'A0-F0-I1-R1').
    Per-lane rows look like 'A0-F0-I1-R1 .Lane 1 Read1'.
    Per-caller rows look like 'A0-F0-I1-R1 .cnvkit'.

    If known_samples is provided, use it to filter. Otherwise fall back to
    pattern matching (no spaces + ALE naming or known_samples).
    """
    path = multiqc_dir / "multiqc_general_stats.txt"
    df = pd.read_csv(path, sep="\t")

    # Exclude rows with spaces (per-lane, per-caller breakdown rows)
    no_space = ~df["Sample"].str.contains(" ", na=False)

    if known_samples:
        # Use the known sample set from bcftools stats
        mask = no_space & df["Sample"].isin(known_samples)
    else:
        # Fallback: ALE pattern only
        mask = no_space & df["Sample"].str.match(r"^A\d+-F\d+-I\d+-R\d+$", na=False)

    df = df[mask].copy()
    df = df.rename(columns={"Sample": "sample"})

    # Select relevant columns (they may have module prefixes)
    cols = {
        "sample": "sample",
        "gatk4_markduplicates_mark_duplicates-PERCENT_DUPLICATION": "dup_pct",
        "samtools_flagstat_stats-reads_mapped_percent": "mapped_pct",
        "mosdepth-median_coverage": "median_coverage",
        "samtools_flagstat_stats-reads_mapped": "mapped_reads",
    }
    available = {k: v for k, v in cols.items() if k in df.columns}
    df = df[list(available.keys())].rename(columns=available)

    # Convert numeric columns
    for col in ["dup_pct", "mapped_pct", "median_coverage", "mapped_reads"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    return df


# ---------------------------------------------------------------------------
# CN/SV data loading from cohort matrix CSVs
# ---------------------------------------------------------------------------

def _get_sample_columns(headers: list[str], suffix: str) -> list[str]:
    """Extract sample names from column headers ending with a given suffix."""
    samples = []
    for h in headers:
        if h.endswith(suffix):
            name = h[: -len(suffix)]
            if name not in samples:
                samples.append(name)
    return samples


def load_cn_chr(path: Path) -> dict | None:
    """Load chromosome-level CN summary CSV. Display value is log2 ratio."""
    if not path.exists():
        return None
    with open(path) as f:
        rows = list(csv.DictReader(f))
    if not rows:
        return None
    samples = _get_sample_columns(list(rows[0].keys()), "_log2")
    out = []
    for r in rows:
        entry = {"chromosome": r["chromosome"], "length": int(r.get("length", 0))}
        # Skip rows where all sample values are empty (e.g. Mito)
        has_data = False
        for s in samples:
            log2_raw = r.get(f"{s}_log2", "")
            if log2_raw:
                has_data = True
                entry[f"{s}_log2"] = round(float(log2_raw), 4)
            else:
                entry[f"{s}_log2"] = None
            fc = r.get(f"{s}_fold_change", "")
            entry[f"{s}_fold_change"] = round(float(fc), 2) if fc else None
        if not has_data:
            continue
        out.append(entry)
    change_count = sum(
        1 for r in out
        if any(_has_cn_change(r.get(f"{s}_log2", 0) or 0) for s in samples)
    )
    return {"rows": out, "samples": samples, "row_count": len(out),
            "change_count": change_count}


def load_contig_cn(path: Path) -> dict | None:
    """Load the contig copy-number CSV (from TIDDIT per-contig coverage, contig_copy_number.py)."""
    if not path.exists():
        return None
    with open(path) as f:
        rows = list(csv.DictReader(f))
    if not rows:
        return None
    samples = _get_sample_columns(list(rows[0].keys()), "_log2")
    out = []
    for r in rows:
        entry = {"chromosome": r["chromosome"]}
        for s in samples:
            log2_raw = r.get(f"{s}_log2", "")
            entry[f"{s}_log2"] = round(float(log2_raw), 4) if log2_raw else None
            fc = r.get(f"{s}_fold_change", "")
            entry[f"{s}_fold_change"] = round(float(fc), 2) if fc else None
            tp = r.get(f"{s}_tiddit_ploidy", "")
            entry[f"{s}_tiddit_ploidy"] = round(float(tp), 2) if tp else None
            cov = r.get(f"{s}_median_cov", "")
            entry[f"{s}_median_cov"] = round(float(cov), 1) if cov else None
            n = r.get(f"{s}_n", "")
            entry[f"{s}_n"] = float(n) if n else None
        out.append(entry)
    # Same thresholds as the CNVKit tables (log2 < -0.4 loss, > 0.3 gain)
    change_count = sum(
        1 for r in out
        if any(_has_cn_change(r.get(f"{s}_log2", 0) or 0) for s in samples)
    )
    return {"rows": out, "samples": samples, "row_count": len(out), "change_count": change_count}


def load_cn_regions(path: Path) -> dict | None:
    """Load collapsed CN region matrix CSV. Display value is log2 ratio."""
    if not path.exists():
        return None
    with open(path) as f:
        rows = list(csv.DictReader(f))
    if not rows:
        return None
    samples = _get_sample_columns(list(rows[0].keys()), "_log2")
    out = []
    for r in rows:
        start = int(r.get("start", 0))
        end = int(r.get("end", 0))
        chr_len = r.get("chr_length")
        entry = {
            "chromosome": r["chromosome"],
            "start": start,
            "end": end,
            "chr_length": int(chr_len) if chr_len else None,
            "span_kb": round((end - start) / 1000, 1),
        }
        for s in samples:
            entry[f"{s}_log2"] = round(float(r.get(f"{s}_log2", 0)), 4)
            fc = r.get(f"{s}_fold_change", "")
            entry[f"{s}_fold_change"] = round(float(fc), 2) if fc else None
        out.append(entry)
    return {"rows": out, "samples": samples, "row_count": len(out)}


def load_sv_matrix(path: Path) -> dict | None:
    """Load SV cohort matrix CSV."""
    if not path.exists():
        return None
    with open(path) as f:
        rows = list(csv.DictReader(f))
    if not rows:
        return None
    fixed_cols = {"chrom", "pos", "chrom2", "end", "svtype", "svlen"}
    samples = [h for h in rows[0].keys() if h not in fixed_cols]
    out = []
    for r in rows:
        entry = {
            "chrom": r["chrom"],
            "pos": int(r.get("pos", 0)),
            "chrom2": r.get("chrom2", ""),
            "end": int(r.get("end", 0)),
            "svtype": r.get("svtype", ""),
            "svlen": int(r.get("svlen", 0)),
        }
        for s in samples:
            entry[s] = r.get(s, "-")
        out.append(entry)
    both_caller_count = sum(
        1 for r in out
        if any("Manta+TIDDIT" in r.get(s, "") for s in samples)
    )
    return {"rows": out, "samples": samples, "row_count": len(out),
            "both_caller_count": both_caller_count}


def _has_cn_change(log2: float) -> bool:
    """Return True if log2 ratio indicates a CN change (same thresholds as heatmap)."""
    return log2 < -0.4 or log2 > 0.3




def load_cnv_sv_data(data_dir: Path) -> dict:
    """Load all CN/SV data from a directory. Returns dict for template context."""
    cn_chr = load_cn_chr(data_dir / "cn_chr_summary_germline.csv")
    cn_reg = load_cn_regions(data_dir / "cn_cohort_collapsed.csv")
    contig_cn = load_contig_cn(data_dir / "contig_copy_number.csv")
    sv_pass = load_sv_matrix(data_dir / "sv_cohort_matrix_union_pass.csv")
    sv_all = load_sv_matrix(data_dir / "sv_cohort_matrix_union.csv")

    summary = {}
    if sv_pass:
        summary["sv_pass_count"] = sv_pass["row_count"]
    if sv_all:
        summary["sv_all_count"] = sv_all["row_count"]

    # Check for downloadable SV files (CSV + VCF)
    sv_downloads = {}
    for key, csv_name, vcf_name in [
        ("pass", "sv_cohort_matrix_union_pass.csv", "sv_cohort_merged_union_pass.vcf.gz"),
        ("all", "sv_cohort_matrix_union.csv", "sv_cohort_merged_union.vcf.gz"),
    ]:
        csv_path = data_dir / csv_name
        vcf_path = data_dir / vcf_name
        if csv_path.exists():
            sv_downloads[f"{key}_csv"] = f"data/{csv_name}"
        if vcf_path.exists():
            sv_downloads[f"{key}_vcf"] = f"data/{vcf_name}"

    # Check for downloadable CN files (CSV)
    cn_downloads = {}
    for key, csv_name in [
        ("regions", "cn_cohort_collapsed.csv"),
        ("chr", "cn_chr_summary_germline.csv"),
        ("matrix", "cn_cohort_full.csv"),
        ("contig", "contig_copy_number.csv"),
    ]:
        csv_path = data_dir / csv_name
        if csv_path.exists():
            cn_downloads[key] = f"data/{csv_name}"

    return {
        "cn_chr": cn_chr,
        "cn_reg": cn_reg,
        "contig_cn": contig_cn,
        "sv_pass": sv_pass,
        "sv_all": sv_all,
        "sv_downloads": sv_downloads,
        "cn_downloads": cn_downloads,
        "cnv_sv_summary": summary,
    }


# ---------------------------------------------------------------------------
# Context building for Jinja2 template
# ---------------------------------------------------------------------------

def discover_igv_reports(sample_reports_dir: Path | None) -> dict[str, dict[str, str]]:
    """Find existing igv-reports HTML files.

    Returns {sample_id: {"hc": path, "cnvkit": path, "manta": path, ...}}.
    """
    if sample_reports_dir is None or not sample_reports_dir.is_dir():
        return {}
    links: dict[str, dict[str, str]] = {}
    caller_suffixes = ["hc", "cnvkit", "manta", "tiddit"]
    for f in sorted(sample_reports_dir.glob("*_report.html")):
        name = f.stem.replace("_report", "")
        rel = f"samples/{f.name}"
        matched = False
        for caller in caller_suffixes:
            if name.endswith(f"_{caller}"):
                sample_id = name[: -(len(caller) + 1)]
                links.setdefault(sample_id, {})
                links[sample_id][caller] = rel
                matched = True
                break
        if not matched:
            # Fallback for legacy reports without caller suffix
            links.setdefault(name, {})
            links[name]["hc"] = rel
    return links


def build_context(
    multiqc_dir: Path,
    cohort_report: Path | None,
    sample_reports_dir: Path | None,
    cnv_sv_data_dir: Path | None = None,
    multiqc_report_path: str | None = None,
    joint_vcf: Path | None = None,
    prepared_vcf: Path | None = None,
    pass_stats_files: list[Path] | None = None,
) -> dict:
    """Build the full template context dictionary."""

    bcftools_df = load_bcftools_stats(multiqc_dir)
    snpeff_df = load_snpeff_stats(multiqc_dir)

    # Get unique samples (sorted) from bcftools stats
    samples = sorted(bcftools_df["sample"].unique())
    callers = sorted(TARGET_CALLERS)

    # Use known samples for general stats filtering
    general_df = load_general_stats(multiqc_dir, known_samples=set(samples))

    # --- Variant counts pivot: {sample: {caller: n_records}} ---
    variant_pivot = {}
    for _, row in bcftools_df.iterrows():
        variant_pivot.setdefault(row["sample"], {})[row["caller"]] = row["n_records"]

    # --- Impact pivot: {sample: {caller: {high, moderate, low}}} ---
    impact_pivot = {}
    for _, row in snpeff_df.iterrows():
        impact_pivot.setdefault(row["sample"], {})[row["caller"]] = {
            "high": row["high"],
            "moderate": row["moderate"],
            "low": row["low"],
        }

    # --- Combined QC + variant summary table ---
    igv_links = discover_igv_reports(sample_reports_dir)

    # Build QC lookup from general_stats
    qc_lookup = {}
    for _, row in general_df.iterrows():
        qc_lookup[row["sample"]] = {
            "dup_pct": round(row.get("dup_pct", 0), 1) if pd.notna(row.get("dup_pct")) else None,
            "mapped_pct": round(row.get("mapped_pct", 0), 1) if pd.notna(row.get("mapped_pct")) else None,
            "median_coverage": int(row.get("median_coverage", 0)) if pd.notna(row.get("median_coverage")) else None,
            "mapped_reads_m": round(row.get("mapped_reads", 0), 1) if pd.notna(row.get("mapped_reads")) else None,
        }

    # Load PASS filter stats (from FILTER_PASS_VCF)
    pass_stats = load_pass_stats(pass_stats_files)

    summary_data = []
    for sample in samples:
        info = classify_sample(sample)
        counts = variant_pivot.get(sample, {})
        qc = qc_lookup.get(sample, {})

        # HC variant count from MultiQC bcftools_stats (soft-filtered, all non-ref)
        hc_variants = counts.get("HaplotypeCaller", 0)

        # TIDDIT: use PASS stats if available, otherwise fall back to raw count
        tiddit_ps = pass_stats.get((sample, "tiddit"), {})
        tiddit_total = tiddit_ps.get("total", counts.get("TIDDIT", 0))
        tiddit_pass = tiddit_ps.get("pass")  # None if no pass stats

        # Manta: same PASS/all split (the Manta IGV report itself keeps all calls)
        manta_ps = pass_stats.get((sample, "manta"), {})
        manta_total = manta_ps.get("total", counts.get("Manta", 0))
        manta_pass = manta_ps.get("pass")

        entry = {
            "sample": sample,
            "type": info["type"],
            # QC fields
            "median_coverage": qc.get("median_coverage"),
            "dup_pct": qc.get("dup_pct"),
            "mapped_pct": qc.get("mapped_pct"),
            "mapped_reads_m": qc.get("mapped_reads_m"),
            # Variant fields
            "hc_variants": hc_variants,
            "cnvkit_events": counts.get("CNVKit", 0),
            "tiddit_svs": tiddit_total,
            "tiddit_pass": tiddit_pass,
            "manta_svs": manta_total,
            "manta_pass": manta_pass,
            "igv_link": igv_links.get(sample, {}).get("hc"),
            "cnvkit_igv_link": igv_links.get(sample, {}).get("cnvkit"),
            "manta_igv_link": igv_links.get(sample, {}).get("manta"),
            "tiddit_igv_link": igv_links.get(sample, {}).get("tiddit"),
        }
        summary_data.append(entry)

    # --- Cohort report path ---
    cohort_link = None
    cohort_variant_count = 0
    if cohort_report and cohort_report.exists():
        cohort_link = cohort_report.name

    # Post-norm counts from prepared VCF (match cohort report table rows)
    prepared_total, prepared_pass = get_prepared_vcf_counts(prepared_vcf)
    if prepared_total is not None:
        cohort_variant_count = prepared_total
        cohort_pass_count = prepared_pass
    else:
        # Fallback to pre-norm counts from MultiQC
        joint_count = get_joint_vcf_variant_count(multiqc_dir)
        if joint_count is not None:
            cohort_variant_count = joint_count
        else:
            cohort_variant_count = sum(s.get("hc_variants", 0) for s in summary_data)
        cohort_pass_count = get_joint_vcf_pass_count(joint_vcf)

    # Pre-norm count for context (shown as subtitle on card)
    cohort_prenorm_count = get_joint_vcf_variant_count(multiqc_dir)

    # --- CN/SV data (optional) ---
    cnv_sv = {}
    if cnv_sv_data_dir and cnv_sv_data_dir.is_dir():
        cnv_sv = load_cnv_sv_data(cnv_sv_data_dir)

    return {
        "title": "ALE Multi-Caller Mutation Dashboard",
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "n_samples": len(samples),
        "callers": callers,
        "cohort_link": cohort_link,
        "cohort_variant_count": cohort_variant_count,
        "cohort_pass_count": cohort_pass_count,
        "cohort_prenorm_count": cohort_prenorm_count,
        "multiqc_report_path": multiqc_report_path or "../../output_all/multiqc/multiqc_report.html",
        "summary_data_json": json.dumps(summary_data),
        # CN/SV data (None if not provided)
        "cn_chr": cnv_sv.get("cn_chr"),
        "cn_reg": cnv_sv.get("cn_reg"),
        "contig_cn": cnv_sv.get("contig_cn"),
        "sv_pass": cnv_sv.get("sv_pass"),
        "sv_all": cnv_sv.get("sv_all"),
        "sv_downloads": cnv_sv.get("sv_downloads", {}),
        "cn_downloads": cnv_sv.get("cn_downloads", {}),
        "cnv_sv_summary": cnv_sv.get("cnv_sv_summary", {}),
    }


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

def render(context: dict, template_dir: Path, output_path: Path) -> None:
    """Render the Jinja2 template and write to output."""
    env = Environment(
        loader=FileSystemLoader(str(template_dir)),
        autoescape=False,  # We handle escaping in the template
    )
    template = env.get_template("index.html.j2")
    html = template.render(**context)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html)
    print(f"Generated: {output_path} ({len(html):,} bytes)")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Generate multi-caller variant dashboard index.html"
    )
    parser.add_argument(
        "--multiqc-dir", required=True, type=Path,
        help="Path to multiqc_data/ directory containing TSV summary files",
    )
    parser.add_argument(
        "--output", required=True, type=Path,
        help="Output path for the generated index.html",
    )
    parser.add_argument(
        "--cohort-report", type=Path, default=None,
        help="Path to cohort_report.html (for linking)",
    )
    parser.add_argument(
        "--sample-reports-dir", type=Path, default=None,
        help="Path to directory containing per-sample igv-reports HTML files",
    )
    parser.add_argument(
        "--templates-dir", type=Path, default=None,
        help="Path to Jinja2 templates directory (default: templates/ next to this script)",
    )
    parser.add_argument(
        "--cnv-sv-data-dir", type=Path, default=None,
        help="Directory containing CN/SV cohort matrix CSVs (from cn_cohort_matrix.py, sv_cohort_matrix.py)",
    )
    parser.add_argument(
        "--multiqc-report-path", type=str, default=None,
        help="Relative path to multiqc_report.html from the output index.html location",
    )
    parser.add_argument(
        "--joint-vcf", type=Path, default=None,
        help="Path to joint HaplotypeCaller VCF (.vcf.gz) for PASS variant counting",
    )
    parser.add_argument(
        "--prepared-vcf", type=Path, default=None,
        help="Path to prepared (post-norm) cohort VCF for accurate row counting matching cohort report table",
    )
    parser.add_argument(
        "--pass-stats", type=Path, nargs="*", default=None,
        help="PASS filter stats TSV files from FILTER_PASS_VCF (sample, caller, total, pass)",
    )
    args = parser.parse_args()

    context = build_context(
        multiqc_dir=args.multiqc_dir,
        cohort_report=args.cohort_report,
        sample_reports_dir=args.sample_reports_dir,
        cnv_sv_data_dir=args.cnv_sv_data_dir,
        multiqc_report_path=args.multiqc_report_path,
        joint_vcf=args.joint_vcf,
        prepared_vcf=args.prepared_vcf,
        pass_stats_files=args.pass_stats,
    )

    # Template directory: explicit arg or relative to this script
    template_dir = args.templates_dir or (Path(__file__).parent / "templates")
    render(context, template_dir, args.output)


if __name__ == "__main__":
    main()