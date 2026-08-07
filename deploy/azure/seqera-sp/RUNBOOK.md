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
| SP `cfb_ale_mutations_pipeline` | Batch account `aledev4test` | `Azure Batch Data Contributor` |
| same | Storage account `aledata` | `Storage Blob Data Contributor` |

Per-resource scope only — never the resource group, never the subscription.

## Context — why this SP, and where it came from

`cfb_ale_mutations_pipeline` is an **existing app registration that was deliberately freed up and is
now being repurposed** for the Nextflow / Seqera Platform cloud testing. It is not a fresh
registration and not an accidental reuse.

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

The cloud-run plan hardcodes workspace `zhlia-wsp` = `148627246605113` in its Phase 3/4/6 commands.
Work is actually happening in **`DTU-Biosustain/RECON-ALE` = `79597273081110`** — a different, org-level
workspace. Every `-w` in the plan must be changed. Consequences:

- Assets the plan lists as "existing" (the `aledev4test` shared-key credential `182ger…`, CE
  `4zcbSAL…`) live in `zhlia-wsp` and are **not** available here.
- `RECON-ALE` has its own six `azure-batch` compute environments (`aledev4test`, `aledev4test_copy`,
  `aledev4test_singlepool`, `aledev4test_e4ds_v4`, `ALE_E4ds_v4`, `ALE_E4ds_v4_16workers`), all
  predating this work and all still on the **shared-key** credential `rgALE_batch_aledev4test`
  (provider `azure`). The plan's "create a NEW CE, do not mutate an existing one" rule therefore still
  holds, and now for a second reason: these are shared with other people's work in an org workspace.
- A GitHub credential `github_Aletechdev` exists here, refreshed 2026-07-30 — **newer than the expired
  token the plan flagged in Phase 2**. Worth testing before generating a deploy key; Phase 2 may
  already be satisfied.

| 2026-07-31 08:43Z | `07_github_deploy_key.sh` | zhlia@dtu.dk | ✅ ed25519 deploy keypair generated at `~/.ssh/seqera_ale_yeast_deploy` (0600). |

### 2026-07-31 — GitHub auth: deploy key, not a PAT

The previous `github_Aletechdev` credential expired. Chosen route: an **SSH deploy key** rather than
either PAT option.

Facts that decided it:

- `Aletechdev` is a GitHub **Organization** (ALEtech), so org-owned PATs were genuinely available.
- The Seqera workspace is now **org-level and shared** (`DTU-Biosustain/RECON-ALE`), which is what
  rules out a personal PAT: the team's launches would break on one person's token expiry, and runs
  would be attributed to that person.
- `tw credentials add ssh -k <keyfile>` exists, so the route is supported, not theoretical.
- `tw credentials add github` accepts only username + token — a GitHub-*provider* credential is
  necessarily a PAT.

A deploy key is attached to the **repository**, so it is scoped to one repo, read-only, has no expiry
to lapse silently, needs no org-approval flow, and survives personnel changes — nobody's account grants
the access. Cost: the launch URL must be the SSH form (`git@github.com:Aletechdev/ALE_Yeast.git`);
a deploy key cannot authenticate an HTTPS clone.

Generated without a passphrase deliberately: Seqera stores the private key and must use it unattended,
so a passphrase would have to be stored beside it — ceremony, not security.

**Verified end-to-end 2026-07-31:**

- `ssh -T -i ~/.ssh/seqera_ale_yeast_deploy git@github.com` → `Hi Aletechdev/ALE_Yeast!` — it
  authenticates as the **repository**, not as a user, which is the confirmation that a deploy key (not
  a personal key) was used. Exit code 1 is normal for this message.
- `git ls-remote` over that key lists `refs/heads/main` and `refs/tags/v1.0.0`, so read access and the
  launch revision are both reachable.
- Registered as Seqera credential **`github_ALE_Yeast_deploykey`** (provider `ssh`) in
  `DTU-Biosustain/RECON-ALE`.

**Plan Phase 2 is complete.** The expired `github_Aletechdev` credential was left in place rather than
deleted — the six pre-existing compute environments in this shared org workspace may reference it, and
removing it is not ours to decide.

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

### 2026-08-05 15:44Z — compute environments forged (plan Phase 4)

Two **new** CEs created in `DTU-Biosustain/RECON-ALE`, both on the Entra credential
`azure_SP_cfb_ale_mutations_pipeline`. None of the six pre-existing shared CEs was touched.

