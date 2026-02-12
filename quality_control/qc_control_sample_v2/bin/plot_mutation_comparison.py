#!/usr/bin/env python3
"""
Create bar chart comparing HaplotypeCaller Joint Call vs AMP mutations
with exact and fuzzy match breakdown.
"""
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

# Data from comparison
vcf_total = 108
amp_total = 52

exact_matches = 6
fuzzy_matches = 41
total_matches = exact_matches + fuzzy_matches

# AMP breakdown
amp_exact = exact_matches
amp_fuzzy = fuzzy_matches
amp_unique = amp_total - total_matches

# VCF breakdown
vcf_exact = exact_matches
vcf_fuzzy = fuzzy_matches
vcf_unique = vcf_total - total_matches

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
# AMP bar
ax.bar(0, amp_exact, bar_width, label='Exact Match', color=color_exact, edgecolor='white', linewidth=2)
ax.bar(0, amp_fuzzy, bar_width, bottom=amp_exact, label='Fuzzy Match (100bp window)', color=color_fuzzy, edgecolor='white', linewidth=2)
ax.bar(0, amp_unique, bar_width, bottom=amp_exact+amp_fuzzy, label='Unique', color=color_unique, edgecolor='white', linewidth=2)

# VCF bar
ax.bar(1, vcf_exact, bar_width, color=color_exact, edgecolor='white', linewidth=2)
ax.bar(1, vcf_fuzzy, bar_width, bottom=vcf_exact, color=color_fuzzy, edgecolor='white', linewidth=2)
ax.bar(1, vcf_unique, bar_width, bottom=vcf_exact+vcf_fuzzy, color=color_unique, edgecolor='white', linewidth=2)

# Add value labels on bars
def add_value_labels(x_pos, values, bottoms, total):
    """Add value labels on stacked bars."""
    for i, (val, bottom) in enumerate(zip(values, bottoms)):
        if val > 3:  # Only show label if segment is big enough
            y_pos = bottom + val/2
            label = f'{val}'
            # Use dark text for yellow segment
            text_color = '#333333' if i == 1 else 'white'
            ax.text(x_pos, y_pos, label, ha='center', va='center',
                   fontsize=16, fontweight='bold', color=text_color)

add_value_labels(0, [amp_exact, amp_fuzzy, amp_unique],
                [0, amp_exact, amp_exact+amp_fuzzy], amp_total)
add_value_labels(1, [vcf_exact, vcf_fuzzy, vcf_unique],
                [0, vcf_exact, vcf_exact+vcf_fuzzy], vcf_total)

# Total labels on top
ax.text(0, amp_total + 3, f'{amp_total}', ha='center', va='bottom',
       fontsize=18, fontweight='bold')
ax.text(1, vcf_total + 3, f'{vcf_total}', ha='center', va='bottom',
       fontsize=18, fontweight='bold')

# Customize plot
ax.set_ylabel('Number of Mutations', fontweight='bold')
ax.set_xticks(x)
ax.set_xticklabels(['AMP', 'Joint-GATK-HC'], fontweight='bold')
ax.set_ylim(0, max(vcf_total, amp_total) * 1.2)

# Remove top and right spines
ax.spines['top'].set_visible(False)
ax.spines['right'].set_visible(False)
ax.tick_params(axis='both', which='both', length=5)

# Legend - positioned inside, upper right
legend_elements = [
    mpatches.Patch(facecolor=color_exact, label='Exact Match'),
    mpatches.Patch(facecolor=color_fuzzy, label='Fuzzy Match (100bp window)'),
    mpatches.Patch(facecolor=color_unique, label='Unique')
]
leg = ax.legend(handles=legend_elements, loc='upper center', fontsize=12,
                framealpha=0.8, edgecolor='black', fancybox=True,
                facecolor='white', frameon=True)
leg.get_frame().set_boxstyle('round')

# Add concordance annotation
concordance = total_matches / amp_total * 100
ax.text(0.02, 0.98, f'Concordance: {concordance:.1f}%\n(Sample: A0-F0-I1-R1)',
        transform=ax.transAxes, fontsize=12, va='top', ha='left',
        bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))

plt.tight_layout()
plt.savefig('comparison/mutation_comparison_barplot.png', dpi=300, bbox_inches='tight',
            facecolor='white', edgecolor='none')
plt.savefig('comparison/mutation_comparison_barplot.pdf', bbox_inches='tight',
            facecolor='white', edgecolor='none')

# Reset style
plt.style.use('default')
print("Bar chart saved to:")
print("  - comparison/mutation_comparison_barplot.png")
print("  - comparison/mutation_comparison_barplot.pdf")

# Also create a summary text file
with open('comparison/mutation_comparison_summary.txt', 'w') as f:
    f.write("MUTATION COMPARISON SUMMARY: HaplotypeCaller Joint Call vs AMP\n")
    f.write("=" * 70 + "\n\n")
    f.write("Sample: A0-F0-I1-R1\n\n")
    
    f.write("DATASET SIZES:\n")
    f.write(f"  AMP (Legacy Pipeline): {amp_total} mutations\n")
    f.write(f"  HaplotypeCaller Joint Call: {vcf_total} mutations\n\n")
    
    f.write("CONCORDANCE:\n")
    f.write(f"  Exact matches (same position): {exact_matches} ({exact_matches/amp_total*100:.1f}% of AMP)\n")
    f.write(f"  Fuzzy matches (100bp window): {fuzzy_matches} ({fuzzy_matches/amp_total*100:.1f}% of AMP)\n")
    f.write(f"  Total matches: {total_matches} ({total_matches/amp_total*100:.1f}% of AMP)\n\n")
    
    f.write("UNIQUE MUTATIONS:\n")
    f.write(f"  AMP-only: {amp_unique} ({amp_unique/amp_total*100:.1f}% of AMP)\n")
    f.write(f"  VCF-only: {vcf_unique} ({vcf_unique/vcf_total*100:.1f}% of VCF)\n\n")
    
    f.write("KEY FINDING:\n")
    f.write(f"  90.4% concordance when allowing 50bp window for variant position\n")
    f.write(f"  VCF detects 2× more variants, but most are low coverage (mean DP 7.3)\n")

print("Summary saved to: comparison/mutation_comparison_summary.txt")

