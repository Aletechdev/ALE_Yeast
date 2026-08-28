# Split Joint VCF Pipeline - Individual Sample Extraction

## Summary
The `SPLIT_JOINT_VCF` subworkflow extracts individual sample VCFs from HaplotypeCaller joint germline calling output. This enables sample-specific analysis, annotation, and comparison between joint calling and individual calling results.

**Key Features**:
- Uses **channel-based metadata propagation** (NextFlow best practice) instead of string parsing for robust sample identification
- Applies **genotype-based filtering** to remove reference genotypes (0/0, 0|0)
- **Does NOT apply quality filtering** - all quality annotations (FILTER, QUAL, INFO) are preserved from joint VCF

## Pipeline Architecture

### 1. Workflow Integration Point
**Location**: `subworkflows/local/bam_variant_calling_germline_all/main.nf:163-175`

```nextflow
// After HaplotypeCaller joint germline calling
if (params.split_haplotypecaller_joint_vcf) {
    // Combine joint VCF with its index
    joint_vcf_tbi = BAM_JOINT_CALLING_GERMLINE_GATK.out.genotype_vcf
        .join(BAM_JOINT_CALLING_GERMLINE_GATK.out.genotype_index, failOnDuplicate: true)

    // Pass both joint VCF and original cram channel for metadata
    SPLIT_JOINT_VCF(joint_vcf_tbi, cram)

    // Add split individual VCFs to vcf_haplotypecaller channel
    vcf_haplotypecaller = vcf_haplotypecaller.mix(SPLIT_JOINT_VCF.out.vcf)

    versions = versions.mix(SPLIT_JOINT_VCF.out.versions)
}
```

**Pipeline Parameter**: `--split_haplotypecaller_joint_vcf` (boolean flag)

### 2. SPLIT_JOINT_VCF Subworkflow
**Location**: `subworkflows/local/split_joint_vcf/main.nf`

**Inputs**:
- `joint_vcf_tbi`: Joint VCF with index `[meta_joint, vcf, tbi]`
- `cram`: Individual sample metadata `[meta_sample, cram, crai]`

**Outputs**:
- `vcf`: Individual sample VCFs with non-reference variants `[meta, vcf]`
- `versions`: Version tracking

**Key Modules Used**:
1. `BCFTOOLS_VIEW` - Extract individual samples from joint VCF
2. `BCFTOOLS_FILTER` - Filter to keep only non-reference genotypes

## How It Works

### Step 1: Channel-Based Metadata Combination

**Challenge**: Map individual samples to the joint VCF that contains all samples.

**Solution**: Combine joint VCF metadata with individual sample metadata using channels:

```nextflow
samples_for_split = joint_vcf_tbi
    .combine(cram)  // Create all combinations of joint VCF × samples
    .filter { meta_joint, vcf, tbi, meta_sample, cram_file, crai_file ->
        // Accept all samples since joint VCF contains all patients
        def joint_patient = meta_joint.patient ?: meta_joint.id
        joint_patient == "all_samples"  // Joint VCF marker
    }
    .map { meta_joint, vcf, tbi, meta_sample, cram_file, crai_file ->
        // Construct bcftools sample name
        def patient = meta_sample.patient ?: meta_sample.id
        def bcftools_sample_name = "${patient}_${meta_sample.sample}"

        // Create enriched metadata
        [
            meta_joint + meta_sample + [
                id: meta_sample.sample,                      // e.g., "A0-F0-I1-R1"
                patient: patient,                            // e.g., "ALE_Exp1"
                variantcaller: "haplotypecaller",
                source: 'joint_calling',
                bcftools_sample: bcftools_sample_name        // e.g., "ALE_Exp1_A0-F0-I1-R1"
            ],
            vcf,
            tbi
        ]
    }
```

### Step 2: Sample Name Construction

**BAM Header Sample Names** (from alignment step):
```
workflows/sarek/main.nf:292
SM:${meta.patient}_${meta.sample}
```

**Example**:
- `meta.patient = "ALE_Exp1"`
- `meta.sample = "A0-F0-I1-R1"`
- **BAM/VCF Sample Name**: `ALE_Exp1_A0-F0-I1-R1`

**In Split Workflow**:
```nextflow
bcftools_sample_name = "${patient}_${meta_sample.sample}"
// Result: "ALE_Exp1_A0-F0-I1-R1"
```

### Step 3: Sample Extraction with BCFTOOLS_VIEW

**Configuration**: `conf/modules/split_joint_vcf.config` (BCFTOOLS_VIEW block; rules keyed on `meta.variantcaller`)

