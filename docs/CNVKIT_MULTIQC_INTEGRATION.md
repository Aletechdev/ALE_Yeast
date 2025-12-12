# CNVkit MultiQC Integration

**Date**: 2025-11-25
**Author**: Modifications to nf-core/sarek v3.5.1
**Purpose**: Enable CNVkit VCF outputs to appear in MultiQC reports

## Problem Statement

CNVkit was running successfully in the Sarek pipeline, but its VCF outputs were not appearing in the MultiQC report, unlike other variant callers (FreeBayes, GATK HaplotypeCaller, TIDDIT, etc.).

## Root Causes

### 1. CNVkit VCFs Not in QC Pipeline
CNVkit VCF outputs were not being added to the `vcf_to_annotate` channel that feeds into `VCF_QC_BCFTOOLS_VCFTOOLS`, which generates the statistics collected by MultiQC.

### 2. Missing BGZF Compression
CNVkit exports plain VCF files, but the pipeline's `TABIX_TABIX` process requires BGZF (block gzip) compressed files for indexing.

### 3. Filename Suffix Loss
When adding bgzip compression, the `.cnvcall` suffix was being lost during compression, causing sample identification issues in MultiQC.

## Solution Overview

The solution involved three main changes:

1. **Add bgzip compression step** for CNVkit VCFs
2. **Emit CNVkit VCFs** from the germline variant calling workflow
3. **Configure filename preservation** to maintain the `.cnvcall` suffix
4. **Add CNVkit VCFs to QC pipeline** by mixing them into `vcf_to_annotate`

## Detailed Changes

### 1. Modified Files

#### A. `subworkflows/local/bam_variant_calling_cnvkit/main.nf`

**Added TABIX_BGZIPTABIX import:**
```groovy
include { TABIX_BGZIPTABIX as TABIX_BGZIP_CNVKIT } from '../../../modules/nf-core/tabix/bgziptabix/main'
```

**Added compression step after export:**
```groovy
// export to VCF for compatibility with other tools
CNVKIT_EXPORT(CNVKIT_CALL.out.cns)

// Compress and index VCF for downstream QC and annotation
TABIX_BGZIP_CNVKIT(CNVKIT_EXPORT.out.output)
```

**Modified VCF output to use compressed files:**
```groovy
// Add variantcaller metadata to compressed VCF output for MultiQC reporting
vcf_cnvkit = TABIX_BGZIP_CNVKIT.out.gz_tbi.map{ meta, gz, tbi ->
    [ meta + [ variantcaller: 'cnvkit'], gz ]
}
```

**Added new emit:**
```groovy
emit:
    cnv_calls_raw    = CNVKIT_CALL.out.cns
    cnv_calls_export = CNVKIT_EXPORT.out.output
    vcf              = vcf_cnvkit  // ← NEW: emit compressed VCF with metadata
    versions
```

#### B. `subworkflows/local/bam_variant_calling_germline_all/main.nf`

**Initialized vcf_cnvkit channel:**
```groovy
vcf_cnvkit               = Channel.empty()
```

**Captured CNVkit VCF output:**
```groovy
if (tools.split(',').contains('cnvkit')) {
    BAM_VARIANT_CALLING_CNVKIT(...)
    vcf_cnvkit = BAM_VARIANT_CALLING_CNVKIT.out.vcf  // ← NEW
    versions = versions.mix(BAM_VARIANT_CALLING_CNVKIT.out.versions)
}
```

**Added to vcf_all channel:**
```groovy
vcf_all = Channel.empty().mix(
    vcf_cnvkit,  // ← NEW
    vcf_deepvariant,
    vcf_freebayes,
    ...
)
```

**Added to emit section:**
```groovy
emit:
    ...
    vcf_cnvkit  // ← NEW
    vcf_deepvariant
    ...
```

#### C. `workflows/sarek/main.nf`

**Added CNVkit VCFs to QC pipeline:**
```groovy
vcf_to_annotate = Channel.empty()
vcf_to_annotate = vcf_to_annotate.mix(BAM_VARIANT_CALLING_GERMLINE_ALL.out.vcf_cnvkit)  // ← NEW
vcf_to_annotate = vcf_to_annotate.mix(BAM_VARIANT_CALLING_GERMLINE_ALL.out.vcf_deepvariant)
...
```

#### D. `conf/modules/cnvkit.config`

**Added TABIX_BGZIP_CNVKIT configuration (CRITICAL FIX):**
```groovy
withName: '.*:BAM_VARIANT_CALLING_CNVKIT:TABIX_BGZIP_CNVKIT' {
    ext.prefix = { "${meta.id}.cnvcall" }  // ← Preserves .cnvcall suffix
    ext.when   = { params.tools && params.tools.split(',').contains('cnvkit') }
}
```

## Why Filename Preservation Matters

