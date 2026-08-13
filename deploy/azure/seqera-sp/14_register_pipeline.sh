#!/usr/bin/env bash
# Register (or re-register) the Seqera Launchpad entry for the ottilie contract test.
#
#   ./14_register_pipeline.sh              # register, then read back and verify
#   ./14_register_pipeline.sh --generate   # regenerate the params box from the profile
#   DRY_RUN=1 ./14_register_pipeline.sh    # print what would happen, touch nothing
#
# 🚨 WHY THE PARAMS BOX REPEATS THE PROFILE.
#
# Platform's launch form populates its parameter fields from `paramsText` ONLY. Values that
# a config profile sets are applied at runtime but are INVISIBLE in the form — verified on
# run 2eiGBEA0NXagap, where the profile's input/fasta/tools took effect yet appeared nowhere
# in the submitted params. Someone opening the launch page saw an empty input box and had to
# go read the profile to know what would run. That is the UX this trades against.
#
# So the box carries the full param set, GENERATED from the profile by `--generate` rather
# than hand-copied: `nextflow config -profile docker,<profile>` diffed against
# `-profile docker` is exactly the set of keys the profile sets. A normal run re-derives it
# and ABORTS if the committed file has drifted, so the two cannot silently diverge.
#
# ⚠️ CONSEQUENCE, accepted deliberately: `-params-file` beats config, so a Launchpad run is
#    now driven by this box, not by the profile. Changing a param means editing the profile,
#    re-running `--generate`, committing, and re-registering — which mints a NEW pipeline id
#    every time, because `tw pipelines update` is broken. The profile remains the single
#    source of truth and is what local runs and nf-test actually use.
#
# 🚨 WHY THIS IS A SCRIPT AND NOT A UI CLICK-THROUGH.
#
# A Launchpad entry does NOT reference the repo — it stores a COPY of whatever was typed
# into its boxes. The previous entry was created by hand on 2026-08-07 and still carried
# params naming a file that no longer exists; nothing warned anyone, and nothing ever
# re-read the repo. Keeping the box contents in
# launchpad_params_ottilie_test_az.yml and applying them from here makes that copy
# reproducible and reviewable, instead of living only in a browser field.
#
# ⚠️ EVERY RUN REPLACES THE ENTRY. No route updates one in place: `tw pipelines update`
#    returns HTTP 500 on 0.38.0, `PUT /pipelines/{id}` returns 400 both with `name` supplied
#    and with the full launch object round-tripped from GET, `versions manage` only renames,
#    and `import --overwrite` reports "New pipeline added" with a changed id (all tested
#    2026-08-12). So a NEW pipeline id is minted each time. Nothing in this repo depends on
#    the id — only RUNBOOK.md records it — but a bookmarked Launchpad URL will break.
#
# WHAT LIVES WHERE, and why it is split:
#
#   conf/test/ottilie_test_az.config   the PROFILE — the single source of truth. Input,
#                                      reference, tools, joint-germline settings, and a
#                                      timestamped outdir. What local runs and nf-test use.
#   launchpad_params_ottilie_test_az.yml
#                                      the BOX — GENERATED from that profile, carrying the
#                                      full param set so the launch form is populated. It
#                                      overrides the profile at launch, which is why it is
#                                      generated and drift-checked rather than hand-written.
#
# ⚠️ The profile is only as current as the REGISTERED REVISION on GitHub. Platform clones
#    it; your working tree is invisible. Push before launching, always.

set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

NAME="${PIPELINE_NAME:-yAMP-ottilie-test-az}"
WORKSPACE="${SEQERA_WORKSPACE:-DTU-Biosustain/RECON-ALE}"
REPO="${PIPELINE_REPO:-https://github.com/Aletechdev/ALE_Yeast}"
REVISION="${PIPELINE_REVISION:-main}"
COMPUTE_ENV="${SEQERA_COMPUTE_ENV:-yAMP-ce-nofusion-256}"
WORK_DIR="${SEQERA_WORK_DIR:-az://aletest/nf-work}"
PROFILES="${SEQERA_PROFILES:-docker,ottilie_test_az}"
PARAMS_FILE="${PARAMS_FILE:-launchpad_params_ottilie_test_az.yml}"
DESCRIPTION="${PIPELINE_DESCRIPTION:-yAMP, params from the ottilie_test_az profile}"
# The engine pin lives HERE, on the pipeline, since 2026-08-12 — the compute environment no longer
# carries NXF_VER. ⚠️ 26.x cannot parse nextflow.config, so this is not cosmetic: an entry without it
# runs on Platform's default engine. Set to empty only if you deliberately want that default.
NEXTFLOW_VERSION="${NEXTFLOW_VERSION:-25.10.4}"
DRY_RUN="${DRY_RUN:-}"

