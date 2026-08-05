#!/usr/bin/env bash
# MUTATING — rollback for 02_grant_roles.sh. Removes the two per-resource grants.
# Does not delete the SP, the app registration, or any client secret.
#
#   ./04_revoke_roles.sh 2>&1 | tee "logs/04_$(date -u +%Y%m%dT%H%M%SZ).log"

set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"
source ./00_vars.sh

revoke() {
    local role="$1" scope="$2"
    echo
    echo "--- revoking '$role' at $scope"
    az role assignment delete \
        --assignee "$SP_OBJECT_ID" \
        --role "$role" \
        --scope "$scope"
}

echo "About to REVOKE both role assignments from SP $SP_APP_ID."
read -r -p "Proceed? [y/N] " reply
[[ "$reply" == "y" || "$reply" == "Y" ]] || { echo "aborted"; exit 1; }

revoke "$BATCH_ROLE"   "$BATCH_SCOPE"
revoke "$STORAGE_ROLE" "$STORAGE_SCOPE"

echo
echo "=== remaining assignments for this SP (expect none) ==="
az role assignment list --assignee "$SP_OBJECT_ID" --all \
    --query '[].{role:roleDefinitionName, scope:scope}' -o table
