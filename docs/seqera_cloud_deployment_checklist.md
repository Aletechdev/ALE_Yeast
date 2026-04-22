# Seqera Platform Deployment Checklist — ALE Sarek Pipeline on Azure

**Created**: 2026-04-16
**Workspace**: RECON-ALE (DTU-Biosustain) — workspace ID: 79597273081110
**Platform**: https://cloud.seqera.io/orgs/DTU-Biosustain/workspaces/RECON-ALE
**Previous workspace**: zhlia-wsp (zhlia-org-ALE-beta) — used for initial setup

---

## Current State

### ✅ Already Prepared

| Item | File | Details |
|------|------|---------|
| Azure Nextflow config | `conf/seqera_azure.config` | Minimal: docker + custom_config_base null (resources now in base.config for E4ds_v5) |
| Launch parameters | `conf/params_seqera_test.yml` | All `az://aletest/` paths, tool selection, SnpEff config |
| Azure samplesheet | `assets/reads/samplesheet_azure.csv` | 5 samples × 4 lanes with `az://aletest/` blob paths |
| Upload script | `bin/upload_test_data_azure.sh` | azcopy-based upload to `aletest` container |
| Forked Sarek pipeline | `nf-core-sarek_3.5.1/3_5_1/` | All custom ALE modifications (ploidy, filtering, etc.) |
| Azure credentials | `aledev4test` in zhlia-wsp | Batch: `aledev4test`, Storage: `aledata` |
| Compute environment | `aledev4test` in zhlia-wsp | Azure Batch, region: northeurope, status: AVAILABLE |

---

## Deployment Steps

### Step 1: Upload Test Data to Azure Blob Storage
- **Status**: ✅ Done (2026-04-16) — 80 files uploaded to `aledata/aletest`
- **Blocker**: Resolved

```bash
# Prerequisites: az login, azcopy installed
export STORAGE_ACCOUNT="aledata"
bash bin/upload_test_data_azure.sh
```

Verify upload:
```bash
az storage blob list \
    --container-name aletest \
    --account-name aledata \
    --auth-mode login \
    --output table \
    --query "[].{Name:name}" | head -30
```

Uploaded paths:
- `az://aletest/assets/reads/` — FASTQ files + samplesheet
- `az://aletest/assets/references/` — FASTA, GFF3, SnpEff cache

---

### Step 2: Commit & Push Branch to GitHub
- **Status**: ✅ Done (2026-04-16) — pushed to `Aletechdev/ALE_Yeast` branch `worktree-seqera-cloud`
- **Blocker**: Resolved

```bash
cd /home/azureuser/Docs/ALE_nextflow/.claude/worktrees/seqera-cloud

git add conf/seqera_azure.config conf/params_seqera_test.yml \
        assets/reads/samplesheet_azure.csv bin/upload_test_data_azure.sh \
        README.md

git commit -m "Add Seqera Platform Azure deployment config and test data paths"

git push origin worktree-seqera-cloud
```

Pipeline reference for Seqera:
- **Repository**: `https://github.com/Aletechdev/ALE_Yeast`
- **Revision**: `worktree-seqera-cloud`
- **Main script**: `nf-core-sarek_3.5.1/3_5_1/main.nf`

---

### Step 3: Fix Compute Environment VM Size vs Config Mismatch
- **Status**: ✅ Done — `conf/seqera_azure.config` updated (2026-04-16)
- **Blocker**: Resolved

**VM chosen**: `Standard_D4s_v3 / D4as_v4` (4 vCPU, 16 GB, ~$0.19/hr)

**Rationale** (from actual Ottilie pilot trace, 4 yeast samples):
- Heaviest task: `BWAMEM1_MEM` — observed 4 vCPU, 4.8 GB RAM peak
- All other tasks (SnpEff, GATK, CNVKit) use < 2 GB RAM
- D4s_v3 fits all tasks with comfortable headroom
- D2as_v4 (2 vCPU) was considered but would halve BWA-MEM speed

**Changes made to `conf/seqera_azure.config`**:
```groovy
// Before
resourceLimits {
    cpus   = 8
    memory = 30.GB
    time   = 72.h
}
withName: 'MUTECT2*' {
    memory = { 14.GB * task.attempt }  // would exceed limit on retry
}

// After
resourceLimits {
    cpus   = 4      // matches D4s_v3 / D4as_v4
    memory = 14.GB  // 16 GB VM - 2 GB headroom
    time   = 72.h
}
withName: 'MUTECT2*' {
    memory = 12.GB  // fixed (was scaling * attempt, unsafe under 14 GB cap)
}
```