| Name | Id | Fusion / Wave | Status |
|---|---|---|---|
| `ale-ottilie-nf25104` | `5CR3jOkRBI58YXWtDIAAtu` | off / off | AVAILABLE |
| `ale-ottilie-nf25104-fusion` | `5ncp4rI8GezvoPBnpvnTEk` | on / on | AVAILABLE |

Identical otherwise: `workDir az://aletest/nf-work`, `northeurope`, forge pool
`Standard_E4ds_v4` ×4 autoscaling, `disposeOnDeletion: true`.

```bash
tw compute-envs add azure-batch forge -n ale-ottilie-nf25104 \
    -w DTU-Biosustain/RECON-ALE -c azure_SP_cfb_ale_mutations_pipeline \
    -l northeurope --work-dir az://aletest/nf-work \
    -e NXF_VER=25.10.4 --vm-type Standard_E4ds_v4 --vm-count 4
# ...and the same again with `-n ale-ottilie-nf25104-fusion --fusion-v2 --wave`
```

**Results worth keeping:**

- ✅ **`-e NXF_VER=25.10.4` stored exactly as intended** — readback shows
  `{"name":"NXF_VER","value":"25.10.4","head":true,"compute":false}`. Head-job-only is what the pin
  needs. That it *stored* is not proof it *takes*: the head job must invoke `nextflow` through the
  self-fetching launcher. Still verify the run log reports 25.10.x, not 26.x.
- ✅ **Batch Forge works with an Entra service principal.** `Azure Batch Data Contributor` on the
  account was sufficient — no `AuthorizationFailed`, no extra grant, no subscription-level role.
- ⚠️ **Fusion + Entra forged with `managedIdentity*` all `null`.** This contradicts the research lead
  that Entra + Forge + Fusion *requires* a user-assigned managed identity — at least at forge time.
  Whether Fusion **mounts** at task runtime is still untested.
- ⚠️ **`tw` 0.26 `--wait AVAILABLE` fails with `Error reading entity from input stream` /
  `Connection error`.** The CE is created correctly regardless — this is the known 0.26-vs-API-1.193
  response-parsing bug, on the *poll*, not the request. **Do not re-run the command on this error**;
  you would create a duplicate CE. Check status via the REST API instead:
  ```bash
  curl -s -H "Authorization: Bearer $TOWER_ACCESS_TOKEN" \
    "https://api.cloud.seqera.io/compute-envs?workspaceId=<ws-id>" | python -m json.tool
  ```
- ✅ **The forged pools carry a *verified* image — checked, not assumed.** Forge creates the pool at
  **CE-creation time**: two new pools appear with `creationTime` equal to the CE timestamps
  (`15:43:57`, `15:45:26`), both `microsoft-dsvm / ubuntu-hpc / 2404`, agent `batch.node.ubuntu 24.04`
  — the same verified combination `conf/azure_batch.config` pins for Nextflow's autopool. Platform's
  own default is current, so Phase 3.5 finding #4 does **not** bite here. All 15 pools on the account
  are on `2404`. Re-check after any region change:
  ```bash
  az batch account login -g rg-aledb -n aledev4test
  az batch pool list --query "sort_by([].{id:id,created:creationTime,sku:virtualMachineConfiguration.imageReference.sku}, &created)" -o table
  ```

### 2026-08-05 — `NXF_VER` on the head job is correct; do NOT set it to `both:`

Asked whether the pin should also target compute tasks. **No — it would be a no-op.** Evidence from an
actual task wrapper (`work/*/.command.run`): the payload is invoked as
`/usr/bin/env bash … .command.sh` inside `docker run`, and the only NXF_* variables forwarded into the
container are `NXF_TASK_WORKDIR` and `NXF_DEBUG`, each enumerated explicitly with `-e`. **No `nextflow`
binary ever executes on a Batch node**, so nothing on a compute node reads `NXF_VER`. The variable
selects which engine the *launcher* self-fetches, and the launcher runs only in the head job.

### 2026-08-05 — `tw` upgraded 0.26.0 → 0.38.0

The plan called this "worth doing eventually; does not help here". **That is now superseded** — 0.26's
response-parsing bug broke `compute-envs add --wait` and `compute-envs view`, which are the readback
path for this work. Client-side only: it cannot change what runs in the cloud.

Installed to `/usr/local/bin/tw` (user-owned, no sudo). SHA-256 verified against the release
`checksums_sha256.txt`. **Roll back** by restoring the saved 0.26 binary if anything regresses.

Re-verified on 0.38 after upgrading:

- ✅ `compute-envs view` now parses — the exact call 0.26 could not make.
- ✅ **`tw launch` still has no single-param option** (`--params-file`, `--config`, `--profile` only),
  so the "`outdir` must live in the params file" conclusion holds unchanged.
