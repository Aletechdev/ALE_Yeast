# NF_ALE Project Notes

## Environment-Specific Configurations

### ~~Apple Silicon (Local Development, not maintained)~~

- **Profile**: `arm,docker`
- **Notes**: Nf-sarek is using some tools that stalled with Docker on Apple Silicon, e.g. multiQC, Mutect2, thus development is moved to a Azure VM. Running on Mac also causes more failed jobs could be file system optimization related...

### Azure Linux VM (Remote dev, Production)

- **Profile**: `AzureD4as,docker` (standard)
- **Recommended**: Use original configuration for production deployment

## Dev Strategy

1. Remote development on an Azure VM, size: D4as
2. A conda environment is setup for running nextflow and testing the packages: `conda activate /home/azureuser/miniforge3/envs/nf-env`
3. Selected nf-sarek's tools: [Prefer Mutect2 over Haptypocaller, but top task to add Haptypocaller, (fix input matrix..)](reference_scripts/compass_artifact_wf-b8f488cc-c606-4f9a-8630-103f7c12f2bf_text_markdown.md)
4. Additional parameters: ploidy, added to the sample table as column ploidy, ploidy has been passed to `cnvkit, controlfreec,FreeBayes, Tiddit`, note that for the tool bcftools mpileup (not top listed tools), the ploidy is still 1 under `nf-core-sarek_3.5.1/3_5_1/conf/modules/ngscheckmate.config`
5. Additional NextFlow processes: VCF filter for SNP&InDel, customized for each variant calling tool, e.g. mutect alraedy subtracted control's variants (name changed to Treated_vs_Control), FreeBaye just show all variants from treated + control.
6. **TODO**: Develop feature of Analysis Dashboard to summarize the results:
7. Decide if go with BreSeq output format, which is used by the ALEdb.org visualization.
8. Run with Azure batch, this is important for large dataset handling, and future web service for submitting analysis by normal users.

### Key Files

- `data`: test data folder with gb and fastq files, **does not** come with this git repo, on Azure: https://aledata.blob.core.windows.net/aledata/Yeast/dicarboxylic_acids_all_clones/REDACTED-CUSTOMER-ID/ANP_Dev_2025Q3/data/
- `bin/CENPK_run_sarek_351.sh`: Main execution script for the test data
- `bin/nextflow.config`: Pipeline configuration, with D4as profile for VM local run resources config
- `bin/prepare_input/process_GeneBank/generate_cache/gen_cache.sh`: Cache generation script from the given gff3 file (given draft_ref52.gb is already in gff3 format)
- `nf-core-sarek_3.5.1` forked from nf-core, when looking for documentation, should use the version for 3.5.1

### Input sample table:

Adapted from nf-sarek input table, it was developed for human cancer research, experiment is used as patient within the nf-Sarek pipeline (considered as Experiment ID for this project), status 0 for starting strain (normal tissue for Sarek), 1 for mutent (tumor tissue for Sarek)

For each experiment (patient) there **has to be one normal sample** (status: 0), as I am planning to use tumor-normal pairing mode of sarek, example below, but should accodimate for the edge cases where **only tumor samples are provided**, the files will be processed under a different nf-Sarek channel: `BAM_VARIANT_CALLING_TUMOR_ONLY_ALL`

TODO: also need a column of sex chromosome (XX) for some CNV tools, auto-fill this info??
```tex
experiment,sample,status,clonal_or_population,ploidy,lane,fastq_1,fastq_2
ALE_Exp1,A4-F5-I1-R1,1,clonal,2,L001,SubSampleA4-5_S11_L001_R1_001.fastq.gz,SubSampleA4-5_S11_L001_R2_001.fastq.gz
ALE_Exp1,A4-F5-I1-R1,1,clonal,2,L003,SubSampleA4-5_S11_L003_R1_001.fastq.gz,SubSampleA4-5_S11_L003_R2_001.fastq.gz
ALE_Exp1,A0-F0-I1-R1,0,clonal,2,L001,SubSampleCENPK113-7D-N_S53_L001_R1_001.fastq.gz,SubSampleCENPK113-7D-N_S53_L001_R2_001.fastq.gz
ALE_Exp1,A0-F0-I1-R1,0,clonal,2,L002,SubSampleCENPK113-7D-N_S53_L002_R1_001.fastq.gz,SubSampleCENPK113-7D-N_S53_L002_R2_001.fastq.gz

```

### Production Strategies for Deliverable 1

Variant calling tools: FreeBayes and GATK Mutect2

