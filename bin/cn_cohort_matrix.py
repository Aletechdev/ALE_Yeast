#!/usr/bin/env python
"""
CN Cohort Matrix — reads bin-level continuous CN matrix and optionally
collapses by removing baseline bins and merging adjacent non-baseline bins.

Reads:
  - cn_bins_continuous.csv  (wide: chromosome,start,end,{sample}_log2,{sample}_fold_change)

With --collapse, bins where ALL samples are baseline (|log2| < 0.3) are removed,
then adjacent non-baseline bins on the same chromosome are merged into single rows.
log2 is averaged; fold_change is re-derived as 2^avg_log2 to avoid Jensen's
inequality (mean(2^x) != 2^mean(x)).

Usage:
    python cn_cohort_matrix.py \
        --cn-dir output_ottilie/cn_matrices \
        --csv results/cn_cohort_matrix.csv

    # Collapsed with chromosome lengths from .fai:
    python cn_cohort_matrix.py \
        --cn-dir output_ottilie/cn_matrices \
        --csv results/cn_cohort_matrix_collapsed.csv \
        --collapse \
        --fai data/ottilie/S288C_reference/S288C_R64.fa.fai
"""

import argparse
import csv
import sys
from pathlib import Path

BASELINE_THRESH = 0.3  # |log2| below this is considered baseline (fc 0.81–1.23)


def load_chr_lengths(fai_path):
    """Load chromosome lengths from a samtools .fai index file.

    Format: chrom\tlength\toffset\tlinebases\tlinewidth
    Returns: {chrom: length} dict.
    """
    lengths = {}
    with open(fai_path) as f:
        for line in f:
            parts = line.strip().split("\t")
            lengths[parts[0]] = int(parts[1])
    return lengths


def is_baseline(row, log2_cols):
    """True if ALL samples have |log2| < threshold (boring bin)."""
    for col in log2_cols:
        val = row.get(col, "")
        if val == "":
            continue
        if abs(float(val)) >= BASELINE_THRESH:
            return False
    return True


def merge_group(rows, log2_cols):
    """Merge a group of adjacent bins into one row.

    log2 columns are averaged; fold_change is re-derived from averaged log2
    to maintain consistency (fold_change = 2^log2 exactly).
    """
    merged = dict(rows[0])
    merged["end"] = rows[-1]["end"]
    for col in log2_cols:
        vals = [float(r[col]) for r in rows if r[col] != ""]
        if vals:
            avg_log2 = sum(vals) / len(vals)
            merged[col] = f"{avg_log2:.4f}"
            fc_col = col.replace("_log2", "_fold_change")
            merged[fc_col] = f"{2 ** avg_log2:.3f}"
        else:
            merged[col] = ""
            fc_col = col.replace("_log2", "_fold_change")
            merged[fc_col] = ""
    return merged


def main():
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--cn-dir", required=True,
                        help="Directory containing cn_bins_continuous.csv")
    parser.add_argument("--csv", required=True,
                        help="Output CSV path")
    parser.add_argument("--collapse", action="store_true",
                        help="Remove baseline bins (|log2|<0.3 in all samples) and merge adjacent non-baseline bins")
    parser.add_argument("--fai", default=None,
                        help="Reference .fai index file for chromosome lengths (adds chr_length column to collapsed output)")
    args = parser.parse_args()

    cn_dir = Path(args.cn_dir)
    bins_path = cn_dir / "cn_bins_continuous.csv"

    if not bins_path.exists():
        print(f"ERROR: {bins_path} not found", file=sys.stderr)
        sys.exit(1)

    # Discover sample names from bin header
    with open(bins_path) as f:
        header = f.readline().strip().split(",")
    samples = []
    for col in header:
        if col.endswith("_log2"):
            samples.append(col[:-5])

    print(f"Samples: {', '.join(samples)}")

    # Read all bins
    out_path = Path(args.csv)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    rows = []
    with open(bins_path) as fin:
        reader = csv.DictReader(fin)
        out_fields = list(reader.fieldnames)
        for row in reader:
            rows.append(row)

    print(f"Loaded {len(rows)} bins")

    if args.collapse:
        log2_cols = [f"{s}_log2" for s in samples]

        # Step 1: Remove baseline bins
        non_baseline = [r for r in rows if not is_baseline(r, log2_cols)]
        n_removed = len(rows) - len(non_baseline)
        print(f"Baseline removed: {n_removed}/{len(rows)} bins "
              f"(|log2|<{BASELINE_THRESH} in all samples)")

        # Step 2: Merge adjacent non-baseline bins on same chromosome
        if non_baseline:
            collapsed = []
            group = [non_baseline[0]]

            for row in non_baseline[1:]:
                prev = group[-1]
                if (row["chromosome"] == prev["chromosome"]
                        and int(row["start"]) == int(prev["end"])):
                    group.append(row)
                else:
                    collapsed.append(merge_group(group, log2_cols))
                    group = [row]
            collapsed.append(merge_group(group, log2_cols))

            print(f"Merged: {len(non_baseline)} bins -> {len(collapsed)} regions")
            rows = collapsed
        else:
            rows = []
            print("No non-baseline bins found")

        # Add chr_length column from .fai if provided
        if args.fai:
            chr_lengths = load_chr_lengths(args.fai)
            end_idx = out_fields.index("end") + 1
            out_fields.insert(end_idx, "chr_length")
            for row in rows:
                row["chr_length"] = chr_lengths.get(row["chromosome"], "")

    # Write output
    with open(out_path, "w", newline="") as fout:
        writer = csv.DictWriter(fout, fieldnames=out_fields, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)

    print(f"Output: {out_path}")


if __name__ == "__main__":
    main()
