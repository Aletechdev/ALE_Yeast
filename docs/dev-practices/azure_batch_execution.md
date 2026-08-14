# Running the pipeline on Azure Batch — execution gotchas

> **Status (2026-08-06): validated end-to-end for BOTH a local head job and a Seqera Platform head job.**
>
> - **Local head job** (2026-08-03): 138 tasks (+32 cached), **540 blobs** published to
>   `az://aletest/ottilie-azurebatch-out/`. This is the **reference baseline**.
> - **Seqera Platform head job** (2026-08-06, run `3C5zYMYY5M32dO`): **170/170 tasks, 0 failed**, and all
>   **9 cohort deliverables byte-identical** to that baseline — the acceptance criterion, met. Every
>   remaining difference falls in a known non-determinism class (§11).
>
> Both run under the **Entra service principal**. `outdir` container placement (§3) is now confirmed for
> a Platform head job too, not just a local one.
>
> ⚠️ Getting there needed **§9 (node OS disk)** and **§10 (head-job restart)** — a Platform head job on a
> single-pool compute environment fails at ~98% completion without them.

Config: [`conf/azure_batch.config`](../../conf/azure_batch.config) (pass with `-c`, deliberately not a
profile, so only opted-in runs are affected) · params: [`conf/params_ottilie_test_blob.yml`](../../conf/params_ottilie_test_blob.yml) ·
launcher: [`bin/test_ottilie_azure_batch.sh`](../../bin/test_ottilie_azure_batch.sh) ·
Azure/SP provisioning: [`deploy/azure/`](../../deploy/azure/).

Everything below was found by *running* it. None of it is visible to the local test suite, and several
items produce errors that point at the wrong thing entirely.

📌 **§16 is a register of claims that were believed and then disproved.** Read it before concluding
that some tool "cannot" do something — several entries here were once confidently written the other way.

---

## Orientation — why this config isn't the five-line example

