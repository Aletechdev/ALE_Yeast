#!/usr/bin/env python3
"""
Create dot plot showing mutation depth (DP) by match category and type.
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

def get_csv_positions(csv_file):
    positions = set()
    with open(csv_file, 'r') as f:
        reader = csv.DictReader(f, delimiter='\t')
        for row in reader:
            if row['DETECTED'] == 'YES':
                positions.add((row['CHROM'], int(row['POS'])))
    return positions

def get_vcf_data(vcf_file, sample_name):
    data = {}
    cmd = ['bcftools', 'query',
           '-f', '%CHROM\t%POS\t%REF\t%ALT\t[%GT]\t[%DP]\n',
           '-s', sample_name, str(vcf_file)]
    
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    
    for line in result.stdout.strip().split('\n'):
        if not line:
            continue
        fields = line.split('\t')
        if len(fields) >= 6:
            chrom, pos, ref, alt, gt, dp = fields[0], int(fields[1]), fields[2], fields[3], fields[4], fields[5]
            if gt not in ['0', '0/0', './.', '.', '0/0/0'] and dp.isdigit():
                var_type = classify_variant_type(ref, alt)
                data[(chrom, pos)] = {'dp': int(dp), 'type': var_type}
    return data

def fuzzy_match(csv_pos, vcf_pos, window=50):
    exact = csv_pos & set(vcf_pos.keys())
    fuzzy = []
    for pos1 in csv_pos - exact:
        for pos2 in vcf_pos.keys():
            if pos2 in exact:
                continue
            if pos1[0] == pos2[0] and 0 < abs(pos1[1] - pos2[1]) <= window:
                fuzzy.append(pos2)
                break
    return exact, fuzzy

# Get data
csv_positions = get_csv_positions('output/A0-F0-I1-R1_AMP_mutations.tsv')
vcf_data = get_vcf_data('data/A0-F0-I1-R1.haplotypecaller.from_joint_calling_snpEff.ann.vcf.gz', 'ALE_Exp1_A0-F0-I1-R1')

# Classify mutations
exact, fuzzy = fuzzy_match(csv_positions, vcf_data, window=50)
vcf_only = set(vcf_data.keys()) - exact - set(fuzzy)

# Organize data by category and type
categories = {
    'Exact Match\n(n=6)': exact,
    'Fuzzy Match\n(n=41)': set(fuzzy),
    'HaplotypeCaller Joint Call only\n(n=61)': vcf_only
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

# Create plot
fig, ax = plt.subplots(figsize=(14, 10))

x_positions = {cat: i for i, cat in enumerate(categories.keys())}

# Plot points
for category, positions in categories.items():
    x_base = x_positions[category]
    for pos in positions:
        dp = vcf_data[pos]['dp']
        var_type = vcf_data[pos]['type']
        
        # Add jitter to x position
        x_jitter = x_base + np.random.uniform(-0.2, 0.2)
        
        marker = type_markers.get(var_type, 'o')
        color = type_colors.get(var_type, '#607D8B')
        
        ax.scatter(x_jitter, dp, marker=marker, s=160, color=color, 
                  alpha=0.7, edgecolors='black', linewidth=0.5)

# Customize plot
ax.set_ylabel('Depth (DP)', fontsize=14, fontweight='bold')
ax.set_xlabel('Match Category', fontsize=14, fontweight='bold')
ax.set_title('Mutation Depth Distribution by Match Category and Variant Type\nSample: A0-F0-I1-R1', 
            fontsize=16, fontweight='bold', pad=20)

ax.set_xticks(list(x_positions.values()))
ax.set_xticklabels(list(x_positions.keys()), fontsize=12, fontweight='bold')

# Add horizontal lines for mean DP per category
for category, positions in categories.items():
    if positions:
        dps = [vcf_data[pos]['dp'] for pos in positions]
        mean_dp = np.mean(dps)
        x_pos = x_positions[category]
        ax.hlines(mean_dp, x_pos - 0.3, x_pos + 0.3, colors='red', linestyles='--', 
                 linewidth=2, alpha=0.7, label=f'Mean DP' if category == list(categories.keys())[0] else '')

# Grid
ax.yaxis.grid(True, linestyle='--', alpha=0.3)
ax.set_axisbelow(True)

# Create legend
legend_elements = [
    mpatches.Patch(color='red', label='Mean DP (dashed line)')
]

# Add type legend
type_legend_elements = [
    plt.Line2D([0], [0], marker='o', color='w', markerfacecolor='#E91E63', 
              markersize=10, label='SNP', markeredgecolor='black', markeredgewidth=0.5),
    plt.Line2D([0], [0], marker='^', color='w', markerfacecolor='#2196F3', 
              markersize=10, label='Insertion', markeredgecolor='black', markeredgewidth=0.5),
    plt.Line2D([0], [0], marker='v', color='w', markerfacecolor='#FF9800', 
              markersize=10, label='Deletion', markeredgecolor='black', markeredgewidth=0.5),
    plt.Line2D([0], [0], marker='s', color='w', markerfacecolor='#9C27B0', 
              markersize=10, label='Multi-allelic', markeredgecolor='black', markeredgewidth=0.5),
    plt.Line2D([0], [0], marker='D', color='w', markerfacecolor='#4CAF50', 
              markersize=10, label='Poly-repeat', markeredgecolor='black', markeredgewidth=0.5),
]

# Add mean DP line to legend
legend_elements.append(plt.Line2D([0], [0], color='red', linestyle='--', linewidth=2, label='Mean DP'))
# Two legends
legend1 = ax.legend(handles=type_legend_elements, loc='upper right', 
                    title='Variant Type', fontsize=10, title_fontsize=11)

# Shift the Mean DP legend downward slightly
legend2 = ax.legend(handles=[legend_elements[-1]], 
                    loc='upper right', 
                    fontsize=10,
                    bbox_to_anchor=(1, 0.83))  # <-- lower Y from 1.0 to e.g. 0.88

ax.add_artist(legend1)

# Add statistics text
stats_text = []
for category, positions in categories.items():
    if positions:
        dps = [vcf_data[pos]['dp'] for pos in positions]
        stats_text.append(f"{category.split(chr(10))[0]}: Mean={np.mean(dps):.1f}, Median={np.median(dps):.0f}")

ax.text(0.02, 0.98, '\n'.join(stats_text), transform=ax.transAxes,
       fontsize=10, verticalalignment='top',
       bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))

plt.tight_layout()
plt.savefig('comparison/mutation_dp_dotplot.png', dpi=300, bbox_inches='tight')
plt.savefig('comparison/mutation_dp_dotplot.pdf', bbox_inches='tight')

print("Dot plot saved to:")
print("  - comparison/mutation_dp_dotplot.png")
print("  - comparison/mutation_dp_dotplot.pdf")

