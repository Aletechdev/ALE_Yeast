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
    --params-file conf/params_ottilie_test_blob.yml
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

**Params stay dataset-specific and ready-to-run.** `conf/params_ottilie_test_blob.yml` is deliberately a
filled-in, launch-without-editing file rather than a template with placeholders — splitting it into a
generic template is explicitly deferred. Note that Platform stores params as a single `paramsText`
blob, so launch-time params **replace** the saved set rather than merging key-by-key; saved params are
an editable template, never inherited defaults.

> 📛 **Renamed 2026-08-12: `params_ottilie_blob.yml` → `params_ottilie_test_blob.yml`.** The unmarked
> name read as the generic default when it is in fact the narrow 2-sample, 4-chromosome subset. `_test`
> matches the convention already used by `fastq_test/`, `S288C_reference_test/`,
> `samplesheet_test_az.csv` and the `ottilie_test` profile. It survives because
> `bin/test_ottilie_azure_batch.sh` reads it for the **local** head-job path.
>
> 🚨 **A Launchpad entry does NOT reference a params file — it stores a pasted COPY.** The
> `yAMP-ottilie-test` entry holds the params as `paramsText`, captured 2026-08-07 and never re-read.
> **Editing the repo file does not change what that entry launches**; the two drift in silence, and
> nothing warns you. The same applies to the *Nextflow config* box — see the same pattern recorded for
> `ALE-Sarek-3.5.1` in [`../../../docs/seqera_cloud/seqera_cloud_deployment_checklist.md`](../../../docs/seqera_cloud/seqera_cloud_deployment_checklist.md)
> ("Parameters | Content of `conf/params_seqera_test.yml`"), where it was written down as a setup step
> rather than as a hazard.
>
> ✅ **The fix is a profile, not a better paste.** `-p docker,ottilie_test_az` makes Platform read
> [`conf/test/ottilie_test_az.config`](../../../conf/test/ottilie_test_az.config) from the cloned repo
> on **every** launch, so there is no copy to rot. Only `outdir` stays in the parameters box, because
> it must change per run anyway.
>
> ⚠️ Two conditions, or the profile silently does nothing:
> 1. **Empty the parameters box down to `outdir`.** Nextflow precedence is config < params-file < CLI,
>    and Platform passes `paramsText` as a params file — a full `paramsText` shadows the profile
>    entirely, and the run looks like the profile never took effect.
> 2. **Push.** Platform clones from GitHub at the registered revision, so an unpushed profile edit does
>    not exist as far as a Launchpad run is concerned.
>
> ⚠️ **`tw pipelines update` cannot be used to switch an existing entry over.** It returns HTTP 500,
> reproduced on 0.38.0 (2026-08-12) — and unlike the `tw`-vs-API split in the autoscale case, going
> under the CLI does **not** help: `PUT /pipelines/{id}` returns 400 both with `name` added and with the
> full launch object round-tripped from `GET`. `add` is the only working path, so switching means
> registering a new entry (new pipeline id) and deleting the old one.

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

> ⚠️ **Superseded 2026-08-11** — the diagnosis holds, but "use the UI" and "`tw` cannot" were both too
> strong. See the 2026-08-11 entry below: CEs are now created by script.

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

### 2026-08-12 — ✅ Launchpad params come from the repo now, not a pasted copy

**New entry `yAMP-ottilie-test-az` (`227711052831937`)**, registered with `tw pipelines add` because
`update` is dead (see the note under *Params stay dataset-specific* above). Readback:

| Field | Value |
|---|---|
| Compute env | `ale-ottilie-nf25104-bigdisk_autoScale_manual_noFusion` (`5u0qeS7p3cNmOITd5Gdhe1`) |
| Repo / revision | `https://github.com/Aletechdev/ALE_Yeast` @ `main` |
| **Config profiles** | **`docker`, `ottilie_test_az`** ← the params live in the repo |
| **paramsText** | **one line** — `outdir: "az://aletest/seqera-runs/2026-08-12-01"` |
| `nextflowVersion` / `configText` | unset |