---

### Step 4: Add GitHub Credentials (repo is private)
- **Status**: ✅ Done (2026-04-17) — GitHub token added to Seqera Credentials
- **Blocker**: Resolved

Options (in order of speed):
1. **SSH deploy key** (no org approval needed): `ssh-keygen -t ed25519 -f seqera_deploy_key` → add public key to repo Deploy Keys → add private key to Seqera Credentials → SSH
2. **Fine-grained PAT** (waiting for org approval): once approved, add at Seqera → Credentials → Add → GitHub
3. **Classic PAT** at https://github.com/settings/tokens (scope: `repo`) — no org approval, personal account only

---

### Step 5: Add Forked Pipeline to Seqera Launchpad
- **Status**: ✅ Done (2026-04-17) — pipeline registered, parameters visible
- **Blocker**: Resolved (see Step 5 notes below)

Pipeline configuration:
| Setting | Value |
|---------|-------|
| Name | `ALE-Sarek-3.5.1` |
| Repository | `https://github.com/Aletechdev/ALE_Yeast` |
| Revision | `worktree-seqera-cloud` |
| Main script | ~~`nf-core-sarek_3.5.1/3_5_1/main.nf`~~ — not settable in this Seqera version (see notes) |
| Compute environment | `aledev4test` |
| Config profiles | `docker` |
| Nextflow config | Content of `conf/seqera_azure.config` |
| Parameters | Content of `conf/params_seqera_test.yml` |

> **Note**: The existing `nf-core-sarek` pipeline in zhlia-wsp points to upstream `nf-core/sarek`. Create a separate entry for the forked version.

#### ❌ Step 5 Notes: Option A (nested folder) does not work

**Problem**: Seqera Cloud hardcodes `-main-script main.nf` in the launch command and does not expose a UI field to change it. `manifest.mainScript` in root `nextflow.config` is ignored because the explicit CLI flag takes precedence.

**What was tried (Option A)**:
1. Added stub `main.nf` at repo root → satisfied Seqera's repo validation check
2. Added `nextflow_schema.json` at repo root → fixed missing parameter UI
3. Added root `nextflow.config` with `manifest { mainScript = 'nf-core-sarek_3.5.1/3_5_1/main.nf' }` → ignored by Seqera

**Actual Seqera launch command generated**:
```bash
nextflow run https://github.com/Aletechdev/ALE_Yeast \
  -name happy_babbage \
  -params-file https://api.cloud.seqera.io/ephemeral/... \
  -with-tower \
  -r worktree-seqera-cloud \
  -profile nextflow.config \   # ← BUG: should be 'docker', not a filename
  -main-script main.nf         # ← hardcoded to root stub, not nested path
```

**Two errors**:
- `Unknown configuration profile: 'nextflow.config'` — Config profiles field must be a profile name (e.g. `docker`), not a filename
- `-main-script main.nf` runs the root stub (just comments) — pipeline never starts

**Root cause**: Seqera Cloud (this version) always passes `-main-script main.nf` explicitly and provides no UI field to override it. `manifest.mainScript` cannot override an explicit CLI flag.

**Resolution**: Proceed to Option B — move pipeline contents to repo root on `worktree-seqera-cloud` branch.

---

### Step 5b: Restructure repo for Seqera (Option B)
- **Status**: ✅ Done (2026-04-17) — pipeline contents moved to repo root
- **Blocker**: Resolved

Moved `nf-core-sarek_3.5.1/3_5_1/` contents to repo root:
- `main.nf`, `nextflow.config`, `nextflow_schema.json` at root
- `workflows/`, `subworkflows/`, `modules/`, `conf/`, `assets/` at root
- Removed stub files added during Option A
- Removed `nf-core-sarek_3.5.1/configs/` (nf-core institutional configs, not needed for ALE)

#### ⚠️ Known Issue: `custom_config_base` local path artifact from `nf-core download`

**Root cause**: 3.5.1 was downloaded via `nf-core download`, which:
1. Places pipeline in a versioned subfolder (`3_5_1/`)
2. Bundles `nf-core/configs` repo alongside it (`configs/`)
3. **Patches `nextflow.config`** to point `custom_config_base` to the local bundled path:
   ```groovy
   custom_config_base = "${projectDir}/../configs/"  // ← patched by nf-core download
   ```

