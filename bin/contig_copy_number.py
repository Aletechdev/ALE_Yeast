#!/usr/bin/env python
"""
Contig copy number — one row per contig, one column set per sample, built from TIDDIT's
per-contig coverage table (<sample>.tiddit.ploidies.tab).

TIDDIT (tiddit_coverage_analysis.determine_ploidy) writes, per contig:
    Ploidy         = n * median_bin_cov(contig) / median_bin_cov(genome)
    Ploidy_rounded = round(Ploidy)
    Mean_coverage  = median_bin_cov(contig)        (misnamed upstream: it is a median)
where n is the `-n` argument — the organism ploidy the pipeline passes from the samplesheet
`ploidy` column. So Ploidy is a coverage ratio scaled by the sample's own n, and it is only
comparable across samples once n is divided out again. This script exports:
    <sample>_fold_change    = Ploidy / n     (depth relative to the sample's genome median; 1.0 = baseline)
    <sample>_log2           = log2(fold_change)
    <sample>_tiddit_ploidy  = Ploidy         (as written by TIDDIT)
    <sample>_median_cov     = Mean_coverage
    <sample>_n              = n
Column naming follows the CNVKit CN matrices (<sample>_log2 / <sample>_fold_change, 4 / 3 decimals)
so the dashboard renders all copy-number tables with one formatter and one fold-change/log2 toggle.
Whole-contig only. This is the one place the mitochondrial contig is quantified: CNVKit
drops every Mito bin via its hard-coded 0.30-0.70 GC mask (yeast mtDNA is ~17% GC).

Usage (from BUILD_CONTIG_CN):
    contig_copy_number.py --tabs *.tiddit.ploidies.tab \
        --ploidies CBR110-15-R3a=1 NODRUG-GM2=1 --csv contig_copy_number.csv
"""

import argparse
import csv
import math
import sys
from pathlib import Path

CHR_ORDER = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII",
             "IX", "X", "XI", "XII", "XIII", "XIV", "XV", "XVI"]
TAB_SUFFIX = ".tiddit.ploidies.tab"


def chr_sort_key(chrom):
    try:
        return (0, CHR_ORDER.index(chrom))
    except ValueError:
        return (1, chrom)


def sample_from_path(path):
    name = Path(path).name
    if not name.endswith(TAB_SUFFIX):
        sys.exit(f"unexpected filename (want <sample>{TAB_SUFFIX}): {name}")
    return name[: -len(TAB_SUFFIX)]


def parse_tab(path):
    rows = {}
    with open(path) as f:
        reader = csv.DictReader(f, delimiter="\t")
        for r in reader:
            rows[r["Chromosome"]] = {
                "ploidy": float(r["Ploidy"]),
                "median_cov": float(r["Mean_coverage"]),
            }
    return rows


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tabs", required=True, nargs="+", help="<sample>.tiddit.ploidies.tab files")
    ap.add_argument("--ploidies", required=True, nargs="+",
                    help="sample=n pairs: the -n ploidy TIDDIT was run with for each sample")
    ap.add_argument("--csv", required=True, help="output CSV")
    args = ap.parse_args()

    n_by_sample = {}
    for item in args.ploidies:
        if "=" not in item:
            sys.exit(f"--ploidies entries must be sample=n, got: {item}")
        s, n = item.split("=", 1)
        n_by_sample[s] = float(n)

    data = {}
    for tab in sorted(args.tabs):
        s = sample_from_path(tab)
        if s not in n_by_sample:
            sys.exit(f"no --ploidies entry for sample {s}")
        data[s] = parse_tab(tab)
    samples = sorted(data)

    contigs = sorted({c for s in samples for c in data[s]}, key=chr_sort_key)

    fieldnames = ["chromosome"]
    for s in samples:
        fieldnames += [f"{s}_log2", f"{s}_fold_change", f"{s}_tiddit_ploidy", f"{s}_median_cov", f"{s}_n"]

    out = Path(args.csv)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, lineterminator="\n")
        w.writeheader()
        for c in contigs:
            row = {"chromosome": c}
            for s in samples:
                n = n_by_sample[s]
                rec = data[s].get(c)
                if rec is None:
                    row.update({f"{s}_log2": "", f"{s}_fold_change": "", f"{s}_tiddit_ploidy": "",
                                f"{s}_median_cov": "", f"{s}_n": f"{n:g}"})
                    continue
                fc = rec["ploidy"] / n if n else None
                row[f"{s}_fold_change"] = f"{fc:.3f}" if fc is not None else ""
                row[f"{s}_log2"] = f"{math.log2(fc):.4f}" if fc else ""   # empty for 0 coverage
                row[f"{s}_tiddit_ploidy"] = f"{rec['ploidy']:.4f}"
                row[f"{s}_median_cov"] = f"{rec['median_cov']:.1f}"
                row[f"{s}_n"] = f"{n:g}"
            w.writerow(row)

    print(f"Samples: {', '.join(samples)}")
    print(f"Contigs: {len(contigs)}")
    print(f"Output: {out}")


if __name__ == "__main__":
    main()
