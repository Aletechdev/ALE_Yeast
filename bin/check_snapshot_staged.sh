#!/bin/bash
# Commit gate for the "what counts as validated" rule (CLAUDE.md; testing_best_practices.md §12).
#
# Blocks a commit whose STAGED files can change pipeline outputs unless the commit carries a trace
# that the tests were run: the re-recorded e2e snapshot staged alongside, or explicit trailer lines
# in the commit message. It never runs a test and never inspects outputs - it only checks that the
# commit says which validation happened, so it takes milliseconds and any false claim is on record.
#
#   bin/check_snapshot_staged.sh [commit-message-file]      exit 0 = allow, 2 = block (message on stderr)
#
# Wired as a Claude Code PreToolUse hook on `git commit` (.claude/settings.json) and installable as a
# git hook:  ln -s ../../bin/check_snapshot_staged.sh .git/hooks/commit-msg
set -u
msg_file="${1:-}"
staged=$(git diff --cached --name-only)
[ -z "$staged" ] && exit 0

# 1. paths whose change CAN alter pipeline outputs (task scripts in bin/ are the .py files modules call)
behaviour=$(grep -E '^(conf/modules/|subworkflows/|modules/|workflows/|nextflow\.config$|bin/[^/]+\.py$)' <<<"$staged")
[ -z "$behaviour" ] && exit 0

msg=""; [ -n "$msg_file" ] && [ -r "$msg_file" ] && msg=$(cat "$msg_file")
fail=0

# 2. e2e contract test: the .snap must be staged, or the message must claim it did not move
if ! grep -q '^tests/ottilie_e2e.nf.test.snap$' <<<"$staged" && ! grep -qi '^Snapshot: unchanged' <<<"$msg"; then
  fail=1
  cat >&2 <<EOT
BLOCKED: staged changes can alter pipeline outputs, but tests/ottilie_e2e.nf.test.snap is not staged:
$(sed 's/^/    /' <<<"$behaviour")
Run the contract test:  nf-test test -c tests/nf-test-ottilie.config tests/ottilie_e2e.nf.test
- outputs moved   -> explain every difference, re-record (--update-snapshot), stage the .snap
- outputs did not -> add a trailer line to the commit message:
      Snapshot: unchanged (e2e green on <commit>, <date>)
EOT
fi

# 3. path -> module/subworkflow test map: each touched entry needs "Module test: <name> green" in the message
declare -A TESTMAP=(
  ['conf/modules/trimming.config']=fastp_preprocessing
  ['modules/nf-core/fastp/']=fastp_preprocessing
  ['subworkflows/local/split_joint_vcf/']=split_joint_vcf
  ['conf/modules/split_joint_vcf.config']=split_joint_vcf
)
for path in "${!TESTMAP[@]}"; do
  if grep -q "^${path}" <<<"$staged"; then
    t=${TESTMAP[$path]}
    if ! grep -qi "^Module test: ${t} green" <<<"$msg"; then
      fail=1
      cat >&2 <<EOT
BLOCKED: $path is staged; its unit test must be cited in the commit message:
      Module test: ${t} green
  (run: nf-test test -c tests/nf-test-ottilie.config tests/${t}.nf.test)
EOT
    fi
  fi
done

[ "$fail" -eq 0 ] && exit 0
echo "See CLAUDE.md 'What counts as validated' / docs/dev-practices/testing_best_practices.md §12." >&2
exit 2
