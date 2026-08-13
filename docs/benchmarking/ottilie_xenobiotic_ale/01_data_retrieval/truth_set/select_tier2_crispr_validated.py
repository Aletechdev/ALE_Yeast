#!/usr/bin/env python3
"""Select Tier 2 benchmark samples: CRISPR-validated clones (Sup 7→4) + CNV clones (Sup 5).

Rationale
---------
Tier 2 combines two high-confidence subsets from the Ottilie et al. study:

1. **CRISPR-validated SNV/INDEL clones**: 48 mutations across 37 genes were confirmed
   by CRISPR/Cas9 knock-in (Sup 7). This script traces those mutations back to the
   original evolved clones in Sup 4 that carry them (matching gene + amino acid change),
   yielding ~64 clones with sequencing data.

2. **CNV clones** (Sup 5): 24 copy number events (11 aneuploidies + 13 amplifications)
   across 23 clones. These are added so Tier 2 can benchmark CNVKit and Control-FREEC
   in addition to SNV callers. Without them, Tier 2 would have no CNV truth set.

After deduplication (2 CNV clones overlap with CRISPR set), this produces ~85 samples.

Selection criteria
------------------
**CRISPR-validated (Sup 7 → Sup 4):**
1. Parse CRISPR-validated mutations from Sup 7 (gene, amino acid change)
2. Convert Sup 7 single-letter AA codes (e.g. R116K) to Sup 4 three-letter
   codes (e.g. Arg116Lys) for matching
3. Find all Sup 4 clones carrying an exact (gene, AA change) match
4. Cross-reference with sample_name_dictionary.csv for SRR accessions

**CNV (Sup 5):**
5. Add all Sup 5 clones not already selected in step 3
6. Cross-reference with dictionary via clone_name_sup5 or clone_name_sup4

**Output:** tier2_crispr_validated_clones.csv

Why not all Sup 7 clones?
--------------------------
- 53 of 69 Sup 7 EAW IDs are CRISPR-engineered strains, not original sequenced
  clones — they have no SRA data
- 20 of 68 mutations don't match Sup 4, likely from the 23 previously published
  selections in a separate SRA batch (SRX1745463–SRX1869282)

Usage
-----
    cd <repo_root>
    python docs/benchmarking/ottilie_xenobiotic_ale/01_data_retrieval/truth_set/select_tier2_crispr_validated.py

Requires: pandas, openpyxl
"""

import re
import sys
from pathlib import Path

import pandas as pd

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[4]
DATA_DIR = REPO_ROOT / "data" / "ottilie"
SUP_DIR = DATA_DIR / "supplementary"

SUP4_FILE = SUP_DIR / "sup_4_42003_2022_3076_MOESM6_ESM.xlsx"
SUP5_FILE = SUP_DIR / "sup_5_42003_2022_3076_MOESM7_ESM.xlsx"
SUP7_FILE = SUP_DIR / "sup_7_42003_2022_3076_MOESM9_ESM.xlsx"
DICT_FILE = DATA_DIR / "sample_name_dictionary.csv"
OUTPUT_FILE = DATA_DIR / "tier2_crispr_validated_clones.csv"

# Single-letter to three-letter amino acid code mapping
AA_MAP = {
    "A": "Ala", "R": "Arg", "N": "Asn", "D": "Asp", "C": "Cys",
    "E": "Glu", "Q": "Gln", "G": "Gly", "H": "His", "I": "Ile",
    "L": "Leu", "K": "Lys", "M": "Met", "F": "Phe", "P": "Pro",
    "S": "Ser", "T": "Thr", "W": "Trp", "Y": "Tyr", "V": "Val",
    "*": "*",
}


def convert_1to3(aa_1letter: str) -> str | None:
    """Convert single-letter AA change (e.g. R116K) to three-letter (Arg116Lys)."""
    m = re.match(r"([A-Z*])(\d+)([A-Z*])", str(aa_1letter))
    if m:
        return AA_MAP.get(m.group(1), "?") + m.group(2) + AA_MAP.get(m.group(3), "?")
    return None


