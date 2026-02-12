#!/usr/bin/env python3
"""
Cross-reference AMP Mutations CSV with Breseq annotated .gd file for sample A1-F6-I2-R1.
Adds rich annotation from .gd file (gene names, mutation categories, amino acid changes, etc.)
to the CSV mutations.
"""
import csv
import re
from collections import defaultdict

# File paths
CSV_FILE = 'data/Mutations_Dev_Yeast_Adipic_Acid.csv'
GD_FILE = 'data/A1-F6-I2-R1_annotated.gd'
RAW_GD_FILE = 'data/A1-F6-I2-R1-bareseq-output.gd'  # Raw .gd with RA evidence
SAMPLE_COL = 9  # 0-indexed column for A1-F6-I2-R1
OUTPUT_TSV = 'output/A1-F6-I2-R1_AMP_mutations_with_gd_annotation.tsv'

def load_ra_evidence(gd_file):
    """Load RA (Read Alignment) evidence entries with coverage info."""
    ra_data = {}
    with open(gd_file, 'r') as f:
        for line in f:
            if line.startswith('RA'):
                parts = line.strip().split('\t')
                ra_id = parts[1]  # RA evidence ID

                # Parse key-value annotations
                annotations = {}
                for part in parts:
                    if '=' in part:
                        key, val = part.split('=', 1)
                        annotations[key] = val

                # Parse coverage fields (format: forward/reverse)
                total_cov = annotations.get('total_cov', '0/0')
                ref_cov = annotations.get('ref_cov', '0/0')
                new_cov = annotations.get('new_cov', '0/0')

                # Calculate totals
                total_fwd, total_rev = map(int, total_cov.split('/'))
                ref_fwd, ref_rev = map(int, ref_cov.split('/'))
                new_fwd, new_rev = map(int, new_cov.split('/'))

                ra_data[ra_id] = {
                    'total_cov': total_cov,
                    'total_cov_sum': total_fwd + total_rev,
                    'total_fwd': total_fwd,
                    'total_rev': total_rev,
                    'ref_cov': ref_cov,
                    'ref_cov_sum': ref_fwd + ref_rev,
                    'new_cov': new_cov,
                    'new_cov_sum': new_fwd + new_rev,
                    'major_cov': annotations.get('major_cov', ''),
                    'minor_cov': annotations.get('minor_cov', ''),
                }
    return ra_data

def load_gd_file(gd_file):
    """Load mutations from annotated Breseq .gd file with all annotations."""
    mutations = {}
    with open(gd_file, 'r') as f:
        for line in f:
            if line.startswith(('SNP', 'DEL', 'INS')):
                parts = line.strip().split('\t')
                mut_type = parts[0]
                mut_id = parts[1]      # Mutation ID (2nd column)
                evidence_id = parts[2]  # Evidence ID (3rd column, usually ".")
                chrom = parts[3]
                pos = int(parts[4])
                new_seq = parts[5]      # New base (SNP) or size (DEL/INS)

                # Parse key-value annotations
                annotations = {}
                for part in parts:
                    if '=' in part:
                        key, val = part.split('=', 1)
                        annotations[key] = val

                # Store by (chrom, pos) as key
                key = (chrom, pos)
                mutations[key] = {
                    'mut_id': mut_id,
                    'evidence_id': evidence_id,
                    'type': mut_type,
                    'chrom': chrom,
                    'pos': pos,
                    'new_seq': new_seq,
                    'frequency': float(annotations.get('frequency', 0)),
                    'gene_name': annotations.get('gene_name', ''),
                    'gene_position': annotations.get('gene_position', ''),
                    'gene_product': annotations.get('gene_product', ''),
                    'mutation_category': annotations.get('mutation_category', ''),
                    'snp_type': annotations.get('snp_type', ''),
                    'aa_ref_seq': annotations.get('aa_ref_seq', ''),
                    'aa_new_seq': annotations.get('aa_new_seq', ''),
                    'aa_position': annotations.get('aa_position', ''),
                    'codon_ref_seq': annotations.get('codon_ref_seq', ''),
                    'codon_new_seq': annotations.get('codon_new_seq', ''),
                    'ref_seq': annotations.get('ref_seq', ''),
                    'locus_tag': annotations.get('locus_tag', ''),
                }
    return mutations

def load_raw_gd_mutations(gd_file):
    """Load mutations from raw .gd file to get evidence_id linkage."""
    mutations = {}
    with open(gd_file, 'r') as f:
        for line in f:
            if line.startswith(('SNP', 'DEL', 'INS')):
                parts = line.strip().split('\t')
                mut_id = parts[1]
                evidence_id = parts[2]  # Links to RA entry
                chrom = parts[3]
                pos = int(parts[4])

                key = (chrom, pos)
                mutations[key] = {
                    'mut_id': mut_id,
                    'evidence_id': evidence_id,
                }
    return mutations

