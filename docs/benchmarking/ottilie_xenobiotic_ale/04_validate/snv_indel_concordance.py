#!/usr/bin/env python3
"""
Task 1: SNV/INDEL Concordance — HaplotypeCaller vs Ottilie Sup Data 4.

Compares pipeline HaplotypeCaller joint-germline output against the
1,405-mutation truth set from Ottilie et al. (2022) Commun Biol 5:128.

Usage:
    source ~/miniforge3/etc/profile.d/conda.sh && conda activate nf-env
    pip install openpyxl  # if not already installed
    python 04_validate/snv_indel_concordance.py
    python 04_validate/snv_indel_concordance.py --output-dir output_ottilie_tier2

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

PARENT_SAMPLE = "NODRUG-GM2"


# ── Helper functions ─────────────────────────────────────────────────────────

def build_sup4_map(dictionary_path, output_dir):
    """Build sup4 clone name -> pipeline sample name mapping dynamically.

    Reads the sample_name_dictionary.csv and checks which samples actually
    exist in the pipeline output directory (individual_from_joint/).
    Returns dict mapping sup4 clone names to pipeline directory names.
    """
    ijf_dir = Path(output_dir) / "variant_calling/haplotypecaller/individual_from_joint"
    if not ijf_dir.exists():
        sys.exit(f"individual_from_joint directory not found: {ijf_dir}")

    available = set(p.name for p in ijf_dir.iterdir() if p.is_dir())

    sup4_map = {}
    with open(dictionary_path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            sup4 = row["clone_name_sup4"].strip()
            sup5 = row["clone_name_sup5"].strip()
            lib = row["library_name_sra"].strip()
            is_parent = row["is_parent"].strip() == "True"

            if not sup4 or is_parent:
                continue

            # Try sup5 first (simplified name), then sup4, then library name
            for candidate in [sup5, sup4, lib]:
                if candidate and candidate in available:
                    sup4_map[sup4] = candidate
                    break

    return sup4_map


def load_truth_set(xlsx_path, sup4_map):
    """Load mutations from Sup Data 4 for samples in sup4_map."""
    wb = openpyxl.load_workbook(xlsx_path, read_only=True)
    ws = wb.active
    rows_iter = ws.iter_rows(values_only=True)
    next(rows_iter)  # skip description row
    headers = [str(v) for v in next(rows_iter)]

    truth = {sample: [] for sample in sup4_map.values()}
    mnv_notes = []
    for row in rows_iter:
        d = dict(zip(headers, row))
        clone = d.get("Clone Name", "")
        if clone not in sup4_map:
            continue
        sample = sup4_map[clone]
        pos_raw = str(d["Mutation Position"])
        # Multi-position MNVs (e.g., "640157, 640159"): use first position
        is_mnv = "," in pos_raw
        try:
            pos = int(pos_raw.split(",")[0].strip())
        except (ValueError, TypeError):
            continue
        if is_mnv:
            mnv_notes.append(
                f"  MNV: {sample} {d['Chromosome']}:{pos_raw} "
                f"{d['Reference Base']}>{d['Alternate Base']} "
                f"({d.get('Standard Name','')}) — matched on first position {pos}"
            )
        truth[sample].append({
            "chrom": str(d["Chromosome"]),
            "pos": pos,
            "ref": str(d["Reference Base"]),
            "alt": str(d["Alternate Base"]),
            "type": str(d["Type"]),
            "gene": str(d.get("Standard Name", "")),
            "effect": str(d.get("Effect", "")),
            "impact": str(d.get("Impact", "")),
            "status": str(d.get("Mutation Status", "")),
            "qual": d.get("GATK Quality Score", ""),
            "is_mnv": is_mnv,
        })
    wb.close()
    return truth, mnv_notes


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
    """Match a truth variant to pipeline calls. SNPs: exact. INDELs: ±window.

    For SNPs, handles multi-allelic VCF records (e.g., ALT=G,A matches truth ALT=G).
    """
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
                    and pv["ref"] == truth_var["ref"]):
                # Handle multi-allelic records on both sides
                pipeline_alts = set(pv["alt"].split(","))
                truth_alts = set(truth_var["alt"].split(","))
                if truth_alts & pipeline_alts:  # any overlap
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
    parser.add_argument("--dictionary", default=str(DEFAULT_DICTIONARY),
                        help="Sample name dictionary CSV (maps sup4 clone names to pipeline names)")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="Pipeline output directory")
    parser.add_argument("--parent", default=PARENT_SAMPLE, help="Parent sample name")
    parser.add_argument("--indel-window", type=int, default=5, help="Position tolerance for INDEL matching (bp)")
    parser.add_argument("--pass-only", action="store_true", help="Only count PASS-filtered pipeline variants")
    parser.add_argument("--csv", help="Write results to CSV file")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)

    # Build sample mapping dynamically from dictionary + available output
    sup4_map = build_sup4_map(args.dictionary, output_dir)
    if not sup4_map:
        sys.exit("No samples matched between dictionary and pipeline output")
    print(f"Dictionary: {args.dictionary}")
    print(f"Matched {len(sup4_map)} evolved samples in {output_dir}")

    # Load truth set
    print(f"Truth set: {args.truth_set}")
    truth, mnv_notes = load_truth_set(args.truth_set, sup4_map)
    if mnv_notes:
        print(f"  Note: {len(mnv_notes)} multi-nucleotide variant(s) matched on first position only:")
        for note in mnv_notes:
            print(note)

    # Filter to samples that actually have truth set mutations
    samples_with_truth = {s for s, variants in truth.items() if variants}
    samples_without_truth = set(sup4_map.values()) - samples_with_truth
    if samples_without_truth:
        print(f"  Note: {len(samples_without_truth)} samples have no mutations in truth set (skipped)")

    # Load parent variants for parent-subtraction precision estimate
    parent_vcf_path = resolve_vcf_path(output_dir, args.parent)
    parent_vars = load_vcf_variants(parent_vcf_path)
    parent_positions = set((v["chrom"], v["pos"]) for v in parent_vars)
    print(f"Parent ({args.parent}): {len(parent_vars)} variants")

    evolved_samples = [s for s in sup4_map.values() if s in samples_with_truth]
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
                flags = []
                if in_parent:
                    flags.append("[IN PARENT]")
                if tv.get("is_mnv"):
                    flags.append("[MNV - matched on 1st pos only]")
                flag_str = " " + " ".join(flags) if flags else ""
                print(f"    {tv['chrom']}:{tv['pos']} {tv['ref']}>{tv['alt']} ({tv['type']}) "
                      f"{tv['gene']} {tv['effect']}{flag_str}")

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