After Option B restructure, `configs/` no longer exists at `../` relative to the pipeline root, causing:
```
ERROR ~ Config file does not exist: .../configs/nfcore_custom.config
```

**Fix applied (2026-04-17)**: Changed `nextflow.config` line 140 to `custom_config_base = null`. This is the correct fix — the `includeConfig` condition on lines 321-324 checks `params.custom_config_base` at parse time, so the override in `seqera_azure.config` was too late to prevent the error.

```groovy
// nextflow.config line 140 — changed from nf-core download artifact:
custom_config_base = null  // was: "${projectDir}/../configs/"
```

The `params.custom_config_base = null` in `conf/seqera_azure.config` and `NXF_OFFLINE=true` in `bin/test_nf.sh` have been removed as they are no longer needed.

---

### Step 5c: Fix Cloud-Path and Resource Blockers During Launch Attempts (2026-04-17 → 2026-04-20)
- **Status**: ✅ Done — five errors diagnosed and fixed (2026-04-17 → 2026-04-20)

#### Fix 1: `custom_config_base` (described in Step 5b above)

#### Fix 2: Missing `aligner` parameter → null `.contains()` crash

**Error**: `Cannot invoke method contains() on null object`
**Location**: `subworkflows/local/samplesheet_to_channel/main.nf:177`
```groovy
if (step == 'mapping' && aligner.contains("dragmap") && ...)
```
**Root cause**: `aligner` has no default in `nextflow_schema.json`. When not set in the params file, it is `null` at runtime.
**Fix**: Added `aligner: "bwa-mem"` to `conf/params_seqera_test.yml`.

#### Fix 3: SnpEff cache validation fails for `az://` paths

**Error**: `Path provided with SnpEff cache is invalid. Make sure there is a directory named draft_ref.52 in az://aletest/assets/references/snpeff_cache`
**Location**: `subworkflows/local/annotation_cache_initialisation/main.nf:29`
```groovy
if ( !snpeff_cache_path_full.exists() || !snpeff_cache_path_full.isDirectory() )
```
**Root cause**: Azure Blob Storage has no real directory objects — only blobs with slash-delimited names. nf-azure's `AzPath.isDirectory()` returns `false` for virtual blob prefixes even when blobs exist beneath them (e.g. `snpeff_cache/draft_ref.52/snpEffectPredictor.bin` exists but `snpeff_cache/draft_ref.52` is not a real blob).
**Fix**: Added a cloud-path bypass in `annotation_cache_initialisation/main.nf` — skip the `exists()`/`isDirectory()` check when `snpeff_cache` starts with `az://`, `s3://`, or `gs://`. The check is a local-path sanity check; cloud paths are validated at runtime by Nextflow when the process actually reads them.

```groovy
def is_cloud_path = snpeff_cache ==~ /^(az|s3|gs):\/\/.*/
if ( !is_cloud_path && (!snpeff_cache_path_full.exists() || !snpeff_cache_path_full.isDirectory()) ) {
    // ... error
}
```

**Comparison with nf-core/sarek 3.8.1**: The upstream 3.8.1 added an `isCloudUrl()` helper but used it only to adjust the cache path prefix, not to bypass the `isDirectory()` check — the same bug exists there. The correct fix (using `isCloudUrl()` to guard the check) was not applied upstream:

```groovy
// 3.8.1 — isCloudUrl() exists but does NOT guard the check on line 29:
def snpeff_annotation_cache_key = isCloudUrl(snpeff_cache) ? "${snpeff_db}/" : ""
if (!snpeff_cache_path_full.exists() || !snpeff_cache_path_full.isDirectory()) { // ← still unguarded
```

If applying this fix to 3.8.1, replace the check with:
```groovy
if (!isCloudUrl(snpeff_cache) && (!snpeff_cache_path_full.exists() || !snpeff_cache_path_full.isDirectory())) {
```

#### Fix 4: `processVersionsFromYAML` calls `toFile()` on cloud paths (2026-04-20)

**Error**: `Operation 'toFile' is not supported by AzPath`
**Location**: `subworkflows/nf-core/utils_nfcore_pipeline/main.nf:113`
```groovy
def versions = yaml.load(new java.io.FileInputStream(path.toFile())).collectEntries { ... }
```
**Stack trace** (from `nf-4DGxqjkDgX4Zd6_20APril.log`):
```
[Actor Thread 38] ERROR nextflow.extension.OperatorImpl - @unknown
java.lang.UnsupportedOperationException: Operation 'toFile' is not supported by AzPath
    at ...AzPath.toFile(AzPath.groovy:279)
    at ...processVersionsFromYAML(Script_...:113)              ← toFile() call
    at ...softwareVersionsToYAML_closure3(Script_...:145)      ← .map operator
    at nextflow.extension.MapOp$_apply_closure1(MapOp.groovy:56)
```