def load_csv_file(csv_file, sample_col):
    """Load mutations from AMP Mutations CSV for a specific sample."""
    mutations = []
    with open(csv_file, 'r') as f:
        reader = csv.reader(f)
        header = next(reader)
        sample_name = header[sample_col]

        for row in reader:
            if len(row) > sample_col and row[sample_col]:
                val = row[sample_col]
                if '/' in val:
                    parts_freq = val.split('/')
                    breseq_freq = float(parts_freq[0]) if parts_freq[0] else 0
                    gatk_freq = float(parts_freq[1]) if parts_freq[1] else 0

                    chrom = row[0].replace('"', '')
                    pos = int(row[1].replace('"', '').replace(',', ''))
                    mut_type = row[2].replace('"', '')
                    seq_change = row[3].replace('"', '')
                    gene_csv = row[4].replace('"', '')
                    details_csv = row[5].replace('"', '')

                    mutations.append({
                        'chrom': chrom,
                        'pos': pos,
                        'csv_type': mut_type,
                        'csv_seq_change': seq_change,
                        'csv_gene': gene_csv,
                        'csv_details': details_csv,
                        'breseq_freq': breseq_freq,
                        'gatk_freq': gatk_freq,
                    })
    return mutations, sample_name

def find_nearby_match(gd_mutations, chrom, pos, window=10):
    """Find a nearby match in .gd file if exact match not found."""
    for offset in range(1, window + 1):
        for delta in [offset, -offset]:
            key = (chrom, pos + delta)
            if key in gd_mutations:
                return gd_mutations[key], delta
    return None, 0

# Load data
print("Loading data...")
gd_mutations = load_gd_file(GD_FILE)
csv_mutations, sample_name = load_csv_file(CSV_FILE, SAMPLE_COL)
ra_evidence = load_ra_evidence(RAW_GD_FILE)
raw_gd_mutations = load_raw_gd_mutations(RAW_GD_FILE)

print(f"Loaded {len(ra_evidence)} RA evidence entries with coverage data")

print(f"Sample: {sample_name}")
print(f"Total .gd mutations: {len(gd_mutations)}")
print(f"Total CSV mutations for sample: {len(csv_mutations)}")

# Filter to Breseq-detected only
breseq_csv = [m for m in csv_mutations if m['breseq_freq'] > 0]
print(f"CSV mutations with BRESEQ_FREQ > 0: {len(breseq_csv)}")

# Cross-reference
exact_matches = 0
fuzzy_matches = 0
no_matches = 0

# Prepare output
output_rows = []

for csv_mut in breseq_csv:
    chrom = csv_mut['chrom']
    pos = csv_mut['pos']
    key = (chrom, pos)

    # Try exact match first
    if key in gd_mutations:
        gd_mut = gd_mutations[key]
        match_type = 'exact'
        offset = 0
        exact_matches += 1
    else:
        # Try fuzzy match
        gd_mut, offset = find_nearby_match(gd_mutations, chrom, pos, window=10)
        if gd_mut:
            match_type = 'fuzzy'
            fuzzy_matches += 1
        else:
            gd_mut = None
            match_type = 'none'
            no_matches += 1

    # Build output row
    row = {
        'CHROM': chrom,
        'POS': pos,
        'CSV_TYPE': csv_mut['csv_type'],
        'CSV_SEQ_CHANGE': csv_mut['csv_seq_change'],
        'CSV_GENE': csv_mut['csv_gene'],
        'CSV_DETAILS': csv_mut['csv_details'],
        'BRESEQ_FREQ': csv_mut['breseq_freq'],
        'GATK_FREQ': csv_mut['gatk_freq'],
        'MATCH_TYPE': match_type,
        'OFFSET': offset,
    }

    if gd_mut:
        row.update({
            'GD_MUT_ID': gd_mut['mut_id'],
            'GD_TYPE': gd_mut['type'],
            'GD_NEW_SEQ': gd_mut['new_seq'],
            'GD_FREQ': gd_mut['frequency'],
            'GD_GENE_NAME': gd_mut['gene_name'],
            'GD_GENE_POSITION': gd_mut['gene_position'],
            'GD_GENE_PRODUCT': gd_mut['gene_product'],
            'GD_MUTATION_CATEGORY': gd_mut['mutation_category'],
            'GD_SNP_TYPE': gd_mut['snp_type'],
            'GD_AA_CHANGE': f"{gd_mut['aa_ref_seq']}{gd_mut['aa_position']}{gd_mut['aa_new_seq']}" if gd_mut['aa_position'] else '',
            'GD_CODON_CHANGE': f"{gd_mut['codon_ref_seq']}->{gd_mut['codon_new_seq']}" if gd_mut['codon_ref_seq'] else '',
            'GD_REF_SEQ': gd_mut['ref_seq'],
            'GD_LOCUS_TAG': gd_mut['locus_tag'],
        })

        # Get coverage from RA evidence using raw .gd file for evidence_id
        raw_key = (chrom, pos)
        if raw_key in raw_gd_mutations:
            evidence_id = raw_gd_mutations[raw_key]['evidence_id']
            if evidence_id in ra_evidence:
                ra = ra_evidence[evidence_id]
                row.update({
                    'RA_EVIDENCE_ID': evidence_id,
                    'TOTAL_COV': ra['total_cov'],
                    'TOTAL_COV_SUM': ra['total_cov_sum'],
                    'REF_COV': ra['ref_cov'],
                    'REF_COV_SUM': ra['ref_cov_sum'],
                    'NEW_COV': ra['new_cov'],
                    'NEW_COV_SUM': ra['new_cov_sum'],
                })
            else:
                row.update({
                    'RA_EVIDENCE_ID': evidence_id,
                    'TOTAL_COV': '',
                    'TOTAL_COV_SUM': '',
                    'REF_COV': '',
                    'REF_COV_SUM': '',
                    'NEW_COV': '',
                    'NEW_COV_SUM': '',
                })
        else:
            row.update({
                'RA_EVIDENCE_ID': '',
                'TOTAL_COV': '',
                'TOTAL_COV_SUM': '',
                'REF_COV': '',
                'REF_COV_SUM': '',
                'NEW_COV': '',
                'NEW_COV_SUM': '',
            })
    else:
        row.update({
            'GD_MUT_ID': '',
            'GD_TYPE': '',
            'GD_NEW_SEQ': '',
            'GD_FREQ': '',
            'GD_GENE_NAME': '',
            'GD_GENE_POSITION': '',
            'GD_GENE_PRODUCT': '',
            'GD_MUTATION_CATEGORY': '',
            'GD_SNP_TYPE': '',
            'GD_AA_CHANGE': '',
            'GD_CODON_CHANGE': '',
            'GD_REF_SEQ': '',
            'GD_LOCUS_TAG': '',
            'RA_EVIDENCE_ID': '',
            'TOTAL_COV': '',
            'TOTAL_COV_SUM': '',
            'REF_COV': '',
            'REF_COV_SUM': '',
            'NEW_COV': '',
            'NEW_COV_SUM': '',
        })

    output_rows.append(row)

