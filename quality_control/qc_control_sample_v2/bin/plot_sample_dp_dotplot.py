#!/usr/bin/env python3
"""
Generate depth dotplot for a specific sample.
Usage: python plot_sample_dp_dotplot.py <sample_name>
Example: python plot_sample_dp_dotplot.py A1-F6-I2-R1
"""

import sys
import subprocess
import csv
from pathlib import Path
import matplotlib.pyplot as plt
import numpy as np

def get_vcf_data(vcf_file, sample_name):
    """Extract position and depth data from VCF."""
    vcf_sample = f'ALE_Exp1_{sample_name}'

    cmd = ['bcftools', 'query',
           '-f', '%CHROM\t%POS\t%REF\t%ALT\t%FILTER\t[%GT]\t[%DP]\n',
           '-s', vcf_sample,
           str(vcf_file)]

    result = subprocess.run(cmd, capture_output=True, text=True, check=True)

    data = []
    for line in result.stdout.strip().split('\n'):
        if not line:
            continue
        fields = line.split('\t')
        if len(fields) >= 7:
            chrom, pos, ref, alt, filt, gt, dp = fields
            # Only non-ref genotypes
            if gt not in ['0', '0/0', './.', '.', '0/0/0']:
                try:
                    dp_val = int(dp) if dp.isdigit() else 0
                except:
                    dp_val = 0
                data.append({
                    'chrom': chrom,
                    'pos': int(pos),
                    'ref': ref,
                    'alt': alt,
                    'filter': filt,
                    'gt': gt,
                    'dp': dp_val
                })
    return data

def get_csv_positions(tsv_file):
    """Get detected positions from AMP TSV."""
    positions = set()
    with open(tsv_file, 'r') as f:
        reader = csv.DictReader(f, delimiter='\t')
        for row in reader:
            if row['DETECTED'] == 'YES':
                positions.add((row['CHROM'], int(row['POS'])))
    return positions

def classify_match(vcf_data, csv_positions, window=50):
    """Classify VCF variants as exact match, fuzzy match, or VCF-only."""
    classified = []

    for var in vcf_data:
        pos = (var['chrom'], var['pos'])
        if pos in csv_positions:
            var['match_type'] = 'exact'
        else:
            # Check for fuzzy match
            fuzzy_found = False
            for csv_chrom, csv_pos in csv_positions:
                if csv_chrom == var['chrom'] and 0 < abs(csv_pos - var['pos']) <= window:
                    var['match_type'] = 'fuzzy'
                    fuzzy_found = True
                    break
            if not fuzzy_found:
                var['match_type'] = 'vcf_only'
        classified.append(var)

    return classified