### The Problem
Without proper configuration, the bgzip process would create:
- Input: `A0-F0-I1-R1.cnvcall.vcf`
- Output: `A0-F0-I1-R1.vcf.gz` ⚠️ (lost `.cnvcall` suffix)

### How TABIX_BGZIPTABIX Names Files
```groovy
def prefix = task.ext.prefix ?: "${meta.id}"
bgzip ... $input > ${prefix}.${input.getExtension()}.gz
```

- `prefix` = `"A0-F0-I1-R1"` (default from meta.id)
- `input.getExtension()` = `"vcf"` (extracts only extension, not full basename)
- Result: `"A0-F0-I1-R1.vcf.gz"` (missing `.cnvcall`)

### The Solution
By setting `ext.prefix = { "${meta.id}.cnvcall" }`, we get:
- `prefix` = `"A0-F0-I1-R1.cnvcall"`
- `input.getExtension()` = `"vcf"`
- Result: `"A0-F0-I1-R1.cnvcall.vcf.gz"` ✓

### Why This Is Critical

MultiQC uses the VCF filename as the sample identifier:
- `A0-F0-I1-R1.freebayes.vcf.gz` → "A0-F0-I1-R1.freebayes"
- `A0-F0-I1-R1.tiddit.vcf.gz` → "A0-F0-I1-R1.tiddit"
- `A0-F0-I1-R1.cnvcall.vcf.gz` → "A0-F0-I1-R1.cnvcall" ✓

Without `.cnvcall`, the sample would be named `"A0-F0-I1-R1"`, potentially conflicting with other samples or being ignored as a duplicate.

## Complete Pipeline Flow

```
CNVKIT_BATCH → .cnr, .cns files
  ↓
CNVKIT_CALL → called .cns segments
  ↓
CNVKIT_EXPORT → A0-F0-I1-R1.cnvcall.vcf
  ↓ (ext.prefix = "${meta.id}.cnvcall")
TABIX_BGZIP_CNVKIT → A0-F0-I1-R1.cnvcall.vcf.gz + .tbi
  ↓ (adds variantcaller: 'cnvkit' to meta)
vcf_cnvkit channel
  ↓
BAM_VARIANT_CALLING_GERMLINE_ALL.out.vcf_cnvkit
  ↓
vcf_to_annotate (main.nf)
  ↓
TABIX_TABIX (indexing - redundant but harmless since already indexed)
  ↓
VCF_QC_BCFTOOLS_VCFTOOLS
  ├─→ bcftools stats
  └─→ vcftools stats
    ↓
reports channel
  ↓
MultiQC ✓
```

## Results

After implementing these changes:

✅ **7 CNVkit germline samples** now appear in MultiQC bcftools stats
✅ **Proper sample identification** with `.cnvcall` suffix preserved
✅ **Bcftools and vcftools statistics** generated for CNVkit VCFs
✅ **Consistent with other variant callers** (TIDDIT, FreeBayes, etc.)

Example output in MultiQC:
```
Sample                  number_of_records  number_of_others
A0-F0-I1-R1.cnvcall     15                 15
A0-F0-I1-R1.freebayes   50                 0
A0-F0-I1-R1.tiddit      2                  0
```

Note: CNV calls appear as "others" type variants (not SNPs/indels), which is expected.

## Lessons Learned

1. **File naming is critical** - Suffixes must be preserved through the entire pipeline for proper sample identification
2. **Follow existing patterns** - TIDDIT provided the template for integrating SV/CNV callers into the QC pipeline
3. **Configuration matters** - The `ext.prefix` setting in `modules.config` was key to solving the filename issue
4. **Nextflow caching gotchas** - Structural workflow changes require clearing cached results (can't rely on `-resume`)

## Future Work

This modification only addresses the **germline variant calling workflow**. To extend CNVkit VCF reporting to:
- **Somatic variant calling** (tumor-normal pairs)
- **Tumor-only variant calling**

Similar changes would need to be applied to:
- `subworkflows/local/bam_variant_calling_somatic_all/main.nf`
- `subworkflows/local/bam_variant_calling_tumor_only_all/main.nf`

## Testing

To verify CNVkit integration is working:

```bash
# Check for CNVkit samples in MultiQC data
grep "cnvcall" output/multiqc/multiqc_data/multiqc_bcftools_stats.txt

# Verify compressed VCF files have correct naming
find work_* -name "*cnvcall*.vcf.gz" | head -5

# Check MultiQC sources
grep "cnvcall" output/multiqc/multiqc_data/multiqc_sources.txt
```

## References

- nf-core/sarek documentation: https://nf-co.re/sarek
- CNVkit documentation: https://cnvkit.readthedocs.io
- TIDDIT integration (used as template): `subworkflows/local/bam_variant_calling_single_tiddit/main.nf`
