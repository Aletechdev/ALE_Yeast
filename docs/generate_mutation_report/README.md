# Mutation Report Integration Plan

## Goal

Integrate the standalone IGV-based HTML report generation (`docs/igvreports/`) into the main Sarek pipeline, so running a pipeline script like `run_ottilie_pilot.sh` automatically produces a self-contained offline report bundle (`index.html` + per-sample reports).

---

## Current Architecture (Two Separate Runs)

```
run_ottilie_pilot.sh  →  main.nf (Sarek)  →  VCFs, CRAMs, MultiQC
                                                    ↓ (manual steps)
build_cn_matrix.py / sv_cohort_matrix.py  →  CN/SV CSVs
                                                    ↓ (manual copy)
generate_ottilie_reports.sh  →  generate_demo_reports.nf  →  index.html + samples/*.html
```

### Target Architecture (Single Run)

```
run_ottilie_pilot.sh  →  main.nf
                              │
                              ├── NFCORE_SAREK workflow
                              │     └── SAREK (alignment → variant calling → annotation → MultiQC)
                              │           ↓ emits: multiqc_report, versions
                              │
                              └── MUTATION_REPORT subworkflow  ← runs after SAREK completes
                                    ├── BUILD_CN_MATRIX
                                    ├── BUILD_SV_MATRIX
                                    ├── PREPARE_VCF
                                    ├── IGVREPORTS_COHORT
                                    ├── IGVREPORTS_SAMPLE
                                    ├── IGVREPORTS_SV_CNV
                                    └── GENERATE_INDEX
                                          ↓
                                    outdir/mutation_reports/
                                    ├── index.html
                                    ├── cohort_report.html
                                    ├── multiqc_report.html
                                    └── samples/*.html
```

**Integration point**: `main.nf` (top-level), inside the unnamed `workflow {}` block, after `NFCORE_SAREK()` and before `PIPELINE_COMPLETION()`. Gated behind `--generate_reports` flag.

**Why here and not inside Sarek?** The SAREK workflow only emits `multiqc_report` and `versions`. Adding new emit channels would require modifying the forked Sarek workflow internals. Instead, MUTATION_REPORT collects its inputs from the published `outdir/` paths (VCFs, CRAMs, MultiQC data), which are already written to disk by the time SAREK completes. This keeps the Sarek fork minimal and the report generation cleanly separated.

**Note**: `outdir/reports/` is already used by Sarek for per-tool QC outputs (bcftools, fastqc, mosdepth, samtools, snpeff, vcftools). The mutation report bundle goes to `outdir/mutation_reports/` to avoid collision.

---

## Report Output Structure

The final deliverable is a folder that can be opened offline in a browser:

```
outdir/mutation_reports/
├── index.html                         ← Dashboard hub (entry point)
├── cohort_report.html                 ← All variants, Tabulator.js, cross-linked to samples
├── multiqc_report.html                ← Copied/linked from MultiQC output
├── samples/
│   ├── {sample}_report.html           ← HaplotypeCaller per-sample + CRAM pileups
│   ├── {sample}_cnvkit_report.html    ← CNVKit SV/CN calls
│   └── {sample}_manta_report.html     ← Manta structural variants
└── data/                              ← Optional: CN/SV cohort CSVs for heatmaps
    ├── cn_chr_summary_sensitive.csv
    ├── cn_chr_summary_stringent.csv
    ├── cn_cohort_collapsed_sensitive.csv
    ├── cn_cohort_collapsed_stringent.csv
    ├── sv_cohort_matrix_union.csv
    └── sv_cohort_matrix_union_pass.csv
```

---

## Source Files Involved

### Report Generation (docs/igvreports/)
| File | Purpose | Status |
|------|---------|--------|
| `generate_demo_reports.nf` | Nextflow workflow with 6 processes | Working, needs channel-based refactor |
| `generate_demo_reports.sh` | CEN.PK launcher (6 I1 samples) | Hardcoded samples/paths |
| `generate_ottilie_reports.sh` | Ottilie launcher (4 samples) | Hardcoded samples/paths, manual steps |
| `generate_index.py` | Jinja2 dashboard renderer | Working, some hardcoded assumptions |
| `templates/index.html.j2` | Dashboard template (dark/light theme) | Production-ready |
| `custom_template.html` | Cohort report template (7:3 split) | Production-ready |
| `custom_template_sample.html` | Per-sample template (1:1 split) | Production-ready |
| `filter_config.yaml` | Tabulator filter definitions | Reference only (custom templates override) |
| `nextflow.config` | Docker executor, queueSize=3 | Needs merge into main config |

