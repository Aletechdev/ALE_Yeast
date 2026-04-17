# Seqera Platform Deployment Checklist — ALE Sarek Pipeline on Azure

**Created**: 2026-04-16
**Workspace**: zhlia-wsp (zhlia-org-ALE-beta)
**Platform**: https://cloud.seqera.io/orgs/zhlia-org-ALE-beta/workspaces/zhlia-wsp

---

## Current State

### ✅ Already Prepared

| Item | File | Details |
|------|------|---------|
| Azure Nextflow config | `conf/seqera_azure.config` | Resource limits (4 vCPU / 14 GB for D4s_v3), retry strategy, Docker enabled |
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

**Current workaround**: `params.custom_config_base = null` in `conf/seqera_azure.config` (and `NXF_OFFLINE=true` in `bin/test_nf.sh`). Safe because nf-core institutional HPC configs are irrelevant for Azure Batch / ALE experiments.

**Ideal fix** (not yet applied): Update `nextflow.config` lines 140 and 321-324 to match 3.8.1 behaviour — use remote URL default and smarter offline check:
```groovy
// Line 140 — change from local path to remote URL:
custom_config_base = "https://raw.githubusercontent.com/nf-core/configs/${params.custom_config_version}"

// Lines 321-324 — smarter condition that skips remote URLs when offline:
includeConfig params.custom_config_base && (!System.getenv('NXF_OFFLINE') || !params.custom_config_base.startsWith('http')) ? "${params.custom_config_base}/nfcore_custom.config" : "/dev/null"
includeConfig params.custom_config_base && (!System.getenv('NXF_OFFLINE') || !params.custom_config_base.startsWith('http')) ? "${params.custom_config_base}/pipeline/sarek.config" : "/dev/null"
```
This would make the pipeline behave correctly with or without `NXF_OFFLINE`, matching standard nf-core 3.8.1+ behaviour.

---

### Step 6: Launch Test Run
- **Status**: ☐ Pending

Launch via Seqera Platform UI or API. Monitor at:
https://cloud.seqera.io/orgs/zhlia-org-ALE-beta/workspaces/zhlia-wsp/watch

---

## Quick Reference

### Seqera Platform Links
- Workspace: https://cloud.seqera.io/orgs/zhlia-org-ALE-beta/workspaces/zhlia-wsp
- Compute Envs: https://cloud.seqera.io/orgs/zhlia-org-ALE-beta/workspaces/zhlia-wsp/compute-envs
- Launchpad: https://cloud.seqera.io/orgs/zhlia-org-ALE-beta/workspaces/zhlia-wsp/launchpad
- Runs: https://cloud.seqera.io/orgs/zhlia-org-ALE-beta/workspaces/zhlia-wsp/watch

### Existing Credentials (zhlia-wsp)
| Name | Provider | Batch Account | Storage Account |
|------|----------|---------------|-----------------|
| `aledev4test` | Azure | aledev4test | aledata |
| `azure-seqera` | Azure | seqeracomputebatch | seqeratestzl |

### Existing Compute Environments (zhlia-wsp)
| Name | Platform | VM Type | Work Dir | Status |
|------|----------|---------|----------|--------|
| `aledev4test` | Azure Batch | Standard_D4s_v3 | `az://debugging` | AVAILABLE |
| `AzBatchForge` | Azure Batch | — | `az://seqeracomputestorage-container` | AVAILABLE |
| `AzBatchForge_copy` | Azure Batch | — | `az://seqeracomputestorage-container` | AVAILABLE |
| `zhlia-compute-env` | Seqera Compute | — | `s3://zhlia-compute-env-*` | AVAILABLE |
