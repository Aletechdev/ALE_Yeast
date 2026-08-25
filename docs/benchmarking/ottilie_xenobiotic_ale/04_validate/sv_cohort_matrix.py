#!/usr/bin/env python
"""
SV Cohort Matrix — merges per-sample SURVIVOR VCFs into a cohort-level
wide-format table (one row per SV event, columns = samples).

Runs SURVIVOR merge across all per-sample VCFs, then maps each cohort
event back to per-sample records to get inner caller info (Manta/TIDDIT).

Supports multiple source VCF types via --source:
  union       — all calls, min_callers=1, no PASS filter (default)
  union_pass  — all calls, min_callers=1, PASS-filtered input
  consensus   — both callers agree, no PASS filter
  consensus_pass — both callers agree, PASS-filtered input

Usage:
    python sv_cohort_matrix.py \
        --output-dir output_ottilie \
        --csv results/sv_cohort_matrix.csv

    # PASS-filtered, with VCF output:
    python sv_cohort_matrix.py \
        --output-dir output_ottilie \
        --source union_pass \
        --csv results/sv_cohort_matrix_pass.csv \
        --vcf results/sv_cohort_merged_pass.vcf.gz

Requires: SURVIVOR, bcftools (both in nf-env)
"""

import argparse
import csv
import os
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_OUTPUT_DIR = REPO_ROOT / "output_ottilie"

CHR_ORDER = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII",
             "IX", "X", "XI", "XII", "XIII", "XIV", "XV", "XVI"]

VALID_SOURCES = ["union", "union_pass", "consensus", "consensus_pass"]

# SURVIVOR merge parameters (same as sv_characterization.py)
MAX_DIST = 1000
MIN_SIZE = 50
TAKE_TYPE = 1
TAKE_STRAND = 0
ESTIMATE_DIST = 0


def find_survivor():
    """Find SURVIVOR binary."""
    for candidate in ["SURVIVOR", "survivor"]:
        try:
            subprocess.check_output([candidate, "merge"], stderr=subprocess.DEVNULL)
        except FileNotFoundError:
            continue
        except subprocess.CalledProcessError:
            return candidate
    conda_prefix = os.environ.get("CONDA_PREFIX", "")
    if conda_prefix:
        path = Path(conda_prefix) / "bin" / "SURVIVOR"
        if path.exists():
            return str(path)
    return None


def parse_survivor_vcf(vcf_path):
    """Parse SURVIVOR VCF, return list of record dicts."""
    records = []
    # Handle both plain and gzipped VCFs
    if str(vcf_path).endswith(".gz"):
        import gzip
        opener = gzip.open(vcf_path, "rt")
    else:
        opener = open(vcf_path)

    with opener as f:
        for line in f:
            if line.startswith("#") or not line.strip():
                continue
            fields = line.strip().split("\t")
            chrom = fields[0]
            pos = int(fields[1])
            info = {}
            for item in fields[7].split(";"):
                if "=" in item:
                    k, v = item.split("=", 1)
                    info[k] = v

            svtype = info.get("SVTYPE", ".")
            svlen = abs(int(info.get("SVLEN", 0)))
            end = int(info.get("END", pos + svlen))
            chrom2 = info.get("CHR2", chrom)
            supp_vec = info.get("SUPP_VEC", "")

            # Parse inner callers from 2-char SUPP_VEC (per-sample VCFs)
            callers = []
            if len(supp_vec) == 2:
                if supp_vec[0] == "1":
                    callers.append("Manta")
                if supp_vec[1] == "1":
                    callers.append("TIDDIT")

            records.append({
                "chrom": chrom,
                "pos": pos,
                "end": end,
                "chrom2": chrom2,
                "svtype": svtype,
                "svlen": svlen,
                "supp_vec": supp_vec,
                "callers": "+".join(callers) if callers else "",
            })
    return records


def chr_sort_key(chrom):
    """Sort key for yeast chromosome order."""
    try:
        return CHR_ORDER.index(chrom)
    except ValueError:
        return len(CHR_ORDER)


def proximity_match(cohort_rec, sample_records, max_dist=MAX_DIST):
    """Find the best matching per-sample record for a cohort event."""
    best = None
    best_dist = float("inf")
    for rec in sample_records:
        if rec["chrom"] != cohort_rec["chrom"]:
            continue
        if rec["svtype"] != cohort_rec["svtype"]:
            continue
        if rec.get("chrom2") != cohort_rec.get("chrom2"):
            continue
        # Check pos and end independently (SURVIVOR can shift both during merge)
        pos_dist = abs(rec["pos"] - cohort_rec["pos"])
        end_dist = abs(rec["end"] - cohort_rec["end"])
        # BOTH breakpoints must agree within max_dist — the same rule SURVIVOR applied
        # when it merged the event. A one-breakpoint match is not enough: distinct SVs
        # that share an anchor (e.g. several inversions/translocations radiating from
        # one hotspot) would otherwise be credited to samples that never called them.
        if pos_dist > max_dist or end_dist > max_dist:
            continue
        dist = pos_dist + end_dist
        if dist < best_dist:
            best = rec
            best_dist = dist
    return best


def save_cohort_vcf(raw_vcf, dest_path):
    """Sort, compress, and index the cohort SURVIVOR VCF."""
    dest_path = Path(dest_path)
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["bcftools", "sort", "-Oz", "-o", str(dest_path), str(raw_vcf)],
        check=True, capture_output=True,
    )
    subprocess.run(
        ["bcftools", "index", "-t", str(dest_path)],
        check=True, capture_output=True,
    )