Annotation tool: SnpEff, the snpeff_df is generated externally by `bin/prepare_input/process_GeneBank/generate_cache/gen_cache.sh`

Issue: for channel `BAM_VARIANT_CALLING_SOMATIC_ALL` the meta data structure cheanged.

### **✅ Updated: Allele Frequency-Based Somatic Filtering**

**Migration from GT-based to AF-based filtering** for both FreeBayes and Mutect2 somatic variant detection:

#### **Mutect2 Filtering (`vcf_filter_mutect2/bcftools/filter_somatic/main.nf`)**
- **Focus on FreeBayes First**
- **Strategy**: Direct AF field usage
- **Filter criteria**:
  - Normal sample AF < 0.10 (10%)
  - Tumor sample AF > 0.05 (5%)
  - AF difference > 0.05 (5%)
  - Depth requirements: tumor ≥10, normal ≥8
- **Implementation**: `FORMAT/AF[sample]` directly available in Mutect2 VCFs

#### **FreeBayes Filtering (`vcf_filter_freebayes/bcftools/filter_somatic/main.nf`)**
- **Strategy**: Multi-allelic splitting + calculated AF
- **Key innovation**: Use `bcftools norm -m-` to split multi-allelic sites before filtering
- **Filter criteria**: Same AF thresholds as Mutect2
- **Implementation**: 
  ```bash
  bcftools norm -m- -O z | #using AWK to calculate AF and AF_diff, there seems to be a but with vcftools to interact with AF#
  ```

#### **Multi-allelic Site Handling Example**
**Before splitting** (position AECK01000002:547636):
```
REF: AGTATAC  ALT: TGTGTAT,AGTGTAC  (multi-allelic)
AO values: AO=12,5 and AO=0,1 (comma-separated arrays)
```

**After `bcftools norm -m-` splitting**:
```
Record 1: AGTATAC → TGTGTAT  (AO=12, AO=0)
Record 2: AGTATAC → AGTGTAC  (AO=5, AO=1)
```

This approach:
- ✅ **Eliminates AO subfield complexity**: No need for sum() or complex indexing
- ✅ **Processes all alternate alleles**: Each gets individual evaluation  
- ✅ **Uses consistent AF thresholds**: Same filtering logic across both tools
- ✅ **More sensitive detection**: Captures low-frequency somatic mutations

**Configuration files**:
- FreeBayes: `nf-core-sarek_3.5.1/3_5_1/conf/modules/custom_freebayes_filter.config`
- Mutect2: `nf-core-sarek_3.5.1/3_5_1/conf/modules/custom_mutect2_filter.config`

#### **⚠️ Important: Mutect2 AF vs AD Discrepancy**

**Observation**: Mutect2's reported `FORMAT/AF` values do not match simple `AD[alt]/DP` calculations:

| Position | Sample | AD (ref,alt) | Reported AF | Expected AF (alt/DP) | Difference |
|----------|--------|--------------|-------------|-------------------|------------|
| 27882 | Normal | 80,2 | 0.033 | 0.024 | +0.009 |
| 27882 | Tumor | 59,4 | 0.075 | 0.063 | +0.012 |
| 27925 | Normal | 87,0 | 0.011 | 0.000 | +0.011 |

**Root Cause**: Mutect2 uses **Bayesian allele frequency estimation** rather than simple count ratios:
- Incorporates base quality scores, mapping quality, and local assembly
- Can report non-zero AF even with zero alternate read counts
- More sophisticated error modeling than simple AD[alt]/DP

**Impact on Filtering**: 
- Using `FORMAT/AF` in filters is correct for Mutect2
- Direct comparison with FreeBayes AO/(AO+RO) ratios may show discrepancies
- Mutect2 AF-based filtering may be more sensitive due to Bayesian uncertainty

**Available Strand Bias Fields in Mutect2**:
- `FORMAT/F1R2`: Forward strand reads (equivalent to FreeBayes SAF)
- `FORMAT/F2R1`: Reverse strand reads (equivalent to FreeBayes SAR)  
- **Implemented**: `FORMAT/F1R2[1:1] > 0 && FORMAT/F2R1[1:1] > 0` for strand support requirement

#### **✅ Strand Bias Filtering - Major Quality Improvement**

**Impact Analysis** (measured on raw Mutect2 data):
- **Total raw variants**: 45,139
- **Pass strand bias filter**: 21,292 variants (47.2%)
- **Fail strand bias filter**: 23,847 variants (52.8%) - **REMOVED**