**Root cause**: `processVersionsFromYAML()` is called within a `.map` operator (line 145) that processes `versions.yml` files emitted by completed tasks. On Azure, these paths are `AzPath` objects (e.g. `az://debugging/scratch/.../versions.yml`). `java.io.FileInputStream` requires a local `File` object via `path.toFile()`, but `AzPath.toFile()` throws `UnsupportedOperationException` because cloud paths have no local filesystem representation.

**Fix**: Replace `FileInputStream(path.toFile())` with `Files.newInputStream(path)`, which routes through the NIO FileSystem provider and supports all cloud path implementations (Azure, S3, GCS):
```groovy
// Before (breaks on cloud paths):
def versions = yaml.load(new java.io.FileInputStream(path.toFile())).collectEntries { k, v -> ... }

// After (works everywhere):
def versions = yaml.load(java.nio.file.Files.newInputStream(path)).collectEntries { k, v -> ... }
```

**Impact**: This error caused `Session aborted` — the entire pipeline run was terminated when the first `versions.yml` file was processed. All running Azure Batch tasks were cancelled.

**Upstream status**: This function exists in all nf-core pipelines via the `utils_nfcore_pipeline` subworkflow. The same `toFile()` bug affects any nf-core pipeline running on cloud storage. Upstream nf-core/sarek 3.8.1 uses a different versions collection mechanism (nf-validation plugin) that avoids this specific code path.

#### Fix 5: BWAMEM1_MEM `samtools sort` OOM + null read group metadata (2026-04-20)

**Error**: `samtools sort: couldn't allocate memory for bam_mem`
**Process**: `NFCORE_SAREK:SAREK:FASTQ_ALIGN_BWAMEM_MEM2_DRAGMAP_SENTIEON:BWAMEM1_MEM`
**Exit status**: 1

**Diagnosis** (via Seqera Platform REST API and `tw` CLI):
- Run `155jcXnP7lx7UX` ("admiring_panini") — 20 BWAMEM1_MEM tasks submitted
- All tasks requested **24 CPUs, 30 GB memory** (from `process_high` label defaults)
- `samtools sort --threads 24` allocates 24 sorting buffers (~768 MB each = ~18 GB)
- Combined with BWA's memory usage, exceeded the 30 GB allocation
- This indicates **the Seqera run did NOT use `conf/seqera_azure.config`** (which caps at 4 CPUs / 14 GB)

**Secondary issue — null read group metadata** (resolved):
```
-R "@RG\tID:null.A1-F6-I1-R1.L003\tPU:L003\tSM:ALE_Exp1_A1-F6-I1-R1\tLB:A1-F6-I1-R1\tDS:az://...\tPL:null"
```
- `ID: null.sample.lane` — flowcell not parsed from FASTQ headers
- `PL: null` — `seq_platform` param was not set in the Seqera launch params
- **Fix**: `seq_platform: "ILLUMINA"` in `conf/params_seqera_test.yml` resolves the `PL:null` issue

**Root cause**: The Seqera UI launch used **different params** than our `params_seqera_381.yml`:
- `seq_platform` was `None` (our file has `ILLUMINA`)
- `tools` included `breseq` (our file excludes it)
- `resourceLimits` were not applied (config not loaded)

**Fixes needed for next launch**:
1. **Verify Seqera "Nextflow config" field** contains `conf/seqera_azure.config` content (not just filename)
2. **Verify Seqera "Parameters" field** uses `conf/params_seqera_381.yml` content
3. `seq_platform: "ILLUMINA"` is already in `params_seqera_381.yml` — ensure it's loaded
4. `resourceLimits { cpus = 4; memory = 14.GB }` in `seqera_azure.config` will reduce to 4 threads, fixing the OOM

**For yeast genome (~12 MB)**: BWA index is 130 MB, BWA-MEM peak RSS < 200 MB. With 4 CPUs and `samtools sort --threads 4`, memory usage will be < 4 GB. The 14 GB cap is more than sufficient.

#### Fix 6: Non-pipeline folders in `bin/` cause tar path length errors on Azure Batch

