#!/usr/bin/env python
"""
SV Characterization — Manta + TIDDIT via SURVIVOR merge.

Note: The core SURVIVOR merge logic (run_survivor_merge, find_survivor,
save_merged_vcf) has been extracted to bin/survivor_sv_merge.py for use
as a standalone Nextflow process. This script retains its own inline copy
for validation use (it calls merge 4x per sample with intermediate parsing).

No truth set for SVs — this script characterizes all SVs across samples,
merges Manta+TIDDIT calls per sample via SURVIVOR, and subtracts parent SVs
to identify evolved-unique events.

Uses sample_name_dictionary.csv for dynamic mapping between library names
and pipeline sample names. Parent samples (is_parent=True) are identified
automatically and used as baseline for subtraction.

Usage:
    python 04_validate/sv_characterization.py \\
        --output-dir output_ottilie \\
        --dictionary data/ottilie/sample_name_dictionary.csv

    # CSV output:
    python 04_validate/sv_characterization.py \\
        --output-dir output_ottilie \\
        --dictionary data/ottilie/sample_name_dictionary.csv \\
        --csv results/sv_characterization.csv

Requires: bcftools, SURVIVOR (both in nf-env)
"""

import argparse
import csv
import json
import os
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path

from sample_names import resolve_sample

REPO_ROOT = Path(__file__).resolve().parents[4]

DEFAULT_DICTIONARY = REPO_ROOT / "data/ottilie/sample_name_dictionary.csv"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "output_ottilie"

# SURVIVOR merge parameters
MAX_DIST = 1000      # max distance between breakpoints (bp)
MIN_SIZE = 50        # minimum SV size to consider
TAKE_TYPE = 1        # require same SV type for merging
TAKE_STRAND = 0      # ignore strand
ESTIMATE_DIST = 0    # use fixed distance, not size-based


def find_survivor():
    """Find SURVIVOR binary."""
    for candidate in ["SURVIVOR", "survivor"]:
        try:
            subprocess.check_output([candidate, "merge"], stderr=subprocess.DEVNULL)
        except FileNotFoundError:
            continue
        except subprocess.CalledProcessError:
            # SURVIVOR prints usage and exits non-zero when called without args
            return candidate
    # Try conda env path directly
    conda_prefix = os.environ.get("CONDA_PREFIX", "")
    if conda_prefix:
        path = Path(conda_prefix) / "bin" / "SURVIVOR"
        if path.exists():
            return str(path)
    return None