- 🆕 **`--pre-run` and `--launch-container` are available per launch.** The `NXF_VER` fallback no
  longer requires rebuilding the CE — a failed pin can be patched on the launch command itself.
- 🆕 `--wait=SUBMITTED|RUNNING|SUCCEEDED|FAILED|…` on launch, and `--stub-run`.
- ⚠️ `--version-id` / `--version-name` render with a required marker (`*`) in the help output; they are
  part of a mutually-exclusive group, not genuinely required. Expect this if launch complains.

### 2026-08-05 — 🚨 the SSH deploy key CANNOT be used to clone the pipeline repo

**Seqera Platform does not support SSH-key authentication for pipeline repositories.** This
invalidates the Phase 2 decision recorded above ("deploy key, not a PAT"). The deploy key is genuinely
valid — `ssh -T` and `git ls-remote` both pass — but it authenticates *your machine* to GitHub, and
Platform never uses it.

Found by trying to launch. Bisected with `tw pipelines add`, which validates the repo at add time and
so is a cheap probe (no run is started):

| Repository URL | Result |
|---|---|
| `git@github.com:Aletechdev/ALE_Yeast.git` (scp-style) | `Unexpected error … Error ID: …` — an internal 500; Platform cannot even parse this form |
| `ssh://git@github.com/Aletechdev/ALE_Yeast.git` | parses, then `Unknown pipeline repository or expired Git credentials` |
| `https://github.com/Aletechdev/ALE_Yeast` | same `Unknown pipeline repository or expired Git credentials` — Platform reached for it and found no usable credential |

Three independent confirmations that this is by design, not a misconfiguration:

1. **Docs** — the Git integration page lists the supported providers as Azure DevOps, GitHub (PAT or
   **GitHub App**), GitLab, Gitea, Bitbucket and AWS CodeCommit. SSH keys are absent, and every
   documented repository base URL is `https://`.
2. **`ssh` credentials are for something else entirely** — "the key pair is used to authenticate a
   connection with your SSH-enabled environment", i.e. **HPC compute environments**, not Git.
3. **Structural** — `tw credentials add github` has `--base-url` (how Platform matches a credential to
   a repository host); `tw credentials add ssh` has **no such option**, so an `ssh` credential cannot
   be bound to `github.com` even in principle. Confirmed by readback: `baseUrl: null`.

**Also learned:** `tw launch <ssh-url>` fails with the misleading `Pipeline 'git@github.com:…' not
found on this workspace`. `tw launch` takes *a workspace pipeline name or a URL*, and since it does not
recognise the scp-style string as a URL it falls back to a name lookup. The message describes the
fallback, not the real problem.

The deploy key itself is **not** wasted — it stays useful for local clones and CI checkouts. It is only
useless *to Platform*. Consider revoking it if no such use materialises.

Demonstrated directly, same key (`SHA256:1VRUK9eZMJAPilP6UZO/1fOqZFVqWkzBnlRTUF+2kfs`,
`~/.ssh/seqera_ale_yeast_deploy`) against the same repo:

```
$ GIT_SSH_COMMAND="ssh -i ~/.ssh/seqera_ale_yeast_deploy -o IdentitiesOnly=yes" \
    git ls-remote git@github.com:Aletechdev/ALE_Yeast.git
1c20c4b…  refs/heads/main                      # ← reads fine

$ git ls-remote https://github.com/Aletechdev/ALE_Yeast
remote: Repository not found.                  # ← same key, HTTPS, denied
```

**Two independent constraints whose intersection is empty:** a GitHub deploy key is an SSH credential
*by definition* (GitHub accepts it only on SSH connections), and Platform's Git integration is
HTTPS-only. No URL form bridges that. The key reads the **repository** perfectly; what it cannot read
is the **`https://` URL**, which is the only form Platform accepts.

#### Registering to the Launchpad is not a way around this

**The Launchpad *is* `tw pipelines`** — same object, same API, and `tw pipelines add` is exactly the
call that fails. Platform validates the repository at registration time, so registration is gated by
the same missing credential as a launch; "register now, fix launching later" is not an available
sequencing. Nor would registering first help: Platform does not cache pipeline code, so the head job
clones at run time and needs a *live* credential either way. The existing `ALE-Yeast-aledev4test`
entry (`181498121471668`) exists only because it was registered on **2026-04-20**, when a working
GitHub credential was available.

#### Where the credentials actually are — the gap is workspace scope

