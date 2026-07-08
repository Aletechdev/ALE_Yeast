#!/usr/bin/env python
"""
Build dual CN matrices from CNVKit output for multi-sample ALE analysis.

Produces three matrix types:
  1. "call" segment matrix     — from .md.call.cns (re-centered log2, has p_ttest)
  2. "germline" segment matrix — from .md.germline.call.cns (CI-filtered, no re-centering)
  3. Continuous bin matrix      — from .md.cnr (bin-level, uniform ~5kb bins)

Also produces a comparison report showing where "call" and "germline" disagree.

Output files:
  cn_segments_call.csv       — per-segment detail from .md.call.cns (sensitive, has p_ttest)
  cn_segments_germline.csv   — per-segment detail from .md.germline.call.cns (CI-filtered)
  cn_chr_summary_call.csv    — one row per chromosome, dominant segment from .md.call.cns
  cn_chr_summary_germline.csv— one row per chromosome, dominant segment from .md.germline.call.cns
  cn_call_vs_germline.csv    — rows where call and germline fold_change disagree by >0.1
  cn_bins_continuous.csv     — bin-level log2/fold_change from .md.cnr (all samples aligned)

Usage:
    python bin/build_cn_matrix.py --output-dir output_ottilie --fai data/ottilie/S288C_reference/S288C_R64.fa.fai

See docs/variant-calling/cnvkit/cnvkit_cn_calculation.md for formula details.
See docs/variant-calling/cnvkit/cnvkit_sarek_dual_call.md for .call.cns vs .germline.call.cns.
"""

import argparse
import csv
import math
import sys
from pathlib import Path


def load_chr_lengths(fai_path):
    """Load chromosome lengths and order from a samtools .fai index file.

    Format: chrom\tlength\toffset\tlinebases\tlinewidth
    Returns: (chr_lengths dict, chr_order list) preserving .fai order.
    """
    lengths = {}
    order = []
    with open(fai_path) as f:
        for line in f:
            parts = line.strip().split("\t")
            lengths[parts[0]] = int(parts[1])
            order.append(parts[0])
    return lengths, order


def discover_samples(output_dir):
    """Find all samples with CNVKit output."""
    cnvkit_dir = Path(output_dir) / "variant_calling/cnvkit"
    if not cnvkit_dir.exists():
        sys.exit(f"CNVKit output directory not found: {cnvkit_dir}")
    samples = sorted(d.name for d in cnvkit_dir.iterdir() if d.is_dir())
    if not samples:
        sys.exit(f"No sample directories found in {cnvkit_dir}")
    return samples


def load_cns(cns_path):
    """Load a .cns file into a list of segment dicts."""
    segments = []
    with open(cns_path) as f:
        header = f.readline().strip().split("\t")
        for line in f:
            parts = line.strip().split("\t")
            d = dict(zip(header, parts))
            seg = {
                "chrom": d["chromosome"],
                "start": int(d["start"]),
                "end": int(d["end"]),
                "log2": float(d["log2"]),
                "depth": float(d["depth"]),
                "probes": int(d["probes"]),
            }
            if "p_ttest" in d:
                seg["p_ttest"] = float(d["p_ttest"])
            segments.append(seg)
    return segments


def load_cnr(cnr_path):
    """Load a .cnr file into a list of bin dicts."""
    bins = []
    with open(cnr_path) as f:
        header = f.readline().strip().split("\t")
        for line in f:
            parts = line.strip().split("\t")
            d = dict(zip(header, parts))
            bins.append({
                "chrom": d["chromosome"],
                "start": int(d["start"]),
                "end": int(d["end"]),
                "depth": float(d["depth"]),
                "log2": float(d["log2"]),
            })
    return bins


def build_segment_matrix(output_dir, samples, cns_suffix):
    """Build a segment-level CN matrix.

    Since segment boundaries differ per sample, the matrix is organized as
    one row per (sample, segment) with a chr-level summary appended.

    Returns:
        segments_by_sample: dict of sample -> list of segment dicts (with fold_change added)
    """
    segments_by_sample = {}
    for sample in samples:
        cns_path = Path(output_dir) / f"variant_calling/cnvkit/{sample}/{sample}.{cns_suffix}"
        if not cns_path.exists():
            print(f"  WARNING: {cns_path.name} not found for {sample}, skipping", file=sys.stderr)
            continue
        segs = load_cns(cns_path)
        for seg in segs:
            seg["fold_change"] = 2 ** seg["log2"]
        segments_by_sample[sample] = segs
    return segments_by_sample


