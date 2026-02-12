#!/usr/bin/env python3
"""
Scatter plot comparing mutation counts: AMP (breseq + GATK_haplotypecaller) vs HaplotypeCaller (VCF)
for each sample in the joint calling output.

AMP CSV format: each sample cell contains "breseq_freq/gatk_freq" (e.g., "1.00/0.96")
"""

import subprocess
import csv
import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path

# File paths
AMP_CSV = Path('data/Mutations_Dev_Yeast_Adipic_Acid.csv')
VCF_FILE = Path('data/HaplotypeCaller_joint_calling_soft_filtered_snpEff.ann.vcf.gz')
OUTPUT_DIR = Path('comparison')


def normalize_sample_name(name):
    """Convert 'A0 F0 I1 R1' to 'A0-F0-I1-R1'."""
    return name.replace(' ', '-').strip('"')


def classify_sample(sample_name):
    """
    Classify sample into groups:
    - Group 1 (Original/Evolved): A0-F0-* (ancestral) and *-I1-* (evolved isolate 1)
    - Group 2 (Genome-shuffling): All other samples (I2-R1, I3-R1)
    """
    if sample_name.startswith('A0-F0-'):
        return 'original_evolved'
    elif '-I1-' in sample_name:
        return 'original_evolved'
    else:
        return 'genome_shuffling'


