#!/usr/bin/env python3
"""Collapse SV breakend PAIRS to one record per junction.

Both callers report an inter-chromosomal (and, for TIDDIT, some intra-chromosomal)
junction as TWO breakend records — one per end. SVDB treats a BND as an unordered
(chrA:posA, chrB:posB) breakpoint pair, and --no_intra only stops a cluster being
SEEDED from a file, not JOINED by it, so feeding both mates produces asymmetric
merges (one Manta mate absorbs both TIDDIT mates while its own mate merges with
nothing). Collapsing to one record per junction BEFORE any merge fixes that; the
dropped mate carries the same GT/PR/SR, so nothing is lost. Validated in
docs/benchmarking/ottilie_xenobiotic_ale/04_validate/sv_merge_bench/ (finding F3).

Rules:
  - Manta:  drop a BND whose MATEID was already emitted (keeps the first mate;
            run convertInversion.py FIRST so INV pairs are already <INV> records).
  - TIDDIT: drop BND records with ids matching SV_<n>_2 (TIDDIT pairs are SV_<n>_1
            / SV_<n>_2 and always adjacent in ascending n).

Non-BND records pass through untouched. Reads .vcf or .vcf.gz; writes plain VCF
to stdout. Usage: collapse_sv_pairs.py <in.vcf[.gz]> > out.vcf
"""
import gzip
import re
import sys


def main():
    path = sys.argv[1]
    opener = gzip.open if path.endswith(".gz") else open
    seen_ids = set()
    kept = dropped = 0
    with opener(path, "rt") as fh:
        for line in fh:
            if line.startswith("#"):
                sys.stdout.write(line)
                continue
            fields = line.rstrip("\n").split("\t")
            info = dict(
                kv.split("=", 1) if "=" in kv else (kv, True)
                for kv in fields[7].split(";")
            )
            if info.get("SVTYPE") == "BND":
                mate = info.get("MATEID")
                if mate is not None:  # Manta
                    if mate in seen_ids:
                        dropped += 1
                        continue
                    seen_ids.add(fields[2])
                elif re.fullmatch(r"SV_\d+_2", fields[2]):  # TIDDIT second mate
                    dropped += 1
                    continue
            kept += 1
            sys.stdout.write(line)
    print(f"collapse_sv_pairs: kept {kept}, dropped {dropped} mate records", file=sys.stderr)


if __name__ == "__main__":
    main()
