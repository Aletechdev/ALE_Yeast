#!/usr/bin/env bash
# Proves the two per-resource roles are ACTUALLY SUFFICIENT — and actually limited —
# by authenticating as the SP and exercising the real data planes. Run this before
# wiring the credential into Seqera, so a permissions problem surfaces here rather
# than as an opaque Azure error inside a Batch head job.
#
# Requires the client secret in the environment (never on disk in this repo):
#   read -rs AZURE_CLIENT_SECRET && export AZURE_CLIENT_SECRET
#   ./05_verify_sp_access.sh 2>&1 | tee "logs/05_$(date -u +%Y%m%dT%H%M%SZ).log"
#
# The SP login is isolated in a temp AZURE_CONFIG_DIR, so your own `az` session is
# untouched and the SP token is discarded on exit.

set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"
source ./00_vars.sh

if [[ -z "${AZURE_CLIENT_SECRET:-}" ]]; then
    cat >&2 <<'EOF'
AZURE_CLIENT_SECRET is not set. This is a setup step, not a failure.

Run these two commands in THIS shell, then re-run the script:

    read -rs AZURE_CLIENT_SECRET && export AZURE_CLIENT_SECRET
    ./05_verify_sp_access.sh 2>&1 | tee "logs/05_$(date -u +%Y%m%dT%H%M%SZ).log"

The `read -rs` form is deliberate: it reads silently (nothing echoes to the screen)
and, unlike `export AZURE_CLIENT_SECRET=...`, keeps the secret out of your shell
history. Paste the value at the blank prompt and press Enter.

The variable lives only in this shell — it is gone when you close the terminal, and
`unset AZURE_CLIENT_SECRET` clears it sooner.

If you no longer have the secret from 03_create_secret.sh, it cannot be retrieved;
re-run 03 to append a second one (the existing credential is preserved), then note
the new key id in RUNBOOK.md.
EOF
    exit 1
fi

# Container to probe read/write in. Defaults to the Nextflow work-dir container the
# existing compute environment uses (az://debugging). Containers on this account:
#   aledata aledb aletest data debugging images output pipeline reference
PROBE_CONTAINER="${PROBE_CONTAINER:-debugging}"

SP_CFG="$(mktemp -d)"
cleanup() { AZURE_CONFIG_DIR="$SP_CFG" az logout >/dev/null 2>&1 || true; rm -rf "$SP_CFG"; }
trap cleanup EXIT
export AZURE_CONFIG_DIR="$SP_CFG"

pass() { echo "  ✅ $*"; }
fail() { echo "  ❌ $*"; FAILED=1; }
FAILED=0

echo "=== 0. authenticate as the SP ==="
az login --service-principal \
    -u "$SP_APP_ID" -p "$AZURE_CLIENT_SECRET" --tenant "$TENANT_ID" \
    --allow-no-subscriptions >/dev/null
pass "SP authenticated (secret is valid)"

echo
echo "=== 1. POSITIVE: Batch data plane on $BATCH_ACCOUNT ==="
if az batch account login -g "$BATCH_RG" -n "$BATCH_ACCOUNT" >/dev/null 2>&1 \
   && az batch pool list --query 'length(@)' -o tsv >/dev/null 2>&1; then
    pass "can list pools via AAD — Azure Batch Data Contributor is working"
else
    fail "cannot reach the Batch data plane (Seqera will not be able to create pools)"
fi

echo
echo "=== 2. POSITIVE: Blob data plane on $STORAGE_ACCOUNT ==="
if az storage container list --account-name "$STORAGE_ACCOUNT" --auth-mode login \
       --query '[].name' -o tsv >/dev/null 2>&1; then
    pass "can list containers"
else
    fail "cannot list containers — Storage Blob Data Contributor not effective"
fi

echo
echo "=== 3. POSITIVE: blob write/read/delete in '$PROBE_CONTAINER' (the work dir) ==="
PROBE="_sp_access_probe.txt"
TMPF="$(mktemp)"; echo "seqera sp access probe" > "$TMPF"
if az storage blob upload --account-name "$STORAGE_ACCOUNT" --auth-mode login \
       -c "$PROBE_CONTAINER" -n "$PROBE" -f "$TMPF" --overwrite >/dev/null 2>&1; then
    pass "upload"
    az storage blob download --account-name "$STORAGE_ACCOUNT" --auth-mode login \
        -c "$PROBE_CONTAINER" -n "$PROBE" -f /dev/null >/dev/null 2>&1 \
        && pass "download" || fail "download"
    az storage blob delete --account-name "$STORAGE_ACCOUNT" --auth-mode login \
        -c "$PROBE_CONTAINER" -n "$PROBE" >/dev/null 2>&1 \
        && pass "delete (cleaned up)" || fail "delete — probe blob may be left behind"
else
    fail "upload failed — check the container '$PROBE_CONTAINER' exists (override with PROBE_CONTAINER=)"
fi
rm -f "$TMPF"

echo
echo "=== 4. NEGATIVE: confirm the grant is actually LIMITED ==="
echo "    (these SHOULD fail — a success means the scope is too broad)"

if az batch account login -g "$BATCH_RG" -n "ale" >/dev/null 2>&1 \
   && az batch pool list --query 'length(@)' -o tsv >/dev/null 2>&1; then
    fail "SP can reach the 'ale' Batch account — scope is TOO BROAD, investigate"
else
    pass "cannot reach the 'ale' Batch account (correctly out of scope)"
fi

if az storage container list --account-name "aleprojectdata" --auth-mode login \
       --query '[].name' -o tsv >/dev/null 2>&1; then
    fail "SP can read storage account 'aleprojectdata' — scope is TOO BROAD, investigate"
else
    pass "cannot read 'aleprojectdata' (correctly out of scope)"
fi

if az group show -n "$STORAGE_RG" >/dev/null 2>&1; then
    fail "SP can read the resource group — an RG-scoped assignment exists, investigate"
else
    pass "cannot read the resource group (no RG-wide grant)"
fi

echo
if [[ "$FAILED" == "0" ]]; then
    echo "=== ALL CHECKS PASSED — least privilege is both sufficient and limited ==="
else
    echo "=== SOME CHECKS FAILED (see ❌ above) — do not wire Seqera until resolved ==="
    exit 1
fi