print(f"\nMatch results:")
print(f"  Exact matches: {exact_matches}")
print(f"  Fuzzy matches (±10bp): {fuzzy_matches}")
print(f"  No match in .gd: {no_matches}")

# Write output TSV
fieldnames = [
    'CHROM', 'POS', 'CSV_TYPE', 'CSV_SEQ_CHANGE', 'CSV_GENE', 'CSV_DETAILS',
    'BRESEQ_FREQ', 'GATK_FREQ', 'MATCH_TYPE', 'OFFSET',
    'GD_MUT_ID', 'GD_TYPE', 'GD_NEW_SEQ', 'GD_FREQ', 'GD_GENE_NAME', 'GD_GENE_POSITION',
    'GD_GENE_PRODUCT', 'GD_MUTATION_CATEGORY', 'GD_SNP_TYPE', 'GD_AA_CHANGE',
    'GD_CODON_CHANGE', 'GD_REF_SEQ', 'GD_LOCUS_TAG',
    'RA_EVIDENCE_ID', 'TOTAL_COV', 'TOTAL_COV_SUM', 'REF_COV', 'REF_COV_SUM', 'NEW_COV', 'NEW_COV_SUM'
]

with open(OUTPUT_TSV, 'w', newline='') as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter='\t')
    writer.writeheader()
    writer.writerows(output_rows)

print(f"\nOutput saved to: {OUTPUT_TSV}")

# Summary by mutation category
print("\n" + "=" * 60)
print("MUTATION CATEGORY BREAKDOWN (from .gd annotation)")
print("=" * 60)

categories = defaultdict(int)
for row in output_rows:
    cat = row.get('GD_MUTATION_CATEGORY', '') or 'unmatched'
    categories[cat] += 1

for cat, count in sorted(categories.items(), key=lambda x: -x[1]):
    print(f"  {cat}: {count}")

# High-impact mutations
print("\n" + "=" * 60)
print("NONSYNONYMOUS MUTATIONS (amino acid changes)")
print("=" * 60)

nonsyn = [r for r in output_rows if r.get('GD_MUTATION_CATEGORY') == 'snp_nonsynonymous']
for row in nonsyn:
    print(f"  {row['CHROM']}:{row['POS']} - {row['GD_GENE_NAME']} {row['GD_AA_CHANGE']} (freq: {row['BRESEQ_FREQ']:.2f})")

# Gene inactivations (frameshift indels in coding regions)
print("\n" + "=" * 60)
print("CODING INDELS (potential frameshifts)")
print("=" * 60)

coding_indels = [r for r in output_rows if r.get('GD_MUTATION_CATEGORY') == 'small_indel'
                 and 'coding' in str(r.get('GD_GENE_POSITION', ''))]
for row in coding_indels:
    print(f"  {row['CHROM']}:{row['POS']} - {row['GD_GENE_NAME']} {row['GD_GENE_POSITION']} (freq: {row['BRESEQ_FREQ']:.2f})")
