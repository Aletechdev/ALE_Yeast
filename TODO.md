# NF_ALE Project TODO List

## 🚀 v0.1.0-alpha Release Preparation

### Pre-Release Cleanup Tasks
- [x] Review and clean up uncommitted files (Doc/, tunnel) - Renamed Doc/ → quality_control/
- [x] Remove or gitignore temporary files and outputs - Updated .gitignore for QC files
- [ ] Verify bin/ scripts are properly organized
- [ ] Check for sensitive data or credentials in repo
- [x] Review and update .gitignore if needed - Added quality_control/ patterns

### Documentation Tasks
- [ ] Create minimal README.md for alpha release
- [ ] Create CHANGELOG.md for v0.1.0-alpha
- [ ] Add LICENSE file

### Release Tasks
- [x] Commit cleanup and documentation changes - quality_control/ committed
- [ ] Create git tag v0.1.0-alpha
- [ ] Push tag and create GitHub release

---

## Current Tasks

### split haplotypecaller vcf, add annotation

---

### ⭐ Rename Mutect2 Filtered VCF to Match HaplotypeCaller Naming Convention

**Priority**: MEDIUM - Consistency and clarity improvement

**Current Naming**:
```bash
# HaplotypeCaller (joint germline):
joint_germline.vcf.gz                     # Unfiltered
HaplotypeCaller_joint_calling_soft_filtered.vcf.gz    # Soft-filtered (FILTER column annotated)

# Mutect2 (joint somatic):
ALE_Exp1.mutect2.vcf.gz                   # Unfiltered
ALE_Exp1.mutect2.filtered.vcf.gz          # Soft-filtered (FILTER column annotated)
```

