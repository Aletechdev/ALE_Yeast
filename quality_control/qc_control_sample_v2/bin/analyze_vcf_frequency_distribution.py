#!/usr/bin/env python3
"""
Analyze mutation frequency distribution from Joint-GATK-HC VCF.
Compares frequency distributions between:
- A0-F0-* (ancestral/original)
- *-I1-* (evolved isolate 1)
- Other samples (genome-shuffled: -I2-*, -I3-*)

Filters: PASS variants, biallelic (single ALT allele)
"""
import subprocess
import numpy as np
import matplotlib.pyplot as plt
from collections import defaultdict
from pathlib import Path

# File paths
VCF_FILE = Path('data/HaplotypeCaller_joint_calling_soft_filtered_snpEff.ann.vcf.gz')
OUTPUT_DIR = Path('comparison')


def classify_sample(sample_name):
    """
    Classify sample into groups:
    - 'ancestral': A0-F0-* samples
    - 'evolved': *-I1-* samples
    - 'genome_shuffled': *-I2-* and *-I3-* samples
    """
    short_name = sample_name.replace('ALE_Exp1_', '')
    if short_name.startswith('A0-F0-'):
        return 'ancestral'
    elif '-I1-' in short_name:
        return 'evolved'
    else:
        return 'genome_shuffled'


def get_sample_frequencies(vcf_file):
    """
    Extract allele frequencies for each sample from VCF.
    Filters for PASS variants and biallelic sites.

    Returns dict: sample_name -> list of frequencies
    """
    # Get sample list
    cmd = ['bcftools', 'query', '-l', str(vcf_file)]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    samples = result.stdout.strip().split('\n')

    print(f"Found {len(samples)} samples in VCF")

    # Initialize frequency storage
    sample_frequencies = {s: [] for s in samples}

    # Query VCF for PASS, biallelic variants
    # Format: CHROM, POS, REF, ALT, FILTER, then for each sample: GT, AD, DP
    # AD format: REF_depth,ALT_depth
    cmd = [
        'bcftools', 'query',
        '-f', '%CHROM\t%POS\t%REF\t%ALT\t%FILTER[\t%GT\t%AD\t%DP]\n',
        '-i', 'FILTER="PASS"',  # Only PASS variants
        str(vcf_file)
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, check=True)

    total_variants = 0
    biallelic_variants = 0

    for line in result.stdout.strip().split('\n'):
        if not line:
            continue

        fields = line.split('\t')
        chrom, pos, ref, alt, filt = fields[0], fields[1], fields[2], fields[3], fields[4]

        total_variants += 1

        # Skip multiallelic sites (ALT contains comma)
        if ',' in alt:
            continue

        biallelic_variants += 1

        # Parse sample data (GT, AD, DP for each sample)
        sample_data = fields[5:]

        for i, sample in enumerate(samples):
            idx = i * 3  # Each sample has 3 fields: GT, AD, DP
            if idx + 2 >= len(sample_data):
                continue

            gt = sample_data[idx]
            ad = sample_data[idx + 1]
            dp = sample_data[idx + 2]

            # Skip if no call or reference call
            if gt in ['./.', '.', '0/0', '0', '0|0']:
                continue

            # Parse AD field (REF_depth,ALT_depth)
            if ad and ',' in ad:
                try:
                    ad_parts = ad.split(',')
                    ref_depth = int(ad_parts[0]) if ad_parts[0].isdigit() else 0
                    alt_depth = int(ad_parts[1]) if ad_parts[1].isdigit() else 0

                    total_depth = ref_depth + alt_depth
                    if total_depth > 0:
                        freq = alt_depth / total_depth
                        sample_frequencies[sample].append(freq)
                except (ValueError, IndexError):
                    pass

    print(f"Total PASS variants: {total_variants}")
    print(f"Biallelic PASS variants: {biallelic_variants}")

    return sample_frequencies


