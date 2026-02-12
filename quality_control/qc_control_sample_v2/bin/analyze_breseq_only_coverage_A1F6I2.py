#!/usr/bin/env python3
"""
Analyze coverage and mutation types for Breseq-only mutations (not in Joint-GATK-HC VCF).
For sample A1-F6-I2-R1.
"""
import csv
import subprocess
from statistics import mean, median, stdev
from collections import defaultdict, Counter

# File paths
SAMPLE_NAME = 'A1-F6-I2-R1'
GD_TSV = f'output/{SAMPLE_NAME}_AMP_mutations_with_gd_annotation.tsv'
AMP_TSV = f'output/{SAMPLE_NAME}_AMP_mutations.tsv'
VCF_FILE = 'data/HaplotypeCaller_joint_calling_soft_filtered_snpEff.ann.vcf.gz'
VCF_SAMPLE = f'ALE_Exp1_{SAMPLE_NAME}'
FUZZY_WINDOW = 50

def get_breseq_positions(tsv_file):
    """Get Breseq positions from AMP TSV."""
    positions = set()
    with open(tsv_file, 'r') as f:
        reader = csv.DictReader(f, delimiter='\t')
        for row in reader:
            if row['DETECTED'] == 'YES' and float(row['BRESEQ_FREQ']) > 0:
                positions.add((row['CHROM'], int(row['POS'])))
    return positions

def get_vcf_positions(vcf_file, vcf_sample):
    """Get variant positions from VCF."""
    cmd = ['bcftools', 'query', '-f', '%CHROM\t%POS\t[%GT]\n', '-s', vcf_sample, vcf_file]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)

    positions = set()
    for line in result.stdout.strip().split('\n'):
        if not line:
            continue
        fields = line.split('\t')
        if len(fields) >= 3:
            chrom, pos, gt = fields[0], int(fields[1]), fields[2]
            if gt not in ['0', '0/0', './.', '.', '0/0/0']:
                positions.add((chrom, pos))
    return positions

def find_breseq_only(breseq_positions, vcf_positions, window=50):
    """Find Breseq-only positions (not in VCF with exact or fuzzy match)."""
    exact = breseq_positions & vcf_positions
    fuzzy_breseq = set()
    for pos1 in breseq_positions - exact:
        for pos2 in vcf_positions:
            if pos2 in exact:
                continue
            if pos1[0] == pos2[0] and 0 < abs(pos1[1] - pos2[1]) <= window:
                fuzzy_breseq.add(pos1)
                break
    return breseq_positions - exact - fuzzy_breseq

def load_mutation_details(gd_tsv):
    """Load mutation details from cross-referenced TSV."""
    details = {}
    with open(gd_tsv, 'r') as f:
        reader = csv.DictReader(f, delimiter='\t')
        for row in reader:
            key = (row['CHROM'], int(row['POS']))
            details[key] = row
    return details