### CN/SV Matrix Generation
| File | Purpose | Status |
|------|---------|--------|
| `bin/build_cn_matrix.py` | Builds CN matrices from CNVKit .cns/.cnr | Working, needs Nextflow process wrapper |
| `04_validate/sv_cohort_matrix.py` | Builds SV cohort matrix from SURVIVOR merge | Working, needs extraction from validation |
| `04_validate/cn_cohort_matrix.py` | CN enrichment + collapsing | Working, needs extraction from validation |

### Prototype / Dead Code (in ottilie_4samples/)
| File | Status |
|------|--------|
| `ottilie_4samples/generate_prototype.py` | SUPERSEDED by `generate_index.py` — remove |
| `ottilie_4samples/mutation_overview.html` | Output of prototype — remove |
| `ottilie_4samples/data/*.csv` | Manual copy of `04_validate/pilot_results/` — eliminate with automation |

---

## Data Provenance: Where Each File Actually Comes From

This section traces exactly how the CN/SV CSV files needed by `generate_index.py` are produced, and why `ottilie_4samples/data/` contains stale, manually-assembled data.

### validate_all.py Execution Chain

`validate_all.py` calls 6 scripts in sequence. Critically, they write to **two different locations**:

```
validate_all.py --output-dir output_ottilie --results-dir pilot_results_v2
│
├─ 1. snv_indel_concordance.py  → pilot_results_v2/snv_indel_concordance.csv     (results_dir)
├─ 2. cnv_concordance.py        → pilot_results_v2/cnv_concordance.csv           (results_dir)
├─ 3. sv_characterization.py    → pilot_results_v2/sv_characterization.csv       (results_dir)
├─ 4. build_cn_matrix.py        → output_ottilie/cn_matrices/                    (output_dir!)
│     ├── cn_chr_summary_sensitive.csv      ← NOT in results_dir
│     ├── cn_chr_summary_stringent.csv      ← NOT in results_dir
│     ├── cn_segments_sensitive.csv
│     ├── cn_segments_stringent.csv
│     ├── cn_sensitive_vs_stringent.csv
│     └── cn_bins_continuous.csv
├─ 5. sv_cohort_matrix.py       → pilot_results_v2/sv_cohort_matrix.csv          (results_dir)
│     (needs output_ottilie/sv_merged/ from step 3's --save-vcfs)
│     (but sv_cohort_matrix_union*.csv require separate run with --filter flag?)
└─ 6. cn_cohort_matrix.py       → pilot_results_v2/cn_cohort_matrix.csv          (results_dir)
      (reads from output_ottilie/cn_matrices/ produced by step 4)
      (but cn_cohort_collapsed_*.csv require separate --collapse run?)
```

### What pilot_results_v2/ Contains (Current, May 28)

```
pilot_results_v2/
├── VALIDATION_REPORT.md
├── cn_cohort_matrix.csv           ← from cn_cohort_matrix.py (step 6)
├── cnv_concordance.csv            ← from cnv_concordance.py (step 2)
├── snv_indel_concordance.csv      ← from snv_indel_concordance.py (step 1)
├── sv_characterization.csv        ← from sv_characterization.py (step 3)
└── sv_cohort_matrix.csv           ← from sv_cohort_matrix.py (step 5)
```

### What pilot_results/ Contains (Original v1, May 26-27)

v1 has 12 extra files that were **manually gathered from multiple locations**:

```
Files in v1 but NOT in v2:
├── DATA_INDEX.md                      ← manually written
├── cn_chr_summary_sensitive.csv       ← copied from output_ottilie/cn_matrices/
├── cn_chr_summary_stringent.csv       ← copied from output_ottilie/cn_matrices/
├── cn_cohort_collapsed_sensitive.csv  ← from cn_cohort_matrix.py (separate run)
├── cn_cohort_collapsed_stringent.csv  ← from cn_cohort_matrix.py (separate run)
├── cn_cohort_matrix_collapsed.csv     ← from cn_cohort_matrix.py --collapse
├── sv_cohort_matrix_union.csv         ← from sv_cohort_matrix.py --filter union
├── sv_cohort_matrix_union_pass.csv    ← from sv_cohort_matrix.py --filter union_pass
├── sv_cohort_merged_union.vcf.gz      ← SURVIVOR merge output
├── sv_cohort_merged_union.vcf.gz.tbi
├── sv_cohort_merged_union_pass.vcf.gz
└── sv_cohort_merged_union_pass.vcf.gz.tbi
```

