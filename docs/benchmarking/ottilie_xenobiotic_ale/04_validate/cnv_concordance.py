#!/usr/bin/env python
"""
CNV Concordance — CNVKit vs Ottilie Sup Data 5.

Compares pipeline CNVKit calls against the 24-event truth set from
Ottilie et al. (2022) Commun Biol 5:128.

Uses sample_name_dictionary.csv for dynamic mapping between Sup Data 5
clone names and pipeline sample names. Reports truth concordance for
samples with known CNVs and characterizes all non-diploid segments for
all samples.

CNVKit CN scale note: cn=2 is always baseline regardless of ploidy.
  cn>2 = gain, cn<2 = loss. See cnvkit_ploidy_behavior.md.

Usage:
    python 04_validate/cnv_concordance.py \\
        --output-dir output_ottilie \\
        --dictionary data/ottilie/sample_name_dictionary.csv

    # All samples, CSV output:
    python 04_validate/cnv_concordance.py \\
        --output-dir output_ottilie \\
        --dictionary data/ottilie/sample_name_dictionary.csv \\
        --all-samples --csv results/cnv_concordance.csv

Requires: openpyxl
"""

import argparse
import csv
import sys
from pathlib import Path

try:
    import openpyxl
except ImportError:
    sys.exit("openpyxl not installed. Run: pip install openpyxl")


REPO_ROOT = Path(__file__).resolve().parents[4]

DEFAULT_TRUTH_SET = REPO_ROOT / "data/ottilie/supplementary/sup_5_42003_2022_3076_MOESM7_ESM.xlsx"
DEFAULT_DICTIONARY = REPO_ROOT / "data/ottilie/sample_name_dictionary.csv"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "output_ottilie"

# Chromosome lengths (S288C R64-1-1, Ensembl)
CHR_LENGTHS = {
    "I": 230218, "II": 813184, "III": 316620, "IV": 1531933,
    "V": 576874, "VI": 270161, "VII": 1090940, "VIII": 562643,
    "IX": 439888, "X": 745751, "XI": 666816, "XII": 1078177,
    "XIII": 924431, "XIV": 784333, "XV": 1091291, "XVI": 948066,
}


