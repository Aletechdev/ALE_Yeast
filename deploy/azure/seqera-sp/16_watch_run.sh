#!/usr/bin/env bash
# Watch a Platform run until it ends, then print its task statistics. Exit 0 on SUCCEEDED, 1 on
# FAILED / CANCELLED, 2 when Platform lost the run (UNKNOWN) and the grace period ran out.
#
#   ./16_watch_run.sh RUN_ID [poll seconds, default 60] [UNKNOWN grace minutes, default 30]
#   ./16_watch_run.sh "$id" && ./15_launch_run.sh --resume "$id" ...      # chain the QC-first pair
#
# One line per status change (SUBMITTED → RUNNING → SUCCEEDED / FAILED / CANCELLED / UNKNOWN), with the
# elapsed minutes, then `tw runs view --stats` — task counts incl. CACHED, the number to check on a
# resumed run. Per-process detail: `tw runs view -i RUN_ID -w <workspace> --processes`.
# A transient CLI/API error prints nothing and is retried at the next poll.
#
# ⚠️ UNKNOWN is NOT an outcome (azure_batch_execution.md §15). It means Platform stopped receiving the
# head job's events — on 2026-09-28 (run 464Scp5QNoznbD) the workflow kept completing tasks and
# publishing files for minutes after the status flipped, after the Tower client had retried HTTP
# calls to api.cloud.seqera.io. So on UNKNOWN this script prints the two authoritative checks and
# keeps polling for the grace period in case Platform catches up; if it does not, exit 2 and decide
# from the head job's own log and the outdir, never from the status:
#     az batch task file download --job-id nf-workflow-RUN_ID --task-id nf-workflow-RUN_ID \
#         --file-path stdout.txt --destination /tmp/head.txt && tail -3 /tmp/head.txt
#     az batch task show --job-id nf-workflow-RUN_ID --task-id nf-workflow-RUN_ID --query state -o tsv
# A head job that finished and hung holds its node indefinitely (§15) — check the head pool after.
set -uo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"
WORKSPACE="${SEQERA_WORKSPACE:-DTU-Biosustain/RECON-ALE}"

SECRET_FILE="${SECRET_FILE:-$HOME/.config/ale-seqera/sp.env}"
if [[ -z "${TOWER_ACCESS_TOKEN:-}" && -r "$SECRET_FILE" ]]; then set -a; . "$SECRET_FILE"; set +a; fi
: "${TOWER_ACCESS_TOKEN:?TOWER_ACCESS_TOKEN not set — see 10_store_secret.sh}"

id=${1:?usage: $0 RUN_ID [poll seconds] [UNKNOWN grace minutes]}; every=${2:-60}; grace=${3:-30}
prev=""; t0=$(date +%s); s=""; unknown_since=""
while true; do
    s=$(tw runs view -i "$id" -w "$WORKSPACE" --status 2>/dev/null \
        | grep -ioE 'SUBMITTED|RUNNING|SUCCEEDED|FAILED|CANCELLED|UNKNOWN' | head -1 | tr '[:lower:]' '[:upper:]' || true)
    if [[ -n "$s" && "$s" != "$prev" ]]; then
        printf '%s  +%3dm  %s  %s\n' "$(date -u +%H:%M:%SZ)" $(( ($(date +%s) - t0) / 60 )) "$id" "$s"
        prev=$s
        if [[ "$s" == UNKNOWN ]]; then
            unknown_since=$(date +%s)
            echo "  ⚠️  UNKNOWN = Platform lost the head job's events, not an outcome (azure_batch_execution.md §15)."
            echo "      Authoritative: the head job's log and the outdir —"
            echo "        az batch task file download --job-id nf-workflow-$id --task-id nf-workflow-$id --file-path stdout.txt --destination /tmp/head.txt && tail -3 /tmp/head.txt"
            echo "      Polling for up to $grace more minutes in case Platform catches up."
        fi
    fi
    case "$s" in
        SUCCEEDED|FAILED|CANCELLED) break ;;
        UNKNOWN) [[ -n "$unknown_since" && $(( $(date +%s) - unknown_since )) -ge $(( grace * 60 )) ]] && break ;;
    esac
    sleep "$every"
done
echo
tw runs view -i "$id" -w "$WORKSPACE" --stats 2>/dev/null | sed 's/^/  /'
case "$s" in SUCCEEDED) exit 0 ;; UNKNOWN) exit 2 ;; *) exit 1 ;; esac
