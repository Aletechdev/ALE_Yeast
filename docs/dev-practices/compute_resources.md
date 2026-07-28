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
| `conf/mymachine.config` | **Template** to copy for any other machine — clamp only, params-free. A `-c` file, **not** a registered profile. | any local machine |
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

## Config precedence — what overrides what

Two separate precedence chains matter here. Rows marked ✅ were verified on this repo with
Nextflow 25.10.4; the rest is Nextflow's documented order.

### 1. Where a setting comes from (highest wins)

| # | Source | Notes |
|---|--------|-------|
| 1 | CLI `--param value` | ✅ beats everything below. Pipeline **params only** — not process directives. |
| 2 | `-params-file` | params only. |
| 3 | **`-c my.config`** | ✅ **outranks `-profile`.** Loaded after the project config, so a params-bearing `-c` will silently clobber a profile's `input`/`tools`. Keep resource `-c` files **params-free**. |
| 4 | `nextflow.config` in the launch dir | |
| 5 | `nextflow.config` in the project dir — **this is where `profiles {}` lives** | Within `-profile a,b`, **later profiles win** on conflicts. |
| 6 | `$HOME/.nextflow/config` | |
| 7 | Directives written in the process body (`main.nf`, modules) | See the twist below. |

### 2. How a process directive is resolved (independent of the above)

Not everything that sets `memory` behaves the same way — verified with a probe process declaring
`memory 16.GB` / `cpus 8` in its body:

| Mechanism | Effect on a script-body directive | Result |
|-----------|-----------------------------------|--------|
| `process { withName: 'X' { memory = '1.GB' } }` | **overrides** it | ✅ resolved to 1 GB |
| `process { resourceLimits = [...] }` | **clamps** it (applied last, to whatever was requested) | ✅ 16 GB → 4 GB |
| `process { memory = '1.GB' }` (unqualified) | only a **default** — the script directive wins | ✅ stayed 16 GB → unschedulable |

**This is why the clamp is the portable knob.** `resourceLimits` is applied *after* every other
mechanism, including the retry escalation `{ 16.GB * task.attempt }`, so it caps requests no matter
where they came from. An unqualified `process { memory }` does not.

### 3. Can it be passed on the command line? **No — `resourceLimits` needs a `-c` file.**

`nextflow run` does accept `-process.<key>=<value>`, but it is unusable here:

- **It cannot express a map.** `-process.resourceLimits='[cpus:2,memory:4.GB]'` is parsed as a
  **String**, and the run then dies with
  `No signature of method: java.lang.String.get() ... values: [memory]` (verified).
- **Even for scalars it only sets a default**, i.e. row 3 of the table above — a module's own
  `memory` directive still wins (verified).

There is also **no `--max_cpus` / `--max_memory` param** in this pipeline: `base.config` hard-codes
`resourceLimits`. Making it param-driven is a deliberate post-1.0.0 item (see the bottom of this page).

So: **a small `-c` file is the supported way to fit the pipeline to a machine.** It's three lines.

## Porting to another machine

**Do not use `-profile azureD4as` on anything but the 16 GB dev VM** — it hard-codes that machine's
ceilings and per-task tuning. Either of the two options below; **`base.config` (the cloud default) is
never touched** in either.

### Option A — clamp-only `-c` (recommended; nothing to author or register)

The **only** thing a new machine strictly needs is the clamp. A ready-to-copy template ships as
[`conf/mymachine.config`](../../conf/mymachine.config) — commented, with the optional executor-pool
and per-task-tuning blocks left commented out. It is deliberately **not** registered in
`nextflow.config`'s `profiles {}` block, so it only loads when you pass it:

```bash
cp conf/mymachine.config conf/$(hostname).config     # then edit cpus + memory
nextflow -c conf/$(hostname).config run main.nf -profile ottilie_test,docker \
    --outdir ./output_ottilie_test --generate_reports
```

Stripped of comments, the load-bearing part is three lines:

