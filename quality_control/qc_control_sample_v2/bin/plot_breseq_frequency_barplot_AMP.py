#!/usr/bin/env python3
"""
Create stacked barplot showing Breseq mutation frequency distribution by sample group.
Uses AMP-filtered TSV files (output/*_AMP_mutations.tsv).

Only counts mutations where DETECTED='YES' and BRESEQ_FREQ > 0 (breseq-detected mutations).
This gives curated, high-confidence mutation counts matching the comparison plots.
"""
import matplotlib.pyplot as plt
import glob
import csv
import numpy as np
from collections import defaultdict

def parse_amp_tsv(tsv_file):
    """Parse AMP TSV file and extract breseq-detected mutation frequencies.

    Only includes mutations where DETECTED='YES' and BRESEQ_FREQ > 0.
    Returns list of BRESEQ_FREQ values.
    """
    frequencies = []

    with open(tsv_file, 'r') as f:
        reader = csv.DictReader(f, delimiter='\t')
        for row in reader:
            if row['DETECTED'] == 'YES':
                breseq_freq = float(row['BRESEQ_FREQ'])
                if breseq_freq > 0:
                    frequencies.append(breseq_freq)

    return frequencies

def classify_sample_group(filename):
    """Classify sample into groups based on filename pattern."""
    # Extract sample ID from filename (e.g., "A1-F6-I2-R1_AMP_mutations.tsv" -> "A1-F6-I2-R1")
    basename = filename.split('/')[-1].replace('_AMP_mutations.tsv', '')
    parts = basename.split('-')

    if len(parts) >= 3:
        # Parse A{a}-F{f}-I{i}-R{r} pattern
        a_val = int(parts[0][1:])  # Remove 'A' prefix
        f_val = int(parts[1][1:])  # Remove 'F' prefix
        i_val = int(parts[2][1:])  # Remove 'I' prefix

        # Classify based on values
        if a_val == 0 and f_val == 0:
            return 'Ancestral', basename
        elif i_val == 1:
            return 'Evolved', basename
        elif i_val in [2, 3]:
            return 'Genome-Shuffled', basename

    return 'Unknown', basename

def categorize_frequencies(frequencies):
    """Categorize frequencies into high/mid/low."""
    high = sum(1 for f in frequencies if f >= 0.9)
    mid = sum(1 for f in frequencies if 0.5 <= f < 0.9)
    low = sum(1 for f in frequencies if f < 0.5)
    return high, mid, low

# Get all AMP TSV files
tsv_files = glob.glob('output/*_AMP_mutations.tsv')
print(f"Found {len(tsv_files)} AMP TSV files")

# Organize data by group
groups = defaultdict(lambda: {'high': [], 'mid': [], 'low': [], 'samples': []})

for tsv_file in sorted(tsv_files):
    group, sample_id = classify_sample_group(tsv_file)

    if group == 'Unknown':
        continue

    frequencies = parse_amp_tsv(tsv_file)
    if not frequencies:
        print(f"{sample_id} ({group}): 0 mutations (no BRESEQ_FREQ > 0)")
        continue

    high, mid, low = categorize_frequencies(frequencies)

    groups[group]['high'].append(high)
    groups[group]['mid'].append(mid)
    groups[group]['low'].append(low)
    groups[group]['samples'].append(sample_id)

    print(f"{sample_id} ({group}): {len(frequencies)} mutations - High: {high}, Mid: {mid}, Low: {low}")

# Calculate totals for each group
group_order = ['Ancestral', 'Evolved', 'Genome-Shuffled']
group_labels = []
high_totals = []
mid_totals = []
low_totals = []
total_counts = []

for group in group_order:
    if group not in groups or not groups[group]['high']:
        continue

    high_sum = sum(groups[group]['high'])
    mid_sum = sum(groups[group]['mid'])
    low_sum = sum(groups[group]['low'])
    total = high_sum + mid_sum + low_sum

    # Create label with sample count
    n_samples = len(groups[group]['samples'])
    if group == 'Ancestral':
        label = f"Ancestral\n(A0-F0-*, n={n_samples})"
    elif group == 'Evolved':
        label = f"Evolved\n(*-*-I1-*, n={n_samples})"
    else:  # Genome-Shuffled
        label = f"Genome-Shuffled\n(*-*-I2/I3-*, n={n_samples})"

    group_labels.append(label)
    high_totals.append(high_sum)
    mid_totals.append(mid_sum)
    low_totals.append(low_sum)
    total_counts.append(total)

print(f"\nGroup totals:")
for i, label in enumerate(group_labels):
    print(f"{label.split()[0]}: Total={total_counts[i]}, High={high_totals[i]}, Mid={mid_totals[i]}, Low={low_totals[i]}")

