#!/usr/bin/env python
"""
SV Cohort Matrix — builds a cohort-level wide-format table from a
SURVIVOR-merged cohort VCF and the original per-sample SURVIVOR VCFs.

Each row is an SV event, columns are samples, cells show which callers
(Manta/TIDDIT) detected it in that sample.

Pipeline-only mode: expects pre-merged cohort VCF from SURVIVOR_COHORT_MERGE
and per-sample plain VCFs from SURVIVOR_SV_MERGE.

Usage (from BUILD_SV_MATRIX process):
    sv_cohort_matrix.py \
        --cohort-vcf cohort_merged.vcf \
        --sample-vcfs CBR110-15-R3a.survivor.union_pass.vcf \
                      NODRUG-GM2.survivor.union_pass.vcf \
        --csv sv_cohort_matrix_union_pass.csv

Standalone version preserved at:
    docs/benchmarking/ottilie_xenobiotic_ale/04_validate/sv_cohort_matrix.py
"""

import argparse
import csv
import sys
from pathlib import Path

CHR_ORDER = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII",
             "IX", "X", "XI", "XII", "XIII", "XIV", "XV", "XVI"]

MAX_DIST = 1000


def parse_survivor_vcf(vcf_path):
    """Parse SURVIVOR VCF, return list of record dicts."""
    records = []
    with open(vcf_path) as f:
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
        pos_dist = abs(rec["pos"] - cohort_rec["pos"])
        end_dist = abs(rec["end"] - cohort_rec["end"])
        if pos_dist > max_dist and end_dist > max_dist:
            continue
        dist = pos_dist + end_dist
        if dist < best_dist:
            best = rec
            best_dist = dist
    return best


def extract_sample_name(vcf_path):
    """Extract sample name from VCF filename (e.g. 'CBR110-15-R3a.survivor.union_pass.vcf' -> 'CBR110-15-R3a')."""
    name = Path(vcf_path).name
    # Strip .survivor.{mode}.vcf suffix
    for suffix in [".vcf", ".vcf.gz"]:
        if name.endswith(suffix):
            name = name[: -len(suffix)]
    # Strip .survivor.{mode}
    parts = name.split(".survivor.")
    return parts[0] if len(parts) > 1 else name


def main():
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--cohort-vcf", required=True,
                        help="Cohort-level SURVIVOR merged VCF (plain)")
    parser.add_argument("--sample-vcfs", required=True, nargs="+",
                        help="Per-sample SURVIVOR merged VCFs (plain)")
    parser.add_argument("--csv", required=True,
                        help="Output CSV path")
    args = parser.parse_args()

    # Parse per-sample VCFs
    sample_records = {}
    sample_names = []
    for vcf_path in sorted(args.sample_vcfs):
        sample = extract_sample_name(vcf_path)
        sample_names.append(sample)
        sample_records[sample] = parse_survivor_vcf(vcf_path)

    print(f"Samples: {', '.join(sample_names)}")

    # Parse cohort VCF
    cohort_records = parse_survivor_vcf(args.cohort_vcf)
    print(f"Cohort events: {len(cohort_records)}")

    # Sort by chromosome order + position
    cohort_records.sort(key=lambda r: (chr_sort_key(r["chrom"]), r["pos"], r["end"], r["svtype"]))

    # Map cohort events back to per-sample caller info
    out_path = Path(args.csv)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = ["chrom", "pos", "chrom2", "end", "svtype", "svlen"] + sample_names
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
            for s in sample_names:
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
