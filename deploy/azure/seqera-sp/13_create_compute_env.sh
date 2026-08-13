#!/usr/bin/env bash
# Create a dual-pool Azure Batch compute environment FROM CODE, with autoscaling on.
#
#   ./13_create_compute_env.sh <new-ce-name> [--fusion]
#   ./13_create_compute_env.sh <new-ce-name> --delete      # tear a throwaway back down
#
# 🚨 WHY NOT `tw compute-envs add azure-batch forge --dual-pool`.
#
# Left to its defaults that command OMITS `headPool.autoScale` / `workerPool.autoScale` from the
# request, which Platform stores as null and Azure builds as `enableAutoScale: False` —
# FIXED-SIZE pools billing 24/7. It reports success. Measured cost of that mistake on
# 2026-08-07: ~$2.75/hr compute + ~$324/month of disks. Upstream: seqeralabs/tower-cli#658,
# fix in #659 (unmerged as of 2026-08-11, latest release 0.38.0).
#
# ⚠️ It is NOT true that the CLI cannot express autoscale. `--head-no-auto-scale=false
#    --worker-no-auto-scale=false` — explicit `=false`, undocumented in `--help` — does emit
#    `autoScale: true` (verified 2026-08-11 by inspecting the request payload). That is an
#    escape hatch for a one-off, not the route taken here.
#
# ➡️  This script uses `tw compute-envs import`, which posts a config JSON verbatim. Two reasons
#     it beats the flag route even now that the flags work:
#
#     1. `add ... forge` HAS NO FLAGS for `jobMaxWallClockTime`, `deleteJobsOnCompletion`,
#        `deleteTasksOnCompletion` or `terminateJobsOnCompletion`, so a CE built from flags
#        silently takes Platform defaults for all four — our CEs pin `7d` / `never`.
#     2. The template is a READBACK of a working CE (ce_import_template.json), so every field
#        is one Platform itself wrote, not a hand-guessed payload. `=false` depends on
#        undocumented option parsing that #659 is actively rewriting.
#
# Why import and not the raw REST API: `tw` validates its arguments; the Seqera API does not
# (a bogus `discriminator` was accepted with HTTP 200, then failed obscurely at launch).
#
# ⚠️ Compute environments are IMMUTABLE. A wrong setting cannot be patched, only deleted and
#    recreated — so this script always runs 12_verify_compute_env.sh before it returns.
#
# ⚠️ Creating a CE costs a few node-minutes: the Forge autoscale formula pins the first
#    interval, so a new pool runs 1 node for ~5 minutes no matter what. `1 + 1` right after
#    creation is normal. `0 + 0` fifteen minutes later is the proof that autoscale works.
#
# House rules honoured: the credential and the workspace are referenced BY NAME and resolved
# by `tw` at runtime; no ids and no secrets live in this tree.

set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

CE_NAME="${1:?usage: $0 <new-ce-name> [--fusion|--delete]}"
MODE="${2:-}"

TEMPLATE="${TEMPLATE:-ce_import_template.json}"
WORKSPACE="${SEQERA_WORKSPACE:-DTU-Biosustain/RECON-ALE}"
# The credential name predates the SP's 2026-08-13 rename and is kept deliberately —
# it binds by clientId, so the old name stays functional. See RUNBOOK.md.
CREDENTIAL="${SEQERA_CREDENTIAL:-azure_SP_cfb_ale_mutations_pipeline}"

# Token only — unlike 00_vars.sh this needs no `az login`, since everything here is Seqera-side.
SECRET_FILE="${SECRET_FILE:-$HOME/.config/ale-seqera/sp.env}"
if [[ -z "${TOWER_ACCESS_TOKEN:-}" && -r "$SECRET_FILE" ]]; then
    set -a; . "$SECRET_FILE"; set +a
fi
: "${TOWER_ACCESS_TOKEN:?TOWER_ACCESS_TOKEN not set — see 10_store_secret.sh}"

if [[ "$MODE" == "--delete" ]]; then
    echo "Deleting compute environment '$CE_NAME' (disposes its pools AND their disks)…"
    tw compute-envs delete -n "$CE_NAME" -w "$WORKSPACE" --wait
    exit 0
fi

[[ -r "$TEMPLATE" ]] || { echo "FATAL: template '$TEMPLATE' not readable" >&2; exit 1; }

# Fusion is the ONLY axis this script varies: two booleans in an otherwise verbatim template.
# ⚠️ The template no longer carries NXF_VER (removed 2026-08-12): the engine pin lives on the
# Launchpad entry's Nextflow-version field instead, so it travels with the pipeline rather than
# with the compute resources. A launch that does not come from such an entry gets Platform's
# default engine — and 26.x cannot parse nextflow.config.
# Everything else (workDir, VM types, disk sizes, autoScale) is deliberately fixed —
# each of those values was established by running it, see docs/dev-practices/azure_batch_execution.md.
FUSION=false
[[ "$MODE" == "--fusion" ]] && FUSION=true

TMP=$(mktemp --suffix=.json); trap 'rm -f "$TMP"' EXIT
python - "$TEMPLATE" "$TMP" "$FUSION" <<'PY'
import json, sys
src, dst, fusion = sys.argv[1], sys.argv[2], sys.argv[3] == "true"
cfg = json.load(open(src))
cfg["fusion2Enabled"] = fusion
cfg["waveEnabled"] = fusion          # Fusion needs Wave; without Fusion, neither is used.
pools = cfg.get("forge", {})
for p in ("headPool", "workerPool"):
    # Fail loudly rather than create the expensive mistake the template exists to prevent.
    if (pools.get(p) or {}).get("autoScale") is not True:
        sys.exit(f"FATAL: template {src} has {p}.autoScale != true — refusing to create a fixed-size CE")
json.dump(cfg, open(dst, "w"), indent=2)
print(f"  config prepared: dualPool={pools.get('dualPoolConfig')} fusion={fusion} "
      f"head={pools['headPool']['vmType']}/{pools['headPool']['bootDiskSizeGB']}GB "
      f"worker={pools['workerPool']['vmType']}/{pools['workerPool']['bootDiskSizeGB']}GB")
PY

echo
echo "Creating '$CE_NAME' in $WORKSPACE with credential '$CREDENTIAL'…"
tw compute-envs import -n "$CE_NAME" -w "$WORKSPACE" -c "$CREDENTIAL" --wait AVAILABLE "$TMP"

echo
echo "=== verifying (import is not proof — the API does not validate payloads) ==="
SEQERA_WORKSPACE_ID="${SEQERA_WORKSPACE_ID:-}" ./12_verify_compute_env.sh "$CE_NAME"

echo
echo "Still to confirm, ~15 minutes from now — that the pools actually DRAIN:"
echo "  az batch pool list --account-name aledev4test \\"
echo "      --query \"[].{id:id,cur:currentDedicatedNodes,auto:enableAutoScale}\" -o table"
echo "  (1 + 1 immediately after creation is by design; 0 + 0 when idle is the real check.)"
echo
echo "Throwaway? Delete it — that also disposes the pools and their disks:"
echo "  ./13_create_compute_env.sh $CE_NAME --delete"