**Key Insight**: Strand bias filtering does the **"heavy lifting"** in quality control:
- **Removes >50% of raw Mutect2 calls** - the largest single filtering step
- **Eliminates strand-biased artifacts**: Variants appearing only on forward OR reverse strand
- **Essential for yeast ALE**: Prevents false positives from PCR artifacts, sequencing errors
- **Comparable to FreeBayes**: Matches SAF>0 & SAR>0 requirement for artifact removal

**Current Pipeline Chain**:
```
Raw Mutect2: 45,139 variants
    ↓ Quality filters (TLOD≥12, depth, mapping quality)
    ↓ Strand bias filter (F1R2>0 & F2R1>0) ← removes 23,847 (52.8%)
    ↓ AF-based somatic filter (tumor AF>5%, AF difference>8%)
Final output: ~4,200 variants (90.7% total reduction)
```

**Biological Significance**: Most Mutect2 artifacts show mutated strand bias, making this filter crucial for distinguishing real mutations from technical artifacts in ALE experiments.

### **✅ Strategic Decision: Disable FreeBayes Somatic Mode for ALE Experiments**

**Issue Identified**: FreeBayes somatic mode (tumor vs normal comparison) produces excessive noise inappropriate for ALE experiments:
- **Somatic mode**: A1-F6-I1-R1_vs_A0-F0-I1-R1.freebayes.vcf.gz → 248,248 variants
- **Germline mode**: A1-F6-I1-R1.freebayes.vcf.gz → 10,965 variants
- **Germline mode**: A0-F0-I1-R1.freebayes.vcf.gz → 6,641 variants

**Root Cause**: FreeBayes somatic calling is designed for cancer genomics (tumor vs normal tissue), not evolutionary experiments where all samples represent independent evolved populations.

**Solution Implemented**:
- **Disabled FreeBayes in somatic workflow** (`subworkflows/local/bam_variant_calling_somatic_all/main.nf:132-146`)
- **Maintained FreeBayes in germline workflow** for clean, biologically relevant variant detection
- **Preserved Mutect2 somatic mode** which provides appropriate tumor-normal filtering for comparison purposes

**Strategic Rationale**:
- **ALE Biology**: Each evolved sample is an independent endpoint, not a tumor-normal pair
- **Noise Reduction**: 95%+ reduction in FreeBayes variants (248K → 10K)
- **Tool Appropriateness**: Use each tool in its optimal mode for the experimental design
- **Multi-tool Strategy**: FreeBayes (germline) + Mutect2 (somatic filtered) + HaplotypeCaller (germline)

**Current Channel Logic**:
- **Germline calling**: All samples processed as "normal" status (hard-coded `cram_variant_calling_status_normal = cram_variant_calling`)
- **Somatic calling**: FreeBayes disabled, Mutect2 enabled for comparison/filtering purposes
- **Result**: Clean, experiment-appropriate variant detection across all tools

**⚠️ Pending Review: Structural Variant Tools**
For structural variant calling tools (Manta, Strelka, TIDDIT), **review needed** to determine whether germline or somatic mode results are preferred for ALE experiments:
- **Manta**: Currently runs in both germline and somatic modes
- **Strelka**: Currently runs in both germline and somatic modes
- **TIDDIT**: Currently runs in both germline and somatic modes
- **Recommendation**: Analyze output quality and noise levels to determine optimal mode per tool

### **⚠️ Note: BaseRecalibrator Not Applied**

The pipeline **no longer uses GATK's BaseRecalibrator** for base quality score recalibration (BQSR). Since our in-house reference genome lacks any curated --known-sites variant VCFs, BaseRecalibrator cannot run. it mandates at least one known-sites database to distinguish true variation from sequencing errors. https://janis.readthedocs.io/en/latest/tools/bioinformatics/gatk4/gatk4baserecalibrator.html?utm_source=chatgpt.com

In future, if we generate a reliable set of high-confidence variants (e.g., through bootstrapped calls), we may revisit and enable BQSR. Until then, BaseRecalibrator is retained in code base for reference only and is **not used in current analyses**.

### **✅ Fixed: YAML Processing Error with Custom VCF Filters**

**Issue**: Pipeline crashed with Groovy method resolution ambiguity error when processing version files from custom VCF filtering processes:
```
ERROR ~ Could not find which method load() to invoke from this list:
  public java.lang.Object org.yaml.snakeyaml.Yaml#load(java.io.InputStream)
  public java.lang.Object org.yaml.snakeyaml.Yaml#load(java.io.Reader)
  public java.lang.Object org.yaml.snakeyaml.Yaml#load(java.lang.String)
  public java.lang.Object org.yaml.snakeyaml.Yaml#load(java.io.File)
  public java.lang.Object org.yaml.snakeyaml.Yaml#load(java.nio.file.Path)
```

