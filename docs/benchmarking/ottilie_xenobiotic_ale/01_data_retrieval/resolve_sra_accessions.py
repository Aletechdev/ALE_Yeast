#!/usr/bin/env python3
"""Resolve SRA accessions and build a sample name dictionary.

Reconciles naming differences between Supplementary Data 4 (sup_4),
Supplementary Data 5 (sup_5), and SRA RunInfo for BioProject PRJNA590203.

Prerequisites:
    conda activate ottilie-benchmark
    # Download RunInfo (if not already present):
    esearch -db sra -query PRJNA590203 | efetch -format runinfo > data/ottilie/PRJNA590203_runinfo.csv

Usage:
    python bin/benchmarking/ottilie_xenobiotic_ale/resolve_sra_accessions.py

Output:
    data/ottilie/sample_name_dictionary.csv
"""

import os
import re
import pandas as pd

# --- Paths ---
BASE_DIR = "data/ottilie"
SUP_DIR = os.path.join(BASE_DIR, "supplementary")
SUP4_PATH = os.path.join(SUP_DIR, "sup_4_42003_2022_3076_MOESM6_ESM.xlsx")
SUP5_PATH = os.path.join(SUP_DIR, "sup_5_42003_2022_3076_MOESM7_ESM.xlsx")
RUNINFO_PATH = os.path.join(BASE_DIR, "PRJNA590203_runinfo.csv")
OUTPUT_PATH = os.path.join(BASE_DIR, "sample_name_dictionary.csv")

# Manual overrides for names too different for automated normalization.
# Format: sup5 clone name -> SRA LibraryName
MANUAL_SUP5_TO_SRA = {
    "GNF-Pf-1618-7R2b": "GNFpf1618--7R2b",
    "GNF-Pf-2740-15R5a": "GNFpf2740--15-R5a",
    "Tavabarole-9Res2c": "Tav--9Res2c",
}


def normalize_name(name):
    """Normalize clone name for fuzzy matching.

    Handles known discrepancies between sup_4, sup_5, and SRA:
    - Double-dash vs single-dash (sup_4: 'MMV665794--8R9c' vs sup_5: 'MMV665794-8R9c')
    - Spaces instead of dashes (SRA: 'MMV1469689-5 R2a' vs sup_4: 'MMV1469689--5-R2a')
    - Spaces after compound name (SRA: 'Wortmannin -17-R3a')
    - Extra dashes in SRA (SRA: 'CBR110-15-R3a' vs sup_5: 'CBR110-15R3a')
    """
    if pd.isna(name):
        return ""
    s = str(name).strip()
    s = s.lower()
    s = re.sub(r"[_\s]+", "-", s)       # underscores and spaces -> dashes
    s = re.sub(r"-{2,}", "-", s)        # collapse multi-dashes
    # Remove dash/space before R-code: '110-15-r3a' -> '110-15r3a'
    # but preserve compound-level dashes like 'doxorubicin-24r3a'
    s = re.sub(r"(\d)-r(\d)", r"\1r\2", s)        # e.g. -15-R3a -> -15R3a
    s = re.sub(r"(\d)-res(\d)", r"\1res\2", s)     # e.g. -12-Res2a -> -12Res2a
    # Handle decimal points: '0.75b' -> '075b'
    s = s.replace(".", "")
    return s


def load_sup4(path):
    """Load sup_4 with correct header row."""
    df = pd.read_excel(path, header=1)
    # Columns: Clone Name, Compound or Drug Name, EAW clone #, ...
    clones = df[["Clone Name", "Compound or Drug Name", "EAW clone #"]].drop_duplicates(
        subset=["Clone Name"]
    )
    clones = clones.rename(columns={
        "Clone Name": "clone_name_sup4",
        "Compound or Drug Name": "compound",
        "EAW clone #": "eaw_id",
    })
    clones["normalized"] = clones["clone_name_sup4"].apply(normalize_name)
    return clones


def load_sup5(path):
    """Load sup_5 with correct header row."""
    df = pd.read_excel(path, header=1)
    # Columns: Clone name, Chromosome, Event type, Genes involved in CNV
    clones = df[["Clone name"]].drop_duplicates()
    clones = clones.rename(columns={"Clone name": "clone_name_sup5"})
    clones["normalized"] = clones["clone_name_sup5"].apply(normalize_name)
    return clones


def load_runinfo(path):
    """Load SRA RunInfo CSV.

    BioProject PRJNA590203 has two SRA submissions:
    - SRR10985xxx (356 runs): evolved clones + NODRUG--GM2 parent
    - SRR14327xxx (7 runs): additional parent/control strains submitted later
      (4 Green Monster replicates, Erg3 parent, 2 Pleio strains)

    Both batches are included. For the SRR14327xxx batch, LibraryName is a
    short code (GM1, GM2, ...) while SampleName has the descriptive name
    (ParentStrain--GM1, ParentStrain--GM, etc.), so we use SampleName as
    library_name_sra for those to keep naming consistent.
    """
    df = pd.read_csv(path)
    # Filter out empty rows (RunInfo CSVs sometimes have trailing blank lines)
    df = df[df["Run"].notna() & (df["Run"] != "")]

    # Original batch: LibraryName is the descriptive clone name
    batch1 = df[df["Run"].str.startswith("SRR10985")].copy()
    batch1_sra = batch1[["Run", "LibraryName", "SampleName", "spots", "bases", "size_MB"]].copy()
    batch1_sra = batch1_sra.rename(columns={
        "Run": "srr_accession",
        "LibraryName": "library_name_sra",
        "SampleName": "sample_name_sra",
    })

    # Later batch: parent/control strains — use SampleName as the descriptive name
    batch2 = df[df["Run"].str.startswith("SRR14327")].copy()
    batch2_sra = batch2[["Run", "LibraryName", "SampleName", "spots", "bases", "size_MB"]].copy()
    batch2_sra = batch2_sra.rename(columns={
        "Run": "srr_accession",
        "LibraryName": "library_name_sra",
        "SampleName": "sample_name_sra",
    })
    # For batch2, SampleName has format "ParentStrain--GM-0, Green Monster Replicate 4"
    # Extract the identifier (before first comma) as library_name_sra
    # Keep full SampleName in sample_name_sra for reference
    batch2_sra["library_name_sra"] = batch2_sra["sample_name_sra"].str.split(",").str[0].str.strip()

    sra = pd.concat([batch1_sra, batch2_sra], ignore_index=True)
    sra["normalized"] = sra["library_name_sra"].apply(normalize_name)

    # Add batch label for clarity
    sra["sra_batch"] = sra["srr_accession"].apply(
        lambda x: "original" if x.startswith("SRR10985") else "parents"
    )

    return sra


