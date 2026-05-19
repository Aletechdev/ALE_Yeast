#!/usr/bin/env python3
"""
Compare breseq structural variants (from .gd file) with SURVIVOR-merged
SV calls from Manta + TIDDIT.

Usage:
    python compare_breseq_sv.py \
        --gd output.gd \
        --survivor_union merged_union.vcf \
        --survivor_consensus merged_consensus.vcf \
        --max_dist 1000 \
        -o comparison_report.tsv
"""

import argparse
import csv
import sys
from dataclasses import dataclass


@dataclass
class SV:
    chrom: str
    pos: int
    end: int
    svtype: str
    svlen: int
    source: str
    extra: str = ""


def parse_breseq_gd(gd_path):
    """Parse DEL, MOB, AMP, INV, CON, INS entries from breseq GD file."""
    svs = []
    with open(gd_path) as f:
        for line in f:
            if line.startswith("#"):
                continue
            fields = line.strip().split("\t")
            if len(fields) < 5:
                continue
            entry_type = fields[0]
            entry_id = fields[1]
            evidence_ids = fields[2]
            chrom = fields[3]
            pos = int(fields[4])

            if entry_type == "DEL" and len(fields) >= 6:
                size = int(fields[5])
                svs.append(SV(chrom, pos, pos + size, "DEL", size,
                              "breseq", f"id={entry_id}"))
            elif entry_type == "MOB" and len(fields) >= 7:
                element = fields[5]
                strand = fields[6]
                dup_size = int(fields[7]) if len(fields) > 7 else 0
                svs.append(SV(chrom, pos, pos + dup_size, "INS", dup_size,
                              "breseq", f"id={entry_id};element={element};strand={strand}"))
            elif entry_type == "AMP" and len(fields) >= 7:
                size = int(fields[5])
                copy = fields[6] if len(fields) > 6 else "?"
                svs.append(SV(chrom, pos, pos + size, "DUP", size,
                              "breseq", f"id={entry_id};copies={copy}"))
            elif entry_type == "INV" and len(fields) >= 6:
                size = int(fields[5])
                svs.append(SV(chrom, pos, pos + size, "INV", size,
                              "breseq", f"id={entry_id}"))
            elif entry_type == "INS" and len(fields) >= 6:
                seq = fields[5]
                svs.append(SV(chrom, pos, pos, "INS", len(seq),
                              "breseq", f"id={entry_id};seq={seq}"))
            elif entry_type == "CON" and len(fields) >= 6:
                size = int(fields[5]) if fields[5].isdigit() else 0
                svs.append(SV(chrom, pos, pos + size, "CON", size,
                              "breseq", f"id={entry_id}"))
    return svs


def parse_survivor_vcf(vcf_path):
    """Parse SURVIVOR merged VCF, extracting per-caller support info."""
    svs = []
    with open(vcf_path) as f:
        for line in f:
            if line.startswith("#"):
                continue
            fields = line.strip().split("\t")
            chrom = fields[0]
            pos = int(fields[1])
            info = fields[7]

            # Parse INFO
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

            svs.append(SV(chrom, pos, end, svtype, svlen,
                          ",".join(callers),
                          f"SUPP={supp};SUPP_VEC={supp_vec}"))
    return svs


def match_svs(breseq_svs, survivor_svs, max_dist=1000):
    """Match breseq SVs to SURVIVOR merged SVs by proximity and type.

    Returns list of (breseq_sv, matched_survivor_sv_or_None, distance).
    """
    # Type mapping: breseq -> compatible SV types
    compatible = {
        "DEL": {"DEL"},
        "INS": {"INS"},
        "DUP": {"DUP"},
        "INV": {"INV"},
        "CON": {"DEL", "DUP", "INV"},  # could be any rearrangement
    }

    results = []
    used_survivor = set()

    for bsv in breseq_svs:
        best_match = None
        best_dist = max_dist + 1

        for i, ssv in enumerate(survivor_svs):
            if i in used_survivor:
                continue
            if ssv.chrom != bsv.chrom:
                continue
            if ssv.svtype not in compatible.get(bsv.svtype, {bsv.svtype}):
                continue

            # Distance = max of start offset and end offset
            dist = max(abs(bsv.pos - ssv.pos), abs(bsv.end - ssv.end))
            if dist < best_dist:
                best_dist = dist
                best_match = (i, ssv)

        if best_match and best_dist <= max_dist:
            used_survivor.add(best_match[0])
            results.append((bsv, best_match[1], best_dist))
        else:
            results.append((bsv, None, None))

    # Survivor SVs not matched to any breseq call
    for i, ssv in enumerate(survivor_svs):
        if i not in used_survivor:
            results.append((None, ssv, None))

    return results


