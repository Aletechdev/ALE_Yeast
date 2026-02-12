#!/usr/bin/env python3
"""
Create dot plot showing mutation depth (DP) by match category and type.
This version only considers Breseq-detected mutations (BRESEQ_FREQ > 0).
"""
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
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

def get_vcf_data(vcf_file, sample_name):
    """Extract VCF data for a specific sample.
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
    fuzzy = []
    for pos1 in breseq_pos - exact:
        for pos2 in vcf_pos.keys():
            if pos2 in exact:
                continue
            if pos1[0] == pos2[0] and 0 < abs(pos1[1] - pos2[1]) <= window:
                fuzzy.append(pos2)
                break
    return exact, fuzzy

# Get data - Breseq-only
breseq_positions = get_breseq_positions('output/A0-F0-I1-R1_AMP_mutations.tsv')
vcf_data = get_vcf_data('data/A0-F0-I1-R1.haplotypecaller.from_joint_calling_snpEff.ann.vcf.gz', 'ALE_Exp1_A0-F0-I1-R1')

# Classify mutations
exact, fuzzy = fuzzy_match(breseq_positions, vcf_data, window=50)
vcf_only = set(vcf_data.keys()) - exact - set(fuzzy)

print(f"Breseq-detected mutations: {len(breseq_positions)}")
print(f"Exact matches: {len(exact)}")
print(f"Fuzzy matches: {len(fuzzy)}")
print(f"Joint-GATK-HC only: {len(vcf_only)}")

# Organize data by category and type
categories = {
    f'Exact Match\n(n={len(exact)})': exact,
    f'Fuzzy Match\n(n={len(fuzzy)})': set(fuzzy),
    f'Joint-GATK-HC Only\n(n={len(vcf_only)})': vcf_only
}

# Type to marker mapping
type_markers = {
    'SNP': 'o',                    # circle
    'Insertion': '^',              # triangle up
    'Deletion': 'v',               # triangle down
    'Multi-allelic': 's',          # square
    'Poly-A': 'D',                 # diamond
    'Poly-T': 'D',                 # diamond
    'Poly-C': 'D',                 # diamond
    'Poly-G': 'D',                 # diamond
    'Poly-repeat': 'D',            # diamond
    'Other': 'x'                   # x
}

type_colors = {
    'SNP': '#E91E63',              # pink
    'Insertion': '#2196F3',        # blue
    'Deletion': '#FF9800',         # orange
    'Multi-allelic': '#9C27B0',    # purple
    'Poly-A': '#4CAF50',           # green
    'Poly-T': '#4CAF50',
    'Poly-C': '#4CAF50',
    'Poly-G': '#4CAF50',
    'Poly-repeat': '#4CAF50',
    'Other': '#607D8B'             # gray
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

# Create plot
fig, ax = plt.subplots(figsize=(12, 8))
fig.patch.set_facecolor('white')

# Simplified category labels for cleaner x-axis
category_labels = ['Exact Match', r'Fuzzy Match ($\pm$50bp window)', 'Joint-GATK-HC\nOnly']
x_positions = {cat: i for i, cat in enumerate(categories.keys())}

np.random.seed(42)

# Plot points
for category, positions in categories.items():
    x_base = x_positions[category]
    for pos in positions:
        dp = vcf_data[pos]['dp']
        var_type = vcf_data[pos]['type']

        # Add jitter to x position
        x_jitter = x_base + np.random.uniform(-0.25, 0.25)

        marker = type_markers.get(var_type, 'o')
        color = type_colors.get(var_type, '#607D8B')

        ax.scatter(x_jitter, dp, marker=marker, s=280, color=color,
                  alpha=0.5, edgecolors='white', linewidth=1.5)

# Customize plot
ax.set_ylabel('Informative depth (DP)', fontweight='bold')
ax.set_xlabel('Match Category', fontweight='bold')

ax.set_xticks(list(x_positions.values()))
ax.set_xticklabels(category_labels, fontweight='bold')

# Add horizontal lines for mean DP per category with labels
for category, positions in categories.items():
    if positions:
        dps = [vcf_data[pos]['dp'] for pos in positions]
        mean_dp = np.mean(dps)
        x_pos = x_positions[category]
        ax.hlines(mean_dp, x_pos - 0.35, x_pos + 0.35, colors='black', linewidth=3, zorder=4)
        ax.text(x_pos + 0.4, mean_dp, f'{mean_dp:.0f}', fontsize=12, fontweight='bold',
                va='center', ha='left')

# Remove top and right spines
ax.spines['top'].set_visible(False)
ax.spines['right'].set_visible(False)
ax.tick_params(axis='both', which='both', length=5)

# Set y limit
ax.set_ylim(0, max([vcf_data[pos]['dp'] for pos in vcf_data.keys()]) * 1.1)

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
    plt.Line2D([0], [0], color='black', linestyle='-', linewidth=3, label='Mean DP'),
]

leg = ax.legend(handles=type_legend_elements, loc='lower left', fontsize=11,
                framealpha=0.8, edgecolor='black', fancybox=True,
                facecolor='white', frameon=True)
leg.get_frame().set_boxstyle('round')

# Add sample and counts annotation
stats_text = f'Sample: A0-F0-I1-R1\nBreseq-only AMP mutations\n\nExact: n={len(exact)}\nFuzzy: n={len(fuzzy)}\nJoint-only: n={len(vcf_only)}'
ax.text(0.02, 0.98, stats_text, transform=ax.transAxes, fontsize=11, va='top', ha='left',
        bbox=dict(boxstyle='round', facecolor='white', alpha=0.8, edgecolor='black'))

plt.tight_layout()
plt.savefig('comparison/mutation_dp_dotplot_HC_Breseq.png', dpi=300, bbox_inches='tight',
            facecolor='white', edgecolor='none')
plt.savefig('comparison/mutation_dp_dotplot_HC_Breseq.pdf', bbox_inches='tight',
            facecolor='white', edgecolor='none')

plt.style.use('default')

print("\nDot plot saved to:")
print("  - comparison/mutation_dp_dotplot_HC_Breseq.png")
print("  - comparison/mutation_dp_dotplot_HC_Breseq.pdf")