def get_amp_counts_by_tool(csv_file):
    """
    Count detected mutations per sample from AMP CSV, split by tool.
    Cell format: "breseq_freq/gatk_freq" (e.g., "1.00/0.96")

    Returns:
        breseq_counts: dict of sample -> count (breseq_freq > 0)
        gatk_counts: dict of sample -> count (gatk_freq > 0)
    """
    breseq_counts = {}
    gatk_counts = {}

    with open(csv_file, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        header = next(reader)

        # Find sample columns (columns 7 onwards contain sample data)
        sample_cols = {}
        for i, col in enumerate(header):
            col_clean = col.strip('"')
            if col_clean and col_clean not in ['Reference Seq', 'Position', 'Mutation Type',
                                                'Sequence Change', 'Gene (Scrollable)', 'Details']:
                sample_name = normalize_sample_name(col_clean)
                sample_cols[i] = sample_name
                breseq_counts[sample_name] = 0
                gatk_counts[sample_name] = 0

        # Count mutations per sample by tool
        for row in reader:
            for col_idx, sample_name in sample_cols.items():
                if col_idx < len(row):
                    cell = row[col_idx].strip()
                    if cell and '/' in cell:
                        parts = cell.split('/')
                        if len(parts) == 2:
                            try:
                                breseq_freq = float(parts[0]) if parts[0] else 0
                                gatk_freq = float(parts[1]) if parts[1] else 0

                                if breseq_freq > 0:
                                    breseq_counts[sample_name] += 1
                                if gatk_freq > 0:
                                    gatk_counts[sample_name] += 1
                            except ValueError:
                                pass

    return breseq_counts, gatk_counts


def get_amp_counts(csv_file):
    """
    Count detected mutations per sample from AMP CSV (combined).
    A mutation is detected if any tool detected it.
    """
    breseq_counts, gatk_counts = get_amp_counts_by_tool(csv_file)

    # Combined: mutation detected if either tool found it
    counts = {}
    for sample in breseq_counts:
        # We need to re-count where either tool detected
        counts[sample] = 0

    with open(csv_file, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        header = next(reader)

        sample_cols = {}
        for i, col in enumerate(header):
            col_clean = col.strip('"')
            if col_clean and col_clean not in ['Reference Seq', 'Position', 'Mutation Type',
                                                'Sequence Change', 'Gene (Scrollable)', 'Details']:
                sample_name = normalize_sample_name(col_clean)
                sample_cols[i] = sample_name
                counts[sample_name] = 0

        for row in reader:
            for col_idx, sample_name in sample_cols.items():
                if col_idx < len(row):
                    cell = row[col_idx].strip()
                    if cell and cell != '':
                        if any(c.isdigit() for c in cell):
                            counts[sample_name] += 1

    return counts


def get_vcf_counts(vcf_file):
    """
    Count non-reference genotypes per sample from VCF.
    Uses bcftools to query GT field for each sample.
    Filters: PASS only (includes multiallelic sites).
    """
    counts = {}

    # Get sample list
    cmd = ['bcftools', 'query', '-l', str(vcf_file)]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    samples = result.stdout.strip().split('\n')

    # Query all samples at once with PASS filter
    # Format: CHROM, POS, ALT, then GT for each sample
    gt_format = '[%GT\t]'
    cmd = [
        'bcftools', 'query',
        '-i', 'FILTER="PASS"',
        '-f', f'%ALT\t{gt_format}\n',
        str(vcf_file)
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)

    # Initialize counts
    for sample in samples:
        short_name = sample.replace('ALE_Exp1_', '')
        counts[short_name] = 0

    # Parse output - count non-ref genotypes for PASS (including multiallelic)
    for line in result.stdout.strip().split('\n'):
        if not line:
            continue
        fields = line.split('\t')
        if len(fields) < 2:
            continue

        # Include multiallelic sites - no longer skip

        # Count non-ref genotypes for each sample
        gt_fields = fields[1:]
        for i, sample in enumerate(samples):
            if i < len(gt_fields):
                gt = gt_fields[i].strip()
                if gt and gt not in ['0', '0/0', './.', '.', '0/0/0', '0|0']:
                    short_name = sample.replace('ALE_Exp1_', '')
                    counts[short_name] += 1

    return counts


def create_scatter_plot(amp_counts, vcf_counts, output_dir):
    """
    Create scatter plot comparing AMP vs VCF mutation counts (legacy - combined AMP).
    """
    # Get common samples
    common_samples = sorted(set(amp_counts.keys()) & set(vcf_counts.keys()))

    if not common_samples:
        print("No common samples found!")
        print(f"AMP samples: {list(amp_counts.keys())}")
        print(f"VCF samples: {list(vcf_counts.keys())}")
        return

    # Prepare data
    x = np.arange(len(common_samples))
    amp_values = [amp_counts[s] for s in common_samples]
    vcf_values = [vcf_counts[s] for s in common_samples]

    # Create figure
    fig, ax = plt.subplots(figsize=(14, 8))

    # Plot both clusters
    scatter_amp = ax.scatter(x - 0.15, amp_values, s=120, c='#E74C3C', marker='o',
                             label='AMP (ALEDB)', alpha=0.8, edgecolors='darkred', linewidths=1)
    scatter_vcf = ax.scatter(x + 0.15, vcf_values, s=120, c='#3498DB', marker='s',
                             label='HaplotypeCaller (VCF)', alpha=0.8, edgecolors='darkblue', linewidths=1)

    # Connect paired points with lines
    for i in range(len(common_samples)):
        ax.plot([x[i] - 0.15, x[i] + 0.15], [amp_values[i], vcf_values[i]],
                color='gray', linestyle='--', alpha=0.4, linewidth=1)

    # Customize plot
    ax.set_xlabel('Sample', fontsize=12, fontweight='bold')
    ax.set_ylabel('Number of Mutations Detected', fontsize=12, fontweight='bold')
    ax.set_title('Mutation Detection: AMP (ALEDB) vs HaplotypeCaller\nPer-Sample Comparison',
                 fontsize=14, fontweight='bold')

    # Set x-axis labels
    ax.set_xticks(x)
    ax.set_xticklabels(common_samples, rotation=45, ha='right', fontsize=9)

    # Add legend
    ax.legend(loc='upper left', fontsize=10)

    # Add grid
    ax.grid(True, alpha=0.3, linestyle='-', linewidth=0.5)
    ax.set_axisbelow(True)

    # Add summary statistics as text
    total_amp = sum(amp_values)
    total_vcf = sum(vcf_values)
    mean_amp = np.mean(amp_values)
    mean_vcf = np.mean(vcf_values)

    stats_text = (f'Total: AMP={total_amp}, VCF={total_vcf}\n'
                  f'Mean: AMP={mean_amp:.1f}, VCF={mean_vcf:.1f}')
    ax.text(0.98, 0.98, stats_text, transform=ax.transAxes, fontsize=10,
            verticalalignment='top', horizontalalignment='right',
            bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))

    # Adjust layout
    plt.tight_layout()

    # Save plots
    output_dir.mkdir(parents=True, exist_ok=True)
    png_path = output_dir / 'amp_vs_vcf_scatter.png'
    pdf_path = output_dir / 'amp_vs_vcf_scatter.pdf'

    plt.savefig(png_path, dpi=150, bbox_inches='tight')
    plt.savefig(pdf_path, bbox_inches='tight')
    plt.close()

    print(f"Scatter plot saved to:")
    print(f"  - {png_path}")
    print(f"  - {pdf_path}")

    # Print summary table
    print(f"\nPer-sample comparison:")
    print(f"{'Sample':<15} {'AMP':>8} {'VCF':>8} {'Diff':>8} {'Ratio':>8}")
    print("-" * 50)
    for sample, amp, vcf in zip(common_samples, amp_values, vcf_values):
        diff = vcf - amp
        ratio = vcf / amp if amp > 0 else float('inf')
        print(f"{sample:<15} {amp:>8} {vcf:>8} {diff:>+8} {ratio:>8.2f}")
    print("-" * 50)
    print(f"{'TOTAL':<15} {total_amp:>8} {total_vcf:>8} {total_vcf - total_amp:>+8}")

    return common_samples, amp_values, vcf_values


def create_scatter_plot_by_tool(breseq_counts, gatk_counts, vcf_counts, output_dir):
    """
    Create scatter plot comparing AMP (breseq + GATK) vs VCF mutation counts.
    Shows three dots per sample: breseq, AMP-GATK, and our VCF HaplotypeCaller.
    """
    # Get common samples
    common_samples = sorted(set(breseq_counts.keys()) & set(gatk_counts.keys()) & set(vcf_counts.keys()))

    if not common_samples:
        print("No common samples found!")
        return

    # Prepare data
    x = np.arange(len(common_samples))
    breseq_values = [breseq_counts[s] for s in common_samples]
    gatk_values = [gatk_counts[s] for s in common_samples]
    vcf_values = [vcf_counts[s] for s in common_samples]

    # Create figure
    fig, ax = plt.subplots(figsize=(16, 9))

    # Plot three clusters with offset
    offset = 0.25
    scatter_breseq = ax.scatter(x - offset, breseq_values, s=120, c='#E74C3C', marker='o',
                                label='AMP-breseq', alpha=0.8, edgecolors='darkred', linewidths=1)
    scatter_gatk = ax.scatter(x, gatk_values, s=120, c='#F39C12', marker='^',
                              label='AMP-HaplotypeCaller', alpha=0.8, edgecolors='darkorange', linewidths=1)
    scatter_vcf = ax.scatter(x + offset, vcf_values, s=120, c='#3498DB', marker='s',
                             label='Sarek-Joint-HaplotypeCaller', alpha=0.8, edgecolors='darkblue', linewidths=1)

    # Connect points with lines for each sample
    for i in range(len(common_samples)):
        # Light gray line connecting all three
        ax.plot([x[i] - offset, x[i], x[i] + offset],
                [breseq_values[i], gatk_values[i], vcf_values[i]],
                color='gray', linestyle=':', alpha=0.3, linewidth=1)

    # Customize plot
    ax.set_xlabel('Sample', fontsize=12, fontweight='bold')
    ax.set_ylabel('Number of Mutations Detected', fontsize=12, fontweight='bold')
    ax.set_title('Mutation Detection Comparison by Tool\nAMP (breseq + HaplotypeCaller) vs Sarek-Joint-HaplotypeCaller',
                 fontsize=14, fontweight='bold')

    # Set x-axis labels
    ax.set_xticks(x)
    ax.set_xticklabels(common_samples, rotation=45, ha='right', fontsize=9)

    # Add legend
    ax.legend(loc='upper left', fontsize=10)

    # Add grid
    ax.grid(True, alpha=0.3, linestyle='-', linewidth=0.5)
    ax.set_axisbelow(True)

    # Add summary statistics as text
    total_breseq = sum(breseq_values)
    total_gatk = sum(gatk_values)
    total_vcf = sum(vcf_values)
    mean_breseq = np.mean(breseq_values)
    mean_gatk = np.mean(gatk_values)
    mean_vcf = np.mean(vcf_values)

    stats_text = (f'Total: breseq={total_breseq}, GATK={total_gatk}, Joint-GATK={total_vcf}\n'
                  f'Mean: breseq={mean_breseq:.1f}, GATK={mean_gatk:.1f}, Joint-GATK={mean_vcf:.1f}')
    ax.text(0.98, 0.98, stats_text, transform=ax.transAxes, fontsize=10,
            verticalalignment='top', horizontalalignment='right',
            bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))

    # Adjust layout
    plt.tight_layout()

    # Save plots
    output_dir.mkdir(parents=True, exist_ok=True)
    png_path = output_dir / 'amp_vs_vcf_scatter_by_tool.png'
    pdf_path = output_dir / 'amp_vs_vcf_scatter_by_tool.pdf'

    plt.savefig(png_path, dpi=150, bbox_inches='tight')
    plt.savefig(pdf_path, bbox_inches='tight')
    plt.close()

    print(f"\nScatter plot (by tool) saved to:")
    print(f"  - {png_path}")
    print(f"  - {pdf_path}")

    # Print summary table
    print(f"\nPer-sample comparison (by tool):")
    print(f"{'Sample':<15} {'breseq':>8} {'GATK':>8} {'Joint-GATK':>12} {'Diff':>8}")
    print("-" * 55)
    for sample, breseq, gatk, vcf in zip(common_samples, breseq_values, gatk_values, vcf_values):
        diff = vcf - gatk
        print(f"{sample:<15} {breseq:>8} {gatk:>8} {vcf:>12} {diff:>+8}")
    print("-" * 55)
    print(f"{'TOTAL':<15} {total_breseq:>8} {total_gatk:>8} {total_vcf:>12} {total_vcf - total_gatk:>+8}")

    return common_samples, breseq_values, gatk_values, vcf_values


