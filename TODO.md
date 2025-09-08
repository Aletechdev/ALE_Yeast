# NF_ALE Project TODO List

## Current Tasks

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

with yeast genome, there is no mutation resources, As --germline-resource is omitted, the parameter `--af-of-alleles-not-in-resource / -default-af` **is also omitted**.
Key parameters to focus on instead:
--af-of-alleles-not-in-resource: Set this based on your expected mutation rate (default 5e-8 is reasonable for most microbes)
--initial-tumor-lod: Lower this (e.g., to 0.5-1.0) if you want to detect very low-frequency variants early in evolution
--max-population-af: Set to 1.0 to allow any allele frequency (important for evolution experiments)
--downsampling-stride: Consider disabling downsampling (set to 1) for smaller yeast genomes

### update controlfreec parameters, e.g., window for yeast

### ⭐ More Stringent Mutect2 Filtering Options

**Current Status**: Mutect2 produces 30% more variants than FreeBayes (11,060 vs 8,488), suggesting need for more stringent filtering.

**Analysis Results**:
- 7,220 variants have low TLOD scores (6-15)
- 2,861 variants have small AF differences (0.05-0.1) 
- 2,801 variants have normal depth < 15
- 1,051 variants have tumor depth < 15

**Proposed Filter Options**:

#### **Option 1: Conservative (Match FreeBayes Stringency)**
```bash
# Quality: TLOD ≥ 15 (vs current ≥ 6)
# Depth: Normal ≥ 15, Tumor ≥ 20 (vs current ≥ 8/10)
# AF difference: > 0.10 (vs current > 0.05)

--include "INFO/TLOD >= 15 && FORMAT/DP[normal] >= 15 && FORMAT/DP[tumor] >= 20"
# AWK filter: min_diff = 0.10
```
**Expected**: ~8,500 variants (similar to FreeBayes TODO: give the correct matching sample, I gave the normal/control sample by mistake...)

#### **Option 2: Moderate (Balanced) - RECOMMENDED**
```bash
# Quality: TLOD ≥ 12 
# Depth: Normal ≥ 12, Tumor ≥ 15
# AF difference: > 0.08

--include "INFO/TLOD >= 12 && FORMAT/DP[normal] >= 12 && FORMAT/DP[tumor] >= 15"  
# AWK filter: min_diff = 0.08
```
**Expected**: ~9,500 variants (moderate reduction)

#### **Option 3: High-Confidence Only**
```bash
# Quality: TLOD ≥ 20
# Depth: Normal ≥ 20, Tumor ≥ 25  
# Normal AF: ≤ 0.05 (reduce germline contamination)
# AF difference: > 0.15

--include "INFO/TLOD >= 20 && FORMAT/DP[normal] >= 20 && FORMAT/DP[tumor] >= 25 && FORMAT/AF[normal] <= 0.05"
# AWK filter: min_diff = 0.15
```
**Expected**: ~6,000 variants (high-confidence only)

**Implementation Location**: `/nf-core-sarek_3.5.1/3_5_1/conf/modules/custom_mutect2_filter.config`

### ⚠️ **DISCUSSION NEEDED: Yeast ALE Variant Filtering Strategy**

**Status**: Requires bench scientist input on filtering philosophy

**Context**: Unlike cancer research, yeast ALE experiments have different biological questions that affect what variants should be reported. Current filtering removes variants based on cancer-focused criteria, but ALE research may have different priorities.

**Key Questions for Bench Scientists**:

1. **Should variants present in original strain be reported?**
   - Cancer approach: Remove all variants present in "normal" (ancestral strain)  
   - ALE approach: May want to track pre-existing variation, lost mutations, population changes

2. **What confidence level is appropriate?**
   - High stringency: Only clear adaptive mutations
   - Medium stringency: Balance between sensitivity and precision  
   - Low stringency: Complete mutational landscape including small changes

**Filtering Strategy Examples** (from raw Mutect2 data):

#### **Example 1: Low Confidence Variants (TLOD < 6)**
```
Position: AECK01000001:2758 G>A
TLOD=5.15 NLOD=2.71 Total_DP=37
Normal: AF=8.8% DP=9  |  Evolved: AF=7.3% DP=28
```
- **Conservative filter**: REMOVE (low confidence)
- **Permissive filter**: KEEP (might be real low-frequency change)