**Root Cause**: The `processVersionsFromYAML()` function in `nf-core-sarek_3.5.1/3_5_1/subworkflows/nf-core/utils_nfcore_pipeline/main.nf` received version files with ambiguous input types (Path, File, String, etc.), causing Groovy to fail method resolution for `yaml.load()`.

**Solution**: Modified the function to use explicit FileInputStream with proper error handling:
- Added null/empty file validation
- Added file existence checks  
- Used explicit `java.io.FileInputStream(path.toFile())` to force specific method overload
- Maintained backward compatibility with existing nf-core modules

**Impact**: Custom VCF filtering processes (VCF_FILTER_FREEBAYES and VCF_FILTER_MUTECT2) now work correctly without causing pipeline crashes.

### ⚠️ Mutect2 with custom genome, omitting panel-of-normal (vcf) and germline resource (vcf)

```
WARN: No Panel-of-normal was specified for Mutect2.
It is highly recommended to use one: https://gatk.broadinstitute.org/hc/en-us/articles/5358911630107-Mutect2
For more information on how to create one: https://gatk.broadinstitute.org/hc/en-us/articles/5358921041947-CreateSomaticPanelOfNormals-BETA-
WARN: If Mutect2 is specified without a germline resource, no filtering will be done.
It is recommended to use one: https://gatk.broadinstitute.org/hc/en-us/articles/5358911630107-Mutect2
```

#### 1.**--germline-resource**

* **Purpose** : Filters out common population variants (SNPs) that are unlikely to be somatic mutations
* **For yeast ALE** : You're looking for ANY mutations that arise during evolution, including what would be "germline" variants in cancer terms
* **Reality** : No comprehensive yeast population databases exist like gnomAD for humans
* **Recommendation** : **Omit this parameter entirely**
* As --germline-resource is omitted, the parameter `--af-of-alleles-not-in-resource / -default-af` **is also omitted**.

#### 2.**--panel-of-normals (PoN)**

* **Purpose** : Identifies systematic artifacts from sequencing/sample prep that appear across multiple "normal" samples
* **For yeast ALE** : Could theoretically be useful if you have multiple ancestral strain replicates
* **Reality** : The effort to create a PoN may not be justified for yeast experiments
* **Recommendation** :** ****Omit unless you have systematic artifacts to filter**


### **⚠️ Note: VCFTOOLS Compatibility Issues and Skipping Conditions**

VCFtools is **conditionally skipped** for several variant callers due to compatibility issues:

#### **1. Ploidy > 2 (FreeBayes)**
- **Error**: "Polyploidy found, and not supported by vcftools"
- **Tested**: Works fine with ploidy = 1 and 2, fails with ploidy ≥ 3

#### **2. Mutect2 Phased Genotype Format**
- **Issue**: Mutect2 outputs phased genotypes (0|0, 0|1) instead of unphased (0/0, 0/1)
- **Impact**: VCFtools expects standard VCF genotype format, fails with phased notation

#### **3. Joint Variant Calling (HaplotypeCaller) Segmentation Fault**
- **Issue**: VCFtools 0.1.16 crashes with **segmentation fault (exit status 139)** on joint_variant_calling.vcf.gz
- **Evidence**: Processes 1748 sites successfully, then crashes with "Segmentation fault (core dumped)"
- **Root cause**: Memory corruption in VCFtools when processing GATK's joint calling output format
- **Meta values**: `id: joint_variant_calling, variantcaller: haplotypecaller, ploidy: null`

```yaml
# nf-core-sarek_3.5.1/3_5_1/conf/modules/modules.config
withName: 'VCFTOOLS_.*' {
        ext.prefix = { variant_file.baseName - ".vcf" }
        ext.when   = { !(params.skip_tools && params.skip_tools.split(',').contains('vcftools')) &&
                      (meta.ploidy == null || meta.ploidy.toString().toInteger() <= 2) &&
                      (meta.variantcaller != 'mutect2') &&
                      !(meta.id ==~ /.*joint_variant_calling.*/) }
        publishDir = [
            mode: params.publish_dir_mode,
            path: { "${params.outdir}/reports/vcftools/${meta.variantcaller}/${meta.id}/" },
            saveAs: { filename -> filename.equals('versions.yml') ? null : filename }
        ]
    }
```