def create_frequency_distribution_plot(sample_frequencies, output_dir):
    """
    Create plots comparing frequency distributions between groups.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    # Group frequencies
    groups = {
        'Ancestral (A0-F0-*)': [],
        'Evolved (*-I1-*)': [],
        'Genome-Shuffled (*-I2/I3-*)': []
    }

    group_samples = {
        'Ancestral (A0-F0-*)': [],
        'Evolved (*-I1-*)': [],
        'Genome-Shuffled (*-I2/I3-*)': []
    }

    for sample, freqs in sample_frequencies.items():
        sample_class = classify_sample(sample)
        if sample_class == 'ancestral':
            groups['Ancestral (A0-F0-*)'].extend(freqs)
            group_samples['Ancestral (A0-F0-*)'].append(sample)
        elif sample_class == 'evolved':
            groups['Evolved (*-I1-*)'].extend(freqs)
            group_samples['Evolved (*-I1-*)'].append(sample)
        else:
            groups['Genome-Shuffled (*-I2/I3-*)'].extend(freqs)
            group_samples['Genome-Shuffled (*-I2/I3-*)'].append(sample)

    # Print summary
    print("\n" + "="*70)
    print("FREQUENCY DISTRIBUTION SUMMARY")
    print("="*70)
    for group_name, freqs in groups.items():
        n_samples = len(group_samples[group_name])
        print(f"\n{group_name}:")
        print(f"  Samples: {n_samples}")
        print(f"  Sample names: {', '.join([s.replace('ALE_Exp1_', '') for s in group_samples[group_name]])}")
        if freqs:
            print(f"  Total mutations: {len(freqs)}")
            print(f"  Mean frequency: {np.mean(freqs):.3f}")
            print(f"  Median frequency: {np.median(freqs):.3f}")
            print(f"  Std dev: {np.std(freqs):.3f}")
            print(f"  Min: {np.min(freqs):.3f}, Max: {np.max(freqs):.3f}")
            # Count by frequency bins
            high_freq = sum(1 for f in freqs if f >= 0.9)
            mid_freq = sum(1 for f in freqs if 0.5 <= f < 0.9)
            low_freq = sum(1 for f in freqs if f < 0.5)
            print(f"  High freq (>=0.9): {high_freq} ({high_freq/len(freqs)*100:.1f}%)")
            print(f"  Mid freq (0.5-0.9): {mid_freq} ({mid_freq/len(freqs)*100:.1f}%)")
            print(f"  Low freq (<0.5): {low_freq} ({low_freq/len(freqs)*100:.1f}%)")

    # Set up presentation style
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

    # Colors for groups
    colors = {
        'Ancestral (A0-F0-*)': '#E74C3C',      # Red
        'Evolved (*-I1-*)': '#4A90D9',          # Blue
        'Genome-Shuffled (*-I2/I3-*)': '#2ECC71'  # Green
    }

    # --- Plot 1: Histogram overlay ---
    fig1, ax1 = plt.subplots(figsize=(10, 7))
    fig1.patch.set_facecolor('white')

    bins = np.linspace(0, 1, 21)  # 20 bins from 0 to 1

    for group_name, freqs in groups.items():
        if freqs:
            ax1.hist(freqs, bins=bins, alpha=0.5, label=f'{group_name} (n={len(freqs)})',
                    color=colors[group_name], edgecolor='white', linewidth=0.5)

    ax1.set_xlabel('Allele Frequency', fontweight='bold')
    ax1.set_ylabel('Count', fontweight='bold')
    ax1.set_title('Mutation Frequency Distribution by Sample Group\n(PASS, Biallelic Variants)',
                  fontweight='bold', pad=10)
    ax1.legend(loc='upper left', fontsize=10)
    ax1.set_xlim(0, 1)
    ax1.spines['top'].set_visible(False)
    ax1.spines['right'].set_visible(False)

    plt.tight_layout()
    plt.savefig(output_dir / 'vcf_frequency_histogram.png', dpi=300, bbox_inches='tight',
                facecolor='white', edgecolor='none')
    plt.savefig(output_dir / 'vcf_frequency_histogram.pdf', bbox_inches='tight',
                facecolor='white', edgecolor='none')
    plt.close()

    # --- Plot 2: Box plot comparison ---
    fig2, ax2 = plt.subplots(figsize=(10, 7))
    fig2.patch.set_facecolor('white')

    group_names = list(groups.keys())
    group_data = [groups[g] for g in group_names]
    group_colors = [colors[g] for g in group_names]

    bp = ax2.boxplot(group_data, patch_artist=True, labels=['Ancestral\n(A0-F0-*)',
                                                             'Evolved\n(*-I1-*)',
                                                             'Genome-Shuffled\n(*-I2/I3-*)'])

    for patch, color in zip(bp['boxes'], group_colors):
        patch.set_facecolor(color)
        patch.set_alpha(0.6)

    for median in bp['medians']:
        median.set_color('black')
        median.set_linewidth(2)

    ax2.set_ylabel('Allele Frequency', fontweight='bold')
    ax2.set_title('Mutation Frequency Distribution Comparison\n(PASS, Biallelic Variants)',
                  fontweight='bold', pad=10)
    ax2.set_ylim(0, 1.05)
    ax2.spines['top'].set_visible(False)
    ax2.spines['right'].set_visible(False)

    # Add sample counts
    for i, (name, freqs) in enumerate(groups.items(), 1):
        ax2.text(i, -0.08, f'n={len(freqs)}', ha='center', va='top', fontsize=10,
                transform=ax2.get_xaxis_transform())

    plt.tight_layout()
    plt.savefig(output_dir / 'vcf_frequency_boxplot.png', dpi=300, bbox_inches='tight',
                facecolor='white', edgecolor='none')
    plt.savefig(output_dir / 'vcf_frequency_boxplot.pdf', bbox_inches='tight',
                facecolor='white', edgecolor='none')
    plt.close()

    # --- Plot 3: Violin plot ---
    fig3, ax3 = plt.subplots(figsize=(10, 7))
    fig3.patch.set_facecolor('white')

    positions = [1, 2, 3]
    for i, (name, freqs) in enumerate(groups.items()):
        if freqs:
            parts = ax3.violinplot([freqs], positions=[positions[i]], showmeans=True,
                                   showmedians=True, widths=0.7)
            for pc in parts['bodies']:
                pc.set_facecolor(colors[name])
                pc.set_alpha(0.6)
            parts['cmeans'].set_color('black')
            parts['cmedians'].set_color('red')

    ax3.set_xticks(positions)
    ax3.set_xticklabels(['Ancestral\n(A0-F0-*)', 'Evolved\n(*-I1-*)', 'Genome-Shuffled\n(*-I2/I3-*)'])
    ax3.set_ylabel('Allele Frequency', fontweight='bold')
    ax3.set_title('Mutation Frequency Distribution (Violin Plot)\n(PASS, Biallelic Variants)',
                  fontweight='bold', pad=10)
    ax3.set_ylim(0, 1.05)
    ax3.spines['top'].set_visible(False)
    ax3.spines['right'].set_visible(False)

    # Add legend for mean/median
    from matplotlib.lines import Line2D
    legend_elements = [
        Line2D([0], [0], color='black', linewidth=2, label='Mean'),
        Line2D([0], [0], color='red', linewidth=2, label='Median')
    ]
    ax3.legend(handles=legend_elements, loc='lower right', fontsize=10)

    plt.tight_layout()
    plt.savefig(output_dir / 'vcf_frequency_violin.png', dpi=300, bbox_inches='tight',
                facecolor='white', edgecolor='none')
    plt.savefig(output_dir / 'vcf_frequency_violin.pdf', bbox_inches='tight',
                facecolor='white', edgecolor='none')
    plt.close()

    # Reset style
    plt.style.use('default')

    print(f"\nPlots saved to:")
    print(f"  - {output_dir / 'vcf_frequency_histogram.png'}")
    print(f"  - {output_dir / 'vcf_frequency_boxplot.png'}")
    print(f"  - {output_dir / 'vcf_frequency_violin.png'}")

    return groups


def create_per_sample_summary(sample_frequencies, output_dir):
    """
    Create per-sample frequency summary.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    summary_file = output_dir / 'vcf_frequency_per_sample_summary.txt'

    with open(summary_file, 'w') as f:
        f.write("VCF MUTATION FREQUENCY SUMMARY BY SAMPLE\n")
        f.write("="*70 + "\n")
        f.write("Filter: PASS variants, biallelic only\n")
        f.write("Frequency = ALT_depth / (REF_depth + ALT_depth)\n")
        f.write("="*70 + "\n\n")

        f.write(f"{'Sample':<20} {'Group':<15} {'N_Muts':>8} {'Mean':>8} {'Median':>8} {'Std':>8} {'>=0.9':>8}\n")
        f.write("-"*80 + "\n")

        for sample in sorted(sample_frequencies.keys()):
            freqs = sample_frequencies[sample]
            short_name = sample.replace('ALE_Exp1_', '')
            group = classify_sample(sample)

            if freqs:
                mean_f = np.mean(freqs)
                median_f = np.median(freqs)
                std_f = np.std(freqs)
                high_f = sum(1 for f in freqs if f >= 0.9)
                f.write(f"{short_name:<20} {group:<15} {len(freqs):>8} {mean_f:>8.3f} {median_f:>8.3f} {std_f:>8.3f} {high_f:>8}\n")
            else:
                f.write(f"{short_name:<20} {group:<15} {0:>8} {'N/A':>8} {'N/A':>8} {'N/A':>8} {0:>8}\n")

    print(f"\nPer-sample summary saved to: {summary_file}")


if __name__ == '__main__':
    print("Extracting allele frequencies from VCF...")
    print(f"VCF file: {VCF_FILE}")
    print("Filters: PASS, biallelic variants only")
    print()

    sample_frequencies = get_sample_frequencies(VCF_FILE)

    print("\nCreating frequency distribution plots...")
    groups = create_frequency_distribution_plot(sample_frequencies, OUTPUT_DIR)

    print("\nCreating per-sample summary...")
    create_per_sample_summary(sample_frequencies, OUTPUT_DIR)
