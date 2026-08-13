#!/usr/bin/env python3
"""Validate sample name dictionary: check match completeness across sources.

Reports which SRA samples are missing sup_4 or sup_5 matches, which clones
appear in both supplementary tables, and summarizes naming differences.

Prerequisites:
    First run resolve_sra_accessions.py to generate the dictionary.

Usage:
    python docs/benchmarking/ottilie_xenobiotic_ale/01_data_retrieval/truth_set/validate_dictionary.py
"""

import pandas as pd

DICTIONARY_PATH = "data/ottilie/sample_name_dictionary.csv"


def main():
    d = pd.read_csv(DICTIONARY_PATH)
    print(f"Loaded {DICTIONARY_PATH}: {len(d)} rows\n")

    # --- Rows missing sup_4 ---
    no_sup4 = d[d["clone_name_sup4"].isna()]
    print(f"=== Missing sup_4 match: {len(no_sup4)} rows ===")
    for _, r in no_sup4.iterrows():
        sup5 = r["clone_name_sup5"] if pd.notna(r["clone_name_sup5"]) else "—"
        print(
            f"  {r['srr_accession']}  sra={str(r['library_name_sra']):30s}"
            f"  sup5={str(sup5):20s}  parent={r['is_parent']}  batch={r['sra_batch']}"
        )

    # --- Have sup_4 but no sup_5 ---
    no_sup5_has_sup4 = d[d["clone_name_sup5"].isna() & d["clone_name_sup4"].notna()]
    print(f"\n=== Have sup_4 but NO sup_5: {len(no_sup5_has_sup4)} ===")
    print("  (Expected — sup_5 only lists 23 CNV clones)")

    # --- Both sup_4 and sup_5 matched ---
    both = d[d["clone_name_sup4"].notna() & d["clone_name_sup5"].notna()]
    print(f"\n=== BOTH sup_4 AND sup_5 matched: {len(both)} clones ===")
    n_match = 0
    n_differ = 0
    for _, r in both.iterrows():
        if r["clone_name_sup4"] == r["clone_name_sup5"]:
            tag = "MATCH"
            n_match += 1
        else:
            tag = "DIFFER"
            n_differ += 1
        print(
            f"  {r['srr_accession']}  sup4={str(r['clone_name_sup4']):30s}"
            f"  sup5={str(r['clone_name_sup5']):25s}  [{tag}]"
        )
    print(f"  Names identical: {n_match}, Names differ (spelling only): {n_differ}")

    # --- Summary ---
    neither_parent = len(
        d[d["clone_name_sup4"].isna() & d["clone_name_sup5"].isna() & d["is_parent"]]
    )
    neither_nonparent = len(
        d[d["clone_name_sup4"].isna() & d["clone_name_sup5"].isna() & ~d["is_parent"]]
    )
    print(f"\n=== SUMMARY ===")
    print(f"Total rows:              {len(d)}")
    print(f"  Parents/controls:      {int(d['is_parent'].sum())}")
    print(f"  Matched sup_4:         {d['clone_name_sup4'].notna().sum()}")
    print(f"  Matched sup_5:         {d['clone_name_sup5'].notna().sum()}")
    print(f"  Matched BOTH:          {len(both)}")
    print(f"  Neither (parents):     {neither_parent}")
    print(f"  Neither (non-parent):  {neither_nonparent}")


if __name__ == "__main__":
    main()
