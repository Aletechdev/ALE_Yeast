# HaplotypeCaller Workflow Analysis: Joint Calling vs Individual Calling

**Date**: 2025-12-10
**Author**: Analysis based on nf-core/sarek v3.5.1
**Purpose**: Document the information flow, channel dependencies, and parameter requirements for HaplotypeCaller variant calling modes

---

## Executive Summary

HaplotypeCaller in Sarek has two distinct modes with significantly different behaviors:

1. **Individual Calling Mode** - Each sample is called independently
2. **Joint Calling Mode** - All samples are jointly genotyped, then split into individual VCFs

**Critical Finding**: For proper VCF QC (bcftools stats, vcftools) and filtering to work reliably, **joint calling mode with splitting and hard filtering is required**.

---

## Table of Contents

1. [Key Parameters](#key-parameters)
2. [Workflow Comparison](#workflow-comparison)
3. [Channel Flow Analysis](#channel-flow-analysis)
4. [Critical Issues with Individual Mode](#critical-issues-with-individual-mode)
5. [Recommended Configuration](#recommended-configuration)
6. [Technical Details](#technical-details)

---

## Key Parameters

### Essential Parameters for Joint Calling

| Parameter | Type | Default | Purpose |
|-----------|------|---------|---------|
| `--joint_germline` | boolean | `false` | Enables joint genotyping across all samples |
| `--split_haplotypecaller_joint_vcf` | boolean | `false` | Splits joint VCF into individual sample VCFs |
| `--hard_filter_haplotypecaller_joint` | boolean | `false` | Applies bcftools hard filtering to split VCFs |

### Supporting Parameters

| Parameter | Type | Default | Purpose |
|-----------|------|---------|---------|
| `--skip_tools` | string | `null` | Can include `haplotypecaller_filter` to skip CNN filtering |
| `--tools` | string | required | Must include `haplotypecaller` |

---

## Workflow Comparison

### Individual Calling Mode (Default)

```
BAM files
    ↓
GATK HaplotypeCaller (per sample)
    ↓
Individual VCF per sample
    ↓
[Optional] CNN Filtering (CNNScoreVariants + FilterVariantTranches)
    ↓
vcf_haplotypecaller channel
    ↓
⚠️ PROBLEM: Channel becomes empty after CNN filtering without known sites
    ↓
❌ VCF QC (bcftools stats) does NOT run
```

**Location**: `output_inde/variant_calling/haplotypecaller/{sample}/{sample}.haplotypecaller.vcf.gz`

**Issues**:
- CNN filtering requires known variant sites (dbSNP) to calibrate `FilterVariantTranches`
- Without dbSNP, `FilterVariantTranches` never runs
- VCFs remain CNN-scored but unfiltered
- `vcf_haplotypecaller` channel fails to propagate to QC workflow
- **No bcftools stats generated**

---

### Joint Calling Mode (Recommended)

```
BAM files (all samples)
    ↓
GATK HaplotypeCaller (GVCF mode, per sample)
    ↓
GVCF files
    ↓
GATK GenomicsDBImport (consolidate all samples)
    ↓
GATK GenotypeGVCFs (joint calling)
    ↓
Joint VCF (all samples together)
    ↓
[If --split_haplotypecaller_joint_vcf]
    ↓
BCFTOOLS_SPLIT_JOINT_VCF (extract individual samples)
    ↓
Individual VCFs (renamed, source='joint_calling')
    ↓
[If --hard_filter_haplotypecaller_joint]
    ↓
BCFTOOLS_HARD_FILTER_JOINT
    ├── bcftools norm -m - (split multi-allelic)
    └── bcftools filter (apply quality filters)
    ↓
Filtered individual VCFs
    ↓
vcf_haplotypecaller channel (properly populated)
    ↓
vcf_to_annotate channel
    ↓
✅ VCF_QC_BCFTOOLS_VCFTOOLS runs successfully
    ├── BCFTOOLS_STATS
    ├── VCFTOOLS_TSTV_COUNT
    ├── VCFTOOLS_TSTV_QUAL
    └── VCFTOOLS_SUMMARY
```

**Locations**:
- Joint VCF: `output_joint/variant_calling/haplotypecaller/joint_variant_calling/joint_germline_recalibrated.vcf.gz`
- Split VCFs: `output_joint/variant_calling/haplotypecaller/{sample}/{sample}.haplotypecaller.from_joint_calling.vcf.gz`
- Filtered VCFs: `output_joint/variant_calling_filtered/haplotypecaller/individual_from_joint/{sample}/{sample}.hard_filtered.vcf.gz`
- bcftools stats: `output_joint/reports/bcftools/haplotypecaller/{sample}/{sample}.haplotypecaller.from_joint_calling.bcftools_stats.txt`

---

## Channel Flow Analysis

### Critical Channels

#### 1. `vcf_haplotypecaller` Channel

**Source**: `subworkflows/local/bam_variant_calling_germline_all/main.nf`

**Individual Mode Flow**:
```groovy
// Line 141: Initial population
vcf_haplotypecaller = BAM_VARIANT_CALLING_HAPLOTYPECALLER.out.vcf

// Line 205-214: CNN filtering (if not skipped)
if (!skip_haplotypecaller_filter) {
    VCF_VARIANT_FILTERING_GATK(...)
    vcf_haplotypecaller = VCF_VARIANT_FILTERING_GATK.out.filtered_vcf  // ⚠️ May be empty!
}
```

**Joint Mode Flow**:
```groovy
// Line 162: Joint VCF
vcf_haplotypecaller = BAM_JOINT_CALLING_GERMLINE_GATK.out.genotype_vcf

// Line 171-175: Split into individual VCFs
if (params.split_haplotypecaller_joint_vcf) {
    SPLIT_JOINT_VCF(joint_vcf_tbi, cram)
    vcf_haplotypecaller = vcf_haplotypecaller.mix(SPLIT_JOINT_VCF.out.vcf)  // ✅ Properly mixed
}

// Line 182-195: Hard filtering (if enabled)
if (params.hard_filter_haplotypecaller_joint) {
    VCF_FILTER_HAPLOTYPECALLER_JOINT(split_vcf_for_filter)
    vcf_haplotypecaller = vcf_haplotypecaller.mix(
        VCF_FILTER_HAPLOTYPECALLER_JOINT.out.vcf_filtered.map{ meta, vcf, tbi -> [meta, vcf] }
    )  // ✅ Filtered VCFs added
}
```

**Emitted to**: `BAM_VARIANT_CALLING_GERMLINE_ALL.out.vcf_haplotypecaller`

---

#### 2. `vcf_to_annotate` Channel

**Source**: `workflows/sarek/main.nf`

```groovy
// Line 800-813: Gather all VCFs for QC and annotation
vcf_to_annotate = Channel.empty()
vcf_to_annotate = vcf_to_annotate.mix(BAM_VARIANT_CALLING_GERMLINE_ALL.out.vcf_cnvkit)
vcf_to_annotate = vcf_to_annotate.mix(BAM_VARIANT_CALLING_GERMLINE_ALL.out.vcf_deepvariant)
vcf_to_annotate = vcf_to_annotate.mix(BAM_VARIANT_CALLING_GERMLINE_ALL.out.vcf_freebayes)
vcf_to_annotate = vcf_to_annotate.mix(BAM_VARIANT_CALLING_GERMLINE_ALL.out.vcf_haplotypecaller)  // ⚠️ Critical
vcf_to_annotate = vcf_to_annotate.mix(BAM_VARIANT_CALLING_GERMLINE_ALL.out.vcf_manta)
// ... more variant callers

// Line 853: VCF QC depends on this channel
VCF_QC_BCFTOOLS_VCFTOOLS(vcf_to_annotate, intervals_bed_combined)
```

**Critical**: If `vcf_haplotypecaller` is empty, VCF QC will not run for HaplotypeCaller VCFs.

---

#### 3. VCF QC Outputs

**Source**: `subworkflows/local/vcf_qc_bcftools_vcftools/main.nf`

```groovy
// Line 15: bcftools stats
BCFTOOLS_STATS(vcf.map{ meta, vcf -> [ meta, vcf, [] ] }, ...)

emit:
    bcftools_stats          = BCFTOOLS_STATS.out.stats
    vcftools_tstv_counts    = VCFTOOLS_TSTV_COUNT.out.tstv_count
    vcftools_tstv_qual      = VCFTOOLS_TSTV_QUAL.out.tstv_qual
    vcftools_filter_summary = VCFTOOLS_SUMMARY.out.filter_summary
```

These outputs are collected into MultiQC reports.

---

#### 4. The known-sites starvation pattern (custom genomes)

[Issue 1](#issue-1-cnn-filtering-without-known-sites) below documents one instance of this — `FilterVariantTranches` "created but NEVER submitted tasks". That is not specific to CNN filtering: it is a **general pattern affecting every GATK step that consumes a known-variants resource**, and on a custom genome (no dbSNP) it is the normal state of affairs. Worth understanding once, because the symptom is always "the process silently never runs".

**The rule.** Nextflow's `collect()` defaults to `flat: true`, so it flattens its items and **emits nothing when the flattened result is empty**. An unset resource param becomes `Channel.value([])`, and collecting empty lists yields nothing at all — not an empty list. Verified:

```groovy
Channel.value([]).collect()                              // -> emits NOTHING
Channel.value([]).concat(Channel.value([])).collect()    // -> emits NOTHING
Channel.value(['x']).concat(Channel.value([])).collect() // -> ['x']
Channel.of(1,2).collect()                                // -> [1, 2]
```

A process whose input channel never emits simply never launches. No error, no log, no task.

**`--dbsnp` has three consumers, and the wiring style decides whether it gates.** This is the part that surprises: the same param is harmless in one place and load-bearing in two others.

| Consumer | How `dbsnp` is passed | Gates? |
|----------|----------------------|--------|
| **GenotypeGVCFs** | directly, `dbsnp.map{ [[:], it] }` — a **tuple** | ❌ No. `[[:], []]` emits regardless; you just get no `--dbsnp` arg and no rsIDs |
| **BaseRecalibrator** | `known_sites_indels = dbsnp.concat(known_indels).collect()` (`main.nf:188`) | ✅ **Yes** |
| **VariantRecalibrator** | `resource_vcf` = `known_sites_snps`/`_indels` (same `.collect()`) | ✅ **Yes** |

**VQSR needs two *separate* param families**, and each starves it independently:

| Input | Built from | Unset → |
|-------|-----------|---------|
| `resource_vcf` / `resource_tbi` | `--dbsnp`, `--known_snps`, `--known_indels` (**files**) | emits nothing |
| `labels` | `--dbsnp_vqsr`, `--known_snps_vqsr`, `--known_indels_vqsr` (**`--resource:` strings**) | emits nothing |

So supplying only the files, or only the labels, still leaves `VARIANTRECALIBRATOR_*` starved and the pipeline falls back to [soft filtering](SOFT_FILTER_HAPLOTYPECALLER_JOINT.md). Both families are required for VQSR to run at all.

**Where each affected step ends up on a custom genome:**

| Step | Behaviour with no known sites |
|------|-------------------------------|
| **VQSR** (`VARIANTRECALIBRATOR` → `APPLYVQSR`) | never runs; **auto-falls back** to `VARIANTFILTRATION_FALLBACK`, which takes no resource inputs. The only step with a real fallback. |
| **BQSR** (`BaseRecalibrator` → `ApplyBQSR`) | never runs, then **the run fails** — see below |
| **`FilterVariantTranches`** (individual mode) | never runs → `vcf_haplotypecaller` empty → VCF QC skipped ([Issue 1](#issue-1-cnn-filtering-without-known-sites)) |

**BQSR's failure is a Nextflow join, not a GATK error.** `GATK4_BASERECALIBRATOR` never launches, so `ch_table_bqsr` stays empty, and the next line trips:

```groovy
// workflows/sarek/main.nf:567
cram_applybqsr = ch_cram_for_bam_baserecalibrator.join(ch_table_bqsr, failOnDuplicate: true, failOnMismatch: true)
```

`failOnMismatch` against an empty channel aborts the run with `Join mismatch for the following entries:` (verified, exit 1). Good news: it fails loudly rather than silently dropping samples. Bad news for debugging: **there is no GATK log to inspect** — the tool never ran. This is why `--skip_tools baserecalibrator` is mandatory for custom genomes (`conf/test/ottilie_test.config`); it is a deliberate opt-out, not an automatic one.

---

## Critical Issues with Individual Mode

### Issue 1: CNN Filtering Without Known Sites

**Problem**:
```groovy
// VCF_VARIANT_FILTERING_GATK requires known sites
VCF_VARIANT_FILTERING_GATK(
    vcf_haplotypecaller.join(tbi_haplotypecaller, ...),
    fasta, fasta_fai, dict, intervals_bed_combined_haplotypec,
    known_sites_indels.concat(known_sites_snps).flatten().unique().collect(),  // ⚠️ Empty if no dbSNP
    known_sites_indels_tbi.concat(known_sites_snps_tbi).flatten().unique().collect())
```

**What happens**:
1. `CNNScoreVariants` runs successfully → produces `*.cnn.vcf.gz` with `CNN_1D` scores
2. `FilterVariantTranches` requires `known_sites` for calibration
3. Without known sites, `FilterVariantTranches` never executes
4. `VCF_VARIANT_FILTERING_GATK.out.filtered_vcf` is empty or invalid
5. `vcf_haplotypecaller` channel becomes empty (line 214)
6. VCF QC never runs

**Evidence from logs**:
```
Dec-09 17:39:24.181 INFO  CNNScoreVariants - Done scoring variants with CNN.
[FILTERVARIANTTRANCHES process created but NEVER submitted tasks]
```

---

### Issue 2: Unpublished CNN-scored VCFs

**Problem**: CNN-scored VCFs exist in work directory but are not published.

**Work directory**: `work_inde/fe/b046119dd094c9da1f2ad03f3ded66/A0-F0-I1-R1.cnn.vcf.gz`

**Config**: `conf/modules/haplotypecaller.config:40-44`
```groovy
withName: '.*:VCF_VARIANT_FILTERING_GATK:CNNSCOREVARIANTS' {
    publishDir = [
        enabled: false  // ⚠️ CNN-scored VCFs not published
    ]
}
```

**Result**: Users cannot access CNN-scored VCFs even though scoring succeeded.

---

### Issue 3: Missing VCF QC Reports

**Symptom**:
```bash
# Individual mode - NO bcftools directory
output_inde/reports/
├── fastqc/
├── markduplicates/
├── mosdepth/
└── samtools/

# Joint mode - HAS bcftools directory
output_joint/reports/
├── bcftools/          # ✅ Present
├── fastqc/
├── markduplicates/
├── mosdepth/
├── samtools/
└── vcftools/          # ✅ Present
```

**Cause**: `VCF_QC_BCFTOOLS_VCFTOOLS` never receives VCFs in individual mode.

---

## Recommended Configuration

### For Production Use (Joint Calling with Filtering)

**Script**: `run_joint.sh`

```bash
nextflow run ${ale_nextflow_folder}/nf-core-sarek_3.5.1/3_5_1/main.nf \
    -profile azureD4as,docker \
    -w ${project_folder}/work_joint \
    --input ${project_folder}/samplesheet.csv \
    --outdir ${project_folder}/output_joint \
    --genome null \
    --igenomes_ignore \
    --fasta ${FASTA} \
    --skip_tools baserecalibrator \
    --tools haplotypecaller \
    --split_fastq 0 \
    --joint_germline \                              # ✅ Enable joint calling
    --save_mapped \
    --split_haplotypecaller_joint_vcf \             # ✅ Split joint VCF into individual VCFs
    --hard_filter_haplotypecaller_joint \           # ✅ Apply hard filtering
    -resume
```

**Benefits**:
- ✅ Joint genotyping improves variant calling accuracy
- ✅ Individual VCFs extracted and renamed
- ✅ Hard filtering applied with sample-specific quality metrics
- ✅ bcftools stats and vcftools QC reports generated
- ✅ Clean MultiQC integration

---

### For Quick Individual Calling (No Filtering)

**Script**: `run_individual.sh`

```bash
nextflow run ${ale_nextflow_folder}/nf-core-sarek_3.5.1/3_5_1/main.nf \
    -profile azureD4as,docker \
    -w ${project_folder}/work_inde \
    --input ${project_folder}/samplesheet.csv \
    --outdir ${project_folder}/output_inde \
    --genome null \
    --igenomes_ignore \
    --fasta ${FASTA} \
    --skip_tools baserecalibrator,haplotypecaller_filter \  # ✅ Skip CNN filtering
    --tools haplotypecaller \
    --split_fastq 0 \
    --save_mapped \
    -resume
```

**Caveats**:
- ⚠️ No joint genotyping (lower accuracy for rare variants)
- ⚠️ No filtering applied (all variants pass)
- ⚠️ VCF QC reports may not be generated reliably
- ✅ Faster execution
- ✅ Lower memory requirements

---

## Technical Details

### Hard Filtering Criteria

**Source**: `conf/modules/custom_haplotypecaller_joint_filter.config:24-30`

```groovy
ext.args = [
    '--include',
    '"FILTER=\\"PASS\\"',                          // Joint calling PASS filter
    '& FORMAT/GQ>=20',                             // Genotype quality ≥ 20
    '& FORMAT/DP>=8',                              // Sample depth ≥ 8 reads
    '& FORMAT/AD[0:1]/(FORMAT/AD[0:0]+FORMAT/AD[0:1])>=0.8"'  // ALT allele freq ≥ 80%
].join(' ')
```

**Process**: `BCFTOOLS_HARD_FILTER_JOINT`

**Steps**:
1. `bcftools norm -m -` - Split multi-allelic variants into bi-allelic records
2. `bcftools filter` - Apply quality filters (removes variants, not set to missing)
3. `bcftools index` - Index filtered VCF

**Key Distinction**:
- **FORMAT/DP**: Sample-specific depth (this sample only)
- **INFO/DP**: Cohort-wide depth (all samples combined)

**Output**: `{sample}.hard_filtered.vcf.gz`

---

### CNN Filtering Architecture

**Model**: 1D CNN (`1d_cnn_mix_train_full_bn`)

**Input Features**:
- Read alignment context
- Base quality scores
- Mapping quality
- Position in read
- Strand information

**Output**: `CNN_1D` score in INFO field
- Negative values: Lower quality
- Positive values: Higher quality
- Typical range: -2.0 to +2.0

**Example from VCF**:
```vcf
chr10  7856   .  C    CTA   1610.01  .  AC=1;AF=1.00;AN=1;CNN_1D=-1.266;DP=40;...
chr10  7863   .  TCCA T     1816.01  .  AC=1;AF=1.00;AN=1;CNN_1D=0.021;DP=45;...
chr10  10362  .  A    AG    259.01   .  AC=1;AF=1.00;AN=1;CNN_1D=0.495;DP=10;...
```

**FilterVariantTranches Requirements**:
- Requires known variant sites (truth set) for calibration
- Creates sensitivity tranches (e.g., 99.9%, 99.5%, 99.0%)
- Without truth set, cannot determine filtering thresholds

---

### VCF Metadata Tracking

**Split VCFs metadata** (added by `SPLIT_JOINT_VCF`):

```groovy
meta.variantcaller = 'haplotypecaller'
meta.source = 'joint_calling'
```

**Filtered VCFs metadata** (added by `VCF_FILTER_HAPLOTYPECALLER_JOINT`):

```groovy
meta.variantcaller = 'haplotypecaller'
meta.source = 'joint_calling'
meta.filter = 'hard_filtered'
```

**File naming convention**:
- Unfiltered: `{sample}.haplotypecaller.from_joint_calling.vcf.gz`
- Filtered: `{sample}.hard_filtered.vcf.gz`

---

## Priority Recommendations for Developers

### High Priority

1. **Fix CNN filtering in individual mode**
   - Make `FilterVariantTranches` optional when `known_sites` is empty
   - OR publish CNN-scored VCFs even without filtering
   - OR automatically skip CNN filtering when no known sites provided

2. **Ensure VCF QC always runs**
   - Make `VCF_QC_BCFTOOLS_VCFTOOLS` more robust to empty channels
   - Add diagnostic logging when VCF channels are empty

3. **Document known sites requirement**
   - Add clear error message when CNN filtering fails due to missing known sites
   - Update parameter documentation

### Medium Priority

1. **Publish CNN-scored VCFs**
   - Change `CNNSCOREVARIANTS` publishDir to `enabled: true` optionally
   - Add parameter `--save_cnn_scored_vcfs`

2. **Improve channel propagation**
   - Add channel validation between workflow stages
   - Log channel sizes for debugging

3. **Add parameter validation**
   - Check parameter compatibility (e.g., warn if `--hard_filter_haplotypecaller_joint` without `--split_haplotypecaller_joint_vcf`)

### Low Priority

1. **Create alternative filtering for individual mode**
   - Implement hard filtering for individual VCFs (similar to joint mode)
   - Add `--hard_filter_haplotypecaller_individual` parameter

2. **Enhance documentation**
   - Add workflow diagrams to main docs
   - Create troubleshooting guide

---

## Testing Checklist

When modifying HaplotypeCaller workflows, test:

- [ ] Individual calling without filtering (`--skip_tools haplotypecaller_filter`)
- [ ] Individual calling with CNN filtering (with dbSNP)
- [ ] Individual calling with CNN filtering (without dbSNP) - should fail gracefully
- [ ] Joint calling without splitting
- [ ] Joint calling with splitting (`--split_haplotypecaller_joint_vcf`)
- [ ] Joint calling with splitting and filtering (`--hard_filter_haplotypecaller_joint`)
- [ ] VCF QC reports generated in all modes
- [ ] MultiQC includes bcftools stats in all modes

---

## References

### Key Files

**Workflow**:
- `workflows/sarek/main.nf:641-874` - Main variant calling orchestration
- `subworkflows/local/bam_variant_calling_germline_all/main.nf` - HaplotypeCaller workflow
- `subworkflows/local/vcf_variant_filtering_gatk/main.nf` - CNN filtering
- `subworkflows/local/vcf_filter_haplotypecaller_joint/main.nf` - Hard filtering for joint calling
- `subworkflows/local/vcf_qc_bcftools_vcftools/main.nf` - VCF QC

**Configuration**:
- `conf/modules/haplotypecaller.config` - HaplotypeCaller process configs
- `conf/modules/custom_haplotypecaller_joint_filter.config` - Hard filtering parameters
- `nextflow_schema.json:359-364` - Parameter definitions

**Modules**:
- `modules/nf-core/gatk4/cnnscorevariants/main.nf`
- `modules/nf-core/gatk4/filtervarianttranches/main.nf`
- `modules/nf-core/bcftools/stats/main.nf`

### External Documentation

- [GATK CNNScoreVariants](https://gatk.broadinstitute.org/hc/en-us/articles/360037226672-CNNScoreVariants)
- [GATK FilterVariantTranches](https://gatk.broadinstitute.org/hc/en-us/articles/360037225412-FilterVariantTranches)
- [GATK Joint Genotyping](https://gatk.broadinstitute.org/hc/en-us/articles/360035890431-The-logic-of-joint-calling-for-germline-short-variants)
- [bcftools filter](https://samtools.github.io/bcftools/bcftools.html#filter)

---

## Appendix: Example Outputs

### Joint Calling Directory Structure

```
output_joint/
├── variant_calling/
│   └── haplotypecaller/
│       ├── joint_variant_calling/
│       │   └── joint_germline_recalibrated.vcf.gz      # All samples together
│       ├── A0-F0-I1-R1/
│       │   └── A0-F0-I1-R1.haplotypecaller.from_joint_calling.vcf.gz
│       ├── A1-F6-I1-R1/
│       │   └── A1-F6-I1-R1.haplotypecaller.from_joint_calling.vcf.gz
│       └── ...
├── variant_calling_filtered/
│   └── haplotypecaller/
│       └── individual_from_joint/
│           ├── A0-F0-I1-R1/
│           │   └── A0-F0-I1-R1.hard_filtered.vcf.gz     # Quality filtered
│           └── ...
└── reports/
    ├── bcftools/
    │   └── haplotypecaller/
    │       ├── A0-F0-I1-R1/
    │       │   └── A0-F0-I1-R1.haplotypecaller.from_joint_calling.bcftools_stats.txt
    │       └── ...
    └── vcftools/
        └── ...
```

### Individual Calling Directory Structure

```
output_inde/
├── variant_calling/
│   └── haplotypecaller/
│       ├── A0-F0-I1-R1/
│       │   └── A0-F0-I1-R1.haplotypecaller.vcf.gz       # Unfiltered only
│       └── ...
└── reports/
    ├── fastqc/
    ├── markduplicates/
    ├── mosdepth/
    └── samtools/
    # ⚠️ NO bcftools/ or vcftools/ directories
```

---

**Document Version**: 1.0
**Last Updated**: 2025-12-10
**Next Review**: When Sarek is upgraded or workflow is modified
