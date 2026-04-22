# Fix 7: MultiQC Crash from Empty Map `{}` in Software Versions YAML

**Date**: 2026-04-22
**Affects**: nf-core/sarek 3.5.1 (fixed in 3.8.1)
**Symptom**: Pipeline fails at MultiQC step with `UnboundLocalError`

---

## Error

```
File "/usr/local/lib/python3.12/site-packages/multiqc/core/software_versions.py", line 87, in load_versions_from_config
    if not isinstance(versions_from_one_file, dict):
                      ^^^^^^^^^^^^^^^^^^^^^^
UnboundLocalError: cannot access local variable 'versions_from_one_file' where it is not associated with a value
```

MultiQC 1.25.1 crashes when parsing `nf_core_sarek_software_mqc_versions.yml` that contains a bare `{}` entry (empty YAML map).

## Root Cause

**File**: `subworkflows/local/bam_variant_calling_germline_controlfreec/main.nf:43`

```groovy
# BEFORE (buggy — sarek 3.5.1 original)
ch_versions = ch_versions.mix(MAKEGRAPH2.out.versions.ifEmpty([]))
```

When MAKEGRAPH2 doesn't run (no BAF files because no SNP database), `.ifEmpty([])` injects an empty Java ArrayList `[]` into the versions channel. The processing chain:

1. `processVersionsFromYAML` receives `[]` (an ArrayList, not a Path)
2. `yaml_file instanceof java.nio.file.Path` → false, so `content = yaml_file` (the list itself)
3. `yaml.load((String) content)` → `yaml.load("[]")` → empty ArrayList
4. `.collectEntries { ... }` on empty list → `[:]` (empty map)
5. `yaml.dumpAsMap([:]).trim()` → `{}`
6. `{}` gets written to the merged versions YAML
7. MultiQC 1.25.1 can't parse `{}` → `UnboundLocalError`

**Why no BAF files**: Control-FREEC requires a SNP database (e.g., dbSNP) to generate B-Allele Frequency files. Custom yeast genomes have no such database, so BAF is never produced, MAKEGRAPH2 never runs, and the `.ifEmpty([])` triggers.

**Why the test run passed**: `bin/test_nf.sh` doesn't include `controlfreec` in `--tools`, so this code path never executes.

## Fixes Applied

### Fix A: Root cause — remove `.ifEmpty([])`

**File**: `subworkflows/local/bam_variant_calling_germline_controlfreec/main.nf:43`

```groovy
# AFTER (fixed)
ch_versions = ch_versions.mix(MAKEGRAPH2.out.versions)
```

Mixing an empty channel is a no-op in Nextflow — no need for `.ifEmpty()`.

**Note**: This fix only takes effect on clean runs (not `-resume`), because `-resume` replays cached channel state from prior runs.

### Fix B: Defensive filter — strip empty maps from versions channel

**File**: `subworkflows/nf-core/utils_nfcore_pipeline/main.nf:119`

```groovy
# BEFORE
def softwareVersionsToYAML(ch_versions) {
    return ch_versions.unique().map { version -> processVersionsFromYAML(version) }
        .unique().mix(Channel.of(workflowVersionToYAML()))
}

# AFTER
def softwareVersionsToYAML(ch_versions) {
    return ch_versions.unique().map { version -> processVersionsFromYAML(version) }
        .filter { it && it != '{}' }
        .unique().mix(Channel.of(workflowVersionToYAML()))
}
```

This filter runs in Groovy (not a cached Nextflow process), so it takes effect even with `-resume`. It catches any empty map entries regardless of source.

## Same Bug Exists in Other Controlfreec Subworkflows

The `.ifEmpty([])` pattern also exists in:
- `subworkflows/local/bam_variant_calling_somatic_controlfreec/main.nf:66`
- `subworkflows/local/bam_variant_calling_tumor_only_controlfreec/main.nf:43`

These are not active in our pipeline (all samples treated as normal), but should be fixed for completeness. The defensive filter (Fix B) protects against them.

## Status in Upstream Sarek

- **sarek 3.5.1**: Has `.ifEmpty([])` bug in all three controlfreec subworkflows
- **sarek 3.8.1**: Fixed — uses plain `.mix(MAKEGRAPH2.out.versions)` without `.ifEmpty([])`

## Interaction with `-resume` and `collectFile(storeDir: ...)`

The versions YAML is generated via:

```groovy
softwareVersionsToYAML(versions)
    .collectFile(storeDir: "${params.outdir}/pipeline_info",
                 name: 'nf_core_sarek_software_mqc_versions.yml',
                 sort: true, newLine: true)
```

Key caching layers:
1. **`storeDir`**: Caches the output file at `output_all/pipeline_info/`. If this file exists, Nextflow skips regeneration entirely.
2. **`collect-file/` hash cache**: In `work_CENPK/collect-file/`, Nextflow caches the file list by content hash.

When debugging, both must be deleted for fixes to take effect:

```bash
rm -f output_all/pipeline_info/nf_core_sarek_software_mqc_versions.yml
rm -rf work_CENPK/collect-file/
```

Fix A alone doesn't help with `-resume` because the cached channel state still contains `[]`. Fix B (the filter) works because it runs in the Groovy function, not in a cached process.

## Seqera Cloud Considerations

- These fixes have NOT been applied to the `worktree-seqera-cloud` branch
- The Seqera test params (`conf/params_seqera_test.yml`) should be checked for `controlfreec` in `--tools`
- If controlfreec is not in the Seqera test tools, the bug won't trigger there
- A Seqera Cloud test run (Step 6) should validate before applying fixes to the worktree
- Upgrading to sarek 3.8.1 eliminates both this bug and the `processVersionsFromYAML` method resolution issue
