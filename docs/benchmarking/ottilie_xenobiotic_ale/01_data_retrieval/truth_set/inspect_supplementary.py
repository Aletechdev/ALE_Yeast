#!/usr/bin/env python3
"""Inspect Ottilie et al. supplementary data files (sup_4 and sup_5).

Downloads files if not already present, then prints column structure,
sample counts, and Stage A pilot clone details.

Usage:
    conda activate ottilie-benchmark
    python docs/benchmarking/ottilie_xenobiotic_ale/01_data_retrieval/truth_set/inspect_supplementary.py
"""

import os
import subprocess
import pandas as pd

DATA_DIR = "data/ottilie/supplementary"

FILES = {
    "sup_4": {
        "filename": "sup_4_42003_2022_3076_MOESM6_ESM.xlsx",
        "url": "https://static-content.springer.com/esm/art%3A10.1038%2Fs42003-022-03076-7/MediaObjects/42003_2022_3076_MOESM6_ESM.xlsx",
        "description": "Supplementary Data 4: Full mutation list (SNVs + INDELs)",
    },
    "sup_5": {
        "filename": "sup_5_42003_2022_3076_MOESM7_ESM.xlsx",
        "url": "https://static-content.springer.com/esm/art%3A10.1038%2Fs42003-022-03076-7/MediaObjects/42003_2022_3076_MOESM7_ESM.xlsx",
        "description": "Supplementary Data 5: Copy number variants",
    },
}

# Stage A pilot clones (from project plan)
PILOT_SNV_CLONES = [
    "Doxorubicin-16--R2b",  # EAW304, 23 mutations
    "Carmaphycin--R9-2",     # EAW131, 15 mutations
    "MMV000442--17-R5a",     # EAW221, 15 mutations
]
PILOT_CNV_CLONES = [
    "CBR110-15R3a",          # EAW744, aneuploidy ChrI
]


def download_if_missing(key):
    """Download supplementary file if not already present."""
    info = FILES[key]
    path = os.path.join(DATA_DIR, info["filename"])
    if os.path.exists(path):
        print(f"  [exists] {path}")
        return path
    os.makedirs(DATA_DIR, exist_ok=True)
    print(f"  [downloading] {info['description']}...")
    subprocess.run(
        ["curl", "-L", "-o", path, info["url"]],
        check=True,
    )
    return path


def inspect_sup4(path):
    """Inspect Supplementary Data 4 (mutations)."""
    print("\n" + "=" * 70)
    print("SUPPLEMENTARY DATA 4: Mutation List")
    print("=" * 70)

    # Read all sheets to see structure
    xls = pd.ExcelFile(path)
    print(f"\nSheets: {xls.sheet_names}")

    for sheet in xls.sheet_names:
        df = pd.read_excel(path, sheet_name=sheet)
        print(f"\n--- Sheet: '{sheet}' ---")
        print(f"  Shape: {df.shape}")
        print(f"  Columns: {list(df.columns)}")
        print(f"\n  First 3 rows:")
        print(df.head(3).to_string(index=False))

        # Look for clone/sample name columns
        for col in df.columns:
            col_lower = str(col).lower()
            if any(kw in col_lower for kw in ["clone", "sample", "name", "eaw", "strain"]):
                unique_vals = df[col].dropna().unique()
                print(f"\n  Column '{col}': {len(unique_vals)} unique values")
                if len(unique_vals) <= 10:
                    print(f"    Values: {list(unique_vals)}")
                else:
                    print(f"    First 5: {list(unique_vals[:5])}")
                    print(f"    Last 5: {list(unique_vals[-5:])}")

        # Check for pilot clones
        print("\n  Pilot SNV clone search:")
        for clone in PILOT_SNV_CLONES:
            for col in df.columns:
                matches = df[df[col].astype(str).str.contains(clone.replace("--", "[-]+"), regex=True, na=False)]
                if len(matches) > 0:
                    print(f"    '{clone}' found in column '{col}': {len(matches)} rows")
                    break
            else:
                print(f"    '{clone}' NOT FOUND in any column")

    return df


def inspect_sup5(path):
    """Inspect Supplementary Data 5 (CNVs)."""
    print("\n" + "=" * 70)
    print("SUPPLEMENTARY DATA 5: Copy Number Variants")
    print("=" * 70)

    xls = pd.ExcelFile(path)
    print(f"\nSheets: {xls.sheet_names}")

    for sheet in xls.sheet_names:
        df = pd.read_excel(path, sheet_name=sheet)
        print(f"\n--- Sheet: '{sheet}' ---")
        print(f"  Shape: {df.shape}")
        print(f"  Columns: {list(df.columns)}")
        print(f"\n  All rows:")
        print(df.to_string(index=False))

        # Check for pilot CNV clones
        print("\n  Pilot CNV clone search:")
        for clone in PILOT_CNV_CLONES:
            for col in df.columns:
                matches = df[df[col].astype(str).str.contains(clone.replace("-", "[-]+"), regex=True, na=False)]
                if len(matches) > 0:
                    print(f"    '{clone}' found in column '{col}': {len(matches)} rows")
                    break
            else:
                print(f"    '{clone}' NOT FOUND in any column")

    return df


def main():
    print("Downloading supplementary files (if needed)...")
    sup4_path = download_if_missing("sup_4")
    sup5_path = download_if_missing("sup_5")

    inspect_sup4(sup4_path)
    inspect_sup5(sup5_path)

    print("\n" + "=" * 70)
    print("DONE — Review output above to confirm column names and clone naming conventions.")
    print("=" * 70)


if __name__ == "__main__":
    main()