**Error**: MultiQC and other processes failed with tar path length errors during Azure Batch file staging.
**Root cause**: Nextflow stages the entire `bin/` directory into every task's working directory. Nested folders not used by the pipeline (benchmarking scripts, analysis comparisons, documentation) created excessively long paths that exceeded tar limits on Azure Batch.
**Fix**: Moved non-pipeline folders out of `bin/` into `docs/`:
- `bin/benchmarking/` → `docs/benchmarking/`
- `bin/compare_mutect2_HpCaller/` → `docs/compare_mutect2_HpCaller/`
- Other nested analysis/documentation folders similarly relocated

**Rule**: `bin/` should contain only scripts directly called by Nextflow processes. Everything else belongs in `docs/` or project-level directories.

**Details**: See `docs/fix6_multiqc_tar_path_length.md`

---

### Step 6: Launch Test Run
- **Status**: ☐ Pending
- **Target VM**: E4ds_v5 (4 vCPU, 32 GB, ~$0.29/hr) — upgrade from D4s_v3 for breseq headroom
- **Config strategy**: Resources baked into `base.config` — no need to paste config in Seqera UI

**What changed (Fix 5 resolution)**:
- `conf/base.config` now contains `resourceLimits { cpus = 4; memory = 28.GB }` and all process overrides
- `conf/seqera_azure.config` stripped to just `params.custom_config_base = null` + docker safety net
- **Seqera "Nextflow config" field**: Optional — paste `seqera_azure.config` content only if docker profile isn't loaded
- **Seqera "Parameters" field**: Use `conf/params_seqera_test.yml`

**Compute environment change needed**:
- Update `aledev4test` pool VM from `Standard_D4s_v3` to `Standard_E4ds_v5`
- Or create new compute environment with E4ds_v5

**Seqera Batch Forge behavior** (important constraints):
- Single VM type per pool — all tasks run on E4ds_v5 regardless of resource requests
- One task per node — no task packing (FastQC gets a whole 32 GB VM)
- This is acceptable: light tasks finish fast, cost per task is pennies
- If breseq OOMs at 28 GB in future: upgrade pool to E8ds_v5 or create second compute env

Launch via Seqera Platform UI or API. Monitor at:
https://cloud.seqera.io/orgs/DTU-Biosustain/workspaces/RECON-ALE/watch

---

### Step 7: Merge `worktree-seqera-cloud` into `main`
- **Status**: ☐ Pending — Seqera deployment working, branch ready to contribute back

**Why merge**: The `worktree-seqera-cloud` branch contains all fixes needed to run the ALE Sarek pipeline on Seqera Cloud Platform with Azure Batch. These changes benefit the main branch regardless of deployment target (cloud-path fixes, resource tuning, repo restructure).

**Strategy**: Use `git merge` (not rebase) to preserve the branch's commit history. Both branches will continue to diverge — `main` for local/production work and new features (e.g., Ottilie benchmark), `worktree-seqera-cloud` for continued Seqera testing and cloud fixes.

**Pre-merge checklist**:
```bash
# 1. Check divergence
cd /home/azureuser/Docs/ALE_nextflow
git fetch origin
git log --oneline main..worktree-seqera-cloud   # commits to bring in
git log --oneline worktree-seqera-cloud..main    # commits on main since branch point

# 2. Preview conflicts
git merge-tree --write-tree main worktree-seqera-cloud
# Or dry-run:
git merge --no-commit --no-ff worktree-seqera-cloud && git merge --abort
```

**Known conflict area**: `bin/` → `docs/` directory moves (Fix 6).
- This branch moved nested folders not used by the pipeline (e.g., `bin/benchmarking/`, `bin/compare_mutect2_HpCaller/`) to `docs/`
- Main branch may still have content in `bin/` or may have added new files there
- **Resolution rule**: Non-pipeline-script content stays in `docs/` — `bin/` staging causes tar path length errors and unnecessary overhead on Azure Batch (see Fix 6 below and `docs/fix6_multiqc_tar_path_length.md`)

**Merge steps**:
```bash
cd /home/azureuser/Docs/ALE_nextflow  # main repo (not worktree)
git checkout main
git merge worktree-seqera-cloud

# If conflicts:
#   - bin/ vs docs/ moves → keep in docs/ (Fix 6 reasoning)
#   - Review each conflict against docs/fix6_multiqc_tar_path_length.md
#   - git add <resolved files> && git commit

git push origin main
```

