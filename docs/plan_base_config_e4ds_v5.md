# Plan: Right-size base.config for E4ds_v5 and eliminate dependency on external config

## Context

The Seqera Cloud runs failed because `conf/seqera_azure.config` was not loaded — the resource caps (4 CPUs, 14 GB) never applied, so processes used `base.config` defaults designed for HPC clusters (e.g., BWAMEM1_MEM: 24 CPUs, 30 GB). Rather than relying on users correctly pasting config into the Seqera UI, we'll bake the correct resource limits directly into `base.config` on this branch.

Additionally, breseq needs more memory than D4s_v3 (16 GB) can provide. Upgrading the target VM to **E4ds_v5 (4 vCPU, 32 GB, ~$0.29/hr)** gives breseq comfortable headroom while keeping costs reasonable.

## Approach: Modify `base.config` directly

**Why not keep `seqera_azure.config` as the primary config?**
- It requires manual paste into Seqera UI "Nextflow config file" field
- Previous runs proved this is error-prone — config wasn't loaded
- `base.config` is always loaded via `includeConfig 'conf/base.config'` in `nextflow.config`

**Why not create a new profile?**
- Seqera UI passes `-profile docker` — adding another profile requires changing the launch config
- A profile would still require manual action in the Seqera UI
- This is a dedicated branch (`worktree-seqera-cloud`) for cloud deployment, so modifying base.config is safe

## Changes

### 0. `subworkflows/nf-core/utils_nfcore_pipeline/main.nf` — Adopt 3.8.1 approach for Fix 4

Replace our verbose Fix 4 (null checks + `Files.newInputStream`) with the cleaner 3.8.1 pattern that avoids file I/O entirely:

```groovy
// 3.8.1 approach — yaml_file is already file content (string), no stream needed
def processVersionsFromYAML(yaml_file) {
    def yaml = new org.yaml.snakeyaml.Yaml()
    def versions = yaml.load(yaml_file).collectEntries { k, v -> [k.tokenize(':')[-1], v] }
    return yaml.dumpAsMap(versions).trim()
}
```

**Why this works**: In `softwareVersionsToYAML` (line 145-146), the `.map { version -> processVersionsFromYAML(version) }` receives channel items. Nextflow auto-reads file content when a Path is used in a closure context with `yaml.load()`. The 3.8.1 version passes the content directly — no `FileInputStream`, no `toFile()`, no cloud path issues.

**Also**: Remove the 15 lines of commented-out old code (lines 116-127) left from the Fix 4 edit.

### 1. `modules/local/breseq/main.nf` — Change label from `process_medium` to `process_high`

Breseq is the most resource-intensive ALE tool — it runs alignment, junction prediction, and mutation calling in parallel with `-j ${task.cpus}`. Give it `process_high` to get maximum resources.

```groovy
// Line 3: change from
label 'process_medium'
// to
label 'process_high'
```

### 2. `conf/base.config` — Right-size for E4ds_v5 (4 vCPU, 32 GB)

Add `resourceLimits` block and differentiate medium vs high:

```groovy
process {
    // Resource limits for Azure Batch E4ds_v5 (4 vCPU, 32 GB)
    resourceLimits {
        cpus   = 4
        memory = 28.GB    // 32 GB VM - 4 GB OS/agent headroom
        time   = 72.h
    }

    // Global defaults (unchanged)
    cpus   = { 1      * task.attempt }
    memory = { 6.GB   * task.attempt }
    time   = { 4.h    * task.attempt }
    errorStrategy = { task.exitStatus in ((130..145) + 104) ? 'retry' : 'finish' }
    maxRetries    = 2          // was 1, increase for Azure transient failures

    // Label-based groups — differentiate medium vs high
    // process_single: 1 CPU, 6 GB   → stays (fits)
    // process_low:    2 CPU, 12 GB  → stays (fits)
    withLabel:process_medium {
        cpus   = { 4     * task.attempt }   // was 6, cap to VM max
        memory = { 16.GB * task.attempt }   // was 36 GB, moderate tasks
        time   = { 24.h  * task.attempt }   // was 8h, batch overhead
    }
    withLabel:process_high {
        cpus   = { 4     * task.attempt }   // was 12, cap to VM max
        memory = { 28.GB * task.attempt }   // was 72 GB, full VM for breseq/heavy callers
        time   = { 48.h  * task.attempt }   // was 16h, batch overhead
    }

    // Process-specific overrides:
    withName: 'BWAMEM1_MEM|BWAMEM2_MEM' {
        cpus   = { 4     * task.attempt }   // was 24
        memory = { 12.GB * task.attempt }   // was 30 GB, yeast needs < 4 GB
    }
    withName: 'FASTP' {
        cpus   = { 4     * task.attempt }   // was 12
        memory = { 4.GB  * task.attempt }   // unchanged
    }
    withName: 'MUTECT2*' {
        cpus   = 4
        memory = 12.GB
        time   = '48h'
    }
    withName: 'GATK4_CREATESEQUENCEDICTIONARY' {
        cpus   = 2
        memory = { 12.GB * task.attempt }
    }
}
```