#### **Example 2: High Confidence but Present in Normal (NLOD < 0)**
```
Position: AECK01000001:774017 T>C  
TLOD=35.55 NLOD=-52.37 Total_DP=35
Normal: AF=76.2% DP=21  |  Evolved: AF=66.6% DP=14
```
- **Cancer-focused**: REMOVE (present in normal = germline)
- **ALE-focused**: KEEP? (frequency change during evolution)

#### **Example 3: Medium Quality Somatic-like**
```
Position: AECK01000001:378 G>A
TLOD=8.13 NLOD=2.71 Total_DP=50  
Normal: AF=9.1% DP=11  |  Evolved: AF=10.8% DP=39
```
- **Moderate filter**: BORDERLINE (depends on AF difference threshold)
- **Questions**: Is 1.7% AF increase biologically meaningful?

#### **Current Filter Settings** (after recent updates):
- TLOD ≥ 12 (increased stringency)
- Normal depth ≥ 12, Tumor depth ≥ 15
- AF difference > 8% (increased from 5%)
- Strand bias required (F1R2>0 & F2R1>0)
- **No NLOD filter yet** - awaiting this discussion

#### **Proposed NLOD Options**:
1. **No NLOD filter**: Keep all variants regardless of normal presence
2. **NLOD ≥ 0**: Remove obvious artifacts, keep potential evolutionary variants
3. **NLOD ≥ 2**: Standard somatic filtering (like cancer)

#### **Impact Analysis** (from current dataset):
- Total raw variants: ~50,000
- After current filters: ~4,200
- With NLOD ≥ 0: ~4,193 (-7 artifacts)  
- With NLOD ≥ 2: ~4,183 (-9 low confidence)

**Recommendation**: Schedule meeting to discuss biological priorities and set filtering philosophy before finalizing NLOD thresholds.

#### **Additional Analysis: GT-based vs AF-based Filtering**

**Key Finding**: Mutect2 NEVER reports AF=0 in any sample. Minimum observed AF is ~4%.

**AF Distribution in Normal Sample**:
- AF = 0%: 0 variants (0%)
- AF 0-5%: 12,502 variants (27.7%) - **Potential true somatic**
- AF 5-10%: 31,513 variants (69.8%) - **Borderline/artifacts**
- AF >10%: 1,124 variants (2.5%) - **Likely pre-existing**

#### **Example 4: GT-based "True Somatic" Variants**
```
Position: AECK01000001:27836 G>C
Normal: GT=0/0 AF=4.2% DP=? → Evolved: GT=0/1 AF=20.7% DP=?
TLOD=11.63 NLOD=6.62
```
- **GT-based filter**: KEEP (0/0 → 0/1 = classic somatic)
- **AF-based filter**: BORDERLINE (depends on 4.2% threshold)
- **Biological interpretation**: Low-level contamination vs. true acquisition?

#### **Example 5: Large AF Increase (Potential True Somatic)**
```
Position: AECK01000001:27887 A>G  
Normal: AF=4.6% → Evolved: AF=22.4% (Δ=17.8%)
TLOD=14.22 NLOD=5.93
```
- **Question**: Is 4.6% background noise or real low-level variant?
- **ALE relevance**: Dramatic frequency increase suggests strong selection

#### **Filtering Strategy Implications**:

1. **Pure AF-based**: Current approach, removes variants with Normal AF > threshold
2. **GT-based**: Remove variants where Normal GT ≠ 0/0 (more stringent)  
3. **Hybrid**: Combine GT (0/0 → 0/1) + minimum AF difference

**GT-based filtering would be MORE stringent** than current AF-based approach, focusing only on variants with clear genotype changes rather than allele frequency shifts.

**Files to review**:
- Raw data: `/output_NCYC495/variant_calling/mutect2/.../A10-F47-I1-R1_vs_A0-F0-I1-R1.mutect2.vcf.gz`
- Current filtered: `/output_NCYC495/variant_calling_filtered/mutect2/.../...somatic.vcf.gz`

### ⚠️ **CRITICAL BUG: FreeBayes Somatic Filter Not Working Properly**

**Date**: 2025-09-08
**Status**: **URGENT - REQUIRES IMMEDIATE FIX**
**Impact**: High - Filtered "somatic" VCFs contain variants that don't meet filtering criteria

#### **Issue Summary**

