#!/usr/bin/env bash
# Generates the SSH deploy key that lets Seqera clone the private pipeline repo.
#
# A deploy key belongs to the REPOSITORY, not to a GitHub user and not to the org's
# token settings. Consequences, which are the reason this route was chosen over a PAT:
#   - read-only and scoped to one repo (a classic PAT grants every repo you can see)
#   - no expiry to lapse silently
#   - survives personnel changes — nobody's account grants the access
#
# Safe to run: generates only if the key is absent, never overwrites, and prints only
# the PUBLIC half. The private key stays in ~/.ssh and is never echoed.
#
#   ./07_github_deploy_key.sh 2>&1 | tee "logs/07_$(date -u +%Y%m%dT%H%M%SZ).log"

set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"
source ./00_vars.sh

KEY="${KEY:-$HOME/.ssh/seqera_ale_yeast_deploy}"
REPO="${REPO:-Aletechdev/ALE_Yeast}"
CRED_NAME="${CRED_NAME:-github_ALE_Yeast_deploykey}"

mkdir -p "$(dirname "$KEY")"; chmod 700 "$(dirname "$KEY")"

if [[ -f "$KEY" ]]; then
    echo "Key already exists at $KEY — reusing it, not regenerating."
    echo "(Delete it manually first if you really want a fresh one; regenerating would"
    echo " orphan the deploy key already registered on GitHub.)"
else
    # No passphrase: Seqera stores the private key and must use it unattended, so a
    # passphrase would have to be stored beside it — it would add ceremony, not security.
    ssh-keygen -t ed25519 -f "$KEY" -N '' -C "seqera-platform $REPO" >/dev/null
    echo "Generated a new ed25519 keypair at $KEY"
fi

chmod 600 "$KEY"; chmod 644 "$KEY.pub"

cat <<EOF

=========================== STEP 1 — GitHub ===========================
Go to:  https://github.com/$REPO/settings/keys   ("Add deploy key")

  Title            : Seqera Platform (RECON-ALE)
  Allow write access: LEAVE UNCHECKED  <-- read-only is the whole point
  Key              : paste the single line below

EOF
cat "$KEY.pub"
cat <<EOF

=========================== STEP 2 — Seqera ===========================
Register the PRIVATE half as an ssh credential (the file is read by tw; its
contents are never printed):

  tw credentials add ssh \\
      -n $CRED_NAME \\
      -w $SEQERA_WORKSPACE \\
      -k $KEY

=========================== STEP 3 — launch URL =======================
A deploy key CANNOT authenticate an HTTPS clone. The pipeline URL must be the
SSH form from now on:

  git@github.com:$REPO.git      (not https://github.com/$REPO)

=========================== verify ====================================
  ssh -T -i $KEY git@github.com
Expect: "Hi $REPO! You've successfully authenticated, but GitHub does not
provide shell access." — that message means SUCCESS (exit code 1 is normal).
EOF

echo
echo "Private key permissions:"
ls -l "$KEY" "$KEY.pub"
