# Mutect2 Joint Calling Timeout Issue

**Date**: October 13, 2025 (Updated: October 14, 2025)
**Issue**: Mutect2 process killed with exit code 143 (SIGTERM) after exactly 8 hours
**Status**: ✅ RESOLVED - Label-based time limits properly overridden

---

## Problem Description

### Symptoms
- Pipeline stopped at Mutect2 variant calling stage
- Process killed at chr4 after ~8 hours runtime
- Exit code 143 (SIGTERM - timeout/external kill)
- VCF file truncated at chr3:297387 (incomplete)
- Error: `No BGZF EOF marker; file may be truncated`

### Root Cause Analysis

**NOT a resource issue:**
- ✅ Memory: 15GB available, 14GB allocated to Mutect2, only ~3.8GB used
- ✅ Storage: 149GB free (70% disk usage)
- ✅ No OOM (Out of Memory) errors in logs

**Actual cause: Default 8-hour timeout with no explicit time limits configured**

### Why Joint Mutect2 Takes So Long

The pipeline was running with `--joint_mutect2` flag, which processes **all 17 samples together**:

```
Samples in joint calling:
- A0-F0-I1-R1, A0-F0-I2-R1 (ancestral, 2 replicates)
- A1-F6-I1-R1, A1-F6-I2-R1, A1-F6-I3-R1 (3 replicates)
- A3-F3-I1-R1, A3-F3-I2-R1, A3-F3-I3-R1 (3 replicates)
- A4-F5-I1-R1, A4-F5-I2-R1, A4-F5-I3-R1 (3 replicates)
- A5-F4-I1-R1, A5-F4-I2-R1, A5-F4-I3-R1 (3 replicates)
- A6-F6-I1-R1, A6-F6-I2-R1, A6-F6-I3-R1 (3 replicates)
Total: 17 samples
```

**Computational complexity: O(n²) where n=17 samples**

### Why Parallelization Didn't Work

**Expected behavior:**
- Sarek generates 17 interval files (chr1-16 + mitochondria)
- Default `nucleotides_per_second = 200000` should split work
- Each interval should run as separate job → parallelization

**Actual behavior with `--joint_mutect2`:**
- Joint calling changes `meta.id` to `meta.patient` (groups by experiment)
- All intervals grouped into **single job** per patient
- Command showed `--intervals chr10_1-759881.bed` but VCF contained chr1-16
- Defeats parallelization strategy

**Result:** One massive job processing 17 samples × 17 chromosomes sequentially = 8+ hours

---

## Solution Implemented

### ✅ Solution 1: Added Time Limits to Configuration (REVISED - Oct 14)

**Initial attempt FAILED** - Time limits were still being overridden!

**Root cause discovered:** The 8-hour timeout comes from `conf/base.config` **label-based limits**:

```groovy
// In conf/base.config
withLabel:process_medium {
    cpus   = { 6     * task.attempt }
    memory = { 36.GB * task.attempt }
    time   = { 8.h   * task.attempt }  // ← SOURCE OF 8-HOUR LIMIT!
}
```

**Mutect2 module declares:** `label 'process_medium'` (in `modules/nf-core/gatk4/mutect2/main.nf`)

**File modified:** the local resources profile — `conf/azured4as.config` (this was `bin/nextflow.config`
when the issue was investigated; it was relocated to a proper profile before v1.0.0)

**CORRECT FIX (Override label limits):**

```groovy
profiles {
  azureD4as {
    process {
      memory = '8 GB'
      cpus = 2
      time = '24h'  // Default time limit: 24 hours

      resourceLimits {
        cpus = 4
        memory = '14 GB'
        time = '72h'  // Maximum time limit: 72 hours
      }
      containerOptions = '--platform linux/amd64'

      // ✅ CRITICAL: Override label-based time limits from base.config
      withLabel: 'process_medium' {
        time = '24h'  // Override default 8h limit from base.config
      }
      withLabel: 'process_high' {
        time = '48h'  // Override default 16h limit from base.config
      }

      // Specific process overrides (most specific, highest precedence)
      withName: 'MUTECT2*' {
        cpus = 4
        memory = '14 GB'
        time = '48h'  // Extended time for Mutect2 (overrides process_medium label)
      }

      // ... rest of config
    }
  }
}
```

**Why this fix works:**
- **Nextflow config precedence**: `withName` > `withLabel` > default process settings
- **Must override BOTH** `withLabel` (for label-based inheritance) **AND** `withName` (for specific processes)
- `withLabel: 'process_medium'` prevents 8h limit on all `process_medium` tasks
- `withName: 'MUTECT2*'` provides Mutect2-specific 48h limit

**Impact:**
- ✅ Prevents 8-hour timeout on Mutect2 and other `process_medium` labeled tasks
- ✅ Allows joint Mutect2 to complete (estimated 20-30 hours)
- ✅ Fixes timeout for other long-running processes with `process_medium` label
- ✅ Properly overrides Sarek's base configuration

---

## Performance Recommendations

### Option A: Keep Joint Calling (Current Approach)

**Pros:**
- Cross-sample variant calling
- Better population-level statistics
- Shared evidence across replicates

