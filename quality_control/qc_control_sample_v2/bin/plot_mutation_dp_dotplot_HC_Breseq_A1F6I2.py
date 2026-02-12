#!/usr/bin/env python3
"""
Create dot plot showing mutation depth (DP) by match category and type.
For sample A1-F6-I2-R1 (genome-shuffled strain).
This version only considers Breseq-detected mutations (BRESEQ_FREQ > 0).
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

def get_breseq_coverage(gd_tsv_file):
    """Load Breseq coverage data from cross-referenced TSV with .gd annotations."""
    # Map CSV_TYPE abbreviations to full names used in type_colors
    type_mapping = {
        'INS': 'Insertion',
        'DEL': 'Deletion',
        'SNP': 'SNP',
    }
    coverage_data = {}
    with open(gd_tsv_file, 'r') as f:
        reader = csv.DictReader(f, delimiter='\t')
        for row in reader:
            chrom = row['CHROM']
            pos = int(row['POS'])
            # Use TOTAL_COV_SUM from RA evidence
            total_cov_sum = row.get('TOTAL_COV_SUM', '')
            if total_cov_sum and total_cov_sum.isdigit():
                csv_type = row.get('CSV_TYPE', 'Other')
                var_type = type_mapping.get(csv_type, csv_type)
                coverage_data[(chrom, pos)] = {
                    'dp': int(total_cov_sum),
                    'type': var_type
                }
    return coverage_data

def get_vcf_data(vcf_file, sample_name):
    """Get VCF data for a sample from joint VCF.
    Filters: PASS only (includes multiallelic sites).
    """
    data = {}
    cmd = ['bcftools', 'query',
           '-i', 'FILTER="PASS"',
           '-f', '%CHROM\t%POS\t%REF\t%ALT\t[%GT]\t[%DP]\n',
           '-s', sample_name, str(vcf_file)]

    result = subprocess.run(cmd, capture_output=True, text=True, check=True)

    for line in result.stdout.strip().split('\n'):
        if not line:
            continue
        fields = line.split('\t')
        if len(fields) >= 6:
            chrom, pos, ref, alt, gt, dp = fields[0], int(fields[1]), fields[2], fields[3], fields[4], fields[5]
            # Include multiallelic sites - classify as Multi-allelic type
            if gt not in ['0', '0/0', './.', '.', '0/0/0', '0|0'] and dp.isdigit():
                if ',' in alt:
                    var_type = 'Multi-allelic'
                else:
                    var_type = classify_variant_type(ref, alt)
                data[(chrom, pos)] = {'dp': int(dp), 'type': var_type}
    return data

def fuzzy_match(breseq_pos, vcf_pos, window=50):
    exact = breseq_pos & set(vcf_pos.keys())
    fuzzy_vcf = []  # VCF positions that fuzzy matched
    fuzzy_breseq = set()  # Breseq positions that had a fuzzy match
    for pos1 in breseq_pos - exact:
        for pos2 in vcf_pos.keys():
            if pos2 in exact:
                continue
            if pos1[0] == pos2[0] and 0 < abs(pos1[1] - pos2[1]) <= window:
                fuzzy_vcf.append(pos2)
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

# Get data - Breseq-only
breseq_positions = get_breseq_positions(tsv_file)
vcf_data = get_vcf_data(vcf_file, vcf_sample)
breseq_coverage = get_breseq_coverage(gd_tsv_file)

# Classify mutations
exact, fuzzy_vcf, fuzzy_breseq = fuzzy_match(breseq_positions, vcf_data, window=50)
vcf_only = set(vcf_data.keys()) - exact - set(fuzzy_vcf)

# Breseq-only: positions in Breseq but NOT in VCF (no exact or fuzzy match)
breseq_only = breseq_positions - exact - fuzzy_breseq

print(f"Breseq-detected mutations: {len(breseq_positions)}")
print(f"VCF variants (non-ref): {len(vcf_data)}")
print(f"Exact matches: {len(exact)}")
print(f"Fuzzy matches: {len(fuzzy_vcf)}")
print(f"Joint-GATK-HC only: {len(vcf_only)}")
print(f"Breseq only: {len(breseq_only)}")

# Organize data by category and type
# Use tuples: (positions, data_source) where data_source is 'vcf' or 'breseq'
categories = {
    f'Exact Match\n(n={len(exact)})': (exact, 'vcf'),
    f'Fuzzy Match\n(n={len(fuzzy_vcf)})': (set(fuzzy_vcf), 'vcf'),
    f'Joint-GATK-HC Only\n(n={len(vcf_only)})': (vcf_only, 'vcf'),
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

# Create plot - wider to accommodate 4th category
fig, ax = plt.subplots(figsize=(14, 8))
fig.patch.set_facecolor('white')

category_labels = ['Exact Match', r'Fuzzy Match ($\pm$50bp window)', 'Joint-GATK-HC\nOnly', 'Breseq Only']
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
            dp = vcf_data[pos]['dp']
            var_type = vcf_data[pos]['type']
        else:  # breseq
            if pos not in breseq_coverage:
                continue
            dp = breseq_coverage[pos]['dp']
            var_type = breseq_coverage[pos]['type']

        x_jitter = x_base + np.random.uniform(-0.25, 0.25)

        marker = type_markers.get(var_type, 'o')
        color = type_colors.get(var_type, '#607D8B')

        ax.scatter(x_jitter, dp, marker=marker, s=280, color=color,
                  alpha=0.5, edgecolors='white', linewidth=1.5)

# Customize plot
ax.set_ylabel('Informative depth (DP) - Log Scale', fontweight='bold')
ax.set_xlabel('Match Category', fontweight='bold')

ax.set_xticks(list(x_positions.values()))
ax.set_xticklabels(category_labels, fontweight='bold')

# Use log scale for y-axis to handle wide range of coverage values
ax.set_yscale('log')

# Add horizontal lines for median DP per category with labels (median better for log scale)
for category, (positions, data_source) in categories.items():
    if positions:
        if data_source == 'vcf':
            dps = [vcf_data[pos]['dp'] for pos in positions if pos in vcf_data]
        else:  # breseq
            dps = [breseq_coverage[pos]['dp'] for pos in positions if pos in breseq_coverage]
        if dps:
            median_dp = np.median(dps)
            x_pos = x_positions[category]
            ax.hlines(median_dp, x_pos - 0.35, x_pos + 0.35, colors='black', linewidth=3, zorder=4)
            ax.text(x_pos + 0.4, median_dp, f'{median_dp:.0f}', fontsize=12, fontweight='bold',
                    va='center', ha='left')

ax.spines['top'].set_visible(False)
ax.spines['right'].set_visible(False)
ax.tick_params(axis='both', which='both', length=5)

# Set y limit for log scale
ax.set_ylim(5, 15000)  # Covers range from ~10 to ~10000

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
    plt.Line2D([0], [0], color='black', linestyle='-', linewidth=3, label='Median DP'),
]

leg = ax.legend(handles=type_legend_elements, loc='upper center', fontsize=11,
                framealpha=0.8, edgecolor='black', fancybox=True,
                facecolor='white', frameon=True)
leg.get_frame().set_boxstyle('round')

# Add sample and counts annotation
stats_text = f'Sample: {sample_name}\nBreseq AMP mutations\n\nExact: n={len(exact)}\nFuzzy: n={len(fuzzy_vcf)}\nJoint-only: n={len(vcf_only)}\nBreseq-only: n={len(breseq_only)}'
ax.text(0.02, 0.98, stats_text, transform=ax.transAxes, fontsize=11, va='top', ha='left',
        bbox=dict(boxstyle='round', facecolor='white', alpha=0.8, edgecolor='black'))

plt.tight_layout()
plt.savefig(f'comparison/mutation_dp_dotplot_HC_Breseq_{sample_name}.png', dpi=300, bbox_inches='tight',
            facecolor='white', edgecolor='none')
plt.savefig(f'comparison/mutation_dp_dotplot_HC_Breseq_{sample_name}.pdf', bbox_inches='tight',
            facecolor='white', edgecolor='none')

plt.style.use('default')

print(f"\nDot plot saved to:")
print(f"  - comparison/mutation_dp_dotplot_HC_Breseq_{sample_name}.png")
print(f"  - comparison/mutation_dp_dotplot_HC_Breseq_{sample_name}.pdf")
