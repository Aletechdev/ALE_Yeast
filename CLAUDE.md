# NF_ALE Project Notes

## Table of Contents
1. [Environment Setup](#environment-setup)
2. [Input Configuration](#input-configuration)
3. [Variant Calling Strategy](#variant-calling-strategy)
4. [Implementation Details](#implementation-details)
5. [Tool-Specific Notes](#tool-specific-notes)
6. [Analysis Dashboard](#analysis-dashboard)
7. [Future Development](#future-development)

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
- **Pipeline Config**: `bin/nextflow.config` (D4as profile for VM resources)
- **Cache Generation**: `bin/prepare_input/process_GeneBank/generate_cache/gen_cache.sh`
- **Forked nf-core**: `nf-core-sarek_3.5.1` (use version 3.5.1 docs)

### Sample Table Format

Adapted from nf-sarek (originally for human cancer research):
- **experiment**: Experiment ID (maps to "patient" in Sarek)
- **status**: 0 = ancestral strain (normal), 1 = evolved strain (tumor)
- **ploidy**: Custom column for ploidy support
- **Requirement**: Each experiment **must have one normal sample** (status: 0)

**Example:**
```csv
experiment,sample,status,clonal_or_population,ploidy,lane,fastq_1,fastq_2
ALE_Exp1,A4-F5-I1-R1,1,clonal,2,L001,SubSampleA4-5_S11_L001_R1_001.fastq.gz,SubSampleA4-5_S11_L001_R2_001.fastq.gz
ALE_Exp1,A4-F5-I1-R1,1,clonal,2,L003,SubSampleA4-5_S11_L003_R1_001.fastq.gz,SubSampleA4-5_S11_L003_R2_001.fastq.gz
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
- Passed to: `cnvkit, controlfreec, FreeBayes, Tiddit`
- **Note**: `bcftools mpileup` still uses ploidy=1 in `conf/modules/ngscheckmate.config`

---

## Implementation Details

### Custom Filtering Workflows

#### ✅ Allele Frequency-Based Somatic Filtering

**Migration from GT-based to AF-based filtering** for somatic variant detection:

**Mutect2 Filtering** (`vcf_filter_mutect2/bcftools/filter_somatic/main.nf`):
- **Strategy**: Direct AF field usage from `FORMAT/AF[sample]`
- **Criteria**: Normal AF < 0.10, Tumor AF > 0.05, AF difference > 0.05, Depth (tumor ≥10, normal ≥8)
- **Config**: `conf/modules/custom_mutect2_filter.config`

**FreeBayes Filtering** (`vcf_filter_freebayes/bcftools/filter_somatic/main.nf`):
- **Strategy**: Multi-allelic splitting (`bcftools norm -m-`) + calculated AF via AWK
- **Criteria**: Same AF thresholds as Mutect2
- **Config**: `conf/modules/custom_freebayes_filter.config`

**Multi-allelic Handling Example:**
```
Before splitting (AECK01000002:547636):
  REF: AGTATAC  ALT: TGTGTAT,AGTGTAC  (AO=12,5 and AO=0,1)

After bcftools norm -m-:
  Record 1: AGTATAC → TGTGTAT  (AO=12, AO=0)
  Record 2: AGTATAC → AGTGTAC  (AO=5, AO=1)
```

**Benefits:**
- ✅ Eliminates AO subfield complexity
- ✅ Processes all alternate alleles individually
- ✅ Consistent AF thresholds across tools
- ✅ More sensitive low-frequency detection

#### ⚠️ Mutect2 AF vs AD Discrepancy

**Observation**: Mutect2's `FORMAT/AF` ≠ simple `AD[alt]/DP` calculation

**Root Cause**: Bayesian allele frequency estimation incorporating base quality, mapping quality, and local assembly

**Impact**:
- Using `FORMAT/AF` in filters is correct for Mutect2
- May show discrepancies when compared to FreeBayes AO/(AO+RO)
- More sensitive due to Bayesian uncertainty

#### ✅ Strand Bias Filtering

**Impact**: Removes >50% of raw Mutect2 calls (23,847/45,139 variants)

**Implementation**: `FORMAT/F1R2[1:1] > 0 && FORMAT/F2R1[1:1] > 0`

**Pipeline Chain:**
```
Raw: 45,139 → Quality filters → Strand bias (-52.8%) → AF filters → Final: ~4,200 (90.7% reduction)
```

**Significance**: Eliminates PCR artifacts and sequencing errors critical for ALE experiments

#### ✅ FreeBayes Somatic Mode Disabled

BAM_VARIANT_CALLING_FREEBAYES channel disabled in workflow `~/Docs/ALE_nextflow/nf-core-sarek_3.5.1/3_5_1/subworkflows/local/bam_variant_calling_somatic_all/main.nf` 
**Rationale**: FreeBayes somatic mode designed for cancer genomics, inappropriate for ALE

**Evidence**:
- Somatic mode: 248,248 variants (excessive noise)
- Germline mode: 10,965 variants (biologically relevant)

**Current Strategy**:
- **FreeBayes**: Germline mode only
- **Mutect2**: Somatic mode with custom filtering
- **HaplotypeCaller**: Joint as individual germline

**Channel Logic**: All samples processed as "normal" status (`cram_variant_calling_status_normal`)

**⚠️ Pending Review**: Structural variant tools (Manta, Strelka, TIDDIT) - germline vs somatic mode optimization needed

### Bug Fixes

#### ✅ YAML Processing Error (Custom VCF Filters)

**Issue**: Groovy method resolution ambiguity in `processVersionsFromYAML()`

**Solution**:
- Used explicit `java.io.FileInputStream(path.toFile())`
- Added null/empty file validation and existence checks
- Maintained backward compatibility

**File**: `nf-core-sarek_3.5.1/3_5_1/subworkflows/nf-core/utils_nfcore_pipeline/main.nf`

**Impact**: VCF_FILTER_FREEBAYES and VCF_FILTER_MUTECT2 processes now work correctly

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

### Control-FREEC Limitations

#### ⚠️ No SNP Database

**Warning**: BAF (B-Allele Frequency) files not generated without SNP database (e.g., dbSNP)

**Impact**: Copy number analysis uses read depth only (expected for custom genomes)

#### ⚠️ ASSESS_SIGNIFICANCE Skipped (Ploidy=1)

**Reason**: Haploid strains produce empty `*.gz_CNVs` files → R script fails

**Configuration** (`conf/modules/controlfreec.config`):
```yaml
withName: 'ASSESS_SIGNIFICANCE' {
    ext.when = { !(meta.ploidy == null || meta.ploidy == 1) }
}
```

**Impact**: Pipeline completes successfully for haploid strains, CNV analysis continues with read depth ratios

#### ✅ FilterMutectCalls Channel Join Fix (Dec 2024)

**Issue**: FilterMutectCalls skipped when no `--germline_resource` provided

**Root Cause**: Empty contamination channels → `vcf.join(Channel.empty())` = empty result

**Fix** (`bam_variant_calling_somatic_mutect2/main.nf:177-199`):
```nextflow
// Replaced Channel.empty() with placeholder channels
calculatecontamination_out_seg = vcf.map{ meta, vcf -> [ meta, [] ] }
calculatecontamination_out_cont = vcf.map{ meta, vcf -> [ meta, [] ] }
```

**Results**:
- ✅ `*.mutect2.filtered.vcf.gz` now generated
- ✅ `*.filteringStats.tsv` now available
- ✅ `*.mutect2.artifactprior.tar.gz` now utilized
- ✅ Read orientation bias + quality filtering applied
- ❌ Contamination/population frequency filtering unavailable (as expected)

#### ✅ Dual Filtering Strategy

**Available Workflows**:
1. **GATK FilterMutectCalls**: Standard cancer genomics filtering (`*.mutect2.filtered.vcf.gz`)
2. **Custom Mutect2**: AF-based ALE-optimized filtering (`vcf_filter_mutect2/`)
3. **Custom FreeBayes**: Multi-allelic splitting + AF filtering (`vcf_filter_freebayes/`)

**Recommendation**: Layered QC - GATK for technical artifacts, custom for biological interpretation

#### ⚠️ FilterMutectCalls Parameters

**Current**: GATK defaults only (no custom `ext.args`)
- `--normal-p-value-threshold 0.001` (very stringent)
- `--false-discovery-rate 0.05`
- **Pass rate**: 54/8,825 variants (0.6%)

**Filter Distribution**:
- base_qual;normal_artifact;orientation;strand_bias: 1,925
- multiallelic;normal_artifact;slippage: 749
- normal_artifact;slippage: 619
- **PASS**: 54 only

**⚠️ TODOs**:
- Review parameter relaxation for ALE (e.g., `--normal-p-value-threshold 0.01`)
- Generate PASS-only VCF extraction workflow
- Evaluate dual-filtering optimal balance

### **✅ IMPLEMENTED: Filter Annotation Fallback for Joint Germline Calling**

**Implementation Date**: September 2025
**Updated**: October 2025 (renamed for clarity)

**Problem Solved**: Joint germline calling produced unfiltered VCFs when VQSR (Variant Quality Score Recalibration) failed due to missing known variant resources for custom yeast genome.

**Solution**: Added GATK VariantFiltration as intelligent fallback when VQSR cannot run. This process **populates the FILTER column** with quality flags but **retains all variants** for manual review.

#### **⚠️ Important: Terminology Clarification**
- **"Filter Annotation"** = Populates FILTER column (`PASS` or filter names like `QD_filter`)
- **Does NOT remove variants** - All 1,748 variants remain in the output VCF
- This is standard VCF **soft filtering** (flagging), not hard removal
- **Results**: 737 variants marked `PASS` (42.2%), 1,011 flagged with filter names (57.8%)
- **Extract PASS-only variants** for downstream analysis:
  ```bash
  bcftools view -f PASS HaplotypeCaller_joint_calling_soft_filtered.vcf.gz -O z -o joint_germline_PASS.vcf.gz
  ```

#### **Changes Made:**

1. **Module Installation**: Added `gatk4/variantfiltration` using `nf-core modules install`

2. **Workflow Integration**: Modified `subworkflows/local/bam_joint_calling_germline_gatk/main.nf`:
   - Added `GATK4_VARIANTFILTRATION` import as `VARIANTFILTRATION_FALLBACK`
   - Added filter annotation process after joint genotyping (always runs)
   - Modified conditional logic: `VQSR > Filter Annotation > Unfiltered`

3. **Configuration**: Added filter annotation parameters in `conf/modules/joint_germline.config`:
   ```groovy
   withName: 'VARIANTFILTRATION_FALLBACK' {
       ext.args = { [
           // SNP filters (populates FILTER column, does not remove variants)
           '--filter-name "QD_filter" --filter "QD < 2.0"',
           '--filter-name "FS_filter" --filter "FS > 60.0"',
           '--filter-name "SOR_filter" --filter "SOR > 3.0"',
           '--filter-name "MQ_filter" --filter "MQ < 40.0"',
           // INDEL filters (more lenient)
           '--filter-name "FS_INDEL_filter" --filter "TYPE==INDEL && FS > 200.0"',
           // ... additional filters
       ].join(' ') }
       ext.prefix = { 'HaplotypeCaller_joint_calling_soft_filtered' }
   }
   ```

#### **Filtering Logic Priority:**
1. **VQSR filtered VCF** (when known sites available - humans)
2. **Filter-annotated VCF** (**NEW** - fallback when VQSR fails - custom genomes)
3. **Unfiltered VCF** (should not happen with our implementation)

#### **Output Files:**
- **VQSR success**: `joint_germline_recalibrated.vcf.gz`
- **VQSR failure**: `HaplotypeCaller_joint_calling_soft_filtered.vcf.gz` (**NEW**)
- **Final output**: `joint_germline.vcf.gz` (best available version)

#### **Filter Performance (Test Data):**
Most common filter flags from 1,748 total variants:
1. **QD_filter**: 831 variants (49.1%) - Quality by Depth < 2.0
2. **SOR_filter**: 278 variants (16.4%) - Strand Odds Ratio > 3.0
3. **MQ_filter**: 107 variants (6.3%) - Mapping Quality < 40.0
4. **FS_filter**: 77 variants (4.5%) - Fisher Strand > 60.0

#### **Benefits for Yeast ALE:**
- **Consistent quality control** regardless of known variant availability
- **Appropriate for evolutionary studies** (no population bias)
- **Quality-based flagging** suitable for detecting novel mutations
- **All variants retained** for manual review and parameter optimization
- **Backward compatible** with human/model organism pipelines

**Status**: ✅ **Production Ready** - Implementation complete and tested

**⚠️ TODO**: **Review and optimize filter parameters** for yeast ALE experiments:
- Current parameters are based on GATK best practices for human data
- QD_filter is most restrictive (49% of variants) - consider relaxing threshold
- May need adjustment for yeast genome characteristics (smaller size, different mutation patterns)
- Consider relaxing thresholds for evolutionary studies vs. clinical diagnostics
- Evaluate filtering stringency against known ALE mutation types

---

### **✅ IMPLEMENTED: Split Joint VCF into Individual Sample VCFs (Channel-Based)**

**Implementation Date**: October 2025
**Updated**: October 2025 (Migrated to channel-based approach)

**Problem Solved**: Joint germline calling produces a multi-sample VCF with all samples combined. For downstream analysis, annotation, or comparison purposes, individual sample VCFs may be needed.

**Solution**: Created `SPLIT_JOINT_VCF` subworkflow that efficiently extracts individual sample VCFs from the joint calling output using channel-based metadata propagation (NextFlow best practice).

#### **How Sample Names Are Formatted:**

Sample names in joint VCF follow the `${patient}_${sample}` format, set during alignment:

**Location**: `workflows/sarek/main.nf:292`
```groovy
SM:${meta.patient}_${meta.sample}
```

**Example**: Input `patient: ALE_Exp1, sample: A0-F0-I1-R1` → Joint VCF column: `ALE_Exp1_A0-F0-I1-R1`

#### **Implementation Approach: Channel-Based (NextFlow Best Practice)**

**Architecture**: Uses existing `cram_variant_calling_status_normal` channel to propagate structured metadata instead of string parsing.

**Files Modified:**
- `subworkflows/local/split_joint_vcf/main.nf` - Channel-based subworkflow
- `subworkflows/local/bam_variant_calling_germline_all/main.nf` - Passes cram channel
- `conf/modules/joint_germline.config` (lines 110-131) - Configuration

**Key Features:**
1. **Channel-Based Metadata**: Uses structured sample metadata from pipeline channels
2. **No String Parsing**: Avoids fragile string manipulation, uses typed metadata fields
3. **Metadata Preservation**: Keeps all original sample info (ploidy, status, sex, etc.)
4. **Parallel Processing**: Each sample extracted independently
5. **Automatic Indexing**: Generates `.tbi` index files
6. **NextFlow Idiomatic**: Follows nf-core/sarek patterns and best practices

**Output Structure:**
```
variant_calling/haplotypecaller/individual_from_joint/
├── A0-F0-I1-R1/
│   ├── A0-F0-I1-R1_from_joint.vcf.gz
│   └── A0-F0-I1-R1_from_joint.vcf.gz.tbi
├── A1-F6-I1-R1/
│   ├── A1-F6-I1-R1_from_joint.vcf.gz
│   └── A1-F6-I1-R1_from_joint.vcf.gz.tbi
└── ...
```

#### **Manual Usage (Quick Split):**

```bash
source ~/miniforge3/etc/profile.d/conda.sh && conda activate nf-env
cd output_all/variant_calling/haplotypecaller/joint_variant_calling

# Extract and split in one command
mkdir -p individual_samples
bcftools query -l HaplotypeCaller_joint_calling_soft_filtered.vcf.gz | while read sample; do
    sample_id=$(echo "$sample" | cut -d'_' -f2-)
    bcftools view -s "$sample" --force-samples -O z \
        -o "individual_samples/${sample_id}_from_joint.vcf.gz" \
        HaplotypeCaller_joint_calling_soft_filtered.vcf.gz
    bcftools index -t "individual_samples/${sample_id}_from_joint.vcf.gz"
done
```

#### **Use Cases:**

1. ✅ **Comparison Analysis**: Compare joint vs individual HaplotypeCaller results
2. ✅ **Sample-Specific Annotation**: Tools that work better with single-sample VCFs
3. ✅ **Data Distribution**: Share individual results without exposing all samples
4. ✅ **Downstream Tools**: Tools expecting single-sample input
5. ✅ **Quality Control**: Per-sample variant review

#### **Performance:**

- **Speed**: ~30-60 seconds for 7 samples (parallel extraction)
- **Efficiency**: bcftools view is very fast and memory-efficient
- **Scalability**: Linear with number of samples

**Status**: ✅ **Fully Integrated** - Ready for production use

#### **Usage:**

**Enable in pipeline run:**
```bash
--joint_germline --split_haplotypecaller_joint_vcf
```

**Pipeline integration** (`bam_variant_calling_germline_all/main.nf:162-170`):
```groovy
if (params.split_haplotypecaller_joint_vcf) {
    joint_vcf_tbi = BAM_JOINT_CALLING_GERMLINE_GATK.out.genotype_vcf
        .join(BAM_JOINT_CALLING_GERMLINE_GATK.out.genotype_index, failOnDuplicate: true)

    // Pass both joint VCF and original cram channel for metadata
    SPLIT_JOINT_VCF(joint_vcf_tbi, cram)
}
```
- Automatically runs after HaplotypeCaller joint germline calling when `--split_haplotypecaller_joint_vcf` is enabled
- Uses both joint VCF and `cram` channel for structured metadata
- Outputs individual VCFs with renamed samples (patient prefix removed)

**Channel-Based Metadata Flow:**
```groovy
// Combines joint VCF with individual sample metadata
joint_vcf_tbi                           cram channel
[meta_joint, vcf, tbi]     +     [meta_sample, cram, crai]
         ↓                                    ↓
    Join on patient ID (meta.patient)
         ↓
[meta_combined, vcf, tbi]
    ↓
meta_combined = {
    id: "A0-F0-I1-R1",              // From cram channel
    patient: "ALE_Exp1",            // From cram channel
    sample: "A0-F0-I1-R1",          // From cram channel
    ploidy: 2,                      // ✅ Preserved from cram
    status: 0,                      // ✅ Preserved from cram
    sex: "XX",                      // ✅ Preserved from cram
    variantcaller: "haplotypecaller", // From joint VCF
    bcftools_sample: "ALE_Exp1_A0-F0-I1-R1"  // Constructed for extraction
}
```

**Output Files:**
```
variant_calling/haplotypecaller/individual_from_joint/
├── A0-F0-I1-R1/
│   ├── A0-F0-I1-R1.haplotypecaller.from_joint_calling.vcf.gz
│   └── A0-F0-I1-R1.haplotypecaller.from_joint_calling.vcf.gz.tbi
├── A1-F6-I1-R1/
│   ├── A1-F6-I1-R1.haplotypecaller.from_joint_calling.vcf.gz
│   └── A1-F6-I1-R1.haplotypecaller.from_joint_calling.vcf.gz.tbi
└── ...
```

**Output VCF Sample Names:**
- **Input (Joint VCF column)**: `ALE_Exp1_A0-F0-I1-R1` (patient_sample format from BAM header)
- **Output (Individual VCF column)**: `ALE_Exp1_A0-F0-I1-R1` (keeps original name for traceability)
- **Rationale**: Keeping full sample names makes it easier to trace variants back to joint calling and compare across different VCF files

**Workflow Steps:**
1. **Join channels**: Combine joint VCF metadata with individual sample metadata by patient ID
2. **Extract samples**: Use `bcftools view -s` with structured metadata (compresses with `-Oz`)
3. **Index**: Generate `.tbi` index with `tabix`

**Advantages of Channel-Based Approach:**
- ✅ **Type-safe**: No string parsing errors
- ✅ **Metadata-rich**: Preserves ploidy, status, sex, etc.
- ✅ **Robust**: Independent of naming conventions
- ✅ **NextFlow idiomatic**: Follows nf-core/sarek patterns
- ✅ **Maintainable**: Changes to naming don't break workflow

---

### ~~Basic VCF Filtering Implementation, ***deprecated***, for idea of folders involved for making nf-sarek changes~~

#### Integration Point (REVISED)

- **Location**: `nf-core-sarek_3.5.1/3_5_1/workflows/sarek/main.nf` around line 801
- **Target**: Filter `vcf_to_annotate` channel (before annotation)
- **Rationale**: More flexible during custom SnpEff/VEP database testing, will add breseq gdtools for annotation, where the output will be in .gb format

#### Implementation Steps

1. **Add BCFTOOLS_FILTER module** from nf-core: `nf-core modules install bcftools/filter`
2. **Create filter configuration** at `nf-core-sarek_3.5.1/3_5_1/conf/modules/custom_mutect2_filter.config` `nf-core-sarek_3.5.1/3_5_1/subworkflows/local/vcf_filter_mutect2/bcftools/filter_somatic/main.nf`
3. **New channel vcf_filtered** for downstream QC and annotation
4. **Output structure**: `variant_calling_filtered/{tool}/{sample}/`

#### Integration Code Location

```nextflow
// Around line 801 in main.nf, after:
vcf_to_annotate = vcf_to_annotate.mix(BAM_VARIANT_CALLING_SOMATIC_ALL.out.vcf_all) ##TODO: fix filtermutectcall, and remove this to vcf_to_annotate channel

// ADD FILTERING HERE:
include { BCFTOOLS_FILTER } from '../modules/nf-core/bcftools/filter/main'
BCFTOOLS_FILTER(vcf_to_annotate)
vcf_filtered = BCFTOOLS_FILTER.out.vcf

```

#### Filter Configuration

```bash
# Basic quality filters (no annotation dependency)
--include "QUAL>=20 && INFO/DP>=10"
```

## Variant Analysis Dashboard System

### **Concept: Research-Grade VCF Organization**

Following bioinformatics community best practices for multi-sample, multi-tool variant analysis, we've developed a dashboard system that converts complex VCF structures into analysis-ready formats.

### **Problem Solved**
- **Raw VCFs**: Hard to compare across samples/tools, require specialized knowledge
- **Standard approach**: Joint VCFs (good for population genetics, not ideal for research)
- **Our solution**: Curated dashboards with structured tables for biological interpretation

### **Dashboard Scripts in `bin/` folder**

#### 1. **`bin/summarize_variants.py`** - Variant Overview Generator
**Purpose**: Quick variant counting across samples and tools
```python
# Key functions:
count_variants_in_vcf()  # Uses bcftools for accurate counting
summarize_variants()     # Creates cross-sample comparison
generate_file_index()    # Maps important files for manual review
```
**Output**: 
- `variant_summary.csv` - Variant counts by sample/tool
- `file_index.csv` - Key files for manual review
**Usage**: `python bin/summarize_variants.py`

#### 2. **`bin/organize_results.sh`** - Manual Review Organizer  
**Purpose**: Creates structured directory for manual variant review
```bash
# Creates manual_review/ with:
# - high_confidence_variants/ (filtered, annotated VCFs)
# - copy_number_plots/ (CNV visualizations)  
# - summary_reports/ (MultiQC, summaries)
# - README.md (review workflow guide)
```
**Output**: `output/manual_review/` directory structure
**Usage**: `./bin/organize_results.sh`

#### 3. **`bin/quick_variant_check.sh`** - Rapid Inspection Tool
**Purpose**: Quick overview of variant detection across all samples
```bash
# Functions:
check_variants()  # Counts variants per VCF with bcftools
# Provides impact summaries and recommendations
```
**Output**: Console report with variant counts and recommendations  
**Usage**: `./bin/quick_variant_check.sh`

#### 4. **`bin/create_variant_dashboard.py`** - Full Dashboard Generator
**Purpose**: Complete bioinformatics research dashboard 
```python
# Advanced functions:
extract_high_impact_variants()     # HIGH/MODERATE impact extraction
create_tool_comparison_matrix()    # Cross-tool validation
generate_summary_statistics()      # Research metrics
```
**Output**: `variant_dashboard/` with analysis tables
**Status**: Requires bcftools, designed for clinical-grade analysis

#### 5. **`bin/create_research_dashboard.py`** ⭐ **MAIN RESEARCH TOOL**
**Purpose**: Research-focused analysis with relaxed filtering  
```python
# Core functions:
extract_research_variants()    # All impact levels, research-friendly
create_tool_comparison_matrix() # Cross-tool validation matrix
create_gene_summary()          # Gene-level mutation burden  
create_sample_summary()        # Sample-level statistics
```

**Key Features**:
- **Multi-tool comparison**: FreeBayes + Mutect2 integration ready
- **Impact prioritization**: HIGH > MODERATE > LOW > MODIFIER
- **Gene-centric analysis**: Groups variants by affected genes
- **Research filtering**: Balances discovery vs. precision
- **Export ready**: CSV format for R/Python/Excel analysis

**Output Files**:
```
research_dashboard/
├── sample_summary.csv           # Cross-sample variant overview
├── tool_comparison_detailed.csv # Method validation matrix
├── genes_affected.csv           # Gene-level analysis
├── high_priority_variants.csv   # Manual review targets  
├── complete_variant_catalog.csv # Full research dataset
└── RESEARCH_GUIDE.md           # Analysis workflow
```

**Proven Results**: Successfully processed 2,968 variants from full dataset:
- 465 high-priority variants (HIGH/MODERATE impact)
- ~490 variants per sample (consistent evolution)  
- 375-393 genes affected per sample
- Identified adaptation hotspots (YDR150W: 25 variants)

### **Integration Strategy for NextFlow**

#### **Proposed NextFlow Process: `VARIANT_DASHBOARD`**
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
    create_research_dashboard.py \\
        --vcf_dir . \\
        --sample_sheet ${sample_sheet} \\
        --output_dir research_dashboard/
    """
}
```

#### **Integration Points in Sarek Pipeline**
1. **After annotation**: Use annotated VCFs as input
2. **Before reporting**: Generate dashboard alongside MultiQC
3. **Output structure**: Parallel to existing `annotation/` directory

### **Bioinformatics Community Alignment**

#### **Best Practices Applied**:
✅ **Tool Comparison**: Multi-caller consensus for validation  
✅ **Impact Prioritization**: Focus on functional variants
✅ **Structured Output**: Analysis-ready CSV format
✅ **Gene-Centric View**: Biological interpretation focus  
✅ **Reproducible**: Documented methodology and filtering
✅ **Scalable**: Easy addition of new samples/tools

#### **Literature Alignment**:
- **Tenaillon et al. (2012) Science**: E. coli evolution experiments
- **Lang et al. (2013) Nature Genetics**: Yeast population analysis  
- **Good et al. (2017) Nature**: Cross-tool variant validation

### **Known Issues & Solutions**

#### **Issue: Mutect2 Missing from Dashboard**
**Observation**: FreeBayes: 492 variants, Mutect2: 0 variants detected
**Likely Causes**:
1. **Format differences**: Mutect2 uses different QUAL/FILTER structure  
2. **File paths**: Different annotation directory structure
3. **Filtering stringency**: Mutect2 more conservative by default

**Solutions**:
```python
# Add Mutect2-specific parsing:
def extract_mutect2_variants(vcf_path):
    # Use TLOD instead of QUAL for Mutect2
    # Handle different annotation structure
    # Parse tumor-normal specific fields
```

#### **Next Development Phase**:
1. **Fix Mutect2 integration** - Handle format differences
2. **Add CNV integration** - Include Control-FREEC results  
3. **Create visualizations** - Manhattan plots, heatmaps
4. **Export integration** - Direct R/Python analysis pipelines

### **Dashboard Usage Workflow**

#### **For Immediate Use**:
```bash
# 1. Generate research dashboard
source ~/miniforge3/etc/profile.d/conda.sh
conda activate nf-env
python bin/create_research_dashboard.py

# 2. Review results
open output/research_dashboard/RESEARCH_GUIDE.md
```

#### **For NextFlow Integration** (Future):
```nextflow
// Add to sarek/main.nf after annotation
VARIANT_DASHBOARD(
    annotation_vcfs,
    samplesheet
)
```

This dashboard system transforms raw VCF complexity into **publication-ready research data**, following community standards while maintaining ALE-specific biological focus.


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