| Scope | GitHub credential |
|---|---|
| `DTU-Biosustain/RECON-ALE` (the workspace in use) | **none** — only `azure_entra`, `ssh`, `azure` |
| user / personal workspace | none |
| `zhlia-org-ALE-beta/zhlia-wsp` | `seqera-platform-ale-16april2026` (provider `github`, last activity 2026-04-20, believed expired) |

**Seqera credentials are workspace-scoped**, so the `zhlia-wsp` credential cannot serve a pipeline in
`RECON-ALE`. `github_Aletechdev` — recorded in the plan as "expired, left in place" — is **not present
in `RECON-ALE` at all**; that note described the other workspace. ⚠️ Token values **cannot be recovered
from Platform** (the API returns `null` for every secret field), so an existing credential cannot be
copied across workspaces — only re-entered from the original token.

**The repository is genuinely private**, so a credential is unavoidable: an unauthenticated
`git ls-remote https://github.com/Aletechdev/ALE_Yeast` returns `Repository not found`.

### 2026-08-05 — GitHub App ruled out (no org ownership) → classic PAT

**Decision: classic PAT**, because the better options are blocked by org permissions, not by merit.

| Option | Verdict |
|---|---|
| **GitHub App**, org-owned, scoped to `ALE_Yeast` | **The right answer, and unavailable.** It preserves every property the deploy key was chosen for — org-owned not person-owned, scopable to one repo, `Contents: Read` only, installation tokens auto-rotate so there is no expiry to miss. Platform supports it (manifest flow, or App ID + Installation ID + App slug + private key + client secret + webhook secret). **Blocked: creating an org-owned App and installing it requires org-owner rights on `Aletechdev`, which the operator does not have.** A *personally*-owned App installed on the org would work technically but reintroduces the person-tied dependency, i.e. it buys nothing over a PAT for much more effort. |
| **Fine-grained PAT** | Gives exactly `Contents: Read` on `ALE_Yeast` alone — real least privilege. **Also needs an org owner**, but only to *approve a request*, not to build anything. Far smaller ask than the App; worth requesting even while unblocked by the classic token. This org has refused/queued these before ("approval pending"). |
| **Machine-user + classic PAT** | Bot account added to `ALE_Yeast` as a read-only collaborator; use *its* token. Effective privilege is repo-scoped **and** not person-tied, and it needs only **repo-admin**, not org-owner. ⚠️ On paid org plans an outside collaborator on a private repo consumes a seat. |
| **Classic PAT (chosen)** | Only option needing no one else's permission. ⚠️ **Cannot be fine-grained** — `repo` is all-or-nothing across every repo the user can reach, and there is no read-only scope for private repos (`public_repo` covers public only). Strictly broader than the deploy key it replaces; that is the price of the fallback, not a tuning oversight. |

Creating it: Settings → Developer settings → Personal access tokens → **Tokens (classic)** →
`repo` scope → **set an explicit expiry** (never "no expiration"). If `Aletechdev` enforces SAML SSO,
**Configure SSO → Authorize** on the token afterwards or it fails silently against org repos.

Registering it — run it yourself so the token never enters a transcript or shell history:

```bash
read -rsp 'GitHub token: ' GH_TOKEN && export GH_TOKEN
tw credentials add github -n github_ALE_Yeast_pat -w DTU-Biosustain/RECON-ALE \
    -u <github-username> -p "$GH_TOKEN" --base-url https://github.com/Aletechdev
```

Then the Launchpad entry and the launch are one command each:

```bash
tw pipelines add https://github.com/Aletechdev/ALE_Yeast \
    -n ale-ottilie-contract-test -w DTU-Biosustain/RECON-ALE \
    -c ale-ottilie-nf25104 --revision main -p docker \
    --params-file conf/params_ottilie_blob.yml
```

> ⏰ **Record the token's owner and expiry in the table below when it is created.** This is a *shared
> org workspace* on *one person's* token — a teammate hitting an opaque launch failure in a year needs
> to know who to chase. The same reasoning already applies to the Azure client secret.
>
> 🔁 **Swap to a GitHub App when an org owner is available.** Nothing depends on which credential
> authenticated the clone, so it is a credential change and nothing else.

### 2026-08-06 — ✅ classic PAT registered; repo clones; Launchpad entry live

**The blocker above is cleared.** A personal **classic** PAT was registered in `RECON-ALE` as
`personal_token_classic_ALE_yeast` (`Z3yo4zFgy1xfdW0Ts11kI`, provider `github`), and Platform
successfully cloned the private repo over HTTPS — proven by `tw pipelines add` succeeding, since it
validates the repository at registration time.