def build_chr_summary(segments_by_sample, samples, chr_lengths, chr_order):
    """Build chromosome-level summary: one row per chromosome, CN per sample.

    For chromosomes with multiple segments, uses the segment covering the
    largest fraction of the chromosome.
    """
    rows = []
    for chrom in chr_order:
        chr_len = chr_lengths.get(chrom, 0)
        row = {"chromosome": chrom, "length": chr_len}
        for sample in samples:
            segs = segments_by_sample.get(sample, [])
            chr_segs = [s for s in segs if s["chrom"] == chrom]
            if not chr_segs:
                row[f"{sample}_log2"] = ""
                row[f"{sample}_fold_change"] = ""
                continue
            # Pick the dominant segment (largest span)
            dominant = max(chr_segs, key=lambda s: s["end"] - s["start"])
            row[f"{sample}_log2"] = f"{dominant['log2']:.4f}"
            row[f"{sample}_fold_change"] = f"{dominant['fold_change']:.3f}"
        rows.append(row)
    return rows


def build_cnr_matrix(output_dir, samples):
    """Build bin-level continuous CN matrix from .cnr files.

    All samples share identical bin coordinates, so rows align directly.
    """
    # Load first sample to get bin coordinates
    first_sample = samples[0]
    cnr_path = Path(output_dir) / f"variant_calling/cnvkit/{first_sample}/{first_sample}.md.cnr"
    if not cnr_path.exists():
        return None
    ref_bins = load_cnr(cnr_path)

    # Build matrix: bin coords + per-sample log2 + fold_change
    matrix = []
    sample_data = {}
    for sample in samples:
        cnr_path = Path(output_dir) / f"variant_calling/cnvkit/{sample}/{sample}.md.cnr"
        if not cnr_path.exists():
            print(f"  WARNING: {cnr_path.name} not found, skipping", file=sys.stderr)
            continue
        sample_data[sample] = load_cnr(cnr_path)

    for i, ref_bin in enumerate(ref_bins):
        row = {
            "chromosome": ref_bin["chrom"],
            "start": ref_bin["start"],
            "end": ref_bin["end"],
        }
        for sample in samples:
            if sample not in sample_data:
                row[f"{sample}_log2"] = ""
                row[f"{sample}_fold_change"] = ""
                continue
            bins = sample_data[sample]
            if i < len(bins):
                b = bins[i]
                row[f"{sample}_log2"] = f"{b['log2']:.4f}"
                row[f"{sample}_fold_change"] = f"{2 ** b['log2']:.3f}"
            else:
                row[f"{sample}_log2"] = ""
                row[f"{sample}_fold_change"] = ""
        matrix.append(row)
    return matrix


