#!/usr/bin/env bash
# MUTATING. Grants the SP exactly two roles, each at a SINGLE RESOURCE scope.
#
#   Azure Batch Data Contributor  ->  batch account   aledev4test   (that account only)
#   Storage Blob Data Contributor ->  storage account aledata       (that account only)
#
# It does NOT grant anything at resource-group or subscription scope, and does not
# touch the other Batch accounts (anp, ale, aledevyeast, seqeracomputebatch) or any
# other storage account in rg-ALEdb.
#
# Idempotent: re-running is a no-op on already-existing assignments.
# Reversible: see 04_revoke_roles.sh.
#
# Run 01_preflight.sh first. Then:
#   ./02_grant_roles.sh 2>&1 | tee "logs/02_$(date -u +%Y%m%dT%H%M%SZ).log"

set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"
source ./00_vars.sh

grant() {
    local role="$1" scope="$2"
    echo
    echo "--- granting '$role'"
    echo "    at scope: $scope"
    az role assignment create \
        --assignee-object-id "$SP_OBJECT_ID" \
        --assignee-principal-type ServicePrincipal \
        --role "$role" \
        --scope "$scope" \
        --query '{role:roleDefinitionName, scope:scope, principalId:principalId}' -o json
}

echo "About to grant 2 per-resource roles to SP $SP_APP_ID."
read -r -p "Proceed? [y/N] " reply
[[ "$reply" == "y" || "$reply" == "Y" ]] || { echo "aborted"; exit 1; }

grant "$BATCH_ROLE"   "$BATCH_SCOPE"
grant "$STORAGE_ROLE" "$STORAGE_SCOPE"

echo
echo "=== resulting assignments for this SP (everywhere) ==="
az role assignment list --assignee "$SP_OBJECT_ID" --all \
    --query '[].{role:roleDefinitionName, scope:scope}' -o table

echo
echo "Expect EXACTLY the two rows above, both ending in a resource name."
echo "Any row whose scope ends at /resourceGroups/<name> is too broad — revoke it."