A **fine-grained** PAT (`Contents: Read` on `ALE_Yeast`, resource owner `Aletechdev`) was submitted in
parallel and is **pending org-owner approval**. → ✅ **Approved the next day and swapped in; the classic
PAT is retired — see the `2026-08-07` entry below.** ⚠️ Note for anyone repeating this: the org *does*
appear in the fine-grained token's **Resource owner** dropdown — if the repo seems missing, the cause
is Resource owner still set to the personal account, not the org disallowing it.

**Launchpad pipeline registered:**

| Field | Value |
|---|---|
| Name / id | `yAMP-ottilie-test` / `227651105760023` |
| Repository | `https://github.com/Aletechdev/ALE_Yeast` (HTTPS — the only form Platform accepts) |
| Revision / profile / labels | `main` / `docker` / `dev` |
| Compute env | `ale-ottilie-nf25104` |
| workDir / outdir | `az://aletest/nf-work` (from the CE) / `az://aletest/seqera-runs/2026-08-06-01` |

⚠️ **`tw pipelines update` is broken** — HTTP 500 (`Unexpected error while processing request`) with
`-n` or `-i`, full or partial options, while `add` with the *same* arguments succeeds. Work around it
by deleting and re-adding (the pipeline id changes), or edit in the web UI.

**One pipeline entry, not one per compute environment.** The CE is a single field at registration but
is **overridable per launch** (`tw launch -c …`, or the dropdown on the UI launch form). So the Fusion
comparison runs from this same entry against `ale-ottilie-nf25104-fusion` — which is also the
methodologically better choice, since launching one record against two CEs guarantees nothing else
differs between the two runs. ⚠️ Give the second run its own `outdir`.

**Params stay dataset-specific and ready-to-run.** `conf/params_ottilie_blob.yml` is deliberately a
filled-in, launch-without-editing file rather than a template with placeholders — splitting it into a
generic template is explicitly deferred. Note that Platform stores params as a single `paramsText`
blob, so launch-time params **replace** the saved set rather than merging key-by-key; saved params are
an editable template, never inherited defaults.

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

CE `ale-ottilie-nf25104-bigdisk` = `6buIkRXLMZFgDXs5NkyuH`. Verified at the Azure level — Forge built
two pools with `diskSizeGb` **64** (head) and **256** (worker); the earlier CEs show `null` (Azure
default), so the flag genuinely applied.

```bash
tw compute-envs add azure-batch forge -n ale-ottilie-nf25104-bigdisk \
    -w DTU-Biosustain/RECON-ALE -c azure_SP_cfb_ale_mutations_pipeline \
    -l northeurope --work-dir az://aletest/nf-work -e NXF_VER=25.10.4 \
    --dual-pool \
    --head-vm-type Standard_D2s_v3    --head-vm-count 1   --head-boot-disk-size 64 \
    --worker-vm-type Standard_E4ds_v4 --worker-vm-count 4 --worker-boot-disk-size 256
```

⚠️ **Dual pool requires explicit per-pool VM counts.** `--vm-count` is single-pool only; omitting
`--head-vm-count`/`--worker-vm-count` fails with `Missing VM count parameter for head pool`, despite the
help text saying the head count defaults to 1.

⚠️ **Dual pool starts slower** — measured **4 min** (single-pool) vs **~17 min** for the head pool to
provision a node. The head job waits on its *own* VM allocation instead of using whichever shared node
came up first; worker nodes sit `idle` meanwhile. Cold-start only. `--head-no-auto-scale` would keep a
head node warm at the cost of a `D2s_v3` running continuously.

> **Better long-term fix (not yet applied):** relocate Docker's data-root to the ephemeral disk via a
> Batch **pool start task** — `/mnt` on `Standard_E4ds_v4` is 150 GB of local NVMe, free with the VM and
> faster than a managed OS disk:
> ```
> systemctl stop docker && mkdir -p /mnt/docker && rsync -aP /var/lib/docker/ /mnt/docker &&
> sed -i "s|^ExecStart=.*|ExecStart=/usr/bin/dockerd --data-root=/mnt/docker|" /lib/systemd/system/docker.service &&
> systemctl daemon-reexec && systemctl start docker
> ```
> ⚠️ **`preRunScript` cannot do this** — it runs in the nf-launch script inside the *head job*, not as a
> pool start task on every worker node. A start task requires a **pre-created pool** plus
> `tw compute-envs add azure-batch manual --compute-pool-name/--worker-pool`, which means taking over
> the autoscale formula, the verified `ubuntu-hpc/2404` image pin, and node lifecycle from Forge — and
> the head pool must ship `azcopy`.

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