def build_sup5_map(dictionary_path, output_dir):
    """Build sup5 clone name -> pipeline sample name mapping.

    Reads the sample_name_dictionary.csv and checks which samples exist
    in the pipeline cnvkit output directory.
    Returns dict mapping sup5 clone names to pipeline directory names.
    """
    cnvkit_dir = Path(output_dir) / "variant_calling/cnvkit"
    if not cnvkit_dir.exists():
        sys.exit(f"CNVKit output directory not found: {cnvkit_dir}")
    available = set(p.name for p in cnvkit_dir.iterdir() if p.is_dir())

    sup5_map = {}
    with open(dictionary_path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            sup5 = row.get("clone_name_sup5", "").strip()
            sup4 = row.get("clone_name_sup4", "").strip()
            lib = row.get("library_name_sra", "").strip()
            is_parent = row.get("is_parent", "").strip() == "True"

            if not sup5 or is_parent:
                continue

            # Try library name first (pipeline uses this), then sup5, then sup4
            for candidate in [lib, sup5, sup4]:
                if candidate and candidate in available:
                    sup5_map[sup5] = candidate
                    break

    return sup5_map


def load_cnv_truth_set(xlsx_path, sup5_map):
    """Load CNV events from Sup Data 5.

    Returns dict: pipeline_sample_name -> list of event dicts.
    Also returns unmapped: list of (clone_name, events) not in sup5_map.
    """
    wb = openpyxl.load_workbook(xlsx_path, read_only=True)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    headers = [str(v) for v in rows[1]]

    truth = {}
    unmapped = {}
    for row in rows[2:]:
        d = dict(zip(headers, row))
        clone = str(d.get("Clone name", "")).strip()
        event = {
            "chrom": str(d["Chromosome"]).strip(),
            "event_type": str(d["Event type"]).strip(),
            "genes": str(d.get("Genes involved in CNV", "")).strip(),
        }
        if clone in sup5_map:
            sample = sup5_map[clone]
            truth.setdefault(sample, []).append(event)
        else:
            unmapped.setdefault(clone, []).append(event)

    wb.close()
    return truth, unmapped


def load_cnvkit_calls(output_dir, sample):
    """Load CNVKit .md.call.cns segments (sensitive, has p_ttest)."""
    cns_path = Path(output_dir) / f"variant_calling/cnvkit/{sample}/{sample}.md.call.cns"
    if not cns_path.exists():
        return []
    segments = []
    with open(cns_path) as f:
        header = f.readline().strip().split("\t")
        for line in f:
            parts = line.strip().split("\t")
            d = dict(zip(header, parts))
            segments.append({
                "chrom": d["chromosome"],
                "start": int(d["start"]),
                "end": int(d["end"]),
                "log2": float(d["log2"]),
                "cn": int(d["cn"]),
                "depth": float(d["depth"]),
                "probes": int(d["probes"]),
                "p_ttest": float(d.get("p_ttest", 1)),
            })
    return segments


def classify_event(event_type):
    """Classify event as 'whole_chromosome' or 'amplification'."""
    lower = event_type.lower()
    if "whole" in lower or "aneuploidy" in lower:
        return "whole_chromosome"
    return "amplification"


def check_cnv_event(segments, chrom, event_type):
    """Check if CNVKit detects a CNV event on a chromosome.

    For whole-chromosome duplications: look for cn>2 covering >80% of chr.
    For amplifications: look for any cn>2 segment on the chromosome.

    Returns (best_segment_or_None, coverage, all_gain_segments_on_chr).
    """
    chr_len = CHR_LENGTHS.get(chrom, 0)
    is_whole_chr = classify_event(event_type) == "whole_chromosome"

    chr_segs = [s for s in segments if s["chrom"] == chrom and s["cn"] > 2]
    if not chr_segs:
        # Also return all segments on the chromosome (including cn<=2) for context
        all_chr = [s for s in segments if s["chrom"] == chrom]
        return None, 0, all_chr

    if is_whole_chr:
        # Check if a single segment covers >80% of chromosome
        for seg in chr_segs:
            coverage = (seg["end"] - seg["start"]) / chr_len if chr_len else 0
            if coverage > 0.8:
                return seg, coverage, chr_segs
        # Also check combined coverage of all gain segments
        total_gain = sum(s["end"] - s["start"] for s in chr_segs)
        combined_cov = total_gain / chr_len if chr_len else 0
        if combined_cov > 0.8:
            best = max(chr_segs, key=lambda s: s["end"] - s["start"])
            return best, combined_cov, chr_segs
        return None, combined_cov, chr_segs
    else:
        # Amplification: any gain segment
        best = max(chr_segs, key=lambda s: s["end"] - s["start"])
        coverage = (best["end"] - best["start"]) / chr_len if chr_len else 0
        return best, coverage, chr_segs


def format_segment(seg, chr_len):
    """Format a segment for display."""
    span_kb = (seg["end"] - seg["start"]) / 1000
    cov_pct = (seg["end"] - seg["start"]) / chr_len * 100 if chr_len else 0
    is_rDNA = seg["chrom"] == "XII" and 400000 < seg["start"] < 500000
    note = " [rDNA]" if is_rDNA else ""
    is_subtel = (seg["start"] < 10000 or seg["end"] > chr_len - 10000) if chr_len else False
    if is_subtel and not is_rDNA:
        note = " [subtelomeric]"
    return (f"{seg['chrom']}:{seg['start']}-{seg['end']} ({span_kb:.0f}kb, {cov_pct:.0f}%) "
            f"cn={seg['cn']} log2={seg['log2']:.3f} depth={seg['depth']:.1f} "
            f"p={seg['p_ttest']:.2e} probes={seg['probes']}{note}")


def main():
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--truth-set", default=str(DEFAULT_TRUTH_SET),
                        help="Sup Data 5 xlsx path")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR),
                        help="Pipeline output directory")
    parser.add_argument("--dictionary", default=str(DEFAULT_DICTIONARY),
                        help="Sample name dictionary CSV")
    parser.add_argument("--all-samples", action="store_true",
                        help="Report all samples, not just truth-set matches")
    parser.add_argument("--csv", default=None,
                        help="Write machine-readable CSV to this path")
    parser.add_argument("--parent", default="NODRUG-GM2",
                        help="Parent sample name (excluded from truth comparison)")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)

    # Build dynamic mapping
    sup5_map = build_sup5_map(args.dictionary, output_dir)
    print(f"Dictionary: {args.dictionary}")
    print(f"Truth set: {args.truth_set}")
    print(f"Mapped {len(sup5_map)} sup5 clone names to pipeline samples")

    # Load truth set
    truth, unmapped = load_cnv_truth_set(args.truth_set, sup5_map)
    if unmapped:
        print(f"  {len(unmapped)} truth clones not in pipeline output: "
              f"{', '.join(sorted(unmapped.keys()))}")

    # Determine samples to analyze
    cnvkit_dir = output_dir / "variant_calling/cnvkit"
    all_samples = sorted(d.name for d in cnvkit_dir.iterdir() if d.is_dir())

    if args.all_samples:
        samples = all_samples
    else:
        # Only truth-set samples + parent
        samples = sorted(set(truth.keys()) | {args.parent} & set(all_samples))
        if not samples:
            samples = all_samples
            print("  No truth-set samples found in output, reporting all samples")

    # CSV output accumulator
    csv_rows = []

    print(f"\n{'=' * 80}")
    print("CNV CONCORDANCE REPORT")
    print(f"Note: CNVKit CN scale uses cn=2 as baseline (diploid scale).")
    print(f"  cn>2 = gain, cn<2 = loss, regardless of biological ploidy.")
    print(f"{'=' * 80}")

    total_expected = 0
    total_detected = 0

    for sample in samples:
        truth_events = truth.get(sample, [])
        cnvkit_segs = load_cnvkit_calls(output_dir, sample)

        if not cnvkit_segs:
            print(f"\n{'─' * 80}")
            print(f"SAMPLE: {sample} — no CNVKit data")
            continue

        print(f"\n{'─' * 80}")
        print(f"SAMPLE: {sample}")
        print(f"  Total segments: {len(cnvkit_segs)}")
        print(f"  Truth set CNVs: {len(truth_events)}")

        # Check each truth set event
        for event in truth_events:
            total_expected += 1
            category = classify_event(event["event_type"])
            print(f"\n  EXPECTED: Chr {event['chrom']} — {event['event_type']} [{category}]")
            if event["genes"] and event["genes"] not in ("N/A", "None"):
                genes_str = event["genes"][:100]
                print(f"    Genes: {genes_str}")

            seg, cov, chr_segs = check_cnv_event(cnvkit_segs, event["chrom"], event["event_type"])
            if seg:
                total_detected += 1
                print(f"    CNVKit: DETECTED — cn={seg['cn']}, log2={seg['log2']:.3f}, "
                      f"depth={seg['depth']:.1f}, p={seg['p_ttest']:.2e}, chr_affected={cov:.0%}")
                csv_rows.append({
                    "sample": sample,
                    "chromosome": event["chrom"],
                    "truth_event": event["event_type"],
                    "event_category": category,
                    "detected": "YES",
                    "cnvkit_cn": seg["cn"],
                    "cnvkit_log2": f"{seg['log2']:.3f}",
                    "cnvkit_depth": f"{seg['depth']:.1f}",
                    "cnvkit_p_ttest": f"{seg['p_ttest']:.2e}",
                    "chr_affected_pct": f"{cov:.0%}",
                    "probes": seg["probes"],
                    "partial_details": "",
                })
            else:
                # Build partial detection details for undetected events
                partial = ""
                if chr_segs:
                    gain_segs = [s for s in chr_segs if s["cn"] > 2]
                    if gain_segs:
                        details = []
                        for s in gain_segs:
                            span_kb = (s["end"] - s["start"]) / 1000
                            details.append(f"{s['chrom']}:{s['start']}-{s['end']} "
                                           f"({span_kb:.0f}kb) cn={s['cn']} log2={s['log2']:.3f}")
                        partial = "; ".join(details)
                    else:
                        # No gain segments — show all segments on chr for context
                        details = []
                        for s in chr_segs:
                            span_kb = (s["end"] - s["start"]) / 1000
                            details.append(f"{s['chrom']}:{s['start']}-{s['end']} "
                                           f"({span_kb:.0f}kb) cn={s['cn']} log2={s['log2']:.3f}")
                        partial = "no gain; all segments: " + "; ".join(details)

                print(f"    CNVKit: NOT DETECTED (chr_affected={cov:.0%})")
                if partial:
                    print(f"    Partial: {partial}")
                csv_rows.append({
                    "sample": sample,
                    "chromosome": event["chrom"],
                    "truth_event": event["event_type"],
                    "event_category": category,
                    "detected": "NO",
                    "cnvkit_cn": "",
                    "cnvkit_log2": "",
                    "cnvkit_depth": "",
                    "cnvkit_p_ttest": "",
                    "chr_affected_pct": f"{cov:.0%}",
                    "probes": "",
                    "partial_details": partial,
                })

        # Show all non-diploid segments
        non_diploid = [s for s in cnvkit_segs if s["cn"] != 2]
        if non_diploid:
            print(f"\n  ALL non-diploid segments ({len(non_diploid)}):")
            for seg in non_diploid:
                chr_len = CHR_LENGTHS.get(seg["chrom"], 0)
                print(f"    {format_segment(seg, chr_len)}")
        else:
            print(f"\n  No non-diploid segments")

    # Summary
    print(f"\n{'=' * 80}")
    print("SUMMARY")
    print(f"  Samples analyzed: {len(samples)}")
    if total_expected > 0:
        sensitivity = total_detected / total_expected * 100
        print(f"  Truth events: {total_expected}")
        print(f"  Detected: {total_detected}/{total_expected} ({sensitivity:.1f}%)")
    else:
        print(f"  No truth events in analyzed samples")
    print(f"{'=' * 80}")

    # Write CSV
    if args.csv and csv_rows:
        csv_path = Path(args.csv)
        csv_path.parent.mkdir(parents=True, exist_ok=True)
        fieldnames = ["sample", "chromosome", "truth_event", "event_category",
                      "detected", "cnvkit_cn", "cnvkit_log2", "cnvkit_depth",
                      "cnvkit_p_ttest", "chr_affected_pct", "probes", "partial_details"]
        with open(csv_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for row in csv_rows:
                writer.writerow(row)
        print(f"\nCSV written to: {csv_path}")


if __name__ == "__main__":
    main()
