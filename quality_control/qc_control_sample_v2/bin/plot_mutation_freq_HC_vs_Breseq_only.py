#!/usr/bin/env python3
"""
Create dot plot showing mutation ALLELE FREQUENCY for HC-only vs Breseq-only mutations.
For sample A1-F6-I2-R1 (genome-shuffled strain).
Simplified version showing only non-overlapping mutations.
"""
import matplotlib.pyplot as plt
import subprocess
import csv
import numpy as np

def classify_variant_type(ref, alt):
    """Classify variant type based on REF and ALT."""
    if ',' in alt:
        return 'Multi-allelic'

    if len(ref) > 3 or len(alt) > 3:
        for base in ['A', 'T', 'C', 'G']:
            if ref == base * len(ref) or alt == base * len(alt):
                return f'Poly-{base}'
            if len(ref) > 5:
                max_base_count = max(ref.count(b) for b in ['A', 'T', 'C', 'G'])
                if max_base_count / len(ref) > 0.8:
                    return f'Poly-repeat'
            if len(alt) > 5:
                max_base_count = max(alt.count(b) for b in ['A', 'T', 'C', 'G'])
                if max_base_count / len(alt) > 0.8:
                    return f'Poly-repeat'

    if len(ref) == 1 and len(alt) == 1:
        return 'SNP'
    if len(ref) < len(alt):
        return 'Insertion'
    if len(ref) > len(alt):
        return 'Deletion'
    return 'Other'

def get_breseq_positions(tsv_file):
    """Load AMP mutations detected by Breseq (BRESEQ_FREQ > 0)."""
    positions = set()
    with open(tsv_file, 'r') as f:
        reader = csv.DictReader(f, delimiter='\t')
        for row in reader:
            if row['DETECTED'] == 'YES' and float(row['BRESEQ_FREQ']) > 0:
                positions.add((row['CHROM'], int(row['POS'])))
    return positions

def get_breseq_data(tsv_file, gd_tsv_file):
    """Load Breseq frequency and coverage data."""
    # Map CSV_TYPE abbreviations to full names
    type_mapping = {
        'INS': 'Insertion',
        'DEL': 'Deletion',
        'SNP': 'SNP',
    }

    # First, get frequencies from main TSV
    freq_data = {}
    with open(tsv_file, 'r') as f:
        reader = csv.DictReader(f, delimiter='\t')
        for row in reader:
            if row['DETECTED'] == 'YES':
                chrom = row['CHROM']
                pos = int(row['POS'])
                breseq_freq = float(row['BRESEQ_FREQ']) if row['BRESEQ_FREQ'] else 0
                freq_data[(chrom, pos)] = breseq_freq

    # Get types from gd annotation TSV
    coverage_data = {}
    with open(gd_tsv_file, 'r') as f:
        reader = csv.DictReader(f, delimiter='\t')
        for row in reader:
            chrom = row['CHROM']
            pos = int(row['POS'])
            csv_type = row.get('CSV_TYPE', 'Other')
            var_type = type_mapping.get(csv_type, csv_type)

            # Combine frequency and type
            if (chrom, pos) in freq_data:
                coverage_data[(chrom, pos)] = {
                    'freq': freq_data[(chrom, pos)],
                    'type': var_type
                }

    return coverage_data

