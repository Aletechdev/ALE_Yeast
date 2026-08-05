#!/usr/bin/env bash
# READ-ONLY. Answers three questions before anything is changed:
#   1. Who am I, and can I actually assign roles at the two target scopes?
#      (needs Owner or User Access Administrator ON THAT SCOPE — Contributor cannot
#       assign roles, and the storage work found this identity is "Contributor
#       without deletes" in places.)
#   2. What does the SP have today — credentials and role assignments?
#   3. Do the two roles even exist by the names in 00_vars.sh?
#
# Run:  ./01_preflight.sh 2>&1 | tee "logs/01_$(date -u +%Y%m%dT%H%M%SZ).log"

set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"
source ./00_vars.sh

hr() { printf '\n=== %s ===\n' "$1"; }

hr "1a. signed-in identity"
az ad signed-in-user show --query '{upn:userPrincipalName, id:id}' -o json
ME_ID="$(az ad signed-in-user show --query id -o tsv)"

hr "1b. my role assignments AT OR ABOVE the batch scope"
az role assignment list --assignee "$ME_ID" --scope "$BATCH_SCOPE" --include-inherited \
    --query '[].{role:roleDefinitionName, scope:scope}' -o table

hr "1c. my role assignments AT OR ABOVE the storage scope"
az role assignment list --assignee "$ME_ID" --scope "$STORAGE_SCOPE" --include-inherited \
    --query '[].{role:roleDefinitionName, scope:scope}' -o table

echo
echo "^ To create role assignments you need Owner or User Access Administrator in the"
echo "  lists above. Plain Contributor is NOT enough — if that is all you see, this needs"
echo "  a subscription admin (plan Phase 1.2)."

hr "2a. SP credentials today (expect: none)"
az ad app credential list --id "$SP_APP_ID" \
    --query '[].{keyId:keyId, hint:hint, start:startDateTime, end:endDateTime}' -o table

hr "2b. SP role assignments today, everywhere (expect: none)"
az role assignment list --assignee "$SP_OBJECT_ID" --all \
    --query '[].{role:roleDefinitionName, scope:scope}' -o table

hr "3. target role definitions resolve"
for role in "$BATCH_ROLE" "$STORAGE_ROLE"; do
    printf '%-32s -> ' "$role"
    az role definition list --name "$role" --query '[0].name' -o tsv 2>/dev/null || echo "NOT FOUND"
done

hr "4. batch account auth modes (Seqera needs the account itself provisioned normally)"
az batch account show -g "$BATCH_RG" -n "$BATCH_ACCOUNT" \
    --query '{name:name, poolAllocationMode:poolAllocationMode, allowedAuthModes:allowedAuthenticationModes, autoStorage:autoStorage.storageAccountId}' -o json

hr "preflight complete"
echo "Nothing was modified. Record the outcome in RUNBOOK.md before running 02."
