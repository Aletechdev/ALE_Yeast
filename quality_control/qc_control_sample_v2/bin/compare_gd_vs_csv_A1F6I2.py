#!/usr/bin/env python3
"""
Compare Breseq .gd output file with AMP Mutations CSV for sample A1-F6-I2-R1.
Creates comparison plots and summary statistics.
"""
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
import re
import csv
from collections import defaultdict

# File paths
GD_FILE = 'data/A1-F6-I2-R1-bareseq-output.gd'
CSV_FILE = 'data/Mutations_Dev_Yeast_Adipic_Acid.csv'
SAMPLE_COL = 9  # 0-indexed column for A1-F6-I2-R1

def load_gd_file(gd_file):
    """Load mutations from Breseq .gd file."""
    mutations = []
    with open(gd_file, 'r') as f:
        for line in f:
            if line.startswith(('SNP', 'DEL', 'INS')):
                parts = line.strip().split('\t')
                mut_type = parts[0]
                chrom = parts[3]
                pos = int(parts[4])

                freq_match = re.search(r'frequency=([0-9.e+-]+)', line)
                freq = float(freq_match.group(1)) if freq_match else 0

                mutations.append({
                    'type': mut_type,
                    'chrom': chrom,
                    'pos': pos,
                    'freq': freq
                })
    return mutations

def load_csv_file(csv_file, sample_col):
    """Load mutations from AMP Mutations CSV for a specific sample."""
    mutations = []
    with open(csv_file, 'r') as f:
        reader = csv.reader(f)
        header = next(reader)
        sample_name = header[sample_col]

        for row in reader:
            if len(row) > sample_col and row[sample_col]:
                val = row[sample_col]
                if '/' in val:
                    parts = val.split('/')
                    breseq_freq = float(parts[0]) if parts[0] else 0
                    gatk_freq = float(parts[1]) if parts[1] else 0

                    chrom = row[0].replace('"', '')
                    pos = int(row[1].replace('"', '').replace(',', ''))
                    mut_type = row[2].replace('"', '')

                    mutations.append({
                        'type': mut_type,
                        'chrom': chrom,
                        'pos': pos,
                        'breseq_freq': breseq_freq,
                        'gatk_freq': gatk_freq
                    })
    return mutations, sample_name

def find_clusters(mutations, window=50, min_size=3):
    """Find clusters of mutations within a window."""
    by_chrom = defaultdict(list)
    for m in mutations:
        by_chrom[m['chrom']].append(m)

    clusters = []
    for chrom, muts in by_chrom.items():
        muts.sort(key=lambda x: x['pos'])
        cluster = [muts[0]]
        for i in range(1, len(muts)):
            if muts[i]['pos'] - cluster[-1]['pos'] <= window:
                cluster.append(muts[i])
            else:
                if len(cluster) >= min_size:
                    clusters.append((chrom, cluster))
                cluster = [muts[i]]
        if len(cluster) >= min_size:
            clusters.append((chrom, cluster))

    return clusters

# Load data
print("Loading data...")
gd_mutations = load_gd_file(GD_FILE)
csv_mutations, sample_name = load_csv_file(CSV_FILE, SAMPLE_COL)

print(f"Sample: {sample_name}")
print(f"Raw .gd mutations: {len(gd_mutations)}")
print(f"CSV mutations: {len(csv_mutations)}")

# Create position sets for comparison
gd_positions = {(m['chrom'], m['pos']): m for m in gd_mutations}
csv_positions = {(m['chrom'], m['pos']): m for m in csv_mutations}

gd_keys = set(gd_positions.keys())
csv_keys = set(csv_positions.keys())

common = gd_keys & csv_keys
gd_only = gd_keys - csv_keys
csv_only = csv_keys - gd_keys

print(f"\nPosition comparison:")
print(f"  Common: {len(common)}")
print(f"  .gd only: {len(gd_only)}")
print(f"  CSV only: {len(csv_only)}")

# Analyze CSV-only (GATK detections not in .gd)
csv_only_breseq = [csv_positions[k] for k in csv_only if csv_positions[k]['breseq_freq'] > 0]
csv_only_gatk = [csv_positions[k] for k in csv_only if csv_positions[k]['breseq_freq'] == 0]
print(f"\nCSV-only breakdown:")
print(f"  With Breseq freq > 0: {len(csv_only_breseq)} (position mismatch)")
print(f"  GATK-only (Breseq=0): {len(csv_only_gatk)}")

# Find clusters in .gd
clusters = find_clusters(gd_mutations, window=50, min_size=3)
clustered_positions = set()
for chrom, cluster in clusters:
    for m in cluster:
        clustered_positions.add((m['chrom'], m['pos']))

