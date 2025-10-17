# QC Control Sample - ALEDB Validation Study

## Overview

This QC study validates the ALE_nextflow pipeline HaplotypeCaller joint calling output against known mutations from the ALE Database (ALEDB).

## Dataset Information

**ALEDB Experiment**: 2533 - Yeast Adipic Acid ALE
- **URL**: https://aledb.org/mutations/?ale_experiment_id=2533
- **Reference file**: `data/Mutations_Dev_Yeast_Adipic_Acid.csv`
- **Organism**: Yeast (Saccharomyces cerevisiae)
- **Experimental condition**: Adipic acid adaptation

## Pipeline Configuration

**Pipeline version**: ALE_nextflow v0.1.0-alpha (nf-core/sarek 3.5.1)

**Run script**: `../../bin/CENPK_run_sarek_351_all.sh`

**Variant calling**:
- Tool: GATK HaplotypeCaller
- Mode: Joint germline calling
- Filtering: Soft-filtered (GATK VariantFiltration fallback)

**Pipeline output location**: `../../output_all/`

**VCF files analyzed**:
- Joint VCF: `HaplotypeCaller_joint_calling_soft_filtered_snpEff.ann.vcf.gz`
- Individual split: `A0-F0-I1-R1.haplotypecaller.from_joint_calling_snpEff.ann.vcf.gz`

## Analysis Workflow

### 1. Data Preparation
- Downloaded reference mutations from ALEDB (experiment 2533)
- Copied relevant annotated VCF files from pipeline output
- Files stored in `data/` directory

### 2. Mutation Comparison
**Script**: `bin/clean_compare_with_dp.py`

Compares pipeline-detected variants against ALEDB reference mutations:
- Matches variants by genomic position and allele
- Extracts depth metrics (DP, AD, AF)
- Categorizes concordance/discordance

### 3. Analysis Scripts

**`parse_amp_csv.py`**
- Parses ALEDB mutation CSV format
- Extracts key mutation information
- Outputs: `output/A0-F0-I1-R1_AMP_mutations.tsv`

**`clean_compare_with_dp.py`**
- Main comparison script
- Compares VCF variants vs ALEDB mutations
- Outputs: `comparison/mutation_comparison_summary.txt`

**`plot_mutation_comparison.py`**
- Generates comparison barplots
- Shows concordant vs discordant mutations
- Outputs: `comparison/mutation_comparison_barplot.{png,pdf}`

**`plot_mutation_dp_dotplot.py`**
- Visualizes mutation depth distribution
- Shows coverage for detected variants
- Outputs: `comparison/mutation_dp_dotplot.{png,pdf}`

## Results

**Summary**: See `comparison/mutation_comparison_summary.txt`

**Key Findings**:
- Documented in comparison summary file
- Visualizations available in `comparison/` directory

## Reproducibility

To reproduce this QC analysis:

```bash
# 1. Run the pipeline (if not already done)
cd ~/Docs/ALE_nextflow
./bin/CENPK_run_sarek_351_all.sh

# 2. Copy VCF files to QC directory
cd quality_control/qc_control_sample/data
cp ../../../output_all/annotation/haplotypecaller/joint_variant_calling/HaplotypeCaller_joint_calling_soft_filtered_snpEff.ann.vcf.gz* .
cp ../../../output_all/annotation/haplotypecaller/individual_from_joint/A0-F0-I1-R1/A0-F0-I1-R1.haplotypecaller.from_joint_calling_snpEff.ann.vcf.gz* .

# 3. Run comparison analysis
cd ../bin
python clean_compare_with_dp.py

# 4. Generate visualizations
python plot_mutation_comparison.py
python plot_mutation_dp_dotplot.py
```

## Files in This Directory

```
qc_control_sample/
├── README.md                              # This file
├── data/
│   ├── README.md                          # Data sources
│   ├── Mutations_Dev_Yeast_Adipic_Acid.csv  # ALEDB reference
│   ├── HaplotypeCaller_joint_calling_soft_filtered_snpEff.ann.vcf.gz*
│   └── A0-F0-I1-R1.haplotypecaller.from_joint_calling_snpEff.ann.vcf.gz*
├── bin/
│   ├── parse_amp_csv.py                   # Parse ALEDB CSV
│   ├── clean_compare_with_dp.py           # Main comparison script
│   ├── plot_mutation_comparison.py        # Comparison barplots
│   └── plot_mutation_dp_dotplot.py        # Depth dotplots
├── comparison/
│   ├── mutation_comparison_summary.txt    # Summary results
│   ├── mutation_comparison_barplot.{png,pdf}
│   └── mutation_dp_dotplot.{png,pdf}
└── output/
    └── A0-F0-I1-R1_AMP_mutations.tsv     # Parsed ALEDB mutations
```

## Notes

- Large VCF files (*.vcf.gz) should not be committed to git
- Reference these files by their location in pipeline output
- Update this README when rerunning with new pipeline versions

---

**Date**: October 2025
**Pipeline Version**: v0.1.0-alpha
**Status**: ✅ Analysis Complete