def get_vcf_data(vcf_file, sample_name):
    """Get VCF data with allele frequencies for a sample from joint VCF.
    Filters: PASS only (includes multiallelic sites).
    """
    data = {}
    cmd = ['bcftools', 'query',
           '-i', 'FILTER="PASS"',
           '-f', '%CHROM\t%POS\t%REF\t%ALT\t[%GT]\t[%AD]\t[%DP]\n',
           '-s', sample_name, str(vcf_file)]

    result = subprocess.run(cmd, capture_output=True, text=True, check=True)

    for line in result.stdout.strip().split('\n'):
        if not line:
            continue
        fields = line.split('\t')
        if len(fields) >= 7:
            chrom, pos, ref, alt, gt, ad, dp = fields[0], int(fields[1]), fields[2], fields[3], fields[4], fields[5], fields[6]

            # Skip reference genotypes
            if gt in ['0', '0/0', './.', '.', '0/0/0', '0|0']:
                continue

            # Calculate allele frequency from AD
            if ad and ',' in ad and dp.isdigit() and int(dp) > 0:
                ad_parts = ad.split(',')
                try:
                    ref_depth = int(ad_parts[0]) if ad_parts[0].isdigit() else 0

                    # Handle multiallelic sites - use genotype to get correct alt depth
                    if ',' in alt:
                        var_type = 'Multi-allelic'
                        # Parse GT to get allele index (e.g., "1" or "2" for multiallelic)
                        gt_val = gt.replace('/', '|').split('|')[0]
                        if gt_val.isdigit():
                            allele_idx = int(gt_val)
                            if allele_idx > 0 and allele_idx < len(ad_parts):
                                alt_depth = int(ad_parts[allele_idx]) if ad_parts[allele_idx].isdigit() else 0
                            else:
                                alt_depth = sum(int(x) for x in ad_parts[1:] if x.isdigit())
                        else:
                            alt_depth = sum(int(x) for x in ad_parts[1:] if x.isdigit())
                    else:
                        var_type = classify_variant_type(ref, alt)
                        alt_depth = int(ad_parts[1]) if len(ad_parts) >= 2 and ad_parts[1].isdigit() else 0

                    total = ref_depth + alt_depth
                    if total > 0:
                        freq = alt_depth / total
                        data[(chrom, pos)] = {'freq': freq, 'type': var_type, 'dp': int(dp)}
                except (ValueError, IndexError):
                    continue
    return data

def fuzzy_match(breseq_pos, vcf_pos, window=50):
    # Handle both dict and set inputs for vcf_pos
    vcf_positions = set(vcf_pos.keys()) if hasattr(vcf_pos, 'keys') else vcf_pos

    exact = breseq_pos & vcf_positions
    fuzzy_vcf = set()  # Unique VCF positions that fuzzy matched (HC side)
    fuzzy_breseq = set()  # Breseq positions that had a fuzzy match
    for pos1 in breseq_pos - exact:
        for pos2 in vcf_positions:
            if pos2 in exact:
                continue
            if pos1[0] == pos2[0] and 0 < abs(pos1[1] - pos2[1]) <= window:
                fuzzy_vcf.add(pos2)  # Use set to track unique HC positions
                fuzzy_breseq.add(pos1)
                break
    return exact, fuzzy_vcf, fuzzy_breseq

# Sample configuration
sample_name = 'A1-F6-I2-R1'
tsv_file = f'output/{sample_name}_AMP_mutations.tsv'
vcf_file = 'data/HaplotypeCaller_joint_calling_soft_filtered_snpEff.ann.vcf.gz'
vcf_sample = f'ALE_Exp1_{sample_name}'
gd_tsv_file = f'output/{sample_name}_AMP_mutations_with_gd_annotation.tsv'

print(f"Processing sample: {sample_name}")

# Get all HC positions (for counting) - PASS only (includes multiallelic sites)
cmd_all = ['bcftools', 'query', '-i', 'FILTER="PASS"', '-f', '%CHROM\t%POS\t%ALT\t[%GT]\n', '-s', vcf_sample, vcf_file]
result_all = subprocess.run(cmd_all, capture_output=True, text=True, check=True)
vcf_all_positions = set()
for line in result_all.stdout.strip().split('\n'):
    if not line:
        continue
    fields = line.split('\t')
    if len(fields) >= 4:
        chrom, pos, alt, gt = fields[0], int(fields[1]), fields[2], fields[3]
        # Include multiallelic sites - check for non-ref genotype
        if gt not in ['0', '0/0', './.', '.', '0/0/0', '0|0']:
            vcf_all_positions.add((chrom, pos))

