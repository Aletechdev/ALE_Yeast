# Runbook — Seqera service principal

Audit record for the Azure side of the Seqera Platform / Azure Batch run. **One entry per script
actually executed**, newest last. Raw transcripts live in `logs/` (gitignored); this file is the
committed summary.

**Nothing identifying goes in this file** — no GUIDs, no secrets. Resources are named; the scripts
resolve names to IDs at runtime (see [`00_vars.sh`](00_vars.sh) and the rationale in
[`../README.md`](../README.md)). To resolve a name to its ID you need tenant access, which is exactly
the audience this record is for.

## Target state

| Principal | Scope | Role |
|---|---|---|
| SP `sp-bright-recon-ale-mutations-pipeline-seqera-deploy` (📛 `cfb_ale_mutations_pipeline` until 2026-08-13) | Batch account `aledev4test` | `Azure Batch Data Contributor` |
| same | Storage account `aledata` | `Storage Blob Data Contributor` |

Per-resource scope only — never the resource group, never the subscription.

## Context — why this SP, and where it came from

`cfb_ale_mutations_pipeline` is an **existing app registration that was deliberately freed up and is
now being repurposed** for the Nextflow / Seqera Platform cloud testing. It is not a fresh
registration and not an accidental reuse.

> 📛 **Renamed 2026-08-13 → `sp-bright-recon-ale-mutations-pipeline-seqera-deploy`** (the naming
> standard of its sibling `sp-bright-recon-ale-mutations-pipeline`, suffixed with its purpose). All
> entries below use whichever name was current at the time. `appId`/`objectId` are untouched, and the
> rename propagated to the service-principal object automatically (verified — `00_vars.sh` resolves by
> SP display name, so propagation is what keeps the scripts working). The Seqera credential keeps its
> original name `azure_SP_cfb_ale_mutations_pipeline` — it binds by clientId, so it is functional
> as-is; align it whenever the credential is next re-entered (e.g. the 2027 secret rotation).

Lineage, in order:

1. It originally served the **ALE mutations web app / pipeline**, holding `Contributor` across the
   whole `rg-ALEdb` resource group.
2. That service was migrated to a **new, separately-scoped SP**
   (`sp-bright-recon-ale-mutations-pipeline`), narrowed to `Contributor` on the `ale` Batch account
   plus `Reader` on the `ensembleamp` image gallery.
3. The old RG-wide `Contributor` was then removed from `cfb_ale_mutations_pipeline`, leaving it with
   **no roles and no secret** — i.e. free.
4. **This runbook** claims that free SP for the Seqera / Azure Batch path, granting two per-resource
   data-plane roles and nothing else.

Steps 1–3 were done from `tmp/azure/azure_sp/` (untracked scratch — see the migration note in
[`../README.md`](../README.md)). Step 4 onward is tracked here.

## Log

| Date (UTC) | Script | Operator | Outcome |
|---|---|---|---|
| 2026-07-31 | `01_preflight.sh` | zhlia@dtu.dk | ✅ Read-only, nothing changed. See findings below. |
| 2026-07-31 08:08Z | `02_grant_roles.sh` | zhlia@dtu.dk | ✅ Both roles granted. Verified: **exactly two** assignments, both single-resource. |

### 2026-07-31 08:08Z — grant verified

`az role assignment list --assignee <sp> --all` returns exactly:

| Role | Scope | Created |
|---|---|---|
| `Azure Batch Data Contributor` | Batch account `aledev4test` | 08:08:47Z |
| `Storage Blob Data Contributor` | Storage account `aledata` | 08:08:50Z |

No resource-group- or subscription-scoped assignment exists for this SP. The other five Batch accounts
and all other storage accounts in `rg-ALEdb` remain untouched.

⚠️ Run without `tee`, so there is no transcript in `logs/` for this step. State was verified
independently afterwards by the query above. Use the `| tee` form from `../README.md` next time.

| 2026-07-31 08:13Z | `03_create_secret.sh` | zhlia@dtu.dk | ✅ Client secret created — see the secret table below. Correctly not logged. |
| 2026-07-31 08:21Z | `05_verify_sp_access.sh` | zhlia@dtu.dk | ⛔ Aborted at the `AZURE_CLIENT_SECRET` guard. No Azure calls made. |
| 2026-07-31 08:23Z | `05_verify_sp_access.sh` | zhlia@dtu.dk | ✅ **ALL CHECKS PASSED** — `logs/05_20260731T082340Z.log`. |

### 2026-07-31 08:23Z — access verification passed

Authenticated as the SP against the real data planes. All eight checks green:

| # | Check | Result |
|---|---|---|
| 0 | SP authenticates with the new secret | ✅ secret valid |
| 1 | List Batch pools on `aledev4test` via AAD | ✅ `Azure Batch Data Contributor` effective |
| 2 | List containers on `aledata` | ✅ |
| 3 | Blob upload / download / delete in `debugging` | ✅ all three, probe cleaned up |
| 4a | **Must NOT** reach Batch account `ale` | ✅ correctly denied |
| 4b | **Must NOT** read storage account `aleprojectdata` | ✅ correctly denied |
| 4c | **Must NOT** read resource group `rg-ALEdb` | ✅ correctly denied |

The negative checks are the substantive result: they demonstrate the grant is genuinely confined to two
resources rather than merely being *believed* to be. Both data planes work with **no** role broader than
a single resource — no `Contributor`, nothing at RG or subscription scope.

**Phase 1 of the cloud-run plan (Azure prerequisites) is complete.** The Entra SP is ready to register
as a Seqera credential.

### 2026-07-31 — preflight findings

- **We can self-assign both roles; no subscription admin needed.** The operator holds **`Role Based
  Access Control Administrator`** on `rg-ALEdb`. Its ABAC condition denies assigning only
  `Owner` / `User Access Administrator` / `RBAC Administrator`; `Azure Batch Data Contributor` and
  `Storage Blob Data Contributor` are **not** on that deny list. This closes the plan's flagged
  "known blocker risk" (Phase 1.2) — the earlier `Contributor without deletes` reading was incomplete.
- **SP is a clean slate**: zero credentials, zero role assignments anywhere. Confirms it is free.
- Batch account `aledev4test`: `allowedAuthenticationModes = [SharedKey, AAD]` → **AAD is enabled**,
  which the Entra service-principal path requires. `poolAllocationMode = BatchService` as Seqera
  expects.
- Batch autoStorage already points at `aledata` — the same storage account we grant blob access on, so
  one grant covers both the Nextflow work dir and Batch's own auto-storage.

| 2026-07-31 08:16Z | _(Seqera web UI)_ | zhlia@dtu.dk | ✅ Entra credential registered in **`DTU-Biosustain/RECON-ALE`**. |
| 2026-07-31 08:3xZ | `06_seqera_readback.sh` | zhlia@dtu.dk | ✅ Credential confirmed; schema captured below. |

### 2026-07-31 — Seqera credential registered, schema captured

Credential `azure_SP_cfb_ale_mutations_pipeline` exists in workspace **`DTU-Biosustain/RECON-ALE`**,
created through the web UI as the plan requires (the credentials API does not validate payloads, so a
guessed field name would save cleanly and fail obscurely at launch).

**The schema — this is the scriptable part.** Provider / `discriminator` = **`azure_entra`**, with
these eight keys:

| Key | Value in our credential |
|---|---|
| `discriminator` | `azure_entra` |
| `batchName` | `aledev4test` |
| `storageName` | `aledata` |
| `clientId` | (set — the SP's application id) |
| `tenantId` | (set) |
| `clientSecret` | secret — withheld by the API |
| `batchKey` | not used on the Entra path |
| `storageKey` | not used on the Entra path |

Verified in the readback: `batchName` and `storageName` match the two resources we granted roles on,
and `clientId`/`tenantId` match the SP. Rotation and any future credential can now be scripted against
these key names instead of guessed.

> ⚠️ The API returns `null` for **every** secret field, so "unset" and "set but withheld" are
> indistinguishable in the readback. Do not infer from `batchKey: null` that no shared key is stored —
> for this credential the Entra form simply never collects one, which is the reason to trust it, not
> the readback.

#### Correction to the plan: `tw` **can** create Entra credentials

The plan records as verified that *"`tw` CLI cannot CREATE Entra credentials — only
`--batch-key/--batch-name/--storage-key/--storage-name`, verified identical in 0.26.0 and 0.38.0"*.
That is **wrong**, and it drove the "must use the web UI" decision. The investigation inspected
`tw credentials add azure` — but there is a **separate `azure-entra` subcommand**, present in the
installed 0.26.0:

```
tw credentials add azure-entra -n <name> -w <org/workspace> \
    --batch-name <batch acct> --storage-name <storage acct> \
    --tenant-id <…> --client-id <…> --client-secret <…>
```

Its five required options map exactly onto the schema captured above. Using the UI for the first one
was still the right call — it guaranteed a known-good shape, and the API genuinely does accept
unvalidated payloads — but **rotation and re-creation are a one-liner**, not a UI chore. Prefer this
over hand-rolled `curl` against `/credentials`, since it validates arguments.

`tw credentials add` also offers an **`ssh`** provider (`-k <private key file>`), which is what makes
the GitHub deploy-key route in plan Phase 2 workable.

### ⚠️ Workspace differs from the plan

The cloud-run plan's commands hardcode `zhlia-wsp`; work actually happens in
**`DTU-Biosustain/RECON-ALE` = `79597273081110`** — org-level and **shared**. Every `-w` in the plan
must be changed, the plan's "existing" assets (shared-key credential, CE) live in the other workspace
and are not available here, and `RECON-ALE`'s six pre-existing shared-key CEs belong to other people's
work — "create a NEW CE, never mutate an existing one" therefore holds for a second reason. (Those six
CEs were eventually retired and deleted 2026-08-13, after this work had replaced them.)

| 2026-07-31 08:43Z | `07_github_deploy_key.sh` | zhlia@dtu.dk | ✅ ed25519 deploy keypair generated at `~/.ssh/seqera_ale_yeast_deploy` (0600). |

### 2026-07-31 — GitHub auth: deploy key chosen (💀 superseded 2026-08-05)

The expired `github_Aletechdev` credential forced a choice, and an **SSH deploy key** won on merit:
repo-scoped, read-only, no expiry to lapse, org-owned rather than person-tied (the workspace is
shared, so a personal token breaks the team on one person's expiry). Generated passphrase-less at
`~/.ssh/seqera_ale_yeast_deploy`, verified end-to-end (`ssh -T` answers `Hi Aletechdev/ALE_Yeast!` —
authenticating as the *repository*, which is the proof it is a deploy key; `git ls-remote` lists
`main` and `v1.0.0`), and registered as Seqera `ssh` credential `github_ALE_Yeast_deploykey`.

**All of it invalidated 2026-08-05** — Platform cannot use an SSH key for a pipeline repository (see
that entry). The keypair survives for local/CI clones; the Seqera registration was deleted 2026-08-07.

| 2026-07-31 | `08_upload_test_data.sh` | zhlia@dtu.dk | ✅ 19 blobs → `az://aletest/ottilie/v1/` (new prefix, no collision). |

### 2026-07-31 — testing `snpeff_cache` as an `az://` directory param

Test data uploaded to the **same** storage account the pipeline authenticates against, so
`snpeff_cache` can be exercised as an `az://` prefix rather than the https route (which cannot work —
Nextflow's http provider has no directory listing, hence the tarball workaround in
`bin/test_ottilie_blob.sh`).

Uploaded (~400 MB of the ~64 GB `data/ottilie/`): `S288C_reference_test/` (15 blobs, incl.
`snpeff_cache/R64-1-1.105/`) and `fastq_test/` (4 blobs). The SP's `Storage Blob Data Contributor`
covers reads at run time — no SAS or shared key needed.

#### RESULT — `az://` directory staging **WORKS**; `--snpeff_cache az://…` is viable

Measured 2026-07-31, verified under two independent auth paths (SP client secret; user-delegation SAS
from an interactive Entra login) and with and without a trailing slash:

| # | Operation | No trailing slash | Trailing slash |
|---|---|---|---|
| 1 | `file('az://…/snpeff_cache').exists()` | true | true |
| 2 | `.isDirectory()` | **false** | **true** |
| 3 | `…/R64-1-1.105` subdir `.exists()` | true | true |
| 4 | `Channel.fromPath(…, checkIfExists: true)` | passes | passes |
| 5 | **Files actually staged into the task** | **7 of 7 ✅** | **7 of 7 ✅** |
| 6 | `Channel.fromPath('az://…/snpeff_cache/**')` | all 7 blobs | — |

**Staging works regardless of the trailing slash**, and regardless of `isDirectory()` returning false.
Nextflow downloads the tree into a `stage-*` directory and symlinks it into the task work dir. The
trailing slash only changes what `isDirectory()` reports (#2) — and the pipeline appends one anyway,
since `snpeff_annotation_cache_key` is `""`, so `file("${snpeff_cache}/")` is what actually gets
evaluated.

Practical consequence: **no tarball workaround is needed for `az://`.** The https limitation is real
and unchanged (no directory listing over http, hence `bin/test_ottilie_blob.sh` untarring locally), but
it does **not** carry over to `az://`. Uploading the test data to `aledata` was the right move and
resolves plan Phase 5's flagged "single most likely functional failure".

> ⚠️ **Correction — an earlier entry here claimed the opposite.** A first pass concluded "az:// stages
> an empty directory, silent failure, use a tarball". That was **wrong**, and the cause was the test,
> not the pipeline: Nextflow stages a directory input as a **symlink**, and `find <link>` does not
> descend into a symlink — so it reported 0 files while all 7 were present. `find -L` shows them.
> `09_test_az_dir_param.sh` now uses `-L`. Two lessons kept deliberately: a verdict must assert on
> staged **content** rather than exit status (still true), and a probe that reports absence must be
> proven able to detect presence before its negative result is believed.

<details>
<summary>Superseded first-pass finding (kept for the record)</summary>

#### ~~RESULT — `az://` directory staging silently produces an EMPTY directory~~

Measured 2026-07-31, and **reproduced twice under two independent auth paths** (the SP client secret,
and a user-delegation SAS minted from an interactive Entra login) — so it is a property of Nextflow's
Azure path handling, not of the credential:

| # | Operation | Result |
|---|---|---|
| 1 | `file('az://…/snpeff_cache').exists()` | **true** |
| 2 | `.isDirectory()` | **false** |
| 3 | `file('az://…/snpeff_cache/R64-1-1.105').exists()` | **true** |
| 4 | `Channel.fromPath(…, checkIfExists: true)` | **passes** — no error |
| 5 | Directory staged into a task | **empty — 0 of 7 files** |
| 6 | `Channel.fromPath('az://…/snpeff_cache/**')` | **works — all 7 blobs enumerated** |

**The distinction that matters.** Nextflow *can* handle `az://` folder paths — #6 proves listing and
globbing over a virtual prefix work fine on this flat (non-HNS) account. What fails is narrower:
passing a **directory prefix as a `path` input** and expecting the tree to be staged. Because
`isDirectory()` is false (#2), Nextflow treats the prefix as a single blob, finds no such blob, and
stages an empty placeholder. **Nothing errors at any layer** — the task exits 0.

Adding a zero-byte directory-marker blob (`…/snpeff_cache/`) was tested and does **not** help:
`isDirectory()` stays false and staging stays empty. The marker was removed afterwards.

> ⚠️ This is the worst failure shape available: not a crash but a silent wrong result. SnpEff would
> annotate against an empty cache and either fail obscurely or emit wrong annotations, with nothing in
> the log pointing back here. The first version of `09_test_az_dir_param.sh` reported ✅ for exactly
> this run because it keyed the verdict on the **exit code**; it now counts the files that actually
> arrived and fails when zero. Any future check of this kind must assert on staged content, never on
> exit status.

**So `--snpeff_cache az://…` is not viable**, and the earlier hope that `az://` would succeed where
`https://` could not is wrong — for different reasons in each case (no directory listing over http; no
directory staging over az).

~~Fix: tarball + untar, mirroring `UNTAR_CHR_DIR`.~~ **Not needed** — see the corrected result above.
A `snpeff_cache` untar path remains a reasonable robustness idea for https-only environments, but it is
**not** a blocker for the Azure run.

</details>

### 2026-08-05 15:44Z — compute environments forged (plan Phase 4) — 💀 CEs since superseded

Two new CEs on the Entra credential (`ale-ottilie-nf25104` and `…-fusion` — single-pool, default boot
disks; both later replaced by the dual-pool/256 GB generation and deleted). None of the six
pre-existing shared CEs was touched. Durable findings, each verified at the time:

- ✅ **Batch Forge works with an Entra SP** — `Azure Batch Data Contributor` on the account sufficed;
  no subscription-level role, no `AuthorizationFailed`.
- ✅ **`-e NXF_VER=25.10.4` stores as head-only** (`head:true, compute:false`), which is all a pin can
  need: **no `nextflow` binary ever executes on a Batch node** (verified from a task wrapper — only
  `NXF_TASK_WORKDIR`/`NXF_DEBUG` are forwarded into containers), so a `both:`/compute pin is a no-op.
  Storing is not taking — always confirm the run log reports the pinned version.
- ⚠️ **Fusion + Entra forged with `managedIdentity*` all `null`** — contradicting the research lead
  that a user-assigned managed identity is required. Runtime proof came 2026-08-07 (`XFwlgZnKvUvpu`).
- ✅ **Forge pools carried the verified `ubuntu-hpc/2404` image** — checked against every pool on the
  account rather than assumed. Re-pinning rules: [`azure_batch_execution.md` §4](../../../docs/dev-practices/azure_batch_execution.md).
- ⚠️ **`tw` 0.26 `--wait AVAILABLE` fails on the *poll*** (`Error reading entity from input stream`)
  while the CE is created fine — re-running creates a **duplicate CE**; read back via the REST API
  instead. Fixed by upgrading to **0.38.0** the same day (SHA-256-verified; the 0.26 binary kept for
  rollback). 0.38 also brought `--pre-run`/`--launch-container` and `--wait` on launch; `tw launch`
  still has no single-param option, so `outdir` must travel in a params file.

### 2026-08-05 — 🚨 the SSH deploy key CANNOT be used to clone the pipeline repo

**Two independent constraints whose intersection is empty:** a GitHub deploy key is an SSH credential
*by definition*, and Seqera Platform's Git integration is **HTTPS-only** — no URL form bridges that.
The key is genuinely valid (`git ls-remote` over SSH reads the repo fine; the same repo over HTTPS:
`Repository not found`), but Platform never consults it. This invalidates the Phase 2 decision above.
Three independent confirmations it is by design: the docs list only HTTPS providers (PAT / GitHub
App / …); Seqera `ssh` credentials exist to reach **SSH-enabled compute environments**, not Git; and
`tw credentials add ssh` has no `--base-url`, so an ssh credential cannot be bound to a Git host even
in principle (readback: `baseUrl: null`).

Also learned, kept because the errors mislead: `tw launch <scp-style-url>` reports `Pipeline '…' not
found on this workspace` (it fell back to a *name* lookup, the message describes the fallback);
**registering to the Launchpad is not a way around** (the Launchpad *is* `tw pipelines` — same
validation, and the head job clones at run time anyway, so a live credential is needed either way);
**Seqera credentials are workspace-scoped** and secret values read back as `null`, so a credential in
another workspace can only be re-entered from the original token, never copied; and the repo is
genuinely private, so *some* credential is unavoidable.

### 2026-08-05 — GitHub App ruled out (no org ownership) → classic PAT

**Decision: classic PAT**, because the better options were blocked by org permissions, not by merit:

| Option | Verdict |
|---|---|
| **GitHub App**, org-owned | **The right answer, and unavailable** — creating and installing one needs org-owner rights on `Aletechdev`, which the operator lacks. A *personally*-owned App buys nothing over a PAT. |
| **Fine-grained PAT** | Real least privilege (`Contents: Read`, one repo) but needs an org owner's *approval*. Submitted in parallel — approved in ~1 day; see 2026-08-07. |
| **Machine-user + PAT** | Repo-scoped and person-free, needs only repo-admin. ⚠️ An outside collaborator on a private repo consumes a paid seat. |
| **Classic PAT (chosen)** | The only option needing nobody's permission. ⚠️ **Cannot be narrowed** — `repo` is all-or-nothing read+write across every reachable repo; strictly broader than the deploy key. The price of the fallback, not a tuning oversight. |

> ⏰ **Record any token's owner and expiry in the table below when it is created** — a shared org
> workspace on one person's token fails, a year later, for someone who doesn't know who to chase.
> 🔁 **Swap to an org-owned GitHub App when an org owner is available** — a credential change and
> nothing else.

### 2026-08-06 — ✅ classic PAT registered; repo clones; first Launchpad entry live (💀 both since replaced)

`personal_token_classic_ALE_yeast` unblocked the clone — proven by `tw pipelines add` succeeding,
since it validates the repository at registration time. Entry `yAMP-ottilie-test` registered (CE
`ale-ottilie-nf25104`, profile `docker`, params pasted from `conf/params_ottilie_test_blob.yml`).
Both since replaced: the PAT by the fine-grained token (2026-08-07), the entry by
`yAMP-ottilie-test-az` (2026-08-12/13). Durable findings:

- ⚠️ **Fine-grained PAT gotcha**: the org *does* appear in the token's **Resource owner** dropdown —
  if the repo seems missing, the cause is Resource owner still set to the personal account.
- ⚠️ **`tw pipelines update` is broken** (HTTP 500; every alternative route fails too — the full
  four-route table is in the 2026-08-12 entry). Every edit is delete-and-re-add, minting a new id.
- **One entry serves many CEs and profiles** — both are overridable per launch, which is also the
  methodologically clean way to compare two CEs with nothing else varying. Separate `outdir` per run.
- 🚨 **An entry stores a pasted COPY of params (`paramsText`), never a reference** — editing the repo
  file changes nothing that entry launches, and the copy rots in silence (the same hazard is written
  into [`seqera_cloud_deployment_checklist.md`](../../../docs/seqera_cloud/seqera_cloud_deployment_checklist.md)
  as if it were a setup step). The fix is profiles + a generated box — see 2026-08-12. Two conditions
  or the profile silently does nothing: the box must not shadow it (`paramsText` is passed as a
  params file, which beats config), and the profile edit must be **pushed** (Platform clones GitHub).
- 📛 Renamed 2026-08-12: `params_ottilie_blob.yml` → `params_ottilie_test_blob.yml` (it is the
  2-sample subset, not a generic default; still read by `bin/test_ottilie_azure_batch.sh` for the
  local head-job path).

## Client secret

| Key id (short) | Display name | Created | **Expires** |
|---|---|---|---|
| `ba06d604…` | `seqera-platform` | 2026-07-31 08:13Z | **2027-07-31 08:13Z** |

> Azure's `hint` field is deliberately **not** recorded here: it is the first three characters of the
> secret itself. Negligible cryptographically, but it is credential material, and this tree holds none.
> Key id plus display name identify the credential unambiguously. Read the hint live with
> `az ad app credential list` if ever needed to match a secret to a key id.

Exactly one credential exists on the app — `--append` worked as intended and nothing was clobbered.
The secret value was never written to this repo.

> ⏰ **Set a calendar reminder for ~2027-06-30** (one month before expiry). An expired secret fails at
> launch with an opaque Azure auth error, a year from now, when nobody has touched this in months —
> this is the single most likely cause of a future "it just stopped working".
>
> 📌 **Since 2026-08-13 the repo also self-warns**: a Claude Code SessionStart hook
> (`.claude/settings.json`) runs `bin/check_credential_expiry.sh` each session and starts warning 60
> days out — for this secret AND the GitHub PAT. It backs up the personal-calendar reminder rather
> than replacing it (it only fires for whoever opens sessions in this repo). After any rotation,
> update the script's dates alongside this file.

### 2026-08-06 — ✅ PHASE 6 COMPLETE: Platform head job runs end-to-end and reproduces the baseline

`ottilie-dualpool-01` (`3C5zYMYY5M32dO`) **SUCCEEDED** — **170 tasks, 0 failed**, matching the local
baseline exactly (138 submitted + 32 cached), with **zero `DiskFull`** on either pool.

Proven for the first time, all in this run: `NXF_VER=25.10.4` takes in a Platform head job; the private
repo clones over HTTPS with the PAT; inputs *and* both directory params (`snpeff_cache`, `chr_dir`)
stage from blob under the Entra SP; containers pull; and **`publishDir` writes to `outdir` from a
Platform-hosted head job** — the last exemption to the same-container SAS rule that had only ever been
verified locally.

**Output comparison vs the verified local-head-job baseline** (`az://aletest/ottilie-azurebatch-out/`):

| | |
|---|---|
| files in common | 529 (540 baseline vs 534 new — the delta is entirely timestamped `pipeline_info/` artifacts; the baseline has two sets because Phase 3.5 ran twice) |
| byte-size identical | 464 |
| differing | 65 — **all in explained classes** |
| **cohort deliverables** | **9/9 byte-identical (md5)** — `cn_cohort_collapsed/full`, `cn_bins_continuous`, `cn_chr_summary_call/germline`, `cn_segments_call/germline`, `sv_cohort_matrix_union/_pass` |

⚠️ **`contentMd5` is NOT populated on these blobs** (0/534) — Azure only stores it when the uploader
supplies it, and Nextflow's publish path does not. The plan's "blob `Content-MD5` vs local md5" method
therefore **does not work here**; compare by size first, then download and hash the files that matter.

The 65 differences classify as: MultiQC plot renders (pdf/png/svg) and `multiqc_data`; igv-reports
`sessionDictionary`; bgzf/gzip framing on `.vcf.gz`/`.tbi`; CRAM ±1 byte; and two Sarek `csv/` files
that **embed the absolute output path** (`seqera-runs/2026-08-06-04` is longer than
`ottilie-azurebatch-out`, which exactly accounts for the +12/+33 byte deltas). Nothing uncategorised,
no variant-content differences.

**`versions.yml` differs by provenance, not content:** `Aletechdev/AMP: v1.0.0` (baseline) vs
`Aletechdev/AMP: v1.0.0-g86c4672` (Platform). nf-core appends the short commit when the pipeline runs
from a **Git clone**; a local-directory run has no commit id. Expected, and desirable.

### 2026-08-06 — root cause of the two failed runs: Docker on the OS disk

Two earlier runs died at **122/138** and **169/170 tasks with ZERO failed tasks** — the signature of a
head-job death, not a pipeline error. The chain:

1. Pool nodes hit **`DiskFull`** and went `unusable`.
2. The head job's node died with them, so Batch rescheduled the head task.
3. The replacement head job tried to re-fetch Platform's **ephemeral launch config** and got **403** —
   the URL is **single-use**. A recoverable node failure therefore became a total run loss.

**It is Docker, not task scratch.** An unusable node had only **0.07 GB across 205 files** in its Batch
task directories — the pressure is `/var/lib/docker` overlay2 on the **OS disk**, from this pipeline's
many tool images (GATK, snpEff, CNVkit, Manta, TIDDIT, igv-reports, MultiQC, FastQC, bwa/samtools).

⚠️ **Concurrency was NOT the cause** — an early hypothesis that proved wrong. The second failure was a
**solo** run. Concurrency only reached the limit faster.

**Fix, both parts needed:**

- **`--dual-pool`** puts the head job on its own pool, so a worker-side disk failure can no longer kill
  a run that is 98% done. This is the durable fix, and it is *cheaper* (head on `Standard_D2s_v3`).
- **`--worker-boot-disk-size 256`** stops the workers filling in the first place.

CE `ale-ottilie-nf25104-bigdisk` (💀 since deleted): the first dual-pool + 256 GB CE, forged with
`tw add … forge` flags — a route later found to silently create **fixed-size** pools (see the
2026-08-07 cost incident); CEs are forged from a template now (`13_create_compute_env.sh`). Verified
at the Azure level that the disk flags genuinely applied (64 GB head / 256 GB worker vs `null` on the
older CEs).

⚠️ **Dual pool requires explicit per-pool VM counts** — omitting `--head-vm-count`/`--worker-vm-count`
fails despite the help text claiming a default. ⚠️ **Dual pool cold-starts slower** — ~17 min for the
head pool to provision vs ~4 min single-pool, because the head job waits on its *own* VM.

> The nicer long-term fix — Docker's data-root on `/mnt` (150 GB ephemeral NVMe) via a pool start
> task — is **deliberately parked** (2026-08-13, see Open items): it needs a `manual` CE that takes
> pool lifecycle, the image pin and `azcopy` back from Forge, to solve a problem dual-pool + 256 GB
> already solved. `preRunScript` cannot do it (head-job scope, not a start task). Detail: §9–§10 of
> [`azure_batch_execution.md`](../../../docs/dev-practices/azure_batch_execution.md).

### 2026-08-06 — other Platform behaviours worth not rediscovering

- **The CE's `NXF_VER` env var beats the launch-UI "Nextflow version" selector.** A run submitted with
  `26.04` selected in Advanced settings still executed **25.10.4**; the selection was silently ignored.
  So you cannot test another engine version from the UI while the CE pins one — use a CE without the
  env var, or a launch-time `--pre-run` that re-exports it.
- **Transient head-job startup failure:** `Unable to access config file .../ephemeral/… Connection
  timed out`, with `start: None` and no Nextflow version reported. Network-level, unrelated to storage,
  credentials or config — it never reached the point of resolving a path. Retry.
- **Seqera shows `manifest.name`, falling back to the repo-derived project name** when a run dies before
  parsing `nextflow.config`. That made one pipeline appear under two names in the runs view; fixed by
  aligning `manifest.name` to the repo handle (see `CLAUDE.md` → Pipeline Identity & Naming).
- **Node `idle` is healthy** — the lifecycle is `creating → starting → idle → running`. `idle` means
  provisioned and waiting for work. The states to worry about are `unusable`, `offline`,
  `startTaskFailed`, `preempted`, `leavingPool`.
- **Batch refuses node removal while autoscale is enabled** (`Remove VMs not allowed when AutoScale is
  enabled`). Use `az batch node reboot --node-reboot-option terminate`. ⚠️ A rebooted node can report
  `state: running, errors: null` and then return to `unusable` minutes later — do not declare a pool
  healthy from one sample.
- ⚠️ **Do not run two pipelines concurrently against one work dir.** Identical code+inputs+params
  produce **identical task hashes**, so both write the same `az://…/nf-work/<hash>` directories. Without
  `-resume` Nextflow does not check for existing dirs and collects outputs by glob, so stale files from
  another run can be picked up as this run's outputs. Use `tw launch --work-dir` to separate them.
- **`tw launch` has no `--resume` flag** in 0.38 (UI/API only).

### 2026-08-07 — ✅ swapped classic PAT → **fine-grained PAT**; org approval landed in ~1 day

`github_ALE_Yeast_finegrained` swapped in; `personal_token_classic_ALE_yeast` deleted from the
workspace **and revoked at GitHub** — two separate actions, and only the second retires the `repo`
read+write reach (a workspace readback looks identical either way). **Correction** to the 2026-08-05
framing ("this org has refused/queued these before"): approval took **about one day**, so the next
person should submit the fine-grained request first and wait a day before reaching for a classic token.

✅ **Verified in live use without spending a run** — reusable technique: note the credential's
`lastUsed` via the API (a genuine usage stamp, distinct from `dateCreated`/`lastUpdated` — all three
differ), open the pipeline's Launchpad form, re-read: `lastUsed` advances, because rendering the form
fetches repo content with the credential live rather than replaying the stored pipeline record. The
`ssh` deploy-key credential read **`never`** under the same test — empirical confirmation that
Platform structurally cannot consult it for a pipeline repo — and was **deleted the same day** (the
keypair survives for local/CI clones). 🗑️ `07_github_deploy_key.sh` was deleted with it (it handed
out dead instructions; recoverable from git history), leaving a deliberate gap in the numbered
sequence. **There is deliberately no replacement script for the GitHub credential**: the token is
minted in the GitHub UI and registered with the hand-typed one-liner under *GitHub PAT* below, so the
secret never enters a transcript or shell history.

**What this fixes, and what it does not.** Blast radius: closed (`Contents: Read` on one repo replaces
`repo` read+write on everything). Person-tied dependency and finite expiry: **unchanged** — the
org-owned GitHub App remains the durable answer and its open item stays open.

### 2026-08-07 — ✅ same-container rule CONFIRMED under a Platform head job (falsification test)

The rule "with an Entra SP, `workDir` must be in the same **container** as the inputs" was verified only
with a **local** head job. Run `48kJmc9QY6Q3h9` (`ottilie-xcontainer-01`) tested it under Platform:
identical to the known-good launch except `--work-dir az://debugging/nf-work-xcontainer`, inputs left in
`aletest`, `outdir` unchanged so only one variable moved.

**Result: 0 succeeded / 6 failed**, dying in `PREPARE_GENOME` ~6 min in (mostly pool warm-up — a cheap
test, no real compute billed). Every failed process reads an input from `aletest`: `SAMTOOLS_FAIDX`,
`GATK4_CREATESEQUENCEDICTIONARY`, `BWAMEM1_INDEX`, `PREPARE_GFF3`, `FASTQC`.

```
.command.log:  Unable to download path:
               https://aledata.blob.core.windows.net/aletest/ottilie/v1/S288C_reference_test/S288C_R64_test.fa
.command.err:  (0 bytes)
```

⚠️ **`.command.err` was empty**, so from the Seqera UI (which shows stderr) this failure looks like *no
error at all*. The real message lives only in `.command.log` in the blob work dir. Anyone debugging a
silent exit-1 here must go fetch it.

So the constraint is a **requirement, not a convention**, and it holds regardless of where the head job
runs — the node-side SAS is minted the same way either way. `outdir` in another container remains
**unproven under Platform**: this run died before publishing, so it tested nothing about `outdir`.
Detail: [`azure_batch_execution.md` §3](../../../docs/dev-practices/azure_batch_execution.md).

The failed run's work dir (58 blobs in the shared `debugging` container) was deleted afterwards.

### 2026-08-07 — ✅ ottilie e2e passed; the hand-edited snapshot is validated

`nf-test test -c tests/nf-test-ottilie.config tests/ottilie_e2e.nf.test` → **PASSED in 802 s**, run
**without** `--update-snapshot` on purpose.

This closes a caveat: the `manifest.name` change was applied to `tests/ottilie_e2e.nf.test.snap` **by
hand** (one line, `Aletechdev/AMP` → `Aletechdev/ALE_Yeast`) rather than regenerated, and was therefore
unverified. A pass proves both halves — the edited value is what the pipeline now emits, **and** nothing
else moved, since the `stable_path` md5 layer would have failed otherwise. The snapshot file is
unchanged on disk after the run.

### 2026-08-07 — Fusion CE re-forged with the dual-pool + disk fixes (💀 since deleted)

`ale-ottilie-nf25104-bigdisk_fusion`: Fusion v2 + Wave, dual-pool, 256 GB workers — carrying the
§9–§10 fixes over so a Fusion run isolates **Fusion** as the single variable instead of re-hitting
`DiskFull`. The original single-pool `…-fusion` was disabled.

### 2026-08-07 — ✅ Fusion + Entra verified, and node disk usage MEASURED (one run, `XFwlgZnKvUvpu`)

`ottilie-fusion-diskprobe` on `ale-ottilie-nf25104-bigdisk_fusion`, with
[`conf/disk_probe.config`](../../../conf/disk_probe.config) attached via `--config`, a **fresh** outdir
(`az://aletest/seqera-runs/2026-08-07-02-fusion`) and a **fresh** work dir (`nf-work-fusion02`).
**SUCCEEDED — 170/170 tasks, 0 failed, 0 `DiskFull`.**

**1. Fusion + Entra SP works.** The plan flagged this as *unverified*, since the only working Fusion CE
was on a **shared-key** credential. It now runs on the Entra SP, with dual-pool and 256 GB workers.
All **9 cohort deliverables byte-identical** to the validated non-Fusion baseline
(`seqera-runs/2026-08-06-04`), 534 blobs. Note this run is on current `main` (`12a599d`, the new
`manifest.name`) while the baseline is `86c4672` — so the deliverables match across **both** the Fusion
change and four commits.

⚠️ An earlier Fusion run (`3eXbxZVVpOPtGW`) also succeeded 170/170, but it shared outdir
`2026-08-07-01` with the non-Fusion `5Ped8HWvzzjoDx`, so that directory is a **mixture** and is not a
citable artifact. `2026-08-07-02-fusion` is the clean one.

**2. Peak OS-disk usage is ~65 GB** — measured across 21 nodes, not inferred:

| disk size | peak used | range | free at peak |
|---|---|---|---|
| 246.9 G | **65.2 G (26%)** | 56.7–65.2 G | 182 G |

- A 57–65 GB working set overruns the default OS disk, whatever it is — that is the whole `DiskFull`
  story, and it confirms the concurrency hypothesis was wrong: a solo run exceeds the default on its
  own. ⚠️ **This bullet originally asserted "the default is ~30 GB, so 57–65 GB overruns it 2×".
  That figure was an assumption, never measured**, and `az vm image show` does not return
  `osDiskImage.sizeInGb` for this image. The default is only known to be *large enough* for 122/138
  and 169/170 tasks before filling, i.e. somewhere near the 65 GB peak — 64 GB would fit the observed
  failure timing exactly, but that is inference. See
  [`azure_batch_execution.md` §9](../../../docs/dev-practices/azure_batch_execution.md).
- 256 GB is ~3.8× the peak; 128 GB would suffice. The margin costs ~$0.05/hr across four nodes.
- ✅ **The `/mnt` relocation fix is viable**: 65 GB fits inside the 150 GB ephemeral NVMe — the
  assumption that fix rested on.

⚠️ **Correction to the config's original comment:** `beforeScript` runs **inside the container**, not on
the node (`hostname` = container id, `/` = `overlay`). The reading is still valid — overlay2's `df`
reports the backing filesystem, and 246.9 G matches the OS disk — but the mechanism is not as stated.
⚠️ **Under Fusion the work-dir `df` is useless**: it reports a synthetic `fusion 8.0P … 50% /fusion`.
Only the `root:` line is usable there.

### 2026-08-07 — 🚨 COST INCIDENT: `tw --dual-pool` creates FIXED-SIZE pools (~$66/day)

**Ten nodes ran idle for hours.** Both dual-pool CEs forged with `tw` read back
`autoScale: null`, which Azure builds as `enableAutoScale: False` — fixed at 1 head + 4 workers:
**8× `E4ds_v4` + 2× `D2s_v3` ≈ $2.75/hr compute plus ~$324/month of managed disks**, billing
regardless of load. Noticed only because a cold pool was wanted for a disk baseline and the pools
would not drain; **reproduced deliberately** with a throwaway CE — repeatable CLI behaviour, not a
one-off. Root cause: for dual-pool the CLI **omits** the `autoScale` field (single-pool is
unaffected), nothing warns, and `tw` reports success. The web UI *can* set it — but "use the UI" was
**superseded 2026-08-11**: CEs are created from a template now (next entry). Remediation: pools
resized to 0; the fixed-size CEs were eventually deleted 2026-08-13.

**Guard added:** [`12_verify_compute_env.sh`](12_verify_compute_env.sh) asserts `autoScale` on both
pools (plus workDir and disk sizes) and fails with the resize/delete steps. ⚠️ **CEs are immutable** —
verify *before* launching, not after the invoice.

⚠️ **A new pool shows 1 node for its first ~5 minutes by design** (the Forge formula pins the first
interval) — `1 + 1` right after creation proves nothing; **`0 + 0` fifteen minutes later** is the real
check. Unrelated to Wave/Fusion. ⚠️ **`--worker-vm-count` is a CEILING under autoscale**, not an
allocation.

### 2026-08-11 — ✅ CEs are now created from code (`tw compute-envs import`)

**CEs are no longer created by hand, and not the way that was planned either.** The plan was a raw REST
creator, "since the CLI cannot express the one field that matters". `tw` *can*: **`compute-envs
export`/`import` round-trip `autoScale`**, and neither subcommand had been tried — the 2026-08-07
investigation stayed inside `add ... forge`'s flag set and generalised from it. **No API client was
written.**

| Ran | Result |
|---|---|
| `tw compute-envs export -n …_autoScale_manual_noFusion` | `headPool.autoScale: true` / `workerPool.autoScale: true` in the exported JSON |
| `./13_create_compute_env.sh ale-ce-import-test` | CE `5HMxAhK0lWX4X7JUDhoOVm` AVAILABLE; `12_verify_compute_env.sh` **6/6 OK** |
| `az batch pool list` at creation | both pools `enableAutoScale: True`, at the expected `1 + 1` |
| same, 17 min later (08:20Z) | **`0 + 0`** — autoscale genuinely working |
| `./13_create_compute_env.sh … --delete` | CE DELETED; both pools disposed by 08:25Z, no orphaned disks |

Cost of the test: ~5 node-minutes (1× `D2s_v3` + 1× `E4ds_v4`).

**Two corrections to the 2026-08-07 entry above.**

1. **`tw add ... forge` CAN set autoscale**, via explicit `--head-no-auto-scale=false
   --worker-no-auto-scale=false`. Undocumented in `--help`; from
   [seqeralabs/tower-cli#658](https://github.com/seqeralabs/tower-cli/issues/658). Verified here by
   inspecting the request payload with `tw -v` against an existing CE name — the collision is rejected
   *after* the body is printed, so the check costs nothing and creates nothing.
2. **The field is OMITTED, not sent as `null`.** The control payload (no flags) has no `autoScale` key
   at all on either pool; the `null` in the 2026-08-07 entry is Platform's readback of the missing
   field. Both descriptions are correct, at different layers.

**Decision: `import` is the route, `=false` is an escape hatch.** `add ... forge` has **no flags** for
`jobMaxWallClockTime`, `deleteJobsOnCompletion`, `deleteTasksOnCompletion` or
`terminateJobsOnCompletion`, so a flag-built CE silently takes Platform defaults for the four
job-lifecycle settings our CEs pin (`7d` / `never`). Fixing autoscale that way trades a loud bug for a
quiet one. The template is a readback, so every field in it is one Platform wrote.

⚠️ **The upstream fix is not released.** [#659](https://github.com/seqeralabs/tower-cli/pull/659) is
**open/unmerged** as of 2026-08-11 and **0.38.0 is the latest release** — there is no version to upgrade
to. Re-check when it merges: plain `add --dual-pool` becomes safe, but the job-lifecycle gap remains.

**Files:** [`13_create_compute_env.sh`](13_create_compute_env.sh) (`<name> [--fusion|--delete]`) ·
[`ce_import_template.json`](ce_import_template.json) (export of the working non-Fusion CE; `--fusion`
flips only `fusion2Enabled`/`waveEnabled`). ⚠️ `tw` strips the template's trailing `"labels": []` —
labels go through `--labels`, not the config body. The script refuses to run if the template's
`autoScale` is not `true`.

### 2026-08-12 — Launchpad params moved into the repo, and the one default that refuses to move

**New entry `yAMP-ottilie-test-az` (`172614290773283`)**, registered by
[`14_register_pipeline.sh`](14_register_pipeline.sh) because `update` is dead (four-route table
below). Config profiles **`docker, ottilie_test_az`** — the params live in the repo, read from the
clone at every launch, so there is no pasted copy to rot. The CE is the autoscaling non-Fusion keeper;
`nextflowVersion` and `configText` unset. **One entry, not one per dataset** — profiles are
overridable per launch, exactly as the CE is, so the full-depth pilot runs from this same entry with
`-p docker,ottilie_pilot_az` plus its own `outdir`. (An earlier same-day registration of this entry
under id `227711052831937` was itself replaced within hours — the id churn below is why.)

⚠️ **There is NO way to change a registered entry in place — all four routes were tried (2026-08-12):**

| Route | Result |
|---|---|
| `tw pipelines update` | **HTTP 500**, any combination of options |
| `PUT /pipelines/{id}` direct | **HTTP 400**, both with `name` added and with the full launch object round-tripped from `GET` |
| `tw pipelines versions manage` | only **renames** a version or sets it default — cannot create one |
| `tw pipelines import --overwrite` | works, but reports *"New pipeline added"* and **the pipeline id changes** — delete-and-re-add underneath |

So every edit mints a new pipeline id, and **a bookmarked Launchpad URL breaks each time**. Nothing in
this repo depends on the id; only this entry records it. Platform pipelines *do* carry versions
(`yAMP-ottilie-test-az-1`, default), but nothing exposed by `tw` or the API can add one.

🔬 **And the version hash is blind to the repo — a reproducibility trap.** `main` advanced
`1e09fc3` → `bd591b6` (six commits, two new profiles, a config refactor) and the hash was
**byte-identical before and after**: it is content-addressed over the *stored entry* only. The entry
pins the branch **name**; Nextflow resolves it to a commit at launch, so the same entry runs different
code as `main` moves. Re-registering identical content also reproduces the hash under a *new* id —
seen three times today — so an unchanged hash proves nothing either way.
**Never cite a pipeline name, version name or hash as provenance.** Use the run's `commitId` (run
`2eiGBEA0NXagap` recorded `1e09fc3c9f6c…`, which the entry never mentioned), the `versions.yml` in the
published outdir, or `--commit-id <sha>` at registration for an entry whose results you intend to cite.
Full detail: [`azure_batch_execution.md` §14](../../../docs/dev-practices/azure_batch_execution.md).

**`-p <profile>` stores a REFERENCE; `--params-file` stores a SNAPSHOT.** The profile name is resolved
by Nextflow after the head job clones the repo, so params are whatever the file says at launch time.
`--params-file` is read once by `tw` and frozen into `paramsText`. Because `update` is broken, a frozen
copy can only be changed by re-registering; the profile is changed by a commit and a push.

**🖥️ The box nevertheless carries the FULL param set — a deliberate UX trade.** Platform's launch form
populates its fields from `paramsText` only; profile values are applied at runtime but never displayed,
so the launch page showed an empty `input` box and a reader had to open the profile to learn what would
run. That break was judged worse than the alternative. The box is therefore **generated from the
profile** (`./14_register_pipeline.sh --generate`), not hand-copied, and a normal run of the script
re-derives it and **aborts on drift** — so the two artifacts cannot silently diverge.

⚠️ **Consequence: a Launchpad run is now driven by the box, not the profile** (`-params-file` beats
config). Changing a param means edit profile → `--generate` → commit → re-register, and re-registering
mints a **new pipeline id** every time. The profile remains the single source of truth and is what local
runs and nf-test actually execute.

**`outdir` is emitted as a deliberately disposable default:** `az://aletest/seqera-runs/yAMP-out-test-DUMP`.
It is *not* taken from the profile — the profile's value is a Groovy timestamp, and freezing one
evaluation of it into the box would send every future run to one stale second. A populated field was the
whole point of generating the box, so the compromise is a destination whose **name announces that it is
not one**: runs that leave it publish on top of each other, and since `publishDir` overwrites but never
deletes, that directory accumulates a mixture and is not citable. ⚠️ **Change it in the launch form for
anything you intend to compare, publish or cite.** The profile's timestamped
`yAMP-out-test-<YYYYMMDD-HHMMSS>` still governs local runs, which have no params box.

**🚨 First launch failed, and the cause is worth knowing.** Run `2eiGBEA0NXagap`, `-profile
docker,ottilie_test_az`, died with `No such file or directory: s3://annotation-cache/snpeff_cache/R64-1-1.105`
— the nf-core default — even though the profile sets an `az://` path *and Platform's own resolved
config for that run shows the `az://` value*. The launch form **injects some `nextflow_schema.json`
defaults into the submitted params**, and submitted params beat config. Four params were submitted from
a two-line box: `step` and `outdir` from the box, `snpeff_cache` and `custom_config_base` injected.
Not every schema default is injected — `split_fastq` and `genome` were not, and the profile's values
survived — which is precisely what makes it easy to miss. Mechanism, and the two API calls that
distinguish *submitted* from *resolved*: [`azure_batch_execution.md` §13](../../../docs/dev-practices/azure_batch_execution.md).

**Consequence: `snpeff_cache` is repeated in the params box on purpose.** It is the only param that
must be, and it is also the one that differs between the two datasets
(`S288C_reference_test/snpeff_cache` vs `S288C_reference/snpeff_cache`). So running the pilot from this
entry means changing **two** things at launch — `-p docker,ottilie_pilot_az` *and* that path. The box
says so in a comment. If the pilot becomes routine, give it its own entry instead.

⚠️ **`nextflowVersion` deliberately unset**, unlike the old entry which stored `26.04`. That never took
effect — the CE's `NXF_VER=25.10.4` wins (§12) — and it contradicts what runs, since 26.x cannot parse
`nextflow.config`. Pinning the engine per *pipeline* rather than per *CE* is arguably the better model,
but neither `tw pipelines add` nor `tw launch` has a `--nextflow-version` flag, so it is UI-only, and
the CE pin also covers ad-hoc launches. Revisit if `tw` gains the flag.

⚠️ **The params box cannot be empty or comments-only** — Platform rejects that with *"Invalid
ParamsText format"*, because a comments-only document is valid YAML that parses to `null` rather than an
object. Hence the inert `step: "mapping"` (already the schema default). **Comments themselves are
preserved verbatim**, confirmed by readback, which is what makes the box usable as in-place guidance.

⚠️ **The launch form cannot display what a profile sets.** It renders from `nextflow_schema.json` plus
the stored `paramsText`, never from a profile — so `input`, `fasta` and `tools` appear blank even though
they are set at runtime. That is the real cost of this design; the comment block in the box is the
mitigation. 📌 Do **not** "fix" it by moving dataset paths into `nextflow_schema.json`: schema defaults
are pipeline-wide, are applied by nf-schema at runtime, and would make an ottilie samplesheet the
default for every use of this pipeline — besides diverging from upstream Sarek 3.5.1.

**`outdir` is not pinned in the box.** Both `_az` profiles now compute
`az://aletest/seqera-runs/yAMP-out-{test,pilot}-<YYYYMMDD-HHMMSS>` in Groovy, so two launches can never
publish into the same directory even if nobody edits anything. Verified at run time: consecutive runs
resolved `…-20260812-150202` and `…-20260812-150208`, and an explicit `outdir` still overrides. ⚠️ It is
evaluated when the head node parses the config, so a `-resume` publishes to a **new** directory — pass
an explicit `outdir` when resuming. ⚠️ `workflow.runName` is **not** available in config on 25.10.4
(`Unknown config attribute`), which is why this uses a timestamp rather than the Platform run name.

✅ **The old `yAMP-ottilie-test` (`227651105760023`) was deleted 2026-08-13**, once run
`1XuapND2cN2oCO` proved the new entry end to end. It was kept until then precisely because a readback
proves configuration, not behaviour.

**Registration is now scripted:** [`14_register_pipeline.sh`](14_register_pipeline.sh) +
[`launchpad_params_ottilie_test_az.yml`](launchpad_params_ottilie_test_az.yml). The box content lives
in the repo, so the copy Platform holds is reproducible and reviewable rather than existing only in a
browser field — which is how the 2026-08-07 entry came to carry params naming a file that no longer
existed. The script deletes-then-adds (no working `update`), refuses a params box that does not parse
to a non-empty object, asserts `snpeff_cache` is present and `nextflowVersion` unset on readback, and
warns when `conf/test/` has uncommitted changes or local is ahead of `origin` — the two ways a launch
silently runs code you are not looking at. `DRY_RUN=1` prints without touching anything.

**Still an interim shape.** Every param is duplicated between the profile and the generated box — the
duplication this change set set out to remove. It is accepted because the two alternatives were worse:
a minimal box breaks the launch-page UX, and no box at all breaks the run outright (`snpeff_cache`).
The duplication is at least *generated and drift-checked* rather than hand-maintained. A genuinely
elegant fix needs one of: Platform reading profiles when rendering the form, Platform not injecting
schema defaults, or `tw pipelines update` working so the box can be refreshed without a new id.

### 2026-08-13 — ✅ the profile/box change set VALIDATED by a run, and two new traps

**Run `1XuapND2cN2oCO`**, launched from the UI on `yAMP-ottilie-test-az` → CE `yAMP-ce-nofusion-256`,
`outdir az://aletest/seqera-runs/yAMP-out-test-20260813`. **All nine cohort deliverables byte-identical
to the `2026-08-06-04` baseline** (downloaded and md5'd — `contentMd5` is not populated on
Nextflow-published blobs), 534 blobs.

| Proved by this run | Evidence |
|---|---|
| Config refactor (`ottilie_common` + `_az` profiles) is behaviour-preserving **in the cloud** | 9/9 deliverables identical; local `nextflow config` equality had only proved it on paper |
| Params via the generated box, not a pasted copy | 17 submitted params, 16 ours + `custom_config_base` |
| `snpeff_cache` repeated in the box fixes §13 | ran past the point that killed `2eiGBEA0NXagap`; **no `s3://` injection** |
| **Engine pin moved CE → Launchpad entry** | head job ran **25.10.4** with **no `NXF_VER` on the CE** |
| `import` carries `nextflowVersion` where `add` cannot | that pin arrived via `14_register_pipeline.sh` |
| A CE forged by `13_create_compute_env.sh` runs real work | dual-pool, autoscaled, no `DiskFull` |
| `main` is resolved at launch (§14) | run recorded `commitId 2fc5ccf3`, which the entry never names |

🚨 **Trap 1 — the run was reported `UNKNOWN` while succeeding.** Platform froze at 132/9 (`lastUpdated`
11:47:31Z) because the head job **completed the pipeline and then hung instead of exiting**, so the
terminal status was never sent. `tw runs cancel` killed it (`exitCode 137`) and pools drained to `0+0`
within 5 minutes — but the run is now filed as **`CANCELLED`**, for a run whose outputs are complete
and verified. ⚠️ **Cite this run by evidence, never by its Platform status.** Mechanism, both failure
directions, and the two authoritative sources:
[`azure_batch_execution.md` §15](../../../docs/dev-practices/azure_batch_execution.md).

🚨 **Trap 2 — `jobMaxWallClockTime` does not apply to the head job.** `ce_import_template.json` sets
`"7d"`; Azure reported `TimeSpan.MaxValue` (no limit) on `nf-workflow-1XuapND2cN2oCO`. A hung head job
therefore holds its node **indefinitely** — the head pool cannot scale to 0 while a task is `running`.
Only noticed because the pool was being watched. **Added to Open items.**

**Also changed today:** `NXF_VER` removed from `ce_import_template.json`; `12_verify_compute_env.sh`
no longer requires it (`EXPECT_NXF_VER` defaults empty — set it to re-assert on an older CE);
`14_register_pipeline.sh` registers via `import` with `NEXTFLOW_VERSION` and asserts it on readback.
⚠️ The trade: a launch that does **not** come from an entry carrying the pin now gets Platform's
default engine, and 26.x cannot parse `nextflow.config`.

### 2026-08-13 — 🧊✅ COLD-POOL DISK BASELINE MEASURED (full-depth pilot, run `18wEWW90THA2Ek`)

**Base ≈ 45 G, pipeline adds ≈ 15 G, peak 60.0 G of 246.9 G; task-scratch disk peaked at 2.7 G.**
The 2026-08-12 spec was executed as written: fresh CE `yAMP-ce-coldprobe-256` forged with
`13_create_compute_env.sh` (6/6 checks; new pools = genuinely cold nodes), launched from
`yAMP-ottilie-test-az` with `-p docker,ottilie_pilot_az --config conf/disk_probe.config`, params
overridden to **two lines only** (pilot `snpeff_cache` + explicit
`outdir az://aletest/seqera-runs/yAMP-out-pilot-coldprobe-20260813`), fresh
`workDir az://aletest/nf-work-coldprobe-20260813`. **SUCCEEDED — 310/310 tasks, 0 failed**, 54 min
(13:23–14:17Z), engine **25.10.4**, `commitId e1b95a2`. All 310 `.command.log`s were harvested — the
numbers are a census, not a sample. Conclusions + numbers live in
[`azure_batch_execution.md` §9 → cold-pool baseline](../../../docs/dev-practices/azure_batch_execution.md);
the headlines: the base is the `ubuntu-hpc 2404` OS image itself (~45 G before any pipeline image);
image pulls, not data, drive the growth (11× the input data did not move `/` usage); **128 GB would
suffice**; the `/mnt` relocation fix has ample headroom (images ~15 G + scratch ≤2.7 G vs 150 G).
The CE was deleted after harvest; pools disposed; the Batch account is back to only
`yAMP-ce-nofusion-256`'s two pools. Outputs kept at the outdir above (no truth set — diagnostic, not
citable as a validation).

Traps found while doing it, each verified:

- **`deleteTasksOnCompletion: true` (our template) erases Batch task records as tasks finish**, so a
  post-hoc task→node mapping via `az batch task list` is impossible — the per-process jobs survive
  (`deleteJobsOnCompletion: never`) but are all empty. Also: those jobs are named
  `job-<hash>-<PROCESS>` with **no run id in the name** — filter by *pool id* to find a run's jobs.
  Node attribution for the measurement came from Seqera's task records (workdir + timestamps) plus
  the df trajectories themselves; a future run wanting exact mapping must snapshot task lists *during*
  the run.
- **`tw pipelines export` silently omits `nextflowVersion`** even when the entry has it set —
  readback shows `None` while `GET /pipelines/{id}/launch` shows `25.10.4`. Do not audit the engine
  pin via `export`.
- ✅ **`tw launch` from an entry DOES carry the entry's `nextflowVersion`** (verified in the submitted
  launch record before the run started), and **does not inject schema defaults when `--params-file`
  is given** — 2 params in, 2 params submitted, no `s3://` `snpeff_cache`. The §13 injection is a
  launch-*form* behaviour.
- ✅ **The head job exited cleanly** — status `SUCCEEDED`, pools drained to 0 unaided. The
  `1XuapND2cN2oCO` hang is therefore intermittent, not systematic; the reaper open item stays open.

### 2026-08-13 — ✅ Fusion does NOT lift the same-container rule; cross-container `outdir` publish DOES work (run `3AJ4JRNkb7D2dG`)

`ottilie-xcontainer-fusion-01` repeated the `48kJmc9QY6Q3h9` predicted-failure launch on a freshly
forged Fusion CE (`yAMP-ce-fusion-256`, forged and deleted the same day by `13_create_compute_env.sh
… --fusion`): inputs in `aletest`, `--work-dir az://debugging/nf-work-xcontainer-fusion-20260813`,
explicit `outdir` back in `aletest`, `conf/disk_probe.config` attached. **FAILED — 0/6 tasks, the
same six `aletest`-reading processes as the baseline, ~5 min in** (engine 25.10.4, `commitId 0a9e65c`).
A cheap test, and each of its four findings is one the baseline could not give:

1. **The same-container rule is a property of the credential delegation, not of the data path.**
   Fusion consumed the same single container-scoped user-delegation SAS Nextflow mints for the
   work-dir container and presented it against `aletest` — `.fusion.log` records the server's
   `403 AuthenticationFailed` with the string-to-sign scoped to the work-dir container, plus Fusion's
   own summary: *"Fusion authenticated successfully but lacks permission to access this resource."*
   The rule is now confirmed under both the azcopy (non-Fusion) and FUSE (Fusion) data paths —
   **do not design around Fusion lifting it.** §3 of
   [`azure_batch_execution.md`](../../../docs/dev-practices/azure_batch_execution.md) updated.
2. **Debuggability is better under Fusion.** `.command.err` is non-empty (`Permission denied` from
   samtools) and `.fusion.log` carries the full 403 — unlike the non-Fusion signature, where the only
   evidence is `Unable to download path` in `.command.log` and stderr is empty.
3. **Cross-container `outdir` under a Platform head job: proven for `publishDir` writes.** The head
   job published five `pipeline_info/` files into
   `az://aletest/seqera-runs/yAMP-out-xcontainer-fusion-20260813/` (kept as evidence) while `workDir`
   sat in `debugging` — publishing runs in the head process under the full SP credential, exempt from
   the node SAS rule, now verified under Platform and not only locally. Task-output publishing uses
   the same head-side mechanism but has not been demonstrated end-to-end by a successful
   cross-container run.
4. **The disk probe is `root:`-only under Fusion, `/mnt` line included.** Cold node: 47.4 G of
   246.9 G ≈ the ~45 G base + first image pulls. The `work:` line reports Fusion's synthetic
   `8.0P /fusion`; the `mnt:` line reports the **container overlay**, not the host `/mnt` — so
   Fusion-cache-vs-Docker competition for the ephemeral disk remains unmeasurable from inside a
   container. No cache-growth data from this run (it died before real I/O); that needs a successful
   same-container Fusion run with the probe attached.

Cleanup: CE deleted (pools and disks disposed — the Batch account is back to only
`yAMP-ce-nofusion-256`'s two pools); the `debugging` work dir purged; the outdir evidence blobs kept.

### 2026-08-13 — 🧊✅ FUSION CACHE FOOTPRINT MEASURED (run `47xZrJ3vg4avR9`): ≲3 G on the OS disk at test-set scale

`ottilie-fusion-cache-01` executed the open item's recipe as written: fresh **cold** Fusion CE
(`yAMP-ce-fusion-256`, second forge of that name, deleted after harvest), inputs + `workDir` together
in `aletest` (`nf-work-fusion-cache-20260813`), `conf/disk_probe.config` attached, explicit
`outdir az://aletest/seqera-runs/yAMP-out-fusion-cache-20260813`. **SUCCEEDED — 170/170 tasks, 0
failed**, engine 25.10.4, `commitId 35e170a`, head job exited cleanly. All 170 `.command.log`s
harvested — a census, not a sample.

| `root:` usage (170 readings) | value |
|---|---|
| min (first task on a cold node) | **45.4 G** — the `ubuntu-hpc` base, matching the non-Fusion cold baseline exactly |
| median / p90 | 53.5 G / 55.5 G |
| **peak** | **63.0 G of 246.9 G (26%)** |

**Conclusion: at test-set scale Fusion adds ≲3 G of OS-disk pressure** — the non-Fusion cold picture
is base ~45 G + images ~15 G ⇒ ~60 G, and the Fusion peak with the same image set is 63.0 G. The
sizing conclusions are unchanged (256 GB ample, 128 GB would still suffice), and the parked `/mnt`
relocation stays parked — Fusion adds no reason to revisit it at this scale.

Caveats, so the number is not over-read:

- **No per-node attribution under Fusion**: the probe's `host=` is the *container* id there — 170
  distinct values across ≤5 nodes — where non-Fusion runs showed node-stable ids (21 hosts across
  340 tasks on 2026-08-07). The peak is a fleet-wide max, not a per-node trajectory.
- **Cache growth may scale with data volume.** The test set stages ~400 MB of inputs; eviction was
  not probed. Re-measure at pilot scale if Fusion ever becomes the default — the standing interim
  policy (probe attached to Fusion dev runs) covers exactly this.
- Readings are point-in-time at task start (`beforeScript`), so intra-task growth is invisible —
  the same limitation as every probe run.

Outputs published to the outdir are **diagnostic, not citable** (probe perturbs task hashes; no
baseline comparison — Fusion output identity was already proven by `XFwlgZnKvUvpu`). Cleanup: CE
deleted with pools and disks; work dir purged after harvest; the Batch account is back to only
`yAMP-ce-nofusion-256`'s two pools.

## GitHub PAT (fine-grained — current credential)

| Seqera credential | Provider | Scope | Owner | Created | **Expires** |
|---|---|---|---|---|---|
| `github_ALE_Yeast_finegrained` (`2NhER3hJHchursPHekAV1P`) | `github` | **`Contents: Read` on `ALE_Yeast` only**, resource owner `Aletechdev` | **personal** account of the operator — GitHub user `zhliUU`, Seqera user `zhlia` | 2026-08-07 | **2027-08-07** (Sat) |

**Registered `baseUrl` = `https://github.com/Aletechdev/ALE_Yeast`** — read back from the API, and
worth recording because it is **repo-level, not org-level**. That is the field Platform matches a
pipeline URL against, so this credential answers for *this repository only*; a second repo under
`Aletechdev` would need its own credential, which mirrors the token's own `Contents: Read on ALE_Yeast`
scope rather than fighting it. ⚠️ Earlier entries in this runbook show `--base-url
https://github.com/Aletechdev` (org-level) — that is what was typed for the **classic** PAT. Rotating
with the org-level form would register a *differently scoped* match than the credential in use, and if
both existed they would overlap on this repo — exactly the ambiguity warned about below.

> ⏰ **Calendar reminder set for ~2027-07-24** (two weeks before expiry). This is a *shared org
> workspace* running on *one person's* personal token: when it lapses, every launch in the workspace
> fails with the opaque `Unknown pipeline repository or expired Git credentials`, and the person who
> can fix it may not be the person who hits it. This has already happened once here —
> `seqera-platform-ale-16april2026` expired unnoticed and cost a full debugging session. **A year of
> silence is exactly the condition under which that recurs.**

Re-registering or rotating it — run it yourself so the token never enters a transcript or shell history:

```bash
read -rsp 'GitHub token: ' GH_TOKEN && export GH_TOKEN
tw credentials add github -n github_ALE_Yeast_finegrained -w DTU-Biosustain/RECON-ALE \
    -u zhliUU -p "$GH_TOKEN" --base-url https://github.com/Aletechdev/ALE_Yeast
```

`-u` must be the GitHub account that **owns the token**, not the org and not the Seqera username.
Both values above reproduce the credential currently in use; verify after any change with
`GET /credentials?workspaceId=…`, which returns `baseUrl` and `keys.username` in clear (secrets read
back as `null`).

⚠️ **Add before deleting, and never leave two `github` credentials matching the same `--base-url`** —
which one Platform picks is undefined, so an overlapping pair makes any failure unattributable.

<details><summary>Retired — the classic PAT it replaced (2026-08-06 → 2026-08-07)</summary>

| Seqera credential | Provider | Owner | Created | Expiry (if never revoked) |
|---|---|---|---|---|
| `personal_token_classic_ALE_yeast` (`Z3yo4zFgy1xfdW0Ts11kI`) | `github` | **personal** account of the operator (Seqera user `zhlia`) | 2026-08-06 | 2026-11-04 (Wed) |

Scope: classic **`repo`**. ⚠️ This could not be narrowed — `repo` grants read *and write* on every
repository the owner can reach, so it was **strictly broader than the deploy key it replaced**. That is
a property of classic PATs, not a configuration mistake: GitHub provides no read-only scope for private
repositories. It was deliberately given a short 90-day expiry because it was always a stopgap; in the
event it was retired after **one day**.

Deleted from the `RECON-ALE` workspace on 2026-08-07. ⚠️ **Deleting the Seqera credential does not
revoke the token** — see the open item below.

</details>

## Open items

> 📋 **Slimmed 2026-08-13** (from ~1,440 lines: superseded sagas compressed, 💀 marks entries whose
> resources no longer exist, every ⚠️ and correction kept). The standing convention (`CLAUDE.md`'s):
> dated record here — *what was run, when, what was concluded* — durable rules in
> `azure_batch_execution.md`, summary + pointer in `CLAUDE.md`. Write new entries in that shape, keep
> corrections (so wrong conclusions are not re-derived), and after edits run
> `python docs/dev-practices/check_docs.py` — broken links must be 0.
> 📌 `NEXT_TASKS.md` (the 2026-08-07 handoff file) was **retired 2026-08-13**: its Task 1 (CE-as-code)
> was closed 2026-08-11, this banner absorbed Task 2 (doc slimming, executed the same day), and every
> remaining item it listed was already tracked in the list below.

- [x] Grant the two roles (`02_grant_roles.sh`) — done 2026-07-31, verified.
- [x] Create a client secret (`03_create_secret.sh`) — done 2026-07-31.
- [x] Verify both data planes (`05_verify_sp_access.sh`) — done 2026-07-31, all checks passed.
- [x] Register the Entra credential in Seqera via the web UI — done 2026-07-31, schema captured.
- [x] Create a new compute environment bound to the `azure_SP_cfb_ale_mutations_pipeline` credential,
      with `NXF_VER=25.10.4` pinned via the head-job environment (plan Phase 4) — done 2026-08-05,
      two CEs (non-Fusion + Fusion), both AVAILABLE. The six existing CEs were not repointed.
- [x] Add `outdir` to `conf/params_ottilie_test_blob.yml` — done 2026-08-05, date-stamped, preview-verified.
- [x] Create a classic GitHub PAT and register it in `RECON-ALE` — done 2026-08-06,
      `personal_token_classic_ALE_yeast`; the repo clones over HTTPS. **Superseded 2026-08-07.**
- [x] Register the Launchpad pipeline — `yAMP-ottilie-test` (`227651105760023`), done 2026-08-06.
- [x] Chase the **fine-grained PAT** approval — **approved and swapped in 2026-08-07**, ~1 day after
      submission. Credential `github_ALE_Yeast_finegrained`; the classic credential was deleted from the
      workspace and the new one is **confirmed in live use** — opening the Launchpad form advances its
      `lastUsed` on demand (see the entry above).
- [x] Record the current PAT's owner and expiry — done: expires **2027-08-07**, see the table above.
- [x] **Revoke the retired classic token at `github.com/settings/tokens`** — done 2026-08-07. Deleting
      the Seqera credential only stopped Platform using it; revoking at GitHub is what actually retires
      the `repo` read+write reach. Both halves are now complete, so the switch's security benefit is
      banked rather than merely intended.
- [x] Delete the unused `github_ALE_Yeast_deploykey` (`ssh`) credential from `RECON-ALE` — done
      2026-08-07, verified by readback (three credentials remain: `github`, `azure_entra`, `azure`).
      The keypair itself is untouched and stays usable for local/CI clones; only the Platform-side
      registration was removed.
- [x] ⏰ Calendar reminder for **~2027-07-24** (two weeks before the PAT expires) — **set 2026-08-07**
      by the operator. ~~2026-10-21~~ — obsolete, that was the classic token's date. ⚠️ The reminder
      lives in *one person's* calendar, which is the same single-point dependency as the token itself;
      it fires two weeks early because re-issuing a fine-grained PAT on an org-owned repo needs a fresh
      org-owner approval, empirically ~1 day.
- [ ] 📌 **(optional, when a citable pilot artifact is needed)** Validation-grade cloud pilot run,
      lightweight form: one clean run from `yAMP-ottilie-test-az` with `-p docker,ottilie_pilot_az`
      (plus the pilot `snpeff_cache` path per the params-box comment), **no probe**, fresh outdir —
      then a **truth-set spot-check** (the known ottilie mutations present in the cohort
      deliverables), *not* a byte comparison against the months-old local pilot (different tool set,
      older commit — reconciling would cost more than it proves; decided 2026-08-13). Until then the
      pilot's cloud viability rests on `18wEWW90THA2Ek` (310/310, diagnostic).
- [ ] 🔁 **Swap to an org-owned GitHub App** when an org owner is available — still the durable answer.
      The fine-grained PAT closed the *blast-radius* half of the problem (`Contents: Read` on one repo,
      not `repo` on everything) but **not** the *person-tied* half: a shared org workspace still depends
      on one person's token, now expiring 2027-08-07 instead of 2026-11-04.
- [x] `tw launch` (plan Phase 6) and compare outputs against the local-head-job baseline — **done
      2026-08-06**: `3C5zYMYY5M32dO` SUCCEEDED, 170/170 tasks, 9/9 cohort deliverables byte-identical.
- [x] Point the `yAMP-ottilie-test` Launchpad entry at `ale-ottilie-nf25104-bigdisk` — done 2026-08-07,
      verified by readback (`computeEnvId 6buIkRXLMZFgDXs5NkyuH`).
- [x] Retire the superseded CEs — **disabled** 2026-08-07 (`ale-ottilie-nf25104`, the original
      single-pool `…-fusion`). Delete them once no run history needs them; disabling already prevents
      accidental use.
- [x] Re-forge the Fusion CE with the §9–§10 fixes — done 2026-08-07,
      `ale-ottilie-nf25104-bigdisk_fusion` (`5acBaUVwry7j0DJmLnwyh0`), AVAILABLE.
- [x] Confirm the same-container rule under a **Platform** head job — done 2026-08-07, run
      `48kJmc9QY6Q3h9`: 0/6 tasks, `Unable to download path` in `.command.log`. See the entry above.
- [x] **Does the pipeline still work under Fusion?** — done 2026-08-07, run `XFwlgZnKvUvpu`: 170/170,
      0 `DiskFull`, all nine cohort deliverables byte-identical to `seqera-runs/2026-08-06-04`. See the
      entry above.
- [x] 🧊 **Fusion cache footprint on the OS disk** — **measured 2026-08-13: ≲3 G at test-set scale.**
      Run `47xZrJ3vg4avR9` executed the recipe as written (fresh cold Fusion CE, same-container,
      probe attached); peak `root:` 63.0 G vs the non-Fusion cold expectation of ~60 G with the same
      image set. Disk sizing conclusions unchanged; the `/mnt` relocation stays parked. Full census
      + caveats in the dated entry.
- [x] **Does Fusion lift the same-container rule?** — **answered 2026-08-13: NO.** Run
      `3AJ4JRNkb7D2dG` repeated the `48kJmc9QY6Q3h9` launch on a fresh Fusion CE and failed
      identically (0/6, same six tasks); `.fusion.log` shows the container-scoped SAS being rejected
      with a 403 against `aletest`. The rule tracks the **credential delegation**, indifferent to the
      data path. See the 2026-08-13 entry.
- [x] **`outdir` in a different container under a Platform head job** — **proven 2026-08-13 for
      `publishDir` writes**: the same run published `pipeline_info/` into `aletest` while `workDir`
      sat in `debugging`. Task-output publishing uses the same head-side mechanism; an end-to-end
      demonstration by a successful cross-container run has not happened (and cannot, given the rule
      above blocks task *reads* — the only way to see it would be inputs+workDir together in one
      container and `outdir` in another).
- [x] 📏 **Measure actual node disk usage** — done 2026-08-07: **peak 65.2 G of 246.9 G (26%)**.
      ⚠️ Measured on **warm** nodes (already ~340 tasks across two runs), so it is a multi-run
      accumulation, and the base-OS vs pipeline-image split is **still unknown**. → split settled by
      the cold-pool baseline below.
- [x] 🧊 **Cold-pool disk baseline — DONE 2026-08-13**, run `18wEWW90THA2Ek` on the full-depth pilot
      (310/310 tasks), executed exactly as the 2026-08-12 spec (fresh CE via
      `13_create_compute_env.sh`, `-p docker,ottilie_pilot_az --config conf/disk_probe.config`,
      fresh outdir + workDir, `-resume` forfeited deliberately). **Cold base 45.4–45.5 G; peak
      60.0 G; pipeline images + writable layers ≈ 15 G; task-scratch disk ≤ 2.7 G.** Images
      dominate — 11× the data did not move `/` usage; **128 GB would suffice**. Numbers + what
      remains open (Fusion's `/mnt` cache):
      [`azure_batch_execution.md` §9 → cold-pool baseline](../../../docs/dev-practices/azure_batch_execution.md),
      and the dated entry above.
- [ ] Repoint `yAMP-ottilie-test` at `…_autoScale_manual_noFusion`, then **delete both fixed-size CEs**
      (`ale-ottilie-nf25104-bigdisk`, `…-bigdisk_fusion`) — deletion disposes their pools and disks.
- [ ] Move Docker's data-root to `/mnt` via a pool start task (needs a `manual` CE) — the better fix
      than a larger OS disk; see the note above. ✅ **Unblocked 2026-08-13**: the cold-pool baseline
      measured the image set at ~15 G and task scratch at ≤ 2.7 G, so the 150 GB ephemeral disk has
      ample headroom. Still open: whether Fusion's cache would compete for `/mnt` (unmeasurable from
      inside a container — see the §9 probe caveat). 📌 **Deliberately parked, not queued** (decided
      2026-08-13): at 4 autoscaling workers the managed-disk cost is cents per run, while a manual CE
      means taking pool lifecycle, the image pin and `azcopy` back from Forge. Interim: attach
      `conf/disk_probe.config` to Fusion dev runs and to the first run after adding a tool — the
      `root:` line shows both Fusion cache pressure and image-set creep. Revisit if the image set
      nears ~100 G, worker counts scale well past 4, or Fusion becomes the default.
- [x] GitHub auth decided and keypair generated (`07_github_deploy_key.sh`) — the pre-existing
      `github_Aletechdev` credential had in fact expired. ⚠️ **That script was deleted 2026-08-07**
      (obsolete route; see the entry above) — the numbered sequence skips 07 by design.
- [x] Deploy key registered on the repo and as a Seqera `ssh` credential; auth + read access verified.
      ⚠️ **The Seqera-side registration was deleted 2026-08-07** (Platform cannot use it for a pipeline
      repo — 2026-08-05). The keypair on the repo is untouched and stays usable for local/CI clones.
- [x] ~~Use the SSH form `git@github.com:Aletechdev/ALE_Yeast.git` in every launch~~ — **dropped
      2026-08-07.** Launches go through the **`yAMP-ottilie-test` Launchpad entry** (`tw launch
      yAMP-ottilie-test -w DTU-Biosustain/RECON-ALE …`), which carries the HTTPS repo URL and resolves
      the `github` credential itself — so no launch names a Git URL at all. The SSH route is closed, not
      pending.
- [ ] ⚠️ **Push before every launch — a standing check, not a one-off.** Seqera clones from GitHub, so
      anything unpushed does not exist for a cloud run: a run against `--revision main` silently uses
      whatever `origin/main` holds, and the failure mode is a *successful* run of stale code rather than
      an error. Confirm `git status` is clean and `main` is level with `origin/main` first. ⚠️ Launching
      a **tag** is not a way around this — a tag pins whatever it pointed at, which is how
      `--revision v1.0.0` came to lack the cloud-portability fixes.
- [ ] 🔬 **Re-test Platform resume — the 2026-08-07 attempt was inconclusive, not negative.** The UI's
      Resume toggle *does* work at the API level: relaunch `5Ped8HWvzzjoDx` recorded `resume: true` with
      the **original** `sessionId` (`128211f9-…`, from the successful `3C5zYMYY5M32dO`) and
      `resumeDir: az://aletest/nf-work-04`. But it re-ran from the start — **`cached=0`** at 64 tasks.
      **Do not conclude resume is broken**: the test was confounded. `wBQPdPBbfyZAH` — a *non*-resume
      relaunch (`resume: false`, new session) — was executing **concurrently into the same work dir**,
      rewriting the very task directories the resuming run needed. Nextflow re-runs a task whose work
      dir is incomplete or altered, which is exactly what it would have found.
      **Retest cleanly, after the local clean run + comparison against the latest pipeline**, and change
      one thing at a time:
      1. Nothing else running against that work dir.
      2. Keep `outdir` **identical** to the run being resumed — it differed here
         (`2026-08-06-04` → `2026-08-07-01`), and whether `outdir` perturbs task hashes is unverified.
      3. Same revision/commit — ✅ **already ruled out as a cause.** The resumed run pinned
         `commitId 86c4672`, identical to the original, even though `main` had moved four commits on.
         Platform honours `resumeCommitId`, so a moving branch does **not** break resume.
      Expect ~170 `cached` and a couple of minutes' wall clock. If `cached=0` persists under those
      conditions, the likely cause is that Platform does not persist Nextflow's **cache DB** — the
      `stage-<sessionId>` directory in the work dir is a *staging* area, and it has not been confirmed
      to contain the hash→result mapping resume actually needs.
- [x] Rename the app registration to match its new purpose — **done 2026-08-13**:
      `cfb_ale_mutations_pipeline` → `sp-bright-recon-ale-mutations-pipeline-seqera-deploy` (see the
      📛 note in *Context* above). Verified: the rename propagated to the SP object, exactly one SP
      matches the new name, and `SP_DISPLAY_NAME` in `00_vars.sh` was updated in the same commit.
      The operator is an app **owner** (with pasdom@dtu.dk, phaneuf@dtu.dk), so no admin was needed.
      Seqera credential name deliberately kept — binds by clientId.
- [x] Rotate the exposed secret on `sp-bright-recon-ale-mutations-pipeline` — **done 2026-08-14, all
      five steps.** New secret `rotated-2026-08` (key id `0026e21c…`) minted by the operator with the
      parameterized `03_create_secret.sh`, swapped into the ALE-mutations service and tested; the
      exposed 2026-06-03 secret (key id `8af5a144…`) then **deleted** — verified: the app now holds
      exactly one credential, expiring **2027-08-14**, which
      [`bin/check_credential_expiry.sh`](../../../bin/check_credential_expiry.sh) now tracks with the
      standard 60-day lead (the every-session nag is retired). Original scoping kept below for the
      record:
- [x] ~~(scoping)~~ Rotate the exposed secret on `sp-bright-recon-ale-mutations-pipeline` (the *other* SP — the
      sibling serving the migrated ALE-mutations service, `Contributor` on Batch `ale` + `Reader` on
      `ensembleamp`). Its secret sat in plaintext in `tmp/azure/azure_sp/.azure_sp.env` from
      ~2026-06-03 until the file was deleted 2026-08-13. **Scoping done 2026-08-13**: never committed
      (verified — no commit in history touched `tmp/` or any `azure_sp` path), never left this VM, so
      this is hygiene, not incident response. The SP holds exactly **one** secret (created 2026-06-03,
      **expires 2026-11-02**), i.e. the exposed value is the live one. **Decision: live-swap; operator
      will run it later.** Recipe — typed in the operator's own terminal, never through an agent/`tee`
      (the secret prints to stdout):
      1. `APP=$(az ad sp list --display-name sp-bright-recon-ale-mutations-pipeline --query "[0].appId" -o tsv)`
      2. `az ad app credential list --id "$APP" -o table` — note the old `keyId`.
      3. `az ad app credential reset --id "$APP" --append --years 1 --query password -o tsv` —
         `--append` keeps the old secret working, so the service keeps running.
         📌 Steps 1–3 also exist as a guarded script (TTY check, confirmation, keeps existing
         creds): `SP_DISPLAY_NAME=sp-bright-recon-ale-mutations-pipeline SECRET_LABEL=rotated-2026-08
         ./03_create_secret.sh` — still typed in your own terminal, never through an agent.
      4. Swap the new value into the ALE-mutations service's config (off this machine) and verify it.
      5. `az ad app credential delete --id "$APP" --key-id <old keyId>` — this step is the actual
         revocation; until it runs, the rotation is not complete.
      ⚠️ The app is co-owned with pasdom@dtu.dk and phaneuf@dtu.dk — coordinate before step 5.
      ⏰ Backstop: the exposed secret self-expires **2026-11-02** even if rotation slips.
- [ ] 🚨 **Make something reap a hung head job.** `jobMaxWallClockTime: "7d"` in
      `ce_import_template.json` does **not** apply — Azure reported `TimeSpan.MaxValue` on
      `nf-workflow-1XuapND2cN2oCO` (2026-08-13), so a head job that hangs after completing holds its
      node until a human notices; the head pool cannot scale to 0 while a task is `running`. Options:
      find where the setting is actually honoured (job vs task constraints), set
      `constraints.maxWallClockTime` on the Batch job directly, or add a cheap post-run check. Until
      then: **after any run that ends in a non-terminal state, check
      `az batch pool list --query "[?contains(id,'<ce-id>')].[id,currentDedicatedNodes]" -o tsv`.**
- [x] Delete the six DISABLED compute environments — **done 2026-08-13**, including both **fixed-size**
      ones (`ale-ottilie-nf25104-bigdisk`, `…-bigdisk_fusion`) from the 2026-08-07 cost incident. All
      were at 0 nodes first; deletion disposed their pools and disks.
      **`yAMP-ce-nofusion-256` (`4xdBRYm1K1rbql3g5CgnSg`) is now the only compute environment.**
      Checked first that no Launchpad entry depended on them — `ALE-Yeast-aledev4test` and
      `ALE_Sarek_dev` already pointed at previously-deleted CEs.
      📌 The two Azure pools with no CE behind them were **also deleted** (2026-08-13), for a clean
      starting point: `nf-pool-21b27…-Standard_E4ds_v4` — a Nextflow **auto-pool** from *local*
      head-job runs, which no CE owns and CE deletion therefore never touches — and
      `tower-pool-4bPUf5SLRHx9gllkj29reo`, orphan of an earlier deletion. Both were at 0 nodes and free.
      ⚠️ This gives up `-resume` on the affected local runs (§2: a resumed run asks for its pool by id
      and fails with *"not in active state"*). Accepted deliberately — those runs are short enough to
      redo. Note the auto-pool is **not** permanently lost: its id is a hash of the pool spec, so the
      next local Batch run with the same `conf/azure_batch.config` recreates the identical id.
      **The Batch account now holds only `yAMP-ce-nofusion-256`'s two pools.**
      ⚠️ `yAMP-ce-nofusion-256` is **warm** after run `1XuapND2cN2oCO`, so the cold-pool disk baseline
      still needs a freshly forged CE — not this one. ✅ Done exactly that way later the same day:
      `yAMP-ce-coldprobe-256`, forged for run `18wEWW90THA2Ek` and deleted after harvest (see the
      cold-pool baseline entry above), leaving the account again with only the keeper's two pools.
