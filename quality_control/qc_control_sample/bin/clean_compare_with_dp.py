#!/usr/bin/env python3
"""
Clean comparison with DP values: VCF vs CSV for sample A0-F0-I1-R1
"""
import subprocess
import csv

def get_csv_positions(csv_file):
    """Get all positions from AMP CSV (detected mutations)."""
    positions = set()
    with open(csv_file, 'r') as f:
        reader = csv.DictReader(f, delimiter='\t')
        for row in reader:
            if row['DETECTED'] == 'YES':
                chrom = row['CHROM']
                pos = int(row['POS'])
                positions.add((chrom, pos))
    return positions

def classify_variant_type(ref, alt):
    """Classify variant type based on REF and ALT."""
    # Check for multi-allelic
    if ',' in alt:
        return 'Multi-allelic'

    # Check for poly-A/T/C/G (repeats)
    if len(ref) > 3 or len(alt) > 3:
        # Check if ref or alt is a homopolymer
        for base in ['A', 'T', 'C', 'G']:
            if ref == base * len(ref) or alt == base * len(alt):
                return f'Poly-{base}'
            # Check if it's mostly one base (>80%)
            if len(ref) > 5:
                max_base_count = max(ref.count(b) for b in ['A', 'T', 'C', 'G'])
                if max_base_count / len(ref) > 0.8:
                    return f'Poly-repeat'
            if len(alt) > 5:
                max_base_count = max(alt.count(b) for b in ['A', 'T', 'C', 'G'])
                if max_base_count / len(alt) > 0.8:
                    return f'Poly-repeat'

    # SNP: both REF and ALT are single base
    if len(ref) == 1 and len(alt) == 1:
        return 'SNP'

    # Insertion: REF shorter than ALT
    if len(ref) < len(alt):
        return 'Insertion'

    # Deletion: REF longer than ALT
    if len(ref) > len(alt):
        return 'Deletion'

    return 'Other'

def get_vcf_positions_with_dp(vcf_file, sample_name):
    """Get all positions from VCF with DP values, REF, ALT, and variant type."""
    positions = {}  # (chrom, pos) -> {'dp': dp, 'gt': gt, 'filter': filter, 'ref': ref, 'alt': alt, 'type': type}

    cmd = ['bcftools', 'query',
           '-f', '%CHROM\t%POS\t%REF\t%ALT\t%FILTER\t[%GT]\t[%DP]\n',
           '-s', sample_name,
           str(vcf_file)]

    result = subprocess.run(cmd, capture_output=True, text=True, check=True)

    for line in result.stdout.strip().split('\n'):
        if not line:
            continue
        fields = line.split('\t')
        if len(fields) >= 7:
            chrom, pos, ref, alt, filter_field, gt, dp = fields[0], int(fields[1]), fields[2], fields[3], fields[4], fields[5], fields[6]

            # Only non-reference genotypes
            if gt not in ['0', '0/0', './.', '.', '0/0/0']:
                var_type = classify_variant_type(ref, alt)
                positions[(chrom, pos)] = {
                    'dp': dp,
                    'gt': gt,
                    'filter': filter_field,
                    'ref': ref,
                    'alt': alt,
                    'type': var_type
                }

    return positions

def fuzzy_match(csv_positions, vcf_positions, window=50):
    """Find fuzzy matches within window, excluding exact matches."""
    exact_matches = csv_positions & set(vcf_positions.keys())
    fuzzy_matches = []
    
    # Check each position in csv against vcf
    for chrom1, pos1 in csv_positions - exact_matches:
        for chrom2, pos2 in vcf_positions.keys():
            if (chrom2, pos2) in exact_matches:
                continue
            if chrom1 == chrom2 and 0 < abs(pos1 - pos2) <= window:
                fuzzy_matches.append(((chrom1, pos1), (chrom2, pos2), abs(pos1 - pos2)))
                break
    
    return exact_matches, fuzzy_matches

# Get positions
csv_positions = get_csv_positions('output/A0-F0-I1-R1_AMP_mutations.tsv')
vcf_positions = get_vcf_positions_with_dp(
    'data/A0-F0-I1-R1.haplotypecaller.from_joint_calling_snpEff.ann.vcf.gz',
    'ALE_Exp1_A0-F0-I1-R1'
)

# Find matches
exact, fuzzy = fuzzy_match(csv_positions, vcf_positions, window=50)

# Calculate unique
csv_unique = csv_positions - exact - {pos1 for pos1, pos2, dist in fuzzy}
vcf_unique = set(vcf_positions.keys()) - exact - {pos2 for pos1, pos2, dist in fuzzy}

print("=" * 120)
print("CLEAN COMPARISON WITH DP: A0-F0-I1-R1 VCF vs CSV")
print("=" * 120)
print()
print("DATASET SIZES:")
print(f"  VCF mutations (non-ref GT): {len(vcf_positions)}")
print(f"  CSV mutations (AMP detected): {len(csv_positions)}")
print()
print("MATCHING RESULTS:")
print(f"  Exact matches (same position): {len(exact)} ({len(exact)/len(csv_positions)*100:.1f}% of CSV)")
print(f"  Fuzzy matches (within 50bp): {len(fuzzy)} ({len(fuzzy)/len(csv_positions)*100:.1f}% of CSV)")
print(f"  Total matches: {len(exact) + len(fuzzy)} ({(len(exact) + len(fuzzy))/len(csv_positions)*100:.1f}% of CSV)")
print()
print("UNIQUE MUTATIONS:")
print(f"  CSV-only (no match): {len(csv_unique)} ({len(csv_unique)/len(csv_positions)*100:.1f}% of CSV)")
print(f"  VCF-only (no match): {len(vcf_unique)} ({len(vcf_unique)/len(vcf_positions)*100:.1f}% of VCF)")

