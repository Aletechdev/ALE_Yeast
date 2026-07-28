# NF_ALE Project Notes

> **Maintenance convention.** This file holds operational summaries + pointers into `docs/`; the
> linked doc is the source of detail. When you change pipeline behavior, update **both** the summary
> here and the linked doc so they stay in sync. Keep inline notes to *stable* facts (tool tiers,
> thresholds, paths); push volatile detail to `docs/`. Pointers must resolve even if the target doc
> isn't yet complete.

## Table of Contents
1. [Pipeline Identity & Naming](#pipeline-identity--naming)
2. [Environment Setup](#environment-setup)
3. [Input Configuration](#input-configuration)
4. [Variant Calling Strategy](#variant-calling-strategy)
5. [Implementation Details](#implementation-details)
6. [Tool-Specific Notes](#tool-specific-notes)
7. [Variant Analysis Dashboard System](#variant-analysis-dashboard-system)
8. [Pipeline Merger Decision - Reminder](#pipeline-merger-decision---reminder)

---

## Pipeline Identity & Naming

Three names refer to the same thing — kept distinct on purpose:

| What | Value | Notes |
|------|-------|-------|
| **Brand** (this version) | **yAMP** — *yeast Automated Mutation Pipeline* | Product name; future majors → AMPv3, … Lives in `manifest.description`. |
| **`manifest.name`** | **`Aletechdev/AMP`** | Stable `org/repo`-form pipeline identity (drives the console banner, MultiQC header, versions `id:`, Seqera launch title). `org/repo` form keeps `nextflow run <name>` viable if ever open-sourced. |
| **GitHub repo (handle/URL)** | **`Aletechdev/ALE_Yeast`** → https://github.com/Aletechdev/ALE_Yeast | The real repo; `worktree-seqera-cloud` lives here. Also `manifest.homePage`. |

**`manifest.name` (`Aletechdev/AMP`) intentionally ≠ the repo handle (`Aletechdev/ALE_Yeast`)** — the
brand stays clean while the repo keeps its existing name. Both may be reconciled/renamed later. The
`description` (brand) evolves per version; `manifest.name` (identity) stays stable so it isn't churned.

> **Status:** ✅ applied 2026-07-27 (WP4 Step 2e). `manifest.name`, `version = '1.0.0'`, `description`,
> `homePage`, and `doi = ''` set in `nextflow.config`; ottilie e2e re-snapshotted — the only output delta
> was the `versions.yml` Workflow line (`nf-core/sarek: v3.5.1` → `Aletechdev/AMP: v1.0.0`).

---

## Environment Setup

### Azure Linux VM (Production)
- **Profile**: `AzureD4as,docker`
- **VM Size**: D4as
- **Conda Environment**: `conda activate /home/azureuser/miniforge3/envs/nf-env`
- **Recommended**: Use original configuration for production deployment

### ~~Apple Silicon (Deprecated)~~
- **Status**: Not maintained
- **Profile**: `arm,docker`
- **Issues**: Tools stalled (multiQC, Mutect2), filesystem optimization problems

---

## Input Configuration

### Key Files and Locations

- **Test Data**: https://aledata.blob.core.windows.net/aledata/Yeast/dicarboxylic_acids_all_clones/REDACTED-CUSTOMER-ID/ANP_Dev_2025Q3/data/
- **Main Execution Script**: `bin/CENPK_run_sarek_351.sh`
- **Pipeline Config**: `conf/azured4as.config` (the `azureD4as` local-VM resources profile; use `-profile azureD4as`, no `-c` needed). See `docs/dev-practices/compute_resources.md`
- **Cache Generation**: `bin/prepare_input/process_GeneBank/generate_cache/gen_cache.sh`
- **Forked nf-core**: `nf-core-sarek_3.5.1` (use version 3.5.1 docs)

### Sample Table Format

Adapted from nf-sarek (originally for human cancer research):
- **experiment**: Experiment ID (maps to "patient" in Sarek)
- **status**: 0 = ancestral strain (normal), 1 = evolved strain (tumor), update: treat all samples as normal, to run haplotypecaller `--joint_germline`
- **ploidy**: Custom column for ploidy support
- **Requirement**: Each experiment **must have one normal sample** (status: 0)

**Example:**
```csv
experiment,sample,status,clonal_or_population,ploidy,lane,fastq_1,fastq_2
ALE_Exp1,A4-F5-I1-R1,0,clonal,2,L001,SubSampleA4-5_S11_L001_R1_001.fastq.gz,SubSampleA4-5_S11_L001_R2_001.fastq.gz
ALE_Exp1,A4-F5-I1-R1,0,clonal,2,L003,SubSampleA4-5_S11_L003_R1_001.fastq.gz,SubSampleA4-5_S11_L003_R2_001.fastq.gz
ALE_Exp1,A0-F0-I1-R1,0,clonal,2,L001,SubSampleCENPK113-7D-N_S53_L001_R1_001.fastq.gz,SubSampleCENPK113-7D-N_S53_L001_R2_001.fastq.gz
ALE_Exp1,A0-F0-I1-R1,0,clonal,2,L002,SubSampleCENPK113-7D-N_S53_L002_R1_001.fastq.gz,SubSampleCENPK113-7D-N_S53_L002_R2_001.fastq.gz
```

**⚠️ TODOs:**
- Support tumor-only mode via `BAM_VARIANT_CALLING_TUMOR_ONLY_ALL` channel
- Auto-fill sex chromosome column (XX) for CNV tools

---

## Variant Calling Strategy

### Production Tools (Deliverable 1)

**Variant Callers:**
- **FreeBayes**: Germline mode only (somatic disabled due to excessive noise)
- **GATK Mutect2**: Somatic mode with custom AF-based filtering
- **GATK HaplotypeCaller**: Joint and individual germline calling

**Annotation:**
- **SnpEff**: Custom cache generated via `bin/prepare_input/process_GeneBank/generate_cache/gen_cache.sh`

**Ploidy Support:**
- Passed to: HaplotypeCaller (`--sample-ploidy`), `controlfreec`, `FreeBayes`, `Tiddit`
- **Note**: `bcftools mpileup` still uses ploidy=1 in `conf/modules/ngscheckmate.config`
- **CNVKit**: does **not** take `--ploidy` (reverted May 2026 → defaults to 2; CN scale is always `cn=2` baseline regardless). Use `fold_change`/log2 for true signal — see the [CNVKit section](#cnvkit-tier-1-cnv-deliverable) and [`docs/variant-calling/cnvkit/cnvkit_ploidy_behavior.md`](docs/variant-calling/cnvkit/cnvkit_ploidy_behavior.md).

---

## Implementation Details

### Tier-2 somatic AF filters (Mutect2 / FreeBayes)

**Tier-2 (functional, not release-validated for ALE).** Mutect2 and FreeBayes are somatic
callers — too sensitive/noisy for ALE (FreeBayes somatic mode alone gave 248,248 variants vs
10,965 germline). Custom AF-based filters (Normal AF < 0.10, Tumor AF > 0.05, diff > 0.05,
depth tumor ≥ 10 / normal ≥ 8), multi-allelic `bcftools norm -m-` splitting, strand-bias
filtering, FreeBayes-somatic disabled, and the FilterMutectCalls channel-join fix all live in
[`docs/variant-calling/tier2_af_filters.md`](docs/variant-calling/tier2_af_filters.md).
**HaplotypeCaller is the Tier-1 SNV/INDEL deliverable.**

### Bug Fixes

#### ✅ YAML Processing Error (Custom VCF Filters)

Groovy method-resolution ambiguity in `processVersionsFromYAML()`
(`nf-core-sarek_3.5.1/3_5_1/subworkflows/nf-core/utils_nfcore_pipeline/main.nf`) fixed via
explicit `java.io.FileInputStream(path.toFile())` + null/empty validation, so
`VCF_FILTER_FREEBAYES` / `VCF_FILTER_MUTECT2` work correctly.

---

## Tool-Specific Notes

### GATK Tools

#### ⚠️ BaseRecalibrator Disabled

**Reason**: Custom reference genome lacks curated --known-sites variant VCFs (required input)

**Status**: Retained in codebase for reference, not used in current analyses

**Future**: May enable if high-confidence variant set generated (e.g., bootstrapped calls)

**Reference**: https://janis.readthedocs.io/en/latest/tools/bioinformatics/gatk4/gatk4baserecalibrator.html

#### ⚠️ Mutect2 Missing Resources (Custom Genome)

**Warning**: Mutect2 running without `--germline-resource` and `--panel-of-normals`

**1. --germline-resource**
- **Purpose**: Filter common population variants (SNPs)
- **For yeast ALE**: All mutations are of interest (no population database like gnomAD)
- **Decision**: **Omit entirely** (also omits `--af-of-alleles-not-in-resource`)

**2. --panel-of-normals (PoN)**
- **Purpose**: Identify systematic sequencing/prep artifacts
- **For yeast ALE**: Could be useful with multiple ancestral strain replicates
- **Decision**: **Omit** (effort not justified for current experiments)

**References**:
- https://gatk.broadinstitute.org/hc/en-us/articles/5358911630107-Mutect2
- https://gatk.broadinstitute.org/hc/en-us/articles/5358921041947-CreateSomaticPanelOfNormals-BETA-


### CNVKit (Tier-1 CNV deliverable)

CNVKit is the **Tier-1 CNV deliverable**. No explicit `--ploidy` is passed (that was reverted
May 2026 — CNVKit defaults to 2); CN matrices use `fold_change = 2^log2` (ploidy-agnostic depth
ratio). **Caveat**: CNVKit's integer `cn` always uses `cn=2` as baseline regardless of ploidy,
so use `fold_change`/`log2` for the true signal. Details:
[`docs/variant-calling/cnvkit/`](docs/variant-calling/cnvkit/).

### VCFtools Compatibility

#### ⚠️ Conditional Skipping

VCFtools **conditionally skipped** due to compatibility issues:

**1. Ploidy > 2**
- Error: "Polyploidy found, and not supported by vcftools"
- Works: ploidy 1-2, Fails: ploidy ≥ 3

**2. Mutect2 Phased Genotypes**
- Issue: Mutect2 outputs phased (0|0, 0|1) instead of unphased (0/0, 0/1)
- Impact: VCFtools expects standard format

**3. Joint Calling Segmentation Fault**
- Issue: VCFtools 0.1.16 crashes on joint_variant_calling.vcf.gz (exit 139)
- Root cause: Memory corruption with GATK joint calling format

**Configuration** (`conf/modules/modules.config`):
```yaml
ext.when = { !(params.skip_tools.contains('vcftools')) &&
             (meta.ploidy == null || meta.ploidy <= 2) &&
             (meta.variantcaller != 'mutect2') &&
             !(meta.id ==~ /.*joint_variant_calling.*/) }
```

**VCFtools runs for**:
- ✅ FreeBayes individual (ploidy ≤ 2)
- ✅ HaplotypeCaller individual
- ❌ Mutect2 (all)
- ❌ Joint variant calling
- ❌ Ploidy > 2

### Control-FREEC (Tier-2 CNV)

**Tier-2 (functional, not release-validated for ALE).** Not the Tier-1 CNV deliverable because:
no SNP database → no BAF (copy number from read depth only); no standard VCF output → no SnpEff
annotation; `ASSESS_SIGNIFICANCE` fails for haploid (ploidy=1) samples (empty `*.gz_CNVs` → R
script error, auto-skipped via `conf/modules/controlfreec.config`); and it crashes on some
samples with `std::length_error`. **CNVKit is the Tier-1 CNV deliverable instead.** Single-sample
germline mode (April 2026) is implemented — see
[`docs/variant-calling/controlfreec/controlfreec_germline_changes.md`](docs/variant-calling/controlfreec/controlfreec_germline_changes.md).

### Soft-filter fallback for joint germline calling

VQSR is unavailable for the custom yeast genome (no known-sites resources). As a fallback, GATK
`VARIANTFILTRATION_FALLBACK` **soft-filters** the joint VCF — it populates the FILTER column
(`PASS` or named tags like `QD_filter`) but **does not remove variants**. Output:
`HaplotypeCaller_joint_calling_soft_filtered.vcf.gz`. Extract PASS-only downstream with
`bcftools view -f PASS`. Details, filter thresholds, and trigger conditions:
[`docs/variant-calling/haplotypecaller/SOFT_FILTER_HAPLOTYPECALLER_JOINT.md`](docs/variant-calling/haplotypecaller/SOFT_FILTER_HAPLOTYPECALLER_JOINT.md).

---

### Split joint VCF into individual sample VCFs

The `SPLIT_JOINT_VCF` subworkflow extracts per-sample VCFs from the HaplotypeCaller joint
calling output using channel-based metadata propagation (no string parsing). Enable with
`--joint_germline --split_haplotypecaller_joint_vcf`. Output:
`variant_calling/haplotypecaller/individual_from_joint/<sample>/<sample>.haplotypecaller.from_joint_calling.vcf.gz`
(+ `.tbi`). Full architecture, channel flow, and manual bcftools recipe:
[`docs/variant-calling/haplotypecaller/SPLIT_JOINT_VCF_PIPELINE.md`](docs/variant-calling/haplotypecaller/SPLIT_JOINT_VCF_PIPELINE.md).

---

## Variant Analysis Dashboard System

**Superseded.** The original `bin/` dashboard scripts (`create_research_dashboard.py`,
`summarize_variants.py`, `organize_results.sh`, `quick_variant_check.sh`, `create_variant_dashboard.py`)
were removed in WP2. Their role — cross-sample / multi-tool variant tables, cohort matrices, and gene /
tool-comparison views — is now delivered by the **`MUTATION_REPORT` subworkflow + `GENERATE_INDEX`**
(igv-reports HTML dashboard backed by `cn_cohort_matrix.csv` / `sv_cohort_matrix_*.csv` /
`cn_segments_*.csv`). See [`docs/igvreports/`](docs/igvreports/) and
[`subworkflows/local/mutation_report/`](subworkflows/local/mutation_report/main.nf). The original design
writeup (kept for future mutation-report work) is archived at
[`docs/archive/variant_dashboard_system.md`](docs/archive/variant_dashboard_system.md).

## Pipeline Merger Decision - Reminder
### Two Pipeline Architectures
#### AMP v1 (Legacy ALE Pipeline)

Input: Individual CSV files per sample
Annotation: GenBank (.gb) files
Tools: breseq + GATK + CNVnator
Target: Bacterial ALE experiments (haploid)
Deployment: Azure Batch → migrating to Nextflow

#### Customer Sarek Pipeline

Input: Population CSV table
Annotation: SnpEff cache + FASTQ
Tools: Standard Sarek workflow (GATK-based)
Target: Eukaryotic ALE experiments
Deployment: Nextflow
Decision Required

#### ⚠️ INVESTIGATE BEFORE PROCEEDING:

Merger Feasibility: Can GenBank and SnpEff annotation systems coexist?
Tool Integration: How to incorporate breseq into Sarek architecture?
Input Standardization: Worth converging to population CSV format?
Maintenance Trade-offs: One complex pipeline vs two focused pipelines?