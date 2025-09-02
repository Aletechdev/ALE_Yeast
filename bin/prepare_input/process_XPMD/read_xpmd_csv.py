#!/usr/bin/env python3

import pandas as pd
import sys
import os
import re

def expand_read_files(df):
    """
    Expand rows with multiple read files (lanes) into individual rows.
    
    Args:
        df (pd.DataFrame): Original dataframe
        
    Returns:
        pd.DataFrame: Expanded dataframe with individual lanes
    """
    expanded_rows = []
    
    for idx, row in df.iterrows():
        # Get the base read files
        filename = row['filename'] if pd.notna(row['filename']) else ''
        filename2 = row['filename2'] if pd.notna(row['filename2']) else ''
        additional_files = row['additional read files'] if pd.notna(row['additional read files']) else ''
        
        # Extract lane information and create individual rows
        if additional_files:
            # Split additional files by comma
            additional_list = [f.strip() for f in additional_files.split(',')]
            
            # Extract lane information from filenames
            all_files = [filename, filename2] + additional_list
            lanes = set()
            
            for file in all_files:
                if file:
                    # Extract both sample index and lane: S{X}_L{X}
                    lane_match = re.search(r'_S(\d+)_L(\d{3})_R', file)
                    if lane_match:
                        sample_idx = lane_match.group(1)
                        lane_num = lane_match.group(2)
                        lanes.add(f"S{sample_idx}_L{lane_num}")
            
            # If no lanes found, create a single entry
            if not lanes:
                new_row = row.copy()
                new_row['lane'] = 'L001'
                new_row['fastq_1'] = filename
                new_row['fastq_2'] = filename2
                expanded_rows.append(new_row)
            else:
                # Create a row for each lane
                for lane in sorted(lanes):
                    new_row = row.copy()
                    new_row['lane'] = lane  # Already in format "S{X}_L{X}"
                    
                    # Find R1 and R2 files for this lane
                    r1_file = ''
                    r2_file = ''
                    
                    # Extract just the lane part for matching (e.g., "L001" from "S27_L001")
                    lane_part = lane.split('_L')[1]  # Get "001" from "S27_L001"
                    
                    for file in all_files:
                        if file and f'_L{lane_part}_' in file and f'_{lane.split("_")[0]}_' in file:
                            if '_R1_' in file:
                                r1_file = file
                            elif '_R2_' in file:
                                r2_file = file
                    
                    new_row['fastq_1'] = r1_file
                    new_row['fastq_2'] = r2_file
                    expanded_rows.append(new_row)
        else:
            # Single lane case
            new_row = row.copy()
            if filename:
                lane_match = re.search(r'_S(\d+)_L(\d{3})_R', filename)
                if lane_match:
                    sample_idx = lane_match.group(1)
                    lane_num = lane_match.group(2)
                    new_row['lane'] = f"S{sample_idx}_L{lane_num}"
                else:
                    new_row['lane'] = 'S1_L001'  # Default
            else:
                new_row['lane'] = 'S1_L001'  # Default
            new_row['fastq_1'] = filename
            new_row['fastq_2'] = filename2
            expanded_rows.append(new_row)
    
    expanded_df = pd.DataFrame(expanded_rows)
    return expanded_df

def read_xpmd_csv(csv_path):
    """
    Read and process the XPMD CSV file from yeast methanol experiment.
    
    Args:
        csv_path (str): Path to the CSV file
        
    Returns:
        pd.DataFrame: Processed dataframe
    """
    try:
        # Read the CSV file
        # Read CSV, using first row as header and skipping the second row (comment/help text)
        df = pd.read_csv(csv_path, header=0, skiprows=[1])
        
        # Data validation: Check for required columns with no empty values
        required_columns = [
            'project', 'experiment/subproject', 'ploidy', 'A', 'F', 'I', 'R',
            'sample type', 'filename', 'reference file name(s)'
        ]
        
        print(f"\nValidating required columns...")
        validation_passed = True
        
        for col in required_columns:
            if col not in df.columns:
                print(f"❌ Missing column: '{col}'")
                validation_passed = False
            else:
                empty_count = df[col].isna().sum() + (df[col] == '').sum()
                if empty_count > 0:
                    print(f"⚠️  Column '{col}' has {empty_count} empty values")
                    empty_rows = df[df[col].isna() | (df[col] == '')].index.tolist()
                    print(f"    Empty in rows: {empty_rows}")
                    validation_passed = False
                else:
                    print(f"✓ Column '{col}' - all values populated")
        
        if not validation_passed:
            print(f"\n❌ Data validation FAILED - please fix empty values before proceeding")
            return None
        else:
            print(f"\n✅ Data validation PASSED - all required columns populated")
        
        # Display basic info about the dataset
        print(f"Dataset shape: {df.shape}")
        print(f"Columns: {list(df.columns)}")
        print(f"\nFirst few rows:")
        print(df.head())
        
        # Group by experiment/subproject
        print(f"\nGrouping by 'experiment/subproject':")
        grouped = df.groupby('experiment/subproject')
        
        for name, group in grouped:
            print(f"\n--- {name} ---")
            print(f"Number of samples: {len(group)}")
            print(group[['A', 'F', 'I', 'R', 'sample type', 'filename', 'filename2']].head())
            
            # Data checkpoint: Check reference file consistency within each group
            ref_files = group['reference file name(s)'].dropna().unique()
            if len(ref_files) > 1:
                print(f"⚠️  WARNING: Multiple reference files found in group '{name}':")
                for ref in ref_files:
                    print(f"    - {ref}")
            elif len(ref_files) == 1:
                print(f"✓ Reference file: {ref_files[0]}")
            else:
                print(f"⚠️  WARNING: No reference file specified for group '{name}'")
        
        # Split pairs into individual rows with lane information
        print(f"\nExpanding read files by lanes...")
        expanded_df = expand_read_files(df)
        print(f"Expanded to {len(expanded_df)} rows with individual lanes")
        print(f"\nExpanded dataframe columns: {list(expanded_df.columns)}")
        print(f"\nSample of expanded data:")
        print(expanded_df[['experiment/subproject', 'A', 'F', 'I', 'R', 'lane', 'fastq_1', 'fastq_2']].head(10))
        
        return df, grouped, expanded_df
        
    except FileNotFoundError:
        print(f"Error: File not found at {csv_path}")
        return None
    except Exception as e:
        print(f"Error reading CSV: {e}")
        return None