SECRET_FILE="${SECRET_FILE:-$HOME/.config/ale-seqera/sp.env}"
if [[ -z "${TOWER_ACCESS_TOKEN:-}" && -r "$SECRET_FILE" ]]; then
    set -a; . "$SECRET_FILE"; set +a
fi
: "${TOWER_ACCESS_TOKEN:?TOWER_ACCESS_TOKEN not set — see 10_store_secret.sh}"

# ---------------------------------------------------------------------------
# Generate the params box from the profile — one source of truth, two artifacts
# ---------------------------------------------------------------------------
# EXCLUDED on purpose:
#   outdir              replaced below by DEFAULT_OUTDIR rather than taken from the profile —
#                       the profile's value is a Groovy timestamp, and freezing one evaluation
#                       of it into the box would publish every future run to one stale second.
#   genomes             an empty-list artifact of igenomes_ignore, not a real input.
#   config_profile_*    nf-core display strings, not run parameters.
EXCLUDE="outdir genomes config_profile_name config_profile_description"

# A deliberately DISPOSABLE default, so the launch form's outdir field is populated (the whole
# point of generating this box) without ever looking like a destination worth keeping. Runs that
# leave it overwrite each other here — publishDir overwrites but never deletes, so this directory
# accumulates a mixture and is not citable. That is what "DUMP" is announcing.
# ⚠️ Change it in the launch form for anything you intend to compare, publish or cite.
DEFAULT_OUTDIR="${DEFAULT_OUTDIR:-az://aletest/seqera-runs/yAMP-out-test-DUMP}"

generate_box() {
    python - "$PROFILES" "$EXCLUDE" "$DEFAULT_OUTDIR" <<'PY'
import subprocess, re, sys
profiles, exclude, default_outdir = sys.argv[1], set(sys.argv[2].split()), sys.argv[3]
base_profile = profiles.split(',')[0]

def params(p):
    out = subprocess.run(["nextflow", "config", "-profile", p],
                         capture_output=True, text=True, cwd="../../..").stdout
    blk = re.search(r"^params \{$(.*?)^\}$", out, re.S | re.M)
    return dict(re.findall(r"^\s+(\w+) = (.+)$", blk.group(1), re.M)) if blk else {}

base, prof = params(base_profile), params(profiles)
if not prof:
    sys.exit("FATAL: could not resolve params for -profile " + profiles)

def to_yaml(v):
    v = v.strip()
    if v == 'null':  return 'null'
    if v in ('true', 'false'): return v
    if re.fullmatch(r"-?\d+(\.\d+)?", v): return v
    if v.startswith("'") and v.endswith("'"): return '"%s"' % v[1:-1].replace('"', r'\"')
    return '"%s"' % v

diff = {k: v for k, v in prof.items() if base.get(k) != v and k not in exclude}
print(f"""# GENERATED — do not edit by hand. Regenerate with:
#     ./14_register_pipeline.sh --generate
#
# Contents of the "Pipeline parameters" box for the Launchpad entry, derived from
# `nextflow config -profile {profiles}` minus `-profile {base_profile}`.
#
# WHY THIS FILE EXISTS AT ALL. Platform's launch form populates its fields from paramsText
# only; values set by a config profile are applied at runtime but never displayed. Without
# this, the launch page shows an empty `input` box and you have to go read the profile.
#
# ⚠️ `-params-file` beats config, so THESE values are what a Launchpad run actually uses.
# The profile ({profiles.split(',')[-1]}) stays the source of truth — edit it, regenerate
# here, commit, and re-register. `tw pipelines update` is broken, so re-registering mints a
# new pipeline id.
#
# ⚠️ `outdir` below is a DISPOSABLE DEFAULT, not a destination. Runs that leave it publish
# on top of each other there — publishDir overwrites but never deletes, so it accumulates a
# mixture and is not citable. CHANGE IT IN THE LAUNCH FORM for anything you intend to
# compare, publish or cite. (The profile's own timestamped default,
# yAMP-out-test-<YYYYMMDD-HHMMSS>, applies to local runs, which have no params box; a
# params-file value always wins over it.)
#
# ⚠️ RUNNING THE FULL-DEPTH PILOT FROM THIS ENTRY? Switch the profile to
# `docker,ottilie_pilot_az` AND change every path below from S288C_reference_test/ to
# S288C_reference/ — or give the pilot its own entry.
""")
for k in sorted(diff):
    print(f"{k}: {to_yaml(diff[k])}")
print(f'outdir: "{default_outdir}"')
PY
}