The FreeBayes somatic filtering pipeline is **NOT working correctly**. Analysis of the filtered output shows that many variants fail to meet the required AF difference threshold.

#### **Detailed Analysis**

**File analyzed**: `/home/azureuser/Docs/ALE_nextflow/output_all/variant_calling_filtered/freebayes/A1-F6-I1-R1_vs_A0-F0-I1-R1.freebayes.quality_filtered/A1-F6-I1-R1_vs_A0-F0-I1-R1.freebayes.quality_filtered.somatic.vcf.gz`

**Expected behavior**: ALL variants should have `(tumor_AF - normal_AF) > 0.05`
**Actual behavior**: Only 366/918 variants (39.9%) meet this criterion

#### **Filter Compliance Analysis**

| Criterion | Expected | Actual | Status |
|-----------|----------|--------|---------|
| Tumor AF > 0.05 | 918/918 (100%) | 918/918 (100%) | ✅ PASS |
| AF difference > 0.05 | 918/918 (100%) | 366/918 (39.9%) | ❌ **FAIL** |
| Tumor DP ≥ 10 | 918/918 (100%) | 918/918 (100%) | ✅ PASS |
| Normal DP ≥ 8 | 918/918 (100%) | 918/918 (100%) | ✅ PASS |

#### **Problematic Examples** (should have been filtered out)

```
chr10:38274 C→A: tumor_AF=0.195, normal_AF=0.234, difference=-0.039 ❌
chr10:38274 C→T: tumor_AF=0.207, normal_AF=0.170, difference=0.037  ❌  
chr10:38394 TCAA→TAAA: tumor_AF=0.148, normal_AF=0.170, difference=-0.022 ❌
```

#### **AF Difference Statistics**
- **Mean**: 0.038 (below 0.05 threshold)
- **Median**: 0.032 (below 0.05 threshold)
- **Range**: -0.358 to 0.965
- **Negative differences**: 269/918 variants (29.3%) have normal_AF > tumor_AF

#### **Root Cause Investigation**

**Pipeline filter command** (from VCF header):
```bash
bcftools view -i 'FORMAT/AO[0:0]/(FORMAT/DP[0:0]) > 0.05 && (FORMAT/AO[0:0]/(FORMAT/DP[0:0]) - FORMAT/AO[1:0]/(FORMAT/DP[1:0])) > 0.05 && FORMAT/DP[0] >= 10 && FORMAT/DP[1] >= 8'
```

**Suspected issues**:
1. **bcftools version bug**: Possible issue with floating point calculations in bcftools 1.22
2. **Filter expression syntax**: Potential operator precedence or parentheses issue
3. **Multi-allelic handling**: Problems after `bcftools norm -m-` splitting
4. **Sample indexing error**: Possible mix-up in sample indices (though sample order verified as correct)

#### **Immediate Actions Required**

1. **Debug the bcftools filter**:
   - Test filter components individually 
   - Verify floating point arithmetic in bcftools
   - Check for known bugs in bcftools 1.22

2. **Alternative filtering approach**:
   - Consider using awk/python post-processing instead of bcftools -i
   - Implement manual AF calculation and filtering

3. **Quality control**:
   - Add validation step to verify all filtered variants meet criteria
   - Implement automated compliance checking in pipeline

#### **Workaround Options**

**Option 1: Post-processing filter**
```bash
# After bcftools filter, add validation step:
bcftools query -f '%CHROM\t%POS[\t%AO\t%DP]\n' input.vcf | \
awk 'tumor_AO/tumor_DP > 0.05 && (tumor_AO/tumor_DP - normal_AO/normal_DP) > 0.05'
```

**Option 2: Python validation**
```python
# Add compliance check after filtering
def validate_somatic_filter(vcf_path):
    # Extract AF data and verify all variants meet criteria
    # Raise error if any variants fail compliance
```

#### **Impact Assessment**

- **Research integrity**: Filtered datasets contain non-somatic variants
- **False positives**: 552 variants incorrectly labeled as "somatic" 
- **Publication risk**: Results based on incorrectly filtered data
- **Pipeline reliability**: Undermines trust in automated filtering

#### **Priority**: **CRITICAL** - Must be fixed before any research publication or data release

#### **Next Steps**
1. Debug bcftools filter expression (immediate)
2. Implement temporary workaround (within 24h)
3. Add automated compliance testing (within 48h)
4. Update all existing filtered datasets (coordinate with research team)

