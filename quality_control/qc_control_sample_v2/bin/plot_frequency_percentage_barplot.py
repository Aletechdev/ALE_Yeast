#!/usr/bin/env python3
"""
Create stacked bar chart showing percentage breakdown of high, mid, and low
frequency mutations for the 3 sample groups:
- Ancestral (A0-F0-*)
- Evolved (*-I1-*)
- Genome-Shuffled (*-I2/I3-*)

Frequency bins:
- High: >= 0.9
- Mid: 0.5 - 0.9
- Low: < 0.5
"""
import subprocess
import numpy as np
import matplotlib.pyplot as plt
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
    """
    # Get sample list
    cmd = ['bcftools', 'query', '-l', str(vcf_file)]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    samples = result.stdout.strip().split('\n')

    print(f"Found {len(samples)} samples in VCF")

    # Initialize frequency storage
    sample_frequencies = {s: [] for s in samples}

    # Query VCF for PASS, biallelic variants
    cmd = [
        'bcftools', 'query',
        '-f', '%CHROM\t%POS\t%REF\t%ALT\t%FILTER[\t%GT\t%AD\t%DP]\n',
        '-i', 'FILTER="PASS"',
        str(vcf_file)
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, check=True)

    for line in result.stdout.strip().split('\n'):
        if not line:
            continue

        fields = line.split('\t')
        chrom, pos, ref, alt, filt = fields[0], fields[1], fields[2], fields[3], fields[4]

        # Skip multiallelic sites
        if ',' in alt:
            continue

        # Parse sample data
        sample_data = fields[5:]

        for i, sample in enumerate(samples):
            idx = i * 3
            if idx + 2 >= len(sample_data):
                continue

            gt = sample_data[idx]
            ad = sample_data[idx + 1]

            # Skip if no call or reference call
            if gt in ['./.', '.', '0/0', '0', '0|0']:
                continue

            # Parse AD field
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

    return sample_frequencies


def calculate_group_percentages(sample_frequencies):
    """
    Calculate percentage of high, mid, low frequency mutations per group.
    Also counts the number of samples in each group.
    """
    # Track frequencies and sample counts per group
    group_data = {
        'ancestral': {'freqs': [], 'samples': set()},
        'evolved': {'freqs': [], 'samples': set()},
        'genome_shuffled': {'freqs': [], 'samples': set()}
    }

    for sample, freqs in sample_frequencies.items():
        sample_class = classify_sample(sample)
        if sample_class in group_data:
            group_data[sample_class]['freqs'].extend(freqs)
            group_data[sample_class]['samples'].add(sample)

    # Build group names with sample counts
    n_ancestral = len(group_data['ancestral']['samples'])
    n_evolved = len(group_data['evolved']['samples'])
    n_shuffled = len(group_data['genome_shuffled']['samples'])

    groups = {
        f'Ancestral\n(A0-F0-*, n={n_ancestral})': group_data['ancestral']['freqs'],
        f'Evolved\n(*-I1-*, n={n_evolved})': group_data['evolved']['freqs'],
        f'Genome-Shuffled\n(*-I2/I3-*, n={n_shuffled})': group_data['genome_shuffled']['freqs']
    }

    # Calculate percentages
    percentages = {}
    for group_name, freqs in groups.items():
        if freqs:
            high = sum(1 for f in freqs if f >= 0.9)
            mid = sum(1 for f in freqs if 0.5 <= f < 0.9)
            low = sum(1 for f in freqs if f < 0.5)
            total = len(freqs)

            percentages[group_name] = {
                'high': high / total * 100,
                'mid': mid / total * 100,
                'low': low / total * 100,
                'total': total
            }
        else:
            percentages[group_name] = {'high': 0, 'mid': 0, 'low': 0, 'total': 0}

    return percentages


def create_percentage_barplot(percentages, output_dir):
    """
    Create stacked bar plot showing absolute counts with percentage labels.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

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

    # Create figure
    fig, ax = plt.subplots(figsize=(10, 7))
    fig.patch.set_facecolor('white')

    # Group names and data
    group_names = list(percentages.keys())
    x = np.arange(len(group_names))
    bar_width = 0.6

    # Colors - colorblind-safe palette (Wong palette)
    color_high = '#0072B2'   # Blue for high freq (>=0.9)
    color_mid = '#E69F00'    # Orange/Amber for mid freq (0.5-0.9)
    color_low = '#CC79A7'    # Pink/Magenta for low freq (<0.5)

    # Extract data - absolute counts
    high_pct = [percentages[g]['high'] for g in group_names]
    mid_pct = [percentages[g]['mid'] for g in group_names]
    low_pct = [percentages[g]['low'] for g in group_names]
    totals = [percentages[g]['total'] for g in group_names]

    # Calculate absolute counts
    high_counts = [int(round(h * t / 100)) for h, t in zip(high_pct, totals)]
    mid_counts = [int(round(m * t / 100)) for m, t in zip(mid_pct, totals)]
    low_counts = [int(round(l * t / 100)) for l, t in zip(low_pct, totals)]

    # Create stacked bars with absolute counts
    bars_high = ax.bar(x, high_counts, bar_width, label='High Freq (>=0.9)',
                       color=color_high, edgecolor='white', linewidth=1.5)
    bars_mid = ax.bar(x, mid_counts, bar_width, bottom=high_counts,
                      label='Mid Freq (0.5-0.9)', color=color_mid,
                      edgecolor='white', linewidth=1.5)
    bars_low = ax.bar(x, low_counts, bar_width, bottom=np.array(high_counts) + np.array(mid_counts),
                      label='Low Freq (<0.5)', color=color_low,
                      edgecolor='white', linewidth=1.5)

    # Add labels on bars: count (percentage) - single line format
    for i, (hc, mc, lc, hp, mp, lp, total) in enumerate(zip(high_counts, mid_counts, low_counts, high_pct, mid_pct, low_pct, totals)):
        # High freq label
        if hc > 20:
            ax.text(i, hc/2, f'{hc} ({hp:.0f}%)', ha='center', va='center',
                   fontsize=12, fontweight='bold', color='white')
        # Mid freq label
        if mc > 20:
            ax.text(i, hc + mc/2, f'{mc} ({mp:.0f}%)', ha='center', va='center',
                   fontsize=12, fontweight='bold', color='white')
        # Low freq label - don't show on bar (too small), will be in legend note

    # Add total count labels on top (moved higher to avoid overlap)
    for i, total in enumerate(totals):
        ax.text(i, total + max(totals) * 0.05, f'n={total}', ha='center', va='bottom',
               fontsize=13, fontweight='bold')

    # Customize plot
    ax.set_ylabel('Number of Mutations', fontweight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels(group_names, fontweight='bold')
    ax.set_ylim(0, max(totals) * 1.25)
    ax.set_xlim(-0.5, len(group_names) - 0.5)

    # Remove top and right spines
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)

    # Legend - position upper left to avoid overlap
    ax.legend(loc='upper left', fontsize=11, framealpha=0.9,
              edgecolor='black', fancybox=True)

    # Add note about low frequency counts - more visible
    low_note = f'Low Freq (<0.5): Ancestral {low_counts[0]} ({low_pct[0]:.1f}%),  Evolved {low_counts[1]} ({low_pct[1]:.1f}%),  Genome-Shuffled {low_counts[2]} ({low_pct[2]:.1f}%)'
    ax.text(0.5, -0.10, low_note, ha='center', va='top', fontsize=11,
            transform=ax.transAxes, fontweight='bold', color='#CC79A7')

    # Title
    ax.set_title('Mutation Frequency Distribution by Sample Group\n(PASS, Biallelic Variants from Joint-GATK-HC)',
                fontweight='bold', pad=15)

    plt.tight_layout()

    # Save
    plt.savefig(output_dir / 'vcf_frequency_percentage_barplot.png', dpi=300,
                bbox_inches='tight', facecolor='white', edgecolor='none')
    plt.savefig(output_dir / 'vcf_frequency_percentage_barplot.pdf',
                bbox_inches='tight', facecolor='white', edgecolor='none')
    plt.close()

    # Reset style
    plt.style.use('default')

    print(f"\nPlot saved to:")
    print(f"  - {output_dir / 'vcf_frequency_percentage_barplot.png'}")
    print(f"  - {output_dir / 'vcf_frequency_percentage_barplot.pdf'}")

    # Print summary
    print("\n" + "="*60)
    print("FREQUENCY PERCENTAGE SUMMARY")
    print("="*60)
    for group_name, data in percentages.items():
        print(f"\n{group_name.replace(chr(10), ' ')}:")
        print(f"  High (>=0.9):    {data['high']:.1f}%")
        print(f"  Mid (0.5-0.9):   {data['mid']:.1f}%")
        print(f"  Low (<0.5):      {data['low']:.1f}%")
        print(f"  Total mutations: {data['total']}")


if __name__ == '__main__':
    print("Extracting allele frequencies from VCF...")
    print(f"VCF file: {VCF_FILE}")
    print("Filters: PASS, biallelic variants only\n")

    sample_frequencies = get_sample_frequencies(VCF_FILE)
    percentages = calculate_group_percentages(sample_frequencies)
    create_percentage_barplot(percentages, OUTPUT_DIR)