def main():
    parser = argparse.ArgumentParser(description="Compare breseq GD vs SURVIVOR-merged SVs")
    parser.add_argument("--gd", required=True, help="breseq output.gd file")
    parser.add_argument("--survivor_union", required=True, help="SURVIVOR union VCF (min_callers=1)")
    parser.add_argument("--survivor_consensus", required=True, help="SURVIVOR consensus VCF (min_callers=2)")
    parser.add_argument("--max_dist", type=int, default=1000, help="Max distance for matching (bp)")
    parser.add_argument("-o", "--output", default="comparison_report.tsv", help="Output TSV")
    args = parser.parse_args()

    breseq_svs = parse_breseq_gd(args.gd)
    union_svs = parse_survivor_vcf(args.survivor_union)
    consensus_svs = parse_survivor_vcf(args.survivor_consensus)

    print(f"Parsed {len(breseq_svs)} SVs from breseq GD")
    print(f"Parsed {len(union_svs)} SVs from SURVIVOR union")
    print(f"Parsed {len(consensus_svs)} SVs from SURVIVOR consensus")
    print()

    # Build consensus lookup for quick check
    consensus_positions = set()
    for sv in consensus_svs:
        consensus_positions.add((sv.chrom, sv.svtype, sv.pos))

    # Match against union (all calls)
    matches = match_svs(breseq_svs, union_svs, args.max_dist)

    # Write report
    with open(args.output, "w", newline="") as f:
        w = csv.writer(f, delimiter="\t")
        w.writerow([
            "breseq_type", "breseq_pos", "breseq_end", "breseq_size", "breseq_extra",
            "sv_type", "sv_pos", "sv_end", "sv_size", "sv_callers", "sv_supp_vec",
            "in_consensus", "match_dist", "status"
        ])

        for bsv, ssv, dist in matches:
            if bsv and ssv:
                # Check if in consensus
                in_cons = any(
                    ssv.chrom == c[0] and ssv.svtype == c[1] and abs(ssv.pos - c[2]) <= args.max_dist
                    for c in consensus_positions
                )
                w.writerow([
                    bsv.svtype, bsv.pos, bsv.end, bsv.svlen, bsv.extra,
                    ssv.svtype, ssv.pos, ssv.end, ssv.svlen, ssv.source, ssv.extra,
                    "YES" if in_cons else "NO", dist,
                    "MATCHED"
                ])
            elif bsv:
                w.writerow([
                    bsv.svtype, bsv.pos, bsv.end, bsv.svlen, bsv.extra,
                    ".", ".", ".", ".", ".", ".",
                    "NO", ".",
                    "BRESEQ_ONLY"
                ])
            elif ssv:
                w.writerow([
                    ".", ".", ".", ".", ".",
                    ssv.svtype, ssv.pos, ssv.end, ssv.svlen, ssv.source, ssv.extra,
                    any(
                        ssv.chrom == c[0] and ssv.svtype == c[1] and abs(ssv.pos - c[2]) <= args.max_dist
                        for c in consensus_positions
                    ),
                    ".",
                    "SV_CALLER_ONLY"
                ])

    print(f"Report written to {args.output}")
    print()

    # Print summary to stdout
    matched = sum(1 for b, s, d in matches if b and s)
    breseq_only = sum(1 for b, s, d in matches if b and not s)
    sv_only = sum(1 for b, s, d in matches if not b and s)

    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"  breseq SVs:           {len(breseq_svs)}")
    print(f"  SURVIVOR union SVs:   {len(union_svs)}")
    print(f"  SURVIVOR consensus:   {len(consensus_svs)}")
    print()
    print(f"  Matched (breseq ↔ SV callers):  {matched}")
    print(f"  breseq-only:                     {breseq_only}")
    print(f"  SV-caller-only:                  {sv_only}")
    print()

    # Print matched details
    print("MATCHED SVs:")
    print(f"  {'Type':<6} {'breseq_pos':>12} {'breseq_size':>12} {'sv_pos':>12} {'sv_size':>12} {'callers':<20} {'dist':>6}")
    print(f"  {'-'*6} {'-'*12} {'-'*12} {'-'*12} {'-'*12} {'-'*20} {'-'*6}")
    for bsv, ssv, dist in matches:
        if bsv and ssv:
            print(f"  {bsv.svtype:<6} {bsv.pos:>12,} {bsv.svlen:>12,} {ssv.pos:>12,} {ssv.svlen:>12,} {ssv.source:<20} {dist:>6}")

    if breseq_only > 0:
        print()
        print("BRESEQ-ONLY SVs (not detected by Manta/TIDDIT):")
        for bsv, ssv, dist in matches:
            if bsv and not ssv:
                print(f"  {bsv.svtype:<6} pos={bsv.pos:,}  size={bsv.svlen:,}  {bsv.extra}")

    if sv_only > 0:
        print()
        print("SV-CALLER-ONLY (not in breseq):")
        for bsv, ssv, dist in matches:
            if not bsv and ssv:
                print(f"  {ssv.svtype:<6} pos={ssv.pos:,}  size={ssv.svlen:,}  callers={ssv.source}  {ssv.extra}")


if __name__ == "__main__":
    main()
