#!/usr/bin/env python3
"""
Find mutations unique to AMP (not found in Joint-GATK-HC VCF).
Uses exact matching and fuzzy matching (100bp window).

Usage: python find_amp_only_mutations.py [sample_name]
Default sample: A0-F0-I1-R1
"""
import csv
import subprocess
import sys

def get_amp_positions(tsv_file):
    """Load AMP mutations from TSV file."""
    positions = []
    with open(tsv_file, 'r') as f:
        reader = csv.DictReader(f, delimiter='\t')
        for row in reader:
            if row['DETECTED'] == 'YES':
                positions.append({
                    'chrom': row['CHROM'],
                    'pos': int(row['POS']),
                    'gene': row['GENE'],
                    'mut_type': row['MUT_TYPE'],
                    'seq_change': row['SEQ_CHANGE'],
                    'details': row['DETAILS']
                })
    return positions

def get_vcf_positions(vcf_file, sample_name):
    """Extract variant positions from VCF for a specific sample."""
    cmd = ['bcftools', 'query', '-f', '%CHROM\t%POS\t[%GT]\n',
           '-s', sample_name, vcf_file]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)

    positions = set()
    for line in result.stdout.strip().split('\n'):
        if not line:
            continue
        fields = line.split('\t')
        if len(fields) >= 3:
            chrom, pos, gt = fields[0], int(fields[1]), fields[2]
            # Only include non-reference genotypes
            if gt not in ['0', '0/0', './.', '.', '0/0/0']:
                positions.add((chrom, pos))
    return positions

def find_amp_only(amp_positions, vcf_positions, window=50):
    """Find AMP mutations not matched in VCF (exact or fuzzy)."""
    amp_only = []

    for amp in amp_positions:
        pos = (amp['chrom'], amp['pos'])

        # Check exact match
        if pos in vcf_positions:
            continue

        # Check fuzzy match (within window bp)
        fuzzy_found = False
        for vcf_chrom, vcf_pos in vcf_positions:
            if vcf_chrom == amp['chrom'] and 0 < abs(vcf_pos - amp['pos']) <= window:
                fuzzy_found = True
                break

        if not fuzzy_found:
            amp_only.append(amp)

    return amp_only

def main():
    # Default sample
    sample_name = sys.argv[1] if len(sys.argv) > 1 else 'A0-F0-I1-R1'

    # File paths
    tsv_file = f'output/{sample_name}_AMP_mutations.tsv'
    vcf_file = f'data/{sample_name}.haplotypecaller.from_joint_calling_snpEff.ann.vcf.gz'
    vcf_sample = f'ALE_Exp1_{sample_name}'

    print(f"Sample: {sample_name}")
    print(f"AMP TSV: {tsv_file}")
    print(f"VCF: {vcf_file}")
    print(f"VCF sample column: {vcf_sample}")
    print()

    # Load data
    amp_positions = get_amp_positions(tsv_file)
    vcf_positions = get_vcf_positions(vcf_file, vcf_sample)

    print(f"AMP mutations (detected): {len(amp_positions)}")
    print(f"VCF variants (non-ref): {len(vcf_positions)}")
    print()

    # Find AMP-only mutations
    amp_only = find_amp_only(amp_positions, vcf_positions, window=50)

    print(f"Found {len(amp_only)} AMP-only mutations (no match within 100bp window):\n")
    print(f"{'CHROM':<8} {'POS':<12} {'TYPE':<6} {'CHANGE':<20} {'GENE':<25} {'DETAILS'}")
    print("=" * 100)

    for m in amp_only:
        print(f"{m['chrom']:<8} {m['pos']:<12} {m['mut_type']:<6} {m['seq_change']:<20} {m['gene']:<25} {m['details']}")

    # Save to file
    output_file = f'comparison/{sample_name}_amp_only_mutations.tsv'
    with open(output_file, 'w') as f:
        f.write("CHROM\tPOS\tTYPE\tCHANGE\tGENE\tDETAILS\n")
        for m in amp_only:
            f.write(f"{m['chrom']}\t{m['pos']}\t{m['mut_type']}\t{m['seq_change']}\t{m['gene']}\t{m['details']}\n")

    print(f"\nSaved to: {output_file}")

if __name__ == '__main__':
    main()
