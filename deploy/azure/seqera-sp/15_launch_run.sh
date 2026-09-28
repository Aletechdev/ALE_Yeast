#!/usr/bin/env bash
# Launch a run of the ottilie Launchpad entry from the command line, with parameter overrides — or
# resume a finished run with changed parameters. What the launch form does, scripted and recorded.
#
#   ./15_launch_run.sh --name yAMP-qc-first-run1-20260928 \
#       --set outdir=az://aletest/seqera-runs/yAMP-qc-first-20260928 --set qc_only=true
#   ./15_launch_run.sh --resume 5m9NorL3JmkHFq --name yAMP-qc-first-run2-20260928 \
#       --set outdir=az://aletest/seqera-runs/yAMP-qc-first-20260928
#   DRY_RUN=1 ./15_launch_run.sh ...        # print the params and the command, launch nothing
#
# The params text sent is the COMMITTED box (launchpad_params_ottilie_test_az.yml — what the launch
# form shows) plus the --set overrides, because `tw launch --params-file` REPLACES the entry's params
# rather than merging into them (RUNBOOK 2026-09-08: 12 params submitted when the file left one out).
# So every launch carries the full set; an override that is not in the box is added to it.
#
# --resume RUN_ID is Platform's *Resume* button: `tw runs relaunch` on that run keeps its session,
# work dir, compute environment, revision and profiles and resumes from the cache; only the params
# are replaced. The QC-first pair (docs/usage/qc_first_run.md): run 1 with `--set qc_only=true`,
# run 2 `--resume <run 1>` WITHOUT that override (the box has no qc_only, so leaving it out clears
# it) and the SAME outdir. `--set qc_only=false` also works but records a param a one-shot run never
# carries, so the two runs' params would differ for no reason.
#
# ⚠️ Platform clones the registered revision from GitHub: your working tree is invisible. The script
#    refuses to launch while local main is ahead of origin/main.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

ENTRY="${PIPELINE_NAME:-yAMP-ottilie-test-az}"
WORKSPACE="${SEQERA_WORKSPACE:-DTU-Biosustain/RECON-ALE}"
PROFILES="${SEQERA_PROFILES:-docker,ottilie_test_az}"
BOX="${PARAMS_FILE:-launchpad_params_ottilie_test_az.yml}"
DRY_RUN="${DRY_RUN:-}"

SECRET_FILE="${SECRET_FILE:-$HOME/.config/ale-seqera/sp.env}"
if [[ -z "${TOWER_ACCESS_TOKEN:-}" && -r "$SECRET_FILE" ]]; then set -a; . "$SECRET_FILE"; set +a; fi
: "${TOWER_ACCESS_TOKEN:?TOWER_ACCESS_TOKEN not set — see 10_store_secret.sh}"

name="" resume="" sets=()
while [[ $# -gt 0 ]]; do
    case "$1" in
        --name)    name=$2;   shift 2 ;;
        --resume)  resume=$2; shift 2 ;;
        --set)     sets+=("$2"); shift 2 ;;
        -h|--help) sed -n '2,24p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
        *) echo "unknown argument: $1 (see --help)" >&2; exit 2 ;;
    esac
done
[[ -n "$name" ]] || { echo "--name is required, e.g. --name yAMP-qc-first-run1-$(date +%Y%m%d)" >&2; exit 2; }
[[ "$name" =~ ^[A-Za-z0-9_-]+$ ]] || { echo "--name: letters, digits, - and _ only" >&2; exit 2; }
[[ -r "$BOX" ]] || { echo "FATAL: '$BOX' not found — run: ./14_register_pipeline.sh --generate" >&2; exit 1; }

if [[ -n "$(git log --oneline origin/main..main 2>/dev/null || true)" ]]; then
    echo "FATAL: local main is ahead of origin/main — push first; Platform clones from GitHub." >&2
    exit 1
fi

# params = the committed box + the overrides (values parse as YAML scalars: true/false/null/numbers/strings)
PARAMS=$(mktemp --suffix=.yml); trap 'rm -f "$PARAMS"' EXIT
python - "$BOX" "$PARAMS" "${sets[@]}" <<'PY'
import sys, yaml
box, dst, *sets = sys.argv[1:]
d = yaml.safe_load(open(box))
for s in sets:
    k, eq, v = s.partition('=')
    if not eq or not k:
        sys.exit(f"--set expects key=value, got {s!r}")
    d[k] = yaml.safe_load(v) if v != '' else None
yaml.safe_dump(d, open(dst, 'w'), sort_keys=True, default_flow_style=False)
print(f"  params: {len(d)} keys" + (f"; overrides: {', '.join(sets)}" if sets else "; no overrides"))
PY

if [[ -n "$resume" ]]; then
    echo "Resuming run $resume as '$name' in $WORKSPACE (params replaced; session, work dir, CE, revision, profiles kept)"
    cmd=(tw runs relaunch -i "$resume" -w "$WORKSPACE" -n "$name" --params-file "$PARAMS")
else
    echo "Launching '$ENTRY' as '$name' in $WORKSPACE (-p $PROFILES)"
    cmd=(tw launch "$ENTRY" -w "$WORKSPACE" -n "$name" -p "$PROFILES" --params-file "$PARAMS")
fi
if [[ -n "$DRY_RUN" ]]; then
    echo "  DRY-RUN: ${cmd[*]}"; echo "  --- params ---"; cat "$PARAMS"; exit 0
fi
out=$("${cmd[@]}" 2>&1); echo "$out"
id=$(grep -oE 'Workflow [A-Za-z0-9]+' <<<"$out" | awk '{print $2}' | head -1)
[[ -n "$id" ]] || { echo "could not parse the run id from the CLI output above" >&2; exit 1; }
echo "  run id : $id"
echo "  watch  : ./16_watch_run.sh $id"