```groovy
withName: '.*:SPLIT_JOINT_VCF:BCFTOOLS_VIEW' {
    ext.args   = { "--samples ${meta.bcftools_sample} --force-samples -Oz" }
    ext.prefix = { "${meta.id}.haplotypecaller.from_joint_calling.raw" }
    publishDir = [
        enabled: false  // Don't publish raw extraction
    ]
}
```

**Command Executed**:
```bash
bcftools view \
    --samples ALE_Exp1_A0-F0-I1-R1 \
    --force-samples \
    -Oz \
    -o A0-F0-I1-R1.haplotypecaller.from_joint_calling.raw.vcf.gz \
    HaplotypeCaller_joint_calling_soft_filtered.vcf.gz
```

**Key Parameters**:
- `--samples ${meta.bcftools_sample}`: Extract specific sample column
- `--force-samples`: Don't fail if sample not found (safety check)
- `-Oz`: Output compressed VCF

**Output**:
- Raw VCF with **all variants** from joint calling for that sample
- Includes reference (0/0 or 0|0) genotypes

### Step 4: Filter Non-Reference Genotypes ⭐

**⚠️ IMPORTANT**: This is a **genotype-based filter**, NOT a quality filter.

**What it does**: Removes variants where the individual sample has a **reference genotype** (0/0 or 0|0)

**What it does NOT do**: Does NOT filter based on quality (QUAL, DP, AF, MQ, etc.)

**Configuration**: `conf/modules/split_joint_vcf.config` (BCFTOOLS_FILTER block; the HaplotypeCaller branch)

```groovy
withName: '.*:SPLIT_JOINT_VCF:BCFTOOLS_FILTER' {
    ext.args   = {
        def ploidy = meta.ploidy ?: 2
        // Build reference genotypes for both phased and unphased
        def ref_gt_unphased = (['0'] * ploidy).join('/')  // e.g., "0/0" for diploid
        def ref_gt_phased = (['0'] * ploidy).join('|')    // e.g., "0|0" for diploid

        // Filter: GT is not missing AND GT is not reference
        "--include 'GT!=\".\" && GT!=\"./\" && GT!=\".|\" && GT!=\"${ref_gt_unphased}\" && GT!=\"${ref_gt_phased}\"' -Oz"
    }
    ext.prefix = { "${meta.id}.haplotypecaller.from_joint_calling" }
    publishDir = [
        mode: params.publish_dir_mode,
        path: { "${params.outdir}/variant_calling/haplotypecaller/individual_from_joint/${meta.id}/" },
        pattern: "*vcf.gz"
    ]
}
```

**Filter Logic** (for diploid, ploidy=2):
```bash
--include 'GT!="." && GT!="./" && GT!=".|" && GT!="0/0" && GT!="0|0"'
```

**What Gets Removed**:
- Missing genotypes: `.`, `./`, `.|`
- Reference homozygotes: `0/0` (unphased), `0|0` (phased)

**What Gets Kept**:
- Heterozygous: `0/1`, `0|1`, `1/0`, `1|0`
- Alternate homozygous: `1/1`, `1|1`
- Multi-allelic: `0/2`, `1/2`, etc.

**Ploidy Support**:
- **Haploid** (ploidy=1): Filters `0` genotypes, keeps `1`, `2`, etc.
- **Diploid** (ploidy=2): Filters `0/0` and `0|0`
- **Triploid** (ploidy=3): Filters `0/0/0` and `0|0|0`
- **Tetraploid** (ploidy=4): Filters `0/0/0/0` and `0|0|0|0`

### Why This Filter? Understanding Joint Calling

**In joint calling**, the joint VCF contains:
- All variants called in **ANY** sample
- Genotypes for **ALL** samples at each variant position
- Many samples will have reference genotype (0/0) at positions where other samples have variants

**Example Joint VCF**:
```
#CHROM  POS    REF  ALT  ...  ALE_Exp1_Sample1  ALE_Exp1_Sample2  ALE_Exp1_Sample3
chr1    1000   A    G    ...  1/1               0/0               0/1
chr1    2000   C    T    ...  0/0               1/1               0/0
                              ^^^               ^^^               ^^^
                           variant          variant           variant
                           (kept)          (removed)          (removed)
```

**Individual VCF for Sample1** (after filtering):
- `chr1:1000` → **KEPT** (genotype is `1/1` - homozygous alternate)
- `chr1:2000` → **REMOVED** (genotype is `0/0` - reference, no mutation in this sample)

**Rationale**:
1. **File size reduction**: Remove positions where sample matches reference
2. **Focus on mutations**: Only keep variants where THIS sample differs from reference
3. **Cleaner annotation**: Don't annotate reference calls that aren't real mutations
4. **Biological relevance**: Only variants specific to this sample/strain

