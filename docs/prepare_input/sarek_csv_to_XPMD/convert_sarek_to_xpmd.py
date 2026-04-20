#!/usr/bin/env python3
"""
Convert Sarek samplesheet CSV to legacy XPMD format for ALE pipeline.

Usage:
    python convert_sarek_to_xpmd.py <input_sarek.csv> <output_xpmd.csv>

Example:
    python convert_sarek_to_xpmd.py ../../data/data_a_paper/samplesheet_gen2.csv output_xpmd.csv
"""

import csv
import sys
import os
from collections import defaultdict
from pathlib import Path


def parse_sarek_sample_name(sample_name):
    """
    Parse Sarek sample name into A, F, I, R components.

    Example: A1-F6-I1-R1 -> A=1, F=6, I=1, R=1
    """
    parts = sample_name.split('-')
    if len(parts) != 4:
        raise ValueError(f"Invalid sample name format: {sample_name}")

    return {
        'A': parts[0][1:],  # Remove 'A' prefix
        'F': parts[1][1:],  # Remove 'F' prefix
        'I': parts[2][1:],  # Remove 'I' prefix
        'R': parts[3][1:]   # Remove 'R' prefix
    }


def group_lanes_by_sample(sarek_csv_path):
    """
    Read Sarek CSV and group all lanes for each sample.

    Returns a dict: {sample_name: {metadata, lanes: [(R1, R2), ...]}}
    """
    samples = defaultdict(lambda: {'lanes': []})

    with open(sarek_csv_path, 'r') as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            sample_name = row['sample']

            # Store metadata (only once per sample)
            if not samples[sample_name].get('metadata'):
                samples[sample_name]['metadata'] = {
                    'experiment': row['experiment'],
                    'sample': sample_name,
                    'status': row['status'],
                    'clonal_or_population': row['clonal_or_population'],
                    'ploidy': row['ploidy'],
                    'sex': row['sex']
                }

            # Collect lane files
            samples[sample_name]['lanes'].append((row['fastq_1'], row['fastq_2']))

    return samples


def extract_filename(file_path):
    """
    Extract just the filename from a file path.

    Example: '../data/data_a_paper/A1-6_S2_L001_R1_001.fastq.gz' -> 'A1-6_S2_L001_R1_001.fastq.gz'
    """
    return os.path.basename(file_path)


def convert_to_xpmd_format(samples, config):
    """
    Convert grouped samples to XPMD format rows.

    Args:
        samples: Dictionary from group_lanes_by_sample()
        config: Dictionary with project-level metadata

    Returns:
        List of dictionaries for XPMD CSV
    """
    xpmd_rows = []

    for sample_name, data in sorted(samples.items()):
        metadata = data['metadata']
        lanes = data['lanes']

        # Parse A-F-I-R from sample name
        afir = parse_sarek_sample_name(sample_name)

        # Determine experiment/subproject from sample name
        # For ancestral strains (A0), use starting strain name
        if afir['A'] == '0':
            experiment_subproject = config['starting_strain']
        else:
            experiment_subproject = config['starting_strain']

        # Group all lanes into filename, filename2, and additional read files
        # Extract only filenames (remove paths)
        if len(lanes) == 0:
            continue
        elif len(lanes) == 1:
            filename_r1 = extract_filename(lanes[0][0])
            filename_r2 = extract_filename(lanes[0][1])
            additional_files = ""
        else:
            # First lane in filename/filename2
            filename_r1 = extract_filename(lanes[0][0])
            filename_r2 = extract_filename(lanes[0][1])

            # Remaining lanes in additional read files (comma-separated)
            additional_r1r2 = []
            for r1, r2 in lanes[1:]:
                additional_r1r2.extend([extract_filename(r1), extract_filename(r2)])
            additional_files = ','.join(additional_r1r2)

        # Create XPMD row
        xpmd_row = {
            'project': config['project'],
            'project description': config.get('project_description', ''),
            'experiment/subproject': experiment_subproject,
            'A': afir['A'],
            'F': afir['F'],
            'I': afir['I'],
            'R': afir['R'],
            'experiment details': config.get('experiment_details', ''),
            'sample type': metadata['clonal_or_population'],
            'filename': filename_r1,
            'filename2': filename_r2,
            'additional read files': additional_files,
            'indexfile': '',
            'indexfile2': '',
            'additional index files': '',
            'starting strain': config['starting_strain'],
            'reference file name(s)': config['reference_file_name'],
            'reference file url(s)': config.get('reference_url', 'other'),
            'medium derived from': config.get('medium_base', ''),
            'medium modifications': config.get('medium_modifications', 'N/A'),
            'carbon source': config.get('carbon_source', 'N/A'),
            'medium description': config.get('medium_description', ''),
            'environmental condition modifications': config.get('env_conditions', 'N/A'),
            'taxonomy id': config.get('taxonomy_id', ''),
            'ploidy': metadata['ploidy'],
            'accession': config.get('accession', ''),
            'ALE module': config.get('ale_module', ''),
            'owner': config.get('owner', ''),
            'owner email': config.get('owner_email', ''),
            'pre culture details': config.get('preculture_details', ''),
            'cultivation details': config.get('cultivation_details', ''),
            'sequencing library prep kit manufacturer': config.get('seq_kit_manufacturer', ''),
            'sequencing library prep kit': config.get('seq_kit', ''),
            'sequencing library prep kit cycles': config.get('seq_kit_cycles', ''),
            'sequencing library layout': config.get('seq_layout', ''),
            'read length': config.get('read_length', '')
        }

        xpmd_rows.append(xpmd_row)

    return xpmd_rows


