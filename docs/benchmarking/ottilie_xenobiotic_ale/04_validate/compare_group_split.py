#!/usr/bin/env python
"""Score a multi-experiment (group-split) joint-Manta run against a single-group run.

Question it answers: when a cohort is split into several `experiment` groups, does every
junction still end up with the same evidence it had in one group -- in particular, is the
parent still on the engineered-cassette rows?

The SV merge unifies two rows only when BOTH breakpoints are within `--window` bp
(the rule used by sv_cohort_matrix.py). So a junction that PASSes in one group but is
FILTERED in another cannot be unified: the second group contributes no row to merge with,
and the junction ends up supported only by the group that called it.

Usage:
  compare_group_split.py --group NAME=joint.vcf.gz [--group NAME=... ] \
                         [--single single_group_joint.vcf.gz] [--parent SAMPLE] [--window 1000]

Reads Manta joint VCFs directly (pre-merge), so it works even when a run failed downstream.
"""
import argparse, gzip, re, sys

# Engineered background of the ABC16-Green Monster parent: cassette parts + the 16 deleted
# ABC transporters. A row at one of these is strain background, not an ALE mutation.
# See DATA_PROVENANCE.md ("ABC16-Green Monster") and 04_validate/README.md.
CASSETTE_ANCHOR = ("XV", 159400, 159900)   # ADH1 terminator (ADH1/YOL086C is on the minus strand)
# 5' flanks of the deleted transporters, as measured in the read-level audit (2026-09-02).
DELETED_5P = {
    "IV": [465900, 727500, 1279200], "III": [136900], "VII": [1052800], "VIII": [27900, 32650],
    "IX": [332400], "XI": [653000], "XII": [46150, 116400], "XIV": [765350],
    "XV": [349650, 353800, 619800, 931850],
}
POLYLINKER = "GGATCCCCGGGTTAATTAAGGCGCGCC"   # cassette polylinker, present in resolved junctions


def in_anchor(chrom, pos):
    c, lo, hi = CASSETTE_ANCHOR
    return chrom == c and lo <= pos <= hi


def at_deleted_5p(chrom, pos, window=2000):
    return any(abs(pos - p) <= window for p in DELETED_5P.get(chrom, []))


def engineered(row):
    """A row is engineered background if either breakend is the cassette anchor or a deleted 5' flank."""
    ends = [(row["chrom"], row["pos"])] + ([row["mate"]] if row["mate"] else [])
    return any(in_anchor(c, p) or at_deleted_5p(c, p) for c, p in ends)


MATE_RE = re.compile(r"[\[\]]([^\[\]:]+):(\d+)[\[\]]")


def read_vcf(path):
    op = gzip.open if str(path).endswith(".gz") else open
    samples, rows = [], []
    with op(path, "rt") as fh:
        for line in fh:
            if line.startswith("#CHROM"):
                samples = line.rstrip("\n").split("\t")[9:]
                continue
            if line.startswith("#"):
                continue
            f = line.rstrip("\n").split("\t")
            m = MATE_RE.search(f[4])
            svtype = re.search(r"SVTYPE=([A-Z]+)", f[7])
            gts = {}
            for name, col in zip(samples, f[9:]):
                gt = col.split(":")[0]
                gts[name] = gt not in ("0/0", "./.", ".", "0|0")
            rows.append({
                "chrom": f[0], "pos": int(f[1]), "filter": f[6], "alt": f[4],
                "svtype": svtype.group(1) if svtype else "?",
                "mate": (m.group(1), int(m.group(2))) if m else None,
                "resolved": POLYLINKER in f[4],
                "gts": gts, "carriers": sorted(k for k, v in gts.items() if v),
            })
    return samples, rows


