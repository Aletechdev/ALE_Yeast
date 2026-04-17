# Modifications to nf-core-sarek 3.5.1

This document describes all modifications made to nf-core-sarek 3.5.1 compared to the original version. GATK HaplotypeCaller is the main variant calling tool with `--joint_germline --split_haplotypecaller_joint_vcf --hard_filter_haplotypecaller_joint`

## Summary of Changes

1. **Per-sample ploidy support** - Read ploidy from input CSV
2. **Experiment ID support** - Alternative to patient ID
3. **Clonal/Population mode** - Sample type classification
4. **VCF filtering subworkflows** - Custom filtering for FreeBayes, Mutect2, HaplotypeCaller
5. **Joint calling improvements** - Split joint VCF into individual samples
6. **Additional bcftools modules** - filter, query, view modules added

## ⚠️ Known Divergence from Upstream: `custom_config_base` (nextflow.config line 140)

**Status**: Workaround in place, ideal fix pending

**Issue**: Pipeline was originally obtained via `nf-core download`, which patched `nextflow.config` to use a local path:
```groovy
// Current (nf-core download artifact) — line 140:
custom_config_base = "${projectDir}/../configs/"

// Upstream 3.8.1 (correct) — uses remote URL:
custom_config_base = "https://raw.githubusercontent.com/nf-core/configs/${params.custom_config_version}"
```

The `includeConfig` logic at lines 321-324 is also weaker than 3.8.1 — it doesn't distinguish between local and remote paths when `NXF_OFFLINE` is set.

**Impact**: Fails on any deployment where `configs/` is not present alongside the pipeline (Seqera Cloud, fresh git clone).

**Current workaround**: `params.custom_config_base = null` in `conf/seqera_azure.config` + `NXF_OFFLINE=true` in `bin/test_nf.sh`.

**Ideal fix**: Apply the two-line change from 3.8.1 to `nextflow.config` (lines 140, 321, 324). See `docs/seqera_cloud_deployment_checklist.md` Step 5b for exact diff.

---

## 1. Input Schema Changes

**File**: `3_5_1/assets/schema_input.json`

### New Columns Added

| Column | Type | Default | Description |
|--------|------|---------|-------------|
| `ploidy` | integer | 2 | Sample ploidy (minimum: 1) |
| `experiment` | string | - | Alternative to patient ID |
| `clonal_or_population` | string | "clonal" | Either "clonal" or "population" |

### Example Input CSV
```csv
patient,sample,lane,fastq_1,fastq_2,ploidy,clonal_or_population
patient1,sample1,lane1,reads_1.fq.gz,reads_2.fq.gz,2,clonal
patient2,sample2,lane1,reads_1.fq.gz,reads_2.fq.gz,1,population
```

---

## 2. Ploidy Integration in Variant Callers

### GATK HaplotypeCaller
**File**: `3_5_1/modules/nf-core/gatk4/haplotypecaller/main.nf:44`
```groovy
--sample-ploidy ${meta.ploidy ?: 2}
```

### FreeBayes
**File**: `3_5_1/conf/modules/freebayes.config:28,66`
```groovy
--ploidy ${meta.ploidy}
```

### CNVKit
**File**: `3_5_1/conf/modules/cnvkit.config:30,39`
```groovy
--ploidy ${meta.ploidy}
```

### Control-FREEC
**File**: `3_5_1/conf/modules/controlfreec.config`
- Uses `meta.ploidy` instead of `params.cf_ploidy` (lines 37, 46, 79, 116)
- Skips `ASSESS_SIGNIFICANCE` when ploidy=1 (line 19)

### TIDDIT
**File**: `3_5_1/conf/modules/tiddit.config:19`
```groovy
(meta.ploidy ? " -n ${meta.ploidy}" : '')
```

### VCFtools
**File**: `3_5_1/conf/modules/modules.config:105-110`
- Auto-skipped when `ploidy > 2` (incompatible with polyploidy)
- Also skipped for mutect2 and joint_variant_calling

---

## 3. New Subworkflows

### VCF Filtering Subworkflows
| Directory | Purpose |
|-----------|---------|
| `subworkflows/local/vcf_filter_freebayes/` | FreeBayes VCF filtering |
| `subworkflows/local/vcf_filter_mutect2/` | Mutect2 VCF filtering |
| `subworkflows/local/vcf_filter_haplotypecaller_joint/` | HaplotypeCaller joint calling filter |
| `subworkflows/local/split_joint_vcf/` | Split joint VCF into individual samples |

### Split Joint VCF Logic
**File**: `3_5_1/conf/modules/joint_germline.config:121-140`

