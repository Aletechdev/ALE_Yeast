#!/usr/bin/env python
"""
Loss audit: per-sample Manta vs joint (multi-sample) Manta on the same CRAMs.

Answers, for every sample, four questions (stdlib only — no pysam):
  (i)   is every per-sample PASS record present in the joint VCF (same SVTYPE, same mate
        contig for BNDs, position within the joint record's CIPOS + tolerance)?
  (ii)  both directions for the rest:
        (a) per-sample NON-PASS records → in the joint VCF? with what FILTER / this sample's FT?
        (b) joint-only presences (sample GT is alt in the joint VCF, no per-sample record) →
            what is this sample's own evidence (PR/SR, GQ, FT)?
  (iii) for matched pairs, the sample's own PR/SR alt counts, per-sample vs joint
        (pooling must not smear evidence between samples);
  (iv)  breakpoint shift |POS_single - POS_joint| vs the joint CIPOS.

Usage:
    manta_joint_vs_single.py --joint joint.manta.diploid_sv.vcf.gz \
        --single CBR110-15-R3a=CBR110-15-R3a.manta.diploid_sv.vcf.gz [--single ...] \
        --joint-sample-prefix Ottilie_pilot_ --out audit_dir

Writes <out>/summary.tsv (one row per sample) and <out>/details_<sample>.tsv (one row per
per-sample record and per joint-only presence). The summary is what goes into the roadmap.
"""

import argparse
import csv
import gzip
import re
from collections import defaultdict
from pathlib import Path

TOL = 50  # bp added to the joint CIPOS when matching breakpoints


def read_vcf(path):
    samples, records = [], []
    with gzip.open(path, "rt") as fh:
        for line in fh:
            if line.startswith("##"):
                continue
            if line.startswith("#CHROM"):
                samples = line.rstrip("\n").split("\t")[9:]
                continue
            f = line.rstrip("\n").split("\t")
            info = {}
            for item in f[7].split(";"):
                k, _, v = item.partition("=")
                info[k] = v if _ else True
            fmt = f[8].split(":")
            per_sample = {}
            for s, col in zip(samples, f[9:]):
                per_sample[s] = dict(zip(fmt, col.split(":")))
            svtype = info.get("SVTYPE", ".")
            mate_chrom, mate_pos = None, None
            if svtype == "BND":
                m = re.search(r"[\[\]]([^:\[\]]+):(\d+)[\[\]]", f[4])
                mate_chrom = m.group(1) if m else None
                mate_pos = int(m.group(2)) if m else None
            elif info.get("END", ".") != ".":
                mate_pos = int(info["END"])  # DEL/DUP/INV/INS: second breakpoint = END
            cipos = info.get("CIPOS", "0,0").split(",")
            cipos = (int(cipos[0]), int(cipos[1])) if len(cipos) == 2 else (0, 0)
            records.append({
                "chrom": f[0], "pos": int(f[1]), "id": f[2], "filter": f[6],
                "svtype": svtype, "mate_chrom": mate_chrom, "mate_pos": mate_pos, "cipos": cipos,
                "svlen": info.get("SVLEN", "."), "end": info.get("END", "."),
                "samples": per_sample,
            })
    return samples, records


def is_present(gt):
    return gt not in ("0/0", "0|0", "./.", ".|.", ".")


def alt_support(fmt):
    """(PR_alt, SR_alt) from Manta's FORMAT; '.' when absent."""
    def alt(v):
        if not v or v == ".":
            return 0
        parts = v.split(",")
        return int(parts[1]) if len(parts) == 2 else 0
    return alt(fmt.get("PR")), alt(fmt.get("SR"))