The fine-grained PAT submitted 2026-08-06 was **approved**, and the credential was swapped the same
morning. `personal_token_classic_ALE_yeast` was deleted from `RECON-ALE` and replaced by
**`github_ALE_Yeast_finegrained`** (`2NhER3hJHchursPHekAV1P`, provider `github`).

**Correction to the 2026-08-05 option table:** it warned that *"this org has refused/queued these
before (approval pending)"*, which framed the fine-grained route as slow enough to need a stopgap. The
approval in fact took **about one day**. The classic PAT was still the right call — it unblocked Phase 6
immediately and the approval time was unknowable in advance — but the next person facing this should
**submit the fine-grained request first and wait a day** before reaching for a classic token.

**Verified in use, without launching a run** — the `yAMP-ottilie-test` Launchpad form renders its
parameters, i.e. Platform resolved `nextflow_schema.json` / `nextflow.config` for the private repo.
`tw credentials list` shows the credential carrying activity:

| ID | Provider | Name | Last activity |
|---|---|---|---|
| `2NhER3hJHchursPHekAV1P` | `github` | `github_ALE_Yeast_finegrained` | 2026-08-07 08:01:57 GMT |
| `2nZYlDlUj2hutarvPunhRb` | `ssh` | `github_ALE_Yeast_deploykey` | **never** |

⚠️ **`Last activity` is worth understanding before leaning on it**, because the obvious objection — that
it is just the creation timestamp — has to be ruled out. The API (`GET /credentials?workspaceId=…`)
exposes three separate fields, and for this credential they are all different: `dateCreated 07:49:50`,
`lastUpdated 08:00:56`, **`lastUsed 08:01:57`**. `lastUsed` is therefore a genuine usage stamp, 12
minutes after creation. The two Azure credentials confirm the semantics from the other direction —
created in March and July, both showing `lastUsed` moving *today*, which is Platform's periodic
compute-environment health check.

It is also the **only** `github` credential in the workspace, so there is no ambiguity about which one
Platform matched to `github.com`.

✅ **Proven by a repeat, not by inference.** The first `lastUsed` (08:01:57) landed 61 s after
`lastUpdated`, which left one loophole — a save-time validation of the just-edited credential, rather
than a repo fetch. Closed by re-opening the Launchpad form at 12:29 and re-reading the API:
`lastUsed` advanced to **12:29:12**, 30 s before the query, while `dateCreated`/`lastUpdated` stayed
put. So **rendering the launch form consults this credential live** — Platform is fetching repo content
over HTTPS with the fine-grained PAT, and is not replaying the pipeline record stored at
`tw pipelines add` time (2026-08-06, under the classic PAT).

**Reusable technique:** to test *any* Seqera Git credential without spending a run, note `lastUsed`,
open the pipeline's launch form, and re-read it. A credential that cannot authenticate leaves it
unchanged — which is exactly the `never` in the `ssh` row above.

⚠️ The `ssh` deploy-key credential reads **`never`**, which is the empirical confirmation of the
2026-08-05 finding: Platform structurally cannot use an SSH credential for a pipeline repository, so it
was never consulted and never would be. **Deleted the same day** — readback then shows three
credentials (`github`, `azure_entra`, `azure`), all with recent activity. The keypair itself is
untouched and stays useful for local and CI clones.

🗑️ **`07_github_deploy_key.sh` was deleted with it**, leaving a deliberate gap in the numbered
sequence. Its STEP 2 registered the very `ssh` credential removed above and its STEP 3 instructed
launching from `git@github.com:…` — both dead routes, so the script's remaining value (an `ssh-keygen`
line) did not justify a file that hands out obsolete instructions. It is in git history if the deploy
key ever needs regenerating; the key already on the repo is unaffected.

**There is deliberately no replacement script for the GitHub credential.** The token is minted by the
operator in the GitHub UI (org approval is a UI flow with no CLI equivalent) and registered with the
one-liner under *GitHub PAT* below, typed by hand so the secret never enters a transcript or shell
history. Scripting it would only move the token into a file.

**The classic token was also revoked at GitHub on 2026-08-07**, not merely unregistered from Seqera.
Those are two separate actions and only the second one actually retires the `repo` read+write reach —
worth stating explicitly, because a workspace readback showing the credential gone looks identical in
both cases.

**What this fixes, and what it does not.** Blast radius: closed — `Contents: Read` on one repository
replaces `repo` read+write across every repository the operator can reach. Person-tied dependency and
finite expiry: **unchanged**. A shared org workspace still runs on one person's token; it now lapses in
2027 instead of 2026. The org-owned GitHub App remains the durable answer and its open item stays open.

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