def create_scatter_plot_by_group(breseq_counts, gatk_counts, vcf_counts, output_dir):
    """
    Create scatter plot with samples separated into two groups:
    - Group 1: Original/Evolved (A0-F0-* and *-I1-*)
    - Group 2: Genome-shuffling (I2-R1, I3-R1)
    """
    # Get common samples and classify
    common_samples = sorted(set(breseq_counts.keys()) & set(gatk_counts.keys()) & set(vcf_counts.keys()))

    if not common_samples:
        print("No common samples found!")
        return

    # Separate into groups
    group1_samples = [s for s in common_samples if classify_sample(s) == 'original_evolved']
    group2_samples = [s for s in common_samples if classify_sample(s) == 'genome_shuffling']

    # Create figure with two subplots
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(18, 8))

    offset = 0.25

    # --- Group 1: Original/Evolved ---
    x1 = np.arange(len(group1_samples))
    breseq1 = [breseq_counts[s] for s in group1_samples]
    gatk1 = [gatk_counts[s] for s in group1_samples]
    vcf1 = [vcf_counts[s] for s in group1_samples]

    ax1.scatter(x1 - offset, breseq1, s=120, c='#E74C3C', marker='o',
                label='AMP-breseq', alpha=0.8, edgecolors='darkred', linewidths=1)
    ax1.scatter(x1, gatk1, s=120, c='#F39C12', marker='^',
                label='AMP-HaplotypeCaller', alpha=0.8, edgecolors='darkorange', linewidths=1)
    ax1.scatter(x1 + offset, vcf1, s=120, c='#3498DB', marker='s',
                label='Sarek-Joint-HaplotypeCaller', alpha=0.8, edgecolors='darkblue', linewidths=1)

    for i in range(len(group1_samples)):
        ax1.plot([x1[i] - offset, x1[i], x1[i] + offset],
                 [breseq1[i], gatk1[i], vcf1[i]],
                 color='gray', linestyle=':', alpha=0.3, linewidth=1)

    ax1.set_xlabel('Sample', fontsize=12, fontweight='bold')
    ax1.set_ylabel('Number of Mutations Detected', fontsize=12, fontweight='bold')
    ax1.set_title('Group 1: Original & Evolved Strains\n(A0-F0-* ancestral + *-I1-* evolved)',
                  fontsize=13, fontweight='bold')
    ax1.set_xticks(x1)
    ax1.set_xticklabels(group1_samples, rotation=45, ha='right', fontsize=9)
    ax1.legend(loc='upper left', fontsize=9)
    ax1.grid(True, alpha=0.3, linestyle='-', linewidth=0.5)
    ax1.set_axisbelow(True)

    # Stats for group 1
    stats1 = (f'Total: breseq={sum(breseq1)}, GATK={sum(gatk1)}, Joint-GATK={sum(vcf1)}\n'
              f'Mean: breseq={np.mean(breseq1):.1f}, GATK={np.mean(gatk1):.1f}, Joint-GATK={np.mean(vcf1):.1f}')
    ax1.text(0.98, 0.98, stats1, transform=ax1.transAxes, fontsize=9,
             verticalalignment='top', horizontalalignment='right',
             bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))

    # --- Group 2: Genome-shuffling ---
    x2 = np.arange(len(group2_samples))
    breseq2 = [breseq_counts[s] for s in group2_samples]
    gatk2 = [gatk_counts[s] for s in group2_samples]
    vcf2 = [vcf_counts[s] for s in group2_samples]

    ax2.scatter(x2 - offset, breseq2, s=120, c='#E74C3C', marker='o',
                label='AMP-breseq', alpha=0.8, edgecolors='darkred', linewidths=1)
    ax2.scatter(x2, gatk2, s=120, c='#F39C12', marker='^',
                label='AMP-HaplotypeCaller', alpha=0.8, edgecolors='darkorange', linewidths=1)
    ax2.scatter(x2 + offset, vcf2, s=120, c='#3498DB', marker='s',
                label='Sarek-Joint-HaplotypeCaller', alpha=0.8, edgecolors='darkblue', linewidths=1)

    for i in range(len(group2_samples)):
        ax2.plot([x2[i] - offset, x2[i], x2[i] + offset],
                 [breseq2[i], gatk2[i], vcf2[i]],
                 color='gray', linestyle=':', alpha=0.3, linewidth=1)

    ax2.set_xlabel('Sample', fontsize=12, fontweight='bold')
    ax2.set_ylabel('Number of Mutations Detected', fontsize=12, fontweight='bold')
    ax2.set_title('Group 2: Genome-Shuffling Strains\n(*-I2-* and *-I3-* isolates)',
                  fontsize=13, fontweight='bold')
    ax2.set_xticks(x2)
    ax2.set_xticklabels(group2_samples, rotation=45, ha='right', fontsize=9)
    ax2.legend(loc='upper left', fontsize=9)
    ax2.grid(True, alpha=0.3, linestyle='-', linewidth=0.5)
    ax2.set_axisbelow(True)

    # Stats for group 2
    stats2 = (f'Total: breseq={sum(breseq2)}, GATK={sum(gatk2)}, Joint-GATK={sum(vcf2)}\n'
              f'Mean: breseq={np.mean(breseq2):.1f}, GATK={np.mean(gatk2):.1f}, Joint-GATK={np.mean(vcf2):.1f}')
    ax2.text(0.98, 0.98, stats2, transform=ax2.transAxes, fontsize=9,
             verticalalignment='top', horizontalalignment='right',
             bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))

    # Set same y-axis limits for comparison
    max_y = max(max(breseq1 + breseq2), max(gatk1 + gatk2), max(vcf1 + vcf2)) * 1.1
    ax1.set_ylim(0, max_y)
    ax2.set_ylim(0, max_y)

    plt.tight_layout()

    # Save plots
    output_dir.mkdir(parents=True, exist_ok=True)
    png_path = output_dir / 'amp_vs_vcf_scatter_by_group.png'
    pdf_path = output_dir / 'amp_vs_vcf_scatter_by_group.pdf'

    plt.savefig(png_path, dpi=150, bbox_inches='tight')
    plt.savefig(pdf_path, bbox_inches='tight')
    plt.close()

    print(f"\nScatter plot (by group) saved to:")
    print(f"  - {png_path}")
    print(f"  - {pdf_path}")

    # Print summary tables
    print(f"\n{'='*70}")
    print("GROUP 1: Original & Evolved Strains (A0-F0-* + *-I1-*)")
    print(f"{'='*70}")
    print(f"{'Sample':<15} {'breseq':>8} {'GATK':>8} {'Joint-GATK':>12} {'Diff':>8}")
    print("-" * 55)
    for sample, b, g, v in zip(group1_samples, breseq1, gatk1, vcf1):
        print(f"{sample:<15} {b:>8} {g:>8} {v:>12} {v-g:>+8}")
    print("-" * 55)
    print(f"{'TOTAL':<15} {sum(breseq1):>8} {sum(gatk1):>8} {sum(vcf1):>12} {sum(vcf1)-sum(gatk1):>+8}")
    print(f"{'MEAN':<15} {np.mean(breseq1):>8.1f} {np.mean(gatk1):>8.1f} {np.mean(vcf1):>12.1f}")

    print(f"\n{'='*70}")
    print("GROUP 2: Genome-Shuffling Strains (*-I2-* + *-I3-*)")
    print(f"{'='*70}")
    print(f"{'Sample':<15} {'breseq':>8} {'GATK':>8} {'Joint-GATK':>12} {'Diff':>8}")
    print("-" * 55)
    for sample, b, g, v in zip(group2_samples, breseq2, gatk2, vcf2):
        print(f"{sample:<15} {b:>8} {g:>8} {v:>12} {v-g:>+8}")
    print("-" * 55)
    print(f"{'TOTAL':<15} {sum(breseq2):>8} {sum(gatk2):>8} {sum(vcf2):>12} {sum(vcf2)-sum(gatk2):>+8}")
    print(f"{'MEAN':<15} {np.mean(breseq2):>8.1f} {np.mean(gatk2):>8.1f} {np.mean(vcf2):>12.1f}")

    return group1_samples, group2_samples


