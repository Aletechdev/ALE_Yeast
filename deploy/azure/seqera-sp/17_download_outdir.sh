#!/usr/bin/env bash
# Download a run's outdir from blob storage for a local comparison, using the pipeline's OWN service
# principal — so it works when the az CLI user login has expired (the tenant's 14-day sign-in policy
# did exactly that on 2026-09-28, mid-comparison).
#
#   ./17_download_outdir.sh az://aletest/seqera-runs/yAMP-qc-first-20260928 /path/to/dest
#     -> files at /path/to/dest/seqera-runs/yAMP-qc-first-20260928/..., .azure_blob_dir markers removed
#
# Credentials: the client and tenant id are read at run time from the workspace's Azure credential
# record (Platform returns those, never the secret); the secret comes from ~/.config/ale-seqera/sp.env.
# azcopy auto-logs in per invocation (SPN) and writes nothing to the az CLI's login state. The storage
# account is AZURE_STORAGE_ACCOUNT (default aledata); the container is the host part of the az:// URI.
# Read-only: the SP's Storage Blob Data Contributor role is used for a download only.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

WORKSPACE="${SEQERA_WORKSPACE:-DTU-Biosustain/RECON-ALE}"
CRED_NAME="${SEQERA_AZURE_CREDENTIAL:-azure_SP_cfb_ale_mutations_pipeline}"
STORAGE_ACCOUNT="${AZURE_STORAGE_ACCOUNT:-aledata}"
API="${SEQERA_API:-https://api.cloud.seqera.io}"

SECRET_FILE="${SECRET_FILE:-$HOME/.config/ale-seqera/sp.env}"
if { [[ -z "${TOWER_ACCESS_TOKEN:-}" ]] || [[ -z "${AZURE_CLIENT_SECRET:-}" ]]; } && [[ -r "$SECRET_FILE" ]]; then
    set -a; . "$SECRET_FILE"; set +a
fi
: "${TOWER_ACCESS_TOKEN:?TOWER_ACCESS_TOKEN not set — see 10_store_secret.sh}"
: "${AZURE_CLIENT_SECRET:?AZURE_CLIENT_SECRET not set — see 10_store_secret.sh}"

uri=${1:?usage: $0 az://<container>/<prefix> <dest>}; dest=${2:?usage: $0 az://<container>/<prefix> <dest>}
[[ "$uri" == az://*/* ]] || { echo "FATAL: expected az://<container>/<prefix>, got '$uri'" >&2; exit 2; }
rest=${uri#az://}; container=${rest%%/*}; prefix=${rest#*/}; prefix=${prefix%/}
[[ -n "$prefix" ]] || { echo "FATAL: refusing to download a whole container" >&2; exit 2; }

WS_ID=$(tw -o json workspaces list | python -c "
import json, sys
want = '$WORKSPACE'.lower()
for w in json.load(sys.stdin)['workspaces']:
    if f\"{w['orgName']}/{w['workspaceName']}\".lower() == want: print(w['workspaceId']); break")
: "${WS_ID:?workspace '$WORKSPACE' not found}"
CRED_ID=$(tw -o json credentials list -w "$WORKSPACE" | python -c "
import json, sys
for c in json.load(sys.stdin)['credentials']:
    if c['name'] == '$CRED_NAME': print(c['id']); break")
: "${CRED_ID:?credential '$CRED_NAME' not found in $WORKSPACE}"
cred=$(curl -sS -H "Authorization: Bearer $TOWER_ACCESS_TOKEN" "$API/credentials/$CRED_ID?workspaceId=$WS_ID")
AZCOPY_SPA_APPLICATION_ID=$(python -c 'import json,sys; print(json.load(sys.stdin)["credentials"]["keys"]["clientId"])' <<<"$cred")
AZCOPY_TENANT_ID=$(python -c 'import json,sys; print(json.load(sys.stdin)["credentials"]["keys"]["tenantId"])' <<<"$cred")
export AZCOPY_AUTO_LOGIN_TYPE=SPN AZCOPY_SPA_APPLICATION_ID AZCOPY_TENANT_ID AZCOPY_SPA_CLIENT_SECRET="$AZURE_CLIENT_SECRET"

mkdir -p "$dest/$prefix"
azcopy copy "https://$STORAGE_ACCOUNT.blob.core.windows.net/$container/$prefix/*" "$dest/$prefix" \
       --recursive --output-level=essential --log-level=ERROR >/dev/null
find "$dest/$prefix" -name '.azure_blob_dir' -delete
echo "$(find "$dest/$prefix" -type f | wc -l) files -> $dest/$prefix"
