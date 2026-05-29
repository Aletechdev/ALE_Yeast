#!/usr/bin/env python
"""
Build dual CN matrices from CNVKit output for multi-sample ALE analysis.

Produces three matrix types:
  1. Sensitive segment matrix  — from .md.call.cns (re-centered log2, has p_ttest)
  2. Stringent segment matrix  — from .md.germline.call.cns (CI-filtered, no re-centering)
  3. Continuous bin matrix      — from .md.cnr (bin-level, uniform ~5kb bins)

Also produces a comparison report showing where sensitive and stringent disagree.

Usage:
    python bin/build_cn_matrix.py --output-dir output_ottilie --results-dir results/cn_matrices
    python bin/build_cn_matrix.py --output-dir output_ottilie --ploidy 1  # haploid samples

See docs/variant-calling/cnvkit/cnvkit_cn_calculation.md for formula details.
See docs/variant-calling/cnvkit/cnvkit_sarek_dual_call.md for .call.cns vs .germline.call.cns.
"""

import argparse
import csv
import math
import sys
from pathlib import Path

# S288C R64-1-1 chromosome lengths (Ensembl)
CHR_LENGTHS = {
    "I": 230218, "II": 813184, "III": 316620, "IV": 1531933,
    "V": 576874, "VI": 270161, "VII": 1090940, "VIII": 562643,
    "IX": 439888, "X": 745751, "XI": 666816, "XII": 1078177,
    "XIII": 924431, "XIV": 784333, "XV": 1091291, "XVI": 948066,
}

# Canonical chromosome order
CHR_ORDER = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII",
             "IX", "X", "XI", "XII", "XIII", "XIV", "XV", "XVI"]


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
                "diploid_cn": int(d["cn"]),
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


def build_segment_matrix(output_dir, samples, cns_suffix, ploidy):
    """Build a segment-level CN matrix.

    Since segment boundaries differ per sample, the matrix is organized as
    one row per (sample, segment) with a chr-level summary appended.

    Returns:
        segments_by_sample: dict of sample -> list of segment dicts (with absolute_cn added)
        chr_summary: list of dicts with per-chromosome CN per sample
    """
    segments_by_sample = {}
    for sample in samples:
        cns_path = Path(output_dir) / f"variant_calling/cnvkit/{sample}/{sample}.{cns_suffix}"
        if not cns_path.exists():
            print(f"  WARNING: {cns_path.name} not found for {sample}, skipping", file=sys.stderr)
            continue
        segs = load_cns(cns_path)
        for seg in segs:
            seg["absolute_cn"] = ploidy * 2 ** seg["log2"]
        segments_by_sample[sample] = segs
    return segments_by_sample


def build_chr_summary(segments_by_sample, samples):
    """Build chromosome-level summary: one row per chromosome, CN per sample.

    For chromosomes with multiple segments, uses the segment covering the
    largest fraction of the chromosome.
    """
    rows = []
    for chrom in CHR_ORDER:
        chr_len = CHR_LENGTHS.get(chrom, 0)
        row = {"chromosome": chrom, "length": chr_len}
        for sample in samples:
            segs = segments_by_sample.get(sample, [])
            chr_segs = [s for s in segs if s["chrom"] == chrom]
            if not chr_segs:
                row[f"{sample}_diploid_cn"] = ""
                row[f"{sample}_log2"] = ""
                row[f"{sample}_absolute_cn"] = ""
                continue
            # Pick the dominant segment (largest span)
            dominant = max(chr_segs, key=lambda s: s["end"] - s["start"])
            row[f"{sample}_diploid_cn"] = dominant["diploid_cn"]
            row[f"{sample}_log2"] = f"{dominant['log2']:.4f}"
            row[f"{sample}_absolute_cn"] = f"{dominant['absolute_cn']:.3f}"
            # Flag if chromosome has multiple segments with different CN
            cn_values = set(s["diploid_cn"] for s in chr_segs)
            if len(cn_values) > 1:
                row[f"{sample}_diploid_cn"] = f"{dominant['diploid_cn']}*"  # * = mixed
        rows.append(row)
    return rows


def build_cnr_matrix(output_dir, samples, ploidy):
    """Build bin-level continuous CN matrix from .cnr files.

    All samples share identical bin coordinates, so rows align directly.
    """
    # Load first sample to get bin coordinates
    first_sample = samples[0]
    cnr_path = Path(output_dir) / f"variant_calling/cnvkit/{first_sample}/{first_sample}.md.cnr"
    if not cnr_path.exists():
        return None
    ref_bins = load_cnr(cnr_path)

    # Build matrix: bin coords + per-sample log2 + absolute_cn
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
                row[f"{sample}_absolute_cn"] = ""
                continue
            bins = sample_data[sample]
            if i < len(bins):
                b = bins[i]
                row[f"{sample}_log2"] = f"{b['log2']:.4f}"
                row[f"{sample}_absolute_cn"] = f"{ploidy * 2 ** b['log2']:.3f}"
            else:
                row[f"{sample}_log2"] = ""
                row[f"{sample}_absolute_cn"] = ""
        matrix.append(row)
    return matrix


