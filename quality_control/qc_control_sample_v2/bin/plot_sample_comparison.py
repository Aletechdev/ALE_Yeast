#!/usr/bin/env python3
"""
Generate comparison barplot for a specific sample.
Usage: python plot_sample_comparison.py <sample_name>
Example: python plot_sample_comparison.py A1-F6-I2-R1
"""

import sys
import csv
from pathlib import Path
import matplotlib.pyplot as plt
import numpy as np

def get_amp_count(tsv_file):
    """Count detected mutations from AMP TSV."""
    count = 0
    with open(tsv_file, 'r') as f:
        reader = csv.DictReader(f, delimiter='\t')
        for row in reader:
            if row['DETECTED'] == 'YES':
                count += 1
    return count

def parse_summary(summary_file):
    """Parse comparison summary file to extract key metrics."""
    metrics = {}
    with open(summary_file, 'r') as f:
        content = f.read()

        for line in content.split('\n'):
            if 'VCF mutations' in line:
                metrics['vcf_total'] = int(line.split(':')[1].strip())
            elif 'CSV mutations' in line:
                metrics['csv_total'] = int(line.split(':')[1].strip())
            elif 'Exact matches' in line and '(' in line:
                metrics['exact'] = int(line.split(':')[1].split('(')[0].strip())
            elif 'Fuzzy matches' in line and '(' in line:
                metrics['fuzzy'] = int(line.split(':')[1].split('(')[0].strip())
            elif 'CSV-only' in line and '(' in line:
                metrics['csv_only'] = int(line.split(':')[1].split('(')[0].strip())
            elif 'VCF-only' in line and '(' in line:
                metrics['vcf_only'] = int(line.split(':')[1].split('(')[0].strip())

    return metrics

def create_barplot(sample_name, metrics, output_dir):
    """Create comparison barplot."""
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))

    # Left plot: Total counts
    ax1 = axes[0]
    categories = ['AMP (ALEDB)', 'HaplotypeCaller']
    values = [metrics['csv_total'], metrics['vcf_total']]
    colors = ['#E74C3C', '#3498DB']

    bars1 = ax1.bar(categories, values, color=colors, edgecolor='black', linewidth=1.5)
    ax1.set_ylabel('Number of Mutations', fontsize=12, fontweight='bold')
    ax1.set_title(f'{sample_name}\nTotal Mutations Detected', fontsize=14, fontweight='bold')
    ax1.set_ylim(0, max(values) * 1.15)

    for bar, val in zip(bars1, values):
        ax1.text(bar.get_x() + bar.get_width()/2, bar.get_height() + max(values)*0.02,
                 str(val), ha='center', va='bottom', fontsize=14, fontweight='bold')

    ax1.grid(axis='y', alpha=0.3)

    # Right plot: Concordance breakdown
    ax2 = axes[1]
    categories2 = ['Exact\nMatches', 'Fuzzy\nMatches\n(±50bp)', 'AMP\nOnly', 'VCF\nOnly']
    values2 = [metrics['exact'], metrics['fuzzy'], metrics['csv_only'], metrics['vcf_only']]
    colors2 = ['#2ECC71', '#F1C40F', '#E74C3C', '#3498DB']

    bars2 = ax2.bar(categories2, values2, color=colors2, edgecolor='black', linewidth=1.5)
    ax2.set_ylabel('Number of Mutations', fontsize=12, fontweight='bold')
    ax2.set_title(f'{sample_name}\nConcordance Breakdown', fontsize=14, fontweight='bold')
    ax2.set_ylim(0, max(values2) * 1.15)

    for bar, val in zip(bars2, values2):
        ax2.text(bar.get_x() + bar.get_width()/2, bar.get_height() + max(values2)*0.02,
                 str(val), ha='center', va='bottom', fontsize=12, fontweight='bold')

    ax2.grid(axis='y', alpha=0.3)

    # Add concordance rate annotation
    total_matches = metrics['exact'] + metrics['fuzzy']
    concordance = total_matches / metrics['csv_total'] * 100 if metrics['csv_total'] > 0 else 0
    ax2.text(0.98, 0.98, f'Concordance: {concordance:.1f}%\n({total_matches}/{metrics["csv_total"]} AMP mutations)',
             transform=ax2.transAxes, fontsize=11, verticalalignment='top', horizontalalignment='right',
             bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))

    plt.tight_layout()

    # Save
    output_dir.mkdir(parents=True, exist_ok=True)
    png_path = output_dir / f'{sample_name}_comparison_barplot.png'
    pdf_path = output_dir / f'{sample_name}_comparison_barplot.pdf'

    plt.savefig(png_path, dpi=150, bbox_inches='tight')
    plt.savefig(pdf_path, bbox_inches='tight')
    plt.close()

    print(f"Bar chart saved to:")
    print(f"  - {png_path}")
    print(f"  - {pdf_path}")

def main(sample_name):
    """Generate barplot for specified sample."""
    summary_file = Path(f'comparison/{sample_name}_comparison_summary.txt')
    output_dir = Path('comparison')

    if not summary_file.exists():
        print(f"Error: Summary file not found: {summary_file}")
        print("Run compare_sample.py first.")
        sys.exit(1)

    metrics = parse_summary(summary_file)
    create_barplot(sample_name, metrics, output_dir)

    # Also save summary
    summary_out = output_dir / f'{sample_name}_comparison_summary.txt'
    with open(summary_out, 'a') as f:
        f.write(f"\nBARPLOT GENERATED: {output_dir / f'{sample_name}_comparison_barplot.png'}\n")

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python plot_sample_comparison.py <sample_name>")
        print("Example: python plot_sample_comparison.py A1-F6-I2-R1")
        sys.exit(1)

    sample_name = sys.argv[1]
    main(sample_name)
