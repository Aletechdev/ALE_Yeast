# Running the pipeline on Azure Batch — execution gotchas

> **Status (2026-08-03): validated end-to-end for a LOCAL head job.** `Pipeline completed successfully`
> — 138 tasks submitted (+32 cached), **540 blobs published** to `az://aletest/ottilie-azurebatch-out/`,
> including `cohort_report.html`, the per-sample igv-reports, and the CN/SV cohort CSVs. Azure Batch
> works with the Entra service principal.
>
> **Still open:** (1) the outputs have **not** been diffed against a local run — byte-identical cohort
> CSVs is the acceptance criterion, and a delta would be a real cloud-vs-local reproducibility finding;
> (2) a **Seqera Platform launch** is a separate step, and at least one rule below (`outdir` container
> placement) is verified only for a local head job.

Config: [`conf/azure_batch.config`](../../conf/azure_batch.config) (pass with `-c`, deliberately not a
profile, so only opted-in runs are affected) · params: [`conf/params_ottilie_blob.yml`](../../conf/params_ottilie_blob.yml) ·
launcher: [`bin/test_ottilie_azure_batch.sh`](../../bin/test_ottilie_azure_batch.sh) ·
Azure/SP provisioning: [`deploy/azure/`](../../deploy/azure/).

Everything below was found by *running* it. None of it is visible to the local test suite, and several
items produce errors that point at the wrong thing entirely.

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
> `aledev4test_e4ds_v4` runs `workDir = az://debugging` against inputs in `aletest` and works. A *cloud*
> run on the **Entra** credential would hit this rule exactly as a local one does.
>
> **More RBAC will not fix it.** The SP already holds `Storage Blob Data Contributor` on the entire
> `aledata` account, so it can read both containers. Batch nodes never authenticate as the SP — they
> receive one delegated, container-scoped token. The limit is what Nextflow *delegates*, not what the SP
> *may* do. Granting the SP Owner on the subscription would change nothing.

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

> ⚠️ **The `outdir` exemption is verified only for a LOCAL head job — do not assume it under
> `tw launch`.** The two constraints behave differently once Seqera Platform runs the head process on a
> Batch node instead of your machine:
>
> | Constraint | Under Seqera Platform |
> |---|---|
> | inputs ↔ `workDir` same container | **Still applies.** The node-side SAS is minted by nf-azure the same way regardless of where the head job runs. |
> | `outdir` may be in another container | **Unproven.** The justification above is "the head process holds SP credentials". That is true locally. On a Seqera head job it depends on whether Platform passes the full Entra credential or only a scoped SAS. |
>
> Likely fine — Seqera injects the `azure_entra` credential into the head job, which would give the
> same account-wide access. But it is an inference, not a measurement.
>
> **De-risk cheaply:** for the *first* `tw launch`, put `outdir` in the **same container** as
> `workDir`/inputs. That removes the variable entirely. Once the run succeeds, move `outdir` to a
> different container as a deliberate second run — then the result is a clean answer about Platform
> head-job credentials rather than one more unknown inside a first launch.

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