### 2026-08-07 — Fusion CE re-forged with the dual-pool + disk fixes

`ale-ottilie-nf25104-bigdisk_fusion` = `5acBaUVwry7j0DJmLnwyh0` — **AVAILABLE**. Fusion v2 + Wave **on**,
dual-pool (head `Standard_D2s_v3`/64 GB, worker `Standard_E4ds_v4`/256 GB), `NXF_VER=25.10.4` on the head
job, Entra credential, `workDir az://aletest/nf-work`.

The original `ale-ottilie-nf25104-fusion` was single-pool with the default boot disk, so a run against it
would have hit `DiskFull` (§9) and told us nothing about Fusion. Carrying the §9–§10 fixes over means a
Fusion run now isolates **Fusion** as the single variable. The superseded CEs were disabled.

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

- Azure's **default** Batch OS disk is ~30 GB, so 57–65 GB overruns it **2×**. That is the whole
  `DiskFull` story, and it confirms the concurrency hypothesis was wrong — a solo run exceeds the
  default on its own.
- 256 GB is ~3.8× the peak; 128 GB would suffice. The margin costs ~$0.05/hr across four nodes.
- ✅ **The `/mnt` relocation fix is viable**: 65 GB fits inside the 150 GB ephemeral NVMe — the
  assumption that fix rested on.

⚠️ **Correction to the config's original comment:** `beforeScript` runs **inside the container**, not on
the node (`hostname` = container id, `/` = `overlay`). The reading is still valid — overlay2's `df`
reports the backing filesystem, and 246.9 G matches the OS disk — but the mechanism is not as stated.
⚠️ **Under Fusion the work-dir `df` is useless**: it reports a synthetic `fusion 8.0P … 50% /fusion`.
Only the `root:` line is usable there.

### 2026-08-07 — 🚨 COST INCIDENT: `tw --dual-pool` creates FIXED-SIZE pools (~$66/day)

**Ten nodes ran idle for hours.** Both dual-pool CEs forged with `tw` had
`headPool.autoScale: null` / `workerPool.autoScale: null`, which Azure built as
`enableAutoScale: False` — fixed at 1 head + 4 workers, billing regardless of load:
**8× `E4ds_v4` + 2× `D2s_v3` ≈ $2.75/hr compute, plus ~$324/month of managed disks.**

Noticed only because a *cold pool* was wanted for a disk baseline and the pools would not drain.

**Reproduced deliberately** with a throwaway CE (`ale-ottilie-autoscale-test`, since deleted): same
flags, same result. Repeatable CLI behaviour, not a one-off.

**Root cause.** `tw compute-envs add azure-batch forge` exposes only flags to *disable* autoscaling —
`--no-auto-scale`, `--head-no-auto-scale`, `--worker-no-auto-scale` — which reads as "enabled by
default", and *is* true for **single-pool** (`autoScale: true`, pools sit at 0). For **dual-pool** it is
not, and nothing warns you: `tw` reports success.

✅ **The web UI CAN set it.** `ale-ottilie-nf25104-bigdisk_autoScale_manual` (`6zsRCxeGmUoiae4OVOGSKO`),
created through the UI, reads back `headPool.autoScale: true` / `workerPool.autoScale: true`, and Azure
confirms `enableAutoScale: True` with the pools draining to 0. So this is a **CLI gap, not a Platform
limitation** — **create dual-pool CEs in the UI.**

**Remediation performed:** all four pinned pools resized to 0 (`az batch pool resize
--target-dedicated-nodes 0`), the test CE deleted (deletion disposes pools *and* disks). Two correct
CEs now exist — `…_autoScale_manual` (Fusion) and `…_autoScale_manual_noFusion`.

⚠️ **Still to do:** the `yAMP-ottilie-test` Launchpad entry points at `ale-ottilie-nf25104-bigdisk`,
one of the **fixed-size** CEs. Repoint it to the `_noFusion` keeper before anyone launches, then delete
both fixed-size CEs.

**Guard added:** [`12_verify_compute_env.sh`](12_verify_compute_env.sh) asserts `autoScale` on both
pools (plus workDir, `NXF_VER`, disk sizes) and exits non-zero with the resize/delete steps. Verified
against both a good and a bad CE. ⚠️ **CEs are immutable** — a wrong setting can only be deleted and
recreated, so verify *before* launching, not after the invoice.