**One entry, not one per dataset.** Profiles are overridable per launch, exactly as the CE is, so the
full-depth pilot runs from this same entry with `-p docker,ottilie_pilot_az` plus its own `outdir`.

⚠️ **`nextflowVersion` is deliberately left unset**, unlike the old entry which stored `26.04`. That
value never took effect — the CE's `NXF_VER=25.10.4` wins (§12) — and it contradicts what actually
runs, since 26.x cannot parse `nextflow.config`. Pinning the engine per *pipeline* rather than per *CE*
is arguably the better model (one CE could then serve entries on different versions), but it is not
usable yet: neither `tw pipelines add` nor `tw launch` has a `--nextflow-version` flag, so it is
UI-only, and the CE-level pin additionally covers ad-hoc launches that name no entry. Revisit if `tw`
gains the flag.

✅ **The old `yAMP-ottilie-test` (`227651105760023`) was kept as a fallback until the new entry was
proven by a run, then deleted 2026-08-13.** A readback proves *configuration*; only a real run proves
the profile resolves on Platform — and since neither entry can be renamed or patched, there was no cost
to waiting. Run `1XuapND2cN2oCO` provided that proof (see the 2026-08-13 entry).

### 2026-08-12 — Launchpad params moved into the repo, and the one default that refuses to move

**New entry `yAMP-ottilie-test-az` (`172614290773283`)**, registered by
[`14_register_pipeline.sh`](14_register_pipeline.sh). Config profiles `docker, ottilie_test_az`; the CE
is the autoscaling non-Fusion keeper; `nextflowVersion` and `configText` unset.

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

> 📋 **This file needs slimming.** ~2,000 lines across it, `azure_batch_execution.md`,
> `output_comparison.md` and `../README.md`, with the same findings written out in full in two or three
> places (the DiskFull story, the dual-pool autoscale incident, the same-container rule). The
> convention to restore is `CLAUDE.md`'s: dated record here, durable rules in `docs/`, summary +
> pointer in `CLAUDE.md`. **This runbook should shrink the most**: entries should say *what was run,
> when, and what was concluded* — then link to `azure_batch_execution.md` for the explanation.
> Superseded sagas can collapse behind `<details>` or reduce to a line plus a pointer.
> ⚠️ **Keep every ⚠️ that cost real time or money, and keep the corrections** —
> entries recording claims that turned out wrong (the "~30 GB default OS disk", concurrency as the
> DiskFull cause, the warm-node disk baseline) exist so the wrong conclusion is not re-derived; they
> can be compressed to a line each, never deleted. Afterwards run
> `python docs/dev-practices/check_docs.py` — broken links must be 0.
> 📌 `NEXT_TASKS.md` (the 2026-08-07 handoff file) was **retired 2026-08-13**: its Task 1 (CE-as-code)
> was closed 2026-08-11, this banner absorbed Task 2 (doc slimming), and every remaining item it
> listed was already tracked in the list below. Its stale "live resources" table (pre-dating the
> 2026-08-13 CE cleanup) died with it.

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
- [ ] **Does Fusion lift the same-container rule?** Repeat the `48kJmc9QY6Q3h9` launch exactly —
      `--work-dir az://debugging/…`, inputs in `aletest`. That run is a clean **predicted-failure**
      baseline (0/6 tasks, `Unable to download path`), so success here is unambiguous evidence Fusion
      uses per-container tokens. ⚠️ Until then, **do not design around it**.
      ⚠️ Launch against **`ale-ottilie-nf25104-bigdisk_autoScale_manual`** (`6zsRCxeGmUoiae4OVOGSKO`),
      the autoscaling Fusion keeper. This item previously named `…-bigdisk_fusion`, which is one of the
      two **fixed-size** CEs on the delete list below — launching there would bill 24/7.
      📌 Predicted failure ⇒ **no disk data**; it cannot double as the cold-pool disk run.
- [ ] Still unproven: **`outdir` in a different container under a Platform head job.** Verified locally
      only; the cross-container run died before publishing, so it tested nothing about `outdir`.