gd_clustered = len(clustered_positions)
gd_non_clustered = len(gd_mutations) - gd_clustered

print(f"\n.gd clustering analysis:")
print(f"  Clustered (>2 muts within 50bp): {gd_clustered} ({gd_clustered/len(gd_mutations)*100:.1f}%)")
print(f"  Non-clustered: {gd_non_clustered}")

# Frequency distribution in .gd
gd_high = [m for m in gd_mutations if m['freq'] >= 0.75]
gd_med = [m for m in gd_mutations if 0.5 <= m['freq'] < 0.75]
gd_low = [m for m in gd_mutations if 0.05 <= m['freq'] < 0.5]

print(f"\n.gd frequency distribution:")
print(f"  >=75%: {len(gd_high)}")
print(f"  50-75%: {len(gd_med)}")
print(f"  5-50%: {len(gd_low)}")

# CSV frequency distribution
csv_breseq_detected = [m for m in csv_mutations if m['breseq_freq'] > 0]
csv_gatk_only = [m for m in csv_mutations if m['breseq_freq'] == 0 and m['gatk_freq'] > 0]
csv_both = [m for m in csv_mutations if m['breseq_freq'] > 0 and m['gatk_freq'] > 0]

print(f"\nCSV detection breakdown:")
print(f"  Breseq detected: {len(csv_breseq_detected)}")
print(f"  GATK-only: {len(csv_gatk_only)}")
print(f"  Both tools: {len(csv_both)}")

# Set up plotting style
plt.style.use('seaborn-v0_8-whitegrid')
plt.rcParams.update({
    'font.family': 'sans-serif',
    'font.size': 12,
    'axes.labelsize': 14,
    'xtick.labelsize': 12,
    'ytick.labelsize': 12,
    'figure.facecolor': 'white',
    'axes.facecolor': 'white',
})

# Create figure with multiple subplots
fig, axes = plt.subplots(2, 2, figsize=(14, 12))
fig.patch.set_facecolor('white')

# Plot 1: Bar chart comparing counts
ax1 = axes[0, 0]
categories = ['Raw .gd\n(Breseq output)', 'CSV Breseq', 'CSV GATK-only', 'CSV Both']
counts = [len(gd_mutations), len(csv_breseq_detected), len(csv_gatk_only), len(csv_both)]
colors = ['#3498DB', '#2ECC71', '#E74C3C', '#9B59B6']

bars = ax1.bar(categories, counts, color=colors, edgecolor='white', linewidth=2)
for bar, count in zip(bars, counts):
    ax1.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 5,
             str(count), ha='center', va='bottom', fontsize=14, fontweight='bold')

ax1.set_ylabel('Number of Mutations', fontweight='bold')
ax1.set_title(f'Mutation Counts: {sample_name}', fontweight='bold', fontsize=14)
ax1.spines['top'].set_visible(False)
ax1.spines['right'].set_visible(False)

# Plot 2: Venn-like bar showing overlap
ax2 = axes[0, 1]
overlap_data = [
    ('Common\n(in both)', len(common), '#2ECC71'),
    ('.gd only', len(gd_only), '#3498DB'),
    ('CSV only', len(csv_only), '#E74C3C')
]
x_pos = np.arange(len(overlap_data))
for i, (label, count, color) in enumerate(overlap_data):
    ax2.bar(i, count, color=color, edgecolor='white', linewidth=2)
    ax2.text(i, count + 10, str(count), ha='center', va='bottom', fontsize=14, fontweight='bold')

ax2.set_xticks(x_pos)
ax2.set_xticklabels([d[0] for d in overlap_data], fontweight='bold')
ax2.set_ylabel('Number of Positions', fontweight='bold')
ax2.set_title('Position Overlap: .gd vs CSV', fontweight='bold', fontsize=14)
ax2.spines['top'].set_visible(False)
ax2.spines['right'].set_visible(False)

# Plot 3: .gd frequency histogram
ax3 = axes[1, 0]
freqs = [m['freq'] for m in gd_mutations]
ax3.hist(freqs, bins=50, color='#3498DB', edgecolor='white', linewidth=0.5, alpha=0.8)
ax3.axvline(x=0.5, color='red', linestyle='--', linewidth=2, label='50% threshold')
ax3.axvline(x=0.75, color='orange', linestyle='--', linewidth=2, label='75% threshold')
ax3.set_xlabel('Mutation Frequency', fontweight='bold')
ax3.set_ylabel('Count', fontweight='bold')
ax3.set_title('Frequency Distribution in .gd File', fontweight='bold', fontsize=14)
ax3.legend()
ax3.spines['top'].set_visible(False)
ax3.spines['right'].set_visible(False)