def create_presentation_plot(breseq_counts, gatk_counts, vcf_counts, output_dir):
    """
    Create PowerPoint-ready scatter plot with 3 tools on x-axis.
    Each dot = one sample, grouped by tool.
    """
    # Get common samples and classify
    common_samples = sorted(set(breseq_counts.keys()) & set(gatk_counts.keys()) & set(vcf_counts.keys()))

    if not common_samples:
        print("No common samples found!")
        return

    # Separate into groups
    group1_samples = [s for s in common_samples if classify_sample(s) == 'original_evolved']
    group2_samples = [s for s in common_samples if classify_sample(s) == 'genome_shuffling']

    # Set up presentation style
    plt.style.use('seaborn-v0_8-whitegrid')
    plt.rcParams.update({
        'font.family': 'sans-serif',
        'font.size': 14,
        'axes.titlesize': 20,
        'axes.labelsize': 16,
        'xtick.labelsize': 14,
        'ytick.labelsize': 14,
        'figure.facecolor': 'white',
        'axes.facecolor': 'white',
        'axes.edgecolor': '#333333',
        'axes.linewidth': 1.5,
    })

    # Create figure
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 7))
    fig.patch.set_facecolor('white')

    marker_size = 350

    # Colors for Group 1: Original vs Evolved
    color_original = '#E74C3C'  # Red for original (A0-F0-*)
    color_evolved = '#4A90D9'   # Blue for evolved (*-I1-*)
    dot_color = '#4A90D9'       # Blue for Group 2
    tool_names = ['Breseq (AMP)', 'GATK-HC (AMP)', 'Joint-GATK-HC (ANP)']

    # --- Group 1: Original/Evolved ---
    breseq1 = [breseq_counts[s] for s in group1_samples]
    gatk1 = [gatk_counts[s] for s in group1_samples]
    vcf1 = [vcf_counts[s] for s in group1_samples]

    # Assign colors based on original (A0-F0-*) vs evolved (*-I1-*)
    colors1 = [color_original if s.startswith('A0-F0-') else color_evolved for s in group1_samples]

    # Add jitter for visibility
    np.random.seed(42)
    jitter1 = np.random.uniform(-0.15, 0.15, len(group1_samples))

    ax1.scatter(0 + jitter1, breseq1, s=marker_size, c=colors1, marker='o',
                alpha=0.5, edgecolors='white', linewidths=2, zorder=3)
    ax1.scatter(1 + jitter1, gatk1, s=marker_size, c=colors1, marker='o',
                alpha=0.5, edgecolors='white', linewidths=2, zorder=3)
    ax1.scatter(2 + jitter1, vcf1, s=marker_size, c=colors1, marker='o',
                alpha=0.5, edgecolors='white', linewidths=2, zorder=3)

    # Add legend for Group 1
    from matplotlib.patches import Patch
    legend_elements = [
        Patch(facecolor=color_original, edgecolor='white', label='Original (A0-F0-*)'),
        Patch(facecolor=color_evolved, edgecolor='white', label='Evolved (*-I1-*)')
    ]
    ax1.legend(handles=legend_elements, loc='upper left', fontsize=10)

    # Add mean bars
    for i, vals in enumerate([breseq1, gatk1, vcf1]):
        mean_val = np.mean(vals)
        ax1.hlines(mean_val, i - 0.3, i + 0.3, colors='black', linewidth=3, zorder=4)
        ax1.text(i, mean_val + 8, f'{mean_val:.0f}', ha='center', va='bottom',
                 fontsize=13, fontweight='bold')

    ax1.set_ylabel('Mutations Detected', fontweight='bold')
    ax1.set_title('Original & Evolved Strains\n(n=7 samples)', fontweight='bold', pad=10)
    ax1.set_xticks([0, 1, 2])
    ax1.set_xticklabels(tool_names, fontweight='bold', rotation=30, ha='right')
    ax1.set_xlim(-0.6, 2.6)

    # --- Group 2: Genome-shuffling ---
    breseq2 = [breseq_counts[s] for s in group2_samples]
    gatk2 = [gatk_counts[s] for s in group2_samples]
    vcf2 = [vcf_counts[s] for s in group2_samples]

    # Colors for Group 2: Tolerant (-I2-*) vs Sensitive (-I3-*)
    # Using colorblind-safe Teal vs Purple (distinct from left panel's Red/Blue)
    color_tolerant = '#1ABC9C'   # Teal for Tolerant (-I2-*)
    color_sensitive = '#9B59B6'  # Purple for Sensitive (-I3-*)
    colors2 = [color_tolerant if '-I2-' in s else color_sensitive for s in group2_samples]

    jitter2 = np.random.uniform(-0.15, 0.15, len(group2_samples))

    ax2.scatter(0 + jitter2, breseq2, s=marker_size, c=colors2, marker='o',
                alpha=0.5, edgecolors='white', linewidths=2, zorder=3)
    ax2.scatter(1 + jitter2, gatk2, s=marker_size, c=colors2, marker='o',
                alpha=0.5, edgecolors='white', linewidths=2, zorder=3)
    ax2.scatter(2 + jitter2, vcf2, s=marker_size, c=colors2, marker='o',
                alpha=0.5, edgecolors='white', linewidths=2, zorder=3)

    # Add legend for Group 2
    legend_elements2 = [
        Patch(facecolor=color_tolerant, edgecolor='white', label='Tolerant (-I2-*)'),
        Patch(facecolor=color_sensitive, edgecolor='white', label='Sensitive (-I3-*)')
    ]
    ax2.legend(handles=legend_elements2, loc='upper left', fontsize=10)

    # Add mean bars
    for i, vals in enumerate([breseq2, gatk2, vcf2]):
        mean_val = np.mean(vals)
        ax2.hlines(mean_val, i - 0.3, i + 0.3, colors='black', linewidth=3, zorder=4)
        ax2.text(i, mean_val + 8, f'{mean_val:.0f}', ha='center', va='bottom',
                 fontsize=13, fontweight='bold')

    ax2.set_ylabel('Mutations Detected', fontweight='bold')
    ax2.set_title('Genome-Shuffled Strains\n(n=10 samples)', fontweight='bold', pad=10)
    ax2.set_xticks([0, 1, 2])
    ax2.set_xticklabels(tool_names, fontweight='bold', rotation=30, ha='right')
    ax2.set_xlim(-0.6, 2.6)

    # Set same y-axis limits
    max_y = max(max(breseq1 + breseq2), max(gatk1 + gatk2), max(vcf1 + vcf2)) * 1.15
    ax1.set_ylim(0, max_y)
    ax2.set_ylim(0, max_y)

    # Remove top and right spines
    for ax in [ax1, ax2]:
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.tick_params(axis='both', which='both', length=5)

    plt.tight_layout()

    # Save plots
    output_dir.mkdir(parents=True, exist_ok=True)
    png_path = output_dir / 'amp_vs_vcf_presentation.png'
    pdf_path = output_dir / 'amp_vs_vcf_presentation.pdf'

    plt.savefig(png_path, dpi=300, bbox_inches='tight', facecolor='white', edgecolor='none')
    plt.savefig(pdf_path, bbox_inches='tight', facecolor='white', edgecolor='none')
    plt.close()

    # Reset style
    plt.style.use('default')

    print(f"\nPresentation plot saved to:")
    print(f"  - {png_path} (300 DPI)")
    print(f"  - {pdf_path}")

    return group1_samples, group2_samples