Splits joint-called VCF into per-sample VCFs with proper genotype handling:
```groovy
def ploidy = meta.ploidy ?: 2
def ref_gt_unphased = (['0'] * ploidy).join('/')  // "0/0" for diploid
def ref_gt_phased = (['0'] * ploidy).join('|')    // "0|0" for diploid
```

---

## 4. New Modules

### BCFtools Modules Added
```
modules/nf-core/bcftools/
├── filter/    # VCF filtering
├── query/     # VCF querying
└── view/      # Sample extraction
```

### GATK4 VariantFiltration
```
modules/nf-core/gatk4/variantfiltration/
```

---

## 5. New Configuration Files

| File | Purpose |
|------|---------|
| `conf/modules/bcftools_filter.config` | BCFtools filter settings |
| `conf/modules/custom_freebayes_filter.config` | FreeBayes-specific filters |
| `conf/modules/custom_haplotypecaller_joint_filter.config` | Joint calling filters |
| `conf/modules/custom_mutect2_filter.config` | Mutect2-specific filters |

---

## 6. Workflow Changes

**File**: `3_5_1/workflows/sarek/main.nf`

### Key Changes:

1. **New imports** (lines 86-95):
   - `VCF_FILTER_FREEBAYES`
   - `VCF_FILTER_MUTECT2`
   - `TABIX_TABIX`

2. **Normal sample handling** (lines 683-688):
   - Hard-coded to run all samples in normal mode:
   ```groovy
   // hard fix to get all samples run as normal mode
   cram_variant_calling_status_normal = cram_variant_calling
   ```

3. **Tumor-normal pair ploidy** (line 704):
   ```groovy
   meta.ploidy = tumor[1].ploidy ?: '2'  // Use tumor ploidy
   ```

4. **CNVKit VCF added to annotation** (line 802):
   ```groovy
   vcf_to_annotate = vcf_to_annotate.mix(BAM_VARIANT_CALLING_GERMLINE_ALL.out.vcf_cnvkit)
   ```

5. **VCF indexing and filtering** (lines 823-840):
   - Added TABIX_TABIX for VCF indexing
   - Added VCF_FILTER_FREEBAYES integration

---

## 7. Joint Germline Calling Parameters

### Command-Line Options for Joint Calling

When running Sarek with HaplotypeCaller joint germline calling, the following parameters control the workflow:

| Parameter | Description |
|-----------|-------------|
| `--joint_germline` | Enable joint germline variant calling (combines all samples) |
| `--split_haplotypecaller_joint_vcf` | Split the joint VCF into individual per-sample VCFs |
| `--hard_filter_haplotypecaller_joint` | Apply GATK hard filters instead of VQSR (useful for small cohorts) |

### Example Usage
```bash
nextflow run nf-core/sarek \
  --input samplesheet.csv \
  --tools haplotypecaller \
  --joint_germline \
  --split_haplotypecaller_joint_vcf \
  --hard_filter_haplotypecaller_joint
```

### When to Use These Options

- **`--joint_germline`**: Required for multi-sample projects where you want to call variants across all samples together, improving sensitivity for rare variants.

- **`--split_haplotypecaller_joint_vcf`**: Use when you need individual VCF files per sample after joint calling. This extracts each sample from the joint VCF and removes reference-only genotypes.

- **`--hard_filter_haplotypecaller_joint`**: Use instead of VQSR when:
  - Working with small cohorts (< 30 samples)
  - Non-human organisms without truth sets
  - When VQSR fails or is inappropriate for your data

---

## 8. Joint Germline Config Details

**File**: `3_5_1/conf/modules/joint_germline.config`

### Hard Filter Settings (lines 86-113)
Applies hard filters when VQSR is not available:
- QD < 2.0
- FS > 60.0
- SOR > 3.0
- MQ < 40.0
- MQRankSum < -12.5
- ReadPosRankSum < -8.0
- QUAL < 30.0

### Per-Sample Extraction from Joint VCF (lines 115-140)
- Uses `BCFTOOLS_VIEW` to extract individual samples
- Uses `BCFTOOLS_FILTER` to remove reference-only genotypes
- Handles both phased and unphased genotypes based on ploidy

---

## 9. Other Changes

### Documentation
- Added: `3_5_1/docs/manual_vcf_operations.md`

### Config Directory
- Added: `configs/` directory (pipeline configurations)

### MultiQC Config
- Modified: `3_5_1/assets/multiqc_config.yml`

---

## Backwards Compatibility

- Samplesheets without new columns (ploidy, experiment, clonal_or_population) continue to work
- Default ploidy is 2 (diploid)
- Default clonal_or_population is "clonal"
