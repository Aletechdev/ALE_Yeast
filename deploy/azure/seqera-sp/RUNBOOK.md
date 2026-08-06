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
parallel and is **pending org-owner approval**. ⚠️ Note for anyone repeating this: the org *does*
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

## GitHub PAT (classic — interim credential)

| Seqera credential | Provider | Owner | Created | **Expires** |
|---|---|---|---|---|
| `personal_token_classic_ALE_yeast` (`Z3yo4zFgy1xfdW0Ts11kI`) | `github` | **personal** account of the operator (Seqera user `zhlia`) | 2026-08-06 | **2026-11-04** (Wed) |

Scope: classic **`repo`**. ⚠️ This cannot be narrowed — `repo` grants read *and write* on every
repository the owner can reach, so it is **strictly broader than the deploy key it replaced**. That is
a property of classic PATs, not a configuration mistake: GitHub provides no read-only scope for private
repositories.

> ⏰ **Set a calendar reminder for ~2026-10-21** (two weeks before expiry). This is a *shared org
> workspace* running on *one person's* personal token: when it lapses, every launch in the workspace
> fails with the opaque `Unknown pipeline repository or expired Git credentials`, and the person who
> can fix it may not be the person who hits it. This has already happened once here —
> `seqera-platform-ale-16april2026` expired unnoticed and cost a full debugging session.

**Retire it early if possible.** The 90-day expiry is deliberately short because this is a stopgap: a
fine-grained PAT (`Contents: Read` on `ALE_Yeast` only) is pending org-owner approval, and an org-owned
GitHub App is the durable answer. On either landing, re-register the credential and **revoke this
token** rather than letting it run to November.

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
      `personal_token_classic_ALE_yeast`; the repo clones over HTTPS.
- [x] Register the Launchpad pipeline — `yAMP-ottilie-test` (`227651105760023`), done 2026-08-06.
- [x] Record the classic PAT's owner and expiry — done: expires **2026-11-04**, see the table above.
- [ ] ⏰ Set a calendar reminder for **~2026-10-21** (two weeks before the PAT expires).
- [ ] Chase the **fine-grained PAT** approval (submitted 2026-08-06, pending an `Aletechdev` owner).
      On approval: re-register the credential, then **revoke the classic token** — `repo` scope cannot
      be narrowed and is strictly broader than the deploy key it replaced.
- [ ] 🔁 **Swap to an org-owned GitHub App** when an org owner is available — the durable answer, and
      the only option that restores what the deploy key was chosen for.
- [x] `tw launch` (plan Phase 6) and compare outputs against the local-head-job baseline — **done
      2026-08-06**: `3C5zYMYY5M32dO` SUCCEEDED, 170/170 tasks, 9/9 cohort deliverables byte-identical.
- [ ] Point the `yAMP-ottilie-test` Launchpad entry at `ale-ottilie-nf25104-bigdisk` — it still
      references the old single-pool CE, which fails at ~98% under disk pressure. ⚠️ `tw pipelines
      update` is broken; delete and re-add, or edit in the web UI.
- [ ] Retire the two superseded CEs (`ale-ottilie-nf25104`, `…-fusion`) once nothing references them.
- [ ] Run 2: relaunch against `ale-ottilie-nf25104-fusion` with a **fresh `outdir` and work dir**, to
      settle whether Fusion removes the same-container SAS rule. ⚠️ That CE is **single-pool** and has
      no boot-disk override, so it will likely hit the same `DiskFull` — re-forge it with `--dual-pool`
      and `--worker-boot-disk-size` before drawing any conclusion about Fusion.
- [ ] Move Docker's data-root to `/mnt` via a pool start task (needs a `manual` CE) — the better fix
      than a larger OS disk; see the note above.
- [x] GitHub auth decided and keypair generated (`07_github_deploy_key.sh`) — the pre-existing
      `github_Aletechdev` credential had in fact expired.
- [x] Deploy key registered on the repo and as a Seqera `ssh` credential; auth + read access verified.
- [ ] Use the SSH form `git@github.com:Aletechdev/ALE_Yeast.git` in every launch — the deploy key
      cannot authenticate HTTPS.
- [ ] ⚠️ **Push before launching.** Seqera clones from GitHub, so anything unpushed does not exist for
      a cloud run. At the time of writing, local `main` is **4 commits ahead** of remote `main`, and
      `deploy/azure/` is entirely uncommitted. One of the unpushed commits
      (`build: align environment.yml to NXF_VER=25.10.4`) is directly relevant to the version pinning
      in Phase 4. Launching `--revision v1.0.0` uses the tag, which does exist remotely — but any run
      against `main` would silently use older code.
- [ ] Rename the app registration to match its new purpose — the current display name describes the
      *previous* tenant of this SP, which is an audit hazard when someone reads a role assignment six
      months from now. `appId`/`objectId` survive a rename, so nothing downstream breaks. Scripts
      resolve by display name, so update `SP_DISPLAY_NAME` in `00_vars.sh` at the same time.
- [ ] Rotate the plaintext secret in `tmp/azure/azure_sp/.azure_sp.env` — it belongs to the *other* SP,
      not this one, but it is a live secret sitting unencrypted in the working tree. (Gitignored via
      `*.env`, so not committed.)