def find_parent_samples(dictionary_path, output_dir):
    """Find parent sample names from dictionary that exist in pipeline output."""
    manta_dir = Path(output_dir) / "variant_calling/manta"
    tiddit_dir = Path(output_dir) / "variant_calling/tiddit"
    available = set()
    for d in [manta_dir, tiddit_dir]:
        if d.exists():
            available.update(p.name for p in d.iterdir() if p.is_dir())

    parents = []
    with open(dictionary_path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("is_parent", "").strip() != "True":
                continue
            lib = row.get("library_name_sra", "").strip()
            # Pipeline spelling may differ in punctuation (see sample_names.py)
            match = resolve_sample([lib], available)
            if match:
                parents.append(match)
    return parents


def discover_samples(output_dir):
    """Discover samples with both Manta and TIDDIT output."""
    manta_dir = Path(output_dir) / "variant_calling/manta"
    tiddit_dir = Path(output_dir) / "variant_calling/tiddit"

    manta_samples = set(p.name for p in manta_dir.iterdir() if p.is_dir()) if manta_dir.exists() else set()
    tiddit_samples = set(p.name for p in tiddit_dir.iterdir() if p.is_dir()) if tiddit_dir.exists() else set()

    both = sorted(manta_samples & tiddit_samples)
    manta_only = sorted(manta_samples - tiddit_samples)
    tiddit_only = sorted(tiddit_samples - manta_samples)

    return both, manta_only, tiddit_only


def get_vcf_path(output_dir, caller, sample):
    """Get VCF path for a caller/sample combination."""
    if caller == "manta":
        return Path(output_dir) / f"variant_calling/manta/{sample}/{sample}.manta.diploid_sv.vcf.gz"
    elif caller == "tiddit":
        return Path(output_dir) / f"variant_calling/tiddit/{sample}/{sample}.tiddit.vcf.gz"
    return None


def count_vcf_records(vcf_path, pass_only=False):
    """Count records in a VCF file."""
    cmd = ["bcftools", "view", "-H"]
    if pass_only:
        cmd.extend(["-f", "PASS"])
    cmd.append(str(vcf_path))
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return len([l for l in result.stdout.strip().split("\n") if l])
    except subprocess.CalledProcessError:
        return 0


def get_svtype_counts(vcf_path, pass_only=False):
    """Get SV type distribution from a VCF."""
    cmd = ["bcftools", "view", "-H"]
    if pass_only:
        cmd.extend(["-f", "PASS"])
    cmd.append(str(vcf_path))
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    except subprocess.CalledProcessError:
        return {}

    counts = Counter()
    for line in result.stdout.strip().split("\n"):
        if not line:
            continue
        info = line.split("\t")[7]
        for item in info.split(";"):
            if item.startswith("SVTYPE="):
                counts[item.split("=")[1]] += 1
                break
    return dict(counts)


def get_filter_counts(vcf_path):
    """Get FILTER field distribution from a VCF."""
    cmd = ["bcftools", "view", "-H", str(vcf_path)]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    except subprocess.CalledProcessError:
        return {}

    counts = Counter()
    for line in result.stdout.strip().split("\n"):
        if not line:
            continue
        filt = line.split("\t")[6]
        counts[filt] += 1
    return dict(counts)


def run_survivor_merge(manta_vcf, tiddit_vcf, workdir, min_callers=1,
                       pass_only=False):
    """Run SURVIVOR merge on Manta + TIDDIT VCFs.

    SURVIVOR does not preserve the FILTER column from input VCFs — all merged
    records get FILTER=PASS regardless of the original filter status. To get
    a PASS-filtered merge, set pass_only=True to pre-filter inputs with
    `bcftools view -f PASS` before merging.

    Returns path to merged VCF and audit dict.
    """
    survivor = find_survivor()
    if not survivor:
        return None, {"error": "SURVIVOR not found"}

    workdir = Path(workdir)
    suffix = "_pass" if pass_only else ""

    # Decompress VCFs (SURVIVOR needs uncompressed)
    # Optionally filter to PASS-only before merging
    manta_plain = workdir / f"manta{suffix}.vcf"
    tiddit_plain = workdir / f"tiddit{suffix}.vcf"

    bcftools_args = ["bcftools", "view"]
    if pass_only:
        bcftools_args.extend(["-f", "PASS"])

    subprocess.run(
        bcftools_args + ["-o", str(manta_plain), str(manta_vcf)],
        check=True, capture_output=True,
    )
    subprocess.run(
        bcftools_args + ["-o", str(tiddit_plain), str(tiddit_vcf)],
        check=True, capture_output=True,
    )

    # Write file list for SURVIVOR
    vcf_list = workdir / f"sv_vcf_list{suffix}.txt"
    vcf_list.write_text(f"{manta_plain}\n{tiddit_plain}\n")

    # Run SURVIVOR merge
    mode = "consensus" if min_callers >= 2 else "union"
    merged_vcf = workdir / f"merged_{mode}{suffix}.vcf"
    cmd = [
        survivor, "merge", str(vcf_list),
        str(MAX_DIST),        # max distance
        str(min_callers),     # min number of supporting callers
        str(TAKE_TYPE),       # take type into account
        str(TAKE_STRAND),     # take strand into account
        str(ESTIMATE_DIST),   # estimate distance by SV size
        str(MIN_SIZE),        # minimum SV size
        str(merged_vcf),      # output
    ]
    subprocess.run(cmd, check=True, capture_output=True)

    return merged_vcf, None


def parse_survivor_vcf(vcf_path):
    """Parse SURVIVOR merged VCF, extract per-record info."""
    records = []
    with open(vcf_path) as f:
        for line in f:
            if line.startswith("#") or not line.strip():
                continue
            fields = line.strip().split("\t")
            chrom = fields[0]
            pos = int(fields[1])
            info = fields[7]

            info_dict = {}
            for item in info.split(";"):
                if "=" in item:
                    k, v = item.split("=", 1)
                    info_dict[k] = v

            svtype = info_dict.get("SVTYPE", ".")
            svlen = abs(int(info_dict.get("SVLEN", 0)))
            end = int(info_dict.get("END", pos + svlen))
            supp = int(info_dict.get("SUPP", 0))
            supp_vec = info_dict.get("SUPP_VEC", "00")

            callers = []
            if len(supp_vec) >= 2:
                if supp_vec[0] == "1":
                    callers.append("Manta")
                if supp_vec[1] == "1":
                    callers.append("TIDDIT")

            records.append({
                "chrom": chrom,
                "pos": pos,
                "end": end,
                "svtype": svtype,
                "svlen": svlen,
                "supp": supp,
                "supp_vec": supp_vec,
                "callers": ",".join(callers),
            })
    return records


def count_supp_vec(records):
    """Count SUPP_VEC distribution."""
    counts = Counter()
    for r in records:
        counts[r["supp_vec"]] += 1
    return dict(counts)


def subtract_parent_svs(evolved_records, parent_records, max_dist=1000):
    """Flag evolved SVs that overlap with parent SVs.

    Returns list of evolved records with 'in_parent' field added.
    """
    result = []
    for ev in evolved_records:
        in_parent = False
        for par in parent_records:
            if ev["svtype"] != par["svtype"]:
                continue
            if ev["chrom"] != par["chrom"]:
                continue
            # Check proximity
            if abs(ev["pos"] - par["pos"]) <= max_dist and abs(ev["end"] - par["end"]) <= max_dist:
                in_parent = True
                break
        result.append({**ev, "in_parent": in_parent})
    return result


def save_merged_vcf(src_vcf, dest_path):
    """Sort, compress, and index a SURVIVOR merged VCF.

    SURVIVOR output is often unsorted, so we sort with bcftools before
    compressing to allow proper indexing.
    """
    dest_path = Path(dest_path)
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["bcftools", "sort", "-Oz", "-o", str(dest_path), str(src_vcf)],
        check=True, capture_output=True,
    )
    subprocess.run(
        ["bcftools", "index", "-t", str(dest_path)],
        check=True, capture_output=True,
    )