### What ottilie_4samples/data/ Contains (Manual Copy of v1)

The `data/` directory is a **snapshot of pilot_results/ (v1)** minus the `.md` and `.vcf.gz` files:
- Same 12 CSVs, identical file sizes
- **Stale**: based on v1 data (May 26-27), not the current v2 run (May 28)
- **Includes validation-specific files** (`snv_indel_concordance.csv`, `cnv_concordance.csv`) that `generate_index.py` doesn't even use

### The Problem

`generate_index.py` needs 6 specific CSVs:

| File | Source | In pilot_results_v2? | In output_ottilie/cn_matrices? |
|------|--------|---------------------|-------------------------------|
| `cn_chr_summary_sensitive.csv` | `build_cn_matrix.py` | NO | YES |
| `cn_chr_summary_stringent.csv` | `build_cn_matrix.py` | NO | YES |
| `cn_cohort_collapsed_sensitive.csv` | `cn_cohort_matrix.py` | NO | NO (separate run needed) |
| `cn_cohort_collapsed_stringent.csv` | `cn_cohort_matrix.py` | NO | NO (separate run needed) |
| `sv_cohort_matrix_union.csv` | `sv_cohort_matrix.py` | NO | NO (separate run needed) |
| `sv_cohort_matrix_union_pass.csv` | `sv_cohort_matrix.py` | NO | NO (separate run needed) |

None of these 6 files are produced in a single `validate_all.py` run to a location that `generate_index.py` can find. They must be:
1. Gathered from `output_ottilie/cn_matrices/` (CN chr summaries)
2. Generated by separate script runs with `--collapse` / `--filter` flags (collapsed + union variants)
3. Manually assembled into a `data/` directory
4. Passed to `generate_ottilie_reports.sh` via `--cnv_sv_data_dir`

### Resolution for Pipeline Integration

In the integrated pipeline, we need a single process that:
1. Runs `build_cn_matrix.py` → produces `cn_chr_summary_*.csv` (already works)
2. Runs `cn_cohort_matrix.py --collapse` → produces `cn_cohort_collapsed_*.csv`
3. Runs `sv_cohort_matrix.py --filter union --filter union_pass` → produces `sv_cohort_matrix_union*.csv`
4. Collects all 6 CSVs into a single directory
5. Passes that directory to `GENERATE_INDEX`

This eliminates all manual copy steps and ensures the report always uses current data.

---

## Identified Gaps

### Critical — Blocks Pipeline Integration

#### 1. Sample List Hardcoded
- **Current**: `--samples "CBR110-15-R3a,Carmaphycin-R9-2,..."` in shell scripts
- **Needed**: Auto-discover from pipeline channels (samplesheet or annotation outputs)
- **Files**: `generate_demo_reports.sh:13`, `generate_ottilie_reports.sh:14`

#### 2. VCF Paths Constructed from Strings
- **Current**: `"${annotation_dir}/${sample}.haplotypecaller.from_joint_calling/..."`
- **Needed**: Receive proper Nextflow channels from upstream annotation processes
- **Files**: `generate_demo_reports.nf:329-351`

#### 3. CN/SV Data Generated Outside Pipeline
- **Current**: Run `build_cn_matrix.py` manually → copy CSVs to `data/` folder
- **Chain**: `validate_all.py` → `build_cn_matrix.py` → `cn_cohort_matrix.py` → CSVs → manual copy → `generate_index.py`
- **Needed**: Nextflow processes for `BUILD_CN_MATRIX` and `BUILD_SV_MATRIX` that feed directly into `GENERATE_INDEX`
- **Note**: `build_cn_matrix.py` and `sv_cohort_matrix.py` are general-purpose (not benchmark-specific) and belong in the pipeline

#### 4. MultiQC Report Manually Copied
- **Current**: `cp output_ottilie/multiqc/multiqc_report.html ottilie_4samples/` (line 18 of shell script)
- **Needed**: Automate in report workflow — publish alongside `index.html`

### Medium — Causes Fragility

#### 5. Caller Suffix Parsing Hardcoded
- **Location**: `generate_index.py` lines 44-53
- **Issue**: `CALLER_SUFFIXES` list breaks if Sarek renames output files
- **Example**: `("haplotypecaller.from_joint_calling.hard_filtered", "HaplotypeCaller")`

