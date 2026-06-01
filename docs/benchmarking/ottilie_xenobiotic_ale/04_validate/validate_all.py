#!/usr/bin/env python
"""
Unified Validation Orchestrator — runs all validation scripts and produces
a combined markdown report.

Calls:
  1. snv_indel_concordance.py  — HaplotypeCaller vs Sup Data 4
  2. cnv_concordance.py        — CNVKit vs Sup Data 5
  3. sv_characterization.py    — Manta+TIDDIT via SURVIVOR merge
  4. build_cn_matrix.py        — Dual CN matrices (sensitive + stringent)

Usage:
    python 04_validate/validate_all.py \\
        --output-dir output_ottilie \\
        --results-dir 04_validate/pilot_results

    python 04_validate/validate_all.py \\
        --output-dir output_ottilie_tier2 \\
        --results-dir 04_validate/tier2_results \\
        --ploidy 1

Requires: bcftools, SURVIVOR, openpyxl (all in nf-env)
"""

import argparse
import csv
import subprocess
import sys
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
SCRIPT_DIR = Path(__file__).resolve().parent
BIN_DIR = REPO_ROOT / "bin"

DEFAULT_OUTPUT_DIR = REPO_ROOT / "output_ottilie"
DEFAULT_DICTIONARY = REPO_ROOT / "data/ottilie/sample_name_dictionary.csv"
DEFAULT_RESULTS_DIR = SCRIPT_DIR / "pilot_results"


def run_script(cmd, label):
    """Run a validation script and capture output."""
    print(f"\n{'=' * 80}")
    print(f"RUNNING: {label}")
    print(f"{'=' * 80}")
    print(f"  Command: {' '.join(str(c) for c in cmd)}")
    result = subprocess.run(
        [str(c) for c in cmd],
        capture_output=True, text=True,
    )
    # Print stdout in real-time style
    if result.stdout:
        for line in result.stdout.strip().split("\n"):
            print(f"  {line}")
    if result.returncode != 0:
        print(f"  ERROR (exit {result.returncode}):")
        if result.stderr:
            for line in result.stderr.strip().split("\n"):
                print(f"    {line}")
        return False
    return True


def read_csv_safe(path):
    """Read CSV file, return list of dicts or empty list."""
    if not path.exists():
        return []
    with open(path) as f:
        return list(csv.DictReader(f))