def compare_matrices(sensitive, stringent, samples):
    """Compare sensitive vs stringent CN calls, report disagreements."""
    disagreements = []
    for sample in samples:
        sens_segs = sensitive.get(sample, [])
        stri_segs = stringent.get(sample, [])

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
            if stri_seg and sens_seg["diploid_cn"] != stri_seg["diploid_cn"]:
                chr_len = CHR_LENGTHS.get(sens_seg["chrom"], 0)
                span_kb = (sens_seg["end"] - sens_seg["start"]) / 1000
                disagreements.append({
                    "sample": sample,
                    "chromosome": sens_seg["chrom"],
                    "start": sens_seg["start"],
                    "end": sens_seg["end"],
                    "span_kb": f"{span_kb:.0f}",
                    "sensitive_cn": sens_seg["diploid_cn"],
                    "sensitive_log2": f"{sens_seg['log2']:.4f}",
                    "stringent_cn": stri_seg["diploid_cn"],
                    "stringent_log2": f"{stri_seg['log2']:.4f}",
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
                "sensitive_cn": f"{len(sens_segs)} segs",
                "sensitive_log2": "-",
                "stringent_cn": f"{len(stri_segs)} segs",
                "stringent_log2": "-",
                "p_ttest": "-",
                "probes": "-",
            })

    return disagreements


def write_segment_csv(segments_by_sample, samples, output_path, has_ptest):
    """Write per-segment detail CSV."""
    fieldnames = ["sample", "chromosome", "start", "end", "log2", "diploid_cn",
                  "absolute_cn", "depth", "probes"]
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
                    "diploid_cn": seg["diploid_cn"],
                    "absolute_cn": f"{seg['absolute_cn']:.3f}",
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
        fieldnames.extend([f"{sample}_diploid_cn", f"{sample}_log2", f"{sample}_absolute_cn"])

    with open(output_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in chr_summary:
            writer.writerow(row)


def write_cnr_matrix_csv(matrix, samples, output_path):
    """Write bin-level continuous CN matrix CSV."""
    fieldnames = ["chromosome", "start", "end"]
    for sample in samples:
        fieldnames.extend([f"{sample}_log2", f"{sample}_absolute_cn"])

    with open(output_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in matrix:
            writer.writerow(row)


def write_comparison_csv(disagreements, output_path):
    """Write sensitive vs stringent comparison CSV."""
    if not disagreements:
        return
    fieldnames = ["sample", "chromosome", "start", "end", "span_kb",
                  "sensitive_cn", "sensitive_log2", "stringent_cn",
                  "stringent_log2", "p_ttest", "probes"]
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
    parser.add_argument("--ploidy", type=int, default=1,
                        help="Biological ploidy for absolute CN calculation (default: 1)")
    parser.add_argument("--samples", nargs="+", default=None,
                        help="Specific samples to include (default: all)")
    parser.add_argument("--skip-cnr", action="store_true",
                        help="Skip bin-level .cnr matrix (faster)")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    results_dir = Path(args.results_dir) if args.results_dir else output_dir / "cn_matrices"
    results_dir.mkdir(parents=True, exist_ok=True)

    # Discover samples
    all_samples = discover_samples(output_dir)
    samples = args.samples if args.samples else all_samples
    samples = [s for s in samples if s in all_samples]

    print(f"Samples: {', '.join(samples)}")
    print(f"Ploidy: {args.ploidy}")
    print(f"Output: {results_dir}")

    # 1. Sensitive matrix (.md.call.cns)
    print("\n1. Building sensitive segment matrix (.md.call.cns)...")
    sensitive = build_segment_matrix(output_dir, samples, "md.call.cns", args.ploidy)
    write_segment_csv(sensitive, samples,
                      results_dir / "cn_segments_sensitive.csv", has_ptest=True)
    sens_chr = build_chr_summary(sensitive, samples)
    write_chr_summary_csv(sens_chr, samples,
                          results_dir / "cn_chr_summary_sensitive.csv")
    print(f"   Wrote {sum(len(v) for v in sensitive.values())} segments across {len(sensitive)} samples")

    # 2. Stringent matrix (.md.germline.call.cns)
    print("2. Building stringent segment matrix (.md.germline.call.cns)...")
    stringent = build_segment_matrix(output_dir, samples, "md.germline.call.cns", args.ploidy)
    write_segment_csv(stringent, samples,
                      results_dir / "cn_segments_stringent.csv", has_ptest=False)
    stri_chr = build_chr_summary(stringent, samples)
    write_chr_summary_csv(stri_chr, samples,
                          results_dir / "cn_chr_summary_stringent.csv")
    print(f"   Wrote {sum(len(v) for v in stringent.values())} segments across {len(stringent)} samples")

    # 3. Comparison
    print("3. Comparing sensitive vs stringent...")
    disagreements = compare_matrices(sensitive, stringent, samples)
    write_comparison_csv(disagreements, results_dir / "cn_sensitive_vs_stringent.csv")
    if disagreements:
        print(f"   {len(disagreements)} disagreement(s):")
        for d in disagreements:
            if d["chromosome"] == "-":
                print(f"     {d['sample']}: segment count differs "
                      f"({d['sensitive_cn']} vs {d['stringent_cn']})")
            else:
                print(f"     {d['sample']} {d['chromosome']}:{d['start']}-{d['end']} "
                      f"({d['span_kb']}kb): cn={d['sensitive_cn']} vs cn={d['stringent_cn']} "
                      f"(log2={d['sensitive_log2']} vs {d['stringent_log2']}, p={d['p_ttest']})")
    else:
        print("   No CN disagreements between sensitive and stringent matrices")

    # 4. Continuous bin matrix (.md.cnr)
    if not args.skip_cnr:
        print("4. Building continuous bin matrix (.md.cnr)...")
        cnr_matrix = build_cnr_matrix(output_dir, samples, args.ploidy)
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
    print(f"\nNote: diploid_cn uses CNVKit's diploid scale (diploid_cn=2 = baseline).")
    print(f"  absolute_cn = {args.ploidy} * 2^log2 (continuous, preserves subclonal signal)")
    print(f"  For integer calls: absolute_cn = diploid_cn - 2 + {args.ploidy}")


if __name__ == "__main__":
    main()