def main():
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR),
                        help="Pipeline output directory")
    parser.add_argument("--sv-merged-dir", default=None,
                        help="Directory with per-sample SURVIVOR VCFs (default: <output-dir>/sv_merged)")
    parser.add_argument("--source", default="union", choices=VALID_SOURCES,
                        help="Which per-sample SURVIVOR VCF to use (default: union)")
    parser.add_argument("--csv", required=True,
                        help="Output CSV path")
    parser.add_argument("--vcf", default=None,
                        help="Save cohort SURVIVOR merged VCF (sorted, compressed, indexed)")
    args = parser.parse_args()

    sv_dir = Path(args.sv_merged_dir) if args.sv_merged_dir else Path(args.output_dir) / "sv_merged"
    if not sv_dir.exists():
        print(f"ERROR: {sv_dir} not found. Run validate_all.py with --save-vcfs first.",
              file=sys.stderr)
        sys.exit(1)

    survivor = find_survivor()
    if not survivor:
        print("ERROR: SURVIVOR not found. Activate nf-env.", file=sys.stderr)
        sys.exit(1)

    # Discover samples from sv_merged directory
    samples = sorted([d.name for d in sv_dir.iterdir() if d.is_dir()])
    if not samples:
        print(f"ERROR: No sample directories in {sv_dir}", file=sys.stderr)
        sys.exit(1)

    print(f"Source: {args.source}")
    print(f"Samples: {', '.join(samples)}")

    # Collect per-sample VCF paths and parse records
    sample_vcfs = {}
    sample_records = {}
    for s in samples:
        vcf = sv_dir / s / f"{s}.survivor.{args.source}.vcf.gz"
        if not vcf.exists():
            print(f"WARNING: {vcf} not found, skipping {s}", file=sys.stderr)
            continue
        sample_vcfs[s] = vcf
        sample_records[s] = parse_survivor_vcf(vcf)

    active_samples = [s for s in samples if s in sample_vcfs]
    print(f"Active samples: {len(active_samples)}")

    if not active_samples:
        print(f"ERROR: No {args.source} VCFs found. Available types per sample:",
              file=sys.stderr)
        # Show what's actually available
        for s in samples[:1]:
            sample_dir = sv_dir / s
            vcfs = sorted(sample_dir.glob("*.vcf.gz"))
            for v in vcfs:
                print(f"  {v.name}", file=sys.stderr)
        sys.exit(1)

    # Run cohort-level SURVIVOR merge
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Decompress VCFs for SURVIVOR (needs plain VCF)
        plain_vcfs = []
        for s in active_samples:
            plain = tmpdir / f"{s}.vcf"
            subprocess.run(
                ["bcftools", "view", "-o", str(plain), str(sample_vcfs[s])],
                check=True, capture_output=True,
            )
            plain_vcfs.append(str(plain))

        # Write file list for SURVIVOR
        filelist = tmpdir / "filelist.txt"
        filelist.write_text("\n".join(plain_vcfs) + "\n")

        # Run SURVIVOR merge
        cohort_vcf = tmpdir / "cohort_merged.vcf"
        min_callers = 1  # union across samples
        cmd = [
            survivor, "merge", str(filelist),
            str(MAX_DIST), str(min_callers), str(TAKE_TYPE),
            str(TAKE_STRAND), str(ESTIMATE_DIST), str(MIN_SIZE),
            str(cohort_vcf),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"ERROR: SURVIVOR merge failed: {result.stderr}", file=sys.stderr)
            sys.exit(1)

        # Save VCF output if requested
        if args.vcf:
            save_cohort_vcf(cohort_vcf, args.vcf)
            print(f"Cohort VCF: {args.vcf}")

        # Parse cohort VCF — SUPP_VEC is now N-char (one per sample)
        cohort_records = []
        with open(cohort_vcf) as f:
            for line in f:
                if line.startswith("#") or not line.strip():
                    continue
                fields = line.strip().split("\t")
                chrom = fields[0]
                pos = int(fields[1])
                info = {}
                for item in fields[7].split(";"):
                    if "=" in item:
                        k, v = item.split("=", 1)
                        info[k] = v

                svtype = info.get("SVTYPE", ".")
                svlen = abs(int(info.get("SVLEN", 0)))
                end = int(info.get("END", pos + svlen))
                chrom2 = info.get("CHR2", chrom)
                supp_vec = info.get("SUPP_VEC", "0" * len(active_samples))

                cohort_records.append({
                    "chrom": chrom,
                    "pos": pos,
                    "end": end,
                    "chrom2": chrom2,
                    "svtype": svtype,
                    "svlen": svlen,
                    "supp_vec": supp_vec,
                })

    print(f"Cohort events: {len(cohort_records)}")

    # Sort by chromosome order + position
    cohort_records.sort(key=lambda r: (chr_sort_key(r["chrom"]), r["pos"]))

    # Map cohort events back to per-sample caller info
    out_path = Path(args.csv)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = ["chrom", "pos", "chrom2", "end", "svtype", "svlen"] + active_samples
    with open(out_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for rec in cohort_records:
            row = {
                "chrom": rec["chrom"],
                "pos": rec["pos"],
                "chrom2": rec["chrom2"],
                "end": rec["end"],
                "svtype": rec["svtype"],
                "svlen": rec["svlen"],
            }
            # Match each sample directly instead of relying solely on SUPP_VEC
            # (SURVIVOR can create phantom associations during cohort merge)
            for s in active_samples:
                match = proximity_match(rec, sample_records[s])
                row[s] = match["callers"] if match else "-"
            writer.writerow(row)

    # Summary stats
    n_shared = sum(1 for r in cohort_records if r["supp_vec"].count("1") > 1)
    n_private = sum(1 for r in cohort_records if r["supp_vec"].count("1") == 1)
    print(f"Shared events (2+ samples): {n_shared}")
    print(f"Private events (1 sample): {n_private}")
    print(f"Output: {out_path}")


if __name__ == "__main__":
    main()
