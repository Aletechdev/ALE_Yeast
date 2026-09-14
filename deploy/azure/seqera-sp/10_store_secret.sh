#!/usr/bin/env bash
# Stores the two cloud secrets ONCE in an out-of-repo file, so nothing afterwards needs
# an interactive prompt:
#
#   AZURE_CLIENT_SECRET   service principal (Azure Batch + Blob)   — from 03_create_secret.sh
#   TOWER_ACCESS_TOKEN    Seqera Platform API token                — cloud.seqera.io → Your tokens
#   SEQERA_ACCESS_TOKEN   same value as TOWER_ACCESS_TOKEN (the `seqera` AI CLI reads this name;
#                         tw reads ONLY TOWER_ACCESS_TOKEN — verified 2026-08-04, keep both)
#
# WHY: `read -rs VAR` prints no prompt and echoes nothing. In a real terminal that is fine;
# in a VS Code task, a pasted block, a tmux send-keys, or an agent shell there is no TTY to
# type into, so it blocks silently until the session times out — which looks like a crash
# rather than "waiting for input". Storing the secrets once removes that failure mode from
# every later script.
#
# The file lives OUTSIDE the repo at ~/.config/ale-seqera/sp.env, mode 600. The repo's
# .gitignore blocks *.env anyway, but the rule is "not in the tree" — this honours it.
#
#   ./10_store_secret.sh          # run once per machine, in a real terminal
#
# Each prompt accepts Enter to KEEP the value already in the file (so rotating one secret
# does not mean re-pasting the other). Afterwards:
#   - `source 00_vars.sh` picks up both secrets (bin/test_ottilie_azure_batch.sh just works);
#   - the ~/.bashrc snippet from docs/usage/new_machine_setup.md exports ONLY the Tower token
#     into every shell, so `tw` / `seqera` work without sourcing anything.
#
# To rotate the SP secret : re-run 03_create_secret.sh, then re-run this (Enter at the token prompt).
# To rotate the token     : mint a new one on cloud.seqera.io, re-run this (Enter at the secret prompt).
# To revoke               : rm ~/.config/ale-seqera/sp.env  (and delete the credentials upstream)

set -euo pipefail

SECRET_FILE="${SECRET_FILE:-$HOME/.config/ale-seqera/sp.env}"

if [[ ! -t 0 ]]; then
    cat >&2 <<EOT
REFUSING: stdin is not a terminal, so there is nothing to type into — this is exactly
the situation that hangs. Run this in a real interactive shell.

If you genuinely have no TTY, write the file yourself instead (prefix with a space if
your shell records history):

    mkdir -p "$(dirname "$SECRET_FILE")" && chmod 700 "$(dirname "$SECRET_FILE")"
    printf 'AZURE_CLIENT_SECRET=%s\nTOWER_ACCESS_TOKEN=%s\nSEQERA_ACCESS_TOKEN=%s\n' \\
        '<sp-secret>' '<tower-token>' '<tower-token>' > "$SECRET_FILE"
    chmod 600 "$SECRET_FILE"
EOT
    exit 1
fi

mkdir -p "$(dirname "$SECRET_FILE")"
chmod 700 "$(dirname "$SECRET_FILE")"

# Existing values, so Enter can keep them.
_read_key() { sed -n -e "s/^$1=//p" "$SECRET_FILE" 2>/dev/null | sed -e 's/^["'"'"']//' -e 's/["'"'"']$//' | head -1; }
OLD_SECRET=""; OLD_TOKEN=""
if [[ -f "$SECRET_FILE" ]]; then
    OLD_SECRET="$(_read_key AZURE_CLIENT_SECRET)"
    OLD_TOKEN="$(_read_key TOWER_ACCESS_TOKEN)"
    echo "Existing $SECRET_FILE: SP secret $([[ -n "$OLD_SECRET" ]] && echo "present (${#OLD_SECRET} chars)" || echo absent)," \
         "Seqera token $([[ -n "$OLD_TOKEN" ]] && echo "present (${#OLD_TOKEN} chars)" || echo absent)."
    echo "Press Enter at a prompt to keep the existing value."
fi

# -p gives a VISIBLE prompt (the missing piece in the bare `read -rs` form) and -t caps
# the wait so this can never hold a session open indefinitely. Nothing echoes — that is
# expected, not a hang. Ctrl-C to abort.
_ask() {   # _ask <label> <old-value>  → prints the value to use
    local v
    if ! read -rsp "$1: " -t 300 v; then
        echo >&2; echo "Timed out after 300s with no input. Nothing was written." >&2; exit 1
    fi
    echo >&2
    [[ -n "$v" ]] && printf '%s' "$v" || printf '%s' "$2"
}

echo
SECRET="$(_ask 'Azure SP client secret (from 03_create_secret.sh)' "$OLD_SECRET")"
TOKEN="$(_ask  'Seqera Platform token (cloud.seqera.io → Your tokens)' "$OLD_TOKEN")"

[[ -n "$SECRET" || -n "$TOKEN" ]] || { echo "Both empty — nothing written." >&2; exit 1; }
[[ -n "$SECRET" ]] || echo "note: no SP secret — Azure Batch runs will prompt; re-run this after 03_create_secret.sh" >&2
[[ -n "$TOKEN"  ]] || echo "note: no Seqera token — tw / seqera CLI stay unauthenticated" >&2

umask 077
{
    echo "# Written by ALE_nextflow/deploy/azure/seqera-sp/10_store_secret.sh on $(date -u +%Y-%m-%dT%H:%M:%SZ)."
    echo "# One Seqera credential, two names: tw reads ONLY TOWER_ACCESS_TOKEN, the seqera CLI reads either."
    [[ -n "$SECRET" ]] && printf 'AZURE_CLIENT_SECRET=%s\n' "$SECRET"
    [[ -n "$TOKEN"  ]] && printf 'TOWER_ACCESS_TOKEN=%s\nSEQERA_ACCESS_TOKEN=%s\n' "$TOKEN" "$TOKEN"
} > "$SECRET_FILE"
chmod 600 "$SECRET_FILE"
unset SECRET TOKEN OLD_SECRET OLD_TOKEN

echo "Written: $SECRET_FILE"
ls -l "$SECRET_FILE"
echo
echo "Verify without printing anything:"
echo "    ./05_verify_sp_access.sh 2>&1 | tee \"logs/05_\$(date -u +%Y%m%dT%H%M%SZ).log\"   # Azure SP"
echo "    exec bash -l && tw info                                                          # Seqera token via ~/.bashrc"