**Post-merge**:
- Keep `worktree-seqera-cloud` branch alive for continued Seqera testing
- Future Seqera-specific fixes go on this branch, then merge back periodically
- Main branch can pull from this branch at any time with `git merge worktree-seqera-cloud`

---

## Cloud-Path Compatibility Patterns

### Why these errors happen

nf-core/sarek 3.5.1 was designed for local and HPC execution, where all paths are POSIX filesystem paths. When running on cloud storage (Azure Blob, S3, GCS), Nextflow replaces `java.nio.file.Path` with cloud-specific implementations (`AzPath`, `S3Path`) that support NIO operations but **not** `java.io.File` operations.

Three categories of incompatibility appear:

### Pattern 1: `path.toFile()` — Local filesystem assumption
**Affected**: Fix 4 (`processVersionsFromYAML`)
**Root cause**: `java.io.FileInputStream(path.toFile())` assumes a local file. `AzPath.toFile()` throws `UnsupportedOperationException`.
**Fix pattern**: Use `java.nio.file.Files.newInputStream(path)` — NIO-based, works with all Path implementations.
**How to find**: Search for `toFile()` in `.nf` and `.groovy` files.

### Pattern 2: `path.exists()` / `path.isDirectory()` — Virtual directories
**Affected**: Fix 3 (SnpEff cache validation)
**Root cause**: Cloud object stores have no real directories — only blob keys with `/` delimiters. `AzPath.isDirectory()` returns `false` for virtual prefixes even when blobs exist beneath them.
**Fix pattern**: Guard `exists()`/`isDirectory()` checks with a cloud-path detector (`path ==~ /^(az|s3|gs):\/\/.*/`). Skip the check for cloud paths and let Nextflow validate at runtime.
**How to find**: Search for `.exists()` and `.isDirectory()` on Path objects in validation code.

### Pattern 3: Config path resolution at parse time
**Affected**: Fix 1 (`custom_config_base`)
**Root cause**: `includeConfig` is evaluated at Nextflow config parse time, before process execution. Cloud paths or relative paths that don't exist at parse time cause immediate failure. Runtime overrides (e.g., in `seqera_azure.config`) are too late.
**Fix pattern**: Set the parameter to `null` directly in `nextflow.config` to prevent the `includeConfig` from firing.
**How to find**: Search for `includeConfig` with path expressions that depend on `${projectDir}` or `params.*`.

### Checklist for cloud-proofing nf-core pipelines

- [ ] Search all `.nf` files for `toFile()` — replace with `Files.newInputStream()` or `Files.newBufferedReader()`
- [ ] Search for `.exists()` and `.isDirectory()` on user-provided paths — guard with cloud-path check
- [ ] Verify all `includeConfig` paths resolve at parse time, not just at runtime
- [ ] Test with `--outdir az://...` and `--input az://...` to catch staging issues
- [ ] Ensure `params.custom_config_base` doesn't point to a nonexistent local path

---

## Quick Reference

### Seqera Platform Links
- Workspace: https://cloud.seqera.io/orgs/DTU-Biosustain/workspaces/RECON-ALE
- Compute Envs: https://cloud.seqera.io/orgs/DTU-Biosustain/workspaces/RECON-ALE/compute-envs
- Launchpad: https://cloud.seqera.io/orgs/DTU-Biosustain/workspaces/RECON-ALE/launchpad
- Runs: https://cloud.seqera.io/orgs/DTU-Biosustain/workspaces/RECON-ALE/watch

### Existing Credentials (zhlia-wsp)
| Name | Provider | Batch Account | Storage Account |
|------|----------|---------------|-----------------|
| `aledev4test` | Azure | aledev4test | aledata |
| `azure-seqera` | Azure | seqeracomputebatch | seqeratestzl |

### Existing Compute Environments (zhlia-wsp)
| Name | Platform | VM Type | Work Dir | Status |
|------|----------|---------|----------|--------|
| `aledev4test` | Azure Batch | Standard_D4s_v3 → **upgrade to E4ds_v5** | `az://debugging` | AVAILABLE |
| `AzBatchForge` | Azure Batch | — | `az://seqeracomputestorage-container` | AVAILABLE |
| `AzBatchForge_copy` | Azure Batch | — | `az://seqeracomputestorage-container` | AVAILABLE |
| `zhlia-compute-env` | Seqera Compute | — | `s3://zhlia-compute-env-*` | AVAILABLE |