def select_crispr_clones(df4, df7_file, dict_df):
    """Select Sup 4 clones carrying CRISPR-validated mutations from Sup 7."""
    df7 = pd.read_excel(df7_file, header=1)
    mask = df7[df7.columns[0]].astype(str).str.startswith("EAW")
    df7_valid = df7[mask]
    print(f"Sup 7: {len(df7_valid)} CRISPR-tested entries")

    matched_rows = []
    unmatched_mutations = []

    for _, row in df7_valid.iterrows():
        gene = str(row[df7.columns[1]]).strip()
        aa_1 = str(row[df7.columns[2]]).strip()
        aa_3 = convert_1to3(aa_1)
        if aa_3 is None:
            continue

        sup4_hits = df4[
            (df4["Standard_Name"].astype(str).str.strip() == gene)
            & (df4["aa_short"] == aa_3)
        ]

        if len(sup4_hits) == 0:
            unmatched_mutations.append(f"{gene}({aa_1})")
            continue

        for _, hit in sup4_hits.iterrows():
            matched_rows.append({
                "clone_name": hit["Clone_Name"],
                "eaw_id": hit["EAW_clone"],
                "compound": hit["Compound"],
                "crispr_gene": gene,
                "crispr_aa_1letter": aa_1,
            })

    mdf = pd.DataFrame(matched_rows)
    mut_counts = df4.groupby("Clone_Name").size().to_dict()

    # Build unique clone table with CRISPR mutation annotations
    unique_clones = mdf[["clone_name", "eaw_id", "compound"]].drop_duplicates("clone_name").copy()
    crispr_muts = (
        mdf.groupby("clone_name")
        .apply(lambda g: "; ".join(
            f"{r.crispr_gene}({r.crispr_aa_1letter})" for _, r in g.iterrows()
        ))
        .to_dict()
    )
    unique_clones["total_mutations"] = unique_clones["clone_name"].map(mut_counts)
    unique_clones["crispr_validated_mutations"] = unique_clones["clone_name"].map(crispr_muts)
    unique_clones["selection_reason"] = "crispr_validated"

    # Merge with SRA dictionary
    merged = unique_clones.merge(
        dict_df[["clone_name_sup4", "srr_accession", "spots", "bases", "size_MB"]],
        left_on="clone_name", right_on="clone_name_sup4", how="left",
    )
    merged = merged.drop(columns=["clone_name_sup4"])

    n_matched = len(set(mdf["crispr_gene"] + mdf["crispr_aa_1letter"]))
    print(f"  CRISPR mutations matched in Sup 4: {n_matched}")
    print(f"  CRISPR mutations NOT matched: {len(unmatched_mutations)}")
    print(f"  Unique clones from CRISPR matching: {len(merged)}")

    return merged


def select_cnv_clones(sup5_file, dict_df, existing_srrs):
    """Select Sup 5 CNV clones not already in the CRISPR set."""
    df5 = pd.read_excel(sup5_file, header=1)
    df5.columns = ["Clone_Name", "Chromosome", "Event_Type", "Genes_Involved"]
    print(f"Sup 5: {len(df5)} CNV events across {df5['Clone_Name'].nunique()} clones")

    # Build per-clone CNV summary
    cnv_summary = (
        df5.groupby("Clone_Name")
        .apply(lambda g: "; ".join(
            f"{r.Event_Type.strip()}(chr{r.Chromosome})" for _, r in g.iterrows()
        ))
        .to_dict()
    )

    cnv_rows = []
    for clone_name in df5["Clone_Name"].dropna().unique():
        # Look up in dictionary (try sup5 name first, then sup4)
        match = dict_df[dict_df["clone_name_sup5"] == clone_name]
        if len(match) == 0:
            match = dict_df[dict_df["clone_name_sup4"] == clone_name]

        if len(match) == 0:
            print(f"  WARNING: No SRR for CNV clone {clone_name}")
            continue

        row = match.iloc[0]
        srr = row["srr_accession"]

        # Skip if already in CRISPR set
        if srr in existing_srrs:
            continue

        cnv_rows.append({
            "clone_name": clone_name,
            "eaw_id": row.get("eaw_id", ""),
            "compound": row.get("compound", ""),
            "total_mutations": None,  # may or may not have SNVs in Sup 4
            "crispr_validated_mutations": None,
            "selection_reason": "cnv_truth_set",
            "srr_accession": srr,
            "spots": row["spots"],
            "bases": row["bases"],
            "size_MB": row["size_MB"],
            "cnv_events": cnv_summary.get(clone_name, ""),
        })

    cnv_df = pd.DataFrame(cnv_rows)
    print(f"  CNV-only clones added (not in CRISPR set): {len(cnv_df)}")
    return cnv_df


