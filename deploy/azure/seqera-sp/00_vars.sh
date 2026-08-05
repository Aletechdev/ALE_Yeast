#!/usr/bin/env bash
# Shared variables for the Seqera service-principal scripts. Source, do not execute:
#   source ./00_vars.sh
#
# TWO RULES, both deliberate:
#
#   1. NO SECRETS. The client secret is never written here or anywhere in this tree.
#      Scripts read it from the environment ($AZURE_CLIENT_SECRET) if at all.
#
#   2. NO HARD-CODED IDs. Subscription / tenant / app / object GUIDs are RESOLVED AT
#      RUNTIME from resource names below. They are not secrets — you cannot authenticate
#      with them — but a committed file listing our subscription, batch account, storage
#      account and the exact SP authorized to write to them is a free targeting package,
#      and git history is permanent. Names in, GUIDs derived, nothing to leak or go stale.
#
# Everything below the "Resolved at runtime" line is computed. Do not paste GUIDs in.

# --- strictness, applied ONLY when executed, never when sourced --------------
# This file is meant to be `source`d. `set -euo pipefail` in a sourced file applies to
# the CALLING SHELL, so the next command that returns non-zero — a typo, a missing
# binary, a grep that finds nothing — kills the interactive terminal outright. That is
# not hypothetical: it closed a session with exit 127 when `nextflow` was not on PATH.
# Sourced: stay strict internally via explicit checks below, but leave the user's shell
# alone. Executed directly: full strictness.
if ! (return 0 2>/dev/null); then
    set -euo pipefail
fi

# _die works in both modes: `return` when sourced (keeps the shell alive), `exit` when run.
_die() { echo "FATAL: $*" >&2; return 1 2>/dev/null || exit 1; }

# --- required commands, checked up front with a useful message ---------------
# Failing here with an explanation beats failing later as a bare 127.
for _c in az; do
    command -v "$_c" >/dev/null 2>&1 || _die "'$_c' not found on PATH. Install the Azure CLI, or activate the environment that provides it."
done
unset _c

# ---------------------------------------------------------------------------
# Identity of the service principal — by DISPLAY NAME
#
# An app registration that was freed up when the ALE mutations service moved to
# its own separately-scoped SP; repurposed here for the Nextflow/Seqera Batch path.
# Override without editing this file:  export SP_DISPLAY_NAME=...
# ---------------------------------------------------------------------------
SP_DISPLAY_NAME="${SP_DISPLAY_NAME:-cfb_ale_mutations_pipeline}"

# ---------------------------------------------------------------------------
# Target resources — exactly two, each granted at its own resource scope.
# Never a resource group, never the subscription. See ../README.md.
# ---------------------------------------------------------------------------
BATCH_RG="${BATCH_RG:-rg-aledb}"
BATCH_ACCOUNT="${BATCH_ACCOUNT:-aledev4test}"
BATCH_ROLE="Azure Batch Data Contributor"

STORAGE_RG="${STORAGE_RG:-rg-ALEdb}"
STORAGE_ACCOUNT="${STORAGE_ACCOUNT:-aledata}"
STORAGE_ROLE="Storage Blob Data Contributor"

# ---------------------------------------------------------------------------
# Seqera Platform target — by org/workspace NAME, not numeric id (same rule as
# above: names in, ids resolved at runtime).
# ---------------------------------------------------------------------------
SEQERA_WORKSPACE="${SEQERA_WORKSPACE:-DTU-Biosustain/RECON-ALE}"
SEQERA_API="${SEQERA_API:-https://api.cloud.seqera.io}"

# ===========================================================================
# Resolved at runtime — nothing below this line is committed as a literal
# ===========================================================================

# --- subscription / tenant, from the active az login -----------------------
SUBSCRIPTION_ID="$(az account show --query id       -o tsv)" || _die "not logged in (az login)"
TENANT_ID="$(      az account show --query tenantId -o tsv)"

# --- the SP, by display name; must match exactly one -----------------------
_sp_matches="$(az ad sp list --display-name "$SP_DISPLAY_NAME" \
                 --query "[?displayName=='$SP_DISPLAY_NAME'].{appId:appId,id:id}" -o tsv)"
_sp_count="$(printf '%s\n' "$_sp_matches" | grep -c . || true)"
[[ "$_sp_count" == "1" ]] || _die "expected exactly 1 SP named '$SP_DISPLAY_NAME', found $_sp_count"

SP_APP_ID="$(   printf '%s' "$_sp_matches" | cut -f1)"   # Application (client) ID
SP_OBJECT_ID="$(printf '%s' "$_sp_matches" | cut -f2)"   # SP object ID — use this for RBAC
SP_APP_OBJECT_ID="$(az ad app show --id "$SP_APP_ID" --query id -o tsv)"  # app reg — for credentials
unset _sp_matches _sp_count