def main():
    print(f"BRESEQ-ONLY MUTATIONS - COVERAGE ANALYSIS")
    print(f"Sample: {SAMPLE_NAME}")
    print("=" * 70)

    # Get positions
    breseq_positions = get_breseq_positions(AMP_TSV)
    vcf_positions = get_vcf_positions(VCF_FILE, VCF_SAMPLE)
    breseq_only = find_breseq_only(breseq_positions, vcf_positions, FUZZY_WINDOW)

    print(f"\nTotal Breseq-only mutations: {len(breseq_only)}\n")

    # Load mutation details
    mutation_details = load_mutation_details(GD_TSV)

    # Analyze coverage
    coverages = []
    frequencies = []
    detailed_list = []
    type_counts = Counter()
    category_counts = Counter()

    for pos in sorted(breseq_only):
        if pos in mutation_details:
            row = mutation_details[pos]
            total_cov = row.get('TOTAL_COV_SUM', '')
            freq = row.get('BRESEQ_FREQ', '')
            csv_type = row.get('CSV_TYPE', '')
            gene = row.get('GD_GENE_NAME', row.get('CSV_GENE', ''))
            category = row.get('GD_MUTATION_CATEGORY', '')

            type_counts[csv_type] += 1
            if category:
                category_counts[category] += 1

            if total_cov and total_cov.isdigit():
                cov = int(total_cov)
                coverages.append(cov)
                detailed_list.append({
                    'pos': pos,
                    'type': csv_type,
                    'gene': gene,
                    'category': category,
                    'coverage': cov,
                    'freq': float(freq) if freq else 0
                })
            if freq:
                frequencies.append(float(freq))

    # Print mutation type breakdown
    print("MUTATION TYPE BREAKDOWN (CSV_TYPE):")
    print("-" * 50)
    for t, c in type_counts.most_common():
        print(f"  {t}: {c}")

    print(f"\nMUTATION CATEGORY BREAKDOWN (from .gd annotation):")
    print("-" * 50)
    for cat, c in category_counts.most_common():
        print(f"  {cat}: {c}")

    # Coverage statistics
    print(f"\nCOVERAGE STATISTICS (TOTAL_COV_SUM from Breseq .gd):")
    print("-" * 50)
    if coverages:
        print(f"  Count with coverage data: {len(coverages)}/{len(breseq_only)}")
        print(f"  Mean:   {mean(coverages):.1f}")
        print(f"  Median: {median(coverages):.1f}")
        print(f"  Min:    {min(coverages)}")
        print(f"  Max:    {max(coverages)}")
        if len(coverages) > 1:
            print(f"  Std:    {stdev(coverages):.1f}")

        # Coverage distribution
        print(f"\nCOVERAGE DISTRIBUTION:")
        print("-" * 50)
        bins = [(0, 50), (50, 100), (100, 200), (200, 500), (500, 1000), (1000, 10000)]
        for low, high in bins:
            count = sum(1 for c in coverages if low <= c < high)
            label = f"{low}-{high-1}" if high != 10000 else f">{low}"
            print(f"  {label:>10}: {count:3} ({count/len(coverages)*100:5.1f}%)")

    # Frequency statistics
    print(f"\nFREQUENCY STATISTICS (BRESEQ_FREQ):")
    print("-" * 50)
    if frequencies:
        print(f"  Mean:   {mean(frequencies):.2f}")
        print(f"  Median: {median(frequencies):.2f}")
        print(f"  Min:    {min(frequencies):.2f}")
        print(f"  Max:    {max(frequencies):.2f}")

    # By mutation type
    print(f"\nCOVERAGE BY MUTATION TYPE:")
    print("-" * 50)
    type_coverages = defaultdict(list)
    for item in detailed_list:
        type_coverages[item['type']].append(item['coverage'])

    for t, covs in sorted(type_coverages.items(), key=lambda x: -len(x[1])):
        print(f"  {t}: n={len(covs)}, mean={mean(covs):.1f}, median={median(covs):.1f}")

    # Show high-coverage outliers
    print(f"\nHIGH COVERAGE OUTLIERS (>500):")
    print("-" * 70)
    print(f"{'CHROM':<10} {'POS':<12} {'TYPE':<6} {'COV':>6} {'FREQ':>6} {'GENE':<20} {'CATEGORY'}")
    print("-" * 70)
    high_cov = sorted([d for d in detailed_list if d['coverage'] > 500], key=lambda x: -x['coverage'])
    for item in high_cov[:10]:
        print(f"{item['pos'][0]:<10} {item['pos'][1]:<12} {item['type']:<6} {item['coverage']:>6} {item['freq']:>6.2f} {item['gene'][:20]:<20} {item['category']}")

    # Show low-coverage mutations
    print(f"\nLOW COVERAGE MUTATIONS (<100):")
    print("-" * 70)
    print(f"{'CHROM':<10} {'POS':<12} {'TYPE':<6} {'COV':>6} {'FREQ':>6} {'GENE':<20} {'CATEGORY'}")
    print("-" * 70)
    low_cov = sorted([d for d in detailed_list if d['coverage'] < 100], key=lambda x: x['coverage'])
    for item in low_cov[:10]:
        print(f"{item['pos'][0]:<10} {item['pos'][1]:<12} {item['type']:<6} {item['coverage']:>6} {item['freq']:>6.2f} {item['gene'][:20]:<20} {item['category']}")

if __name__ == '__main__':
    main()