def main():
    # --- Validate inputs ---
    for f in [SUP4_FILE, SUP5_FILE, SUP7_FILE, DICT_FILE]:
        if not f.exists():
            print(f"ERROR: {f} not found. Run download_truth_set.sh first.", file=sys.stderr)
            sys.exit(1)

    # --- Load shared data ---
    df4 = pd.read_excel(SUP4_FILE, header=1)
    df4.columns = [
        "Clone_Name", "Compound", "EAW_clone", "Chromosome", "Position",
        "Standard_Name", "SGDID", "Systematic_Name", "Essentiality", "Description",
        "GATK_QualScore", "Ref_Base", "Alt_Base", "Type", "Effect", "Impact",
        "Codon_Change", "AA_Change", "Mutation_Status",
    ]
    df4["aa_short"] = (
        df4["AA_Change"].astype(str)
        .str.extract(r"(p\.\w+)", expand=False)
        .str.replace("p.", "", regex=False)
    )
    print(f"Sup 4: {len(df4)} mutations across {df4['Clone_Name'].nunique()} clones")

    dict_df = pd.read_csv(DICT_FILE)

    # --- Step 1: CRISPR-validated clones ---
    crispr_df = select_crispr_clones(df4, SUP7_FILE, dict_df)

    # --- Step 2: CNV clones (Sup 5) not already selected ---
    existing_srrs = set(crispr_df["srr_accession"].dropna())
    cnv_df = select_cnv_clones(SUP5_FILE, dict_df, existing_srrs)

    # --- Combine ---
    # Add cnv_events column to crispr_df (empty for most, but some may have CNVs)
    if "cnv_events" not in crispr_df.columns:
        crispr_df["cnv_events"] = None

    # Check if any CRISPR clones also have CNV events
    df5 = pd.read_excel(SUP5_FILE, header=1)
    df5.columns = ["Clone_Name", "Chromosome", "Event_Type", "Genes_Involved"]
    cnv_summary_all = (
        df5.groupby("Clone_Name")
        .apply(lambda g: "; ".join(
            f"{r.Event_Type.strip()}(chr{r.Chromosome})" for _, r in g.iterrows()
        ))
        .to_dict()
    )
    # Match by SRR since clone names may differ between Sup 4 and Sup 5
    sup5_srrs = {}
    for clone_name in df5["Clone_Name"].dropna().unique():
        match = dict_df[dict_df["clone_name_sup5"] == clone_name]
        if len(match) == 0:
            match = dict_df[dict_df["clone_name_sup4"] == clone_name]
        if len(match) > 0:
            sup5_srrs[match.iloc[0]["srr_accession"]] = cnv_summary_all[clone_name]

    for srr, events in sup5_srrs.items():
        mask = crispr_df["srr_accession"] == srr
        if mask.any():
            crispr_df.loc[mask, "cnv_events"] = events

    combined = pd.concat([crispr_df, cnv_df], ignore_index=True)
    combined = combined.sort_values(["selection_reason", "compound", "clone_name"]).reset_index(drop=True)

    # --- Report ---
    n_crispr = (combined["selection_reason"] == "crispr_validated").sum()
    n_cnv = (combined["selection_reason"] == "cnv_truth_set").sum()
    n_with_srr = combined["srr_accession"].notna().sum()
    n_missing = combined["srr_accession"].isna().sum()
    total_gb = combined["size_MB"].sum() / 1024
    n_with_cnv = combined["cnv_events"].notna().sum()

    print(f"\n{'='*50}")
    print(f"Tier 2 Combined Results:")
    print(f"  CRISPR-validated clones: {n_crispr}")
    print(f"  CNV truth set clones:    {n_cnv}")
    print(f"  Total unique clones:     {len(combined)}")
    print(f"  Clones with CNV events:  {n_with_cnv} (for CNVKit/Control-FREEC benchmarking)")
    print(f"  With SRR accession:      {n_with_srr}")
    print(f"  Missing SRR:             {n_missing}")
    print(f"  Compounds represented:   {combined['compound'].nunique()}")
    print(f"  Estimated download size: {total_gb:.1f} GB")
    print(f"{'='*50}")

    if n_missing > 0:
        missing = combined[combined["srr_accession"].isna()][["clone_name", "eaw_id", "selection_reason"]]
        print(f"\n  Missing SRR clones (exclude from download):")
        for _, r in missing.iterrows():
            print(f"    {r.clone_name} ({r.eaw_id}) [{r.selection_reason}]")

    # --- Save ---
    combined.to_csv(OUTPUT_FILE, index=False)
    print(f"\nSaved: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
