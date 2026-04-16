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
- **Status**: ☐ Pending
- **Blocker**: Yes — no data, no run

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
- **Status**: ☐ Pending
- **Blocker**: **Yes — biggest blocker** (Seqera pulls pipeline from Git)

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

### Step 4: Add GitHub Credentials (if repo is private)
- **Status**: ☐ Pending (skip if repo is public)
- **Blocker**: Only if `Aletechdev/ALE_nextflow` is private

If needed, add a GitHub Personal Access Token (PAT) to Seqera:
1. Generate PAT at https://github.com/settings/tokens (scope: `repo`)
2. Add credential in Seqera Platform → Credentials → Add → GitHub
3. Or use Seqera API to create credential

---

### Step 5: Add Forked Pipeline to Seqera Launchpad
- **Status**: ☐ Pending
- **Blocker**: Yes — need pipeline entry to launch

Pipeline configuration:
| Setting | Value |
|---------|-------|
| Name | `ALE-Sarek-3.5.1` |
| Repository | `https://github.com/Aletechdev/ALE_Yeast` |
| Revision | `worktree-seqera-cloud` |
| Main script | `nf-core-sarek_3.5.1/3_5_1/main.nf` |
| Compute environment | `aledev4test` |
| Config profiles | `docker` |
| Nextflow config | Content of `conf/seqera_azure.config` |
| Parameters | Content of `conf/params_seqera_test.yml` |

> **Note**: The existing `nf-core-sarek` pipeline in zhlia-wsp points to upstream `nf-core/sarek`. Create a separate entry for the forked version.

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
