#!/usr/bin/env bash
# Warns when a tracked credential approaches expiry. Run automatically by the
# Claude Code SessionStart hook (.claude/settings.json); safe to run by hand too.
# Prints NOTHING while every credential has more lead time than its threshold,
# so sessions stay quiet until action is actually due.
#
# After any rotation: update the entry here AND in deploy/azure/seqera-sp/RUNBOOK.md
# (the audit record). Dates and names only — no secrets, no GUIDs (deploy/azure/README.md).

set -u

today_s=$(date -u +%s)
warned=0

# args: name | expiry (UTC date) | lead-days | action when it fires
check() {
    local name="$1" expiry="$2" lead="$3" action="$4"
    local expiry_s days_left
    expiry_s=$(date -u -d "$expiry" +%s 2>/dev/null) || { echo "⚠️ $0: bad date '$expiry' for $name"; warned=1; return; }
    days_left=$(( (expiry_s - today_s) / 86400 ))
    if (( days_left < 0 )); then
        echo "🚨 EXPIRED $(( -days_left )) days ago: $name (expired $expiry) — $action"
        warned=1
    elif (( days_left <= lead )); then
        echo "⏰ $name expires $expiry ($days_left days left) — $action"
        warned=1
    fi
}

check "Azure SP client secret (sp-bright-recon-ale-mutations-pipeline-seqera-deploy, hint 'seqera-platform')" \
      "2027-07-31" 60 \
      "mint a new secret with deploy/azure/seqera-sp/03_create_secret.sh (operator terminal ONLY — it prints the secret), update the Seqera credential and ~/.config/ale-seqera/sp.env, then delete the old keyId. Expired = opaque auth error at launch."

check "GitHub fine-grained PAT (github_ALE_Yeast_finegrained)" \
      "2027-08-07" 60 \
      "re-issue at github.com/settings/tokens and swap into the Seqera credential; org-owner re-approval takes ~1 day, so start early. Expired = Seqera cannot clone the pipeline repo."

# Pending one-off, not a renewal: fires every session until done, then delete this entry.
check "Sister-SP secret awaiting rotation (sp-bright-recon-ale-mutations-pipeline)" \
      "2026-11-02" 9999 \
      "operator live-swap pending; recipe in deploy/azure/seqera-sp/RUNBOOK.md open items. REMOVE this entry once rotated."

if (( warned )); then
    echo "(bin/check_credential_expiry.sh — update its dates after any rotation)"
fi
exit 0
