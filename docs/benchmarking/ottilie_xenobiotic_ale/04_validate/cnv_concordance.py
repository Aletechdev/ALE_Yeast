#!/usr/bin/env python3
"""
Task 2: CNV Concordance — CNVKit/Control-FREEC vs Ottilie Sup Data 5.

Compares pipeline CNV calls against the 24-event truth set from
Ottilie et al. (2022) Commun Biol 5:128.

For Tier 1, only CBR110-15-R3a has a known CNV (whole chr I duplication).

Usage:
    source ~/miniforge3/etc/profile.d/conda.sh && conda activate nf-env
    pip install openpyxl  # if not already installed
    python 04_validate/cnv_concordance.py

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
DEFAULT_OUTPUT_DIR = REPO_ROOT / "output_ottilie"

# Pilot samples with known CNV in Sup Data 5
PILOT_CNV_SAMPLES = {
    "CBR110-15R3a": "CBR110-15-R3a",  # sup5 name -> pipeline name
}

# Chromosome lengths (S288C R64-1-1, Ensembl)
CHR_LENGTHS = {
    "I": 230218, "II": 813184, "III": 316620, "IV": 1531933,
    "V": 576874, "VI": 270161, "VII": 1090940, "VIII": 562643,
    "IX": 439888, "X": 745751, "XI": 666816, "XII": 1078177,
    "XIII": 924431, "XIV": 784333, "XV": 1091291, "XVI": 948066,
}


def load_cnv_truth_set(xlsx_path, sample_map):
    """Load CNV events from Sup Data 5."""
    wb = openpyxl.load_workbook(xlsx_path, read_only=True)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    headers = [str(v) for v in rows[1]]

    truth = {}
    for row in rows[2:]:
        d = dict(zip(headers, row))
        clone = str(d.get("Clone name", "")).strip()
        if clone in sample_map:
            sample = sample_map[clone]
            if sample not in truth:
                truth[sample] = []
            truth[sample].append({
                "chrom": str(d["Chromosome"]).strip(),
                "event_type": str(d["Event type"]).strip(),
                "genes": str(d.get("Genes involved in CNV", "")).strip(),
            })
    wb.close()
    return truth


def load_cnvkit_calls(output_dir, sample):
    """Load CNVKit .call.cns segments."""
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


def load_controlfreec_ratios(output_dir, sample):
    """Load Control-FREEC per-chromosome median ratios."""
    ratio_path = list(
        (Path(output_dir) / f"variant_calling/controlfreec/{sample}").glob("*_ratio.txt")
    )
    if not ratio_path:
        return {}
    ratios_by_chr = {}
    with open(ratio_path[0]) as f:
        f.readline()  # header
        for line in f:
            parts = line.strip().split("\t")
            chrom = parts[0]
            median_ratio = float(parts[3])
            if chrom not in ratios_by_chr:
                ratios_by_chr[chrom] = []
            ratios_by_chr[chrom].append(median_ratio)
    # Average the median ratios per chromosome
    return {ch: sum(vals) / len(vals) for ch, vals in ratios_by_chr.items()}


def check_whole_chr_dup(segments, chrom):
    """Check if CNVKit calls a whole-chromosome duplication."""
    chr_len = CHR_LENGTHS.get(chrom, 0)
    for seg in segments:
        if seg["chrom"] == chrom and seg["cn"] > 2:
            coverage = (seg["end"] - seg["start"]) / chr_len if chr_len else 0
            if coverage > 0.8:  # >80% of chromosome = whole-chr event
                return seg, coverage
    return None, 0


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--truth-set", default=str(DEFAULT_TRUTH_SET), help="Sup Data 5 xlsx")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="Pipeline output directory")
    parser.add_argument("--all-samples", action="store_true", help="Report CNVKit for all samples, not just truth-set matches")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)

    # Load truth set
    print(f"Truth set: {args.truth_set}")
    truth = load_cnv_truth_set(args.truth_set, PILOT_CNV_SAMPLES)

    # Determine which samples to analyze
    if args.all_samples:
        cnvkit_dir = output_dir / "variant_calling/cnvkit"
        samples = sorted(d.name for d in cnvkit_dir.iterdir() if d.is_dir()) if cnvkit_dir.exists() else []
    else:
        samples = list(PILOT_CNV_SAMPLES.values())

    print(f"\n{'=' * 80}")
    print("CNV CONCORDANCE REPORT")
    print(f"{'=' * 80}")

    for sample in samples:
        truth_events = truth.get(sample, [])
        cnvkit_segs = load_cnvkit_calls(output_dir, sample)
        freec_ratios = load_controlfreec_ratios(output_dir, sample)

        print(f"\n{'─' * 80}")
        print(f"SAMPLE: {sample}")
        print(f"  Truth set CNVs: {len(truth_events)}")

        # Show truth set events and whether detected
        for event in truth_events:
            print(f"\n  EXPECTED: Chr {event['chrom']} — {event['event_type']}")
            if event["genes"] and event["genes"] != "N/A":
                print(f"    Genes: {event['genes'][:80]}")

            if "duplication" in event["event_type"].lower():
                seg, cov = check_whole_chr_dup(cnvkit_segs, event["chrom"])
                if seg:
                    print(f"    CNVKit: DETECTED — cn={seg['cn']}, log2={seg['log2']:.3f}, "
                          f"depth={seg['depth']:.1f}, p={seg['p_ttest']:.2e}, coverage={cov:.0%}")
                else:
                    print(f"    CNVKit: NOT DETECTED as whole-chromosome event")
                fr = freec_ratios.get(event["chrom"])
                if fr:
                    detected = "ELEVATED" if fr > 1.2 else "normal"
                    print(f"    Control-FREEC: median ratio={fr:.3f} ({detected})")

        # Show all non-diploid CNVKit segments
        non_diploid = [s for s in cnvkit_segs if s["cn"] != 2]
        if non_diploid:
            print(f"\n  ALL CNVKit non-diploid segments ({len(non_diploid)}):")
            for seg in non_diploid:
                chr_len = CHR_LENGTHS.get(seg["chrom"], 0)
                span_kb = (seg["end"] - seg["start"]) / 1000
                cov_pct = (seg["end"] - seg["start"]) / chr_len * 100 if chr_len else 0
                is_rDNA = seg["chrom"] == "XII" and 400000 < seg["start"] < 500000
                note = " [rDNA]" if is_rDNA else ""
                is_subtel = (seg["start"] < 10000 or seg["end"] > chr_len - 10000) if chr_len else False
                if is_subtel and not is_rDNA:
                    note = " [subtelomeric]"
                print(f"    {seg['chrom']}:{seg['start']}-{seg['end']} ({span_kb:.0f}kb, {cov_pct:.0f}%) "
                      f"cn={seg['cn']} log2={seg['log2']:.3f} depth={seg['depth']:.1f} "
                      f"p={seg['p_ttest']:.2e} probes={seg['probes']}{note}")

        # Per-chromosome Control-FREEC summary
        if freec_ratios:
            elevated = {ch: r for ch, r in freec_ratios.items() if r > 1.2 and ch != "XII"}
            if elevated:
                print(f"\n  Control-FREEC elevated chromosomes (ratio > 1.2, excl. XII/rDNA):")
                for ch, r in sorted(elevated.items()):
                    print(f"    Chr {ch}: {r:.3f}")

    print(f"\n{'=' * 80}")


if __name__ == "__main__":
    main()