**Summary of label differentiation:**
| Label | CPUs | Memory | Time | Key processes |
|-------|------|--------|------|--------------|
| `process_medium` | 4 | 16 GB | 24h | GATK4_MARKDUPLICATES, CNVKIT_BATCH |
| `process_high` | 4 | 28 GB | 48h | **BRESEQ**, HaplotypeCaller (heavy) |

### 3. `conf/seqera_azure.config` — Simplify to minimal overrides

Keep this file as a **lightweight supplement** (docker enablement + `custom_config_base` nulling), not the primary resource config. Remove the `resourceLimits` and process overrides since they're now in `base.config`.

```groovy
// Seqera Platform config — supplements base.config for Azure Batch
// Optional: paste into Seqera "Nextflow config file" if docker profile isn't sufficient
params.custom_config_base = null

docker {
    enabled    = true
    runOptions = '-u $(id -u):$(id -g)'
}
```

**Note**: The `docker` block is redundant if Seqera launches with `-profile docker`, but kept as a safety net.

### 4. `conf/params_seqera_test.yml` — No changes needed

Already updated with `seq_platform: "ILLUMINA"` in previous step.

### 5. `docs/seqera_cloud_deployment_checklist.md` — Update with new VM target

Update Fix 5 section and Step 6 to reflect E4ds_v5 target and base.config approach.

## Files to modify

| File | Change |
|------|--------|
| `subworkflows/nf-core/utils_nfcore_pipeline/main.nf` | Adopt 3.8.1 `processVersionsFromYAML`, remove commented-out code |
| `modules/local/breseq/main.nf` | Change label from `process_medium` to `process_high` |
| `conf/base.config` | Add `resourceLimits`, adjust labels/processes for E4ds_v5, bump maxRetries |
| `conf/seqera_azure.config` | Strip to docker + custom_config_base only |
| `docs/seqera_cloud_deployment_checklist.md` | Update VM target from D4s_v3 to E4ds_v5 |

## Seqera Azure Batch pool behavior and VM sizing rationale

### Key constraint: Seqera Batch Forge = single VM type per pool

Seqera's "Batch Forge" creates **one pool with a fixed VM type**. It does NOT use Nextflow's native `autoPoolMode` (which creates multiple pools per resource profile). All tasks run on the same VM size regardless of their resource requests.

**Additionally**: Azure Batch assigns **one Nextflow task per node**. A FastQC task requesting 1 CPU + 2 GB still occupies an entire VM. There is no task packing within Seqera Forge pools.

### Why E4ds_v5 (4 vCPU, 32 GB) and not larger

| Pool VM | Breseq fit | Light tasks (FastQC etc.) | Cost/hr |
|---------|-----------|---------------------------|---------|
| E4ds_v5 (32 GB) | 28 GB usable — sufficient for yeast (~12 Mb genome) | Wastes ~30 GB per node | ~$0.29 |
| E8ds_v5 (64 GB) | Comfortable headroom | Wastes ~62 GB per node | ~$0.58 |

Since each task gets a whole VM, oversizing the pool VM means **every lightweight task wastes the excess**. E4ds_v5 is the right balance: enough for breseq on yeast, not excessively wasteful for the many small tasks.

### Retry behavior with fixed VM size

Because `resourceLimits` caps memory at 28 GB (the VM ceiling), `memory = { 28.GB * task.attempt }` on `process_high` evaluates to 56 GB on retry but gets clamped back to 28 GB. Retries therefore only help with **transient Azure failures** (preemption, network), not OOM.

This is acceptable because:
- 28 GB is generous for breseq on yeast genomes
- `maxRetries = 2` targets exit codes 130-145 and 104 (transient/killed), not OOM

### Scaling path if breseq OOMs in the future

If a larger genome or dataset causes breseq to OOM at 28 GB:

1. **Simplest**: Change pool VM to E8ds_v5 in Seqera UI (accepts higher cost for all tasks)
2. **Targeted**: Create a second Seqera compute environment with E8ds_v5, route breseq via `queue` directive:
   ```groovy
   process { withName: 'BRESEQ' { queue = 'large-pool-env' } }
   ```
3. **Not available in Seqera Forge**: Native `autoPoolMode` with per-process VM selection (would require running Nextflow directly against Azure Batch)

## Local compatibility

`base.config` sets `resourceLimits` to 28 GB (E4ds_v5), but local D4as VM has only 16 GB.
**No conflict**: local runs use `-profile azureD4as,docker` which loads `bin/nextflow.config` with its own `resourceLimits { memory = '14 GB' }`. Profile-level `resourceLimits` override `base.config` — so local runs stay capped at 14 GB.

## Verification

1. **Grep for resourceLimits** — confirm definitions exist in both `base.config` (28 GB) and `bin/nextflow.config` (14 GB)
2. **Check config resolution** — `nextflow config -profile docker` should show 4 CPU / 28 GB limits (Seqera path)
3. **Check local resolution** — `nextflow config -profile azureD4as,docker` should show 4 CPU / 14 GB limits (local path)
4. **Seqera launch** — run without pasting any Nextflow config; base.config should handle everything
5. **Monitor via API** — verify BWAMEM1_MEM tasks get 4 CPUs, ≤28 GB (not 24/30)
