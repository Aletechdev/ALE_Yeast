# Understanding ext.prefix in Nextflow/nf-core Pipelines

**Date**: 2025-11-25
**Context**: Lessons learned from CNVkit MultiQC integration
**Relevance**: Critical for maintaining file naming conventions through multi-step workflows

## What is ext.prefix?

`ext.prefix` is a Nextflow configuration parameter used in nf-core modules to control output file naming. It overrides the default naming behavior of processes.

## Default Behavior Without ext.prefix

Most nf-core modules default to using `meta.id` as the filename prefix:

```groovy
process EXAMPLE_TOOL {
    script:
    def prefix = task.ext.prefix ?: "${meta.id}"
    """
    tool --input ${input} --output ${prefix}.result.txt
    """
}
```

**Default output**: `sample_name.result.txt`

## Why ext.prefix Matters

### Problem: Filename Suffix Loss in Multi-Step Pipelines

Consider this workflow:

```
Process A → sample.specific_suffix.txt
  ↓
Process B → sample.txt  ⚠️ Lost suffix!
```

**Without ext.prefix configuration**, intermediate suffixes get lost because:
1. Process A creates: `sample.specific_suffix.txt`
2. Process B receives `sample.specific_suffix.txt` as input
3. Process B uses default `prefix = meta.id = "sample"`
4. Process B creates: `sample.txt` (losing `.specific_suffix`)

### Real-World Example: CNVkit Pipeline

#### The Problem
```
CNVKIT_EXPORT
  ↓ creates: A0-F0-I1-R1.cnvcall.vcf
TABIX_BGZIP (without ext.prefix)
  ↓ creates: A0-F0-I1-R1.vcf.gz  ⚠️ Lost .cnvcall!
```

#### The Solution
```groovy
// In conf/modules/cnvkit.config
withName: 'CNVKIT_EXPORT' {
    ext.prefix = { "${meta.id}.cnvcall" }
}

withName: 'TABIX_BGZIP_CNVKIT' {
    ext.prefix = { "${meta.id}.cnvcall" }  // ← Preserves suffix
}
```

**Result**:
```
CNVKIT_EXPORT
  ↓ creates: A0-F0-I1-R1.cnvcall.vcf
TABIX_BGZIP (with ext.prefix)
  ↓ creates: A0-F0-I1-R1.cnvcall.vcf.gz  ✓ Suffix preserved!
```

## Common Use Cases

### 1. Preserving Tool-Specific Identifiers

Different variant callers need unique identifiers:

```groovy
withName: 'FREEBAYES' {
    ext.prefix = { "${meta.id}.freebayes" }
}

withName: 'HAPLOTYPECALLER' {
    ext.prefix = { "${meta.id}.haplotypecaller" }
}

withName: 'CNVKIT_EXPORT' {
    ext.prefix = { "${meta.id}.cnvcall" }
}
```

**Why**: MultiQC and downstream tools use filenames to distinguish between different variant callers on the same sample.

### 2. Maintaining Processing Stage Labels

```groovy
withName: 'FILTER_RAW' {
    ext.prefix = { "${meta.id}.raw" }
}

withName: 'FILTER_QUALITY' {
    ext.prefix = { "${meta.id}.quality_filtered" }
}
```

**Output**:
- `sample.raw.vcf`
- `sample.quality_filtered.vcf`

### 3. Preserving Comparison Labels (e.g., Tumor-Normal)

```groovy
withName: 'SOMATIC_CALLER' {
    ext.prefix = { "${meta.tumor_id}_vs_${meta.normal_id}" }
}
```

**Output**: `tumor_sample_vs_normal_sample.vcf`

## How ext.prefix Works with Different Modules

### Example 1: Simple Text Output

```groovy
process SIMPLE_TOOL {
    script:
    def prefix = task.ext.prefix ?: "${meta.id}"
    """
    echo "result" > ${prefix}.txt
    """
}
```

- Without config: `sample.txt`
- With `ext.prefix = { "${meta.id}.custom" }`: `sample.custom.txt`

### Example 2: File Extension Preservation (TABIX_BGZIPTABIX)

```groovy
process TABIX_BGZIPTABIX {
    script:
    def prefix = task.ext.prefix ?: "${meta.id}"
    """
    bgzip -c $input > ${prefix}.${input.getExtension()}.gz
    """
}
```

**Input**: `sample.cnvcall.vcf`

- Without config:
  - `prefix = "sample"`
  - `input.getExtension() = "vcf"`
  - Output: `sample.vcf.gz` ⚠️

- With `ext.prefix = { "${meta.id}.cnvcall" }`:
  - `prefix = "sample.cnvcall"`
  - `input.getExtension() = "vcf"`
  - Output: `sample.cnvcall.vcf.gz` ✓

### Example 3: Dynamic Prefixes from Input Files

```groovy
withName: 'PROCESS_FILES' {
    ext.prefix = { "${input.baseName}" }  // Uses input filename
}
```

**Input**: `data.filtered.bam`
**Output**: `data.filtered.result.txt`

## Configuration Best Practices

### 1. Consistency Across Related Processes

Always use the **same ext.prefix pattern** for processes in the same sub-workflow:

```groovy
// ✓ GOOD: Consistent naming through pipeline
withName: 'CNVKIT_EXPORT' {
    ext.prefix = { "${meta.id}.cnvcall" }
}
withName: 'TABIX_BGZIP_CNVKIT' {
    ext.prefix = { "${meta.id}.cnvcall" }
}
withName: 'VCF_STATS_CNVKIT' {
    ext.prefix = { "${meta.id}.cnvcall" }
}

// ✗ BAD: Inconsistent naming causes confusion
withName: 'CNVKIT_EXPORT' {
    ext.prefix = { "${meta.id}.cnvcall" }
}
withName: 'TABIX_BGZIP_CNVKIT' {
    // No prefix configured - uses default meta.id
}
// Output: cnvcall.vcf → sample.vcf.gz (lost suffix!)
```

### 2. Use Closures for Dynamic Values

```groovy
// ✓ GOOD: Closure allows access to meta and task variables
ext.prefix = { "${meta.id}.${meta.sample_type}" }

// ✗ BAD: Static string doesn't evaluate variables
ext.prefix = "${meta.id}.${meta.sample_type}"  // Literal string!
```

### 3. Document Naming Conventions

In your config files, add comments explaining the naming scheme:

```groovy
withName: 'VARIANT_CALLER' {
    // Format: <sample_id>.<caller_name>
    // Example: A0-F0-I1-R1.freebayes.vcf
    ext.prefix = { "${meta.id}.freebayes" }
}
```

## Debugging ext.prefix Issues

### Symptom 1: Files Have Wrong Names

**Check**: Is ext.prefix configured for the process?

```bash
# Find the process configuration
grep -r "withName.*YOUR_PROCESS" conf/modules/
```

### Symptom 2: Downstream Tools Can't Find Files

**Issue**: File naming changed between processes

**Solution**: Trace the naming through the pipeline:

```bash
# Check work directory for actual filenames
ls work/XX/XXXXXXXX/*.vcf*

# Compare with expected names in logs
grep "ERROR" .nextflow.log
```

### Symptom 3: MultiQC Shows Duplicate or Missing Samples

**Issue**: Sample identifiers not unique

**Solution**: Each variant caller/tool needs a unique suffix:

```groovy
withName: 'TOOL_A' {
    ext.prefix = { "${meta.id}.toolA" }
}
withName: 'TOOL_B' {
    ext.prefix = { "${meta.id}.toolB" }
}
```

## Common Pitfalls

### 1. Forgetting to Configure All Processes in a Chain

```groovy
// ✗ INCOMPLETE
withName: 'PROCESS_A' {
    ext.prefix = { "${meta.id}.custom" }
}
// PROCESS_B not configured - will lose .custom suffix!
```

### 2. Using Static Strings Instead of Closures

```groovy
// ✗ WRONG: This is a literal string, not evaluated
ext.prefix = "${meta.id}.suffix"

// ✓ CORRECT: Closure allows runtime evaluation
ext.prefix = { "${meta.id}.suffix" }
```

### 3. Not Accounting for File Extensions

Some modules use `input.baseName` or `input.getExtension()`:

```groovy
// If input is "sample.cnvcall.vcf"
input.baseName          // → "sample.cnvcall"
input.simpleName        // → "sample"
input.getExtension()    // → "vcf"
input.name              // → "sample.cnvcall.vcf"
```

Choose the right one for your needs!

## Nextflow Resume and ext.prefix

⚠️ **Important**: Changing ext.prefix in config does **not** automatically invalidate cached results!

When you modify ext.prefix:
1. **Clear affected work directories**: `rm -rf work/XX/XXXXXX/`
2. **Or run without `-resume`**: Forces re-execution
3. **Or use a new work directory**: `-w work_new/`

## Real-World Impact: The CNVkit Case Study

### Before ext.prefix Configuration
```
Pipeline ran successfully ✓
Files created ✓
MultiQC report generated ✓
CNVkit samples in MultiQC ✗
```

**Why**: Files were named `sample.vcf.gz` instead of `sample.cnvcall.vcf.gz`, so:
- MultiQC couldn't distinguish CNVkit from other samples
- Sample names conflicted with default naming
- Stats were generated but not included in report

### After ext.prefix Configuration
```
Pipeline ran successfully ✓
Files named sample.cnvcall.vcf.gz ✓
MultiQC report generated ✓
CNVkit samples in MultiQC ✓
```

**Result**: 7 CNVkit samples now visible in MultiQC with proper identification

## Summary Checklist

When adding a new tool to a pipeline:

- [ ] Define ext.prefix for the main tool process
- [ ] Define ext.prefix for ALL downstream processes that handle the output
- [ ] Use closures `{ }` for dynamic values
- [ ] Ensure naming is consistent across the sub-workflow
- [ ] Test that filenames are correct at each step
- [ ] Verify MultiQC can identify samples correctly
- [ ] Document the naming convention in comments
- [ ] Clear cached results after config changes

## References

- [nf-core modules guidelines](https://nf-co.re/docs/contributing/modules)
- [Nextflow process directives](https://www.nextflow.io/docs/latest/process.html#directives)
- CNVkit MultiQC Integration: `docs/archive/cnvkit/CNVKIT_MULTIQC_INTEGRATION.md`

## Key Takeaway

> **ext.prefix is not just about naming - it's about maintaining semantic meaning through multi-step workflows. File suffixes carry information about tool identity, processing stage, and comparison context. Losing this information breaks downstream analysis and reporting.**

When in doubt, preserve the suffix!