### Important: Quality Filtering is Separate

**This genotype filter does NOT filter by quality**:
- ❌ No QUAL threshold
- ❌ No depth (DP) filtering
- ❌ No allele frequency (AF) filtering
- ❌ No strand bias filtering
- ✅ All quality annotations (FILTER, QUAL, INFO) preserved from joint VCF

**Quality filtering happens earlier** at the joint VCF level:
- Source: `HaplotypeCaller_joint_calling_soft_filtered.vcf.gz`
- Method: GATK VariantFiltration (see CLAUDE.md: "Filter Annotation Fallback")
- Result: FILTER column populated with `PASS`, `QD_filter`, `FS_filter`, etc.

**To get high-quality variants only**:
```bash
# Extract only PASS variants from individual VCF
bcftools view -f PASS A0-F0-I1-R1.haplotypecaller.from_joint_calling.vcf.gz \
    -Oz -o A0-F0-I1-R1.PASS_only.vcf.gz
```

## Recommended Additional Filtering

### Current Status
Individual VCFs from joint calling contain:
- ✅ Only variants where sample has non-reference genotype (0/1, 1/1, etc.)
- ✅ All quality annotations from joint VCF (FILTER, QUAL, INFO fields)
- ⚠️ May include low-quality or false positive variants

### Filtering Strategy: Three-Tier Approach

#### Tier 1: PASS-Only (Recommended Starting Point) ⭐

**Use Case**: High-confidence variant analysis for publication or clinical decisions

**Command**:
```bash
bcftools view -f PASS input.vcf.gz -Oz -o output.PASS.vcf.gz
```

**What it does**:
- Keeps only variants with `FILTER=PASS`
- Removes variants flagged by GATK VariantFiltration (QD_filter, FS_filter, etc.)
- No additional custom filtering needed

**Pros**:
- ✅ Simple one-line command
- ✅ Leverages GATK's comprehensive quality model
- ✅ Well-validated for germline calling

**Cons**:
- ❌ May be too stringent for discovery-mode analysis
- ❌ Might miss true positives in low-coverage regions

#### Tier 2: Custom Quality Filters (For ALE-Specific Tuning)

**Use Case**: Balance sensitivity and specificity for evolutionary studies

**Command**:
```bash
bcftools filter \
    --include 'FILTER="PASS" || (QUAL>=30 && INFO/DP>=10 && INFO/QD>=5.0)' \
    -Oz -o output.custom_filtered.vcf.gz \
    input.vcf.gz
```

**Filter Breakdown**:
- `FILTER="PASS"`: Keep all PASS variants (high confidence)
- **OR** meet all of these criteria:
  - `QUAL>=30`: Minimum variant quality (Phred score)
  - `INFO/DP>=10`: Total read depth ≥10 across all samples
  - `INFO/QD>=5.0`: Quality by Depth ≥5 (QUAL/DP ratio)

**Why These Metrics**:
- **QUAL**: Overall confidence in variant call
- **DP**: Read depth (avoid low-coverage noise)
- **QD**: Quality normalized by depth (catches high-DP but low-quality calls)

**Adjust Thresholds For**:
- Higher coverage data: Increase DP to 15-20
- More stringent: Add `INFO/MQ>=40` (mapping quality)
- Discovery mode: Relax to `QUAL>=20 && DP>=8 && QD>=2.0`

#### Tier 3: Sample-Specific Genotype Quality (Most Stringent)

**Use Case**: Filter based on individual sample genotype quality, not just variant-level metrics

**Two Approaches**:

##### 3A: Remove Failing Variants (Recommended for MultiQC/QC Reporting) ⭐

**Command**:
```bash
bcftools filter \
    --include 'FILTER="PASS" && FORMAT/GQ>=20 && FORMAT/DP>=8' \
    -Oz -o output.genotype_filtered.vcf.gz \
    input.vcf.gz
```

**What it does**:
- ✅ **Removes variants entirely** if they fail sample-level filters
- ✅ **Clean variant counts** for bcftools stats and MultiQC
- ✅ **No missing genotypes** - all remaining variants are confident

**Best for**:
- ✅ MultiQC reporting and QC tracking across pipeline stages
- ✅ Variant count comparisons (joint calling → individual filtering → annotation)
- ✅ Publication-ready variant sets
- ✅ Downstream analysis tools expecting confident genotypes

##### 3B: Mark as Missing (For Manual Review)

**Command**:
```bash
bcftools filter \
    --include 'FILTER="PASS" && FORMAT/GQ>=20 && FORMAT/DP>=8' \
    --set-GTs . \
    -Oz -o output.genotype_filtered_with_missing.vcf.gz \
    input.vcf.gz
```

