#!/usr/bin/env python3
"""
Compare variant calling precision/recall by frequency bin.
Truth set: manually curated SNVs from spore-seq (03_table_s8_genomic_locations.csv)
Tools: breseq VCF and HaplotypeCaller joint germline VCF
"""

import csv
import subprocess
import os
import sys
from collections import defaultdict

# --- Paths ---
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TRUTH_CSV = os.path.join(BASE, "data/dicarboxylic_acids/process_adipic_muts/03_table_s8_genomic_locations.csv")
BRESEQ_DIR = os.path.join(BASE, "output_all/variant_calling/breseq")
HC_JOINT_VCF = os.path.join(BASE, "output_all/variant_calling/haplotypecaller/joint_variant_calling/joint_germline.vcf.gz")
OUTPUT_DIR = os.path.join(BASE, "output_all")


def parse_truth_set(csv_path):
    """Parse truth CSV into list of (gene, chrom, pos, ref, alt, sample, freq) entries."""
    entries = []
    with open(csv_path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            ref = row["ref"].strip()
            alt = row["alt"].strip()
            if not ref or not alt:
                # Skip repeat expansions / complex indels (no simple ref/alt)
                continue

            chrom = row["chrom"].strip()
            pos = int(row["genomic_pos"])
            gene = row["gene"].strip()

            pos_strain = row["positive_strain"].strip()
            neg_strain = row["negative_strain"].strip()
            pct_pos = float(row["pct_positive"])
            pct_neg = float(row["pct_negative"])

            if pos_strain:
                entries.append({
                    "gene": gene, "chrom": chrom, "pos": pos,
                    "ref": ref, "alt": alt,
                    "sample": pos_strain, "expected_freq": pct_pos,
                })
            if neg_strain:
                entries.append({
                    "gene": gene, "chrom": chrom, "pos": pos,
                    "ref": ref, "alt": alt,
                    "sample": neg_strain, "expected_freq": pct_neg,
                })
    return entries


def freq_bin(freq):
    if freq == 0:
        return "Absent (0%)"
    elif freq >= 90:
        return "Fixed (>=90%)"
    elif freq >= 60:
        return "High (60-89%)"
    elif freq >= 35:
        return "Medium (35-59%)"
    else:
        return "Low (1-34%)"


def bcftools_query(args):
    """Run bcftools and return stdout lines."""
    try:
        result = subprocess.run(
            ["bcftools"] + args,
            capture_output=True, text=True, timeout=10
        )
        return result.stdout.strip().split("\n") if result.stdout.strip() else []
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return []


def check_breseq(chrom, pos, alt, sample):
    """Check if breseq VCF has this variant. Returns (found, observed_af)."""
    vcf = os.path.join(BRESEQ_DIR, sample, f"{sample}.vcf.gz")
    if not os.path.exists(vcf):
        return False, None

    lines = bcftools_query([
        "query", "-r", f"{chrom}:{pos}", "-f", "%POS\t%REF\t%ALT\t%INFO/AF\n", vcf
    ])
    for line in lines:
        fields = line.split("\t")
        if len(fields) >= 4 and fields[2] == alt:
            return True, float(fields[3])
    return False, None


def check_haplotypecaller(chrom, pos, alt, sample):
    """Check if HC joint VCF has this variant called in the sample. Returns (found, observed_af)."""
    vcf_sample = f"ALE_Exp1_{sample}"

    lines = bcftools_query([
        "view", "-r", f"{chrom}:{pos}", "-s", vcf_sample,
        "-H", HC_JOINT_VCF
    ])
    for line in lines:
        fields = line.split("\t")
        if len(fields) < 10:
            continue
        alts = fields[4].split(",")
        if alt not in alts:
            continue
        alt_idx = alts.index(alt)

        # Parse FORMAT and sample fields
        fmt = fields[8].split(":")
        sample_data = fields[9].split(":")
        fmt_dict = dict(zip(fmt, sample_data))

        gt = fmt_dict.get("GT", ".")
        # Check if genotype includes the alt allele
        gt_alleles = gt.replace("|", "/").split("/")
        alt_called = str(alt_idx + 1) in gt_alleles

        # Calculate AF from AD
        ad = fmt_dict.get("AD", "")
        observed_af = None
        if ad and "," in ad:
            ad_vals = [int(x) for x in ad.split(",")]
            total = sum(ad_vals)
            if total > 0 and len(ad_vals) > alt_idx + 1:
                observed_af = ad_vals[alt_idx + 1] / total

        return alt_called, observed_af

    return False, None


def main():
    entries = parse_truth_set(TRUTH_CSV)
    print(f"Truth set: {len(entries)} variant×sample entries (after expanding pos/neg strains)\n")

    # Check each entry against both tools
    results = []
    for e in entries:
        breseq_found, breseq_af = check_breseq(e["chrom"], e["pos"], e["alt"], e["sample"])
        hc_found, hc_af = check_haplotypecaller(e["chrom"], e["pos"], e["alt"], e["sample"])
        results.append({
            **e,
            "freq_bin": freq_bin(e["expected_freq"]),
            "breseq_found": breseq_found,
            "breseq_af": breseq_af,
            "hc_found": hc_found,
            "hc_af": hc_af,
        })

    # --- Write per-variant detail CSV ---
    detail_path = os.path.join(OUTPUT_DIR, "variant_match_details.csv")
    with open(detail_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "gene", "chrom", "pos", "ref", "alt", "sample",
            "expected_freq", "freq_bin",
            "breseq_found", "breseq_af", "hc_found", "hc_af"
        ])
        writer.writeheader()
        writer.writerows(results)
    print(f"Per-variant details written to: {detail_path}")

    # --- Split results into expected-present vs expected-absent ---
    present_results = [r for r in results if r["expected_freq"] > 0]
    absent_results = [r for r in results if r["expected_freq"] == 0]

    # --- Recall by frequency bin (expected-present variants) ---
    bins = ["Fixed (>=90%)", "High (60-89%)", "Medium (35-59%)", "Low (1-34%)"]
    summary = []

    for b in bins:
        bin_results = [r for r in present_results if r["freq_bin"] == b]
        n = len(bin_results)
        if n == 0:
            continue
        breseq_tp = sum(1 for r in bin_results if r["breseq_found"])
        hc_tp = sum(1 for r in bin_results if r["hc_found"])
        summary.append({
            "freq_bin": b,
            "n_truth": n,
            "breseq_TP": breseq_tp,
            "breseq_recall": f"{breseq_tp/n:.1%}",
            "hc_TP": hc_tp,
            "hc_recall": f"{hc_tp/n:.1%}",
        })

    # Totals for present variants
    n_present = len(present_results)
    breseq_present = sum(1 for r in present_results if r["breseq_found"])
    hc_present = sum(1 for r in present_results if r["hc_found"])
    summary.append({
        "freq_bin": "TOTAL (present)",
        "n_truth": n_present,
        "breseq_TP": breseq_present,
        "breseq_recall": f"{breseq_present/n_present:.1%}",
        "hc_TP": hc_present,
        "hc_recall": f"{hc_present/n_present:.1%}",
    })

    # Absent variants (expected 0% — calls here are false positives)
    n_absent = len(absent_results)
    breseq_fp = sum(1 for r in absent_results if r["breseq_found"])
    hc_fp = sum(1 for r in absent_results if r["hc_found"])
    summary.append({
        "freq_bin": "Absent (0%)",
        "n_truth": n_absent,
        "breseq_TP": breseq_fp,
        "breseq_recall": f"{breseq_fp}/{n_absent} FP",
        "hc_TP": hc_fp,
        "hc_recall": f"{hc_fp}/{n_absent} FP",
    })

    # --- Write summary CSV ---
    summary_path = os.path.join(OUTPUT_DIR, "precision_recall_by_freq_bin.csv")
    with open(summary_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "freq_bin", "n_truth", "breseq_TP", "breseq_recall", "hc_TP", "hc_recall"
        ])
        writer.writeheader()
        writer.writerows(summary)
    print(f"Summary written to: {summary_path}\n")

    # --- Console output: Recall table ---
    print("=== RECALL (expected-present variants) ===")
    print(f"{'Freq Bin':<20} {'N':>4} {'breseq TP':>10} {'breseq Recall':>14} {'HC TP':>8} {'HC Recall':>11}")
    print("-" * 70)
    for s in summary:
        if s["freq_bin"] == "Absent (0%)":
            continue
        print(f"{s['freq_bin']:<20} {s['n_truth']:>4} {s['breseq_TP']:>10} {s['breseq_recall']:>14} {s['hc_TP']:>8} {s['hc_recall']:>11}")

    # --- Console output: Absent variants (specificity) ---
    print(f"\n=== SPECIFICITY (expected-absent variants, expected_freq=0%) ===")
    print(f"Total absent entries: {n_absent}")
    print(f"  breseq false positives: {breseq_fp}/{n_absent}")
    print(f"  HC false positives:     {hc_fp}/{n_absent}")
    if breseq_fp > 0 or hc_fp > 0:
        print("\n  False positive details:")
        for r in absent_results:
            if r["breseq_found"] or r["hc_found"]:
                tools = []
                if r["breseq_found"]:
                    tools.append(f"breseq AF={r['breseq_af']:.3f}")
                if r["hc_found"]:
                    tools.append(f"HC AF={r['hc_af']:.3f}")
                print(f"    {r['gene']} {r['chrom']}:{r['pos']} {r['ref']}>{r['alt']} in {r['sample']} — {', '.join(tools)}")

    # --- Missed variants ---
    missed = [r for r in present_results if not r["breseq_found"] and not r["hc_found"]]
    print("\n--- Variants missed by BOTH tools ---")
    if missed:
        for m in missed:
            print(f"  {m['gene']} {m['chrom']}:{m['pos']} {m['ref']}>{m['alt']} in {m['sample']} (expected {m['expected_freq']}%)")
    else:
        print("  None — all expected-present variants found by at least one tool")


if __name__ == "__main__":
    main()