def characterize_sample(sample, output_dir, parent_union_records=None,
                        parent_union_pass_records=None, save_vcfs_dir=None):
    """Full SV characterization for one sample.

    If save_vcfs_dir is set, persist merged VCFs to
    <save_vcfs_dir>/<sample>/*.vcf.gz (bgzipped + indexed).

    Returns dict with all characterization data.
    """
    manta_vcf = get_vcf_path(output_dir, "manta", sample)
    tiddit_vcf = get_vcf_path(output_dir, "tiddit", sample)

    result = {
        "sample": sample,
        "manta_total": 0,
        "manta_pass": 0,
        "tiddit_total": 0,
        "tiddit_pass": 0,
        "union_total": 0,
        "consensus_total": 0,
        "union_pass_total": 0,
        "consensus_pass_total": 0,
        "evolved_unique": 0,
        "evolved_unique_pass": 0,
        "manta_svtypes": {},
        "tiddit_svtypes": {},
        "union_svtypes": {},
        "union_supp_vec": {},
        "union_records": [],
        "error": None,
    }

    if not manta_vcf.exists():
        result["error"] = f"Manta VCF not found: {manta_vcf}"
        return result
    if not tiddit_vcf.exists():
        result["error"] = f"TIDDIT VCF not found: {tiddit_vcf}"
        return result

    # Count raw records
    result["manta_total"] = count_vcf_records(manta_vcf)
    result["manta_pass"] = count_vcf_records(manta_vcf, pass_only=True)
    result["tiddit_total"] = count_vcf_records(tiddit_vcf)
    result["tiddit_pass"] = count_vcf_records(tiddit_vcf, pass_only=True)
    result["manta_svtypes"] = get_svtype_counts(manta_vcf)
    result["tiddit_svtypes"] = get_svtype_counts(tiddit_vcf)

    # SURVIVOR merge
    with tempfile.TemporaryDirectory(prefix=f"sv_{sample}_") as tmpdir:
        # Union — all records (min_callers=1)
        union_vcf, err = run_survivor_merge(manta_vcf, tiddit_vcf, tmpdir, min_callers=1)
        if err:
            result["error"] = str(err)
            return result
        union_records = parse_survivor_vcf(union_vcf)
        result["union_total"] = len(union_records)
        result["union_supp_vec"] = count_supp_vec(union_records)
        result["union_svtypes"] = Counter(r["svtype"] for r in union_records)

        # Consensus — all records (min_callers=2)
        consensus_vcf, _ = run_survivor_merge(manta_vcf, tiddit_vcf, tmpdir, min_callers=2)
        consensus_records = parse_survivor_vcf(consensus_vcf)
        result["consensus_total"] = len(consensus_records)

        # Union — PASS-only (pre-filtered inputs)
        union_pass_vcf, _ = run_survivor_merge(
            manta_vcf, tiddit_vcf, tmpdir, min_callers=1, pass_only=True)
        union_pass_records = parse_survivor_vcf(union_pass_vcf)
        result["union_pass_total"] = len(union_pass_records)

        # Consensus — PASS-only
        consensus_pass_vcf, _ = run_survivor_merge(
            manta_vcf, tiddit_vcf, tmpdir, min_callers=2, pass_only=True)
        consensus_pass_records = parse_survivor_vcf(consensus_pass_vcf)
        result["consensus_pass_total"] = len(consensus_pass_records)

        # Save merged VCFs if requested
        if save_vcfs_dir:
            sample_dir = Path(save_vcfs_dir) / sample
            save_merged_vcf(union_vcf, sample_dir / f"{sample}.survivor.union.vcf.gz")
            save_merged_vcf(consensus_vcf, sample_dir / f"{sample}.survivor.consensus.vcf.gz")
            save_merged_vcf(union_pass_vcf, sample_dir / f"{sample}.survivor.union_pass.vcf.gz")
            save_merged_vcf(consensus_pass_vcf, sample_dir / f"{sample}.survivor.consensus_pass.vcf.gz")

        # Parent subtraction (on all-records union)
        if parent_union_records is not None:
            subtracted = subtract_parent_svs(union_records, parent_union_records)
            result["evolved_unique"] = sum(1 for r in subtracted if not r["in_parent"])
            result["union_records"] = subtracted
            # Also subtract on PASS-only union
            subtracted_pass = subtract_parent_svs(union_pass_records, parent_union_pass_records)
            result["evolved_unique_pass"] = sum(1 for r in subtracted_pass if not r["in_parent"])
        else:
            result["evolved_unique"] = len(union_records)
            result["evolved_unique_pass"] = len(union_pass_records)
            result["union_records"] = [{**r, "in_parent": False} for r in union_records]

    return result