# Plot 4: Clustered vs non-clustered
ax4 = axes[1, 1]
cluster_data = ['Clustered\n(repetitive)', 'Non-clustered\n(unique)']
cluster_counts = [gd_clustered, gd_non_clustered]
cluster_colors = ['#BDC3C7', '#2ECC71']

bars = ax4.bar(cluster_data, cluster_counts, color=cluster_colors, edgecolor='white', linewidth=2)
for bar, count in zip(bars, cluster_counts):
    pct = count / len(gd_mutations) * 100
    ax4.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 5,
             f'{count}\n({pct:.1f}%)', ha='center', va='bottom', fontsize=12, fontweight='bold')

ax4.set_ylabel('Number of Mutations', fontweight='bold')
ax4.set_title('.gd Mutations: Clustered vs Unique', fontweight='bold', fontsize=14)
ax4.spines['top'].set_visible(False)
ax4.spines['right'].set_visible(False)

plt.tight_layout()
plt.savefig('comparison/gd_vs_csv_comparison_A1-F6-I2-R1.png', dpi=300, bbox_inches='tight',
            facecolor='white', edgecolor='none')
plt.savefig('comparison/gd_vs_csv_comparison_A1-F6-I2-R1.pdf', bbox_inches='tight',
            facecolor='white', edgecolor='none')

plt.style.use('default')

print(f"\nPlots saved to:")
print(f"  - comparison/gd_vs_csv_comparison_A1-F6-I2-R1.png")
print(f"  - comparison/gd_vs_csv_comparison_A1-F6-I2-R1.pdf")

# Create summary report
with open('comparison/gd_vs_csv_comparison_A1-F6-I2-R1.txt', 'w') as f:
    f.write("=" * 70 + "\n")
    f.write("COMPARISON: Breseq .gd Output vs AMP Mutations CSV\n")
    f.write(f"Sample: {sample_name}\n")
    f.write("=" * 70 + "\n\n")

    f.write("DATA SOURCES:\n")
    f.write(f"  .gd file: {GD_FILE}\n")
    f.write(f"  CSV file: {CSV_FILE}\n\n")

    f.write("MUTATION COUNTS:\n")
    f.write(f"  Raw Breseq (.gd): {len(gd_mutations)}\n")
    f.write(f"  CSV total: {len(csv_mutations)}\n")
    f.write(f"    - Breseq detected: {len(csv_breseq_detected)}\n")
    f.write(f"    - GATK-only: {len(csv_gatk_only)}\n")
    f.write(f"    - Both tools: {len(csv_both)}\n\n")

    f.write("POSITION OVERLAP:\n")
    f.write(f"  Common positions: {len(common)}\n")
    f.write(f"  .gd only: {len(gd_only)} ({len(gd_only)/len(gd_mutations)*100:.1f}% of .gd)\n")
    f.write(f"  CSV only: {len(csv_only)}\n\n")

    f.write(".gd FREQUENCY DISTRIBUTION:\n")
    f.write(f"  >=75% (high confidence): {len(gd_high)}\n")
    f.write(f"  50-75% (medium): {len(gd_med)}\n")
    f.write(f"  5-50% (low frequency): {len(gd_low)}\n\n")

    f.write("CLUSTERING ANALYSIS:\n")
    f.write(f"  Clustered mutations: {gd_clustered} ({gd_clustered/len(gd_mutations)*100:.1f}%)\n")
    f.write(f"  Non-clustered: {gd_non_clustered}\n")
    f.write(f"  Number of clusters: {len(clusters)}\n\n")

    f.write("KEY FINDINGS:\n")
    f.write(f"  1. The .gd file contains {len(gd_mutations)} raw mutations, but only\n")
    f.write(f"     {len(csv_breseq_detected)} ({len(csv_breseq_detected)/len(gd_mutations)*100:.1f}%) appear in the CSV with Breseq detection.\n")
    f.write(f"  2. {gd_clustered} ({gd_clustered/len(gd_mutations)*100:.1f}%) of .gd mutations are in clusters,\n")
    f.write(f"     suggesting they're in repetitive regions (rDNA, telomeres).\n")
    f.write(f"  3. Most .gd mutations have low frequency (5-50%), indicating\n")
    f.write(f"     heterogeneous population or sequencing artifacts.\n")
    f.write(f"  4. The AMP CSV appears to be a curated/filtered subset.\n")

print(f"Summary saved to: comparison/gd_vs_csv_comparison_A1-F6-I2-R1.txt")