def create_individual_group_plots(breseq_counts, gatk_counts, vcf_counts, output_dir):
    """
    Create individual plots for each group with independent y-axis scales.
    """
    # Get common samples and classify
    common_samples = sorted(set(breseq_counts.keys()) & set(gatk_counts.keys()) & set(vcf_counts.keys()))

    if not common_samples:
        print("No common samples found!")
        return

    # Separate into groups
    group1_samples = [s for s in common_samples if classify_sample(s) == 'original_evolved']
    group2_samples = [s for s in common_samples if classify_sample(s) == 'genome_shuffling']

    # Set up presentation style
    plt.style.use('seaborn-v0_8-whitegrid')
    plt.rcParams.update({
        'font.family': 'sans-serif',
        'font.size': 14,
        'axes.titlesize': 20,
        'axes.labelsize': 16,
        'xtick.labelsize': 14,
        'ytick.labelsize': 14,
        'figure.facecolor': 'white',
        'axes.facecolor': 'white',
        'axes.edgecolor': '#333333',
        'axes.linewidth': 1.5,
    })

    marker_size = 350
    tool_names = ['Breseq (AMP)', 'GATK-HC (AMP)', 'Joint-GATK-HC (ANP)']
    np.random.seed(42)

    # Colors for Group 1: Original vs Evolved
    color_original = '#E74C3C'  # Red for original (A0-F0-*)
    color_evolved = '#4A90D9'   # Blue for evolved (*-I1-*)

    # Colors for Group 2: Tolerant vs Sensitive
    color_tolerant = '#1ABC9C'   # Teal for Tolerant (-I2-*)
    color_sensitive = '#9B59B6'  # Purple for Sensitive (-I3-*)

    output_dir.mkdir(parents=True, exist_ok=True)

    # --- Group 1: Original/Evolved (individual plot) ---
    fig1, ax1 = plt.subplots(figsize=(8, 7))
    fig1.patch.set_facecolor('white')

    breseq1 = [breseq_counts[s] for s in group1_samples]
    gatk1 = [gatk_counts[s] for s in group1_samples]
    vcf1 = [vcf_counts[s] for s in group1_samples]

    colors1 = [color_original if s.startswith('A0-F0-') else color_evolved for s in group1_samples]
    jitter1 = np.random.uniform(-0.15, 0.15, len(group1_samples))

    ax1.scatter(0 + jitter1, breseq1, s=marker_size, c=colors1, marker='o',
                alpha=0.5, edgecolors='white', linewidths=2, zorder=3)
    ax1.scatter(1 + jitter1, gatk1, s=marker_size, c=colors1, marker='o',
                alpha=0.5, edgecolors='white', linewidths=2, zorder=3)
    ax1.scatter(2 + jitter1, vcf1, s=marker_size, c=colors1, marker='o',
                alpha=0.5, edgecolors='white', linewidths=2, zorder=3)

    from matplotlib.patches import Patch
    legend_elements = [
        Patch(facecolor=color_original, edgecolor='white', label='Original (A0-F0-*)'),
        Patch(facecolor=color_evolved, edgecolor='white', label='Evolved (*-I1-*)')
    ]
    ax1.legend(handles=legend_elements, loc='upper left', fontsize=10)

    for i, vals in enumerate([breseq1, gatk1, vcf1]):
        mean_val = np.mean(vals)
        ax1.hlines(mean_val, i - 0.3, i + 0.3, colors='black', linewidth=3, zorder=4)
        ax1.text(i, mean_val + max(breseq1 + gatk1 + vcf1) * 0.03, f'{mean_val:.0f}', ha='center', va='bottom',
                 fontsize=13, fontweight='bold')

    ax1.set_ylabel('Mutations Detected', fontweight='bold')
    ax1.set_title('Original & Evolved Strains\n(n=7 samples)', fontweight='bold', pad=10)
    ax1.set_xticks([0, 1, 2])
    ax1.set_xticklabels(tool_names, fontweight='bold', rotation=30, ha='right')
    ax1.set_xlim(-0.6, 2.6)
    ax1.set_ylim(0, max(breseq1 + gatk1 + vcf1) * 1.15)
    ax1.spines['top'].set_visible(False)
    ax1.spines['right'].set_visible(False)
    ax1.tick_params(axis='both', which='both', length=5)

    plt.tight_layout()
    plt.savefig(output_dir / 'amp_vs_vcf_group1_original_evolved.png', dpi=300, bbox_inches='tight',
                facecolor='white', edgecolor='none')
    plt.savefig(output_dir / 'amp_vs_vcf_group1_original_evolved.pdf', bbox_inches='tight',
                facecolor='white', edgecolor='none')
    plt.close()

    # --- Group 2: Genome-shuffling (individual plot) ---
    fig2, ax2 = plt.subplots(figsize=(8, 7))
    fig2.patch.set_facecolor('white')

    breseq2 = [breseq_counts[s] for s in group2_samples]
    gatk2 = [gatk_counts[s] for s in group2_samples]
    vcf2 = [vcf_counts[s] for s in group2_samples]

    colors2 = [color_tolerant if '-I2-' in s else color_sensitive for s in group2_samples]
    jitter2 = np.random.uniform(-0.15, 0.15, len(group2_samples))

    ax2.scatter(0 + jitter2, breseq2, s=marker_size, c=colors2, marker='o',
                alpha=0.5, edgecolors='white', linewidths=2, zorder=3)
    ax2.scatter(1 + jitter2, gatk2, s=marker_size, c=colors2, marker='o',
                alpha=0.5, edgecolors='white', linewidths=2, zorder=3)
    ax2.scatter(2 + jitter2, vcf2, s=marker_size, c=colors2, marker='o',
                alpha=0.5, edgecolors='white', linewidths=2, zorder=3)

    legend_elements2 = [
        Patch(facecolor=color_tolerant, edgecolor='white', label='Tolerant (-I2-*)'),
        Patch(facecolor=color_sensitive, edgecolor='white', label='Sensitive (-I3-*)')
    ]
    ax2.legend(handles=legend_elements2, loc='upper left', fontsize=10)

    for i, vals in enumerate([breseq2, gatk2, vcf2]):
        mean_val = np.mean(vals)
        ax2.hlines(mean_val, i - 0.3, i + 0.3, colors='black', linewidth=3, zorder=4)
        ax2.text(i, mean_val + max(breseq2 + gatk2 + vcf2) * 0.03, f'{mean_val:.0f}', ha='center', va='bottom',
                 fontsize=13, fontweight='bold')

    ax2.set_ylabel('Mutations Detected', fontweight='bold')
    ax2.set_title('Genome-Shuffled Strains\n(n=10 samples)', fontweight='bold', pad=10)
    ax2.set_xticks([0, 1, 2])
    ax2.set_xticklabels(tool_names, fontweight='bold', rotation=30, ha='right')
    ax2.set_xlim(-0.6, 2.6)
    ax2.set_ylim(0, max(breseq2 + gatk2 + vcf2) * 1.15)
    ax2.spines['top'].set_visible(False)
    ax2.spines['right'].set_visible(False)
    ax2.tick_params(axis='both', which='both', length=5)

    plt.tight_layout()
    plt.savefig(output_dir / 'amp_vs_vcf_group2_genome_shuffled.png', dpi=300, bbox_inches='tight',
                facecolor='white', edgecolor='none')
    plt.savefig(output_dir / 'amp_vs_vcf_group2_genome_shuffled.pdf', bbox_inches='tight',
                facecolor='white', edgecolor='none')
    plt.close()

    # Reset style
    plt.style.use('default')

    print(f"\nIndividual group plots saved to:")
    print(f"  - {output_dir / 'amp_vs_vcf_group1_original_evolved.png'}")
    print(f"  - {output_dir / 'amp_vs_vcf_group1_original_evolved.pdf'}")
    print(f"  - {output_dir / 'amp_vs_vcf_group2_genome_shuffled.png'}")
    print(f"  - {output_dir / 'amp_vs_vcf_group2_genome_shuffled.pdf'}")