- [x] 📏 **Measure actual node disk usage** — done 2026-08-07: **peak 65.2 G of 246.9 G (26%)**.
      ⚠️ Measured on **warm** nodes (already ~340 tasks across two runs), so it is a multi-run
      accumulation, and the base-OS vs pipeline-image split is **still unknown**. A cold-pool baseline
      is outstanding — see below.
- [ ] 🧊 **Cold-pool disk baseline — on the FULL-DEPTH ottilie pilot.** Specified 2026-08-12; not yet run.

      **What it settles.** The 2026-08-07 figure (peak 65.2 G) was measured on **warm** nodes, so the
      ~54 G base was never split into OS vs Docker images. `/` carries two things: image layers
      (*data-independent*) and container writable layers + logs/temp (*data-dependent* — anything a
      task writes inside the container rather than into the bind-mounted work dir). Running ~11× the
      input data discriminates between them: a flat cold base ⇒ images dominate; a base that moves
      ⇒ they do not. At test-set scale the two cannot be separated at all. Also settles 128-vs-256 GB
      sizing, and whether Fusion's cache competes with Docker for `/mnt` before Docker is moved there.

      **Inputs — full-depth ottilie pilot, 4 samples. ✅ STAGED 2026-08-12** by
      [`upload_pilot_data.sh`](../../../docs/benchmarking/ottilie_xenobiotic_ale/01_data_retrieval/release/upload_pilot_data.sh):
      8 FASTQs (4.0 G, verified byte-for-byte) → `az://aletest/ottilie/v1/fastq_pilot_full/`, full
      reference (~79 M: fasta, genbank, snpeff_cache, chromosomes) → `…/S288C_reference/`, plus
      `…/samplesheet_pilot_az.csv`. All in the **private** `aletest` container — same container as
      `workDir`, per the SP SAS rule (§3). Params: the **`ottilie_pilot_az` profile**
      ([`conf/test/ottilie_pilot_az.config`](../../../conf/test/ottilie_pilot_az.config)) — every
      `az://` path verified to resolve. It sets no `outdir`: supply a fresh dated one per run, and a
      fresh work dir with it. **Remaining: forge a fresh CE, then launch with
      `-p docker,ottilie_pilot_az --config conf/disk_probe.config`.**
      ⚠️ **Real project data (dicarboxylic acids / CENPK) is not to be used** — it is not public;
      ottilie is. The public `aletestdatapublic/releases` account is untouched, and the upload script
      refuses to run against it. Layout + how the two ottilie datasets are told apart:
      [`blob_layout.md`](../../../docs/benchmarking/ottilie_xenobiotic_ale/blob_layout.md).

      **Tools: `snpeff,cnvkit,tiddit,manta,haplotypecaller`** — the validated cloud set, so the image
      set matches the 170-task run and the difference between readings is data scale alone. **No
      `controlfreec`**, though the local pilot script uses it: Tier-2, and its `ASSESS_SIGNIFICANCE`
      is auto-skipped at ploidy 1 (which every pilot sample is), so it adds an image and a
      failure-prone step for nothing.

      **Method.** Forge a **fresh CE** with `13_create_compute_env.sh` — new pools guarantee cold
      nodes, which is stronger than waiting for a drain. Attach the probe with
      `-c conf/disk_probe.config`. Fresh `outdir` **and** fresh `workDir`. Sample the **first task on
      each node** — that reading is the base cost and is the point of the exercise — not only the peak.

      ⚠️ **The probe perturbs the task hash** (`beforeScript` lives in `.command.run`), so this run
      cannot reuse or be reused by a cached run. Accept losing `-resume` deliberately.
      ⚠️ **Not comparable to the 65.2 G figure** — that came from the 2-sample, 4-chromosome test set.
      This is a new absolute measurement, not a diff.
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
      `*.env`, so not committed.) 📌 As of 2026-08-13 **the file no longer exists on this machine**, so
      the local exposure is gone — but the credential itself may still be live. Rotation is the task.
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
      still needs a freshly forged CE — not this one.