def generate_report(results_dir, output_dir):
    """Generate unified markdown report from CSV outputs."""
    snv_csv = results_dir / "snv_indel_concordance.csv"
    cnv_csv = results_dir / "cnv_concordance.csv"
    sv_csv = results_dir / "sv_characterization.csv"

    snv_rows = read_csv_safe(snv_csv)
    cnv_rows = read_csv_safe(cnv_csv)
    sv_rows = read_csv_safe(sv_csv)

    lines = []
    lines.append(f"# Ottilie Benchmark Validation Report")
    lines.append(f"")
    lines.append(f"**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append(f"**Pipeline output**: `{output_dir}`")
    lines.append(f"")

    # SNV/INDEL section
    lines.append(f"## 1. SNV/INDEL Concordance (HaplotypeCaller vs Sup Data 4)")
    lines.append(f"")
    if snv_rows:
        # Overall stats
        total_tp = sum(int(r["tp_sensitivity"]) for r in snv_rows)
        total_truth = sum(int(r["truth_n"]) for r in snv_rows)
        overall_sens = total_tp / total_truth * 100 if total_truth else 0
        lines.append(f"**Overall sensitivity**: {total_tp}/{total_truth} ({overall_sens:.1f}%)")
        lines.append(f"")

        # Undetected SNV/INDEL events
        fn_csv = results_dir / "snv_indel_missed.csv"
        fn_rows = read_csv_safe(fn_csv)
        if fn_rows:
            lines.append(f"### Undetected variants ({len(fn_rows)})")
            lines.append(f"")
            lines.append(f"| Sample | Position | Ref>Alt | Type | Gene | Effect | Flags |")
            lines.append(f"|--------|----------|---------|------|------|--------|-------|")
            for r in fn_rows:
                flags = r.get("flags", "")
                lines.append(f"| {r['sample']} | {r['chrom']}:{r['pos']} | "
                             f"{r['ref']}>{r['alt']} | {r['type']} | "
                             f"{r.get('gene', '')} | {r.get('effect', '')} | {flags} |")
            lines.append(f"")
    else:
        lines.append(f"*No SNV/INDEL concordance data (CSV not found)*")
    lines.append(f"")

    # CNV section
    lines.append(f"## 2. CNV Concordance (CNVKit vs Sup Data 5)")
    lines.append(f"")
    if cnv_rows:
        detected = sum(1 for r in cnv_rows if r["detected"] == "YES")
        total = len(cnv_rows)
        lines.append(f"**Detection rate**: {detected}/{total} ({detected/total*100:.1f}%)")
        lines.append(f"")

        # Breakdown by event category
        has_category = any(r.get("event_category") for r in cnv_rows)
        if has_category:
            cat_stats = {}
            for r in cnv_rows:
                cat = r.get("event_category", "unknown")
                cat_stats.setdefault(cat, {"total": 0, "detected": 0})
                cat_stats[cat]["total"] += 1
                if r["detected"] == "YES":
                    cat_stats[cat]["detected"] += 1

            lines.append(f"| Event type | Detected | Total | Rate |")
            lines.append(f"|------------|----------|-------|------|")
            for cat in ["whole_chromosome", "amplification"]:
                if cat in cat_stats:
                    s = cat_stats[cat]
                    rate = s["detected"] / s["total"] * 100 if s["total"] else 0
                    label = ("Whole chromosome duplication" if cat == "whole_chromosome"
                             else "Focal amplification")
                    lines.append(f"| {label} | {s['detected']} | {s['total']} | {rate:.0f}% |")
            lines.append(f"")

        # Undetected CNV events table
        missed = [r for r in cnv_rows if r["detected"] == "NO"]
        if missed:
            lines.append(f"### Undetected events ({len(missed)})")
            lines.append(f"")
            lines.append(f"| Sample | Chr | Event type | Chr affected | CNVKit segments |")
            lines.append(f"|--------|-----|------------|--------------|-----------------|")
            for r in missed:
                cat = r.get("event_category", "")
                cat_label = ("whole chr dup" if cat == "whole_chromosome"
                             else "focal amp")
                cov = r.get("chr_affected_pct") or r.get("coverage", "0%")
                partial = r.get("partial_details", "no signal")
                lines.append(f"| {r['sample']} | {r['chromosome']} | {cat_label} | {cov} | {partial} |")
            lines.append(f"")
    else:
        lines.append(f"*No CNV concordance data (CSV not found)*")
    lines.append(f"")

    # Detected events section (full tables)
    lines.append(f"## 3. Detected Events")
    lines.append(f"")
    if snv_rows:
        lines.append(f"### SNV/INDEL per-sample concordance ({len(snv_rows)} samples)")
        lines.append(f"")
        lines.append(f"| Sample | Truth | Pipeline | Evolved-unique | TP | FN | Sensitivity | Precision |")
        lines.append(f"|--------|-------|----------|----------------|----|----|-------------|-----------|")
        for r in snv_rows:
            lines.append(f"| {r['sample']} | {r['truth_n']} | {r['pipeline_total']} | "
                         f"{r['evolved_unique']} | {r['tp_sensitivity']} | {r['fn_sensitivity']} | "
                         f"{r['sensitivity_pct']}% | {r['precision_pct']}% |")
        lines.append(f"")
    if cnv_rows:
        lines.append(f"### CNV per-event concordance ({len(cnv_rows)} events)")
        lines.append(f"")
        lines.append(f"| Sample | Chromosome | Truth event | Detected | CN | log2 | Chr affected |")
        lines.append(f"|--------|------------|-------------|----------|------|------|--------------|")
        for r in cnv_rows:
            cn = r.get("cnvkit_cn", "")
            log2 = r.get("cnvkit_log2", "")
            cov = r.get("chr_affected_pct") or r.get("coverage", "")
            lines.append(f"| {r['sample']} | {r['chromosome']} | {r['truth_event']} | "
                         f"{r['detected']} | {cn} | {log2} | {cov} |")
        lines.append(f"")

    # SV section
    lines.append(f"## 4. SV Characterization (Manta + TIDDIT)")
    lines.append(f"")
    if sv_rows:
        lines.append(f"| Sample | Parent | Manta | TIDDIT | Union | Consensus | Both | Evolved-unique |")
        lines.append(f"|--------|--------|-------|--------|-------|-----------|------|----------------|")
        for r in sv_rows:
            parent_flag = "Yes" if r.get("is_parent") == "True" else ""
            lines.append(f"| {r['sample']} | {parent_flag} | "
                         f"{r['manta_total']}({r['manta_pass']}P) | "
                         f"{r['tiddit_total']}({r['tiddit_pass']}P) | "
                         f"{r['union_total']} | {r['consensus_total']} | "
                         f"{r['supp_both']} | {r.get('evolved_unique', '')} |")
        lines.append(f"")
        lines.append(f"*PASS counts in parentheses. Union=SURVIVOR merge (min_callers=1), "
                     f"Consensus=min_callers=2, Both=SUPP_VEC=11.*")
    else:
        lines.append(f"*No SV characterization data (CSV not found)*")
    lines.append(f"")

    # CN matrix note
    cn_matrix_dir = Path(output_dir) / "cn_matrices"
    if cn_matrix_dir.exists():
        lines.append(f"## 5. CN Matrices")
        lines.append(f"")
        lines.append(f"Dual CN matrices generated in `{cn_matrix_dir}/`:")
        for f in sorted(cn_matrix_dir.glob("*.csv")):
            lines.append(f"- `{f.name}`")
    lines.append(f"")

    # Footer
    lines.append(f"---")
    lines.append(f"*Report generated by `validate_all.py`*")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR),
                        help="Pipeline output directory")
    parser.add_argument("--results-dir", default=str(DEFAULT_RESULTS_DIR),
                        help="Directory for output CSVs and report")
    parser.add_argument("--dictionary", default=str(DEFAULT_DICTIONARY),
                        help="Sample name dictionary CSV")
    parser.add_argument("--parent", default="NODRUG-GM2",
                        help="Parent sample name")
    parser.add_argument("--ploidy", type=int, default=1,
                        help="Sample ploidy for CN matrix builder")
    parser.add_argument("--save-vcfs", action="store_true",
                        help="Save SURVIVOR merged SV VCFs to <output-dir>/sv_merged/")
    parser.add_argument("--skip", nargs="*", default=[],
                        choices=["snv", "cnv", "sv", "matrix", "sv_matrix", "cn_matrix"],
                        help="Skip specific validation steps")
    args = parser.parse_args()

    results_dir = Path(args.results_dir)
    results_dir.mkdir(parents=True, exist_ok=True)

    python = sys.executable
    success = {}

    # 1. SNV/INDEL concordance
    if "snv" not in args.skip:
        success["snv"] = run_script([
            python, SCRIPT_DIR / "snv_indel_concordance.py",
            "--output-dir", args.output_dir,
            "--dictionary", args.dictionary,
            "--parent", args.parent,
            "--csv", results_dir / "snv_indel_concordance.csv",
        ], "SNV/INDEL Concordance")
    else:
        print("\nSkipping SNV/INDEL concordance")

    # 2. CNV concordance
    if "cnv" not in args.skip:
        success["cnv"] = run_script([
            python, SCRIPT_DIR / "cnv_concordance.py",
            "--output-dir", args.output_dir,
            "--dictionary", args.dictionary,
            "--all-samples",
            "--csv", results_dir / "cnv_concordance.csv",
        ], "CNV Concordance")
    else:
        print("\nSkipping CNV concordance")

    # 3. SV characterization
    if "sv" not in args.skip:
        sv_cmd = [
            python, SCRIPT_DIR / "sv_characterization.py",
            "--output-dir", args.output_dir,
            "--dictionary", args.dictionary,
            "--csv", results_dir / "sv_characterization.csv",
        ]
        if args.save_vcfs:
            sv_cmd.extend(["--save-vcfs",
                           str(Path(args.output_dir) / "sv_merged")])
        success["sv"] = run_script(sv_cmd, "SV Characterization")
    else:
        print("\nSkipping SV characterization")

    # 4. CN matrix builder
    if "matrix" not in args.skip:
        success["matrix"] = run_script([
            python, BIN_DIR / "build_cn_matrix.py",
            "--output-dir", args.output_dir,
            "--ploidy", str(args.ploidy),
            "--skip-cnr",
        ], "CN Matrix Builder")
    else:
        print("\nSkipping CN matrix builder")

    # 5. SV cohort matrix
    if "sv_matrix" not in args.skip:
        sv_merged_dir = Path(args.output_dir) / "sv_merged"
        if sv_merged_dir.exists():
            success["sv_matrix"] = run_script([
                python, SCRIPT_DIR / "sv_cohort_matrix.py",
                "--output-dir", args.output_dir,
                "--csv", results_dir / "sv_cohort_matrix.csv",
            ], "SV Cohort Matrix")
        else:
            print("\nSkipping SV cohort matrix (sv_merged/ not found — run with --save-vcfs)")
    else:
        print("\nSkipping SV cohort matrix")

    # 6. CN cohort matrix
    if "cn_matrix" not in args.skip:
        cn_matrix_dir = Path(args.output_dir) / "cn_matrices"
        if cn_matrix_dir.exists():
            success["cn_matrix"] = run_script([
                python, SCRIPT_DIR / "cn_cohort_matrix.py",
                "--cn-dir", str(cn_matrix_dir),
                "--csv", results_dir / "cn_cohort_matrix.csv",
            ], "CN Cohort Matrix")
        else:
            print("\nSkipping CN cohort matrix (cn_matrices/ not found — run matrix step first)")
    else:
        print("\nSkipping CN cohort matrix")

    # Generate unified report
    print(f"\n{'=' * 80}")
    print("GENERATING UNIFIED REPORT")
    print(f"{'=' * 80}")

    report = generate_report(results_dir, args.output_dir)
    report_path = results_dir / "VALIDATION_REPORT.md"
    report_path.write_text(report)
    print(f"  Report written to: {report_path}")

    # Summary
    print(f"\n{'=' * 80}")
    print("VALIDATION COMPLETE")
    for step, ok in success.items():
        status = "OK" if ok else "FAILED"
        print(f"  {step}: {status}")
    print(f"\nResults: {results_dir}/")
    print(f"  VALIDATION_REPORT.md")
    for f in sorted(results_dir.glob("*.csv")):
        print(f"  {f.name}")
    print(f"{'=' * 80}")

    if not all(success.values()):
        sys.exit(1)


if __name__ == "__main__":
    main()