if __name__ == '__main__':
    print("Loading AMP mutation counts by tool...")
    breseq_counts, gatk_counts = get_amp_counts_by_tool(AMP_CSV)
    print(f"  Found {len(breseq_counts)} samples in AMP CSV")
    print(f"  breseq total: {sum(breseq_counts.values())}")
    print(f"  GATK total: {sum(gatk_counts.values())}")

    print("\nLoading VCF genotype counts...")
    vcf_counts = get_vcf_counts(VCF_FILE)
    print(f"  Found {len(vcf_counts)} samples in VCF")
    print(f"  Joint-GATK total: {sum(vcf_counts.values())}")

    print("\nCreating scatter plot (by tool)...")
    create_scatter_plot_by_tool(breseq_counts, gatk_counts, vcf_counts, OUTPUT_DIR)

    print("\nCreating scatter plot (by group)...")
    create_scatter_plot_by_group(breseq_counts, gatk_counts, vcf_counts, OUTPUT_DIR)

    print("\nCreating presentation plot...")
    create_presentation_plot(breseq_counts, gatk_counts, vcf_counts, OUTPUT_DIR)

    print("\nCreating individual group plots...")
    create_individual_group_plots(breseq_counts, gatk_counts, vcf_counts, OUTPUT_DIR)

    # Also create combined plot for comparison
    print("\nCreating combined scatter plot...")
    amp_counts = get_amp_counts(AMP_CSV)
    create_scatter_plot(amp_counts, vcf_counts, OUTPUT_DIR)
