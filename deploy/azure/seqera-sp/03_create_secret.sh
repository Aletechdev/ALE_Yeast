#!/usr/bin/env bash
# MUTATING. Creates a client secret on the app registration and prints it ONCE.
#
# ⚠️ RUN THIS YOURSELF, IN YOUR OWN TERMINAL.
#    Do NOT run it through an agent/CI/tee — the secret is printed to stdout and
#    would be captured in a transcript or log file. That is why this is the one
#    script in this directory with no `| tee` in its usage line.
#
#   ./03_create_secret.sh
#
# Uses --append: existing credentials are KEPT. (Plain `az ad app credential reset`
# DELETES all existing secrets — that would break any other consumer mid-flight.)

set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"
source ./00_vars.sh

YEARS="${YEARS:-1}"

if [[ -n "${TEE_GUARD:-}" ]] || [[ ! -t 1 ]]; then
    echo "REFUSING: stdout is not a terminal — the secret would be written to a file or pipe." >&2
    echo "Run this directly in an interactive shell." >&2
    exit 1
fi

echo "Existing credentials on this app (will be kept):"
az ad app credential list --id "$SP_APP_ID" \
    --query '[].{keyId:keyId, hint:hint, end:endDateTime}' -o table

echo
echo "About to create a NEW client secret valid for $YEARS year(s) on '$SP_DISPLAY_NAME'."
read -r -p "Proceed? [y/N] " reply
[[ "$reply" == "y" || "$reply" == "Y" ]] || { echo "aborted"; exit 1; }

echo
echo "================= SECRET — SHOWN ONCE, COPY IT NOW ================="
az ad app credential reset \
    --id "$SP_APP_ID" \
    --append \
    --years "$YEARS" \
    --display-name "seqera-platform" \
    --query password -o tsv
echo "==================================================================="
echo
echo "Paste it straight into the Seqera Platform credential form."
echo "If it must persist: ~/.config/ale-seqera/sp.env, chmod 600, OUTSIDE this repo."
echo

echo "Record these in RUNBOOK.md (key id + expiry only, never the secret):"
az ad app credential list --id "$SP_APP_ID" \
    --query '[].{keyId:keyId, hint:hint, start:startDateTime, end:endDateTime}' -o table

echo
echo "Seqera credential form also needs (safe to read from 01_preflight logs):"
echo "  Tenant ID            : $TENANT_ID"
echo "  Client ID            : $SP_APP_ID"
echo "  Batch account name   : $BATCH_ACCOUNT"
echo "  Storage account name : $STORAGE_ACCOUNT"