⚠️ **A new pool shows 1 node for its first ~5 minutes and that is normal** — the Forge autoscale formula
pins the first interval (`$TargetDedicatedNodes = lifespan < interval ? 1 : targetPoolSize`). `1 + 1`
right after creation proves nothing; **`0 + 0` fifteen minutes later** is the real check. Confirmed
unrelated to Wave/Fusion — a duplicate CE with both disabled behaves identically.
⚠️ **`--worker-vm-count` is a CEILING under autoscale**, not an allocation: the autoscaling CE started
at 1 + 1 and scales toward 4, while the fixed one went straight to 1 + 4 and stayed.

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

- [x] Grant the two roles (`02_grant_roles.sh`) — done 2026-07-31, verified.
- [x] Create a client secret (`03_create_secret.sh`) — done 2026-07-31.
- [x] Verify both data planes (`05_verify_sp_access.sh`) — done 2026-07-31, all checks passed.
- [x] Register the Entra credential in Seqera via the web UI — done 2026-07-31, schema captured.
- [x] Create a new compute environment bound to the `azure_SP_cfb_ale_mutations_pipeline` credential,
      with `NXF_VER=25.10.4` pinned via the head-job environment (plan Phase 4) — done 2026-08-05,
      two CEs (non-Fusion + Fusion), both AVAILABLE. The six existing CEs were not repointed.
- [x] Add `outdir` to `conf/params_ottilie_blob.yml` — done 2026-08-05, date-stamped, preview-verified.
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
- [ ] **Fusion run — two questions, one launch each.** Both against
      `ale-ottilie-nf25104-bigdisk_fusion`, which now carries dual-pool + 256 GB workers so `DiskFull`
      cannot confound the result:
      1. **Does the pipeline still work under Fusion?** Same params as the validated run, **fresh
         `outdir` and work dir**. Success ⇒ compare the 9 cohort deliverables against
         `az://aletest/seqera-runs/2026-08-06-04`; they should stay byte-identical.
      2. **Does Fusion lift the same-container rule?** Repeat the `48kJmc9QY6Q3h9` launch exactly —
         `--work-dir az://debugging/…`, inputs in `aletest`. That run is a clean predicted-failure
         baseline, so success here is unambiguous evidence Fusion uses per-container tokens. ⚠️ Until
         then, **do not design around it**.
- [ ] Still unproven: **`outdir` in a different container under a Platform head job.** Verified locally
      only; the cross-container run died before publishing, so it tested nothing about `outdir`.
- [x] 📏 **Measure actual node disk usage** — done 2026-08-07: **peak 65.2 G of 246.9 G (26%)**.
      ⚠️ Measured on **warm** nodes (already ~340 tasks across two runs), so it is a multi-run
      accumulation, and the base-OS vs pipeline-image split is **still unknown**. A cold-pool baseline
      is outstanding — see below.
- [ ] 🧊 **Cold-pool disk baseline** — rerun with `conf/disk_probe.config` on a pool that has drained to
      0, so the first task's reading is a genuine baseline. Only that separates the fixed base-image
      cost from this pipeline's own footprint, and the 128-vs-256 GB sizing decision rests on it.
      ⚠️ The probe now also samples `/mnt`: under Fusion the work dir is a FUSE mount reporting a
      synthetic `8.0P … 50%`, so `/mnt` is the only way to see whether Fusion's local cache competes
      with Docker for the ephemeral disk — which matters before moving Docker there.
- [ ] Repoint `yAMP-ottilie-test` at `…_autoScale_manual_noFusion`, then **delete both fixed-size CEs**
      (`ale-ottilie-nf25104-bigdisk`, `…-bigdisk_fusion`) — deletion disposes their pools and disks.
- [ ] Move Docker's data-root to `/mnt` via a pool start task (needs a `manual` CE) — the better fix
      than a larger OS disk; see the note above. ⚠️ Do the disk measurement **first**: it tells you
      whether 150 GB of ephemeral disk is actually enough headroom for the image set, which is the
      assumption that fix depends on.
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
- [ ] Rename the app registration to match its new purpose — the current display name describes the
      *previous* tenant of this SP, which is an audit hazard when someone reads a role assignment six
      months from now. `appId`/`objectId` survive a rename, so nothing downstream breaks. Scripts
      resolve by display name, so update `SP_DISPLAY_NAME` in `00_vars.sh` at the same time.
- [ ] Rotate the plaintext secret in `tmp/azure/azure_sp/.azure_sp.env` — it belongs to the *other* SP,
      not this one, but it is a live secret sitting unencrypted in the working tree. (Gitignored via
      `*.env`, so not committed.)