# Show exact matches with DP
print()
print("=" * 170)
print(f"EXACT MATCHES ({len(exact)} positions)")
print("=" * 170)
print(f"{'#':<5} {'Position':<20} {'Type':<15} {'REF':<12} {'ALT':<30} {'Filter':<12} {'GT':<6} {'DP':<6}")
print("-" * 170)
for i, (chrom, pos) in enumerate(sorted(exact), 1):
    info = vcf_positions[(chrom, pos)]
    ref_display = info['ref'][:9] + '...' if len(info['ref']) > 12 else info['ref']
    alt_display = info['alt'][:27] + '...' if len(info['alt']) > 30 else info['alt']
    print(f"{i:<5} {chrom}:{pos:<15} {info['type']:<15} {ref_display:<12} {alt_display:<30} {info['filter']:<12} {info['gt']:<6} {info['dp']:<6}")

# Show fuzzy matches with DP
print()
print("=" * 175)
print(f"FUZZY MATCHES ({len(fuzzy)} positions, within 50bp)")
print("=" * 175)
print(f"{'#':<5} {'CSV Position':<17} {'VCF Position':<17} {'Dist':<7} {'Type':<14} {'REF':<10} {'ALT':<25} {'Filter':<12} {'GT':<6} {'DP':<6}")
print("-" * 175)
for i, ((chrom1, pos1), (chrom2, pos2), dist) in enumerate(sorted(fuzzy, key=lambda x: (x[0][0], x[0][1])), 1):
    info = vcf_positions[(chrom2, pos2)]
    ref_display = info['ref'][:7] + '...' if len(info['ref']) > 10 else info['ref']
    alt_display = info['alt'][:22] + '...' if len(info['alt']) > 25 else info['alt']
    print(f"{i:<5} {chrom1}:{pos1:<12} {chrom2}:{pos2:<12} {dist}bp{'':<3} {info['type']:<14} {ref_display:<10} {alt_display:<25} {info['filter']:<12} {info['gt']:<6} {info['dp']:<6}")

# Show CSV-only
print()
print("=" * 120)
print(f"CSV-ONLY MUTATIONS ({len(csv_unique)} positions)")
print("=" * 120)
for i, (chrom, pos) in enumerate(sorted(csv_unique), 1):
    print(f"{i:>3}. {chrom}:{pos}")

# Show VCF-only with DP
print()
print("=" * 170)
print(f"VCF-ONLY MUTATIONS ({len(vcf_unique)} positions)")
print("=" * 170)
print(f"{'#':<5} {'Position':<20} {'Type':<15} {'REF':<12} {'ALT':<30} {'Filter':<12} {'GT':<6} {'DP':<6}")
print("-" * 170)
for i, (chrom, pos) in enumerate(sorted(vcf_unique), 1):
    info = vcf_positions[(chrom, pos)]
    ref_display = info['ref'][:9] + '...' if len(info['ref']) > 12 else info['ref']
    alt_display = info['alt'][:27] + '...' if len(info['alt']) > 30 else info['alt']
    print(f"{i:<5} {chrom}:{pos:<15} {info['type']:<15} {ref_display:<12} {alt_display:<30} {info['filter']:<12} {info['gt']:<6} {info['dp']:<6}")

# DP Statistics
print()
print("=" * 120)
print("DEPTH STATISTICS")
print("=" * 120)

exact_dps = [int(vcf_positions[pos]['dp']) for pos in exact if vcf_positions[pos]['dp'].isdigit()]
fuzzy_dps = [int(vcf_positions[pos2]['dp']) for _, pos2, _ in fuzzy if vcf_positions[pos2]['dp'].isdigit()]
vcf_only_dps = [int(vcf_positions[pos]['dp']) for pos in vcf_unique if vcf_positions[pos]['dp'].isdigit()]

if exact_dps:
    print(f"\nExact matches:")
    print(f"  Min DP: {min(exact_dps)}, Max DP: {max(exact_dps)}, Mean DP: {sum(exact_dps)/len(exact_dps):.1f}, Median DP: {sorted(exact_dps)[len(exact_dps)//2]}")

if fuzzy_dps:
    print(f"\nFuzzy matches:")
    print(f"  Min DP: {min(fuzzy_dps)}, Max DP: {max(fuzzy_dps)}, Mean DP: {sum(fuzzy_dps)/len(fuzzy_dps):.1f}, Median DP: {sorted(fuzzy_dps)[len(fuzzy_dps)//2]}")

if vcf_only_dps:
    print(f"\nVCF-only mutations:")
    print(f"  Min DP: {min(vcf_only_dps)}, Max DP: {max(vcf_only_dps)}, Mean DP: {sum(vcf_only_dps)/len(vcf_only_dps):.1f}, Median DP: {sorted(vcf_only_dps)[len(vcf_only_dps)//2]}")