def build_dictionary(sup4, sup5, sra):
    """Build the cross-source sample name dictionary."""
    # Start from SRA as the master list (356 samples incl parent)
    merged = sra.copy()

    # Left-join sup4 on normalized name
    merged = merged.merge(
        sup4[["clone_name_sup4", "compound", "eaw_id", "normalized"]],
        on="normalized",
        how="left",
    )

    # Left-join sup5 on normalized name
    merged = merged.merge(
        sup5[["clone_name_sup5", "normalized"]],
        on="normalized",
        how="left",
    )

    # Apply manual overrides for sup5 names that differ too much for normalization
    for sup5_name, sra_lib_name in MANUAL_SUP5_TO_SRA.items():
        mask = merged["library_name_sra"] == sra_lib_name
        if mask.any():
            merged.loc[mask, "clone_name_sup5"] = sup5_name

    # Flag parent/control clones
    # NODRUG--GM2 is the original parent in the SRR10985xxx batch
    # ParentStrain--* are additional parent/control strains in the SRR14327xxx batch
    # Pleio--1 (SRR14327624) is labeled "Pleio Rep 2" but lacks ParentStrain prefix
    merged["is_parent"] = (
        merged["library_name_sra"].str.contains("NODRUG", case=False, na=False)
        | merged["library_name_sra"].str.contains("ParentStrain", case=False, na=False)
        | (merged["srr_accession"] == "SRR14327624")  # Pleio--1 = Pleio Rep 2
    )

    # Select and order columns
    result = merged[[
        "clone_name_sup4",
        "clone_name_sup5",
        "library_name_sra",
        "sample_name_sra",
        "eaw_id",
        "srr_accession",
        "compound",
        "is_parent",
        "sra_batch",
        "spots",
        "bases",
        "size_MB",
    ]].copy()

    result = result.sort_values("srr_accession").reset_index(drop=True)
    return result


def report_mismatches(dictionary):
    """Report samples with naming differences across sources."""
    print("\n=== NAMING MISMATCHES ===")
    mismatches = dictionary[
        dictionary["clone_name_sup4"].notna()
        & dictionary["clone_name_sup5"].notna()
        & (dictionary["clone_name_sup4"] != dictionary["clone_name_sup5"])
    ]
    if len(mismatches) == 0:
        print("  No samples appear in both sup_4 and sup_5 with different names.")
    else:
        for _, row in mismatches.iterrows():
            print(f"  sup4: {row['clone_name_sup4']}")
            print(f"  sup5: {row['clone_name_sup5']}")
            print(f"  SRA:  {row['library_name_sra']}")
            print()

    # Samples in sup4 but NOT matched in SRA
    sup4_only = dictionary[dictionary["clone_name_sup4"].isna() & ~dictionary["is_parent"]]
    print(f"\n=== SRA samples NOT in sup_4: {len(sup4_only)} ===")
    if len(sup4_only) > 0 and len(sup4_only) <= 10:
        for _, row in sup4_only.iterrows():
            print(f"  SRA: {row['library_name_sra']} ({row['srr_accession']})")

    # Parent/control clones
    parent = dictionary[dictionary["is_parent"]]
    print(f"\n=== PARENT/CONTROL CLONES ({len(parent)} total) ===")
    for _, row in parent.iterrows():
        print(f"  {row['library_name_sra']} ({row['srr_accession']}, {row['sra_batch']})")
        print(f"    SampleName: {row['sample_name_sra']}, Spots: {row['spots']:,}, Size: {row['size_MB']} MB")


def main():
    print("Loading data sources...")
    sup4 = load_sup4(SUP4_PATH)
    print(f"  sup_4: {len(sup4)} unique clones")

    sup5 = load_sup5(SUP5_PATH)
    print(f"  sup_5: {len(sup5)} unique clones")

    sra = load_runinfo(RUNINFO_PATH)
    print(f"  SRA RunInfo: {len(sra)} runs (original batch)")

    print("\nBuilding sample name dictionary...")
    dictionary = build_dictionary(sup4, sup5, sra)

    # Stats
    matched_sup4 = dictionary["clone_name_sup4"].notna().sum()
    matched_sup5 = dictionary["clone_name_sup5"].notna().sum()
    print(f"  Matched to sup_4: {matched_sup4}/{len(sra)} SRA samples")
    print(f"  Matched to sup_5: {matched_sup5}/{len(sra)} SRA samples")

    report_mismatches(dictionary)

    # Save
    dictionary.to_csv(OUTPUT_PATH, index=False)
    print(f"\nSaved: {OUTPUT_PATH}")
    print(f"  Total rows: {len(dictionary)}")


if __name__ == "__main__":
    main()
