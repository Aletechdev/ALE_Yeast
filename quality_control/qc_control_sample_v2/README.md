# QC Control Sample v2 - ALEDB Validation Study

## Overview

This QC study validates the ALE_nextflow pipeline HaplotypeCaller joint calling output against known mutations from the ALE Database (ALEDB). This is version 2, comparing output from **output_all_normal** (Feb 2026 pipeline run with all samples treated as normal status).

## Changes from v1

- **Pipeline run**: `output_all_normal` (all samples status=0) vs `output_all` (mixed status)
- **Date**: February 2026 vs October 2025
- **Configuration**: Joint germline calling with all samples as normal

## Dataset Information

**ALEDB Experiment**: 2533 - Yeast Adipic Acid ALE
- **URL**: https://aledb.org/mutations/?ale_experiment_id=2533
- **Organism**: Yeast (Saccharomyces cerevisiae)
- **Experimental condition**: Adipic acid adaptation

## Input Data Sources

- **AMP mutations CSV** (`data/Mutations_Dev_Yeast_Adipic_Acid.csv`): Exported from https://aledb.org/mutations/?ale_experiment_id=2533#. This is the input for `bin/parse_amp_csv.py`, which generates per-sample TSV files in `output/`.
- **Breseq annotated GD** (`data/A1-F6-I2-R1_annotated.gd`): Downloaded from Azure blob `aledata/Dev_YEAST_Adipic_acid_control_run5/Dev_YEAST_Dicar_Acid/Adipic_Acid/breseq/1-6-2-1/output/` as `annotated.gd`, renamed to `A1-F6-I2-R1_annotated.gd`.
- **Breseq raw output GD** (`data/A1-F6-I2-R1-bareseq-output.gd`): Downloaded from the same Azure blob path as `output.gd`, renamed to `A1-F6-I2-R1-bareseq-output.gd`.

## Pipeline Configuration

**Pipeline version**: ALE_nextflow v0.1.0-alpha (nf-core/sarek 3.5.1)

**Run script**: `../../bin/CENPK_run_sarek_351_all_normal.sh`

**Key change**: All samples treated as normal (status=0) for joint germline calling

**Pipeline output location**: `../../output_all_normal/`

**VCF files analyzed**:
- Joint VCF: `HaplotypeCaller_joint_calling_soft_filtered_snpEff.ann.vcf.gz`
- Individual split: `A0-F0-I1-R1.haplotypecaller.from_joint_calling_snpEff.ann.vcf.gz`

## Results Comparison: v1 vs v2

| Metric | v1 (output_all) | v2 (output_all_normal) |
|--------|-----------------|------------------------|
| VCF mutations | 108 | 106 |
| AMP reference | 52 | 52 |
| Exact matches | 6 (11.5%) | 6 (11.5%) |
| Fuzzy matches (50bp) | 41 (78.8%) | 41 (78.8%) |
| **Total matches** | **47 (90.4%)** | **47 (90.4%)** |
| CSV-only | 5 (9.6%) | 5 (9.6%) |
| VCF-only | 61 (56.5%) | 59 (55.7%) |
| Mean DP (VCF-only) | 7.3 | 7.2 |

**Key Finding**: Results are highly consistent between runs. The all-normal configuration produces nearly identical variant detection with 90.4% concordance.

## Summary Results

See `comparison/mutation_comparison_summary.txt` for detailed output.

**Highlights**:
- 90.4% of AMP-detected mutations found in HaplotypeCaller output
- 6 exact position matches, 41 fuzzy matches within 50bp
- 5 mutations detected by AMP but not by HaplotypeCaller
- 59 additional variants detected by HaplotypeCaller (mean DP 7.2)
- VCF-only variants have lower depth, suggesting they may be lower-confidence calls

## Files in This Directory

```
qc_control_sample_v2/
├── README.md                              # This file
├── data/
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
    ├── A0-F0-I1-R1_AMP_mutations.tsv     # Parsed ALEDB mutations
    └── AMP_mutation_summary.tsv          # All sample summary
```

## Reproducibility

To reproduce this QC analysis:

```bash
# 1. Ensure pipeline has been run
cd ~/Docs/ALE_nextflow
./bin/CENPK_run_sarek_351_all_normal.sh

# 2. Copy VCF files to QC directory
cd quality_control/qc_control_sample_v2/data
cp ../../../output_all_normal/annotation/haplotypecaller/joint_variant_calling/HaplotypeCaller_joint_calling_soft_filtered_snpEff.ann.vcf.gz* .
cp ../../../output_all_normal/annotation/haplotypecaller/A0-F0-I1-R1/A0-F0-I1-R1.haplotypecaller.from_joint_calling_snpEff.ann.vcf.gz* .

# 3. Parse AMP reference CSV
cd ..
source ~/miniforge3/etc/profile.d/conda.sh
conda activate nf-env
python bin/parse_amp_csv.py data/Mutations_Dev_Yeast_Adipic_Acid.csv output/

# 4. Run comparison analysis
python bin/clean_compare_with_dp.py | tee comparison/mutation_comparison_summary.txt

# 5. Generate visualizations (vcf-analysis env for plotting, nf-env for bcftools)
conda activate vcf-analysis
python bin/plot_mutation_comparison.py
conda activate nf-env
python bin/plot_mutation_dp_dotplot.py
```

## Notes

- Large VCF files (*.vcf.gz) should not be committed to git
- Reference these files by their location in pipeline output
- This v2 analysis confirms that all-normal status configuration maintains variant detection accuracy

---

**Date**: February 2026
**Pipeline Version**: v0.1.0-alpha
**Pipeline Output**: output_all_normal
**Status**: Analysis Complete