# Set up presentation style - match VCF plot
plt.style.use('seaborn-v0_8-whitegrid')
plt.rcParams.update({
    'font.family': 'sans-serif',
    'font.size': 12,
    'axes.labelsize': 14,
    'xtick.labelsize': 12,
    'ytick.labelsize': 12,
    'figure.facecolor': 'white',
    'axes.facecolor': 'white',
    'axes.edgecolor': '#333333',
    'axes.linewidth': 1.5,
})

# Create stacked bar plot - match VCF plot layout
fig, ax = plt.subplots(figsize=(10, 7))
fig.patch.set_facecolor('white')

x = np.arange(len(group_labels))
width = 0.6

# Create stacked bars with exact colors from VCF barplot (Wong colorblind-safe palette)
color_high = '#0072B2'   # Blue for high freq (>=0.9)
color_mid = '#E69F00'    # Orange/Amber for mid freq (0.5-0.9)
color_low = '#CC79A7'    # Pink/Magenta for low freq (<0.5)

bars1 = ax.bar(x, high_totals, width, label='High Freq (>=0.9)', color=color_high,
               edgecolor='white', linewidth=1.5)
bars2 = ax.bar(x, mid_totals, width, bottom=high_totals, label='Mid Freq (0.5-0.9)',
               color=color_mid, edgecolor='white', linewidth=1.5)

# Calculate bottom for low freq bars
low_bottom = [high_totals[i] + mid_totals[i] for i in range(len(group_labels))]
bars3 = ax.bar(x, low_totals, width, bottom=low_bottom, label='Low Freq (<0.5)',
               color=color_low, edgecolor='white', linewidth=1.5)

# Add value labels on bars
for i, (h, m, l, total) in enumerate(zip(high_totals, mid_totals, low_totals, total_counts)):
    # Label for high freq
    if h > 0:
        height = h / 2
        ax.text(i, height, f'{h} ({h/total*100:.0f}%)', ha='center', va='center',
                fontsize=11, fontweight='bold', color='white')

    # Label for mid freq
    if m > 0:
        height = h + m / 2
        ax.text(i, height, f'{m} ({m/total*100:.0f}%)', ha='center', va='center',
                fontsize=11, fontweight='bold', color='white')

    # Label for low freq
    if l > 0:
        height = h + m + l / 2
        ax.text(i, height, f'{l} ({l/total*100:.0f}%)', ha='center', va='center',
                fontsize=11, fontweight='bold', color='white')

    # Total count above bar
    ax.text(i, total + max(total_counts) * 0.05, f'n={total}', ha='center', va='bottom',
            fontsize=13, fontweight='bold')

# Customize plot - match VCF plot layout
ax.set_ylabel('Number of Mutations', fontweight='bold')
ax.set_title('Mutation Frequency Distribution by Sample Group\n(AMP-Filtered Breseq Mutations, BRESEQ_FREQ > 0)',
             fontweight='bold', pad=15)
ax.set_xticks(x)
ax.set_xticklabels(group_labels, fontweight='bold')
ax.set_ylim(0, max(total_counts) * 1.25)
ax.set_xlim(-0.5, len(group_labels) - 0.5)

# Remove top and right spines
ax.spines['top'].set_visible(False)
ax.spines['right'].set_visible(False)

# Legend - position upper left to avoid overlap
ax.legend(loc='upper left', fontsize=11, framealpha=0.9,
          edgecolor='black', fancybox=True)

# Add note about high frequency counts below x-axis
high_note = f'High Freq (>=0.9): Ancestral {high_totals[0]} ({high_totals[0]/total_counts[0]*100:.0f}%),  Evolved {high_totals[1]} ({high_totals[1]/total_counts[1]*100:.0f}%),  Genome-Shuffled {high_totals[2]} ({high_totals[2]/total_counts[2]*100:.0f}%)'
ax.text(0.5, -0.10, high_note, ha='center', va='top', fontsize=11,
        transform=ax.transAxes, fontweight='bold', color=color_high)

plt.tight_layout()
plt.savefig('comparison/breseq_frequency_percentage_barplot_AMP.png', dpi=300,
            bbox_inches='tight', facecolor='white', edgecolor='none')
plt.savefig('comparison/breseq_frequency_percentage_barplot_AMP.pdf',
            bbox_inches='tight', facecolor='white', edgecolor='none')
plt.close()

# Reset style
plt.style.use('default')

print(f"\nBarplot saved to:")
print(f"  - comparison/breseq_frequency_percentage_barplot_AMP.png")
print(f"  - comparison/breseq_frequency_percentage_barplot_AMP.pdf")