if [[ "${1:-}" == "--generate" ]]; then
    TMP=$(mktemp); trap 'rm -f "$TMP"' EXIT
    generate_box > "$TMP"
    if [[ -r "$PARAMS_FILE" ]] && diff -q "$PARAMS_FILE" "$TMP" >/dev/null; then
        echo "  $PARAMS_FILE is already up to date with the profile."
    else
        cp "$TMP" "$PARAMS_FILE"
        echo "  wrote $PARAMS_FILE from -profile $PROFILES"
        echo "  ⚠️  commit it, then re-run this script without --generate to register."
    fi
    exit 0
fi

[[ -r "$PARAMS_FILE" ]] || { echo "FATAL: '$PARAMS_FILE' not found — run: $0 --generate" >&2; exit 1; }

# Drift guard: the committed box must still match the profile it was generated from.
TMP=$(mktemp); trap 'rm -f "$TMP"' EXIT
generate_box > "$TMP"
if ! diff -q "$PARAMS_FILE" "$TMP" >/dev/null; then
    echo "FATAL: $PARAMS_FILE has drifted from -profile $PROFILES:" >&2
    diff "$PARAMS_FILE" "$TMP" >&2 || true
    echo "Regenerate and commit:  $0 --generate" >&2
    exit 1
fi

# The box must parse to a YAML OBJECT. A comments-only file is valid YAML but parses to
# null, which Platform rejects with an unhelpful "Invalid ParamsText format" — catch it here.
python - "$PARAMS_FILE" <<'PY'
import sys, yaml
d = yaml.safe_load(open(sys.argv[1]))
if not isinstance(d, dict) or not d:
    sys.exit(f"FATAL: {sys.argv[1]} must parse to a non-empty YAML object (got {type(d).__name__}). "
             "Platform rejects a comments-only params text.")
print(f"  params box: {len(d)} keys, incl. input={d.get('input')!r}")
PY

# The profile is resolved from the registered revision on GitHub, not from this checkout.
if ! git diff --quiet HEAD -- ../../../conf/test/ 2>/dev/null; then
    echo "  ⚠️  conf/test/ has uncommitted changes — they will NOT be seen by a launch." >&2
fi
if [[ -n "$(git log --oneline "origin/$REVISION..$REVISION" 2>/dev/null || true)" ]]; then
    echo "  ⚠️  local '$REVISION' is ahead of origin/$REVISION — PUSH before launching." >&2
fi

echo "Registering '$NAME' in $WORKSPACE"
echo "  repo/revision : $REPO @ $REVISION"
echo "  compute env   : $COMPUTE_ENV"
echo "  profiles      : $PROFILES"
echo "  params box    : $PARAMS_FILE"

if [[ -n "$DRY_RUN" ]]; then
    echo "  DRY-RUN: would delete any existing '$NAME', then tw pipelines add"
    exit 0
fi

# Delete first: `add` refuses a duplicate name, and `update` is broken (see header).
if tw pipelines view -n "$NAME" -w "$WORKSPACE" >/dev/null 2>&1; then
    echo "  existing entry found — deleting (its pipeline id will not be reused)"
    tw pipelines delete -n "$NAME" -w "$WORKSPACE"
fi