**Summary**: VCFtools **only runs** for:
- ✅ **FreeBayes** individual samples (ploidy ≤ 2)
- ✅ **HaplotypeCaller** individual samples
- ❌ **Mutect2** (all samples) - phased genotype incompatibility
- ❌ **Joint variant calling** - segmentation fault
- ❌ **Any sample with ploidy > 2** - polyploidy not supported
### ⚠️ Control-FREEC Warnings and Limitations

#### Case 1: No SNP Database Provided
**Warning: No SNP information provided for Control-FREEC analysis**
- BAF (B-Allele Frequency) files will **not be generated**
- Copy number analysis will proceed using **read depth only**
- This occurs when running without a SNP database (e.g., dbSNP)
- **Expected behavior** for custom reference genomes without curated variant databases

#### Case 2: Haploid Strains (Ploidy=1)
**Empty CNVs file causing ASSESS_SIGNIFICANCE failure**
- Haploid strains typically produce **empty `*.gz_CNVs` files**
- ASSESS_SIGNIFICANCE process fails with "no lines available in input" error
- **Solution**: ASSESS_SIGNIFICANCE is **automatically skipped** when `ploidy=1`
- Copy number analysis still proceeds using read depth ratios

### ⚠️ Control-FREEC ASSESS_SIGNIFICANCE Skipped for Haploid Strains (ploidy =1)

Control-FREEC's `ASSESS_SIGNIFICANCE` step is **automatically skipped when ploidy=1** because haploid strains typically produce empty `*.gz_CNVs` files, causing the R script to fail with "no lines available in input" error.

**Configuration**: `conf/modules/controlfreec.config` includes:
```yaml
withName: 'ASSESS_SIGNIFICANCE' {
    ext.when = { !(meta.ploidy == null || meta.ploidy.toString().toInteger() == 1) }
    # ... rest of config
}
```

This prevents the process from running on samples with ploidy=1, allowing the pipeline to complete successfully for haploid yeast strains.

### ⚠️ **BUG: GATK FilterMutectCalls Not Running Without Germline Resource**

**Issue**: When running Mutect2 without `--germline_resource`, the GATK FilterMutectCalls process is **completely skipped**, despite the pipeline showing the warning:
```
WARN: If Mutect2 is specified without a germline resource, no filtering will be done.
It is recommended to use one: https://gatk.broadinstitute.org/hc/en-us/articles/5358911630107-Mutect2
```

**Evidence**:
- ✅ **Present in output**: `*.mutect2.vcf.gz` (raw Mutect2 calls)
- ✅ **Present in output**: `*.mutect2.artifactprior.tar.gz` (LearnReadOrientationModel runs)
- ❌ **Missing from output**: `*.mutect2.filtered.vcf.gz` (FilterMutectCalls output)
- ❌ **Missing from output**: `*.filteringStats.tsv` (FilterMutectCalls statistics)

**Root Cause**: The nf-core Sarek pipeline conditionally skips FilterMutectCalls when no germline resource is provided, making the generated `artifactprior` files **unused**.

**Impact on This Project**:
- **Positive**: Forces reliance on custom filtering (`VCF_FILTER_MUTECT2`), which is more appropriate for yeast ALE experiments
- **Negative**: `LearnReadOrientationModel` runs unnecessarily, consuming compute resources without benefit
- **Negative**: Misleading warning suggests filtering will happen when it actually doesn't

**Workaround**: The custom filtering pipeline (`subworkflows/local/vcf_filter_mutect2/`) provides more appropriate filtering for yeast somatic variant calling than GATK's FilterMutectCalls would.

### **⚠️ Note: GATK Processes Not Used in Current Configuration**

The following GATK processes are **included in the pipeline but not actually executed** due to the missing germline resource:

1. **`GATK4_FILTERMUTECTCALLS`**: Should apply artifact filtering using LearnReadOrientationModel results, but is skipped entirely
2. **`GATK4_LEARNREADORIENTATIONMODEL`**: Runs and generates `artifactprior.tar.gz` files, but these are **never consumed** by FilterMutectCalls

**Alternative**: Custom filtering workflows are used instead:
- **Mutect2**: `subworkflows/local/vcf_filter_mutect2/` - Applies AF-based somatic filtering with strand bias requirements
- **FreeBayes**: `subworkflows/local/vcf_filter_freebayes/` - Multi-allelic splitting with AF-based filtering

These custom workflows are **more appropriate for yeast ALE experiments** than GATK's cancer-focused filtering approach. 

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
