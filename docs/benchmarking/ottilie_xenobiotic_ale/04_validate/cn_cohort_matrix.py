#!/usr/bin/env python
"""
CN Cohort Matrix — enriches bin-level continuous CN matrix with integer
diploid_cn from segment-level calls.

Reads:
  - cn_bins_continuous.csv  (wide: chromosome,start,end,{sample}_log2,{sample}_absolute_cn)
  - cn_segments_sensitive.csv (long: sample,chromosome,start,end,...,diploid_cn)

Outputs a wide CSV with {sample}_diploid_cn columns added for each sample.

With --collapse, adjacent bins on the same chromosome with identical diploid_cn
across all samples are merged into single rows. Continuous columns (log2, cn)
are averaged over the merged bins.

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
from bisect import bisect_right
from pathlib import Path


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


def merge_group(rows, samples, continuous_cols, diploid_cn_cols):
    """Merge a group of adjacent bins into one row, averaging continuous columns."""
    merged = dict(rows[0])
    merged["end"] = rows[-1]["end"]
    n = len(rows)
    for col in continuous_cols:
        vals = [float(r[col]) for r in rows if r[col] != ""]
        merged[col] = f"{sum(vals) / len(vals):.4f}" if vals else ""
    # diploid_cn is identical across group (that's why they were grouped)
    for col in diploid_cn_cols:
        merged[col] = rows[0][col]
    return merged


def main():
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--cn-dir", required=True,
                        help="Directory containing cn_bins_continuous.csv and cn_segments_sensitive.csv")
    parser.add_argument("--csv", required=True,
                        help="Output CSV path")
    parser.add_argument("--segments", default="sensitive",
                        choices=["sensitive", "stringent"],
                        help="Which segment file to use for diploid_cn overlay (default: sensitive)")
    parser.add_argument("--collapse", action="store_true",
                        help="Collapse adjacent bins with identical diploid_cn across all samples")
    parser.add_argument("--fai", default=None,
                        help="Reference .fai index file for chromosome lengths (adds chr_length column to collapsed output)")
    args = parser.parse_args()

    cn_dir = Path(args.cn_dir)
    bins_path = cn_dir / "cn_bins_continuous.csv"
    segments_path = cn_dir / f"cn_segments_{args.segments}.csv"

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

    print(f"Segments: {args.segments}")
    print(f"Samples: {', '.join(samples)}")

    # Load segment lookup
    seg_lookup = load_segments(segments_path)

    # Read bins and enrich with diploid_cn
    out_path = Path(args.csv)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # Read and enrich all bins
    enriched_rows = []
    with open(bins_path) as fin:
        reader = csv.DictReader(fin)
        out_fields = list(reader.fieldnames)
        for s in samples:
            out_fields.append(f"{s}_diploid_cn")

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

            enriched_rows.append(row)

    total = mapped + unmapped
    print(f"Bins enriched: {mapped}/{total} ({mapped/total*100:.1f}%) mapped to segments")
    if unmapped:
        print(f"  {unmapped} bins had no matching segment (gaps between segments)")

    # Collapse adjacent bins with identical diploid_cn across all samples
    if args.collapse:
        diploid_cn_cols = [f"{s}_diploid_cn" for s in samples]
        continuous_cols = []
        for s in samples:
            continuous_cols.extend([f"{s}_log2", f"{s}_absolute_cn"])

        collapsed = []
        group = [enriched_rows[0]]

        def cn_key(row):
            return (row["chromosome"], tuple(row[c] for c in diploid_cn_cols))

        for row in enriched_rows[1:]:
            prev = group[-1]
            # Same chromosome, contiguous, same diploid_cn for all samples
            if (row["chromosome"] == prev["chromosome"]
                    and int(row["start"]) == int(prev["end"])
                    and cn_key(row) == cn_key(prev)):
                group.append(row)
            else:
                collapsed.append(merge_group(group, samples, continuous_cols, diploid_cn_cols))
                group = [row]
        collapsed.append(merge_group(group, samples, continuous_cols, diploid_cn_cols))

        print(f"Collapsed: {len(enriched_rows)} bins → {len(collapsed)} regions")
        enriched_rows = collapsed

        # Add chr_length column from .fai if provided
        if args.fai:
            chr_lengths = load_chr_lengths(args.fai)
            # Insert chr_length after 'end'
            end_idx = out_fields.index("end") + 1
            out_fields.insert(end_idx, "chr_length")
            for row in enriched_rows:
                row["chr_length"] = chr_lengths.get(row["chromosome"], "")

    # Write output
    with open(out_path, "w", newline="") as fout:
        writer = csv.DictWriter(fout, fieldnames=out_fields)
        writer.writeheader()
        for row in enriched_rows:
            writer.writerow(row)

    print(f"Output: {out_path}")


if __name__ == "__main__":
    main()
