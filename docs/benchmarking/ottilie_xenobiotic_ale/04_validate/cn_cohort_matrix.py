#!/usr/bin/env python
"""
CN Cohort Matrix — enriches bin-level continuous CN matrix with integer
diploid_cn from segment-level calls.

Reads:
  - cn_bins_continuous.csv  (wide: chromosome,start,end,{sample}_log2,{sample}_cn)
  - cn_segments_sensitive.csv (long: sample,chromosome,start,end,...,diploid_cn)

Outputs a wide CSV with {sample}_diploid_cn columns added for each sample.

Usage:
    python cn_cohort_matrix.py \
        --cn-dir output_ottilie/cn_matrices \
        --csv results/cn_cohort_matrix.csv
"""

import argparse
import csv
import sys
from bisect import bisect_right
from pathlib import Path


def load_segments(segments_path):
    """Load segments and build per-sample lookup: {(sample, chrom): [(start, end, diploid_cn), ...]}."""
    lookup = {}
    with open(segments_path) as f:
        for row in csv.DictReader(f):
            key = (row["sample"], row["chromosome"])
            lookup.setdefault(key, []).append((
                int(row["start"]),
                int(row["end"]),
                int(row["diploid_cn"]),
            ))
    # Sort each list by start position for bisect
    for key in lookup:
        lookup[key].sort()
    return lookup


def find_diploid_cn(segments, midpoint):
    """Find the diploid_cn for a bin midpoint using bisect on segment starts."""
    if not segments:
        return None
    starts = [s[0] for s in segments]
    idx = bisect_right(starts, midpoint) - 1
    if idx < 0:
        return None
    start, end, cn = segments[idx]
    if start <= midpoint < end:
        return cn
    return None


def main():
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--cn-dir", required=True,
                        help="Directory containing cn_bins_continuous.csv and cn_segments_sensitive.csv")
    parser.add_argument("--csv", required=True,
                        help="Output CSV path")
    args = parser.parse_args()

    cn_dir = Path(args.cn_dir)
    bins_path = cn_dir / "cn_bins_continuous.csv"
    segments_path = cn_dir / "cn_segments_sensitive.csv"

    for p in (bins_path, segments_path):
        if not p.exists():
            print(f"ERROR: {p} not found", file=sys.stderr)
            sys.exit(1)

    # Discover sample names from bin header
    with open(bins_path) as f:
        header = f.readline().strip().split(",")
    samples = []
    for col in header:
        if col.endswith("_log2"):
            samples.append(col[:-5])

    print(f"Samples: {', '.join(samples)}")

    # Load segment lookup
    seg_lookup = load_segments(segments_path)

    # Read bins and enrich with diploid_cn
    out_path = Path(args.csv)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with open(bins_path) as fin, open(out_path, "w", newline="") as fout:
        reader = csv.DictReader(fin)
        # Build output header: original columns + {sample}_diploid_cn
        out_fields = list(reader.fieldnames)
        for s in samples:
            out_fields.append(f"{s}_diploid_cn")

        writer = csv.DictWriter(fout, fieldnames=out_fields)
        writer.writeheader()

        mapped = 0
        unmapped = 0
        for row in reader:
            chrom = row["chromosome"]
            start = int(row["start"])
            end = int(row["end"])
            midpoint = (start + end) // 2

            for s in samples:
                segs = seg_lookup.get((s, chrom), [])
                cn = find_diploid_cn(segs, midpoint)
                row[f"{s}_diploid_cn"] = cn if cn is not None else ""
                if cn is not None:
                    mapped += 1
                else:
                    unmapped += 1

            writer.writerow(row)

    total = mapped + unmapped
    print(f"Bins enriched: {mapped}/{total} ({mapped/total*100:.1f}%) mapped to segments")
    if unmapped:
        print(f"  {unmapped} bins had no matching segment (gaps between segments)")
    print(f"Output: {out_path}")


if __name__ == "__main__":
    main()
