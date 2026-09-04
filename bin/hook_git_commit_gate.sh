#!/bin/bash
# Claude Code PreToolUse adapter for bin/check_snapshot_staged.sh: reads the tool call from stdin,
# acts only on Bash commands that run `git commit`, and passes the -F message file through when
# the command names one. Exit 2 blocks the commit and surfaces the reason.
set -u
input=$(cat)
cmd=$(python3 -c 'import json,sys; print(json.load(sys.stdin).get("tool_input",{}).get("command",""))' <<<"$input" 2>/dev/null)
grep -qE '(^|[;&| ])git[[:space:]]+commit([[:space:]]|$)' <<<"$cmd" || exit 0
grep -qE -- '--amend|--no-verify' <<<"$cmd" && { echo "note: amend/--no-verify - check origin/main..main before amending (memory: commit-workflow)" >&2; }
msg_file=$(grep -oE -- '-F[[:space:]]+[^[:space:]]+' <<<"$cmd" | head -1 | awk '{print $2}')
# heredoc messages (-F - <<'EOF') arrive on stdin of git itself; capture the heredoc body from the command text
if [ "$msg_file" = "-" ] || [ -z "$msg_file" ]; then
  tmp=$(mktemp); awk 'f{print} /<<'\''?EOF'\''?[[:space:]]*$/{f=1}' <<<"$cmd" | sed '/^EOF$/,$d' > "$tmp"; msg_file=$tmp
fi
cd "${CLAUDE_PROJECT_DIR:-.}" && bash bin/check_snapshot_staged.sh "$msg_file"
