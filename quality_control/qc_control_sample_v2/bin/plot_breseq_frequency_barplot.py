#!/usr/bin/env python3
"""
Create stacked barplot showing Breseq mutation frequency distribution by sample group.
Uses Breseq .gd output files.

Counts actual mutation entries (SNP, INS, DEL, SUB, MOB, AMP, CON, INV)
and extracts their frequencies from supporting evidence (RA, JC, MC entries).
"""
import matplotlib.pyplot as plt
import glob
import re
import numpy as np
from collections import defaultdict

def parse_breseq_gd(gd_file):
    """Parse Breseq .gd file and extract mutation frequencies from evidence.

    Counts actual mutation entries (SNP, INS, DEL, SUB, MOB, AMP, CON, INV)
    and looks up their frequencies from supporting evidence entries (RA, JC, MC).
    """
    # Mutation entry types in breseq .gd format
    mutation_types = {'SNP', 'INS', 'DEL', 'SUB', 'MOB', 'AMP', 'CON', 'INV'}
    # Evidence entry types that have frequency
    evidence_types = {'RA', 'JC', 'MC'}

    # First pass: build evidence ID -> frequency lookup
    evidence_freq = {}
    mutations = []  # List of (mutation_id, evidence_ids)

    with open(gd_file, 'r') as f:
        for line in f:
            if line.startswith('#'):
                continue

            fields = line.strip().split('\t')
            if len(fields) < 3:
                continue

            entry_type = fields[0]
            entry_id = fields[1]

            if entry_type in evidence_types:
                # Extract frequency from evidence entry
                for field in fields:
                    if field.startswith('frequency='):
                        freq_str = field.split('=')[1]
                        # Handle NA values
                        if freq_str != 'NA':
                            try:
                                freq = float(freq_str)
                                evidence_freq[entry_id] = freq
                            except ValueError:
                                pass
                        break

            elif entry_type in mutation_types:
                # Mutation entry: field 3 contains evidence IDs (comma-separated)
                evidence_ids = fields[2].split(',') if len(fields) > 2 else []
                mutations.append((entry_id, evidence_ids))

    # Second pass: get frequency for each mutation from its evidence
    frequencies = []
    for mut_id, ev_ids in mutations:
        # Get frequency from first available evidence
        freq = None
        for ev_id in ev_ids:
            if ev_id in evidence_freq:
                freq = evidence_freq[ev_id]
                break

        if freq is not None:
            frequencies.append(freq)
        else:
            # Default to 1.0 if no evidence found (shouldn't happen)
            frequencies.append(1.0)

    return frequencies

def classify_sample_group(filename):
    """Classify sample into groups based on filename pattern."""
    # Extract sample ID from filename (e.g., "0-0-1-1_output.gd" -> "0-0-1-1")
    basename = filename.split('/')[-1].replace('_output.gd', '')
    parts = basename.split('-')

    if len(parts) >= 3:
        # Parse A-F-I-R pattern
        a_val = int(parts[0])
        f_val = int(parts[1])
        i_val = int(parts[2])

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

# Get all .gd files
gd_files = glob.glob('data/Breseq_out_gd/*_output.gd')
print(f"Found {len(gd_files)} Breseq .gd files")

# Organize data by group
groups = defaultdict(lambda: {'high': [], 'mid': [], 'low': [], 'samples': []})

for gd_file in sorted(gd_files):
    group, sample_id = classify_sample_group(gd_file)

    if group == 'Unknown':
        continue

    frequencies = parse_breseq_gd(gd_file)
    if not frequencies:
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

    # Calculate sample range for label
    samples = groups[group]['samples']
    sample_parts = [s.split('-') for s in samples]

    if group == 'Ancestral':
        label = f"Ancestral\n(A0-F0-*)"
    elif group == 'Evolved':
        a_vals = set(int(p[0]) for p in sample_parts if len(p) >= 1)
        f_vals = set(int(p[1]) for p in sample_parts if len(p) >= 2)
        label = f"Evolved\n(*-*-I1-*)"
    else:  # Genome-Shuffled
        label = f"Genome-Shuffled\n(*-*-I2/I3-*)"

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
    # Label for high freq (skip Ancestral - i=0)
    if h > 0 and i != 0:
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
ax.set_title('Mutation Frequency Distribution by Sample Group\n(Breseq Mutations with Evidence Frequencies)',
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

# Add note about high frequency counts below x-axis (similar to VCF plot's low freq note)
high_note = f'High Freq (>=0.9): Ancestral {high_totals[0]} ({high_totals[0]/total_counts[0]*100:.0f}%),  Evolved {high_totals[1]} ({high_totals[1]/total_counts[1]*100:.0f}%),  Genome-Shuffled {high_totals[2]} ({high_totals[2]/total_counts[2]*100:.0f}%)'
ax.text(0.5, -0.10, high_note, ha='center', va='top', fontsize=11,
        transform=ax.transAxes, fontweight='bold', color=color_high)

plt.tight_layout()
plt.savefig('comparison/breseq_frequency_percentage_barplot.png', dpi=300,
            bbox_inches='tight', facecolor='white', edgecolor='none')
plt.savefig('comparison/breseq_frequency_percentage_barplot.pdf',
            bbox_inches='tight', facecolor='white', edgecolor='none')
plt.close()

# Reset style
plt.style.use('default')

print(f"\nBarplot saved to:")
print(f"  - comparison/breseq_frequency_percentage_barplot.png")
print(f"  - comparison/breseq_frequency_percentage_barplot.pdf")
