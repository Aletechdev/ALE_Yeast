#!/usr/bin/env python3
"""
Parse breseq summary.json and output.gd to produce a MultiQC custom content TSV.

Usage:
    breseq_mqc_summary.py --summary summary.json --gd output.gd --sample SAMPLE_ID
"""

import argparse
import json
import sys


def parse_summary_json(path):
    """Extract read and coverage stats from breseq summary.json."""
    with open(path) as f:
        data = json.load(f)

    reads = data.get("reads", {})
    total_reads = reads.get("total_reads", 0)
    total_aligned = reads.get("total_aligned_reads", 0)
    alignment_rate = reads.get("total_fraction_aligned_reads", 0) * 100

    refs = data.get("references", {}).get("reference", {})
    total_length = data.get("references", {}).get("total_length", 0)

    # Weighted average coverage across chromosomes
    if total_length > 0 and refs:
        weighted_cov = sum(
            r.get("coverage_average", 0) * r.get("length", 0)
            for r in refs.values()
        )
        avg_coverage = weighted_cov / total_length
    else:
        avg_coverage = 0.0

    return {
        "total_reads": total_reads,
        "aligned_reads": total_aligned,
        "alignment_rate": round(alignment_rate, 1),
        "avg_coverage": round(avg_coverage, 2),
    }


def parse_gd(path):
    """Count mutation and evidence types from a GenomeDiff (.gd) file."""
    mutation_types = {"SNP": 0, "DEL": 0, "INS": 0, "SUB": 0, "MOB": 0, "AMP": 0, "CON": 0, "INV": 0}
    evidence_types = {"RA": 0, "MC": 0, "JC": 0, "UN": 0}

    with open(path) as f:
        for line in f:
            if line.startswith("#"):
                continue
            token = line.split("\t", 1)[0]
            if token in mutation_types:
                mutation_types[token] += 1
            elif token in evidence_types:
                evidence_types[token] += 1

    total_mutations = sum(mutation_types.values())
    other_mutations = mutation_types["MOB"] + mutation_types["AMP"] + mutation_types["CON"] + mutation_types["INV"]

    return {
        "mutations_total": total_mutations,
        "mutations_snp": mutation_types["SNP"],
        "mutations_del": mutation_types["DEL"],
        "mutations_ins": mutation_types["INS"],
        "mutations_sub": mutation_types["SUB"],
        "mutations_other": other_mutations,
        "evidence_ra": evidence_types["RA"],
        "evidence_mc": evidence_types["MC"],
        "evidence_jc": evidence_types["JC"],
        "unassigned": evidence_types["UN"],
    }


MQC_HEADER = """\
# id: 'breseq'
# section_name: 'breseq'
# description: 'breseq variant calling and alignment summary'
# plot_type: 'table'
# pconfig:
#     namespace: 'breseq'
# headers:
#     total_reads:
#         title: 'Total Reads'
#         format: '{:,.0f}'
#     aligned_reads:
#         title: 'Aligned Reads'
#         format: '{:,.0f}'
#     alignment_rate:
#         title: 'Align %'
#         format: '{:.1f}'
#         suffix: '%'
#         min: 0
#         max: 100
#     avg_coverage:
#         title: 'Avg Cov'
#         format: '{:.1f}'
#     mutations_total:
#         title: 'Mutations'
#         format: '{:,.0f}'
#     mutations_snp:
#         title: 'SNPs'
#         format: '{:,.0f}'
#     mutations_del:
#         title: 'DELs'
#         format: '{:,.0f}'
#     mutations_ins:
#         title: 'INSs'
#         format: '{:,.0f}'
#     mutations_sub:
#         title: 'SUBs'
#         format: '{:,.0f}'
#     mutations_other:
#         title: 'Other (MOB/AMP/CON/INV)'
#         format: '{:,.0f}'
#     evidence_ra:
#         title: 'RA Evidence'
#         format: '{:,.0f}'
#         hidden: true
#     evidence_mc:
#         title: 'MC Evidence'
#         format: '{:,.0f}'
#         hidden: true
#     evidence_jc:
#         title: 'JC Evidence'
#         format: '{:,.0f}'
#         hidden: true
#     unassigned:
#         title: 'Unassigned'
#         format: '{:,.0f}'
#         hidden: true"""

COLUMNS = [
    "total_reads", "aligned_reads", "alignment_rate", "avg_coverage",
    "mutations_total", "mutations_snp", "mutations_del", "mutations_ins",
    "mutations_sub", "mutations_other",
    "evidence_ra", "evidence_mc", "evidence_jc", "unassigned",
]


def main():
    parser = argparse.ArgumentParser(description="Generate breseq MultiQC custom content TSV")
    parser.add_argument("--summary", required=True, help="Path to breseq summary.json")
    parser.add_argument("--gd", required=True, help="Path to breseq output.gd")
    parser.add_argument("--sample", required=True, help="Sample ID")
    args = parser.parse_args()

    stats = parse_summary_json(args.summary)
    stats.update(parse_gd(args.gd))

    output_file = f"{args.sample}.breseq_mqc.tsv"
    with open(output_file, "w") as f:
        f.write(MQC_HEADER + "\n")
        f.write("Sample\t" + "\t".join(COLUMNS) + "\n")
        values = [str(stats[col]) for col in COLUMNS]
        f.write(args.sample + "\t" + "\t".join(values) + "\n")

    print(f"Written: {output_file}", file=sys.stderr)


if __name__ == "__main__":
    main()
