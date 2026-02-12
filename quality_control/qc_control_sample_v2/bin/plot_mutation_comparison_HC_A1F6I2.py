#!/usr/bin/env python3
"""
Create bar chart comparing HaplotypeCaller Joint Call vs Breseq (AMP) mutations
with exact and fuzzy match breakdown for sample A1-F6-I2-R1.
"""
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
import csv
import subprocess

def get_breseq_positions(tsv_file):
    """Load AMP mutations detected by Breseq (BRESEQ_FREQ > 0)."""
    positions = set()
    with open(tsv_file, 'r') as f:
        reader = csv.DictReader(f, delimiter='\t')
        for row in reader:
            if row['DETECTED'] == 'YES' and float(row['BRESEQ_FREQ']) > 0:
                positions.add((row['CHROM'], int(row['POS'])))
    return positions

def get_vcf_positions(vcf_file, sample_name):
    """Extract variant positions from VCF for a specific sample.
    Filters: PASS only (includes multiallelic sites).
    """
    cmd = ['bcftools', 'query',
           '-i', 'FILTER="PASS"',
           '-f', '%CHROM\t%POS\t%ALT\t[%GT]\n',
           '-s', sample_name, vcf_file]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)

    positions = set()
    for line in result.stdout.strip().split('\n'):
        if not line:
            continue
        fields = line.split('\t')
        if len(fields) >= 4:
            chrom, pos, alt, gt = fields[0], int(fields[1]), fields[2], fields[3]
            # Include multiallelic sites - check for non-ref genotype
            if gt not in ['0', '0/0', './.', '.', '0/0/0', '0|0']:
                positions.add((chrom, pos))
    return positions

def fuzzy_match(breseq_positions, vcf_positions, window=50):
    """Find exact and fuzzy matches between two position sets."""
    exact = breseq_positions & vcf_positions
    fuzzy_breseq = set()  # Breseq positions that had a fuzzy match
    fuzzy_vcf = set()     # VCF positions that had a fuzzy match

    for pos1 in breseq_positions - exact:
        for pos2 in vcf_positions:
            if pos2 in exact:
                continue
            if pos1[0] == pos2[0] and 0 < abs(pos1[1] - pos2[1]) <= window:
                fuzzy_breseq.add(pos1)
                fuzzy_vcf.add(pos2)
                break

    return exact, fuzzy_breseq, fuzzy_vcf

# Sample configuration
sample_name = 'A1-F6-I2-R1'
tsv_file = f'output/{sample_name}_AMP_mutations.tsv'
vcf_file = 'data/HaplotypeCaller_joint_calling_soft_filtered_snpEff.ann.vcf.gz'
vcf_sample = f'ALE_Exp1_{sample_name}'

# Get positions
breseq_positions = get_breseq_positions(tsv_file)
vcf_positions = get_vcf_positions(vcf_file, vcf_sample)

# Calculate matches
exact, fuzzy_breseq, fuzzy_vcf = fuzzy_match(breseq_positions, vcf_positions, window=50)

# Calculate counts
breseq_total = len(breseq_positions)
vcf_total = len(vcf_positions)
exact_matches = len(exact)
fuzzy_breseq_count = len(fuzzy_breseq)
fuzzy_vcf_count = len(fuzzy_vcf)

# Breseq-only breakdown
breseq_exact = exact_matches
breseq_fuzzy = fuzzy_breseq_count
breseq_unique = breseq_total - exact_matches - fuzzy_breseq_count

# VCF breakdown (relative to Breseq) - use actual VCF fuzzy positions
vcf_exact = exact_matches
vcf_fuzzy = fuzzy_vcf_count
vcf_unique = vcf_total - exact_matches - fuzzy_vcf_count