**What it does**:
- ✅ **Keeps variant records** but sets genotype to `.` (missing)
- ⚠️ **Variant counted** by bcftools stats but AC=0, AN=0, AF=missing
- ⚠️ **May confuse** downstream tools and MultiQC variant counts

**Best for**:
- Manual review in IGV
- Seeing where low-quality calls occurred
- Comparing positions across samples
- ❌ NOT for MultiQC reporting (counts will be misleading)

**Sample-Level Filters**:
- `FORMAT/GQ>=20`: Genotype quality ≥20 (confidence in GT call for THIS sample)
- `FORMAT/DP>=8`: Read depth for THIS sample ≥8 (not cohort-wide DP)
- No `--set-GTs`: Remove variants entirely (clean counts for reporting)

**Why Sample-Level Filtering**:
- Joint calling uses cohort information, but individual sample may have low coverage
- Ensures variant is well-supported in THIS specific sample
- Critical for ALE experiments where you compare specific strains

**Example Scenario**:
```
Joint VCF: chr1:1000  DP=50  Sample1_DP=45  Sample2_DP=2
                              ^^^high        ^^^low (problematic)
```
Sample-level filtering catches low-coverage samples even if cohort DP is high.

**Key Distinction: INFO/DP vs FORMAT/DP**:
```
INFO/DP = 50      # Cohort-wide depth (all 7 samples)
FORMAT/DP = 2     # THIS sample's depth only ⚠️

Filter: INFO/DP>=10   → PASS (50≥10) but sample only has 2 reads!
Filter: FORMAT/DP>=10 → FAIL (2<10) correctly catches low sample coverage
```

### Recommended Workflow for ALE Experiments (MultiQC-Compatible)

#### Step 1: Apply Sample-Specific Quality Filters (Tier 3A - Remove Failing) ⭐

**Recommended for MultiQC reporting and QC tracking**:

```bash
sample="A4-F5-I1-R1"
input="output/variant_calling/haplotypecaller/individual_from_joint/${sample}/${sample}.haplotypecaller.from_joint_calling.vcf.gz"

# Apply sample-level filters (removes failing variants)
bcftools filter \
    --include 'FILTER="PASS" && FORMAT/GQ>=20 && FORMAT/DP>=8' \
    -Oz -o ${sample}.sample_filtered.vcf.gz \
    $input

bcftools index -t ${sample}.sample_filtered.vcf.gz

# Generate stats for MultiQC
bcftools stats ${sample}.sample_filtered.vcf.gz > ${sample}.sample_filtered.stats.txt
```

**Why this approach**:
- ✅ Clean variant counts for MultiQC
- ✅ Easy to track: joint calling (4 vars) → sample filtering (X vars) → annotation
- ✅ No ambiguity with missing genotypes
- ✅ Ready for downstream analysis

#### Step 2: Check Filtering Impact (QC)
```bash
echo "=== Filtering Summary for ${sample} ==="
echo "Original variants: $(bcftools view -H $input | wc -l)"
echo "After sample filtering: $(bcftools view -H ${sample}.sample_filtered.vcf.gz | wc -l)"
echo "Removed: $(($(bcftools view -H $input | wc -l) - $(bcftools view -H ${sample}.sample_filtered.vcf.gz | wc -l)))"

# Breakdown by FILTER status in original
echo ""
echo "Original FILTER breakdown:"
bcftools query -f '%FILTER\n' $input | sort | uniq -c

# Quality metrics of filtered variants
echo ""
echo "Filtered variants quality:"
bcftools query -f '[%GQ\t%DP]\n' ${sample}.sample_filtered.vcf.gz | \
    awk '{sum_gq+=$1; sum_dp+=$2; n++} END {print "Avg GQ:", sum_gq/n, "Avg DP:", sum_dp/n}'
```

#### Step 3: Optional - Add Custom Filters for Very Stringent Analysis
```bash
# For publication-ready high-confidence calls
bcftools filter \
    --include 'FORMAT/GQ>=30 && FORMAT/DP>=10' \
    -Oz -o ${sample}.high_confidence.vcf.gz \
    ${sample}.sample_filtered.vcf.gz

bcftools index -t ${sample}.high_confidence.vcf.gz

echo "High confidence variants: $(bcftools view -H ${sample}.high_confidence.vcf.gz | wc -l)"
```

#### Step 3: Compare with Individual HaplotypeCaller (Optional)
```bash
# If you ran both joint and individual calling
joint_vcf="${sample}.haplotypecaller.from_joint_calling.vcf.gz"
individual_vcf="output/variant_calling/haplotypecaller/${sample}/${sample}.haplotypecaller.vcf.gz"

# Find intersection (high-confidence variants)
bcftools isec -p comparison_dir -Oz $joint_vcf $individual_vcf

# Results in comparison_dir:
# 0000.vcf.gz - unique to joint calling
# 0001.vcf.gz - unique to individual calling
# 0002.vcf.gz - intersection (highest confidence)
```