```groovy
process {
    resourceLimits = [ cpus: 8, memory: '28.GB', time: '72.h' ]   // vCPUs, RAM − ~2 GB headroom
}
```

- **Skip the executor pool.** With no `executor` block, Nextflow's default local executor
  **auto-detects the host's CPUs/RAM** and sizes concurrency itself — which is what you want on an
  unfamiliar machine. (This is exactly how the nf-test path runs; see below.)
- **A params-free `-c` does not clobber profiles.** Verified: with the config above,
  `-profile ottilie_test` keeps its `input`/`tools`/`fasta`. Only add params to a `-c` if you intend
  them to outrank the profile — `-c` wins over `-profile`.
- Same resolved `resourceLimits` as the full `azureD4as` profile, without its pool or tuning.

### Option B — a named profile (for a machine you'll use repeatedly)

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

> ⚠️ **If you set an `executor` pool by hand, keep `executor.memory / process.memory ≥ 2.`** A pool
> only slightly larger than a single task's request fits exactly one task and can **deadlock** the
> local scheduler ("No more task to compute"). Full symptoms and diagnosis:
> [`docs/usage/nextflow_local_executor_deadlock.md`](../usage/nextflow_local_executor_deadlock.md).
> Option A sidesteps this entirely by not setting a pool.

| Machine | resourceLimits memory | cpus |
|---------|-----------------------|------|
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

## nf-test resources — clamp only (no pool)

Running the suite through **nf-test** is a fourth context, and it fits the machine differently from a
`nextflow run`. The ALE tests launch with `-c tests/nf-test-ottilie.config`, which sets
`profile "ottilie_test,docker"` — **deliberately without `azureD4as`**. So of the two layers above,
only the **clamp** applies:

- **`resourceLimits`** comes from `tests/ottilie_nftest_resources.config` (the nf-test config's
  `configFile`): `[cpus:4, memory:'14.GB', time:'24.h']`. This is the whole resource story for a test run.
- **No `executor` pool** and **no per-task tuning** — those live in `conf/azured4as.config`, which the
  test path doesn't load. Concurrency falls back to Nextflow's **default local executor** (it
  auto-detects the host's CPUs/RAM). For the 2-sample ottilie run that's plenty; the clamp is what
  guarantees every task stays schedulable.

Why a separate clamp-only file instead of reusing `azureD4as`? Its `executor='local'` pool is
full-run machinery the test doesn't want, and a **params-bearing `-c` would clobber** the
`ottilie_test` profile's input/tools (`-c` outranks profiles — verified during nf-test wiring). A
`resourceLimits`-only config caps resources without touching params.

**Porting a test run to another machine:** same idea as porting a VM profile, but edit the two numbers
in `tests/ottilie_nftest_resources.config` (the [porting table](#porting-to-another-machine) applies
directly). For a CI box that differs from the dev VM, add a second
`tests/ottilie_nftest_resources_ci.config` and a matching `tests/nf-test-ottilie-ci.config` whose
`configFile` points at it — keeping the dev-VM config untouched.

## Summary — the three orthogonal axes

A run = **dataset** × **resources** × **engine**, each an independent profile:

- **dataset:** `ottilie_test` (or your input params)
- **resources:** `azureD4as` (this dev VM only) / a clamp-only `-c` / a new per-machine profile /
  cloud compute environment
- **engine:** `docker` / `singularity` / `conda`

e.g. `-profile ottilie_test,azureD4as,docker` on the dev VM, or
`-c mymachine.config -profile ottilie_test,docker` anywhere else. Porting = swap the **resources**
axis only.

## Post-1.0.0 follow-up (deferred, deliberate)

Make the ceiling a single param (`--max_cpus` / `--max_memory`) that `base.config`'s `resourceLimits`
reads, so porting is two CLI numbers instead of a profile. Deferred because it edits the shared
`base.config` the cloud release depends on, and the nf-test (which uses its own `resourceLimits`)
wouldn't catch a regression — it needs its own cloud + VM validation cycle.