print(f"Sample: {sample_name}")
print(f"Breseq-detected mutations: {breseq_total}")
print(f"Joint-GATK-HC variants: {vcf_total}")
print(f"Exact matches: {exact_matches}")
print(f"Fuzzy matches (50bp window) - Breseq positions: {fuzzy_breseq_count}")
print(f"Fuzzy matches (50bp window) - VCF positions: {fuzzy_vcf_count}")
print(f"Breseq-only unique: {breseq_unique}")
print(f"VCF-only unique: {vcf_unique}")

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

# Create figure
fig, ax = plt.subplots(figsize=(10, 7))
fig.patch.set_facecolor('white')

# Bar positions
bar_width = 0.5
x = np.arange(2)

# Colors - cleaner palette
color_exact = '#2ECC71'    # Green for exact
color_fuzzy = '#F1C40F'    # Yellow for fuzzy
color_unique = '#BDC3C7'   # Light gray for unique

# Stacked bars with edge
# Breseq bar
ax.bar(0, breseq_exact, bar_width, label='Exact Match', color=color_exact, edgecolor='white', linewidth=2)
ax.bar(0, breseq_fuzzy, bar_width, bottom=breseq_exact, label=r'Fuzzy Match ($\pm$50bp window)', color=color_fuzzy, edgecolor='white', linewidth=2)
ax.bar(0, breseq_unique, bar_width, bottom=breseq_exact+breseq_fuzzy, label='Unique', color=color_unique, edgecolor='white', linewidth=2)

# VCF bar
ax.bar(1, vcf_exact, bar_width, color=color_exact, edgecolor='white', linewidth=2)
ax.bar(1, vcf_fuzzy, bar_width, bottom=vcf_exact, color=color_fuzzy, edgecolor='white', linewidth=2)
ax.bar(1, vcf_unique, bar_width, bottom=vcf_exact+vcf_fuzzy, color=color_unique, edgecolor='white', linewidth=2)

# Add value labels on bars
def add_value_labels(x_pos, values, bottoms, total):
    """Add value labels on stacked bars."""
    for i, (val, bottom) in enumerate(zip(values, bottoms)):
        if val > 5:  # Only show label if segment is big enough
            y_pos = bottom + val/2
            label = f'{val}'
            text_color = '#333333' if i == 1 else 'white'
            ax.text(x_pos, y_pos, label, ha='center', va='center',
                   fontsize=16, fontweight='bold', color=text_color)

add_value_labels(0, [breseq_exact, breseq_fuzzy, breseq_unique],
                [0, breseq_exact, breseq_exact+breseq_fuzzy], breseq_total)
add_value_labels(1, [vcf_exact, vcf_fuzzy, vcf_unique],
                [0, vcf_exact, vcf_exact+vcf_fuzzy], vcf_total)

# Total labels on top
ax.text(0, breseq_total + 3, f'{breseq_total}', ha='center', va='bottom',
       fontsize=18, fontweight='bold')
ax.text(1, vcf_total + 3, f'{vcf_total}', ha='center', va='bottom',
       fontsize=18, fontweight='bold')

# Customize plot
ax.set_ylabel('Number of Mutations', fontweight='bold')
ax.set_xticks(x)
ax.set_xticklabels(['Breseq (AMP)', 'Joint-GATK-HC (ANP)'], fontweight='bold')
ax.set_ylim(0, max(vcf_total, breseq_total) * 1.2)

# Remove top and right spines
ax.spines['top'].set_visible(False)
ax.spines['right'].set_visible(False)
ax.tick_params(axis='both', which='both', length=5)

# Legend - positioned inside, upper right
legend_elements = [
    mpatches.Patch(facecolor=color_exact, label='Exact Match'),
    mpatches.Patch(facecolor=color_fuzzy, label=r'Fuzzy Match ($\pm$50bp window)'),
    mpatches.Patch(facecolor=color_unique, label='Unique')
]
leg = ax.legend(handles=legend_elements, loc='upper right', fontsize=12,
                framealpha=0.8, edgecolor='black', fancybox=True,
                facecolor='white', frameon=True)
