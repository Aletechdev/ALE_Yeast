#!/usr/bin/env bash
# Verify a Seqera Azure Batch compute environment BEFORE running anything on it.
#
#   ./12_verify_compute_env.sh <ce-name-or-id>
#
# 🚨 WHY THIS EXISTS — a silent ~$66/day leak.
#
# `tw compute-envs add azure-batch forge --dual-pool` creates pools with `autoScale: null`,
# which Azure builds as `enableAutoScale: False` — FIXED SIZE, running 24/7 whether or not
# anything is queued. It reports success. Nothing warns you. On 2026-08-07 ten nodes
# (8x E4ds_v4 + 2x D2s_v3) ran idle for hours: ~$2.75/hr compute + ~$324/month of disks.
#
# The CLI only offers flags to DISABLE autoscaling (--no-auto-scale, --head-no-auto-scale,
# --worker-no-auto-scale), which reads as "on by default". For SINGLE-pool that is true.
# For DUAL-pool it is not. Upstream: seqeralabs/tower-cli#658, fix #659 (unmerged 2026-08-11).
#
# ➡️  CREATE DUAL-POOL CEs WITH ./13_create_compute_env.sh, which imports a readback of a known-good
#     config and then calls THIS script. (Earlier guidance here said "use the web UI" — superseded
#     2026-08-11.) This script still creates nothing: noticing that a CE will bill you forever is
#     the part worth automating.
#
# ⚠️ Compute environments are IMMUTABLE: a wrong setting cannot be patched, only deleted and
#    recreated. So verify at creation time, not after the invoice.
#
# Config reference (each value established by running it — see
# docs/dev-practices/azure_batch_execution.md):
#   workDir  az://aletest/nf-work   §3  MUST share a container with the inputs
#   NXF_VER  25.10.4                §12 26.x cannot parse nextflow.config
#   head     Standard_D2s_v3  64GB  §10 head job isolated from worker churn
#   worker   Standard_E4ds_v4 256GB §9  peak measured 65.2 G; the default overflows

set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

CE_REF="${1:?usage: $0 <ce-name-or-id>}"

SECRET_FILE="${SECRET_FILE:-$HOME/.config/ale-seqera/sp.env}"
if [[ -z "${TOWER_ACCESS_TOKEN:-}" && -r "$SECRET_FILE" ]]; then
    set -a; . "$SECRET_FILE"; set +a
fi
: "${TOWER_ACCESS_TOKEN:?TOWER_ACCESS_TOKEN not set — see 10_store_secret.sh}"

WORKSPACE_ID="${SEQERA_WORKSPACE_ID:-79597273081110}"
API="${SEQERA_API:-https://api.cloud.seqera.io}"

EXPECT_WORKER_DISK="${EXPECT_WORKER_DISK:-256}"
EXPECT_HEAD_DISK="${EXPECT_HEAD_DISK:-64}"
EXPECT_NXF_VER="${EXPECT_NXF_VER:-25.10.4}"
EXPECT_WORKDIR="${EXPECT_WORKDIR:-az://aletest/nf-work}"

# Resolve name -> id (accepts either).
CE_ID=$(curl -sS -H "Authorization: Bearer $TOWER_ACCESS_TOKEN" \
        "$API/compute-envs?workspaceId=$WORKSPACE_ID" \
      | python -c "
import sys,json
ref='$CE_REF'
for c in json.load(sys.stdin)['computeEnvs']:
    if ref in (c['name'], c['id']): print(c['id']); break")
: "${CE_ID:?no compute environment named or identified '$CE_REF' in workspace $WORKSPACE_ID}"

# ⚠️ The CE JSON goes to a temp FILE, not a pipe. `python -` reads its program from stdin,
# and the heredoc below already claims stdin — so a piped body would never reach json.load
# (it fails with "Expecting value: line 1 column 1"). Pass the path as argv instead.
TMP=$(mktemp); trap 'rm -f "$TMP"' EXIT
curl -sS -H "Authorization: Bearer $TOWER_ACCESS_TOKEN" \
     "$API/compute-envs/$CE_ID?workspaceId=$WORKSPACE_ID" > "$TMP"

python - "$TMP" "$CE_ID" "$EXPECT_WORKER_DISK" "$EXPECT_HEAD_DISK" "$EXPECT_NXF_VER" "$EXPECT_WORKDIR" <<'PY'
import sys, json
src, ce_id = sys.argv[1], sys.argv[2]
wdisk, hdisk, nxf, workdir = int(sys.argv[3]), int(sys.argv[4]), sys.argv[5], sys.argv[6]
c = json.load(open(src))['computeEnv']; g = c['config']; f = g.get('forge') or {}
head, worker = f.get('headPool') or {}, f.get('workerPool') or {}
bad = []

def chk(ok, msg):
    print(("  OK    " if ok else "  FAIL  ") + msg)
    if not ok: bad.append(msg)

print(f"{c['name']}  ({ce_id})  status={c['status']}")
chk(g.get('workDir') == workdir, f"workDir = {workdir} (got {g.get('workDir')})")
chk(any(e.get('name')=='NXF_VER' and e.get('value')==nxf and e.get('head')
        for e in (g.get('environment') or [])), f"NXF_VER={nxf} on the head job")

if f.get('dualPoolConfig'):
    chk(worker.get('bootDiskSizeGB')==wdisk, f"worker boot disk {wdisk} GB (got {worker.get('bootDiskSizeGB')})")
    chk(head.get('bootDiskSizeGB')==hdisk,   f"head boot disk {hdisk} GB (got {head.get('bootDiskSizeGB')})")
    # The expensive checks.
    for label, pool in (("head", head), ("worker", worker)):
        chk(pool.get('autoScale') is True,
            f"{label} pool autoScale is True (got {pool.get('autoScale')!r})")
else:
    chk(f.get('bootDiskSizeGB')==wdisk, f"boot disk {wdisk} GB (got {f.get('bootDiskSizeGB')})")
    chk(f.get('autoScale') is True, f"autoScale is True (got {f.get('autoScale')!r})")

print(f"  info  fusion2={g.get('fusion2Enabled')} wave={g.get('waveEnabled')} "
      f"dualPool={f.get('dualPoolConfig')}")

if bad:
    print("\n🚨 VERIFICATION FAILED — do not launch against this compute environment.")
    if any('autoScale' in b for b in bad):
        print("""
  autoScale is not enabled: the pools are FIXED SIZE and bill 24/7 regardless of load.
  Measured cost of this exact mistake: ~$2.75/hr compute plus ~$324/month of disks.

  1. Stop the billing now:
       az batch pool resize --pool-id tower-pool-<ce-id>-worker --target-dedicated-nodes 0
       az batch pool resize --pool-id tower-pool-<ce-id>-head   --target-dedicated-nodes 0
  2. CEs are immutable, so delete and recreate — deleting also disposes the pools and disks.
  3. Recreate with ./13_create_compute_env.sh <name> [--fusion]; plain `tw --dual-pool`
     omits autoScale unless you pass --head-no-auto-scale=false --worker-no-auto-scale=false.""")
    sys.exit(1)

print("\n✅ All checks passed.")
PY

echo
echo "Now confirm Azure agrees, and that the pools actually drain:"
echo "  az batch pool list --query \"[].{id:id,cur:currentDedicatedNodes,auto:enableAutoScale}\" -o table"
echo
echo "⚠️  A pool shows 1 node for its first ~5 minutes by design (the Forge autoscale formula"
echo "    pins the first interval). '0 nodes when idle, 15+ min after creation' is the real check."