#### 6. MultiQC Column Names Hardcoded
- **Location**: `generate_index.py` lines 222-225
- **Issue**: `gatk4_markduplicates_mark_duplicates-PERCENT_DUPLICATION` etc. break if MultiQC module names change

#### 7. Two-Stage Index Generation
- **Current**: Workflow generates `index.html`, then shell script regenerates it standalone (lines 42-50)
- **Reason**: Workaround to iterate on Jinja2 template without re-running expensive igvreports
- **Issue**: Unclear which output is canonical

#### 8. ALE Regex Fallback for Sample Discovery
- **Location**: `generate_index.py` line 214
- **Issue**: `^A\d+-F\d+-I\d+-R\d+$` only matches CEN.PK naming — Ottilie samples (`CBR110-15-R3a`, `NODRUG-GM2`) don't match
- **Impact**: Falls back to bcftools stats parsing (works, but fragile)

#### 9. Missing INFO Columns in Reports
- **Issue**: `FS`, `SOR`, `MQRankSum`, `ReadPosRankSum` not shown in igvreports
- **Impact**: Reviewers can't see WHY variants were soft-filtered (QD_filter, SOR_filter, etc.)
- **Fix**: Add to `--info-columns` in `IGVREPORTS_COHORT` and `IGVREPORTS_SAMPLE` processes

---

## Data Flow: What generate_index.py Expects

### Required: MultiQC TSVs (from Sarek MultiQC output)
```
multiqc_data/
├── multiqc_bcftools_stats.txt    → variant counts per sample/caller
├── multiqc_snpeff.txt            → HIGH/MODERATE/LOW impact counts
└── multiqc_general_stats.txt     → coverage, dup%, mapped%
```

### Optional: CN/SV CSVs (currently from validate_all.py, should be from pipeline)
```
data/
├── cn_chr_summary_sensitive.csv       ← from build_cn_matrix.py
├── cn_chr_summary_stringent.csv       ← from build_cn_matrix.py
├── cn_cohort_collapsed_sensitive.csv  ← from cn_cohort_matrix.py
├── cn_cohort_collapsed_stringent.csv  ← from cn_cohort_matrix.py
├── sv_cohort_matrix_union.csv         ← from sv_cohort_matrix.py
└── sv_cohort_matrix_union_pass.csv    ← from sv_cohort_matrix.py
```

When CN/SV data is absent, `generate_index.py` gracefully hides those sections — the dashboard still works with just MultiQC data.

### Validation-Specific CSVs (stay separate, NOT in pipeline)
```
snv_indel_concordance.csv    ← requires truth set (Ottilie Sup Data 4)
cnv_concordance.csv          ← requires truth set (Ottilie Sup Data 5)
sv_characterization.csv      ← general but tightly coupled to validation
```

---

## Integration Approach

### Phase 1: Clean Up

#### 1a. Remove dead code from `ottilie_4samples/`

| File | Action | Reason |
|------|--------|--------|
| `generate_prototype.py` | DELETE | Superseded by `generate_index.py` |
| `mutation_overview.html` | DELETE | Output of prototype, superseded by `index.html` |
| `data/*.csv` | DELETE folder | Stale manual copy of pilot_results v1; will be auto-generated in pipeline |
| `Screenshot *.png` | DELETE | Development screenshots, not needed in repo |
| `prepare/` | DELETE folder | Intermediate files from PREPARE_VCF process, regenerated each run |
| `pipeline_info/` | DELETE folder | Nextflow execution traces, not needed in repo |

Keep:
| File | Reason |
|------|--------|
| `index.html` | Reference output / demo |
| `cohort_report.html` | Reference output / demo |
| `multiqc_report.html` | Reference output / demo |
| `samples/*.html` | Reference output / demo |

