#!/usr/bin/env python3
"""
Multi-Caller Mutation Report Index Generator

Reads MultiQC summary TSVs and generates a rich static HTML dashboard
using Jinja2 templates with Tabulator.js tables. Links to existing
igv-reports HTML files for alignment drill-down.

Usage (standalone):
    python generate_index.py \
        --multiqc-dir output_all/multiqc/multiqc_data \
        --output docs/igvreports/demo/index.html \
        --sample-reports-dir docs/igvreports/demo/samples \
        --cohort-report docs/igvreports/demo/cohort_report.html

Usage (from Nextflow GENERATE_INDEX process):
    Called with paths resolved by the workflow.
"""

import argparse
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
    ("haplotypecaller.from_joint_calling.hard_filtered", None),  # skip filtered rows
    ("haplotypecaller.from_joint_calling", "HaplotypeCaller"),
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
    """Classify a sample as Ancestral or Evolved and extract ALE lineage."""
    if sample_id.startswith("A0-"):
        return {"type": "Ancestral", "lineage": "CEN.PK parent"}
    m = re.match(r"^(A\d+)-F(\d+)", sample_id)
    if m:
        return {"type": "Evolved", "lineage": f"{m.group(1)} (Flask {m.group(2)})"}
    return {"type": "Unknown", "lineage": sample_id}


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


def load_general_stats(multiqc_dir: Path) -> pd.DataFrame:
    """Load multiqc_general_stats.txt, keeping only sample-level rows.

    Sample-level rows have no space+dot suffix (e.g., 'A0-F0-I1-R1').
    Per-lane rows look like 'A0-F0-I1-R1 .Lane 1 Read1'.
    Per-caller rows look like 'A0-F0-I1-R1 .cnvkit'.
    """
    path = multiqc_dir / "multiqc_general_stats.txt"
    df = pd.read_csv(path, sep="\t")

    # Keep only rows where Sample has no space (pure sample ID)
    # and matches the expected ALE sample pattern (A{n}-F{n}-I{n}-R{n})
    mask = (~df["Sample"].str.contains(" ", na=False) &
            df["Sample"].str.match(r"^A\d+-F\d+-I\d+-R\d+$", na=False))
    df = df[mask].copy()
    df = df.rename(columns={"Sample": "sample"})

    # Select relevant columns (they may have module prefixes)
    cols = {
        "sample": "sample",
        "gatk4_markduplicates_mark_duplicates-PERCENT_DUPLICATION": "dup_pct",
        "samtools_flagstat_stats-reads_mapped_percent": "mapped_pct",
        "mosdepth-median_coverage": "median_coverage",
        "samtools_flagstat_stats-raw_total_sequences": "total_reads",
    }
    available = {k: v for k, v in cols.items() if k in df.columns}
    df = df[list(available.keys())].rename(columns=available)

    # Convert numeric columns
    for col in ["dup_pct", "mapped_pct", "median_coverage", "total_reads"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    return df


# ---------------------------------------------------------------------------
# Context building for Jinja2 template
# ---------------------------------------------------------------------------

def discover_igv_reports(sample_reports_dir: Path | None) -> dict[str, str]:
    """Find existing igv-reports HTML files, return {sample_id: relative_path}."""
    if sample_reports_dir is None or not sample_reports_dir.is_dir():
        return {}
    links = {}
    for f in sorted(sample_reports_dir.glob("*_report.html")):
        sample_id = f.stem.replace("_report", "")
        # Relative path from the output index.html location
        links[sample_id] = f"samples/{f.name}"
    return links


def build_context(
    multiqc_dir: Path,
    cohort_report: Path | None,
    sample_reports_dir: Path | None,
    variant_counts: dict[str, int] | None,
) -> dict:
    """Build the full template context dictionary."""

    bcftools_df = load_bcftools_stats(multiqc_dir)
    snpeff_df = load_snpeff_stats(multiqc_dir)
    general_df = load_general_stats(multiqc_dir)

    # Get unique samples (sorted)
    samples = sorted(bcftools_df["sample"].unique())
    callers = sorted(TARGET_CALLERS)

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

    # --- QC data for general stats table ---
    qc_data = []
    for _, row in general_df.iterrows():
        info = classify_sample(row["sample"])
        entry = {
            "sample": row["sample"],
            "type": info["type"],
            "lineage": info["lineage"],
            "dup_pct": round(row.get("dup_pct", 0), 1) if pd.notna(row.get("dup_pct")) else None,
            "mapped_pct": round(row.get("mapped_pct", 0), 1) if pd.notna(row.get("mapped_pct")) else None,
            "median_coverage": int(row.get("median_coverage", 0)) if pd.notna(row.get("median_coverage")) else None,
            # MultiQC stores total_sequences already in millions
            "total_reads_m": round(row.get("total_reads", 0), 1) if pd.notna(row.get("total_reads")) else None,
        }
        qc_data.append(entry)

    # --- Per-sample summary table (combines variant counts + QC + igv links) ---
    igv_links = discover_igv_reports(sample_reports_dir)

    summary_data = []
    for sample in samples:
        info = classify_sample(sample)
        counts = variant_pivot.get(sample, {})
        hc_impact = impact_pivot.get(sample, {}).get("HaplotypeCaller", {})

        # Use variant_counts from Nextflow if provided, otherwise from MultiQC
        hc_variants = counts.get("HaplotypeCaller", 0)
        if variant_counts and sample in variant_counts:
            hc_variants = variant_counts[sample]

        entry = {
            "sample": sample,
            "type": info["type"],
            "lineage": info["lineage"],
            "hc_variants": hc_variants,
            "cnvkit_events": counts.get("CNVKit", 0),
            "tiddit_svs": counts.get("TIDDIT", 0),
            "manta_svs": counts.get("Manta", 0),
            "hc_high": hc_impact.get("high", 0),
            "hc_moderate": hc_impact.get("moderate", 0),
            "hc_low": hc_impact.get("low", 0),
            "igv_link": igv_links.get(sample),
        }
        summary_data.append(entry)

    # --- Cohort report path ---
    cohort_link = None
    if cohort_report and cohort_report.exists():
        cohort_link = cohort_report.name

    return {
        "title": "ALE Multi-Caller Variant Dashboard",
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "n_samples": len(samples),
        "callers": callers,
        "cohort_link": cohort_link,
        "qc_data_json": json.dumps(qc_data),
        "summary_data_json": json.dumps(summary_data),
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
        "--variant-counts-json", type=Path, default=None,
        help="JSON file with {sample_id: count} from Nextflow COUNT_VARIANTS",
    )
    parser.add_argument(
        "--templates-dir", type=Path, default=None,
        help="Path to Jinja2 templates directory (default: templates/ next to this script)",
    )
    args = parser.parse_args()

    # Load optional variant counts from Nextflow
    variant_counts = None
    if args.variant_counts_json and args.variant_counts_json.exists():
        variant_counts = json.loads(args.variant_counts_json.read_text())

    context = build_context(
        multiqc_dir=args.multiqc_dir,
        cohort_report=args.cohort_report,
        sample_reports_dir=args.sample_reports_dir,
        variant_counts=variant_counts,
    )

    # Template directory: explicit arg or relative to this script
    template_dir = args.templates_dir or (Path(__file__).parent / "templates")
    render(context, template_dir, args.output)


if __name__ == "__main__":
    main()
