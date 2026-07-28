# Variant Analysis Dashboard System (archived — superseded design)

> **Status: superseded / archived (2026-07-27).** This is the original `bin/`-script "research
> dashboard" design from early development. **All five scripts it describes were removed during the
> v1.0.0 code cleanup**
> (`summarize_variants.py`, `organize_results.sh`, `quick_variant_check.sh`,
> `create_variant_dashboard.py`, `create_research_dashboard.py`), and the `VARIANT_DASHBOARD`
> Nextflow process was never built. Its purpose — cross-sample/multi-tool variant tables, cohort
> matrices, gene-centric and tool-comparison views — is now delivered by the **`MUTATION_REPORT`
> subworkflow + `GENERATE_INDEX`** (igv-reports HTML dashboard backed by `cn_cohort_matrix.csv` /
> `sv_cohort_matrix_*.csv` / `cn_segments_*.csv`). See `docs/igvreports/` and
> `subworkflows/local/mutation_report/`.
>
> Kept here for reference: the **design ideas** (impact prioritization, tool-comparison matrix,
> gene-level mutation burden, the literature alignment, and the Mutect2-integration notes) are still
> useful input if the mutation-report functionality is extended.

---

## Concept: Research-Grade VCF Organization

Following bioinformatics community best practices for multi-sample, multi-tool variant analysis, we've developed a dashboard system that converts complex VCF structures into analysis-ready formats.

### Problem Solved
- **Raw VCFs**: Hard to compare across samples/tools, require specialized knowledge
- **Standard approach**: Joint VCFs (good for population genetics, not ideal for research)
- **Our solution**: Curated dashboards with structured tables for biological interpretation

## Dashboard Scripts (removed in the v1.0.0 code cleanup — described for design reference)

### 1. `bin/summarize_variants.py` — Variant Overview Generator
**Purpose**: Quick variant counting across samples and tools
```python
count_variants_in_vcf()  # Uses bcftools for accurate counting
summarize_variants()     # Creates cross-sample comparison
generate_file_index()    # Maps important files for manual review
```
**Output**: `variant_summary.csv` (counts by sample/tool), `file_index.csv` (key files for review)

### 2. `bin/organize_results.sh` — Manual Review Organizer
Creates a `manual_review/` directory: `high_confidence_variants/` (filtered, annotated VCFs),
`copy_number_plots/` (CNV visualizations), `summary_reports/` (MultiQC, summaries), `README.md`.

### 3. `bin/quick_variant_check.sh` — Rapid Inspection Tool
`check_variants()` counts variants per VCF with bcftools; console report with impact summaries.

### 4. `bin/create_variant_dashboard.py` — Full Dashboard Generator
```python
extract_high_impact_variants()     # HIGH/MODERATE impact extraction
create_tool_comparison_matrix()    # Cross-tool validation
generate_summary_statistics()      # Research metrics
```
Output: `variant_dashboard/` with analysis tables. Designed for clinical-grade analysis.

### 5. `bin/create_research_dashboard.py` — main research tool
```python
extract_research_variants()     # All impact levels, research-friendly
create_tool_comparison_matrix() # Cross-tool validation matrix
create_gene_summary()           # Gene-level mutation burden
create_sample_summary()         # Sample-level statistics
```

**Key features**: multi-tool comparison (FreeBayes + Mutect2), impact prioritization
(HIGH > MODERATE > LOW > MODIFIER), gene-centric analysis, research filtering, CSV export.

**Output files**:
```
research_dashboard/
├── sample_summary.csv           # Cross-sample variant overview
├── tool_comparison_detailed.csv # Method validation matrix
├── genes_affected.csv           # Gene-level analysis
├── high_priority_variants.csv   # Manual review targets
├── complete_variant_catalog.csv # Full research dataset
└── RESEARCH_GUIDE.md            # Analysis workflow
```

**Proven results**: processed 2,968 variants from the full dataset — 465 high-priority (HIGH/MODERATE),
~490 variants/sample, 375-393 genes affected/sample, adaptation hotspots (e.g. YDR150W: 25 variants).

## Integration Strategy (proposed `VARIANT_DASHBOARD` process — never built)

```nextflow
process VARIANT_DASHBOARD {
    tag "$meta.id"
    label 'process_medium'
    input:
    tuple val(meta), path(vcfs)
    path(sample_sheet)
    output:
    tuple val(meta), path("research_dashboard/"), emit: dashboard
    tuple val(meta), path("*.csv"), emit: tables
    path "versions.yml", emit: versions
    script:
    """
    create_research_dashboard.py --vcf_dir . --sample_sheet ${sample_sheet} --output_dir research_dashboard/
    """
}
```

Integration points considered: after annotation (annotated VCFs as input), before reporting (alongside
MultiQC), output parallel to `annotation/`.

## Bioinformatics Community Alignment

**Best practices applied**: tool comparison (multi-caller consensus), impact prioritization, structured
CSV output, gene-centric view, reproducible methodology, scalable to new samples/tools.

**Literature alignment**: Tenaillon et al. (2012) *Science* (E. coli evolution); Lang et al. (2013)
*Nature Genetics* (yeast population analysis); Good et al. (2017) *Nature* (cross-tool validation).

## Known Issues & Solutions (design notes)

**Mutect2 missing from dashboard** — FreeBayes: 492 variants, Mutect2: 0 detected. Likely causes: format
differences (Mutect2 QUAL/FILTER structure), file paths (different annotation dir), filtering stringency.
Solution sketch: Mutect2-specific parsing (use TLOD not QUAL, handle annotation structure, tumor-normal
fields).

**Next development phase (as envisioned)**: fix Mutect2 integration; add CNV integration (Control-FREEC);
visualizations (Manhattan plots, heatmaps); direct R/Python export pipelines.
