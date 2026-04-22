---
name: tw-cli-reference
description: Reference for using the Seqera Tower CLI (tw) to manage pipeline runs, workspaces, and Azure Batch compute
triggers:
  - tw cli
  - tower cli
  - check runs
  - pipeline run status
  - batch pool
allowed-tools: Bash(tw:*)
metadata:
  service: seqera-tower-cli
  audience: developers
  workflow: operations
  version: '0.26.0'
---

# Seqera Tower CLI (tw) Reference

## Authentication

```bash
# Set token (stored in .env)
export TOWER_ACCESS_TOKEN=<token>

# Verify connection
tw info
```

Credentials file: `/home/azureuser/Docs/ALE_nextflow/.claude/worktrees/seqera-cloud/.env`

## Workspaces

```bash
# List all workspaces
tw workspaces list

# Key workspaces:
#   79597273081110  | RECON-ALE      | DTU-Biosustain
#  148627246605113  | zhlia-wsp      | zhlia-org-ALE-beta
```

Always specify `-w <workspace_id>` — the default user workspace is usually empty.

## Pipeline Runs

```bash
# List recent runs
tw runs list -w 79597273081110

# View run details (use flags to select sections)
tw runs view -i <run_id> -w <workspace_id> --status
tw runs view -i <run_id> -w <workspace_id> --processes
tw runs view -i <run_id> -w <workspace_id> --command
tw runs view -i <run_id> -w <workspace_id> --params
tw runs view -i <run_id> -w <workspace_id> --config
tw runs view -i <run_id> -w <workspace_id> --stats

# View task-level details
tw runs view -i <run_id> -w <workspace_id> tasks
```

**Note**: `tw runs view` can error with "Error reading entity from input stream" for some runs. Fallback to the API directly:

```bash
curl -s -H "Authorization: Bearer $TOWER_ACCESS_TOKEN" \
  "https://api.cloud.seqera.io/workflow/<run_id>?workspaceId=<workspace_id>" \
  | python3 -m json.tool
```

Extract key failure info from API response:
```bash
curl -s -H "Authorization: Bearer $TOWER_ACCESS_TOKEN" \
  "https://api.cloud.seqera.io/workflow/<run_id>?workspaceId=<workspace_id>" \
  | python3 -c "
import sys,json
d = json.load(sys.stdin)
w = d['workflow']
print('Status:', w['status'])
print('Run:', w['runName'])
print('Error:', (w.get('errorReport') or 'N/A')[:2000])
"
```

## Compute Environments

The Seqera browser UI for creating compute environments can be buggy. Use the API instead.

```bash
# List compute environments
tw compute-envs list -w 79597273081110
```

### Create a New Compute Environment (API)

Export an existing one as a template, then POST with modifications:

```bash
# Get existing compute env config
curl -s -H "Authorization: Bearer $TOWER_ACCESS_TOKEN" \
  "https://api.cloud.seqera.io/compute-envs/<env_id>?workspaceId=79597273081110" \
  | python3 -m json.tool

# Create new compute environment
curl -s -X POST \
  -H "Authorization: Bearer $TOWER_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  "https://api.cloud.seqera.io/compute-envs?workspaceId=79597273081110" \
  -d '{
    "computeEnv": {
      "name": "ALE_E4ds_v4_16workers",
      "platform": "azure-batch",
      "credentialsId": "26xUXkaHb4vh0oLSAyKRK6",
      "config": {
        "workDir": "az://debugging",
        "region": "northeurope",
        "forge": {
          "disposeOnDeletion": true,
          "dualPoolConfig": true,
          "headPool": {
            "vmType": "Standard_D2s_v3",
            "vmCount": 1,
            "autoScale": true
          },
          "workerPool": {
            "vmType": "Standard_E4ds_v4",
            "vmCount": 16,
            "autoScale": true
          }
        },
        "jobMaxWallClockTime": "7d",
        "deleteJobsOnCompletionEnabled": false,
        "deleteTasksOnCompletion": true,
        "terminateJobsOnCompletion": true,
        "deletePoolsOnCompletion": false,
        "waveEnabled": false,
        "fusion2Enabled": false
      }
    }
  }'
```

### Key Fields to Customize

| Field | Description |
|-------|-------------|
| `name` | Display name in Seqera UI |
| `credentialsId` | Azure credentials — use `26xUXkaHb4vh0oLSAyKRK6` for aledev4test |
| `config.workDir` | Azure Blob work directory (e.g., `az://debugging`) |
| `config.region` | Azure region (e.g., `northeurope`) |
| `forge.headPool.vmType` | Head node VM size (small is fine, e.g., `Standard_D2s_v3`) |
| `forge.workerPool.vmType` | Worker VM size — must have quota (see VM families table below) |
| `forge.workerPool.vmCount` | Max worker nodes (vCPUs = vmCount × cores_per_vm, must fit quota) |
| `forge.workerPool.autoScale` | `true` to scale down when idle |
| `forge.dualPoolConfig` | `true` for separate head/worker pools |

### Delete a Compute Environment

```bash
tw compute-envs delete -i <env_id> -w 79597273081110
```

## Azure Batch Troubleshooting

When runs fail with pool resize errors, use `az` CLI to diagnose:

```bash
# Login to batch account
az batch account login --name aledev4test --resource-group rg-aledb

# List pools and their state
az batch pool list \
  --query "[].{name:id, state:allocationState, vmSize:vmSize, currentDedicated:currentDedicatedNodes, targetDedicated:targetDedicatedNodes}" \
  -o table

# Check resize errors on a specific pool
az batch pool show --pool-id <pool-id> \
  --query "{vmSize:vmSize, resizeErrors:resizeErrors}" -o json

# Check per-family VM quotas
az batch account show --name aledev4test --resource-group rg-aledb \
  -o json | python3 -c "
import sys,json
d = json.load(sys.stdin)
for f in d['dedicatedCoreQuotaPerVmFamily']:
    if f['coreQuota'] > 0:
        print(f'{f[\"name\"]}: {f[\"coreQuota\"]} cores')
"
```

### Batch Account: aledev4test (northeurope, rg-aledb)

**Quotas:**
| Resource | Limit |
|----------|-------|
| Dedicated cores (total) | 350 vCPUs |
| Low-priority cores | 350 vCPUs |
| Pool quota | 100 pools |
| Active jobs & schedules | 300 |

**VM families with quota (as of 2026-04-20):**
| Family | Quota | Example VM |
|--------|-------|------------|
| standardDv3 / DSv3 | 350 | standard_d4s_v3 |
| standardEv3 / ESv3 | 350 | standard_e4s_v3 |
| standardDDv4 / DDSv4 | 350 | standard_d4ds_v4 |
| standardEDv4 / EDSv4 | 350 | standard_e4ds_v4 |
| standardDv2 / DSv2 | 350 | standard_d4s_v2 |
| standardAv2 | 350 | standard_a4_v2 |
| standardFSv2 | 175 | standard_f4s_v2 |

**Zero quota (common pitfall):**
- standardEDSv5Family = 0 (caused `dreamy_church` failure)
- All GPU families = 0
- All v6 families = 0

### Common Errors

| Error | Cause | Fix |
|-------|-------|-----|
| `AccountVMSeriesCoreQuotaReached` | VM family has 0 or insufficient quota | Switch VM size to a family with quota, or request increase in Azure Portal |
| `toFile not supported by AzPath` | Nextflow operation incompatible with Azure Blob | Check pipeline code for local filesystem assumptions |
| File name too long (>100 bytes) | Container tar layer path limit | Shorten file paths in pipeline |
