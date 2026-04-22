#!/usr/bin/env python3

import os
import re

def get_filename_mapping(fastq_dir):
    """Create comprehensive mapping from incorrect patterns to correct filenames."""
    actual_files = set(os.listdir(fastq_dir))
    mapping = {}
    
    for actual_file in actual_files:
        if actual_file.endswith('.fastq.gz'):
            # Pattern 1: A{X}-F{X}-I{X}-{A|B}_S{X}_L{X}_R{X}_001.fastq.gz
            match1 = re.match(r'A(\d+)-F(\d+)-I(\d+)-([AB])_S(\d+)_L(\d+)_R([12])_001\.fastq\.gz', actual_file)
            if match1:
                ale, flask, isolate, replicate, sample, lane, read = match1.groups()
                
                # Incorrect pattern 1: A{X}-F{X}-I{X}-R_S{X}_L{X}_R{X}_001.fastq.gz
                incorrect1 = f"A{ale}-F{flask}-I{isolate}-R_S{sample}_L{lane}_R{read}_001.fastq.gz"
                mapping[incorrect1] = actual_file
                
                # Incorrect pattern 2: A{X}-F{X}-I{X}_S{X}_L{X}_R{X}_001.fastq.gz (missing -A/-B)
                incorrect2 = f"A{ale}-F{flask}-I{isolate}_S{sample}_L{lane}_R{read}_001.fastq.gz"
                mapping[incorrect2] = actual_file
            
            # Pattern 2: CBS4732-{A|B}_S{X}_L{X}_R{X}_001.fastq.gz
            match2 = re.match(r'CBS4732-([AB])_S(\d+)_L(\d+)_R([12])_001\.fastq\.gz', actual_file)
            if match2:
                replicate, sample, lane, read = match2.groups()
                
                # Incorrect CBS4732 patterns
                incorrect_cbs1 = f"CBS4732-R_S{sample}_L{lane}_R{read}_001.fastq.gz"
                mapping[incorrect_cbs1] = actual_file
                
                incorrect_cbs2 = f"CBS4732_S{sample}_L{lane}_R{read}_001.fastq.gz"
                mapping[incorrect_cbs2] = actual_file
            
            # Pattern 3: DL-1-{A|B}_S{X}_L{X}_R{X}_001.fastq.gz
            match3 = re.match(r'DL-1-([AB])_S(\d+)_L(\d+)_R([12])_001\.fastq\.gz', actual_file)
            if match3:
                replicate, sample, lane, read = match3.groups()
                
                # Incorrect DL-1 patterns
                incorrect_dl1 = f"DL-1-R_S{sample}_L{lane}_R{read}_001.fastq.gz"
                mapping[incorrect_dl1] = actual_file
                
                incorrect_dl2 = f"DL-1_S{sample}_L{lane}_R{read}_001.fastq.gz"
                mapping[incorrect_dl2] = actual_file
            
            # Pattern 4: NCYC495-{A|B}_S{X}_L{X}_R{X}_001.fastq.gz
            match4 = re.match(r'NCYC495-([AB])_S(\d+)_L(\d+)_R([12])_001\.fastq\.gz', actual_file)
            if match4:
                replicate, sample, lane, read = match4.groups()
                
                # Incorrect NCYC495 patterns
                incorrect_ncyc1 = f"NCYC495-R_S{sample}_L{lane}_R{read}_001.fastq.gz"
                mapping[incorrect_ncyc1] = actual_file
                
                incorrect_ncyc2 = f"NCYC495_S{sample}_L{lane}_R{read}_001.fastq.gz"
                mapping[incorrect_ncyc2] = actual_file
    
    return mapping

def fix_csv_filenames(input_file, output_file, fastq_dir):
    """Fix all filename patterns in CSV file."""
    mapping = get_filename_mapping(fastq_dir)
    print(f"Created mapping for {len(mapping)} filename corrections")
    
    # Show some sample mappings
    print("Sample mappings:")
    for i, (incorrect, correct) in enumerate(mapping.items()):
        if 'CBS4732' in incorrect or i < 3:
            print(f"  {incorrect} -> {correct}")
        if i >= 5: break
    
    fixes_made = 0
    
    with open(input_file, 'r') as infile, open(output_file, 'w') as outfile:
        for line_num, line in enumerate(infile, 1):
            original_line = line
            
            # Fix all occurrences of incorrect filenames in this line
            for incorrect, correct in mapping.items():
                if incorrect in line:
                    line = line.replace(incorrect, correct)
                    fixes_made += 1
            
            outfile.write(line)
            
            # Show progress for data lines that were changed
            if line_num >= 38 and line != original_line:
                print(f"Row {line_num}: Fixed filenames")
    
    print(f"\n✅ Made {fixes_made} filename corrections")
    print(f"📁 Fixed file saved to: {output_file}")
    return fixes_made

if __name__ == "__main__":
    input_csv = "/home/azureuser/Docs/ALE_nextflow/data/Yeast_methanol_RWTH/Yeast_Methanol_XPMD.csv"
    output_csv = "/home/azureuser/Docs/ALE_nextflow/data/Yeast_methanol_RWTH/Yeast_Methanol_XPMD_final_fixed.csv"
    fastq_dir = "/home/azureuser/Docs/ALE_nextflow/data/Yeast_methanol_RWTH/sequencing_data/Yeast_methanol_RWTH"
    
    print("🔧 Fixing all filename patterns in XPMD CSV...")
    fixes_made = fix_csv_filenames(input_csv, output_csv, fastq_dir)
    
    if fixes_made > 0:
        print(f"\n🎉 SUCCESS: {fixes_made} filename corrections applied!")
        print(f"📁 Use this file: {output_csv}")
    else:
        print("⚠️  No fixes needed - all filenames were already correct")