def format_for_sarek(selected_sample_df, fastq_path, sex="XX"):
    """
    Format the selected sample dataframe to match Sarek samplesheet format.
    
    Args:
        selected_sample_df (pd.DataFrame): Selected samples from XPMD data
        fastq_path (str): Base path for fastq files
        sex (str): Sex chromosome designation (default: "XX")
        
    Returns:
        pd.DataFrame: Formatted dataframe matching samplesheet.csv structure
    """
    # Expand selected samples to include lanes
    selected_expanded_df = expand_read_files(selected_sample_df)
    
    # Create formatted dataframe matching samplesheet.csv structure
    formatted_df = pd.DataFrame()
    
    # 1. Change column "experiment/subproject" to "experiment"
    formatted_df['experiment'] = selected_expanded_df['experiment/subproject']
    
    # 2. Concatenate A-F-I-R columns by "-" to format the sample name
    formatted_df['sample'] = (
        'A' + selected_expanded_df['A'].astype(str) + '-' +
        'F' + selected_expanded_df['F'].astype(str) + '-' +
        'I' + selected_expanded_df['I'].astype(str) + '-' +
        'R' + selected_expanded_df['R'].astype(str)
    )
    
    # 3. Set status: A0-F0-I1-R1 = 0 (control), others = 1 (treated)
    formatted_df['status'] = selected_expanded_df.apply(
        lambda row: 0 if (row['A'] == 0 and row['F'] == 0 and row['I'] == 1 and row['R'] == 1) else 1,
        axis=1
    )
    
    # Add other required columns
    formatted_df['clonal_or_population'] = 'clonal'  # From sample type or default
    formatted_df['ploidy'] = selected_expanded_df['ploidy']
    formatted_df['sex'] = sex
    formatted_df['lane'] = selected_expanded_df['lane']
    
    # 4. Add fastq_path to fastq_1 and fastq_2 columns
    formatted_df['fastq_1'] = selected_expanded_df['fastq_1'].apply(
        lambda x: os.path.join(fastq_path, x) if pd.notna(x) and x != '' else x
    )
    formatted_df['fastq_2'] = selected_expanded_df['fastq_2'].apply(
        lambda x: os.path.join(fastq_path, x) if pd.notna(x) and x != '' else x
    )
    
    return formatted_df


def main():
    # Path to the test CSV file
    csv_path = "test/Yeast_Methanol_XPMD_final_fixed.csv"
    #TODO: change the path to the relative path of the nextflow run, or change it to a Azure path??
    fastq_path = "/home/azureuser/Docs/ALE_nextflow/data/Yeast_methanol_RWTH/sequencing_data/Yeast_methanol_RWTH"
    sex = "XX"
    print("Reading XPMD CSV file...")
    result = read_xpmd_csv(csv_path)
    
    if result is not None:
        df, grouped, expanded_df = result
        print("\nCSV file read, grouped, and expanded successfully!")
    else:
        print("Failed to read CSV file.")
        sys.exit(1)
    ####
    # for quick test, run with two samples from project NCYC495:
    # the control A=0 F=0 I=1 R=1
    # one treated A=10 F=47 I=2 R=1
    selected_sample_df = df[(df['experiment/subproject'] == 'NCYC495') & (df['A'].isin([0, 10])) & (df['F'].isin([0, 47])) & (df['I'].isin([1, 2])) & (df['R'].isin([1]))]
    print(selected_sample_df)

    # format the table to be ready for sarek input:
    formatted_df = format_for_sarek(selected_sample_df, fastq_path, sex)
    
    print("\nFormatted samplesheet for Sarek:")
    print(formatted_df)
    
    # Save to CSV file
    output_path = "/home/azureuser/Docs/ALE_nextflow/data/Yeast_methanol_RWTH/Ogataea_polymorpha_NCYC495/sarek_samplesheet.csv"
    formatted_df.to_csv(output_path, index=False)
    print(f"\nSamplesheet saved to: {output_path}")

if __name__ == "__main__":
    main()