def write_xpmd_csv(xpmd_rows, output_path, include_header_comments=True):
    """
    Write XPMD format CSV with optional header comments.

    Args:
        xpmd_rows: List of dictionaries with XPMD data
        output_path: Output CSV file path
        include_header_comments: If True, include lines 2-37 as comments
    """
    # XPMD column order
    columns = [
        'project', 'project description', 'experiment/subproject',
        'A', 'F', 'I', 'R', 'experiment details', 'sample type',
        'filename', 'filename2', 'additional read files',
        'indexfile', 'indexfile2', 'additional index files',
        'starting strain', 'reference file name(s)', 'reference file url(s)',
        'medium derived from', 'medium modifications', 'carbon source',
        'medium description', 'environmental condition modifications',
        'taxonomy id', 'ploidy', 'accession', 'ALE module',
        'owner', 'owner email', 'pre culture details', 'cultivation details',
        'sequencing library prep kit manufacturer', 'sequencing library prep kit',
        'sequencing library prep kit cycles', 'sequencing library layout', 'read length'
    ]

    with open(output_path, 'w', newline='') as fh:
        writer = csv.DictWriter(fh, fieldnames=columns)

        # Write header
        writer.writeheader()

        # Optionally skip comment rows (lines 2-37) as requested
        # User said to ignore lines 2-37 which are comments

        # Write data rows
        for row in xpmd_rows:
            writer.writerow(row)

    print(f"✅ Successfully wrote {len(xpmd_rows)} samples to {output_path}")


def main():
    # Configuration for this project
    config = {
        'project': 'ZL_dev_Tolerance to Dicarboxylic acids in S cerevisiae',
        'project_description': 'Adaptive laboratory evolution for tolerance to dicarboxylic acids',
        'starting_strain': 'CENPK113-7D',
        'reference_file_name': 'Saccharomyces_cerevisiae_S288C.gbk',
        'reference_url': 'https://www.ncbi.nlm.nih.gov/assembly/GCF_000146045.2/',
        'medium_base': 'YPD',
        'medium_modifications': 'N/A',
        'carbon_source': 'glucose(20 g/L)',
        'medium_description': '',
        'env_conditions': 'temp:30\naerobic:true',
        'taxonomy_id': '4932',  # S. cerevisiae
        'accession': 'GCF_000146045.2',
        'ale_module': 'ALE',
        'owner': 'Your Name',  # Update this
        'owner_email': 'your.email@example.com',  # Update this
        'preculture_details': '',
        'cultivation_details': '',
        'seq_kit_manufacturer': '',
        'seq_kit': '',
        'seq_kit_cycles': '',
        'seq_layout': 'paired-end',
        'read_length': '150'
    }

    # Parse command line arguments
    if len(sys.argv) < 3:
        print("Usage: python convert_sarek_to_xpmd.py <input_sarek.csv> <output_xpmd.csv>")
        print("\nExample:")
        print("  python convert_sarek_to_xpmd.py ../../data/data_a_paper/samplesheet_gen2.csv output_xpmd.csv")
        sys.exit(1)

    input_csv = sys.argv[1]
    output_csv = sys.argv[2]

    # Verify input file exists
    if not os.path.exists(input_csv):
        print(f"❌ Error: Input file not found: {input_csv}")
        sys.exit(1)

    print(f"Converting Sarek CSV to XPMD format...")
    print(f"  Input:  {input_csv}")
    print(f"  Output: {output_csv}")
    print(f"  Project: {config['project']}")
    print()

    # Process
    samples = group_lanes_by_sample(input_csv)
    print(f"✅ Grouped {len(samples)} unique samples")

    xpmd_rows = convert_to_xpmd_format(samples, config)
    print(f"✅ Converted to {len(xpmd_rows)} XPMD rows")

    write_xpmd_csv(xpmd_rows, output_csv, include_header_comments=False)

    print(f"\n{'='*60}")
    print(f"Conversion complete!")
    print(f"Output file: {output_csv}")
    print(f"{'='*60}")


if __name__ == '__main__':
    main()
