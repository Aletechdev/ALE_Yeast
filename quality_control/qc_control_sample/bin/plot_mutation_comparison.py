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

# Create figure
fig, ax = plt.subplots(figsize=(14, 8))

# Bar positions
bar_width = 0.6
x = np.arange(2)

# Colors
color_exact = '#2E7D32'    # Dark green
color_fuzzy = '#66BB6A'    # Light green  
color_unique = '#9E9E9E'   # Gray

# Stacked bars
# AMP bar
ax.bar(0, amp_exact, bar_width, label='Exact Match', color=color_exact)
ax.bar(0, amp_fuzzy, bar_width, bottom=amp_exact, label='Fuzzy Match (≤50bp)', color=color_fuzzy)
ax.bar(0, amp_unique, bar_width, bottom=amp_exact+amp_fuzzy, label='Unique (no match)', color=color_unique)

# VCF bar
ax.bar(1, vcf_exact, bar_width, color=color_exact)
ax.bar(1, vcf_fuzzy, bar_width, bottom=vcf_exact, color=color_fuzzy)
ax.bar(1, vcf_unique, bar_width, bottom=vcf_exact+vcf_fuzzy, color=color_unique)

# Add value labels on bars
def add_value_labels(x_pos, values, bottoms):
    """Add value labels on stacked bars."""
    for i, (val, bottom) in enumerate(zip(values, bottoms)):
        if val > 0:
            y_pos = bottom + val/2
            label = f'{val}\n({val/sum(values)*100:.1f}%)'
            ax.text(x_pos, y_pos, label, ha='center', va='center', 
                   fontsize=11, fontweight='bold', color='white')

add_value_labels(0, [amp_exact, amp_fuzzy, amp_unique], 
                [0, amp_exact, amp_exact+amp_fuzzy])
add_value_labels(1, [vcf_exact, vcf_fuzzy, vcf_unique], 
                [0, vcf_exact, vcf_exact+vcf_fuzzy])

# Total labels on top
ax.text(0, amp_total + 2, f'Total: {amp_total}', ha='center', va='bottom', 
       fontsize=14, fontweight='bold')
ax.text(1, vcf_total + 2, f'Total: {vcf_total}', ha='center', va='bottom', 
       fontsize=14, fontweight='bold')

# Customize plot
ax.set_ylabel('Number of Mutations', fontsize=14, fontweight='bold')
ax.set_title('SNP & InDel Calling Comparison: HaplotypeCaller Joint Call vs AMP\nSample: A0-F0-I1-R1', 
            fontsize=16, fontweight='bold', pad=20)
ax.set_xticks(x)
ax.set_xticklabels(['AMP\n(Breseq + HaplotypeCaller single call)', 'HaplotypeCaller\n(Joint Call)'], 
                   fontsize=13, fontweight='bold')
ax.set_ylim(0, max(vcf_total, amp_total) * 1.15)

# Grid
ax.yaxis.grid(True, linestyle='--', alpha=0.3)
ax.set_axisbelow(True)

# Legend - positioned outside plot area
legend_elements = [
    mpatches.Patch(color=color_exact, label=f'Exact Match (same position): {exact_matches}'),
    mpatches.Patch(color=color_fuzzy, label=f'Fuzzy Match (within 50bp): {fuzzy_matches}'),
    mpatches.Patch(color=color_unique, label='Unique (no match in other pipeline)')
]
ax.legend(handles=legend_elements, loc='upper left', bbox_to_anchor=(1.02, 1),
         fontsize=11, framealpha=0.9, borderaxespad=0)

plt.tight_layout()
plt.savefig('comparison/mutation_comparison_barplot.png', dpi=300, bbox_inches='tight')
plt.savefig('comparison/mutation_comparison_barplot.pdf', bbox_inches='tight')
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
    f.write(f"  Fuzzy matches (≤50bp): {fuzzy_matches} ({fuzzy_matches/amp_total*100:.1f}% of AMP)\n")
    f.write(f"  Total matches: {total_matches} ({total_matches/amp_total*100:.1f}% of AMP)\n\n")
    
    f.write("UNIQUE MUTATIONS:\n")
    f.write(f"  AMP-only: {amp_unique} ({amp_unique/amp_total*100:.1f}% of AMP)\n")
    f.write(f"  VCF-only: {vcf_unique} ({vcf_unique/vcf_total*100:.1f}% of VCF)\n\n")
    
    f.write("KEY FINDING:\n")
    f.write(f"  90.4% concordance when allowing 50bp window for variant position\n")
    f.write(f"  VCF detects 2× more variants, but most are low coverage (mean DP 7.3)\n")

print("Summary saved to: comparison/mutation_comparison_summary.txt")

