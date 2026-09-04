#!/usr/bin/env python
"""
Compare the merged SV pass table (the deliverable) across Manta calling modes.

Row counts alone are misleading — per-sample and joint mode can produce near-identical
totals while saying completely different things. What matters is the GENOTYPE pattern:

  parent present     the parent carries the event (shared background, correctly shown)
  clone-specific     parent absent, >=1 clone present  -> reads as an evolved mutation
  of which FALSE     a clone-specific row whose breakpoints touch a locus the parent MUST
                     carry (engineered cassette or its components) -> false specificity

The ottilie parent is the ABC16-Green Monster: 16 ABC transporters replaced by a GFP-URA3
cassette. So a breakend at a deleted transporter, at ADH1 (the cassette's terminator), or
at URA3/CYC1 (cassette components) is engineered background — never an evolved mutation.
Getting this list wrong understates false specificity: an earlier revision omitted URA3
and CYC1 and consequently scored two cassette junctions as "real" (corrected 2026-09-04).

Usage:
    compare_sv_pass_tables.py --parent NODRUG-GM2 \
        --mode "per-sample=output_x_persample" \
        --mode "joint default=output_x_jointdefault" \
        --mode "joint high-sens=output_x_joinths" \
        [--gff3 data/ottilie/S288C_reference/S288C_R64.gff3] [--csv out.csv]

Each --mode value is "<label>=<pipeline outdir>"; the table is read from
<outdir>/mutation_reports/data/sv_cohort_matrix_union_pass.csv.
"""

import argparse
import csv
import re
import sys
from pathlib import Path

# Deleted in the ABC16-Green Monster (the breakend far-ends), plus the cassette's own parts.
ABC16 = ["PDR5", "PDR10", "PDR15", "SNQ2", "YOR1", "AUS1", "BPT1", "YCF1", "PDR11",
         "PDR12", "PDR18", "ADP1", "VMR1", "NFT1", "YBT1", "STE6", "YOL075C"]
CASSETTE_PARTS = ["ADH1",   # terminator carried by the cassette -> the breakend-star anchor
                  "URA3",   # selection marker ("universal GFP-URA3 fragment", Suzuki et al.)
                  "CYC1"]   # terminator; pairs with URA3 in the junctions Manta reports
FLANK = 500          # bp of slack around a gene when matching a breakpoint
META_COLS = ("chrom", "pos", "chrom2", "end", "svtype", "svlen")


def load_genes(gff3):
    genes = {}
    with open(gff3) as fh:
        for line in fh:
            f = line.split("\t")
            if len(f) > 8 and f[2] == "gene":
                m = re.search(r"Name=([^;]+)", f[8])
                if m:
                    genes.setdefault(m.group(1), (f[0], int(f[3]), int(f[4])))
    return genes


def cassette_hit(genes, chrom, pos):
    """Name of the engineered locus this breakpoint falls in, or None."""
    try:
        pos = int(pos)
    except (TypeError, ValueError):
        return None
    for g in ABC16 + CASSETTE_PARTS:
        if g in genes:
            gc, start, end = genes[g]
            if gc == chrom and start - FLANK <= pos <= end + FLANK:
                return g
    return None


def load_table(outdir):
    path = Path(outdir) / "mutation_reports/data/sv_cohort_matrix_union_pass.csv"
    if not path.exists():
        sys.exit(f"missing pass table: {path}")
    rows = list(csv.DictReader(open(path)))
    if not rows:
        return [], []
    samples = [c for c in rows[0] if c not in META_COLS]
    return rows, samples


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--mode", action="append", required=True, metavar="LABEL=OUTDIR")
    ap.add_argument("--parent", required=True, help="parent/ancestral sample name")
    ap.add_argument("--gff3", default="data/ottilie/S288C_reference/S288C_R64.gff3")
    ap.add_argument("--csv", help="write the summary table here")
    args = ap.parse_args()

    genes = load_genes(args.gff3)
    out_rows = []

    for spec in args.mode:
        label, _, outdir = spec.partition("=")
        rows, samples = load_table(outdir)
        if args.parent not in samples:
            sys.exit(f"parent {args.parent!r} not among columns {samples}")
        clones = [s for s in samples if s != args.parent]
        present = lambda r, s: r[s] != "-"

        parent_present = sum(1 for r in rows if present(r, args.parent))
        parent_manta = sum(1 for r in rows if "Manta" in r[args.parent])
        clone_specific = [r for r in rows
                          if not present(r, args.parent) and any(present(r, c) for c in clones)]
        false_specific = [r for r in clone_specific
                          if cassette_hit(genes, r["chrom"], r["pos"])
                          or cassette_hit(genes, r["chrom2"], r["end"])]

        out_rows.append({
            "mode": label, "samples": len(samples), "pass_rows": len(rows),
            "parent_present": parent_present, "parent_via_manta": parent_manta,
            "clone_specific": len(clone_specific), "clone_specific_false": len(false_specific),
            "clone_specific_candidate_real": len(clone_specific) - len(false_specific),
        })

        print(f"\n### {label}  ({len(samples)} samples, {len(rows)} pass rows)")
        print(f"    parent present in {parent_present} rows ({parent_manta} with Manta support)")
        print(f"    clone-specific: {len(clone_specific)}  of which false (engineered locus): "
              f"{len(false_specific)}")
        for r in clone_specific:
            tag = (cassette_hit(genes, r["chrom"], r["pos"])
                   or cassette_hit(genes, r["chrom2"], r["end"]))
            carriers = ", ".join(f"{c}={r[c]}" for c in clones if present(r, c))
            verdict = f"FALSE [{tag}]" if tag else "candidate real"
            print(f"      {r['chrom']}:{r['pos']}->{r['chrom2']}:{r['end']} {r['svtype']:4} "
                  f"{verdict}\n          {carriers}")

    if args.csv:
        with open(args.csv, "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(out_rows[0]))
            w.writeheader()
            w.writerows(out_rows)
        print(f"\nSummary written to {args.csv}")

    print("\nNOTE: 'candidate real' means only 'not at a known engineered locus'. Verify any such "
          "row against the parent's READS before believing it — a parent that carries the junction "
          "with comparable support but is scored '-' is a calling artifact, not biology "
          "(see REPORT.md, URA3xCYC1 case).")


if __name__ == "__main__":
    main()