def compare_matrices(call_segs, germline_segs, samples):
    """Compare call vs germline CN calls, report disagreements.

    "call" = .md.call.cns (re-centered, sensitive)
    "germline" = .md.germline.call.cns (CI-filtered, stringent)
    """
    disagreements = []
    for sample in samples:
        sens_segs = call_segs.get(sample, [])
        stri_segs = germline_segs.get(sample, [])

        # Build per-chromosome CN lookup for each
        def chr_cn_map(segs):
            result = {}
            for seg in segs:
                key = (seg["chrom"], seg["start"], seg["end"])
                result[key] = seg
            return result

        sens_map = chr_cn_map(sens_segs)
        stri_map = chr_cn_map(stri_segs)

        # Compare matching segments (same boundaries)
        for key, sens_seg in sens_map.items():
            stri_seg = stri_map.get(key)
            if stri_seg and abs(sens_seg["fold_change"] - stri_seg["fold_change"]) > 0.1:
                span_kb = (sens_seg["end"] - sens_seg["start"]) / 1000
                disagreements.append({
                    "sample": sample,
                    "chromosome": sens_seg["chrom"],
                    "start": sens_seg["start"],
                    "end": sens_seg["end"],
                    "span_kb": f"{span_kb:.0f}",
                    "call_fc": f"{sens_seg['fold_change']:.3f}",
                    "call_log2": f"{sens_seg['log2']:.4f}",
                    "germline_fc": f"{stri_seg['fold_change']:.3f}",
                    "germline_log2": f"{stri_seg['log2']:.4f}",
                    "p_ttest": f"{sens_seg.get('p_ttest', float('nan')):.2e}",
                    "probes": sens_seg["probes"],
                })

        # Check for segments present in one but not the other (different boundaries)
        # This happens when segment count differs between files
        if len(sens_segs) != len(stri_segs):
            disagreements.append({
                "sample": sample,
                "chromosome": "-",
                "start": 0,
                "end": 0,
                "span_kb": "0",
                "call_fc": f"{len(sens_segs)} segs",
                "call_log2": "-",
                "germline_fc": f"{len(stri_segs)} segs",
                "germline_log2": "-",
                "p_ttest": "-",
                "probes": "-",
            })

    return disagreements