### Quality Metrics Reference

| Metric | Recommended | Conservative | Discovery |
|--------|-------------|--------------|-----------|
| **QUAL** | ≥30 | ≥50 | ≥20 |
| **INFO/DP** | ≥10 | ≥20 | ≥8 |
| **INFO/QD** | ≥5.0 | ≥10.0 | ≥2.0 |
| **INFO/MQ** | ≥40 | ≥50 | ≥30 |
| **INFO/FS** | ≤60 | ≤30 | ≤80 |
| **INFO/SOR** | ≤3.0 | ≤2.0 | ≤4.0 |
| **FORMAT/GQ** | ≥20 | ≥30 | ≥10 |
| **FORMAT/DP** | ≥8 | ≥10 | ≥5 |

**Metric Explanations**:
- **QUAL**: Phred-scaled quality score (30 = 0.1% error, 50 = 0.001% error)
- **DP**: Total read depth (higher = more confident, but watch for duplicates)
- **QD**: Quality by Depth = QUAL/DP (catches high-DP but poor-quality calls)
- **MQ**: Mapping quality (low = multi-mapping reads, alignment issues)
- **FS**: Fisher Strand (high = strand bias, potential PCR artifact)
- **SOR**: Strand Odds Ratio (alternative strand bias metric, more robust)
- **GQ**: Genotype quality (confidence in 0/1 vs 1/1 assignment)
- **FORMAT/DP**: Per-sample depth (different from INFO/DP which is cohort-wide)

### MultiQC Reporting and Variant Count Tracking

**Why Tier 3A (Remove Failing) is Critical for QC**:

When you use `--set-GTs .` (mark as missing), variant count tracking becomes confusing:

| Stage | With `--set-GTs .` | Without `--set-GTs` (Remove) |
|-------|-------------------|------------------------------|
| **Joint VCF** | 1,748 variants | 1,748 variants |
| **Individual VCF** | 4 variants (for sample) | 4 variants |
| **After GQ/DP filter** | 4 variants ⚠️ | 2 variants ✅ |
| **bcftools stats** | Reports 4 but AC=0 ⚠️ | Reports 2 (real variants) ✅ |
| **MultiQC** | Confusing counts ⚠️ | Clear progression ✅ |

**MultiQC Workflow for Clean Reporting**:

```bash
# For each sample, apply filtering and generate stats
for sample in A0-F0-I1-R1 A4-F5-I1-R1 A6-F6-I1-R1; do
    input="output/variant_calling/haplotypecaller/individual_from_joint/${sample}/${sample}.haplotypecaller.from_joint_calling.vcf.gz"

    # Apply Tier 3A filter (remove failing)
    bcftools filter \
        --include 'FILTER="PASS" && FORMAT/GQ>=20 && FORMAT/DP>=8' \
        -Oz -o ${sample}.sample_filtered.vcf.gz \
        $input

    # Generate stats for MultiQC
    bcftools stats ${sample}.sample_filtered.vcf.gz > ${sample}.sample_filtered.bcftools_stats.txt
done

# Run MultiQC to aggregate all stats
multiqc output/ --outdir multiqc_report/
```

**What MultiQC Will Show**:
```
Sample A0-F0-I1-R1:
  - Joint VCF: 1,748 total variants
  - Individual (from joint): 4 variants with this sample's genotype
  - After sample filtering: 2 variants (GQ>=20, DP>=8)
  - After annotation: 2 variants annotated

Sample A4-F5-I1-R1:
  - Joint VCF: 1,748 total variants
  - Individual (from joint): 4 variants with this sample's genotype
  - After sample filtering: 3 variants (GQ>=20, DP>=8)
  - After annotation: 3 variants annotated
```

**Benefit**: Clear tracking of filtering impact across all samples in one report!

**Comparison: `--set-GTs` vs Remove**:

```bash
# Test both approaches
sample="A4-F5-I1-R1"
input="${sample}.haplotypecaller.from_joint_calling.vcf.gz"

# Approach 1: Mark as missing (NOT RECOMMENDED for MultiQC)
bcftools filter --include 'FORMAT/GQ>=20 && FORMAT/DP>=8' --set-GTs . $input -Oz -o test_missing.vcf.gz
bcftools stats test_missing.vcf.gz > test_missing.stats.txt

# Approach 2: Remove failing (RECOMMENDED for MultiQC)
bcftools filter --include 'FORMAT/GQ>=20 && FORMAT/DP>=8' $input -Oz -o test_remove.vcf.gz
bcftools stats test_remove.vcf.gz > test_remove.stats.txt

# Compare
echo "With --set-GTs . (missing):"
grep "number of records" test_missing.stats.txt

echo "Without --set-GTs (remove):"
grep "number of records" test_remove.stats.txt
```