**Decision needed**: Should `ottilie_4samples/` be kept as a demo/reference, or should all generated outputs be excluded from the repo (since they're large HTML files, 1-23 MB each)?

#### 1b. Move general-purpose scripts to `bin/`

| Script | Current Location | Action |
|--------|------------------|--------|
| `build_cn_matrix.py` | `bin/` | Already there — no move needed |
| `sv_cohort_matrix.py` | `04_validate/` | MOVE to `bin/` — general-purpose, not validation-specific |
| `cn_cohort_matrix.py` | `04_validate/` | MOVE to `bin/` — general-purpose, not validation-specific |

Both `sv_cohort_matrix.py` and `cn_cohort_matrix.py` produce cohort-level matrices that the report dashboard needs regardless of whether validation is being run. They should live in `bin/` alongside `build_cn_matrix.py`.

#### 1c. Clean up launcher scripts

| Script | Action | Reason |
|--------|--------|--------|
| `generate_demo_reports.sh` | KEEP (for now) | CEN.PK reference; will be replaced by pipeline integration |
| `generate_ottilie_reports.sh` | KEEP (for now) | Ottilie reference; documents the manual steps to eliminate |

#### 1d. Document template files

Add a brief header comment to each template explaining its role:
- `custom_template.html` — Cohort report (7:3 table/IGV split, cross-links to samples)
- `custom_template_sample.html` — Per-sample report (1:1 split, CRAM pileups + GFF3)
- `templates/index.html.j2` — Dashboard hub (Jinja2, dark/light theme, CN/SV heatmaps)

### Phase 2: Create Subworkflow
- Convert `generate_demo_reports.nf` processes into `subworkflows/local/mutation_report/main.nf`
- Add `BUILD_CN_MATRIX` and `BUILD_SV_MATRIX` processes
- Wire inputs from pipeline channels (not constructed paths)
- Gate behind `--generate_reports` flag

### Phase 3: Integrate into main.nf

**Location**: Top-level `main.nf` (`/home/azureuser/Docs/ALE_nextflow/main.nf`), inside the unnamed `workflow {}` block.

**Integration sketch** (after `NFCORE_SAREK`, before `PIPELINE_COMPLETION`):
```groovy
// main.nf — unnamed workflow {} block

NFCORE_SAREK(PIPELINE_INITIALISATION.out.samplesheet)

// MUTATION_REPORT: generate IGV-based HTML report bundle
if (params.generate_reports) {
    MUTATION_REPORT(
        params.outdir,           // base output dir (published VCFs, CRAMs, MultiQC already here)
        params.input,            // samplesheet CSV → auto-discover sample list
        fasta,                   // reference FASTA
        fasta_fai,               // reference index
        // GFF3 from SnpEff cache or params
    )
}

PIPELINE_COMPLETION(...)
```

**Key design decisions:**
- Inputs collected from `params.outdir` paths (already published by Sarek), not from internal Sarek channels
- Sample list auto-discovered from `params.input` samplesheet (eliminates hardcoded `--samples`)
- Gated behind `--generate_reports` flag (opt-in, no impact on existing runs)
- Publish report bundle to `outdir/mutation_reports/` (note: `outdir/reports/` is already used by Sarek for per-tool QC outputs like bcftools, fastqc, mosdepth, etc.)
- SAREK workflow stays unmodified — no new emit channels needed

### Phase 4: Test and Document
- Test with Ottilie pilot (4 samples) and CEN.PK (17 samples)
- Add `--generate_reports` to example run scripts
- Document report features and customization options

---

## Pipeline Inputs Already Available

All inputs needed by the report workflow are already produced by Sarek:

| Input | Sarek Output Channel/Path |
|-------|--------------------------|
| Joint annotated VCF | `annotation/haplotypecaller/joint_variant_calling/` |
| Per-sample annotated VCFs | `annotation/haplotypecaller/{sample}/` (from SPLIT_JOINT_VCF) |
| CNVKit annotated VCFs | `annotation/cnvkit/{sample}/` |
| Manta annotated VCFs | `annotation/manta/{sample}/` |
| CRAMs | `preprocessing/markduplicates/{sample}/` |
| CNVKit .cns/.cnr files | `variant_calling/cnvkit/{sample}/` |
| SV VCFs (Manta/TIDDIT) | `variant_calling/manta/{sample}/`, `variant_calling/tiddit/{sample}/` |
| MultiQC data | `multiqc/multiqc_data/` |
| Reference FASTA + FAI | Pipeline params |
| GFF3 gene annotation | From SnpEff cache or params |

---

## Related Documentation
- [igvreports/README.md](../igvreports/README.md) — Current report system docs
- [igvreports/REPORTING_PLAN.md](../igvreports/REPORTING_PLAN.md) — Phase-based roadmap
- [igvreports/check_mutations.md](../igvreports/check_mutations.md) — Detailed architecture and three-tier strategy
- [CLAUDE.md](../../CLAUDE.md) — Pipeline overview and variant calling strategy
