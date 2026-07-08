#!/usr/bin/env python
"""
SURVIVOR SV Merge — merge Manta + TIDDIT VCFs for a single sample.

Runs bcftools to decompress (and optionally PASS-filter) input VCFs,
then SURVIVOR merge to combine calls from both callers.

SURVIVOR does not preserve the FILTER column from input VCFs — all merged
records get FILTER=PASS regardless of the original filter status. To get
a PASS-filtered merge, use --pass-only to pre-filter inputs with
`bcftools view -f PASS` before merging.

Output naming convention:
  <output-dir>/<sample>.survivor.<mode>.vcf.gz   (bgzipped, sorted)
  <output-dir>/<sample>.survivor.<mode>.vcf.gz.tbi

Where <mode> is derived from --min-callers and --pass-only:
  union          — min_callers=1, no PASS filter (all calls from either caller)
  union_pass     — min_callers=1, PASS-filtered inputs
  consensus      — min_callers=2, no PASS filter (both callers agree)
  consensus_pass — min_callers=2, PASS-filtered inputs

SURVIVOR merge parameters (matching sv_characterization.py defaults):
  max_dist=1000   — max distance between breakpoints (bp)
  min_size=50     — minimum SV size to consider
  take_type=1     — require same SV type for merging
  take_strand=0   — ignore strand
  estimate_dist=0 — use fixed distance, not size-based

Usage:
    # Default: union (all calls, no PASS filter)
    python survivor_sv_merge.py \\
        --manta-vcf output/variant_calling/manta/S1/S1.manta.diploid_sv.vcf.gz \\
        --tiddit-vcf output/variant_calling/tiddit/S1/S1.tiddit.vcf.gz \\
        --output-dir output/sv_merged/S1 \\
        --sample S1

    # PASS-filtered union (what sv_cohort_matrix.py uses by default)
    python survivor_sv_merge.py \\
        --manta-vcf output/variant_calling/manta/S1/S1.manta.diploid_sv.vcf.gz \\
        --tiddit-vcf output/variant_calling/tiddit/S1/S1.tiddit.vcf.gz \\
        --output-dir output/sv_merged/S1 \\
        --sample S1 \\
        --pass-only

    # Consensus (both callers agree)
    python survivor_sv_merge.py ... --min-callers 2

Requires: bcftools, SURVIVOR (both in nf-env)
"""

import argparse
import os
import subprocess
import sys
import tempfile
from pathlib import Path

# SURVIVOR merge parameters (same as sv_characterization.py)
MAX_DIST = 1000
MIN_SIZE = 50
TAKE_TYPE = 1
TAKE_STRAND = 0
ESTIMATE_DIST = 0


def find_survivor():
    """Find SURVIVOR binary on PATH or in conda env."""
    for candidate in ["SURVIVOR", "survivor"]:
        try:
            subprocess.check_output([candidate, "merge"], stderr=subprocess.DEVNULL)
        except FileNotFoundError:
            continue
        except subprocess.CalledProcessError:
            # SURVIVOR prints usage and exits non-zero when called without args
            return candidate
    conda_prefix = os.environ.get("CONDA_PREFIX", "")
    if conda_prefix:
        path = Path(conda_prefix) / "bin" / "SURVIVOR"
        if path.exists():
            return str(path)
    return None


def main():
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--manta-vcf", required=True,
                        help="Path to Manta VCF (.vcf.gz)")
    parser.add_argument("--tiddit-vcf", required=True,
                        help="Path to TIDDIT VCF (.vcf.gz)")
    parser.add_argument("--output-dir", required=True,
                        help="Output directory for merged VCF")
    parser.add_argument("--sample", required=True,
                        help="Sample name (used in output filename)")
    parser.add_argument("--pass-only", action="store_true",
                        help="Pre-filter inputs to PASS-only before merging")
    parser.add_argument("--min-callers", type=int, default=1, choices=[1, 2],
                        help="Minimum callers supporting an SV (1=union, 2=consensus)")
    args = parser.parse_args()

    manta_vcf = Path(args.manta_vcf)
    tiddit_vcf = Path(args.tiddit_vcf)
    out_dir = Path(args.output_dir)

    if not manta_vcf.exists():
        sys.exit(f"ERROR: Manta VCF not found: {manta_vcf}")
    if not tiddit_vcf.exists():
        sys.exit(f"ERROR: TIDDIT VCF not found: {tiddit_vcf}")

    survivor = find_survivor()
    if not survivor:
        sys.exit("ERROR: SURVIVOR not found. Activate nf-env.")

    # Determine output mode name
    mode = "consensus" if args.min_callers >= 2 else "union"
    if args.pass_only:
        mode += "_pass"

    out_dir.mkdir(parents=True, exist_ok=True)
    out_vcf = out_dir / f"{args.sample}.survivor.{mode}.vcf.gz"

    print(f"Sample: {args.sample}")
    print(f"Mode: {mode} (min_callers={args.min_callers}, pass_only={args.pass_only})")
    print(f"Manta: {manta_vcf}")
    print(f"TIDDIT: {tiddit_vcf}")

    with tempfile.TemporaryDirectory(prefix=f"sv_merge_{args.sample}_") as tmpdir:
        tmpdir = Path(tmpdir)

        # Step 1: Decompress VCFs for SURVIVOR (needs uncompressed input).
        #         Optionally filter to PASS-only before merging.
        bcftools_args = ["bcftools", "view"]
        if args.pass_only:
            bcftools_args.extend(["-f", "PASS"])

        manta_plain = tmpdir / "manta.vcf"
        tiddit_plain = tmpdir / "tiddit.vcf"

        subprocess.run(
            bcftools_args + ["-o", str(manta_plain), str(manta_vcf)],
            check=True, capture_output=True,
        )
        subprocess.run(
            bcftools_args + ["-o", str(tiddit_plain), str(tiddit_vcf)],
            check=True, capture_output=True,
        )

        # Step 2: Write file list for SURVIVOR (one VCF path per line).
        #         Order matters: index 0 = Manta, index 1 = TIDDIT.
        #         SUPP_VEC encodes presence as positional bits matching this order.
        filelist = tmpdir / "filelist.txt"
        filelist.write_text(f"{manta_plain}\n{tiddit_plain}\n")

        # Step 3: Run SURVIVOR merge.
        merged_vcf = tmpdir / "merged.vcf"
        cmd = [
            survivor, "merge", str(filelist),
            str(MAX_DIST),
            str(args.min_callers),
            str(TAKE_TYPE),
            str(TAKE_STRAND),
            str(ESTIMATE_DIST),
            str(MIN_SIZE),
            str(merged_vcf),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            sys.exit(f"ERROR: SURVIVOR merge failed: {result.stderr}")

        # Count output records
        with open(merged_vcf) as f:
            n_records = sum(1 for line in f if not line.startswith("#") and line.strip())

        # Step 4: Sort, compress (bgzip), and index the merged VCF.
        #         SURVIVOR output is often unsorted; bcftools sort fixes this.
        subprocess.run(
            ["bcftools", "sort", "-Oz", "-o", str(out_vcf), str(merged_vcf)],
            check=True, capture_output=True,
        )
        subprocess.run(
            ["bcftools", "index", "-t", str(out_vcf)],
            check=True, capture_output=True,
        )

    print(f"Output: {out_vcf} ({n_records} records)")


if __name__ == "__main__":
    main()