def same_junction(a, b, window):
    """Both breakends within `window` bp -- the sv_cohort_matrix proximity rule."""
    def near(x, y):
        return x[0] == y[0] and abs(x[1] - y[1]) <= window
    ea = [(a["chrom"], a["pos"])] + ([a["mate"]] if a["mate"] else [])
    eb = [(b["chrom"], b["pos"])] + ([b["mate"]] if b["mate"] else [])
    if len(ea) != len(eb):
        return False
    if len(ea) == 1:
        return near(ea[0], eb[0])
    return (near(ea[0], eb[0]) and near(ea[1], eb[1])) or (near(ea[0], eb[1]) and near(ea[1], eb[0]))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--group", action="append", required=True, metavar="NAME=VCF")
    ap.add_argument("--single", help="single-group joint VCF over the same samples, for reference")
    ap.add_argument("--parent", default="NODRUG-GM2", help="substring identifying the parent column")
    ap.add_argument("--window", type=int, default=1000)
    args = ap.parse_args()

    groups = {}
    for spec in args.group:
        name, _, path = spec.partition("=")
        samples, rows = read_vcf(path)
        groups[name] = {"samples": samples, "rows": rows,
                        "pass": [r for r in rows if r["filter"] == "PASS"]}

    print("=" * 78)
    print("PER-GROUP SUMMARY")
    print("=" * 78)
    for name, g in groups.items():
        has_parent = any(args.parent in s for s in g["samples"])
        res_pass = sum(1 for r in g["pass"] if r["resolved"])
        res_filt = sum(1 for r in g["rows"] if r["resolved"] and r["filter"] != "PASS")
        eng_pass = sum(1 for r in g["pass"] if engineered(r))
        print(f"\n{name}: {len(g['samples'])} samples, parent {'PRESENT' if has_parent else 'ABSENT'}")
        print(f"  records {len(g['rows'])}, PASS {len(g['pass'])}, engineered-locus PASS {eng_pass}")
        print(f"  cassette-resolved junctions (polylinker in ALT): {res_pass} PASS, {res_filt} filtered")
        if res_filt:
            tags = {}
            for r in g["rows"]:
                if r["resolved"] and r["filter"] != "PASS":
                    tags[r["filter"]] = tags.get(r["filter"], 0) + 1
            print(f"    filtered as: {tags}")
        if has_parent:
            eng = [r for r in g["pass"] if engineered(r)]
            withp = sum(1 for r in eng if any(args.parent in c for c in r["carriers"]))
            print(f"  parent carries {withp}/{len(eng)} engineered-locus PASS rows")

    # Cross-group unification: can the merge put these back together?
    names = list(groups)
    print()
    print("=" * 78)
    print(f"CROSS-GROUP UNIFICATION  (both breakends within {args.window} bp)")
    print("=" * 78)
    print("A junction PASSing in one group but absent from another group's PASS set cannot be")
    print("unified by the merge -- it will carry evidence from the calling group only.\n")

    for i, a in enumerate(names):
        for b in names:
            if a == b:
                continue
            unmatched = [r for r in groups[a]["pass"]
                         if not any(same_junction(r, s, args.window) for s in groups[b]["pass"])]
            eng_un = [r for r in unmatched if engineered(r)]
            print(f"{a} PASS rows with no {b} counterpart: {len(unmatched)}"
                  f"  (at engineered loci: {len(eng_un)})")
            for r in eng_un:
                mate = f"{r['mate'][0]}:{r['mate'][1]}" if r["mate"] else "-"
                # was it merely filtered in the other group, rather than never called?
                filt = [s for s in groups[b]["rows"] if s["filter"] != "PASS"
                        and same_junction(r, s, args.window)]
                why = f"FILTERED in {b} as {filt[0]['filter']}" if filt else f"not called in {b}"
                print(f"    {r['chrom']}:{r['pos']} {r['svtype']} -> {mate}"
                      f"  [{len(r['carriers'])} carriers]  {why}")
        if i == 0:
            print()

    if args.single:
        s_samples, s_rows = read_vcf(args.single)
        s_pass = [r for r in s_rows if r["filter"] == "PASS"]
        print()
        print("=" * 78)
        print("VS SINGLE-GROUP RUN OVER THE SAME SAMPLES")
        print("=" * 78)
        print(f"single group: {len(s_samples)} samples, {len(s_rows)} records, {len(s_pass)} PASS")
        allg = [r for g in groups.values() for r in g["pass"]]
        lost = [r for r in s_pass if not any(same_junction(r, t, args.window) for t in allg)]
        gained = [r for r in allg if not any(same_junction(r, t, args.window) for t in s_pass)]
        print(f"  in single but in NO group: {len(lost)}  (engineered: {sum(1 for r in lost if engineered(r))})")
        for r in lost:
            mate = f"{r['mate'][0]}:{r['mate'][1]}" if r["mate"] else "-"
            print(f"    LOST   {r['chrom']}:{r['pos']} {r['svtype']} -> {mate}"
                  f"  {'[engineered]' if engineered(r) else '[candidate real]'}")
        print(f"  in a group but NOT in single: {len(gained)}  (engineered: {sum(1 for r in gained if engineered(r))})")
        for r in gained:
            mate = f"{r['mate'][0]}:{r['mate'][1]}" if r["mate"] else "-"
            print(f"    GAINED {r['chrom']}:{r['pos']} {r['svtype']} -> {mate}"
                  f"  {'[engineered]' if engineered(r) else '[candidate real]'}")

    print()
    print("NOTE: 'candidate real' means only 'not at a known engineered locus'. It is NOT a")
    print("      validated mutation -- confirm at read level before calling anything real.")


if __name__ == "__main__":
    main()
