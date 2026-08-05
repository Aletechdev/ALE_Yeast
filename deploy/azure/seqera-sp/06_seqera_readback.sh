#!/usr/bin/env bash
# READ-ONLY. Confirms the Entra credential registered in Seqera and reads its SCHEMA back.
#
# Why this exists: plan Phase 3 says create the FIRST credential in the web UI, because the
# Seqera credentials API accepts unvalidated payloads — a guessed field name saves cleanly
# (HTTP 200) and then fails obscurely at launch. Once the UI has created a known-good one,
# reading it back gives the real key names + provider discriminator, which turns future
# creation and rotation into a scriptable operation instead of a guess.
#
# Secret values come back REDACTED by the API — expected. We want the shape, not the values.
#
# Needs a Seqera token in the environment (never on disk in this repo):
#   read -rs TOWER_ACCESS_TOKEN && export TOWER_ACCESS_TOKEN
#   ./06_seqera_readback.sh 2>&1 | tee "logs/06_$(date -u +%Y%m%dT%H%M%SZ).log"

set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"
source ./00_vars.sh

if [[ -z "${TOWER_ACCESS_TOKEN:-}" ]]; then
    cat >&2 <<'EOF'
TOWER_ACCESS_TOKEN is not set. This is a setup step, not a failure.

Run these two commands in THIS shell, then re-run the script:

    read -rs TOWER_ACCESS_TOKEN && export TOWER_ACCESS_TOKEN
    ./06_seqera_readback.sh 2>&1 | tee "logs/06_$(date -u +%Y%m%dT%H%M%SZ).log"

`read -rs` reads silently and keeps the token out of your shell history.
Create a token at: Seqera Platform -> your avatar -> Access tokens.
EOF
    exit 1
fi

TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT

# NOTE: python is invoked with -c (program as an argument) so that stdin stays
# free for the JSON being piped in. `python - <<'PY'` would make python read its
# PROGRAM from stdin, colliding with the data.

echo "=== 1. platform / identity ==="
tw info 2>&1 | grep -iE 'version|user' || true

echo
echo "=== 2. resolve workspace '$SEQERA_WORKSPACE' ==="
# `-o json` is a GLOBAL tw option and must precede the subcommand; `tw workspaces
# list -o json` would bind -o to that subcommand's --organization instead.
tw -o json workspaces list > "$TMP/ws.json"

read -r -d '' RESOLVE <<'PY' || true
import json, sys
want = sys.argv[1].strip().lower()
rows = json.load(sys.stdin).get("workspaces", [])
for w in rows:
    if f"{w.get('orgName','')}/{w.get('workspaceName','')}".lower() == want:
        print(w["workspaceId"]); break
else:
    sys.stderr.write("visible workspaces:\n")
    for w in rows:
        sys.stderr.write(f"  {w.get('orgName')}/{w.get('workspaceName')}\n")
PY

WS_ID="$(python -c "$RESOLVE" "$SEQERA_WORKSPACE" < "$TMP/ws.json")"
[[ -n "$WS_ID" ]] || { echo "FATAL: workspace '$SEQERA_WORKSPACE' not found for this token" >&2; exit 1; }
echo "  -> workspace id $WS_ID"

echo
echo "=== 3. credentials in this workspace ==="
tw credentials list -w "$SEQERA_WORKSPACE" 2>&1 || true

echo
echo "=== 4. AZURE credential SCHEMA (values redacted by the API) ==="
echo "    Record the key names + provider discriminator in RUNBOOK.md."
curl -sS -H "Authorization: Bearer $TOWER_ACCESS_TOKEN" \
     "$SEQERA_API/credentials?workspaceId=$WS_ID" > "$TMP/creds.json"

read -r -d '' SHOW <<'PY' || true
import json, sys
try:
    creds = json.load(sys.stdin).get("credentials", [])
except Exception as e:
    print("could not parse API response:", e); sys.exit(0)

az = [c for c in creds if (c.get("provider") or "").lower().startswith("azure")]
if not az:
    print("No azure-provider credential in this workspace.")
    print("Providers present:", sorted({c.get("provider") for c in creds}))
    sys.exit(0)

for c in az:
    print(f"\n  name       : {c.get('name')}")
    print(f"  provider   : {c.get('provider')}      <-- the discriminator")
    print(f"  description: {c.get('description')}")
    keys = c.get("keys") or {}
    print(f"  key names  : {sorted(keys)}")
    for k, v in sorted(keys.items()):
        if v in (None, ""):
            # The API returns null for every secret field, so null is ambiguous:
            # it means "unset" OR "set but withheld". Do not read it as "empty".
            state = "<null — withheld by API; unset and set-but-secret look identical>"
        else:
            state = f"{v!r}  (non-secret, returned in clear)"
        print(f"      {k:26s} = {state}")
PY

python -c "$SHOW" < "$TMP/creds.json"

echo
echo "=== 5. compute environments in this workspace ==="
tw compute-envs list -w "$SEQERA_WORKSPACE" 2>&1 || true

echo
echo "read-only; nothing was created or modified."