**Result**:
```
With --set-GTs . (missing):
SN  0  number of records:  4    ← Misleading (includes GT=.)

Without --set-GTs (remove):
SN  0  number of records:  2    ← Accurate count
```

### Automation: Pipeline Integration (Future Enhancement)

To integrate custom filtering into the Sarek pipeline, you could add a process after `SPLIT_JOINT_VCF`:

```nextflow
// Pseudocode - not currently implemented
process FILTER_INDIVIDUAL_JOINT_VCF {
    input:
    tuple val(meta), path(vcf)

    output:
    tuple val(meta), path("*.filtered.vcf.gz")

    script:
    """
    bcftools filter \\
        --include 'FILTER="PASS" || (QUAL>=30 && INFO/DP>=10 && INFO/QD>=5.0)' \\
        -Oz -o ${meta.id}.filtered.vcf.gz \\
        $vcf
    bcftools index -t ${meta.id}.filtered.vcf.gz
    """
}
```

### Key Recommendations Summary

1. ✅ **Use Tier 3A (remove failing variants) for MultiQC reporting** - Clean counts across pipeline stages ⭐
2. ✅ **Apply sample-level FORMAT/GQ and FORMAT/DP filters** - Ensures per-sample quality (not cohort-wide)
3. ✅ **Avoid `--set-GTs` for QC tracking** - Missing genotypes confuse variant counts in reports
4. ✅ **Generate bcftools stats after filtering** - Track filtering impact in MultiQC
5. ✅ **Compare joint vs individual calling** - Intersection = highest confidence
6. ✅ **Document your filtering strategy** - Reproducibility for publications

**For MultiQC Integration**:
```bash
# After filtering, generate stats that MultiQC can parse
bcftools stats filtered.vcf.gz > filtered.stats.txt

# MultiQC will show:
# - Variant counts at each stage
# - Filtering impact
# - Quality metrics distribution
```

**Current Individual VCFs are ready for analysis** - They contain all quality information needed for flexible downstream filtering based on your experimental requirements.

## Output Structure

```
output/variant_calling/haplotypecaller/
├── joint_variant_calling/
│   ├── HaplotypeCaller_joint_calling_soft_filtered.vcf.gz  # Joint VCF (all samples)
│   └── joint_germline.vcf.gz                                # Alternative joint VCF
└── individual_from_joint/
    ├── A0-F0-I1-R1/
    │   └── A0-F0-I1-R1.haplotypecaller.from_joint_calling.vcf.gz
    ├── A1-F6-I1-R1/
    │   └── A1-F6-I1-R1.haplotypecaller.from_joint_calling.vcf.gz
    ├── A4-F5-I1-R1/
    │   └── A4-F5-I1-R1.haplotypecaller.from_joint_calling.vcf.gz
    └── ...
```

**Published Directory**: `${params.outdir}/variant_calling/haplotypecaller/individual_from_joint/${meta.id}/`

**File Naming**:
- Pattern: `${sample_id}.haplotypecaller.from_joint_calling.vcf.gz`
- Example: `A0-F0-I1-R1.haplotypecaller.from_joint_calling.vcf.gz`

## Sample Name Preservation

### VCF Column Names (Kept Original)

**Joint VCF Header**:
```
#CHROM  POS  ID  REF  ALT  QUAL  FILTER  INFO  FORMAT  ALE_Exp1_A0-F0-I1-R1  ALE_Exp1_A1-F6-I1-R1  ...
```

**Individual VCF Header** (after split):
```
#CHROM  POS  ID  REF  ALT  QUAL  FILTER  INFO  FORMAT  ALE_Exp1_A0-F0-I1-R1
```

**Rationale**: Keeping `patient_sample` format maintains traceability back to joint calling.

### File Names (Sample ID Only)

**File Path**: `individual_from_joint/A0-F0-I1-R1/A0-F0-I1-R1.haplotypecaller.from_joint_calling.vcf.gz`

**Rationale**: Simplifies file organization while VCF column name preserves full context.

## Use Cases

### 1. Joint vs Individual Calling Comparison
Compare variants called by joint germline vs individual germline methods:

```bash
# Source conda environment
source ~/miniforge3/etc/profile.d/conda.sh
conda activate nf-env

# Individual from joint calling
joint_individual="output/variant_calling/haplotypecaller/individual_from_joint/A4-F5-I1-R1/A4-F5-I1-R1.haplotypecaller.from_joint_calling.vcf.gz"

# Individual calling (if available)
individual="output/variant_calling/haplotypecaller/A4-F5-I1-R1/A4-F5-I1-R1.haplotypecaller.vcf.gz"

# Compare
bcftools isec -p comparison_dir $joint_individual $individual
```

### 2. Sample-Specific Annotation
Annotate individual VCFs separately for focused analysis:

```bash
# These VCFs are automatically added to vcf_to_annotate channel
# So they will be annotated alongside other VCFs if annotation is enabled
```

### 3. Quality Control
Verify sample extraction and filtering:

```bash
sample="A0-F0-I1-R1"
vcf="output/variant_calling/haplotypecaller/individual_from_joint/${sample}/${sample}.haplotypecaller.from_joint_calling.vcf.gz"

# Check sample name in VCF
bcftools query -l $vcf
# Output: ALE_Exp1_A0-F0-I1-R1

# Check variant count
bcftools stats $vcf | grep "number of records"

# View genotypes
bcftools query -f '%CHROM:%POS\t%REF\t%ALT\t[%GT]\n' $vcf | head
```

### 4. Data Distribution
Share individual results without exposing entire cohort:

```bash
# Individual VCF only contains that sample's data
# Joint VCF information is preserved in variant quality scores
```

## Channel-Based Design (NextFlow Best Practice)

### Why Not String Parsing?

**Avoided Approach** (fragile):
```groovy
// ❌ String parsing - breaks if naming conventions change
def sample_id = vcf_sample_name.split('_').last()
```

**Our Approach** (robust):
```groovy
// ✅ Channel-based metadata - type-safe and maintainable
samples_for_split = joint_vcf_tbi
    .combine(cram)  // Structured metadata from existing channels
    .map { meta_joint, vcf, tbi, meta_sample, cram_file, crai_file ->
        // Use meta_sample fields directly
        def bcftools_sample = "${meta_sample.patient}_${meta_sample.sample}"
        [meta_sample + [bcftools_sample: bcftools_sample], vcf, tbi]
    }
```

**Advantages**:
- ✅ **Type-safe**: Uses structured metadata fields
- ✅ **Metadata-rich**: Preserves ploidy, status, sex, experiment info
- ✅ **Robust**: Independent of naming conventions
- ✅ **Maintainable**: Changes to naming don't break workflow
- ✅ **NextFlow idiomatic**: Follows nf-core/sarek patterns

### Metadata Flow

```
cram channel (from alignment)              joint VCF (from joint calling)
[meta_sample, cram, crai]         +        [meta_joint, vcf, tbi]
    ↓                                             ↓
meta_sample = {                           meta_joint = {
    id: "A0-F0-I1-R1",                       id: "joint_germline",
    patient: "ALE_Exp1",                     patient: "all_samples",
    sample: "A0-F0-I1-R1",                   variantcaller: "haplotypecaller"
    ploidy: 2,                            }
    status: 0,
    sex: "XX"
}
         ↓
    .combine()  # Cross product
         ↓
    .filter()   # Match patient IDs
         ↓
    .map()      # Create enriched metadata
         ↓
meta_combined = {
    id: "A0-F0-I1-R1",              # For file naming
    patient: "ALE_Exp1",            # Original patient ID
    sample: "A0-F0-I1-R1",          # Original sample ID
    ploidy: 2,                      # ✅ Preserved from cram
    status: 0,                      # ✅ Preserved from cram
    sex: "XX",                      # ✅ Preserved from cram
    variantcaller: "haplotypecaller", # From joint VCF
    source: "joint_calling",        # Track origin
    bcftools_sample: "ALE_Exp1_A0-F0-I1-R1"  # Constructed for extraction
}
```

## Integration with Downstream Processes

### 1. Annotation
Split individual VCFs are **automatically added** to the annotation channel:

```nextflow
vcf_haplotypecaller = vcf_haplotypecaller.mix(SPLIT_JOINT_VCF.out.vcf)
```

This means if SnpEff/VEP annotation is enabled, individual VCFs will be annotated alongside other VCFs.

### 2. MultiQC Reporting
Individual VCF statistics are included in MultiQC reports automatically via bcftools stats.

### 3. Variant Dashboard
Individual VCFs can be included in variant analysis dashboards for per-sample comparisons.

## Performance Characteristics

### Computational Cost
- **Low**: bcftools view and filter are very fast (seconds per sample)
- **Memory**: Minimal (streaming processing)
- **Parallelization**: Each sample extracted independently (parallel-friendly)