**Problem**: Inconsistent naming pattern
- HaplotypeCaller: `HaplotypeCaller_joint_calling_soft_filtered` (descriptive)
- Mutect2: `ALE_Exp1.mutect2.filtered` (less clear that it's soft filtering)

**Proposed Naming** (for consistency):
```bash
# Option A: Match HaplotypeCaller style
ALE_Exp1.mutect2.vcf.gz                        # Unfiltered
ALE_Exp1.mutect2.filter_annotated.vcf.gz       # Soft-filtered (FILTER annotated)

# Option B: More explicit about soft filtering
ALE_Exp1.mutect2.vcf.gz                        # Unfiltered
ALE_Exp1.mutect2.soft_filtered.vcf.gz          # Soft-filtered (keeps all variants)

# Option C: Keep joint_ prefix for consistency
ALE_Exp1.joint_somatic.vcf.gz                  # Unfiltered
ALE_Exp1.joint_somatic_filter_annotated.vcf.gz # Soft-filtered
```

**Recommendation**: **Option A** - `filter_annotated` suffix
- Matches HaplotypeCaller naming
- Clear that FILTER column is annotated (not removed)
- Consistent across germline and somatic workflows

**Implementation**:
- **Location**: `nf-core-sarek_3.5.1/3_5_1/conf/modules/mutect2.config:48`
- **Current**: `ext.prefix = {"${meta.id}.mutect2.filtered"}`
- **Change to**: `ext.prefix = {"${meta.id}.mutect2.filter_annotated"}`

**HaplotypeCaller Naming Logic** (verified):
- **Location**: `conf/modules/joint_germline.config:102`
- **Config**: `ext.prefix = { 'HaplotypeCaller_joint_calling_soft_filtered' }`
- **Process**: `VARIANTFILTRATION_FALLBACK` (line 87)
- Naming is set via config, not hardcoded

**Implementation Details**:
1. **Mutect2 config**: Change line 48 in `conf/modules/mutect2.config`
   ```groovy
   # Current:
   ext.prefix = {"${meta.id}.mutect2.filtered"}

   # Change to:
   ext.prefix = {"${meta.id}.mutect2.filter_annotated"}
   ```

2. **Process name**: `FILTERMUTECTCALLS.*` (matches pattern in config)

**Files to Modify**:
1. ✅ `conf/modules/mutect2.config:48` - Change prefix
2. ⏳ Update CLAUDE.md documentation if referencing old filename
3. ⏳ Check if any custom scripts reference `.filtered.vcf.gz` pattern

**Testing**: After rename, verify:
1. ✅ File published with new name
2. ✅ No downstream processes break (annotation, QC)
3. ✅ MultiQC still recognizes the file
4. ✅ Documentation updated

---

### filter population VCFs from mutect2 and haplotypcaller: /home/azureuser/Docs/ALE_nextflow/bin/compare_mutect2_HpCaller/CENPK_all/paper_a_benchmark/README.md

### freebayes filter AF calculation (maybe no more AF based filter??)
==> prioritize improving freebayes germline filter first, somatic mode disabled for now
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

### ⭐ Implement Joint FreeBayes Population Calling, 

**Goal**: Create elegant joint FreeBayes calling following HaplotypeCaller's pattern (line 142 in `bam_variant_calling_germline_all/main.nf`)

**Current Issue**: FreeBayes only produces individual sample VCFs under germline mode, requiring post-processing to merge into population VCF for ALE analysis. adjust: first filter individual germline mode output, then merge

**Proposed Implementation**:
```groovy
if (joint_freebayes) {
    BAM_JOINT_CALLING_FREEBAYES(
        BAM_VARIANT_CALLING_FREEBAYES.out.vcf_all_samples, // Collect all individual VCFs
        fasta,
        fasta_fai,
        dict
    )
    vcf_freebayes_joint = BAM_JOINT_CALLING_FREEBAYES.out.joint_vcf
}
```

**Implementation Tasks**:
1. **Add parameter**: `params.joint_freebayes` to nextflow config
2. **Create subworkflow**: `subworkflows/local/bam_joint_calling_freebayes/main.nf`
3. **Use bcftools merge**: Combine individual FreeBayes VCFs into population VCF
4. **Channel logic**: Similar to HaplotypeCaller's `gvcf_tbi_intervals` collection
5. **Update main workflow**: Add conditional joint calling logic in `bam_variant_calling_germline_all/main.nf`

**Benefits**:
- **Consistent API**: Same pattern as HaplotypeCaller joint calling
- **Parameter-controlled**: `--joint_freebayes` flag for user control
- **Population genetics**: Proper allele frequency calculations across all samples
- **ALE-appropriate**: Single population VCF showing evolutionary trajectories
- **nf-core compliant**: Follows established pipeline patterns

**Priority**: Medium - Provides elegant solution for population analysis without post-processing

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

### ⚠️ BUG: Triple-Layer Misleading Error Messages in Pipeline Validation

**Severity**: CRITICAL - Can waste hours of debugging time

**Locations**:
- Console error: `/nf-core-sarek_3.5.1/3_5_1/subworkflows/local/samplesheet_to_channel/main.nf:146-167`
- Schema validation: nf-validation plugin (`assets/schema_input.json`)
- Actual error: Various locations depending on real issue

#### **The Triple-Layer Problem**

**Layer 1 (What user sees in console)**: ❌ **COMPLETELY WRONG**
```
"The sample-sheet only contains normal-samples, but the following tools expect
at least one tumor-sample: controlfreec, mutect2, msisensorpro"
```
- **Reality**: Samplesheet has BOTH normal and tumor samples with correct status values
- **Why shown**: `input_sample.filter{...}.ifEmpty{}` triggers when channel is empty due to upstream errors

**Layer 2 (What `.nextflow.log` shows)**: ⚠️ **MISLEADING**
```
SchemaValidationException: the file or directory
'../data/data_a_paper/A1-6_S2_L001_R1_001.fastq.gz' does not exist
```
- **Reality**: File DOES exist at that exact path (verified with `ls ../data/data_a_paper/A1-6_S2_L001_R1_001.fastq.gz`)
- **Why shown**: nf-validation plugin checks file existence relative to **different context** than where it exists

**Layer 3 (Actual root cause)**: ✅ **REAL ISSUE**
- nf-validation plugin validates file paths relative to **samplesheet's parent directory** or **projectDir**
- Samplesheet had paths as `../data/data_a_paper/file.fastq.gz` (relative to bin/ directory)
- But validation checks from a different location, so "relative" means something different
- **Solution**: Use absolute paths or paths relative to samplesheet location

#### **Impact - Real Debugging Session (Oct 8, 2025)**

**Time wasted**: 30+ minutes debugging wrong issues
1. First checked if samplesheet had tumor/normal samples → ✅ It did
2. Then checked if files existed → ✅ They did
3. Then checked file permissions → ✅ Fine
4. Then checked `.nextflow.log` → Found "file does not exist" error
5. Then manually verified file exists → ✅ It does!
6. Finally realized: **path resolution context mismatch** in nf-validation

#### **Other Examples of This Bug**

**Example 2**: SPLIT_JOINT_VCF Process Input Mismatch
- **Console shows**: "sample-sheet only contains tumor-samples, but tools expect normal-sample"
- **Log shows**: `Process BCFTOOLS_VIEW declares 4 input channels but 1 were specified`
- **Real issue**: Process definition error in workflow code (nothing to do with samplesheet!)

**Example 3**: Config Syntax Error (from earlier notes)
- **Console shows**: "sample-sheet only contains normal-samples"
- **Real issue**: Missing comma in `custom_freebayes_filter.config`

#### **Root Cause Technical Details**

The `input_sample` channel fails to populate when ANY upstream error occurs:
1. nf-validation plugin runs first (validates samplesheet schema)
2. If it throws exception → channel never gets data
3. Workflow code tries to filter samples: `input_sample.filter{status==1}.ifEmpty{error(...)}`
4. Empty channel triggers `.ifEmpty{}` block → misleading tumor/normal error
5. Original validation error is only in `.nextflow.log`, not shown to user

**Why This Happens**:
- No proper exception handling between validation plugin and workflow logic
- Error messages don't propagate correctly through Nextflow channels
- Workflow assumes empty channel = wrong sample status (incorrect assumption)

#### **How to Find the REAL Bug When You See This Error** 🔍

**IMPORTANT**: If you see "sample-sheet only contains normal-samples" or "tumor-samples" error, **DO NOT trust it**. Follow these steps:

**Step 1: Check `.nextflow.log` file** (most recent run)
```bash
tail -200 .nextflow.log | grep -A 5 -B 5 "Exception\|ERROR"
```
Look for the FIRST exception/error, not the tumor/normal error.

**Step 2: Common Real Errors to Look For**

| Log Error Message | Real Cause | Solution |
|-------------------|------------|----------|
| `SchemaValidationException: file or directory '...' does not exist` | File paths in samplesheet are relative but checked from wrong directory | Use **absolute paths** in samplesheet |
| `Process XXX declares N input channels but M were specified` | Process invocation error in workflow code | Fix process call to match input signature |
| `No such variable: XXX` or `Unknown method: XXX` | Config syntax error or missing import | Check recent config file changes |
| `Missing or unknown field in csv file header` | Actual samplesheet format error | Fix samplesheet column names |

**Step 3: If Log Shows "file does not exist" but File EXISTS**
- Check if paths are absolute vs relative
- Test file path from **samplesheet's directory**: `cd data/data_a_paper && ls file.fastq.gz`
- **Solution**: Convert all paths to absolute in samplesheet

**Step 4: Verify Samplesheet is Actually Valid**
```bash
# Check for both tumor and normal samples
grep ",0," samplesheet.csv  # Should show normal samples (status=0)
grep ",1," samplesheet.csv  # Should show tumor samples (status=1)
```

**Step 5: Test Without Recently Added Features**
If you recently added a new workflow/feature (e.g., `--split_haplotypecaller_joint_vcf`), try disabling it to isolate the issue.

#### **Quick Diagnostic Commands**
```bash
# 1. Check what error really happened
tail -200 .nextflow.log | grep -E "Exception|ERROR" | head -20

# 2. Verify samplesheet has tumor/normal samples
awk -F, 'NR>1 {print $3}' samplesheet.csv | sort | uniq -c

# 3. Check if files exist (run from project root)
head -5 samplesheet.csv | tail -4 | awk -F, '{print $8}' | xargs ls -lh

# 4. Find the actual error location
grep -n "error\|Error\|ERROR" .nextflow.log | tail -10
```

#### **Solution needed**:
Improve exception handling to only show sample sheet errors for actual sample sheet validation issues, not for upstream configuration problems.

**Proposed Solutions**:

#### **Option 1: Add Specific Exception Handling**
Wrap sample validation logic in more specific try-catch blocks that distinguish between sample sheet issues and configuration errors:
```groovy
try {
    // Sample validation logic
} catch (Exception e) {
    if (e.message.contains('status') || e.message.contains('sample')) {
        error('Sample sheet validation failed: ' + e.message)
    } else {
        throw e  // Re-throw for proper debugging
    }
}
```

#### **Option 2: Earlier Configuration Validation**
Move configuration syntax validation **before** sample sheet validation to catch config errors early:
```groovy
if (tools && tools.contains(',')) {
    try {
        tools.split(',').each{ tool -> /* validate */ }
    } catch (Exception e) {
        error("Configuration syntax error in --tools parameter: ${e.message}")
    }
}
```

#### **Option 3: Better Error Context (Recommended)**
Improve error messages to provide debugging context:
```groovy
try {
    // Sample validation logic
} catch (Exception e) {
    def contextualError = """
    Pipeline configuration error detected during sample sheet validation.
    This may indicate:
    1. Syntax error in configuration files (check .config files)
    2. Invalid --tools parameter format
    3. Missing function references
    4. Actual sample sheet validation issue

    Original error: ${e.message}
    """
    error(contextualError)
}
```

**Recommendation**: Implement Option 3 for better user experience without major refactoring.

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

---

## Completed Tasks

### ✅ GATK FilterMutectCalls Channel Join Issue Fixed

**Git Commit**: 8319ef9 - "fix GATK FilterMutectCalls without Germline Resource nor Panel of Normals"

**Problem Solved**: GATK FilterMutectCalls was completely skipped when running Mutect2 without germline resources due to channel join failure with empty contamination tables.

**Solution Implemented**: Provided placeholder contamination tables with proper metadata handling:
```nextflow
if (!(germline_resource && germline_resource_tbi)) {
    // No germline resource provided - create placeholder channels for FilterMutectCalls
    if (joint_mutect2) {
        calculatecontamination_out_seg = vcf.map{ meta, vcf -> [ meta + [id: meta.patient], [] ] }
        calculatecontamination_out_cont = vcf.map{ meta, vcf -> [ meta + [id: meta.patient], [] ] }
    } else {
        calculatecontamination_out_seg = vcf.map{ meta, vcf -> [ meta, [] ] }
        calculatecontamination_out_cont = vcf.map{ meta, vcf -> [ meta, [] ] }
    }
}
```

**Impact**: FilterMutectCalls now runs successfully without germline resources, applying artifact filtering and quality control appropriate for custom yeast genomes.

### ✅ Variant Calling Mode Strategy for ALE Experiments

**Summary**: Hard-coded `cram_variant_calling_status_normal = cram_variant_calling` approach confirmed as optimal. FreeBayes somatic mode disabled due to 95%+ noise (248K→10K variants). Strategy documented in CLAUDE.md.

### ✅ YAML load() method ambiguity error - Groovy method resolution issue

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

### ✅ FilterMutectCalls Behavior Investigation - Soft vs Hard Filtering

**Date Completed**: October 15, 2025

**Question Answered**: Does FilterMutectCalls remove variants (hard filter) or just annotate FILTER column (soft filter)?

**Answer**: ✅ **Confirmed SOFT FILTERING** - FilterMutectCalls annotates the FILTER column but retains ALL variants.

**Dataset Analyzed**: `output_all/variant_calling/mutect2/ALE_Exp1/`

**Key Findings**:
- **Unfiltered VCF**: 5,798 variants (FILTER = "." for all)
- **Filtered VCF**: 5,798 variants (FILTER = various values)
- **Verdict**: NO variants removed, only FILTER column annotation changed

**Filter Pass Rate**: 2.10% (122 PASS / 5,676 failed)

**Top Filter Reasons** (individual flags, not combinations):
1. `normal_artifact`: 3,747 occurrences (64.6% of failed variants)
2. `clustered_events`: 2,618 occurrences
3. `strand_bias`: 2,594 occurrences
4. `slippage`: 2,245 occurrences
5. `base_qual`: 2,022 occurrences

**Most Common Filter Combinations**:
- `multiallelic;normal_artifact;slippage`: 1,081 variants
- `normal_artifact;slippage`: 564 variants
- `base_qual;clustered_events;normal_artifact;orientation;strand_bias`: 454 variants

**GATK FilterMutectCalls Command Used**:
```bash
gatk FilterMutectCalls \
    --variant ALE_Exp1.mutect2.vcf.gz \
    --output ALE_Exp1.mutect2.filtered.vcf.gz \
    --reference draft_ref52.fasta \
    --orientation-bias-artifact-priors ALE_Exp1.mutect2.artifactprior.tar.gz
```
- No `--exclude-filtered` flag → Soft filtering (GATK default behavior)
- Uses artifact priors from LearnReadOrientationModel
- No germline resource or panel of normals (expected for custom yeast genome)

**Filtering Statistics** (from `filteringStats.tsv`):
- Overall FDR threshold: 0.049 (4.9%)
- Overall sensitivity: 0.918 (91.8%)
- Posterior probability threshold: 0.5

**Implications**:
1. ✅ **Behavior matches HaplotypeCaller** - Both use soft filtering with FILTER column annotation
2. ✅ **Pipeline already annotates filtered VCF** - FILTER info preserved in annotations
3. ✅ **Can extract PASS-only variants downstream** - Use `bcftools view -f PASS` when needed
4. ✅ **Two parallel filtering strategies available**:
   - GATK FilterMutectCalls → Technical artifact removal (122 PASS variants)
   - Custom AF filtering (VCF_FILTER_MUTECT2) → Biological variant discovery (likely ~thousands)
5. ✅ **Layered QC approach recommended** - Use both GATK and custom filters for comprehensive analysis

**Items Deferred** (not critical for current workflow):
- Investigating why 2.10% PASS rate (may be appropriate stringency for yeast ALE)
- Comparing GATK PASS variants vs Custom AF-filtered variants
- Optimizing FilterMutectCalls parameters for ALE experiments

**Documentation Updated**: CLAUDE.md FilterMutectCalls section reflects soft filtering behavior