def find_match(rec, joint_by_key):
    """Joint record with same chrom/svtype/mate_chrom whose CIPOS(+TOL) covers POS; among
    candidates, the one whose SECOND breakpoint (BND mate / END) is nearest — breakend stars
    (many BNDs at one position, different mates) are only separable on the mate coordinate."""
    best, best_d = None, None
    for j in joint_by_key.get((rec["chrom"], rec["svtype"], rec["mate_chrom"]), []):
        lo = j["pos"] + j["cipos"][0] - TOL
        hi = j["pos"] + j["cipos"][1] + TOL
        if not (lo <= rec["pos"] <= hi):
            continue
        d = abs(j["pos"] - rec["pos"])
        if rec["mate_pos"] is not None and j["mate_pos"] is not None:
            d_mate = abs(j["mate_pos"] - rec["mate_pos"])
            if d_mate > hi - lo + 2 * TOL:      # mate must agree within the same window
                continue
            d += d_mate
        if best is None or d < best_d:
            best, best_d = j, d
    return best


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--joint", required=True)
    ap.add_argument("--single", required=True, action="append", help="sample=vcf.gz (repeatable)")
    ap.add_argument("--joint-sample-prefix", default="", help="prefix of the joint VCF's sample columns (e.g. 'Ottilie_pilot_')")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    joint_samples, joint = read_vcf(args.joint)
    joint_by_key = defaultdict(list)
    for j in joint:
        joint_by_key[(j["chrom"], j["svtype"], j["mate_chrom"])].append(j)

    summary_rows = []
    for spec in args.single:
        sample, _, path = spec.partition("=")
        jcol = args.joint_sample_prefix + sample
        if jcol not in joint_samples:
            raise SystemExit(f"{jcol} not in joint VCF columns {joint_samples}")
        _, single = read_vcf(path)
        scol = next(iter(single[0]["samples"])) if single else None

        details = []
        matched_ids = set()
        n_pass = n_pass_found = 0
        n_nonpass = n_nonpass_found = 0
        n_pr_sr_diff = 0
        max_shift = 0
        shifts_outside_cipos = 0

        for rec in single:
            j = find_match(rec, joint_by_key)
            s_fmt = rec["samples"][scol]
            row = {
                "sample": sample, "direction": "single->joint", "chrom": rec["chrom"], "pos_single": rec["pos"],
                "svtype": rec["svtype"], "filter_single": rec["filter"],
                "gt_single": s_fmt.get("GT"), "ft_single": s_fmt.get("FT"), "gq_single": s_fmt.get("GQ"),
                "pr_sr_alt_single": "%d/%d" % alt_support(s_fmt),
            }
            if j:
                matched_ids.add(j["id"])
                jf = j["samples"][jcol]
                shift = abs(j["pos"] - rec["pos"])
                max_shift = max(max_shift, shift)
                inside = j["cipos"][0] <= (rec["pos"] - j["pos"]) <= j["cipos"][1]
                shifts_outside_cipos += 0 if inside else 1
                pr_s, sr_s = alt_support(s_fmt)
                pr_j, sr_j = alt_support(jf)
                if (pr_s, sr_s) != (pr_j, sr_j):
                    n_pr_sr_diff += 1
                row.update({
                    "pos_joint": j["pos"], "shift": shift, "cipos_joint": "%d,%d" % j["cipos"], "shift_inside_cipos": inside,
                    "filter_joint": j["filter"], "gt_joint": jf.get("GT"), "ft_joint": jf.get("FT"), "gq_joint": jf.get("GQ"),
                    "pr_sr_alt_joint": "%d/%d" % (pr_j, sr_j),
                    "outcome": "found",
                })
            else:
                row.update({"outcome": "LOST"})
            if rec["filter"] == "PASS":
                n_pass += 1
                n_pass_found += 1 if j else 0
            else:
                n_nonpass += 1
                n_nonpass_found += 1 if j else 0
            details.append(row)

        # (ii-b) joint-only presences for this sample
        n_joint_present = n_joint_only = 0
        for j in joint:
            jf = j["samples"][jcol]
            if not is_present(jf.get("GT", ".")):
                continue
            n_joint_present += 1
            if j["id"] in matched_ids:
                continue
            n_joint_only += 1
            pr_j, sr_j = alt_support(jf)
            details.append({
                "sample": sample, "direction": "joint-only", "chrom": j["chrom"], "pos_joint": j["pos"],
                "svtype": j["svtype"], "filter_joint": j["filter"], "gt_joint": jf.get("GT"), "ft_joint": jf.get("FT"),
                "gq_joint": jf.get("GQ"), "pr_sr_alt_joint": "%d/%d" % (pr_j, sr_j), "cipos_joint": "%d,%d" % j["cipos"],
                "outcome": "NEW_PRESENCE" if (pr_j + sr_j) > 0 else "NEW_PRESENCE_NO_EVIDENCE",
            })

        fields = ["sample", "direction", "outcome", "chrom", "pos_single", "pos_joint", "shift", "cipos_joint", "shift_inside_cipos",
                  "svtype", "filter_single", "filter_joint", "gt_single", "gt_joint", "ft_single", "ft_joint",
                  "gq_single", "gq_joint", "pr_sr_alt_single", "pr_sr_alt_joint"]
        with open(out / f"details_{sample}.tsv", "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=fields, delimiter="\t", extrasaction="ignore", restval="")
            w.writeheader()
            w.writerows(details)

        summary_rows.append({
            "sample": sample,
            "single_records": len(single),
            "single_PASS": n_pass, "single_PASS_found_in_joint": n_pass_found, "single_PASS_LOST": n_pass - n_pass_found,
            "single_nonPASS": n_nonpass, "single_nonPASS_found_in_joint": n_nonpass_found,
            "joint_present(GT alt)": n_joint_present, "joint_only_presences": n_joint_only,
            "joint_only_with_evidence": sum(1 for d in details if d.get("outcome") == "NEW_PRESENCE"),
            "joint_only_without_evidence": sum(1 for d in details if d.get("outcome") == "NEW_PRESENCE_NO_EVIDENCE"),
            "matched_PR_SR_alt_differs": n_pr_sr_diff,
            "max_breakpoint_shift_bp": max_shift, "shifts_outside_joint_CIPOS": shifts_outside_cipos,
        })

    with open(out / "summary.tsv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(summary_rows[0].keys()), delimiter="\t")
        w.writeheader()
        w.writerows(summary_rows)
    for r in summary_rows:
        print("\t".join(f"{k}={v}" for k, v in r.items()))
    print(f"joint records: {len(joint)}; details in {out}/")


if __name__ == "__main__":
    main()
