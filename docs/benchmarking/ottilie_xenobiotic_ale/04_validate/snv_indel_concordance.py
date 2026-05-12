#!/usr/bin/env python3
"""
Task 1: SNV/INDEL Concordance — HaplotypeCaller vs Ottilie Sup Data 4.

Compares pipeline HaplotypeCaller joint-germline output against the
1,405-mutation truth set from Ottilie et al. (2022) Commun Biol 5:128.

Usage:
    source ~/miniforge3/etc/profile.d/conda.sh && conda activate nf-env
    pip install openpyxl  # if not already installed
    python 04_validate/snv_indel_concordance.py

Requires: openpyxl, bcftools (in PATH)
"""

import argparse
import csv
import subprocess
import sys
from pathlib import Path

try:
    import openpyxl
except ImportError:
    sys.exit("openpyxl not installed. Run: pip install openpyxl")


# ── Defaults (relative to repo root) ────────────────────────────────────────

REPO_ROOT = Path(__file__).resolve().parents[4]  # 04_validate -> ottilie -> benchmarking -> docs -> repo

DEFAULT_TRUTH_SET = REPO_ROOT / "data/ottilie/supplementary/sup_4_42003_2022_3076_MOESM6_ESM.xlsx"
DEFAULT_DICTIONARY = REPO_ROOT / "data/ottilie/sample_name_dictionary.csv"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "output_ottilie"

# Pilot sample mapping: sup4 clone name -> pipeline sample name
PILOT_SUP4_MAP = {
    "Doxorubicin-16--R2b": "Doxorubicin16-R2b",
    "Carmaphycin--R9-2": "Carmaphycin-R9-2",
    "CBR110-15R3a": "CBR110-15-R3a",
}

PARENT_SAMPLE = "NODRUG-GM2"


# ── Helper functions ─────────────────────────────────────────────────────────

def load_truth_set(xlsx_path, sup4_map):
    """Load mutations from Sup Data 4 for samples in sup4_map."""
    wb = openpyxl.load_workbook(xlsx_path, read_only=True)
    ws = wb.active
    rows_iter = ws.iter_rows(values_only=True)
    next(rows_iter)  # skip description row
    headers = [str(v) for v in next(rows_iter)]

    truth = {sample: [] for sample in sup4_map.values()}
    for row in rows_iter:
        d = dict(zip(headers, row))
        clone = d.get("Clone Name", "")
        if clone not in sup4_map:
            continue
        sample = sup4_map[clone]
        truth[sample].append({
            "chrom": str(d["Chromosome"]),
            "pos": int(d["Mutation Position"]),
            "ref": str(d["Reference Base"]),
            "alt": str(d["Alternate Base"]),
            "type": str(d["Type"]),
            "gene": str(d.get("Standard Name", "")),
            "effect": str(d.get("Effect", "")),
            "impact": str(d.get("Impact", "")),
            "status": str(d.get("Mutation Status", "")),
            "qual": d.get("GATK Quality Score", ""),
        })
    wb.close()
    return truth