def main():
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR),
                        help="Pipeline output directory")
    parser.add_argument("--dictionary", default=str(DEFAULT_DICTIONARY),
                        help="Sample name dictionary CSV")
    parser.add_argument("--csv", default=None,
                        help="Write machine-readable CSV to this path")
    parser.add_argument("--parent", default=None,
                        help="Parent sample name (auto-detected from dictionary if not set)")
    parser.add_argument("--save-vcfs", default=None,
                        help="Save merged VCFs to this directory (e.g. output_ottilie/sv_merged)")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)

    # Check dependencies
    survivor = find_survivor()
    if not survivor:
        sys.exit("SURVIVOR not found. Activate conda nf-env first.")
    try:
        subprocess.check_output(["bcftools", "--version"], stderr=subprocess.DEVNULL)
    except FileNotFoundError:
        sys.exit("bcftools not found. Activate conda nf-env first.")

    # Discover samples
    both, manta_only, tiddit_only = discover_samples(output_dir)
    print(f"Samples with both Manta+TIDDIT: {len(both)}")
    if manta_only:
        print(f"  Manta only: {', '.join(manta_only)}")
    if tiddit_only:
        print(f"  TIDDIT only: {', '.join(tiddit_only)}")

    # Find parent
    if args.parent:
        parents = [args.parent]
    else:
        parents = find_parent_samples(args.dictionary, output_dir)
    parent = parents[0] if parents else None
    print(f"Parent sample: {parent or 'none (no subtraction)'}")

    # Merge parent first (for subtraction)
    parent_union_records = None
    parent_union_pass_records = None
    save_vcfs_dir = args.save_vcfs
    if save_vcfs_dir:
        print(f"Saving merged VCFs to: {save_vcfs_dir}/")

    if parent and parent in both:
        print(f"\nMerging parent SVs ({parent})...")
        parent_result = characterize_sample(parent, output_dir,
                                            save_vcfs_dir=save_vcfs_dir)
        if not parent_result["error"]:
            parent_union_records = parent_result["union_records"]
            # Build PASS-only parent records for PASS-tier subtraction
            manta_vcf = get_vcf_path(output_dir, "manta", parent)
            tiddit_vcf = get_vcf_path(output_dir, "tiddit", parent)
            with tempfile.TemporaryDirectory(prefix="sv_parent_pass_") as tmpdir:
                pass_vcf, _ = run_survivor_merge(
                    manta_vcf, tiddit_vcf, tmpdir, min_callers=1, pass_only=True)
                parent_union_pass_records = parse_survivor_vcf(pass_vcf)
            print(f"  Parent union: {parent_result['union_total']} SVs "
                  f"(all), {len(parent_union_pass_records)} SVs (PASS-only)")

    # Characterize all samples
    print(f"\n{'=' * 80}")
    print("SV CHARACTERIZATION REPORT")
    print(f"Note: SURVIVOR does not preserve FILTER from input VCFs.")
    print(f"  'All' merges use all records. 'PASS' merges pre-filter inputs to PASS-only.")
    print(f"{'=' * 80}")

    csv_rows = []
    all_results = []

    for sample in both:
        is_parent = (sample == parent)
        print(f"\n{'─' * 80}")
        print(f"SAMPLE: {sample}{'  [PARENT]' if is_parent else ''}")

        result = characterize_sample(
            sample, output_dir,
            parent_union_records=None if is_parent else parent_union_records,
            parent_union_pass_records=None if is_parent else parent_union_pass_records,
            save_vcfs_dir=save_vcfs_dir,
        )
        all_results.append(result)

        if result["error"]:
            print(f"  ERROR: {result['error']}")
            continue

        print(f"  Manta:  {result['manta_total']} total, {result['manta_pass']} PASS")
        print(f"  TIDDIT: {result['tiddit_total']} total, {result['tiddit_pass']} PASS")
        print(f"  SURVIVOR merge (all records):")
        print(f"    Union: {result['union_total']}  |  Consensus: {result['consensus_total']}")
        print(f"  SURVIVOR merge (PASS-only inputs):")
        print(f"    Union: {result['union_pass_total']}  |  Consensus: {result['consensus_pass_total']}")

        # SUPP_VEC breakdown
        supp = result["union_supp_vec"]
        print(f"  Union SUPP_VEC (all): 11(both)={supp.get('11', 0)}, "
              f"10(Manta)={supp.get('10', 0)}, 01(TIDDIT)={supp.get('01', 0)}")

        # SV type breakdown (union)
        if result["union_svtypes"]:
            types_str = ", ".join(f"{k}={v}" for k, v in sorted(result["union_svtypes"].items()))
            print(f"  Union SV types (all): {types_str}")

        # Parent subtraction
        if not is_parent and parent_union_records is not None:
            in_parent = sum(1 for r in result["union_records"] if r["in_parent"])
            print(f"  Parent subtraction (all):")
            print(f"    Overlap: {in_parent}/{result['union_total']} "
                  f"({in_parent/result['union_total']*100:.0f}% shared)  |  "
                  f"Evolved-unique: {result['evolved_unique']}")
            print(f"  Parent subtraction (PASS):")
            print(f"    Evolved-unique: {result['evolved_unique_pass']}")

        # CSV row
        csv_rows.append({
            "sample": sample,
            "is_parent": is_parent,
            "manta_total": result["manta_total"],
            "manta_pass": result["manta_pass"],
            "tiddit_total": result["tiddit_total"],
            "tiddit_pass": result["tiddit_pass"],
            "union_total": result["union_total"],
            "consensus_total": result["consensus_total"],
            "union_pass_total": result["union_pass_total"],
            "consensus_pass_total": result["consensus_pass_total"],
            "supp_both": supp.get("11", 0),
            "supp_manta_only": supp.get("10", 0),
            "supp_tiddit_only": supp.get("01", 0),
            "evolved_unique": result["evolved_unique"] if not is_parent else "",
            "evolved_unique_pass": result["evolved_unique_pass"] if not is_parent else "",
            "union_svtypes": json.dumps(dict(result["union_svtypes"])),
        })

    # Summary
    evolved_results = [r for r in all_results if r["sample"] != parent and not r.get("error")]
    print(f"\n{'=' * 80}")
    print("SUMMARY")
    print(f"  Samples analyzed: {len(both)}")
    if parent:
        print(f"  Parent: {parent}")
    if evolved_results:
        n = len(evolved_results)
        avg_union = sum(r["union_total"] for r in evolved_results) / n
        avg_consensus = sum(r["consensus_total"] for r in evolved_results) / n
        avg_union_pass = sum(r["union_pass_total"] for r in evolved_results) / n
        avg_consensus_pass = sum(r["consensus_pass_total"] for r in evolved_results) / n
        print(f"  Evolved samples: {n}")
        print(f"  All records:  avg union={avg_union:.1f}, avg consensus={avg_consensus:.1f}")
        print(f"  PASS-only:    avg union={avg_union_pass:.1f}, avg consensus={avg_consensus_pass:.1f}")
        if parent_union_records is not None:
            avg_unique = sum(r["evolved_unique"] for r in evolved_results) / n
            avg_unique_pass = sum(r["evolved_unique_pass"] for r in evolved_results) / n
            print(f"  Avg evolved-unique: {avg_unique:.1f} (all), {avg_unique_pass:.1f} (PASS)")
    print(f"{'=' * 80}")

    # Write CSV
    if args.csv and csv_rows:
        csv_path = Path(args.csv)
        csv_path.parent.mkdir(parents=True, exist_ok=True)
        fieldnames = ["sample", "is_parent", "manta_total", "manta_pass",
                      "tiddit_total", "tiddit_pass",
                      "union_total", "consensus_total",
                      "union_pass_total", "consensus_pass_total",
                      "supp_both", "supp_manta_only", "supp_tiddit_only",
                      "evolved_unique", "evolved_unique_pass", "union_svtypes"]
        with open(csv_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for row in csv_rows:
                writer.writerow(row)
        print(f"\nCSV written to: {csv_path}")


if __name__ == "__main__":
    main()