# Get data
breseq_positions = get_breseq_positions(tsv_file)
vcf_data = get_vcf_data(vcf_file, vcf_sample)  # With AD for frequency plotting
breseq_data = get_breseq_data(tsv_file, gd_tsv_file)

# Classify mutations using ALL HC positions (for correct counts)
exact, fuzzy_vcf, fuzzy_breseq = fuzzy_match(breseq_positions, vcf_all_positions, window=50)
vcf_only_all = vcf_all_positions - exact - fuzzy_vcf  # Total HC-only count

# For plotting, use only positions with AD data
vcf_only = vcf_only_all & set(vcf_data.keys())

# Breseq-only: positions in Breseq but NOT in VCF (no exact or fuzzy match)
breseq_only = breseq_positions - exact - fuzzy_breseq

print(f"Breseq-detected mutations: {len(breseq_positions)}")
print(f"Total HC variants: {len(vcf_all_positions)}")
print(f"HC variants with AD (for frequency): {len(vcf_data)}")
print(f"Exact matches: {len(exact)}")
print(f"Fuzzy matches (Breseq positions): {len(fuzzy_breseq)}")
print(f"Fuzzy matches (unique HC positions): {len(fuzzy_vcf)}")
print(f"GATK-HC only (total): {len(vcf_only_all)}")
print(f"GATK-HC only (with AD for plotting): {len(vcf_only)}")
print(f"Breseq only: {len(breseq_only)}")

# Organize data by category and type - ONLY HC-only and Breseq-only
# Use vcf_only_all for count label, but vcf_only for actual plotting
categories = {
    f'GATK-HC Only\n(n={len(vcf_only_all)})': (vcf_only, 'vcf'),  # Label shows total, plots only with AD
    f'Breseq Only\n(n={len(breseq_only)})': (breseq_only, 'breseq'),
}

# Type to marker mapping
type_markers = {
    'SNP': 'o',
    'Insertion': '^',
    'Deletion': 'v',
    'Multi-allelic': 's',
    'Poly-A': 'D',
    'Poly-T': 'D',
    'Poly-C': 'D',
    'Poly-G': 'D',
    'Poly-repeat': 'D',
    'Other': 'x'
}

type_colors = {
    'SNP': '#E91E63',
    'Insertion': '#2196F3',
    'Deletion': '#FF9800',
    'Multi-allelic': '#9C27B0',
    'Poly-A': '#4CAF50',
    'Poly-T': '#4CAF50',
    'Poly-C': '#4CAF50',
    'Poly-G': '#4CAF50',
    'Poly-repeat': '#4CAF50',
    'Other': '#607D8B'
}

# Set up presentation style
plt.style.use('seaborn-v0_8-whitegrid')
plt.rcParams.update({
    'font.family': 'sans-serif',
    'font.size': 14,
    'axes.labelsize': 16,
    'xtick.labelsize': 14,
    'ytick.labelsize': 14,
    'figure.facecolor': 'white',
    'axes.facecolor': 'white',
    'axes.edgecolor': '#333333',
    'axes.linewidth': 1.5,
})

# Create plot - narrower since only 2 categories
fig, ax = plt.subplots(figsize=(10, 8))
fig.patch.set_facecolor('white')

category_labels = ['GATK-HC Only', 'Breseq Only']
x_positions = {cat: i for i, cat in enumerate(categories.keys())}

np.random.seed(42)

# Plot points
for category, (positions, data_source) in categories.items():
    x_base = x_positions[category]
    for pos in positions:
        # Get data from appropriate source
        if data_source == 'vcf':
            if pos not in vcf_data:
                continue
            freq = vcf_data[pos]['freq']
            var_type = vcf_data[pos]['type']
        else:  # breseq
            if pos not in breseq_data:
                continue
            freq = breseq_data[pos]['freq']
            var_type = breseq_data[pos]['type']

        x_jitter = x_base + np.random.uniform(-0.25, 0.25)

        marker = type_markers.get(var_type, 'o')
        color = type_colors.get(var_type, '#607D8B')

        ax.scatter(x_jitter, freq * 100, marker=marker, s=280, color=color,
                  alpha=0.5, edgecolors='white', linewidth=1.5)