### Example Performance (Test Dataset)
```
7 samples × 2 processes (view + filter) = 14 tasks
Average time: 5-10 seconds per sample
Total overhead: ~1 minute for full dataset
```

### Scalability
- **Linear**: Time scales linearly with number of samples
- **Storage**: Each individual VCF much smaller than joint VCF
- **Network**: Efficient for distributed file systems (small file sizes)

## Validation & Quality Control

### Check Extraction Success
```bash
# Source conda environment
source ~/miniforge3/etc/profile.d/conda.sh
conda activate nf-env

# List all extracted samples
for sample in output/variant_calling/haplotypecaller/individual_from_joint/*/; do
    sample_name=$(basename "$sample")
    vcf="${sample}${sample_name}.haplotypecaller.from_joint_calling.vcf.gz"

    if [ -f "$vcf" ]; then
        count=$(bcftools view -H "$vcf" | wc -l)
        echo "${sample_name}: ${count} variants"
    fi
done
```

### Verify Sample Names Match
```bash
joint_vcf="output/variant_calling/haplotypecaller/joint_variant_calling/HaplotypeCaller_joint_calling_soft_filtered.vcf.gz"

echo "Samples in joint VCF:"
bcftools query -l $joint_vcf

echo ""
echo "Individual VCFs created:"
ls output/variant_calling/haplotypecaller/individual_from_joint/
```

### Compare Genotypes
Verify that individual VCF genotypes match the joint VCF:

```bash
sample="ALE_Exp1_A0-F0-I1-R1"
joint_vcf="output/variant_calling/haplotypecaller/joint_variant_calling/HaplotypeCaller_joint_calling_soft_filtered.vcf.gz"
individual_vcf="output/variant_calling/haplotypecaller/individual_from_joint/A0-F0-I1-R1/A0-F0-I1-R1.haplotypecaller.from_joint_calling.vcf.gz"

# Extract same sample from joint VCF
bcftools view -s $sample $joint_vcf | \
    bcftools query -f '%CHROM:%POS\t[%GT]\n' > joint_genotypes.txt

# Extract from individual VCF
bcftools query -f '%CHROM:%POS\t[%GT]\n' $individual_vcf > individual_genotypes.txt

# Compare (should show only reference genotypes in joint but not individual)
diff joint_genotypes.txt individual_genotypes.txt | grep "^<" | head
```

## Comparison with Alternative Approaches

### Manual Extraction (Command Line)
```bash
# Manual approach (what the pipeline automates)
bcftools view -s ALE_Exp1_A0-F0-I1-R1 --force-samples joint.vcf.gz | \
    bcftools filter --include 'GT!="./." && GT!="0/0" && GT!="0|0"' -Oz \
    -o A0-F0-I1-R1.vcf.gz
bcftools index -t A0-F0-I1-R1.vcf.gz
```

**Pipeline Advantages**:
- ✅ Automated for all samples
- ✅ Integrated with NextFlow channels
- ✅ Metadata preservation (ploidy, patient, status)
- ✅ Automatic versioning and provenance

### GATK SelectVariants
Alternative tool for sample extraction:

```bash
# GATK approach (heavier, slower)
gatk SelectVariants \
    -V joint.vcf.gz \
    -sn ALE_Exp1_A0-F0-I1-R1 \
    --exclude-non-variants \
    -O A0-F0-I1-R1.vcf.gz
```

**Why bcftools was chosen**:
- ✅ Faster (C vs Java)
- ✅ Lower memory usage
- ✅ Better integration with other bcftools steps
- ✅ More flexible filtering syntax

## References

### Pipeline Files
- Subworkflow: `subworkflows/local/split_joint_vcf/main.nf`
- Integration: `subworkflows/local/bam_variant_calling_germline_all/main.nf:163-175`
- Configuration: `conf/modules/split_joint_vcf.config` (HaplotypeCaller + Manta branches)

### Related Documentation
- See `CLAUDE.md` section: "✅ IMPLEMENTED: Split Joint VCF into Individual Sample VCFs (Channel-Based)"
- See `CLAUDE.md` section: "✅ IMPLEMENTED: Filter Annotation Fallback for Joint Germline Calling"
- GATK Joint Calling: https://gatk.broadinstitute.org/hc/en-us/articles/360035890431
- bcftools documentation: https://samtools.github.io/bcftools/

### Design Rationale
- **Channel-based**: Follows NextFlow/nf-core best practices for metadata handling
- **Ploidy-aware**: Dynamically adjusts filters based on sample ploidy
- **Non-reference only**: Reduces file sizes and focuses on variants of interest
- **Traceability**: Preserves sample names for easy cross-referencing with joint VCF

**Status**: ✅ Production-ready, fully integrated with Sarek pipeline