# ⚠️ REGISTERED VIA `import`, NOT `add`. `tw pipelines add` has no --nextflow-version flag, so an
# entry it creates carries no engine pin — and since 2026-08-12 the compute environment no longer
# carries NXF_VER either, which would leave the run on Platform's default engine (26.x cannot parse
# nextflow.config). `import` accepts `launch.nextflowVersion` in its JSON and preserves it, verified
# by readback. That is the only scriptable way to pin the engine per pipeline; the alternative is a
# manual UI edit repeated after every re-registration.
CE_ID=$(tw -o json compute-envs list -w "$WORKSPACE" 2>/dev/null | python -c "
import json,sys
for c in json.load(sys.stdin)['computeEnvs']:
    if c['name']=='$COMPUTE_ENV': print(c['id']); break")
: "${CE_ID:?compute environment '$COMPUTE_ENV' not found in $WORKSPACE}"

IMPORT_JSON=$(mktemp --suffix=.json)
python - "$IMPORT_JSON" "$REPO" "$REVISION" "$CE_ID" "$WORK_DIR" "$PROFILES" \
         "$PARAMS_FILE" "$DESCRIPTION" "$NEXTFLOW_VERSION" <<'PY'
import json, sys
dst, repo, rev, ce, wd, profiles, params_file, desc, nfver = sys.argv[1:10]
launch = {"pipeline": repo, "revision": rev, "computeEnvId": ce, "workDir": wd,
          "configProfiles": profiles.split(','), "paramsText": open(params_file).read(),
          "pullLatest": False, "stubRun": False, "resume": False}
if nfver:
    launch["nextflowVersion"] = nfver
json.dump({"description": desc, "launch": launch}, open(dst, "w"), indent=2)
PY

# ⚠️ `import` takes no --labels (only `add` does), so the entry carries none. Add them in the UI
# if you want them; they are cosmetic and would be lost on the next re-registration anyway.
tw pipelines import -n "$NAME" -w "$WORKSPACE" --overwrite "$IMPORT_JSON"
rm -f "$IMPORT_JSON"

# Readback. The API accepts unvalidated payloads elsewhere, so assert rather than assume.
echo
echo "=== verifying ==="
PID=$(tw -o json pipelines list -w "$WORKSPACE" 2>/dev/null \
      | python -c "
import json,sys
for p in json.load(sys.stdin)['pipelines']:
    if p['name']=='$NAME': print(p['pipelineId']); break")
: "${PID:?could not resolve the new pipeline id}"

API="${SEQERA_API:-https://api.cloud.seqera.io}"
WS_ID=$(tw -o json workspaces list 2>/dev/null | python -c "
import json,sys
want='$WORKSPACE'.lower()
for w in json.load(sys.stdin)['workspaces']:
    if f\"{w['orgName']}/{w['workspaceName']}\".lower()==want: print(w['workspaceId']); break")

# ⚠️ The response goes to a temp FILE, not a pipe. `python -` reads its program from stdin,
# and the heredoc below already claims stdin — a piped body would never reach json.load
# (it fails with "Expecting value: line 1 column 1"). Pass the path as argv instead. Same
# trap as 12_verify_compute_env.sh; it catches everyone once.
RESP=$(mktemp); trap 'rm -f "$TMP" "$RESP"' EXIT
curl -sS -H "Authorization: Bearer $TOWER_ACCESS_TOKEN" \
     "$API/pipelines/$PID/launch?workspaceId=$WS_ID" > "$RESP"

python - "$RESP" "$PID" "$PROFILES" "$NEXTFLOW_VERSION" <<'PY'
import json, sys, yaml
l = json.load(open(sys.argv[1]))['launch']
pid, want_profiles = sys.argv[2], sys.argv[3].split(',')
bad = []
def chk(ok, msg):
    print(("  OK    " if ok else "  FAIL  ") + msg)
    if not ok: bad.append(msg)
print(f"pipeline id {pid}")
chk(l.get('configProfiles') == want_profiles, f"configProfiles = {want_profiles} (got {l.get('configProfiles')})")
box = yaml.safe_load(l.get('paramsText') or '') or {}
chk(isinstance(box, dict) and bool(box), f"params box is a non-empty object: {box}")
chk('snpeff_cache' in box,
    "snpeff_cache present in the box — the launch form injects the schema default otherwise (§13)")
want_nf = sys.argv[4] or None
chk(l.get('nextflowVersion') == want_nf,
    f"nextflowVersion = {want_nf!r} (got {l.get('nextflowVersion')!r}) — the CE no longer pins the "
    f"engine, so this is the only pin; 26.x cannot parse nextflow.config")
print(f"  info  computeEnv = {l['computeEnv']['name']}")
print(f"  info  {l['pipeline']} @ {l.get('revision')}")
if bad:
    print("\n🚨 VERIFICATION FAILED — do not launch against this entry.")
    sys.exit(1)
print("\n✅ All checks passed.")
PY

echo
echo "⚠️  Record the new pipeline id in RUNBOOK.md — it changes on every re-registration."