def load_vcf_variants(vcf_path):
    """Extract variants from a VCF using bcftools."""
    result = subprocess.run(
        ["bcftools", "query", "-f", "%CHROM\t%POS\t%REF\t%ALT\t%QUAL\t%FILTER\n", str(vcf_path)],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        sys.exit(f"bcftools failed on {vcf_path}: {result.stderr}")
    variants = []
    for line in result.stdout.strip().split("\n"):
        if not line:
            continue
        chrom, pos, ref, alt, qual, filt = line.split("\t")
        variants.append({
            "chrom": chrom,
            "pos": int(pos),
            "ref": ref,
            "alt": alt,
            "qual": float(qual) if qual != "." else 0,
            "filter": filt,
        })
    return variants


def find_match(truth_var, pipeline_vars, indel_window=5):
    """Match a truth variant to pipeline calls. SNPs: exact. INDELs: ±window."""
    is_indel = truth_var["type"] == "INDEL"
    for pv in pipeline_vars:
        if pv["chrom"] != truth_var["chrom"]:
            continue
        if is_indel:
            if abs(pv["pos"] - truth_var["pos"]) <= indel_window:
                if len(pv["ref"]) != len(pv["alt"]):  # confirm it's also an indel
                    return pv
        else:
            if (pv["pos"] == truth_var["pos"]
                    and pv["ref"] == truth_var["ref"]
                    and pv["alt"] == truth_var["alt"]):
                return pv
    return None


def resolve_vcf_path(output_dir, sample):
    """Find the individual-from-joint VCF for a sample."""
    vcf_dir = Path(output_dir) / "variant_calling/haplotypecaller/individual_from_joint" / sample
    vcfs = list(vcf_dir.glob("*.vcf.gz"))
    if not vcfs:
        sys.exit(f"No VCF found in {vcf_dir}")
    return vcfs[0]


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--truth-set", default=str(DEFAULT_TRUTH_SET), help="Sup Data 4 xlsx")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="Pipeline output directory")
    parser.add_argument("--parent", default=PARENT_SAMPLE, help="Parent sample name")
    parser.add_argument("--indel-window", type=int, default=5, help="Position tolerance for INDEL matching (bp)")
    parser.add_argument("--pass-only", action="store_true", help="Only count PASS-filtered pipeline variants")
    parser.add_argument("--csv", help="Write results to CSV file")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)

    # Load truth set
    print(f"Truth set: {args.truth_set}")
    truth = load_truth_set(args.truth_set, PILOT_SUP4_MAP)

    # Load parent variants for parent-subtraction precision estimate
    parent_vcf_path = resolve_vcf_path(output_dir, args.parent)
    parent_vars = load_vcf_variants(parent_vcf_path)
    parent_positions = set((v["chrom"], v["pos"]) for v in parent_vars)
    print(f"Parent ({args.parent}): {len(parent_vars)} variants")

    evolved_samples = [s for s in PILOT_SUP4_MAP.values()]
    csv_rows = []

    # Per-type accumulators
    totals = {"snp_tp": 0, "snp_fn": 0, "indel_tp": 0, "indel_fn": 0}

    print(f"\n{'=' * 80}")

    for sample in evolved_samples:
        vcf_path = resolve_vcf_path(output_dir, sample)
        pipeline_vars = load_vcf_variants(vcf_path)
        if args.pass_only:
            pipeline_vars = [v for v in pipeline_vars if v["filter"] == "PASS"]

        truth_vars = truth[sample]
        n_truth = len(truth_vars)

        # Sensitivity
        tp_list, fn_list = [], []
        for tv in truth_vars:
            match = find_match(tv, pipeline_vars, args.indel_window)
            if match:
                tp_list.append((tv, match))
            else:
                fn_list.append(tv)

        tp = len(tp_list)
        fn = len(fn_list)
        sensitivity = tp / n_truth * 100 if n_truth else 0

        # Per-type
        for tv in truth_vars:
            matched = find_match(tv, pipeline_vars, args.indel_window) is not None
            key = "snp" if tv["type"] == "SNP" else "indel"
            totals[f"{key}_tp" if matched else f"{key}_fn"] += 1

        # Precision (after parent subtraction)
        evolved_unique = [v for v in pipeline_vars if (v["chrom"], v["pos"]) not in parent_positions]
        truth_positions = set((tv["chrom"], tv["pos"]) for tv in truth_vars)
        tp_prec = sum(
            1 for v in evolved_unique
            if any(v["chrom"] == tc and abs(v["pos"] - tp_) <= args.indel_window
                   for tc, tp_ in truth_positions)
        )
        precision = tp_prec / len(evolved_unique) * 100 if evolved_unique else 0

        print(f"\n{'─' * 80}")
        print(f"SAMPLE: {sample}")
        print(f"  Truth mutations: {n_truth}  |  Pipeline calls: {len(pipeline_vars)}  |  Evolved-unique: {len(evolved_unique)}")
        print(f"  Sensitivity: {tp}/{n_truth} ({sensitivity:.1f}%)")
        print(f"  Precision (post parent-sub): {tp_prec}/{len(evolved_unique)} ({precision:.1f}%)")

        if fn_list:
            print(f"\n  MISSED ({fn}):")
            for tv in fn_list:
                in_parent = (tv["chrom"], tv["pos"]) in parent_positions
                flag = " [IN PARENT]" if in_parent else ""
                print(f"    {tv['chrom']}:{tv['pos']} {tv['ref']}>{tv['alt']} ({tv['type']}) "
                      f"{tv['gene']} {tv['effect']}{flag}")

        csv_rows.append({
            "sample": sample,
            "truth_n": n_truth,
            "pipeline_total": len(pipeline_vars),
            "evolved_unique": len(evolved_unique),
            "tp_sensitivity": tp,
            "fn_sensitivity": fn,
            "sensitivity_pct": f"{sensitivity:.1f}",
            "tp_precision": tp_prec,
            "fp_precision": len(evolved_unique) - tp_prec,
            "precision_pct": f"{precision:.1f}",
        })

    # Overall
    total_tp = totals["snp_tp"] + totals["indel_tp"]
    total_fn = totals["snp_fn"] + totals["indel_fn"]
    total = total_tp + total_fn
    snp_total = totals["snp_tp"] + totals["snp_fn"]
    indel_total = totals["indel_tp"] + totals["indel_fn"]

    print(f"\n{'=' * 80}")
    print("OVERALL SENSITIVITY")
    print(f"  All:   {total_tp}/{total} ({total_tp / total * 100:.1f}%)")
    print(f"  SNP:   {totals['snp_tp']}/{snp_total} ({totals['snp_tp'] / snp_total * 100:.1f}%)" if snp_total else "")
    print(f"  INDEL: {totals['indel_tp']}/{indel_total} ({totals['indel_tp'] / indel_total * 100:.1f}%)" if indel_total else "")
    print(f"{'=' * 80}")

    if args.csv:
        csv_path = Path(args.csv)
        with open(csv_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=csv_rows[0].keys())
            writer.writeheader()
            writer.writerows(csv_rows)
        print(f"\nResults written to {csv_path}")


if __name__ == "__main__":
    main()