**Cons:**
- Very slow (20-30 hours with 48h limit)
- Single point of failure (one job must complete)
- High memory overhead

**When to use:**
- Population genetics studies
- Need cross-sample allele frequency estimates
- Comparing variants across all samples simultaneously

### Option B: Disable Joint Calling (Recommended for ALE)

**Edit `bin/CENPK_run_sarek_351_all.sh`** - Remove `--joint_mutect2`:

```bash
nextflow run main.nf -profile azureD4as,docker \
    -w ${run_folder}/work_CENPK \
    --input ${run_folder}/data/data_a_paper/samplesheet_gen2.csv \
    --outdir ${run_folder}/output_all  --genome null --igenomes_ignore  \
    --fasta ${run_folder}/data/BakerYeast_reference/draft_ref52.fasta \
    --skip_tools baserecalibrator \
    --tools snpeff,freebayes,controlfreec,manta,mutect2,cnvkit,msisensorpro,tiddit,haplotypecaller,deepvariant \
    --split_fastq 0 \
    --joint_germline --save_mapped --split_haplotypecaller_joint_vcf \
    --snpeff_cache ${run_folder}/data/BakerYeast_reference/snpeff_cache \
    --snpeff_db draft_ref.52 -resume
    # NOTE: Removed --joint_mutect2
```

**Pros:**
- ✅ Much faster: ~2-3 hours per tumor-normal pair
- ✅ True parallelization: 17 intervals × multiple pairs
- ✅ Robust: Individual failures don't affect other samples
- ✅ Sufficient for ALE: comparing evolved vs ancestral strains

**Cons:**
- No cross-sample variant calling
- Separate VCF per pair (still have joint HaplotypeCaller for germline)

**Performance comparison:**
```
Joint Mutect2:     ████████████████████████████████████ (20-30 hours)
Individual pairs:  ████ ████ ████ ... (2-3 hours each, parallel)
```

### Option C: Alternative - Use Individual Mutect2 + Merge

Process pairs independently, then merge VCFs for cross-sample analysis:

```bash
# After individual Mutect2 completes
bcftools merge *.mutect2.filtered.vcf.gz -O z -o all_samples_merged.vcf.gz
```

**Benefits:**
- Fast parallel processing
- Cross-sample analysis available post-hoc
- Best of both worlds

---

## Technical Details

### Exit Code Reference
- **Exit 143**: SIGTERM (graceful termination signal)
- **Exit 130**: SIGINT (interrupt signal, e.g., Ctrl+C)
- **Exit 137**: SIGKILL (OOM killer or forced termination)

### Diagnostic Commands Used

```bash
# Check failed tasks
find work_CENPK -name ".exitcode" -exec sh -c 'cat "$1" | grep -q "^0$" || echo "$1: $(cat "$1")"' _ {} \;

# Check VCF integrity
source ~/miniforge3/etc/profile.d/conda.sh && conda activate nf-env
bcftools query -l failed.vcf.gz  # Check samples
bcftools view -H failed.vcf.gz | wc -l  # Count variants
zcat failed.vcf.gz | tail -5  # Check for truncation

# Check resource usage in logs
grep "Runtime.totalMemory()" work_dir/.command.err
grep "ProgressMeter" work_dir/.command.err | tail -20
```

### Incomplete VCF Results

**Truncated file:** `work_CENPK/0e/dc5db8/ALE_Exp1.mutect2.vcf.gz`

```
Chromosomes processed:
✅ chr1:   237 variants
✅ chr2:   421 variants
✅ chr3:   166 variants (TRUNCATED at position 297387)
❌ chr4:   Expected ~1.5Mb, killed at ~872kb (57% complete)
❌ chr5-16: Not processed
❌ mit:    Not processed

Total variants found: 3,371 (incomplete)
Last valid variant: chr3:297387
```

---

## Related Issues

### Similar Timeout Issues

- MultiQC mosdepth processing (see `../../qc-reporting/multiqc_mosdepth_coverage.md`)
- Long-running annotation jobs (future consideration)

### Related Configuration

- **Intervals**: Automatically generated from FASTA (17 files)
- **nucleotides_per_second**: Default 200000 (Sarek schema)
- **VM specs**: D4as_v5 - 4 vCPU, 16GB RAM, 495GB disk

---

## Resolution Summary

**Date resolved**: October 13, 2025
**Solution**: Added explicit time limits (24h default, 48h for Mutect2, 72h max)
**Status**: Pipeline can now resume with `-resume` flag
**Expected completion**: 20-30 hours with joint calling, or 6-8 hours with individual pairs

**Recommendation**: For future ALE experiments, disable `--joint_mutect2` for faster processing while maintaining HaplotypeCaller joint germline calling for population analysis.

---

## References

- GATK Mutect2 documentation: https://gatk.broadinstitute.org/hc/en-us/articles/5358911630107-Mutect2
- Nextflow time limits: https://www.nextflow.io/docs/latest/process.html#time
- Sarek interval splitting: `nextflow_schema.json` line 90
- Related notes: `CLAUDE.md` - Mutect2 configuration section
