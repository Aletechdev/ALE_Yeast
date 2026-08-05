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

## Open items

- [x] Grant the two roles (`02_grant_roles.sh`) — done 2026-07-31, verified.
- [x] Create a client secret (`03_create_secret.sh`) — done 2026-07-31.
- [x] Verify both data planes (`05_verify_sp_access.sh`) — done 2026-07-31, all checks passed.
- [x] Register the Entra credential in Seqera via the web UI — done 2026-07-31, schema captured.
- [x] Create a new compute environment bound to the `azure_SP_cfb_ale_mutations_pipeline` credential,
      with `NXF_VER=25.10.4` pinned via the head-job environment (plan Phase 4) — done 2026-08-05,
      two CEs (non-Fusion + Fusion), both AVAILABLE. The six existing CEs were not repointed.
- [ ] **Next:** `tw launch` against `ale-ottilie-nf25104` (plan Phase 6). Blocked on adding `outdir`
      to `conf/params_ottilie_blob.yml` — `tw launch` has no way to pass a single pipeline param.
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
