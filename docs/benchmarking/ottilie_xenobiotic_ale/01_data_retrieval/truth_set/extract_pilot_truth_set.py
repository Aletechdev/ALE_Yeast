#!/usr/bin/env python3
"""Extract the published truth set for the 4-sample pilot into one machine-readable CSV.

Ottilie et al. (2022) report every called mutation in Supplementary Data 4 (SNV/INDEL, 1,405 rows,
355 clones) and Data 5 (CNV, 24 events). Both are xlsx, both spell clone names their own way
(`Doxorubicin-16--R2b` vs the SRA/pipeline `Doxorubicin16-R2b`), so anyone benchmarking a pipeline
on the pilot has to parse two workbooks and reconcile names first. This writes the pilot's rows
under the PIPELINE sample names, one event per line, with the Sup 4 spelling kept for traceability.

The parent (NODRUG-GM2) has no rows by definition — every event is called against it.

Prerequisites:
    conda activate nf-env            # openpyxl
    bash download_truth_set.sh       # data/ottilie/supplementary/sup_{4,5}_*.xlsx

Usage (from repo root):
    python docs/benchmarking/ottilie_xenobiotic_ale/01_data_retrieval/truth_set/extract_pilot_truth_set.py
    # → data/ottilie/pilot_truth_set.csv  (shipped in the public bundle by release/publish_test_data.sh)
"""

import csv
import sys
from pathlib import Path

import openpyxl

REPO_ROOT = Path(__file__).resolve().parents[5]
SUP_DIR = REPO_ROOT / "data/ottilie/supplementary"
SUP4 = SUP_DIR / "sup_4_42003_2022_3076_MOESM6_ESM.xlsx"
SUP5 = SUP_DIR / "sup_5_42003_2022_3076_MOESM7_ESM.xlsx"
OUT = REPO_ROOT / "data/ottilie/pilot_truth_set.csv"

# pipeline sample name -> (Sup 4 clone name, Sup 5 clone name, SRA run)
PILOT = {
    "NODRUG-GM2":        (None,                  None,           "SRR10985539"),
    "Doxorubicin16-R2b": ("Doxorubicin-16--R2b", None,           "SRR10985527"),
    "Carmaphycin-R9-2":  ("Carmaphycin--R9-2",   None,           "SRR10985678"),
    "CBR110-15-R3a":     ("CBR110-15R3a",        "CBR110-15R3a", "SRR10985585"),
}

COLUMNS = ["sample", "sra_run", "source", "clone_name_published", "event_type", "chrom", "pos",
           "ref", "alt", "gene", "effect", "aa_change", "status", "genes_in_cnv"]


def rows_with_header(path, first_header_cell):
    ws = openpyxl.load_workbook(path, read_only=True).worksheets[0]
    rows = [r for r in ws.iter_rows(values_only=True) if r and r[0] is not None]
    h = next(i for i, r in enumerate(rows) if r[0] == first_header_cell)
    header = [str(c) for c in rows[h]]
    return [dict(zip(header, r)) for r in rows[h + 1:]]


def main():
    for p in (SUP4, SUP5):
        if not p.exists():
            sys.exit(f"missing {p} — run download_truth_set.sh first")

    by_sup4 = {v[0]: k for k, v in PILOT.items() if v[0]}
    by_sup5 = {v[1]: k for k, v in PILOT.items() if v[1]}
    out = []

    for d in rows_with_header(SUP4, "Clone Name"):
        sample = by_sup4.get(d["Clone Name"])
        if not sample:
            continue
        out.append({
            "sample": sample, "sra_run": PILOT[sample][2], "source": "Sup Data 4",
            "clone_name_published": d["Clone Name"], "event_type": d["Type"],
            "chrom": d["Chromosome"], "pos": d["Mutation Position"],
            "ref": d["Reference Base"], "alt": d["Alternate Base"],
            "gene": d["Standard Name"], "effect": d["Effect"],
            "aa_change": d["Amino Acid Change"] or "", "status": d["Mutation Status"],
            "genes_in_cnv": "",
        })

    for d in rows_with_header(SUP5, "Clone name"):
        sample = by_sup5.get(d["Clone name"])
        if not sample:
            continue
        out.append({
            "sample": sample, "sra_run": PILOT[sample][2], "source": "Sup Data 5",
            "clone_name_published": d["Clone name"], "event_type": "CNV",
            "chrom": d["Chromosome"], "pos": "", "ref": "", "alt": "",
            "gene": "", "effect": d["Event type"], "aa_change": "", "status": "",
            "genes_in_cnv": "" if d["Genes involved in CNV"] in (None, "N/A") else d["Genes involved in CNV"],
        })

    order = list(PILOT)
    out.sort(key=lambda r: (order.index(r["sample"]), r["source"], str(r["chrom"]), int(r["pos"] or 0)))
    with open(OUT, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        w.writerows(out)

    counts = {}
    for r in out:
        counts.setdefault(r["sample"], {}).setdefault(r["event_type"], 0)
        counts[r["sample"]][r["event_type"]] += 1
    print(f"Wrote {OUT} ({len(out)} events)")
    for s in order:
        print(f"  {s:20s} {counts.get(s, {}) or 'parent — no events'}")


if __name__ == "__main__":
    main()
