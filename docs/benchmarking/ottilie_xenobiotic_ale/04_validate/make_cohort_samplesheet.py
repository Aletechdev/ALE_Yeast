#!/usr/bin/env python
"""
Build a CRAM samplesheet for a cohort-size / grouping experiment from the Tier-2 CRAMs.

The SV mode comparison (run_sv_mode_series.sh -> compare_sv_pass_tables.py) needs the SAME samples
entered at --step variant_calling at several cohort sizes. This builds those sheets.

Two rules that are easy to get wrong and cost a run each:

  * `--experiment` must match the experiment encoded in the CRAMs' @RG SM tags. The joint-VCF split
    looks for "<experiment>_<sample>" while the caller names VCF columns from SM; if they diverge the
    run dies later with a misleading `the tag "FT" is not defined in the VCF header`. The Tier-2
    CRAMs are stamped `Ottilie_tier2`, so keep that unless you re-aligned. (Keeping it constant
    across sizes also lets per-sample TIDDIT tasks cache-hit between runs.)
  * The parent can be in only ONE group. Repeating it across groups collides in the cohort report
    (`input file name collision -- ... NODRUG-GM2.tiddit.ploidies.tab`), because per-sample files are
    collected by sample name. Use --groups with the parent landing in the first group.

Usage:
  # single-group cohorts of 16 and 48 (parent + first N-1 clones, sorted for determinism)
  make_cohort_samplesheet.py --n 16 --out sheet16.csv
  make_cohort_samplesheet.py --n 48 --out sheet48.csv
  # all 86
  make_cohort_samplesheet.py --out sheet86.csv
  # split a 16-sample cohort into 2 experiment groups (parent goes to the first)
  make_cohort_samplesheet.py --n 16 --groups 2 --out sheet_2groups.csv
"""

import argparse
import csv
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
CRAM_DIR = REPO / "output_ottilie_tier2/preprocessing/markduplicates"
TIER2_SHEET = REPO / "data/ottilie/samplesheet_tier2.csv"
FIELDS = ["experiment", "sample", "status", "clonal_or_population", "ploidy", "sex", "cram", "crai"]


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", required=True)
    ap.add_argument("--n", type=int, help="cohort size incl. parent (default: all available)")
    ap.add_argument("--groups", type=int, default=1, help="split into N experiment groups")
    ap.add_argument("--parent", default="NODRUG-GM2")
    ap.add_argument("--experiment", default="Ottilie_tier2",
                    help="must match the CRAMs' @RG SM prefix; ignored when --groups > 1")
    args = ap.parse_args()

    seen, meta = [], {}
    for r in csv.DictReader(open(TIER2_SHEET)):
        if r["sample"] not in meta:
            meta[r["sample"]] = r
            seen.append(r["sample"])

    def entry(sample, experiment):
        cram = CRAM_DIR / sample / f"{sample}.md.cram"
        if not (cram.exists() and Path(str(cram) + ".crai").exists()):
            sys.exit(f"missing CRAM for {sample}: {cram}")
        m = meta[sample]
        return {"experiment": experiment, "sample": sample, "status": m["status"],
                "clonal_or_population": m["clonal_or_population"], "ploidy": m["ploidy"],
                "sex": m["sex"], "cram": str(cram), "crai": str(cram) + ".crai"}

    clones = sorted(s for s in seen if s != args.parent)
    if args.n:
        clones = clones[:args.n - 1]

    rows = []
    if args.groups == 1:
        rows.append(entry(args.parent, args.experiment))
        rows += [entry(s, args.experiment) for s in clones]
    else:
        # parent joins the FIRST group only — it cannot be repeated (see docstring)
        chunks = [clones[i::args.groups] for i in range(args.groups)]
        for i, chunk in enumerate(chunks):
            grp = f"{args.experiment}_grp{chr(ord('A') + i)}"
            if i == 0:
                rows.append(entry(args.parent, grp))
            rows += [entry(s, grp) for s in chunk]

    with open(args.out, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)
    from collections import Counter
    print(f"{len(rows)} rows -> {args.out}   groups: {dict(Counter(r['experiment'] for r in rows))}")


if __name__ == "__main__":
    main()