# Customize plot
ax.set_ylabel('Allele Frequency (%)', fontweight='bold')
ax.set_xlabel('Detection Category', fontweight='bold')

ax.set_xticks(list(x_positions.values()))
ax.set_xticklabels(category_labels, fontweight='bold')

# Set y-axis to 0-100% range
ax.set_ylim(-5, 105)

# Add horizontal lines for median frequency per category with labels
for category, (positions, data_source) in categories.items():
    if positions:
        if data_source == 'vcf':
            freqs = [vcf_data[pos]['freq'] * 100 for pos in positions if pos in vcf_data]
        else:  # breseq
            freqs = [breseq_data[pos]['freq'] * 100 for pos in positions if pos in breseq_data]
        if freqs:
            median_freq = np.median(freqs)
            x_pos = x_positions[category]
            ax.hlines(median_freq, x_pos - 0.35, x_pos + 0.35, colors='black', linewidth=3, zorder=4)
            ax.text(x_pos + 0.4, median_freq, f'{median_freq:.1f}%', fontsize=12, fontweight='bold',
                    va='center', ha='left')

ax.spines['top'].set_visible(False)
ax.spines['right'].set_visible(False)
ax.tick_params(axis='both', which='both', length=5)

# Create combined legend
type_legend_elements = [
    plt.Line2D([0], [0], marker='o', color='w', markerfacecolor='#E91E63',
              markersize=12, label='SNP', markeredgecolor='white', markeredgewidth=1.5),
    plt.Line2D([0], [0], marker='^', color='w', markerfacecolor='#2196F3',
              markersize=12, label='Insertion', markeredgecolor='white', markeredgewidth=1.5),
    plt.Line2D([0], [0], marker='v', color='w', markerfacecolor='#FF9800',
              markersize=12, label='Deletion', markeredgecolor='white', markeredgewidth=1.5),
    plt.Line2D([0], [0], marker='s', color='w', markerfacecolor='#9C27B0',
              markersize=12, label='Multi-allelic', markeredgecolor='white', markeredgewidth=1.5),
    plt.Line2D([0], [0], marker='D', color='w', markerfacecolor='#4CAF50',
              markersize=12, label='Poly-repeat', markeredgecolor='white', markeredgewidth=1.5),
    plt.Line2D([0], [0], color='black', linestyle='-', linewidth=3, label='Median Freq'),
]

leg = ax.legend(handles=type_legend_elements, loc='upper right', fontsize=11,
                framealpha=0.8, edgecolor='black', fancybox=True,
                facecolor='white', frameon=True)
leg.get_frame().set_boxstyle('round')

# Add sample and counts annotation
stats_text = f'Sample: {sample_name}\nTool-Specific Mutations\n(GATK-HC freq for HC-only)\n(Breseq freq for Breseq-only)\n\nHC-only: n={len(vcf_only_all)}\nBreseq-only: n={len(breseq_only)}'
ax.text(0.98, 0.70, stats_text, transform=ax.transAxes, fontsize=10, va='top', ha='right',
        bbox=dict(boxstyle='round', facecolor='white', alpha=0.8, edgecolor='black'))

plt.tight_layout()
plt.savefig(f'comparison/mutation_freq_HC_vs_Breseq_only_{sample_name}.png', dpi=300, bbox_inches='tight',
            facecolor='white', edgecolor='none')
plt.savefig(f'comparison/mutation_freq_HC_vs_Breseq_only_{sample_name}.pdf', bbox_inches='tight',
            facecolor='white', edgecolor='none')

plt.style.use('default')

print(f"\nHC vs Breseq-only frequency plot saved to:")
print(f"  - comparison/mutation_freq_HC_vs_Breseq_only_{sample_name}.png")
print(f"  - comparison/mutation_freq_HC_vs_Breseq_only_{sample_name}.pdf")
