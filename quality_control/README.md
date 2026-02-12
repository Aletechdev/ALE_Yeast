# Quality Control and Validation

This directory contains QC analyses and validation studies for the ALE_nextflow pipeline.

## Purpose

Quality control analyses here are **separate from standard pipeline outputs** and are used to:
- Validate variant calling accuracy against known mutations
- Compare pipeline versions or parameter changes
- Benchmark against external datasets (e.g., ALEDB)
- Document quality metrics and concordance

## Directory Structure

```
quality_control/
├── README.md              # This file
├── qc_control_sample/     # v1: Validation against ALEDB (Oct 2025, output_all)
│   ├── data/              # Reference data and pipeline outputs for comparison
│   ├── bin/               # QC analysis scripts
│   ├── comparison/        # Comparison results and plots
│   └── output/            # Processed QC results
└── qc_control_sample_v2/  # v2: Validation with all-normal config (Feb 2026, output_all_normal)
    ├── data/              # Reference data and pipeline outputs for comparison
    ├── bin/               # QC analysis scripts
    ├── comparison/        # Comparison results and plots
    └── output/            # Processed QC results
```

## Current QC Studies

### qc_control_sample - ALEDB Validation Study

**Purpose**: Validate HaplotypeCaller joint calling output against known mutations from ALE Database

**Dataset**:
- ALEDB Experiment ID: 2533
- URL: https://aledb.org/mutations/?ale_experiment_id=2533
- Reference: `Mutations_Dev_Yeast_Adipic_Acid.csv`

**Pipeline Configuration**:
- Run script: `bin/CENPK_run_sarek_351_all.sh`
- Pipeline output: `output_all/`
- Variant caller: HaplotypeCaller (joint germline calling)

**Analysis Components**:
1. **Data preparation**: Copy relevant VCFs from pipeline output
2. **Mutation comparison**: Compare detected variants vs ALEDB reference
3. **Depth analysis**: Validate variant depth coverage
4. **Visualization**: Generate comparison plots

**Scripts**:
- `parse_amp_csv.py` - Parse ALEDB mutation CSV format
- `clean_compare_with_dp.py` - Compare variants with depth metrics
- `plot_mutation_comparison.py` - Generate comparison barplots
- `plot_mutation_dp_dotplot.py` - Visualize mutation depth distribution

**Results**: See `comparison/mutation_comparison_summary.txt`

**Status**: ✅ Completed - Results documented

### qc_control_sample_v2 - ALEDB Validation (All-Normal Configuration)

**Purpose**: Validate HaplotypeCaller output with all samples treated as normal (status=0)

**Dataset**: Same as v1 (ALEDB Experiment 2533)

**Pipeline Configuration**:
- Run script: `bin/CENPK_run_sarek_351_all_normal.sh`
- Pipeline output: `output_all_normal/`
- Key change: All samples status=0 for joint germline calling

**Results Summary**:
| Metric | v1 (output_all) | v2 (output_all_normal) |
|--------|-----------------|------------------------|
| VCF mutations | 108 | 106 |
| Total matches | 47 (90.4%) | 47 (90.4%) |
| VCF-only | 61 | 59 |

**Key Finding**: Results highly consistent - all-normal config maintains 90.4% concordance

**Status**: ✅ Completed - February 2026

---

## Adding New QC Analyses

When testing new datasets or validating pipeline changes:

1. **Create subdirectory** with descriptive name:
   ```bash
   mkdir quality_control/my_qc_analysis
   ```

2. **Add README.md** documenting:
   - Purpose of the QC study
   - Dataset information (with URLs if public)
   - Pipeline configuration used
   - Analysis methodology
   - Key findings

3. **Organize files**:
   ```
   my_qc_analysis/
   ├── README.md          # QC documentation
   ├── data/              # Reference data (link to large files)
   ├── bin/               # Analysis scripts
   ├── comparison/        # Results
   └── output/            # Processed outputs
   ```

4. **Version control**:
   - Commit: Scripts, READMEs, summary results, plots
   - Ignore: Large VCF/BAM files (reference via URLs)
   - Document: File locations in README

## Guidelines

### What to Commit
- ✅ Analysis scripts (Python, R, shell)
- ✅ README documentation
- ✅ Summary text files
- ✅ Plots and visualizations (PNG/PDF)
- ✅ Small reference files (<1MB)

### What to Ignore
- ❌ Large VCF files (>10MB) - reference by path or URL
- ❌ BAM/CRAM files - reference pipeline output location
- ❌ Intermediate processing files
- ❌ Pipeline work directories

### Documentation Best Practices
- Link to external datasets (ALEDB, SRA, etc.)
- Document pipeline version and parameters
- Include sample commands for reproducibility
- Summarize key findings in README
- Note any discrepancies or issues found

---

**Last Updated**: February 2026 (v0.1.0-alpha)