# --- scopes, resolved from Azure so a typo fails loudly --------------------
BATCH_SCOPE="$(  az batch account   show -g "$BATCH_RG"   -n "$BATCH_ACCOUNT"   --query id -o tsv)"
STORAGE_SCOPE="$(az storage account show -g "$STORAGE_RG" -n "$STORAGE_ACCOUNT" --query id -o tsv)"

# --- guard: a scope must name a specific resource --------------------------
# Anything shorter is a resource-group- or subscription-wide grant.
for _v in BATCH_SCOPE STORAGE_SCOPE; do
    [[ "${!_v}" == */providers/*/* ]] || \
        _die "$_v is not a single-resource scope: '${!_v}' — refusing to continue"
done
unset _v

# --- convenience exports under the standard Azure env-var names --------------
# So `source 00_vars.sh` is enough to run conf/azure_batch.config and
# bin/test_ottilie_azure_batch.sh — no manual re-exporting.
# These are IDENTIFIERS, not secrets. AZURE_CLIENT_SECRET is deliberately NOT set
# here and never will be: it is read interactively (`read -rs`) so it stays out of
# shell history and out of this repo.
export AZURE_CLIENT_ID="$SP_APP_ID"
export AZURE_TENANT_ID="$TENANT_ID"
export AZURE_BATCH_ACCOUNT="$BATCH_ACCOUNT"
export AZURE_STORAGE_ACCOUNT="$STORAGE_ACCOUNT"

# --- optional: pick up secrets from OUTSIDE the repo -------------------------
# Created by 10_store_secret.sh at ~/.config/ale-seqera/sp.env (mode 600). Loading it
# here means no later script needs an interactive `read -rs`, which has no prompt and
# no echo and therefore hangs silently wherever there is no real TTY.
# The secrets are still never stored in, or read from, this repository.
#
# The file now holds TWO independent secrets:
#   AZURE_CLIENT_SECRET  — the service principal (Azure Batch + Blob)
#   TOWER_ACCESS_TOKEN / SEQERA_ACCESS_TOKEN — Seqera Platform API (same value, two names:
#                          `tw` reads the first, the `seqera` AI CLI reads the second)
#
# ⚠️ The guard below tests BOTH. It used to test only AZURE_CLIENT_SECRET, which meant a
# shell that already had the Azure secret exported would skip the file entirely and
# silently never load the Seqera token.
_secret_file="${SECRET_FILE:-$HOME/.config/ale-seqera/sp.env}"
if [[ ( -z "${AZURE_CLIENT_SECRET:-}" || -z "${TOWER_ACCESS_TOKEN:-}" ) && -r "$_secret_file" ]]; then
    _perm="$(stat -c '%a' "$_secret_file" 2>/dev/null || echo '?')"
    if [[ "$_perm" != "600" && "$_perm" != "400" ]]; then
        echo "  ⚠️  $_secret_file is mode $_perm — expected 600. Fix: chmod 600 '$_secret_file'" >&2
    fi
    set -a; . "$_secret_file"; set +a
fi
unset _secret_file _perm

# --- summary: names and truncated ids, so transcripts in logs/ stay tame ------
# The TRUNCATION IS DISPLAY-ONLY. The variables above hold full 36-char GUIDs;
# `${#SP_APP_ID}` is 36. Do not re-type an id from this output.
_short() { printf '%s…' "${1:0:8}"; }
echo "vars loaded (ids shown truncated — the variables hold full values):"
echo "  subscription : $(_short "$SUBSCRIPTION_ID")  tenant: $(_short "$TENANT_ID")"
echo "  SP           : $SP_DISPLAY_NAME  app $(_short "$SP_APP_ID")  obj $(_short "$SP_OBJECT_ID")"
echo "  batch        : $BATCH_ACCOUNT ($BATCH_RG)     <- $BATCH_ROLE"
echo "  storage      : $STORAGE_ACCOUNT ($STORAGE_RG) <- $STORAGE_ROLE"
echo "  exported     : AZURE_CLIENT_ID, AZURE_TENANT_ID, AZURE_BATCH_ACCOUNT, AZURE_STORAGE_ACCOUNT"
if [[ -n "${AZURE_CLIENT_SECRET:-}" ]]; then
    echo "  secret       : loaded (${#AZURE_CLIENT_SECRET} chars) — ready to run"
else
    echo "  secret       : NOT set. Run ./10_store_secret.sh once (stores it outside the repo),"
    echo "                 or for this shell only: read -rsp 'secret: ' AZURE_CLIENT_SECRET && export AZURE_CLIENT_SECRET"
fi
if [[ -n "${TOWER_ACCESS_TOKEN:-}" ]]; then
    echo "  seqera token : loaded (${#TOWER_ACCESS_TOKEN} chars) — tw + seqera CLI ready"
else
    echo "  seqera token : NOT set. Needed for Phase 4/6 (tw compute-envs, tw launch)."
    echo "                 Add TOWER_ACCESS_TOKEN=<token> to $HOME/.config/ale-seqera/sp.env (mode 600)."
fi