def write_segment_csv(segments_by_sample, samples, output_path, has_ptest):
    """Write per-segment detail CSV."""
    fieldnames = ["sample", "chromosome", "start", "end", "log2",
                  "fold_change", "depth", "probes"]
    if has_ptest:
        fieldnames.append("p_ttest")

    with open(output_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for sample in samples:
            for seg in segments_by_sample.get(sample, []):
                row = {
                    "sample": sample,
                    "chromosome": seg["chrom"],
                    "start": seg["start"],
                    "end": seg["end"],
                    "log2": f"{seg['log2']:.4f}",
                    "fold_change": f"{seg['fold_change']:.3f}",
                    "depth": f"{seg['depth']:.1f}",
                    "probes": seg["probes"],
                }
                if has_ptest:
                    row["p_ttest"] = f"{seg.get('p_ttest', float('nan')):.2e}"
                writer.writerow(row)


def write_chr_summary_csv(chr_summary, samples, output_path):
    """Write chromosome-level summary CSV."""
    fieldnames = ["chromosome", "length"]
    for sample in samples:
        fieldnames.extend([f"{sample}_log2", f"{sample}_fold_change"])

    with open(output_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in chr_summary:
            writer.writerow(row)


def write_cnr_matrix_csv(matrix, samples, output_path):
    """Write bin-level continuous CN matrix CSV."""
    fieldnames = ["chromosome", "start", "end"]
    for sample in samples:
        fieldnames.extend([f"{sample}_log2", f"{sample}_fold_change"])

    with open(output_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in matrix:
            writer.writerow(row)


def write_comparison_csv(disagreements, output_path):
    """Write call vs germline comparison CSV."""
    if not disagreements:
        return
    fieldnames = ["sample", "chromosome", "start", "end", "span_kb",
                  "call_fc", "call_log2", "germline_fc",
                  "germline_log2", "p_ttest", "probes"]
    with open(output_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in disagreements:
            writer.writerow(row)


def main():
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--output-dir", required=True,
                        help="Pipeline output directory (e.g., output_ottilie)")
    parser.add_argument("--results-dir", default=None,
                        help="Directory for output CSVs (default: <output-dir>/cn_matrices)")
    parser.add_argument("--samples", nargs="+", default=None,
                        help="Specific samples to include (default: all)")
    parser.add_argument("--skip-cnr", action="store_true",
                        help="Skip bin-level .cnr matrix (faster)")
    parser.add_argument("--fai", required=True,
                        help="Reference .fai index file for chromosome lengths and order")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    results_dir = Path(args.results_dir) if args.results_dir else output_dir / "cn_matrices"
    results_dir.mkdir(parents=True, exist_ok=True)

    # Load chromosome lengths from .fai
    chr_lengths, chr_order = load_chr_lengths(args.fai)
    print(f"Reference: {args.fai} ({len(chr_lengths)} chromosomes)")

    # Discover samples
    all_samples = discover_samples(output_dir)
    samples = args.samples if args.samples else all_samples
    samples = [s for s in samples if s in all_samples]

    print(f"Samples: {', '.join(samples)}")
    print(f"Output: {results_dir}")

    # 1. "call" matrix — from {sample}.md.call.cns
    #    Source: cnvkit.py call → re-centered log2, includes p_ttest column.
    #    More sensitive: reports all segments with shifted log2, even marginal ones.
    #    CNVKit docs call this the "call" step (applies thresholds to assign CN states).
    print("\n1. Building 'call' segment matrix (.md.call.cns)...")
    call_segs = build_segment_matrix(output_dir, samples, "md.call.cns")
    write_segment_csv(call_segs, samples,
                      results_dir / "cn_segments_call.csv", has_ptest=True)
    call_chr = build_chr_summary(call_segs, samples, chr_lengths, chr_order)
    write_chr_summary_csv(call_chr, samples,
                          results_dir / "cn_chr_summary_call.csv")
    print(f"   Wrote {sum(len(v) for v in call_segs.values())} segments across {len(call_segs)} samples")

    # 2. "germline" matrix — from {sample}.md.germline.call.cns
    #    Source: cnvkit.py call --filter germline → CI-filtered, no re-centering.
    #    More stringent: drops segments where the confidence interval overlaps neutral.
    #    Fewer segments but higher confidence; used by the dashboard for display.
    print("2. Building 'germline' segment matrix (.md.germline.call.cns)...")
    germline_segs = build_segment_matrix(output_dir, samples, "md.germline.call.cns")
    write_segment_csv(germline_segs, samples,
                      results_dir / "cn_segments_germline.csv", has_ptest=False)
    germline_chr = build_chr_summary(germline_segs, samples, chr_lengths, chr_order)
    write_chr_summary_csv(germline_chr, samples,
                          results_dir / "cn_chr_summary_germline.csv")
    print(f"   Wrote {sum(len(v) for v in germline_segs.values())} segments across {len(germline_segs)} samples")

    # 3. Comparison — where call vs germline CN calls disagree
    #    Useful for debugging: shows segments present in "call" but filtered out by
    #    germline CI filter, or where re-centering shifted log2 values significantly.
    print("3. Comparing call vs germline...")
    disagreements = compare_matrices(call_segs, germline_segs, samples)
    write_comparison_csv(disagreements, results_dir / "cn_call_vs_germline.csv")
    if disagreements:
        print(f"   {len(disagreements)} disagreement(s):")
        for d in disagreements:
            if d["chromosome"] == "-":
                print(f"     {d['sample']}: segment count differs "
                      f"({d['call_fc']} vs {d['germline_fc']})")
            else:
                print(f"     {d['sample']} {d['chromosome']}:{d['start']}-{d['end']} "
                      f"({d['span_kb']}kb): fc={d['call_fc']} vs fc={d['germline_fc']} "
                      f"(log2={d['call_log2']} vs {d['germline_log2']}, p={d['p_ttest']})")
    else:
        print("   No CN disagreements between call and germline matrices")

    # 4. Continuous bin matrix (.md.cnr)
    if not args.skip_cnr:
        print("4. Building continuous bin matrix (.md.cnr)...")
        cnr_matrix = build_cnr_matrix(output_dir, samples)
        if cnr_matrix:
            write_cnr_matrix_csv(cnr_matrix, samples,
                                 results_dir / "cn_bins_continuous.csv")
            print(f"   Wrote {len(cnr_matrix)} bins x {len(samples)} samples")
        else:
            print("   WARNING: No .cnr files found, skipping")
    else:
        print("4. Skipping bin matrix (--skip-cnr)")

    # Summary
    print(f"\n{'=' * 60}")
    print("Output files:")
    for f in sorted(results_dir.glob("*.csv")):
        size_kb = f.stat().st_size / 1024
        print(f"  {f.name} ({size_kb:.0f} KB)")
    print(f"\nNote: fold_change = 2^log2 (ploidy-agnostic depth ratio).")
    print(f"  fold_change=1.0 = same as reference, >1 = gain, <1 = loss")


if __name__ == "__main__":
    main()
