# Compute resources & deployment

How the pipeline is fitted to a machine — the dev VM, another VM, or Seqera cloud. This is the
authoritative reference for the resource config; older docs may still mention the pre-relocation
`bin/nextflow.config` path.

## The model: two layers (+ one optional)

Fitting a run to a machine uses two independent mechanisms — **you need both**:

1. **Executor pool** (`executor { cpus; memory }`) — the *total* budget the local scheduler works
   within. Nextflow only runs as many tasks *concurrently* as fit. Stops **over-subscription**
   (starting more tasks than RAM allows → OOM). Local runs only; on cloud the compute environment
   owns this.
2. **`resourceLimits` (the clamp)** (`process.resourceLimits = [...]`) — caps any *single* task's
   request. base.config asks `process_medium = 16 GB`; the clamp lowers it to the ceiling so it can
   actually be scheduled. Stops a **single over-request** (incl. retry escalation `X * task.attempt`
   → 56 GB) from becoming unschedulable.
3. *(Optional)* **per-task tuning** (`withLabel`/`withName { memory }`) — trims requests to observed
   peaks so more tasks pack in. Pure throughput; not correctness. The fragile, machine-specific bit.

Mnemonic: **pool** = don't run too many at once; **clamp** = don't let one ask for more than exists;
**tuning** = pack more in for speed.

## Where the config lives

| File | Role | Applies to |
|------|------|-----------|
| `conf/base.config` | Per-tool requests (labels + names) **and** the default `resourceLimits` — sized for **Azure Batch E4ds_v5 (4 vCPU / 32 GB)**, the cloud pool. | everywhere (the base) |
| `conf/azured4as.config` → `-profile azureD4as` | Local **dev-VM** override: executor pool + `resourceLimits` **14 GB** (16 GB VM − 2 GB headroom) + per-task tuning. | local dev VM only |
| `conf/seqera_azure.config` | Seqera supplement (disables institutional-config fetch; docker safety net). Pasted into the Seqera "Nextflow config" field. **Not** a profile. | cloud |

Profiles are registered in the main `nextflow.config` `profiles {}` block (e.g.
`azureD4as { includeConfig 'conf/azured4as.config' }`), so `-profile azureD4as` works with **no `-c`**.

## Ensuring a machine can run it through

Two things must hold — one guaranteed, one empirical:

- **Requests fit (guaranteed):** `resourceLimits ≤ machine` ⟹ no task can ever *request* more than
  exists ⟹ always schedulable. Automatic.
- **Actual usage fits (empirical):** the heaviest task's real peak must be ≤ the ceiling. Measure it
  from `pipeline_info/execution_report_*.html` → **peak_rss** per task. The tuning comments in
  `conf/azured4as.config` are exactly these measurements (BWA-MEM 5.0 GB, MARKDUPLICATES 7.1 GB, …);
  for the yeast data all peaks are <8 GB, so 14 GB is comfortable.

Safety nets already in place: `errorStrategy='retry'` with `memory = { X * task.attempt }` (OOM →
retry with more, clamped to the ceiling), and 8 GB swap on the dev VM.

**Hard limit:** if a task's *actual* peak > the ceiling (real human WGS), clamping just OOMs — no
config fixes insufficient RAM. That's the signal to use a bigger machine / cloud. This VM is sized
for the yeast test data.

## Porting to another VM

The per-VM config is isolated in a profile — **`base.config` (the cloud default) is never touched**.

1. Copy `conf/azured4as.config` → `conf/<machine>.config`.
2. Change the two ceilings to the new machine (RAM − ~2 GB headroom, and vCPUs):
   ```groovy
   executor { name='local'; cpus=<vcpus>; memory='<RAM-2>.GB' }
   process  { resourceLimits = [ cpus:<vcpus>, memory:'<RAM-2>.GB', time:'72.h' ] }
   ```
   Drop or re-measure the per-task tuning (`withLabel`/`withName`) — `resourceLimits` alone keeps it
   *correct*; the tuning only affects VM throughput and is specific to the old machine's peaks.
3. Register the profile in `nextflow.config`: `<machine> { includeConfig 'conf/<machine>.config' }`.
4. Run `-profile ottilie_test,<machine>,docker`.

| Machine | executor / resourceLimits memory | cpus |
|---------|----------------------------------|------|
| D4as_v5 (16 GB) — `azureD4as` | `14.GB` | 4 |
| D8as_v5 (32 GB) | `28.GB` | 8 |
| Big box (256 GB) | `240.GB` | 32 |

## Seqera cloud — why it's different (and more involved)

On cloud you **do not** use `azureD4as` (its `executor='local'` would pin everything to the head
node). Resources come from **`base.config` + the Seqera compute environment**:

- **Compute environment / Batch Forge** provisions the Azure Batch pool. Batch Forge uses a **single
  VM type per pool** — every task runs on that machine type (default target: **E4ds_v5**, which is why
  `base.config` is sized for it). Pick a bigger machine type for WGS; `resourceLimits` in base.config
  should match (or exceed) that machine so tasks aren't needlessly clamped.
- **`resourceLimits` vs the pool:** on cloud, `resourceLimits` still clamps per-task requests to the
  chosen machine type; the *pool* (concurrency) is Batch's, not a local `executor` block.
- **Container registry credentials:** the report image `ale-reports` is public Docker Hub (anonymous
  pull works), but the **ghcr mirror is private** — register a read-only container-registry credential
  in the Seqera workspace if you pin ghcr. See
  [`generate_index_container.md`](../generate_mutation_report/generate_index_container.md).
- **`conf/seqera_azure.config`:** paste into the Seqera "Nextflow config file" field if the plain
  `docker` profile isn't enough — it disables the nf-core institutional-config fetch (absent in this
  repo) and adds a docker UID/GID safety net.
- **Nextflow version:** run on **25.10.x**; 26.04+ fails to parse `nextflow.config` (see the CHANGELOG
  known-limitations). Seqera's functionality matrix still supports 25.10.x.

For the full cloud step-by-step (compute environment setup, Batch Forge, launch), see
[`docs/seqera_cloud/seqera_cloud_deployment_checklist.md`](../seqera_cloud/seqera_cloud_deployment_checklist.md)
and [`docs/seqera_cloud/azure_batch_recommendations.md`](../seqera_cloud/azure_batch_recommendations.md).

## Summary — the three orthogonal axes

A run = **dataset** × **resources** × **engine**, each an independent profile:

- **dataset:** `ottilie_test` (or your input params)
- **resources:** `azureD4as` (local VM) / a new per-VM profile / cloud compute environment
- **engine:** `docker` / `singularity` / `conda`

e.g. `-profile ottilie_test,azureD4as,docker`. Porting = swap the **resources** axis only.

## Post-1.0.0 follow-up (deferred, deliberate)

Make the ceiling a single param (`--max_cpus` / `--max_memory`) that `base.config`'s `resourceLimits`
reads, so porting is two CLI numbers instead of a profile. Deferred because it edits the shared
`base.config` the cloud release depends on, and the nf-test (which uses its own `resourceLimits`)
wouldn't catch a regression — it needs its own cloud + VM validation cycle.