def create_dotplot(sample_name, classified_data, output_dir):
    """Create depth dotplot."""
    fig, axes = plt.subplots(2, 1, figsize=(14, 10))

    # Extract data by match type
    exact = [d for d in classified_data if d['match_type'] == 'exact']
    fuzzy = [d for d in classified_data if d['match_type'] == 'fuzzy']
    vcf_only = [d for d in classified_data if d['match_type'] == 'vcf_only']

    # Top plot: Depth by match type (strip plot)
    ax1 = axes[0]

    # Create jittered x positions
    np.random.seed(42)
    categories = ['Exact Match', 'Fuzzy Match (±50bp)', 'VCF Only']
    colors = ['#2ECC71', '#F1C40F', '#E74C3C']

    all_groups = [exact, fuzzy, vcf_only]

    for i, (group, cat, color) in enumerate(zip(all_groups, categories, colors)):
        if group:
            dps = [d['dp'] for d in group]
            x = np.random.normal(i, 0.1, len(dps))
            ax1.scatter(x, dps, c=color, alpha=0.6, s=40, label=f'{cat} (n={len(group)})')

            # Add median line
            median_dp = np.median(dps)
            ax1.hlines(median_dp, i - 0.3, i + 0.3, colors='black', linewidth=2)
            ax1.text(i + 0.35, median_dp, f'med={median_dp:.0f}', fontsize=9, va='center')

    ax1.set_xticks(range(len(categories)))
    ax1.set_xticklabels(categories, fontsize=11)
    ax1.set_ylabel('Read Depth (DP)', fontsize=12, fontweight='bold')
    ax1.set_title(f'{sample_name}\nVariant Depth by Match Type', fontsize=14, fontweight='bold')
    ax1.legend(loc='upper right')
    ax1.grid(axis='y', alpha=0.3)
    ax1.set_ylim(bottom=0)

    # Bottom plot: Depth distribution histogram
    ax2 = axes[1]

    bins = np.arange(0, max([d['dp'] for d in classified_data]) + 10, 5)

    for group, cat, color in zip(all_groups, categories, colors):
        if group:
            dps = [d['dp'] for d in group]
            ax2.hist(dps, bins=bins, alpha=0.5, label=f'{cat}', color=color, edgecolor='black')

    ax2.set_xlabel('Read Depth (DP)', fontsize=12, fontweight='bold')
    ax2.set_ylabel('Count', fontsize=12, fontweight='bold')
    ax2.set_title(f'{sample_name}\nDepth Distribution', fontsize=14, fontweight='bold')
    ax2.legend()
    ax2.grid(axis='y', alpha=0.3)

    # Add summary stats
    all_dps = [d['dp'] for d in classified_data]
    vcf_only_dps = [d['dp'] for d in vcf_only] if vcf_only else []
    matched_dps = [d['dp'] for d in exact + fuzzy] if (exact or fuzzy) else []

    stats_text = f"All variants: n={len(all_dps)}, mean DP={np.mean(all_dps):.1f}\n"
    if matched_dps:
        stats_text += f"Matched: n={len(matched_dps)}, mean DP={np.mean(matched_dps):.1f}\n"
    if vcf_only_dps:
        stats_text += f"VCF-only: n={len(vcf_only_dps)}, mean DP={np.mean(vcf_only_dps):.1f}"

    ax2.text(0.98, 0.98, stats_text, transform=ax2.transAxes, fontsize=10,
             verticalalignment='top', horizontalalignment='right',
             bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))

    plt.tight_layout()

    # Save
    output_dir.mkdir(parents=True, exist_ok=True)
    png_path = output_dir / f'{sample_name}_dp_dotplot.png'
    pdf_path = output_dir / f'{sample_name}_dp_dotplot.pdf'

    plt.savefig(png_path, dpi=150, bbox_inches='tight')
    plt.savefig(pdf_path, bbox_inches='tight')
    plt.close()

    print(f"Dot plot saved to:")
    print(f"  - {png_path}")
    print(f"  - {pdf_path}")

def main(sample_name):
    """Generate dotplot for specified sample."""
    vcf_file = Path(f'data/{sample_name}.haplotypecaller.from_joint_calling_snpEff.ann.vcf.gz')
    tsv_file = Path(f'output/{sample_name}_AMP_mutations.tsv')
    output_dir = Path('comparison')

    if not vcf_file.exists():
        print(f"Error: VCF not found: {vcf_file}")
        sys.exit(1)

    if not tsv_file.exists():
        print(f"Error: AMP TSV not found: {tsv_file}")
        print("Run parse_amp_csv.py first.")
        sys.exit(1)

    print(f"Loading VCF data for {sample_name}...")
    vcf_data = get_vcf_data(vcf_file, sample_name)
    print(f"  Found {len(vcf_data)} non-ref variants")

    print("Loading AMP positions...")
    csv_positions = get_csv_positions(tsv_file)
    print(f"  Found {len(csv_positions)} unique positions")

    print("Classifying variants...")
    classified = classify_match(vcf_data, csv_positions)

    print("Creating dotplot...")
    create_dotplot(sample_name, classified, output_dir)

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python plot_sample_dp_dotplot.py <sample_name>")
        print("Example: python plot_sample_dp_dotplot.py A1-F6-I2-R1")
        sys.exit(1)

    sample_name = sys.argv[1]
    main(sample_name)