leg.get_frame().set_boxstyle('round')

# Add concordance annotation
total_breseq_matches = exact_matches + fuzzy_breseq_count
if breseq_total > 0:
    concordance = total_breseq_matches / breseq_total * 100
else:
    concordance = 0
ax.text(0.5, 0.98, f'Concordance: {concordance:.1f}%\n(Sample: {sample_name})\n\nBreseq-only AMP mutations',
        transform=ax.transAxes, fontsize=12, va='top', ha='center',
        bbox=dict(boxstyle='round', facecolor='white', alpha=0.8, edgecolor='black'))

plt.tight_layout()
plt.savefig(f'comparison/mutation_comparison_barplot_HC_{sample_name}.png', dpi=300, bbox_inches='tight',
            facecolor='white', edgecolor='none')
plt.savefig(f'comparison/mutation_comparison_barplot_HC_{sample_name}.pdf', bbox_inches='tight',
            facecolor='white', edgecolor='none')

# Reset style
plt.style.use('default')
print(f"\nBar chart saved to:")
print(f"  - comparison/mutation_comparison_barplot_HC_{sample_name}.png")
print(f"  - comparison/mutation_comparison_barplot_HC_{sample_name}.pdf")

# Also create a summary text file
with open(f'comparison/mutation_comparison_summary_HC_{sample_name}.txt', 'w') as f:
    f.write(f"MUTATION COMPARISON SUMMARY: HaplotypeCaller Joint Call vs Breseq (AMP)\n")
    f.write("=" * 70 + "\n\n")
    f.write(f"Sample: {sample_name}\n\n")

    f.write("DATASET SIZES:\n")
    f.write(f"  Breseq (AMP - BRESEQ_FREQ > 0): {breseq_total} mutations\n")
    f.write(f"  HaplotypeCaller Joint Call: {vcf_total} mutations\n\n")

    f.write("CONCORDANCE:\n")
    total_breseq_matches = exact_matches + fuzzy_breseq_count
    if breseq_total > 0:
        f.write(f"  Exact matches (same position): {exact_matches} ({exact_matches/breseq_total*100:.1f}% of Breseq)\n")
        f.write(f"  Fuzzy matches (50bp window) - Breseq: {fuzzy_breseq_count} ({fuzzy_breseq_count/breseq_total*100:.1f}% of Breseq)\n")
        f.write(f"  Fuzzy matches (50bp window) - VCF: {fuzzy_vcf_count}\n")
        f.write(f"  Total Breseq matches: {total_breseq_matches} ({total_breseq_matches/breseq_total*100:.1f}% of Breseq)\n\n")
    else:
        f.write(f"  Exact matches: {exact_matches}\n")
        f.write(f"  Fuzzy matches (50bp window) - Breseq: {fuzzy_breseq_count}\n")
        f.write(f"  Fuzzy matches (50bp window) - VCF: {fuzzy_vcf_count}\n")
        f.write(f"  Total Breseq matches: {total_breseq_matches}\n\n")

    f.write("UNIQUE MUTATIONS:\n")
    if breseq_total > 0:
        f.write(f"  Breseq-only: {breseq_unique} ({breseq_unique/breseq_total*100:.1f}% of Breseq)\n")
    else:
        f.write(f"  Breseq-only: {breseq_unique}\n")
    if vcf_total > 0:
        f.write(f"  VCF-only: {vcf_unique} ({vcf_unique/vcf_total*100:.1f}% of VCF)\n\n")
    else:
        f.write(f"  VCF-only: {vcf_unique}\n\n")

    f.write("KEY FINDING:\n")
    f.write(f"  {concordance:.1f}% concordance when allowing 50bp window for variant position\n")
    f.write(f"  Breseq detected {breseq_total} mutations vs Joint-GATK-HC {vcf_total} variants\n")

print(f"Summary saved to: comparison/mutation_comparison_summary_HC_{sample_name}.txt")
