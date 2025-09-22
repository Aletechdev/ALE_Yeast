# NF_ALE Project TODO List

## Current Tasks

### ✅ RESOLVED: Keep hard-coded cram_variant_calling_status_normal for ALE experiments

**Decision**: Maintain current hard-coded implementation (`cram_variant_calling_status_normal = cram_variant_calling`) at lines 685 and 690.

**Rationale**: Analysis shows this approach is optimal for ALE experiments:
- **FreeBayes**: Eliminates 95%+ noise from inappropriate somatic mode (248K → 10K variants)
- **HaplotypeCaller**: All samples available for germline calling as intended
- **ALE-appropriate**: Treats evolved samples as independent populations, not tumor vs normal
- **Proven effective**: Current implementation produces clean, biologically relevant results

**Previous Goal**: ~~Implement dynamic logic so that HaplotypeCaller runs on all samples as "normal" status~~
**New Status**: Hard-coded solution is the correct approach for this use case.

**Analysis Summary**:
FreeBayes somatic mode comparison showed dramatic noise increase:
- Somatic mode (A1-F6-I1-R1_vs_A0-F0-I1-R1): 248,248 variants
- Normal mode (A1-F6-I1-R1): 10,965 variants
- Normal mode (A0-F0-I1-R1): 6,641 variants

**Current Implementation** (Lines 685, 690):
```groovy
cram_variant_calling_status_normal = cram_variant_calling
```

This hard-coded approach correctly:
1. **Disables FreeBayes somatic mode** - prevents 95%+ noise from inappropriate tumor/normal comparisons
2. **Enables HaplotypeCaller germline calling** - all samples treated as normal for germline variant detection
3. **Maintains Mutect2 functionality** - still processes tumor-normal pairs appropriately
4. **Aligns with ALE biology** - treats evolved samples as independent populations rather than tumor vs normal

### freebayes filter AF calculation
there is a bug with how freebayes AF is calculated for the multi allelic site, since the AO are split into multiple rows, the AO+RO denominator is not right... ==> a solution could be do the AF=sum(AO)/(sum(AO)+RO) first, then split the multi-allelic variants.

### haplotypecaller joint-report, sill run the cnn filter?
something like: NFCORE_SAREK:SAREK:BAM_VARIANT_CALLING_GERMLINE_ALL:VCF_VARIANT_FILTERING_GATK:CNNSCOREVARIANTS

### how about setting all sample to status 1 (or a dedicate channel?), and run haplotypcaller
### also interested to see, how to report all samples' freebayes output into one VCF?
### with mutect and -joint_mutect2, a experiment VCF is generated, if can enable filtFilterMutectCallser (bug?) it would be great??

### add a new column to sample table, call starting strain?
also test if the starting strin name A0F0I1R1 can be named to multiple samples but different experiment
### cram_variant_calling_status_normal, from quick fix to smarter fix, 
under /home/azureuser/Docs/ALE_nextflow/nf-core-sarek_3.5.1/3_5_1/workflows/sarek/main.nf
### FreeBayes: generate population table?

### for the hpcaller joint germline, filter strategy, and how to flag fixed, convergent mutations.
### ✅ RESOLVED: YAML load() method ambiguity error - Groovy method resolution issue

**Root Cause**: Groovy method resolution ambiguity (not Java version issue - Nextflow officially supports Java up to 24)

- Environment: Nextflow 25.04.6 + Java 23.0.2 (within supported range)
- Issue: `yaml_file` parameter has ambiguous type (could be Path, File, String, etc.), causing Groovy to fail method resolution
- Trigger: Custom VCF filtering processes producing version files with different input types than expected
- Location: `/nf-core-sarek_3.5.1/3_5_1/subworkflows/nf-core/utils_nfcore_pipeline/main.nf:113`

**Solution Implemented**: Used explicit FileInputStream approach with proper error handling:

```groovy
def processVersionsFromYAML(yaml_file) {
    // Handle null or empty files
    if (!yaml_file || yaml_file.toString().isEmpty() || yaml_file.toString() == "[]") {
        return ""
    }
  
    def yaml = new org.yaml.snakeyaml.Yaml()
    def path = yaml_file instanceof java.nio.file.Path ? yaml_file : java.nio.file.Paths.get(yaml_file.toString())
  
    // Check if file exists before trying to read it
    if (!java.nio.file.Files.exists(path)) {
        return ""
    }
  
    def versions = yaml.load(new java.io.FileInputStream(path.toFile())).collectEntries { k, v -> [k.tokenize(':')[-1], v] }
    // ... rest of function
}
```

**Status**: ✅ Fixed - Forces specific `yaml.load(InputStream)` method, eliminates ambiguity

### ⭐ Integrate Variant Analysis Dashboard as NextFlow Process

**Status**: Research dashboard system developed and tested successfully
**Current implementation**: Standalone Python scripts in `bin/` folder
**Goal**: Convert to NextFlow process for automated dashboard generation

**Key Components Developed**:

- ✅ `bin/create_research_dashboard.py` - Main research tool (tested with 2,968 variants)
- ✅ `bin/summarize_variants.py` - Quick variant overview
- ✅ `bin/organize_results.sh` - Manual review structure
- ✅ Analysis-ready CSV outputs (sample_summary, gene_analysis, priority_variants)

**Integration Tasks**:

1. **Fix Mutect2 parsing**: Handle different VCF format (TLOD vs QUAL scores)
2. **Create NextFlow process**: `VARIANT_DASHBOARD` with proper input/output channels
3. **Add to main workflow**: Integration point after annotation, before reporting
4. **CNV integration**: Include Control-FREEC results in dashboard
5. **Documentation**: Update parameter documentation for dashboard options

**Expected Output**:

- `research_dashboard/` directory with analysis tables
- Cross-sample variant comparison matrices
- Gene-level mutation burden analysis
- Publication-ready CSV exports

**Priority**: High - Transforms raw VCFs into research-ready data following community best practices

### ⚠️ BUG: Misleading error message in samplesheet validation

**Location**: `/nf-core-sarek_3.5.1/3_5_1/subworkflows/local/samplesheet_to_channel/main.nf:166`
**Issue**: The error message "sample-sheet only contains tumor-samples, but the following tools expect at least one normal-sample" is incorrectly triggered when there are other unrelated errors (e.g., Nextflow function reference errors, syntax issues).

**Root Cause**: Exception handling logic that doesn't distinguish between actual sample sheet validation failures and upstream configuration/syntax errors.

**Impact**: Misleading debugging - users waste time checking sample sheets when the real issue is elsewhere (e.g., config syntax errors, missing functions).

**Example**: When `custom_freebayes_filter.config` had missing comma syntax error, this tumor/normal error was shown instead of the actual syntax error.

**Solution needed**: Improve exception handling to only show sample sheet errors for actual sample sheet validation issues, not for upstream configuration problems.

### change mutect2 calling parameters for yeast genomes:

with yeast genome, there is no mutation resources, As --germline-resource is omitted, the parameter 
--af-of-alleles-not-in-resource: Set this based on your expected mutation rate (default 5e-8 is reasonable for most microbes): For other organisms, change --af-of-alleles-not-in-resource to 1/(ploidy*samples in resource). https://gatk.broadinstitute.org/hc/en-us/articles/360037593851-Mutect2 
--initial-tumor-lod: Lower this (e.g., to 0.5-1.0) if you want to detect very low-frequency variants early in evolution
--max-population-af: Set to 1.0 to allow any allele frequency (important for evolution experiments)
--downsampling-stride: Consider disabling downsampling (set to 1) for smaller yeast genomes

### update controlfreec parameters, e.g., window for yeast

### ⭐ More Stringent Mutect2 Filtering Options (not high priority, since we decide to keep more muts, rank for top, and look for fixed & convergent mutations)

**Current Status**: Mutect2 produces 30% more variants than FreeBayes (11,060 vs 8,488), suggesting need for more stringent filtering.

**Analysis Results**:
- 7,220 variants have low TLOD scores (6-15)
- 2,861 variants have small AF differences (0.05-0.1) 
- 2,801 variants have normal depth < 15
- 1,051 variants have tumor depth < 15
