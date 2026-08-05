#!/usr/bin/env bash
# Stores the SP client secret ONCE in an out-of-repo file, so nothing afterwards needs
# an interactive prompt.
#
# WHY: `read -rs AZURE_CLIENT_SECRET` prints no prompt and echoes nothing. In a real
# terminal that is fine; in a VS Code task, a pasted block, a tmux send-keys, or an
# agent shell there is no TTY to type into, so it blocks silently until the session
# times out — which looks like a crash rather than "waiting for input". Storing the
# secret once removes that failure mode from every later script.
#
# The file lives OUTSIDE the repo at ~/.config/ale-seqera/sp.env, mode 600. The repo's
# .gitignore blocks *.env anyway, but the rule is "not in the tree" — this honours it.
#
#   ./10_store_secret.sh          # run once, in a real terminal
#
# Afterwards, `source 00_vars.sh` picks the secret up automatically and
# bin/test_ottilie_azure_batch.sh just works.
#
# To rotate: re-run 03_create_secret.sh, then re-run this.
# To revoke : rm ~/.config/ale-seqera/sp.env  (and delete the credential in Azure)

set -euo pipefail

SECRET_FILE="${SECRET_FILE:-$HOME/.config/ale-seqera/sp.env}"

if [[ ! -t 0 ]]; then
    cat >&2 <<EOF
REFUSING: stdin is not a terminal, so there is nothing to type into — this is exactly
the situation that hangs. Run this in a real interactive shell.

If you genuinely have no TTY, write the file yourself instead:

    mkdir -p "$(dirname "$SECRET_FILE")" && chmod 700 "$(dirname "$SECRET_FILE")"
    printf 'AZURE_CLIENT_SECRET=%s\n' '<secret>' > "$SECRET_FILE"
    chmod 600 "$SECRET_FILE"

(Prefix that command with a space if your shell records history.)
EOF
    exit 1
fi

mkdir -p "$(dirname "$SECRET_FILE")"
chmod 700 "$(dirname "$SECRET_FILE")"

if [[ -f "$SECRET_FILE" ]]; then
    echo "A secret file already exists at $SECRET_FILE"
    read -r -p "Overwrite it? [y/N] " reply
    [[ "$reply" == "y" || "$reply" == "Y" ]] || { echo "aborted — existing file kept"; exit 1; }
fi

echo
echo "Paste the client secret from 03_create_secret.sh, then press Enter."
echo "Nothing will echo — that is expected, not a hang. Ctrl-C to abort."
echo
# -p gives a VISIBLE prompt (the missing piece in the bare `read -rs` form) and -t caps
# the wait so this can never hold a session open indefinitely.
if ! read -rsp 'secret: ' -t 300 SECRET; then
    echo >&2
    echo "Timed out after 300s with no input. Nothing was written." >&2
    exit 1
fi
echo

[[ -n "${SECRET:-}" ]] || { echo "Empty input — nothing written." >&2; exit 1; }

umask 077
printf 'AZURE_CLIENT_SECRET=%s\n' "$SECRET" > "$SECRET_FILE"
chmod 600 "$SECRET_FILE"
unset SECRET

echo "Written: $SECRET_FILE"
ls -l "$SECRET_FILE"
echo
echo "Verify it is the right secret without printing it:"
echo "    ./05_verify_sp_access.sh 2>&1 | tee \"logs/05_\$(date -u +%Y%m%dT%H%M%SZ).log\""