Every Azure Batch tutorial, including Seqera's own
[Nextflow and Azure Batch (part 1)](https://seqera.io/blog/nextflow-and-azure-batch-part-1-of-2/),
shows a config that fits on a screen:

```groovy
process { executor = 'azurebatch' }
azure {
    storage { accountName = "…"; accountKey = "<key>" }
    batch {
        location = 'eastus'; accountName = '…'; accountKey = '<key>'
        autoPoolMode = true
        allowPoolCreation = true
        pools { auto { autoScale = true; vmCount = 1; maxVmCount = 10 } }
    }
}
// work dir passed on the CLI:  -w az://nextflow-scratch/work
```

[`conf/azure_batch.config`](../../conf/azure_batch.config) has the **same skeleton** — the executor
line, `autoPoolMode`, `allowPoolCreation`, and the `pools.auto` autoscale block are byte-for-byte the
same idea. It looks bigger mostly because it carries its reasoning inline. Only **four** settings
actually diverge, and three of them are forced rather than chosen:

| Setting | Tutorial | Here | Why it differs |
|---|---|---|---|
| **Auth** | `accountKey` for storage + batch | Entra service principal (`azure.activeDirectory`), read from env vars | **Chosen.** Shared account keys are all-or-nothing, can't be scoped, and must not sit in the repo. The SP holds two *data-plane* roles on **one** Batch account and **one** storage account (`deploy/azure/`). This is the root cause of gotcha §3 below. |
| **`vmType`** | omitted → default `Standard_D4_v3` | `Standard_E4ds_v4` | **Forced by quota.** On `aledev4test` only Ev4/Dv3/Dv4-family SKUs have vCPU quota (350); anything else fails `AccountVMSeriesCoreQuotaReached`. The 32 GB (vs 16 GB on `D4s_v3`) also suits the GATK steps. |
| **`publisher`/`offer`/`sku`** | omitted → rely on the default image | pinned, `sku = 'batch.node.ubuntu 24.04'` | **Pin the current verified LTS.** Nextflow only accepts images Batch marks `verified`; its built-in default (22.04) has aged out and now matches nothing. Expect to bump this at each LTS. See §4. |
| **`workDir`** | `-w` on the CLI, any container | in the config, **same container as the inputs** | **Consequence of the auth choice.** SP auth makes Nextflow mint one container-scoped SAS. Under the tutorial's account-key auth this constraint does not exist. See §3. |

Two things that look like divergences but are not:

- **`deletePoolsOnCompletion = false`** is Nextflow's own default. It is written out explicitly only
  because the reason to keep it matters (§2) and because an env var can flip it for one-shot runs.
- **`maxVmCount = 4`** (vs 10) is just test-scale sizing, not a technical constraint.

⚠️ **The tutorial is also older than the engine we run.** It states the default pool image is
`microsoft-azure-batch / ubuntu-server-container / 20-04-lts`. On Nextflow 25.10.4 the observed
default is `microsoft-dsvm / ubuntu-hpc / batch.node.ubuntu 22.04` (§4). So "just take the defaults"
is advice from a different Nextflow. Treat the blog as correct on *shape*, not on *values*.

**The one-line summary:** the extra complexity buys least-privilege auth and nothing else. Swap the
SP for account keys and this config collapses to roughly the tutorial's size — along with the
work-dir constraint. That trade is deliberate; see [`deploy/azure/seqera-sp/RUNBOOK.md`](../../deploy/azure/seqera-sp/RUNBOOK.md).

---

## 1. `-resume` silently resumes the WRONG session

**Symptom.** `-resume` reruns everything: `Cached process` count is 0.

**Cause.** Bare `-resume` resumes **the most recent run in `.nextflow/history`**, whatever that was.
Any other `nextflow run` in the same directory — including a `-preview` sanity check or an unrelated
local profile test — becomes "most recent" and its (empty) cache is what gets inherited. The real run's
cache is untouched but never consulted.

**Fix.** Resume an explicit session id:

```bash
tail -5 .nextflow/history          # columns: time, duration, run name, status, revision, SESSION ID
nextflow run ... -resume 7bd76ec1-9112-4937-a672-d0022eff396c
```

**Prevention — `-work-dir` does NOT help.** It isolates the *work directory*, but `.nextflow/history`
lives in the **launch** directory, so the run is still recorded and still becomes "most recent". This
was tried and failed. Either:

```bash
# (a) launch the check from a different directory — history is per-launchDir
mkdir -p /tmp/nf-check && cd /tmp/nf-check && nextflow run /path/to/repo/main.nf -profile ottilie_test,docker -preview

# (b) or simply always resume by explicit session id (the reliable habit)
nextflow run ... -resume <session-id>
```

**(b) is the habit worth forming** — it is correct regardless of what else has run, whereas (a) depends
on remembering to isolate *every* incidental run.

`-resume` also requires the **same `workDir`**. Changing `workDir` invalidates every cached task, since
task caching is keyed on work-dir paths.

---

## 2. Pool names are content-addressed — and that breaks `deletePoolsOnCompletion`

Nextflow names auto-pools `nf-pool-<hash>-<vmType>`, where the hash is a `CacheHelper` digest of
`AzVmPoolSpec` = `vmType` + the whole `AzPoolOpts` (the `azure.batch.pools.<name>` block) + metadata.
Same pool config → same id → the pool is reused across runs; change `vmType`, `sku`, `publisher`,
`offer`, autoscale or node counts → new hash → a fresh pool. Same principle as task work-dir hashing:
you can never silently execute on a pool built to a different spec than you asked for.

Options on `azure.batch.*` (as opposed to `azure.batch.pools.*`) are **not** in the hash —
`deletePoolsOnCompletion` can be flipped without minting a new pool.

**Symptom.** On `-resume`: `Azure Batch pool 'nf-pool-<hash>-<vmType>' not in active state`.

**Cause.** `deletePoolsOnCompletion = true` destroyed the pool at the end of the previous run. Because
the id is derived rather than random, the resumed run asks for that exact pool and finds it in
`deleting` state.

**Fix.** Keep pools between runs (the repo default). Idle pools cost nothing — autoscale drains them to
0 nodes and billing is per-VM, not per-pool. Set `AZURE_DELETE_POOLS=true` for one-shot production runs.
Occasional cleanup:

```bash
az batch pool list --query "[?starts_with(id,'nf-pool')].id" -o tsv | xargs -r -n1 az batch pool delete --yes --pool-id
```

---

## 3. With an Entra/SP credential, the work dir must be in the SAME CONTAINER as the inputs

> **This rule tracks the CREDENTIAL, not local-vs-cloud.** A **shared-key** credential gives Batch
> nodes account-wide access and has no such restriction — verified 2026-08-04: the Seqera CE
> `aledev4test_e4ds_v4` (credential `rgALE_batch_aledev4test`; CE since deleted 2026-08-13) ran
> `workDir = az://debugging` against inputs in `aletest` and worked. A *cloud* run on the **Entra**
> credential hits this rule exactly as a local one does.
>
> **⛔ No bypass exists under the SP credential — every candidate has been tested:**
>
> | Candidate bypass | Verdict |
> |---|---|
> | More RBAC on the SP | ✗ — the SP already holds `Storage Blob Data Contributor` account-wide and can read both containers itself. Nodes never authenticate as the SP; they get one delegated container-scoped token. The limit is what Nextflow *delegates*, not what the SP *may* do — Owner on the subscription would change nothing. |
> | Fusion (per-container tokens?) | ✗ — verified 2026-08-13 (run `3AJ4JRNkb7D2dG`): same single SAS through the FUSE path, rejected 403. See below. |
> | **Switch credential type: shared key** | ✓ works (2026-08-04, above) — **the only lever**, and it is a *trade*, not a free fix: every Batch node gets account-wide blob access, which is the blast radius the Entra SP path was chosen to avoid. |
>
> So under the SP: keep inputs and `workDir` in one container — it is a requirement, not a tuning knob.

**Symptom.** A task exits 1 with **empty stderr**. The real message appears only in `.command.log` in
blob: `Unable to download path: https://<account>.blob.core.windows.net/<container>/...`

**Cause.** With Entra/service-principal auth, Nextflow mints **exactly one** container-scoped
user-delegation SAS (`sr=c`) for the work-dir container and reuses it for *every* blob URL in the task
script. Verified: the generated `.command.run` contains a single `sig=` value. A node therefore has no
credential for any other container — **same storage account is not sufficient**.

**Fix.** Put `workDir` in the container holding the inputs (here: inputs under `az://aletest/ottilie/v1/`,
so `workDir = az://aletest/nf-work`). Same storage account either way, so no extra RBAC grant is needed.

**`outdir` is exempt** and may live in another container: `publishDir` runs in the **head process**
using the SP credentials, which have account-wide blob access — not the node's container-scoped SAS.
Verified: 195 blobs published to `az://debugging/ottilie-azurebatch-out/` while `workDir` was
`az://aletest/nf-work`.

### ✅ Confirmed under a Seqera Platform head job (2026-08-07)

Previously this rule was verified only with a **local** head job, leaving open whether Platform — which
runs the head process on a Batch node — behaves the same. **It does.** Run `48kJmc9QY6Q3h9`
(`ottilie-xcontainer-01`) was launched deliberately to falsify it: identical to a known-good run except
`--work-dir az://debugging/nf-work-xcontainer`, with inputs left in `aletest`.

**Result: 0 tasks succeeded, 6 failed**, dying in `PREPARE_GENOME` about 6 minutes in. Every failed
process is one that reads an input from `aletest` — `SAMTOOLS_FAIDX`, `GATK4_CREATESEQUENCEDICTIONARY`,
`BWAMEM1_INDEX` (the fasta), `PREPARE_GFF3`, `FASTQC`. The evidence, from the task's blob work dir:

```
.command.log:  Unable to download path:
               https://aledata.blob.core.windows.net/aletest/ottilie/v1/S288C_reference_test/S288C_R64_test.fa
.command.err:  (0 bytes)
```

⚠️ **Note where the message is.** `.command.err` was empty — the Seqera UI and `tw` both surface
stderr, so this failure looks like *no error at all* from the console. **Always read `.command.log`
from the blob work dir**:

```bash
az storage blob download -c <workdir-container> --name "<path>/<hash>/.command.log" \
  --file /tmp/x.log --account-name <acct> --auth-mode login
```

| Constraint | Status |
|---|---|
| inputs ↔ `workDir` same container | ✅ **Confirmed for local and Platform head jobs, AND under Fusion.** Not a convention — a requirement. |
| `outdir` may be in another container | ✅ **Confirmed under Platform for `publishDir` writes (2026-08-13)** — run `3AJ4JRNkb7D2dG` published `pipeline_info/` into `aletest` while `workDir` was in `debugging`; verified locally earlier (195 blobs to `az://debugging/…`). Task-output publishing uses the same head-side mechanism, but a *successful* cross-container run cannot exist to demonstrate it end-to-end — the rule above kills the tasks first. |

### ✅ Fusion does NOT lift this (2026-08-13)

Answered by repeating the predicted-failure launch above on a Fusion CE (run `3AJ4JRNkb7D2dG`,
`yAMP-ce-fusion-256` — dual-pool + 256 GB per §9–§10, so `DiskFull` could not confound): **failed
identically**, 0/6, the same six `aletest`-reading tasks, ~5 min in. Fusion consumes the same single
container-scoped user-delegation SAS and presents it against the other container; the server rejects
it, and Fusion says so plainly. **The rule is a property of the credential delegation, indifferent to
the data path (azcopy staging or FUSE mount). Do not design around Fusion lifting it.**

⚠️ The failure *signature* differs under Fusion — and is friendlier: `.command.err` is **non-empty**
(the tool's own `Permission denied`), and `.fusion.log` in the task work dir holds the underlying
`403 AuthenticationFailed` complete with the SAS scope mismatch and the line *"Fusion authenticated
successfully but lacks permission to access this resource."* The empty-stderr trap above is
non-Fusion-specific.

Terminology, since the distinction is the whole point: `aledata` is the **storage account**;
`aletest` and `debugging` are **containers** within it. `az://<container>/<path>` — the account comes
from `azure.storage.accountName`. The constraint is **inputs ↔ workDir must share a container**, not
"everything in one container".

---

## 4. Pin the current *verified* `ubuntu-hpc` LTS — and re-pin when it ages out

**Rule.** Always run the newest `ubuntu-hpc` image that Batch marks **`verified`**, named by its
**node agent SKU ID** (`batch.node.ubuntu 24.04`), not its image sku (`2404`).

Two independent reasons the pin exists:

- **`verified` is what Nextflow will accept.** It filters candidates to verified images, so an
  unverified one is unusable through nf-azure regardless of whether Azure would run it.
- **`ubuntu-hpc` is the only verified family with `DockerCompatible`.** `canonical/*` and
  `almalinux/*` are verified but ship no container runtime — they fail *every task* instead of
  failing pool creation, which is the far worse failure.

**Symptom when the pin is missing or stale.** `Cannot find a matching VM image with
publisher=microsoft-dsvm; offer=ubuntu-hpc; OS type=linux; verification type=verified`

Nextflow's own defaults (`microsoft-dsvm` / `ubuntu-hpc` / `batch.node.ubuntu 22.04`) are already
stale: 22.04 has reached end of Batch node-agent support and is now `unverified`, so the default
matches nothing. **This is Microsoft's image lifecycle, not an account setting** — verified as
identical across four Batch accounts in two regions, so a new account or region inherits the same
requirement. Expect to bump the pin at each LTS transition.

⚠️ `sku = '2404'` (the *image* sku) is silently ignored and the 22.04 default is used instead. Only
the agent SKU ID works.

**Re-check when a run fails on image matching, or at the next LTS:**

```bash
az batch account login -g <rg> -n <account>
az batch pool supported-images list -o json | jq -r '.[] | select(.verificationType=="verified" and .osType=="linux")
  | "\(.imageReference.publisher) \(.imageReference.offer) \(.imageReference.sku) \(.nodeAgentSkuId) \(.capabilities)"'
```

---

## 5. A remote work dir requires every input file to actually EXIST

**Symptom.** `Can't stage file /path/to/SENTINEL -- file does not exist`

**Cause.** `file('SOME_SENTINEL')` for a non-existent path works on the **local** executor — Nextflow
symlinks it, and `ln -s` to a missing target succeeds. With a remote work dir Nextflow must *copy* every
input, so `FilePorter` throws. This hit `NO_DEPTH_BG` / `NO_LOG2_BG`, the placeholders
`IGVREPORTS_SV_CNV` uses when a caller has no CNVKit coverage tracks (it keys off the file *name*, never
the contents).

**Fix.** Don't declare a file at all — pass **`[]`**, the Nextflow idiom for an absent optional path.
[`subworkflows/local/mutation_report/main.nf`](../../subworkflows/local/mutation_report/main.nf) sets
`no_depth_bg = []` / `no_log2_bg = []`; the module sees a falsy value and drops the track. `[]` has
nothing to stage, so the failure cannot recur.

> Shipping real empty `assets/NO_DEPTH_BG` / `NO_LOG2_BG` files was the first attempt and was
> **abandoned** — it keeps a meaningless file in the repo and still stages bytes to every cloud task.
> Those assets do not exist; don't reintroduce them. Full recipe, including the `tuple path(a), path(b)`
> case, in [`troubleshooting.md`](troubleshooting.md) → "Making an optional file param actually optional".

**Generalisation.** `projectDir`-based assets are fine on Azure Batch — Nextflow stages them like any
local file, and upstream nf-core already relies on this (`$projectDir/assets/multiqc_config.yml`,
`schema_input.json`, the email templates). The rule is not "avoid `projectDir`" but **"every declared
input path must exist, and should say so with `checkIfExists: true`."**

---

## 6. A null optional param reports itself as a samplesheet error — ✅ fixed for `report_gff3`

**Symptom.**

> `The sample-sheet only contains tumor-samples, but the following tools, which were requested by the option "tools", expect at least one normal-sample : haplotypecaller`

**The samplesheet is fine.** `generate_reports` defaults to `true`; with `report_gff3` unset,
`file(params.report_gff3)` threw while the DAG was being built, and a dangling `ifEmpty` on the
samplesheet channel then fired this unrelated message. Bisect: params-file as-is → FAIL;
`+ report_gff3` → PASS; `+ generate_reports false` → PASS.

**Fixed 2026-08-04.** `report_gff3` is now genuinely optional — reports build without the gene track.
Verified end-to-end with `report_gff3` unset: 30 reports, `PREPARE_GFF3` skipped, `--tracks` dropped
from the cohort report (it was that report's only track), cohort variant table intact.

⚠️ **The misdirection itself is NOT fixed.** The dangling `ifEmpty` at
`subworkflows/local/samplesheet_to_channel/main.nf:159-168` still reports *any* early DAG abort as a
sample-status error. It is inherited from nf-core/sarek 3.5.1 and present in the pristine fork base, so
changing it is a deliberate divergence decision. Recipe for optional params, and how to find the real
error: [`troubleshooting.md`](troubleshooting.md).

---

## 7. `--foo null` on the CLI is the STRING `"null"`

`--genome null` sets `params.genome = 'null'`, which is **truthy**. A real null can only be expressed in
a config or `-params-file`. This is one reason the launcher uses `-params-file` rather than a pile of
`--flags` — the other being that the same file feeds both the local Batch run and a Seqera launch, so
they cannot drift.

---

## 8. Checking cost

[`deploy/azure/seqera-sp/11_check_cost.sh`](../../deploy/azure/seqera-sp/11_check_cost.sh) reports actual
spend by meter and day. **Cost data lags 8–24h** (sometimes 48h) — a run finished today shows `0.00`,
meaning *not billed yet*, not free.

Azure Batch itself is free; you pay for pool VMs, their managed disks (~25% on top of compute), and
storage transactions. `northeurope` list prices:

| SKU | Dedicated | Low priority | Spot |
|---|---|---|---|
| `Standard_E4ds_v4` | $0.320/hr | **$0.064/hr** | $0.086/hr |
| `Standard_D4s_v3` | $0.214/hr | $0.043/hr | $0.040/hr |

Low priority is ~5× cheaper and well suited to resumable test runs. For scale reference, real ALE
production jobs on the `ale` Batch account cost roughly **$30–40 each**. Cost Management returns **DKK**
while the retail price API returns **USD** — do not mix them (~6.9 DKK/USD).

---

## 9. Batch nodes fill their **OS disk** with Docker images — not with task data

**Symptom.** Nodes go `unusable` with:

```
code: DiskFull
"The VM disk is full. Delete jobs, tasks, or files on the node to free up space and then reboot the node."
```

Downstream this looks like something else entirely: the workflow is marked `FAILED` with **zero failed
tasks** (see §10), so nothing points at the disk.

**Why.** An Azure Batch Linux node has two disks, and they do different jobs:

| Disk | Mount | On `Standard_E4ds_v4` | Holds | Billed |
|---|---|---|---|---|
| **OS / boot** | `/` | **default size unknown** — near 65 GB, never measured (see below) | the OS and **`/var/lib/docker`** (image layers, overlay2) | yes, managed disk |
| **Temp / ephemeral** | `/mnt` | **150 GB** local NVMe | `/mnt/batch/tasks` — Nextflow task dirs, staged inputs | no, included with the VM |

Task scratch is on the *big* disk already. **Docker is on the small one**, and this pipeline pulls
10–15 tool images (GATK, snpEff, CNVkit, Manta, TIDDIT, igv-reports, MultiQC, FastQC, bwa/samtools),
which exhausts the default root disk.

**Evidence it is Docker, not task data:** an unusable node had **0.07 GB across 205 files** in its Batch
task directories. Confirm with:

```bash
az batch node file list --pool-id <pool> --node-id <node> --recursive \
  --query "[].properties.contentLength" -o tsv | paste -sd+ | bc
```

⚠️ **Concurrency is NOT the cause.** An early hypothesis blamed two runs sharing a pool; the next
failure was a **solo** run. Concurrency only reaches the limit sooner.

### Two fixes — pick per situation

**(a) Enlarge the OS disk — what we run today.** One flag, Batch Forge keeps managing the pools:

```bash
tw compute-envs add azure-batch forge ... --worker-boot-disk-size 256 --head-boot-disk-size 64
```

Verify it applied — Batch reports `osDisk.diskSizeGb`, and a CE without the flag shows `null`:

```bash
az batch pool list --query "[].{id:id,diskGB:virtualMachineConfiguration.osDisk.diskSizeGb}" -o table
```

**(b) Move Docker to the ephemeral disk — better, but needs a manual pool.** Uses the 150 GB of local
NVMe you already pay for with the VM, and it is faster for image-layer extraction. As a Batch **pool
start task**:

```bash
systemctl stop docker && mkdir -p /mnt/docker && rsync -aP /var/lib/docker/ /mnt/docker &&
sed -i "s|^ExecStart=.*|ExecStart=/usr/bin/dockerd --data-root=/mnt/docker|" /lib/systemd/system/docker.service &&
systemctl daemon-reexec && systemctl start docker
```

⚠️ **`preRunScript` cannot do this.** Platform's pre-run script executes in the nf-launch script inside
the **head job**, not as a start task on every worker node. A start task requires a pre-created pool
plus `tw compute-envs add azure-batch manual --compute-pool-name/--worker-pool` — which means taking
autoscale, the verified image pin (§4), node lifecycle and `azcopy` back from Forge.

**Trade-off:** (a) costs a managed disk per node and leaves the free NVMe idle; (b) is free and faster
but hands you the pool lifecycle. (a) also tolerates an image set larger than 150 GB, which (b) cannot.

### ✅ Measured 2026-08-07 — peak OS-disk usage is ~65 GB

Sampled with [`conf/disk_probe.config`](../../conf/disk_probe.config) (opt-in `-c`/`--config`, logs
`df` at the start of every task) across 21 nodes of run `XFwlgZnKvUvpu`:

| | |
|---|---|
| disk size | **246.9 G** (the 256 GB `--worker-boot-disk-size`) |
| **peak used** | **65.2 G — 26%** |
| range | 56.7 G – 65.2 G |
| free at peak | 182 G |

What this does and does not establish:

1. ✅ **256 GB is ample** — ~3.8× the observed peak, 182 G free. 128 GB would also fit; the difference
   is about $0.05/hr across four workers, so there is no reason to trim it.
2. ✅ **The `/mnt` relocation fix is viable** — 65 GB fits well inside the 150 GB ephemeral NVMe, which
   was the untested assumption underneath it.
3. ❓ **The default disk size is still UNKNOWN.** An earlier draft of this section asserted "Azure's
   default is ~30 GB"; that was an **assumption, not a measurement**, and `az vm image show` will not
   return `osDiskImage.sizeInGb` for this image. All that is actually known is that the default was
   *large enough* to run 122/138 and 169/170 tasks before filling — so it sits somewhere near the
   65 GB peak. **A 64 GB default would fit the observed failure timing exactly** (survives most of the
   run, crosses the line at the end), but that is inference.

⚠️ **These numbers are a MULTI-RUN accumulation, not a single run.** The sampled nodes were allocated
**67 minutes before** this run's first task and had already executed a complete 170-task pipeline —
`totalTasksRun` per node was 57/94/80/109, i.e. ~340 tasks across two runs. Consequences:

- Every container image was **already cached** when sampling began, so the first-task reading
  (53.8 G) is **not a baseline** and cannot be used to separate the base OS image from this
  pipeline's images. An earlier draft did exactly that and was wrong.
- The ~11 GB of growth *during* the run is therefore **not** image pulls — more likely container
  writable layers, logs and temp.
- The 65 GB figure is the **more conservative** number for sizing a long-lived pool, since it reflects
  accumulation across runs. Autoscale draining to 0 destroys the nodes and resets it.

**To get a true baseline**, the pool must be cold: let autoscale drain it to 0 (or forge a fresh CE),
then read the *genuine* first task. That gives base OS + one image, and growth from there is this
pipeline's real footprint. ✅ **Done 2026-08-13 — see the cold-pool baseline below.**

⚠️ **`beforeScript` runs INSIDE the container**, not on the node (`hostname` returns a container id,
`/` shows as `overlay`). The reading is still valid because overlay2's `df` reports the **backing**
filesystem — 246.9 G matches the OS disk — but the mechanism is not what it appears.

⚠️ **Under Fusion the work-dir `df` is meaningless**: Fusion presents a synthetic filesystem
(`fusion 8.0P 4.0P 4.0P 50% /fusion`). Only the `root:` line is usable on a Fusion CE.

⚠️ **The probe's `mnt :` line is useless too** — a Docker task container has no `/mnt` bind, so
in-container `df /mnt` falls back to `/` and duplicates the `root:` line (measured 2026-08-13).
The host's ephemeral disk is visible only through the `work:` line, because the task sandbox
(`/mnt/batch/tasks`) actually lives on it.

### ✅ Measured 2026-08-13 — COLD-pool baseline: base ≈ 45 G, pipeline adds ≈ 15 G

Run `18wEWW90THA2Ek` (`ottilie-pilot-coldprobe-01`): the **full-depth 4-sample ottilie pilot**
(~11× the test set's input data) on a freshly forged CE (`yAMP-ce-coldprobe-256`, since deleted), so
every node was genuinely cold. 310/310 tasks, 0 failed; all 310 `.command.log`s harvested, not a sample.

| | |
|---|---|
| **cold base** (first task on each fresh node, 13:28Z) | **45.4–45.5 G** of 246.9 G |
| **peak** (end of run) | **60.0 G — 24%** |
| growth over the run | ≈ 14.6 G, stepping up as each new process type first pulls its image |
| task work-dir disk (`/dev/sdb1`, 146.6 G ephemeral) | **max 2.7 G** |

What this settles:

1. **The warm figure's split.** Of the 65.2 G warm peak, ~45 G is the **base OS image** — the
   `ubuntu-hpc 2404` stack costs that much before a single pipeline image is pulled. This
   pipeline's images + container writable layers add only **~15 G**.
2. **Images dominate; `/` usage does not scale with input data.** Running ~11× the data produced a
   *lower* single-run peak (60.0 G cold) than the test set's two-run warm accumulation (65.2 G),
   and the growth curve steps at process-phase boundaries (image pulls), not with data volume.
3. **Sizing: 128 GB would be comfortably sufficient** (>2× the observed peak); 256 GB is 4×.
   And the "~64 GB default" inference in the 2026-08-07 entry gets stronger: base 45 G + images
   15 G ≈ 60 G — exactly the shape of a default-sized disk surviving most of a run and filling
   near the end.
4. **The `/mnt` relocation fix has more headroom than assumed** — only Docker's ~15 G would move
   (the 45 G base is the OS image itself, not `/var/lib/docker`), and task scratch peaked at
   2.7 G, so the 150 G ephemeral disk is ample for both.
5. ❓ **Whether Fusion's cache competes for `/mnt` is still open** — this was a non-Fusion run, and
   the probe cannot see the host's `/mnt` from inside a container anyway (see the ⚠️ above).
   **Interim monitoring:** attach `--config conf/disk_probe.config` to routine **Fusion dev runs**.
   The `root:` line is still valid under Fusion, so if Fusion's cache lands on the OS disk it shows
   up as `/` usage well above the ~60 G non-Fusion ceiling; a flat `root:` means the cache lives
   somewhere the probe cannot see (host `/mnt` or memory), which needs a node-level measurement
   (pool start task or a native, non-container Batch task running `df`). ⚠️ Only on runs where
   losing `-resume`/cache reuse is acceptable — the probe perturbs task hashes — and never on a run
   whose outputs you intend to byte-compare against a no-probe baseline run's task cache.

```bash
az batch node reboot --pool-id <pool> --node-id <node> --node-reboot-option terminate
```

⚠️ `az batch node delete` is **rejected while autoscale is enabled** (`Remove VMs not allowed when
AutoScale is enabled`). ⚠️ And a rebooted node can report `state: running, errors: null` and return to
`unusable` minutes later — **never declare a pool healthy from a single sample.**

---

## 10. A Seqera Platform head job **cannot survive a restart** — isolate it with `--dual-pool`

**Symptom.** The workflow is `FAILED` with **zero failed tasks** (seen at 122/138 and 169/170), and:

```
ERROR ~ Unable to access config file 'https://api.cloud.seqera.io/ephemeral/…'
        -- Cause: Server returned HTTP response code: 403
```

**Why.** Platform passes launch parameters to the head job through an **ephemeral, single-use URL**.
When the head job's node dies — §9 — Batch reschedules the head task, the replacement re-fetches that
URL, and gets **403**. A recoverable node failure becomes a total run loss near completion.

Tell-tale: the surviving Batch task ran for ~14 seconds with `retryCount: 0`, while the workflow had
been running for 20+ minutes. That short-lived task is the *replacement*, not the original.

```bash
az batch task list --job-id nf-workflow-<runId> \
  --query "[].{state:state,retries:executionInfo.retryCount,exit:executionInfo.exitCode,
               start:executionInfo.startTime,end:executionInfo.endTime}" -o json
```

**Fix: `--dual-pool`.** The head job gets its own pool, so a worker-side disk failure can no longer kill
it. It is also *cheaper* — the head sits on a `Standard_D2s_v3` instead of an `E4ds_v4`.

⚠️ **Dual pool requires explicit per-pool VM counts.** `--vm-count` is single-pool only; omitting the
per-pool flags fails with `Missing VM count parameter for head pool`, despite the help text claiming the
head count defaults to 1.

### 🚨 A dual-pool CE defaults to NO autoscale — create it with `13_create_compute_env.sh`

**Measured cost of getting this wrong: ~$66/day.** `tw compute-envs add azure-batch forge --dual-pool`
**omits `autoScale` from the request** unless you force it, so Platform stores null and Azure builds
**`enableAutoScale: False`** — fixed size, running 24/7 whether or not anything is queued. Reproduced
deliberately on 2026-08-07 with a throwaway CE, so it is repeatable CLI behaviour, not a one-off. Ten
nodes (8× `E4ds_v4` + 2× `D2s_v3`) ran idle for hours before it was noticed: ~$2.75/hr compute plus
~$324/month of managed disks. Upstream: [seqeralabs/tower-cli#658](https://github.com/seqeralabs/tower-cli/issues/658),
fix in [#659](https://github.com/seqeralabs/tower-cli/pull/659) — **unmerged as of 2026-08-11**, and
0.38.0 is the latest release, so there is no version to upgrade to.

The `--help` offers **only flags to DISABLE** autoscaling — `--no-auto-scale`, `--head-no-auto-scale`,
`--worker-no-auto-scale` — which reads as "enabled by default". For **single-pool** that is true
(`autoScale: true`, pools sit at 0 nodes). For **dual-pool** it is not, and nothing warns you.

**Use [`13_create_compute_env.sh`](../../deploy/azure/seqera-sp/13_create_compute_env.sh)** — it
`tw compute-envs import`s a readback of a known-good CE, which carries `autoScale: true` verbatim, then
runs the verifier. Both the web UI and the import route set the field correctly, so this is a CLI
**default**, not a Platform limitation.

> ⚠️ **Correction (2026-08-11).** This section previously said `tw` *cannot* set autoscale and that the
> **web UI** was therefore required. Both halves were too strong. `add ... forge` **can** set it via
> explicit `--head-no-auto-scale=false --worker-no-auto-scale=false` (undocumented in `--help`, verified
> by payload inspection), and the UI is no longer needed. Keep using the script anyway: `add ... forge`
> has **no flags at all** for `jobMaxWallClockTime`, `deleteJobsOnCompletion`, `deleteTasksOnCompletion`
> or `terminateJobsOnCompletion`, so a flag-built CE silently takes Platform defaults for the four
> job-lifecycle settings our CEs pin (`7d` / `never`). Fixing autoscale that way would trade a loud bug
> for a quiet one.

⚠️ **Compute environments are IMMUTABLE.** A fixed-size CE cannot be patched; the only fix is delete
and recreate. **Verify the readback before running anything:**

```bash
curl -s -H "Authorization: Bearer $TOWER_ACCESS_TOKEN" \
  "$API/compute-envs/<ce-id>?workspaceId=<ws>" | python -c "
import sys,json; f=json.load(sys.stdin)['computeEnv']['config']['forge']
print(f['headPool']['autoScale'], f['workerPool']['autoScale'])"     # must print: True True

az batch pool list --query "[].{cur:currentDedicatedNodes,auto:enableAutoScale}" -o table
```

If it is already wrong, stop the billing first — `az batch pool resize --pool-id <pool>
--target-dedicated-nodes 0` — then delete the CE, which disposes the pools *and* their managed disks.

⚠️ **A new pool always shows 1 node for ~5 minutes; that is not a fault.** The Forge autoscale formula
hardcodes the first interval: `$TargetDedicatedNodes = lifespan < interval ? 1 : targetPoolSize`. So
`1 + 1` right after creation proves nothing — **`0 + 0` fifteen minutes later** is what proves
autoscale works. Confirmed unrelated to Wave/Fusion: a duplicate CE with both disabled behaves
identically.

⚠️ **`--worker-vm-count` is a CEILING under autoscale, not an allocation.** The autoscaling CE
provisioned 1 + 1 and scales toward 4 as tasks queue; the fixed-size one went straight to 1 + 4 and
stayed there.

⚠️ **Dual pool starts slower** — measured **4 min** (single-pool) vs **~17 min** for the head pool to
provision. The head job waits on its *own* VM allocation rather than using whichever shared node came up
first; worker nodes sit `idle` meanwhile. Cold-start only. `--head-no-auto-scale` keeps a head node warm
at the cost of a `D2s_v3` running continuously.

> **`--dual-pool` alone is not sufficient** — it does not stop workers filling up, it only stops that
> from killing the run. §9 is the load-bearing fix; §10 is the safety net. Use both.

**Also transient, and unrelated:** `Unable to access config file … Connection timed out` with
`start: None` and no Nextflow version reported. That is the head job failing to reach Seqera's API at
startup — network-level, before any path is resolved. Retry.

---

## 11. Platform-vs-local output differences that are NOT regressions

> Generalised, with normalisation recipes for each class and the 3-tier comparison method:
> [`output_comparison.md`](output_comparison.md). This section is the Azure-specific summary.

Comparing a Platform run against the local-head-job baseline, 464 of 529 common files were byte-size
identical and **all 9 cohort deliverables were byte-identical by md5**. The rest classify as:

| Difference | Cause |
|---|---|
| MultiQC plot renders (pdf/png/svg), `multiqc_data` | render non-determinism — already in `tests/.nftignore` |
| igv-reports HTML | `sessionDictionary` is a base64 gzip blob, non-deterministic |
| `.vcf.gz` / `.tbi` ±1–7 bytes | bgzf/gzip framing, `##fileDate`, `##source` |
| CRAM ±1 byte | header metadata |
| `csv/markduplicates_no_table.csv`, `csv/variantcalled.csv` | these **embed the absolute output path**, so a longer `outdir` string changes the byte count |
| `versions.yml` | a run from a **Git clone** appends the short commit (`v1.0.0-g86c4672`); a local-directory run does not |
| `pipeline_info/*` file *count* | timestamped per execution — the baseline has two sets because it was run twice |

⚠️ **`contentMd5` is NOT populated on published blobs** (0/534) — Azure stores it only when the uploader
supplies it, and Nextflow's publish path does not. So the "compare blob `Content-MD5` against local md5"
shortcut **does not work**. Compare `contentLength` first, then download and hash the files that matter:

```bash
az storage blob list -c <container> --prefix <run>/ --account-name <acct> --auth-mode login \
  --num-results 10000 --query "[].{n:name,s:properties.contentLength}" -o json
```

⚠️ `##TIDDITcmd` embeds the thread count, so TIDDIT VCFs can never be byte-identical across runs with
different vCPU allocations. Strip that line before comparing.

---

## 12. `NXF_VER` beats the launch UI's "Nextflow version" selector

A run submitted with **26.04** chosen in the launch form's Advanced settings still executed **25.10.4** —
the compute environment's `NXF_VER` environment variable won, silently. `NXF_VER` selects the engine the
launcher self-fetches, and that wins wherever it is set.

Consequence: **you cannot test another engine version from the UI while the CE pins one.** Use a CE
without the env var, or a launch-time `--pre-run` that re-exports it.

`-e NXF_VER=…` is the right delivery mechanism — `tw`'s help states env vars are added to the **Nextflow
head job process** by default, which is exactly where the pin is needed. Confirmed stored as
`{"name":"NXF_VER","value":"25.10.4","head":true,"compute":false}`, and confirmed in effect: the run
reported Nextflow 25.10.4. Nothing on a compute node ever reads it — task wrappers invoke `.command.sh`
via plain bash inside `docker run`, forwarding only `NXF_TASK_WORKDIR` and `NXF_DEBUG`.

---

## 13. A Seqera launch INJECTS some schema defaults, silently overriding your profile

**Symptom.** A Launchpad run using `-profile docker,ottilie_test_az` died with:

```
ERROR ~ No such file or directory: s3://annotation-cache/snpeff_cache/R64-1-1.105
```

…even though the profile sets `snpeff_cache` to an `az://` path, and Platform's own resolved config
for that run *shows* the `az://` value.

**Cause.** Platform submits a params file alongside the launch, and **`-params-file` beats config**, so
anything in it overrides the profile. That params file is not just what you typed in the *Pipeline
parameters* box — the launch form **adds some `nextflow_schema.json` defaults of its own**. For run
`2eiGBEA0NXagap` the box held two lines but four params were submitted:

```
step                'mapping'                                 ← from the box
outdir              'az://aletest/seqera-runs/2026-08-12-01'  ← from the box
snpeff_cache        's3://annotation-cache/snpeff_cache/'     ← INJECTED, schema default
custom_config_base  'https://raw.githubusercontent.com/…'     ← INJECTED, schema default
```

⚠️ **It is not every schema default.** `split_fastq` (default `50000000`) and `genome` (default
`GATK.GRCh38`) were **not** injected, and the profile's values (`0`, `null`) survived. So the rule is
narrower than "schema defaults always win" — which is exactly what makes it dangerous: most profile
params work, and the one that doesn't fails deep into the run.

**Fix.** Any param that has a `default:` in `nextflow_schema.json` **and** matters to the run must be
set in the *Pipeline parameters* box, not only in the profile. There your value replaces the schema
default before the form submits anything. Everything without a schema default is safe in the profile —
`input`, `fasta`, `genbank`, `chr_dir`, `snpeff_db`, `tools`, `joint_germline`, `igenomes_ignore` all
came through untouched on the same run.

⚠️ **`snpeff_cache` is the one that bites here, and it differs per dataset** —
`S288C_reference_test/snpeff_cache` for the contract test, `S288C_reference/snpeff_cache` for the
full-depth pilot. So a single Launchpad entry serving both profiles needs that field edited at launch
time, alongside `outdir`.

**How to diagnose this class of failure** — compare what was *submitted* against what the config
*resolved to*; they are different objects and only the first wins:

```bash
# what the launch actually submitted (the authority)
curl -s -H "Authorization: Bearer $TOWER_ACCESS_TOKEN" \
  "$API/workflow/<runId>/launch?workspaceId=<ws>" | python -c "
import json,sys; print(json.loads(json.load(sys.stdin)['launch']['paramsText']))"

# what the pipeline config resolved to (informative, but overridden)
curl -s -H "Authorization: Bearer $TOWER_ACCESS_TOKEN" \
  "$API/workflow/<runId>?workspaceId=<ws>" | python -c "
import json,sys; print(json.load(sys.stdin)['workflow']['configText'])" | grep snpeff
```

---

## 14. 🔬 A Launchpad entry pins a BRANCH NAME — its version hash is blind to your repo

**"Launched from `yAMP-ottilie-test-az`" is not a reproducible statement.** The entry stores
`revision: main` — a *name*. Nextflow resolves it to a commit when the run starts, so the same entry,
unchanged, executes different code as `main` moves.

**Measured 2026-08-12.** `main` advanced from `1e09fc3` to `bd591b6` — six commits, including two new
config profiles, a config refactor and a new script — and the pipeline's version hash was **byte-identical
before and after**:

```
before push (1e09fc3)   JHY5OjA0ZjA5MTBkZmI…FiZGVmOTVlNzg4MTg3
after  push (bd591b6)   JHY5OjA0ZjA5MTBkZmI…FiZGVmOTVlNzg4MTg3
```

The hash is content-addressed over the **stored entry** — repo URL, revision *name*, compute env,
profiles, `paramsText`, description — and over nothing else. It answers *"how is this Launchpad entry
configured"*, never *"what code ran"*. A Platform "pipeline version" is likewise a property of the
entry, not of the pipeline source: `yAMP-ottilie-test-az-1` stayed version 1 across all of it.

⚠️ **So do not cite a pipeline name, version name, or version hash as provenance.** Three things that
*are* reliable, in order of preference:

1. **`--commit-id <sha>` at registration** — pins the entry to one commit. Do this for an entry whose
   results you intend to cite as a baseline; leave it unpinned for routine dev entries.
2. **The run's own `commitId`**, resolved at launch and recorded on the run:
   ```bash
   curl -s -H "Authorization: Bearer $TOWER_ACCESS_TOKEN" \
     "$API/workflow/<runId>?workspaceId=<ws>" | python -c "
   import json,sys; w=json.load(sys.stdin)['workflow']; print(w['revision'], w['commitId'])"
   ```
   Run `2eiGBEA0NXagap` recorded `main 1e09fc3c9f6c26842183f1537b77d1fe50db9ab9` — the head at that
   moment, which the entry itself never mentioned.
3. **`versions.yml` in the published outdir.** A run launched from a Git clone appends the short commit
   to the pipeline version (`Aletechdev/ALE_Yeast: v1.0.0-g86c4672`), so the outputs carry their own
   provenance in-band. See [`CLAUDE.md`](../../CLAUDE.md) → Pipeline Identity.

⚠️ **The inverse trap:** because the hash does not move, an unchanged hash is **not** evidence that
nothing changed. Re-registering with identical content also reproduces the hash under a *new* pipeline
id — observed three times on 2026-08-12. Compare `commitId`s, never hashes.

---

## 15. 🚨 Platform's run status can be wrong in BOTH directions — and nothing reaps a hung head job

**Observed 2026-08-13, run `1XuapND2cN2oCO`.** Platform showed **`UNKNOWN`**, frozen at 132 succeeded /
9 running. The run had in fact **finished successfully**: the head job's own log ends with
`[Aletechdev/ALE_Yeast] Pipeline completed successfully`, 534 blobs were published, and all nine
cohort deliverables were byte-identical to the `2026-08-06-04` baseline.

**What actually happened.** The head job completed the pipeline and then **hung instead of exiting** —
most likely blocked in the Tower plugin posting its terminal status, which fits the heartbeats stopping
at the same moment (`lastUpdated` froze at 11:47:31Z, the last log line was 11:48:13Z, and the Batch
task was still `running` 40 minutes later). Platform never received the completion event, so it fell
back to `UNKNOWN`.

⚠️ **Cancelling then makes the record wrong the other way.** `tw runs cancel` does reach Azure — the
head task ended `exitCode 137` (SIGKILL) and the pools drained within 5 minutes — but Platform now
records the run as **`CANCELLED`**, for a run whose outputs are complete and verified. So:

| Platform says | Can actually mean |
|---|---|
| `UNKNOWN` | finished successfully but could not report it |
| `CANCELLED` | finished successfully, then someone killed the hung process |
| `RUNNING` | finished; the head job simply has not exited |

**Never treat Platform status as the outcome.** Two sources that are authoritative:

```bash
# 1. the head job's own log — the only place "Pipeline completed successfully" appears
az batch task file download --job-id nf-workflow-<runId> --task-id nf-workflow-<runId> \
    --file-path stdout.txt --destination /tmp/head.txt && tail -3 /tmp/head.txt

# 2. what actually landed (see also output_comparison.md — contentMd5 is NOT populated)
az storage blob list -c aletest --account-name aledata --auth-mode login \
    --prefix "seqera-runs/<outdir>" --query "length(@)" -o tsv
```

⚠️ **Worker nodes going `leavingpool` is not a symptom.** They drain because the work finished — during
this incident that reading looked like a stall and it was the opposite.

🚨 **`jobMaxWallClockTime` does NOT apply to the head job.** `ce_import_template.json` sets `"7d"`, but
Azure reported `P10675199DT2H48M5.4775807S` — .NET `TimeSpan.MaxValue`, i.e. **no limit** — on
`nf-workflow-1XuapND2cN2oCO`. So a hung head job holds its node **indefinitely**; nothing reaps it. The
head pool cannot scale to 0 while a task is `running`, so the node bills until someone notices. Check
after any run that ends in a non-terminal state:

```bash
az batch pool list --query "[?contains(id,'<ce-id>')].[id,currentDedicatedNodes]" -o tsv
```

---

## 16. Corrections — claims that were believed, then disproved

**Read this before re-deriving anything.** Each line is a conclusion that was written down as fact and
later shown to be wrong. They are kept because the wrong answer is reachable from the same evidence
that produced it the first time — deleting them invites a second trip. One line each; the dated detail
is in [`RUNBOOK.md`](../../deploy/azure/seqera-sp/RUNBOOK.md).

| Claimed | Actually | Why it was believed |
|---|---|---|
| `tw` cannot create Entra credentials — only shared-key | `tw credentials add **azure-entra**` does it, present since 0.26.0 | only `credentials add azure` was inspected; the Entra form is a separate subcommand |
| `tw` cannot enable autoscale on a dual-pool CE — use the web UI | `compute-envs import` carries `autoScale`, and `add ... forge` takes explicit `--head-no-auto-scale=false` | only `add ... forge`'s flag list was inspected, then generalised to the whole CLI (2026-08-11) |
| Two runs sharing a pool caused `DiskFull` | a **solo** run exceeds the default disk on its own | the first two failures happened to overlap; concurrency was the visible difference |
| Azure's default Batch OS disk is ~30 GB, so 65 GB overruns it 2× | **unknown** — only bounded near 65 GB by when runs actually failed | plausible round number, never measured; `az vm image show` does not report it for this image |
| Peak OS-disk use of 65.2 G is a per-run baseline | measured on **warm** nodes (~340 prior tasks), so it is a multi-run high-water mark | the probe was read as if the pool were cold |
| `az://` staged an empty directory — use a tarball instead | all 7 files were present; `find` does not descend a symlink, and Nextflow stages directories as symlinks | the probe reported absence without proving it could detect presence (`find -L` shows them) |
| `beforeScript` runs on the node | it runs **inside the container** | the config's own comment said so; `hostname` returns the container id |
| The org refuses/queues fine-grained PAT requests | approval took **about one day** | an untested assumption that made the classic-PAT stopgap look necessary |
| Upgrading `tw` 0.26 → 0.38 "does not help here" | 0.38 was needed for later work | judged against one immediate blocker only |
| An `org/repo`-form `manifest.name` keeps `nextflow run <name>` viable | `nextflow run` resolves against GitHub, so only the real repo handle runs | see [`CLAUDE.md`](../../CLAUDE.md) → Pipeline Identity |

⚠️ **Four of these ten share one shape** (rows 1, 2, 6 and 9): a subcommand, flag list, or probe was
inspected, the result was correct *about that surface*, and the conclusion was then stated about the
whole tool. When writing "X cannot do Y", name the surface actually checked. Three more (rows 4, 8, 10)
are plain assumptions written in the voice of findings — if it was not run, say so.
