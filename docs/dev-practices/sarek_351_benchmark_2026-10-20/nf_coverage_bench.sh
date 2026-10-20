#!/bin/bash
# Bench copy of ALE_Yeast tests/nf_coverage.sh: the same JaCoCo method applied to ANOTHER pipeline tree
# (issue #14 item 5: pristine nf-core/sarek 3.5.1 under its own test route). Committed copy of the script that produced
# docs/dev-practices/sarek_351_benchmark_2026-10-20.md; it was run from ~/bench on the dev VM and needs no repo path
# other than REPO_DIR (the report script). Not part of the test suite or the commit gate.
#
# Unchanged from tests/nf_coverage.sh, so the counts are comparable: JaCoCo 0.8.12, the agent and its
# includes filter (Script*:_nf_config_*), NXF_VER 25.10.4, the report script (read from the repo, not copied).
# Changed:
#   - the measured tree comes from PIPE_DIR (required), its tests from TESTS_DIR (default PIPE_DIR/tests), the
#     profile from PROFILE (default test,docker); nf-test runs from the tree's root with the tree's own nf-test.config
#     (NFT_CONFIG=<file> passes a -c instead); nothing of the ALE repo (ottilie profile, resources config) is used
#   - "own code" = every .nf / .config of the measured tree. The report script keeps its fork-vs-upstream split, so
#     it is given a baseline of EMPTY files at the same paths (tools/empty_baseline): every executable line is then
#     a "fork" line and the "... - fork lines only" tables ARE the all-code tables (the all-code lines/closures tables
#     are printed too; `report` checks that the two agree). For pristine sarek the fork/upstream split does not apply.
#   - no --qc_only run (a fork flag) and no fixed test list: `run` = plan-only run + the tests in BENCH_TESTS
#     (default: default); `pipeline <name> <nextflow args>` records one direct run, for a route that has no nf-test
#     file (sarek 3.5.1's joint_germline is a pytest-workflow yml) - the profile for it comes from PROFILE as well
#   - RUN_INFO.txt records the tree and BENCH_REF (default: the tree's basename) instead of a git commit of the tree,
#     plus the commit of the report script in REPO_DIR (default ~/Docs/ALE_nextflow)
#
#   PIPE_DIR=~/bench/sarek-3.5.1 COV_DIR=~/bench/output_sarek351 nf_coverage_bench.sh run
#                                             the plan-only run (-preview), then every test in BENCH_TESTS; the report
#   ... run <test> [...]                      only these test files (names without .nf.test), added to the data there
#   ... pipeline <name> <nextflow args...>    one direct run under the agent, e.g.  pipeline joint_germline --tools ...
#                                             (PROFILE=test,targeted,docker to change its profile); then the report
#   ... report                                rebuild the report from the recorded data
#   ... annotate <set> <path-suffix>          one source file line by line (sets: all, preview, t_<test>, <name>)
#
# Output: $COV_DIR, default ~/bench/output_<basename of PIPE_DIR>:
#   tables.txt     lines / closures / branches per code group, per run set and everything merged
#   uncovered.txt  lines, closures and partly covered decision lines that nothing executed
#   levels.txt     the same tables per test level (plan-only pipeline, full-run pipeline, ...)
#   unique.txt     what each run set covers that no other does
#   coverage.tsv   per-file counts          lcov.info  for editor gutters / genhtml / Codecov
#   RUN_INFO.txt   tree, versions, the result and duration of every run
#   exec/ classes/ logs/ xml/               the raw data the report is built from
#
# A full `run` starts from an empty $COV_DIR/exec and classes; a partial run adds to them.
# A failing test still records coverage; it is listed in RUN_INFO.txt and the script exits 1.
# Requires on PATH: nextflow, nf-test, java + javap (JDK), python, curl; docker; network for the tree's test data
# and nf-test plugins. First use downloads JaCoCo into $COV_DIR/tools.
set -euo pipefail

bench=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
repo=${REPO_DIR:-$HOME/Docs/ALE_nextflow}                 # the report script, unchanged
pipe=$(cd "${PIPE_DIR:?set PIPE_DIR=<root of the pipeline tree to measure>}" && pwd)
tests_dir=${TESTS_DIR:-$pipe/tests}
profile=${PROFILE:-test,docker}
ref=${BENCH_REF:-$(basename "$pipe")}
export NXF_VER=${NXF_VER:-25.10.4}
out=${COV_DIR:-$bench/output_$(basename "$pipe")}
jacoco=0.8.12
cmd=${1:-}; [ $# -gt 0 ] && shift

usage() { sed -n '2,/^set -euo/p' "$0" | sed '$d; s/^# \{0,1\}//'; exit 1; }
[ -n "$cmd" ] || usage
[ -f "$repo/tests/nf_coverage_report.py" ] || { echo "report script not found: $repo/tests/nf_coverage_report.py (set REPO_DIR)" >&2; exit 1; }

mkdir -p "$out"/{tools,exec,classes,logs,xml,runs}
cli="java -jar $out/tools/jacococli.jar"
baseline="$out/tools/empty_baseline"

tools() {
  for t in runtime:agent nodeps:cli; do
    [ -s "$out/tools/jacoco${t#*:}.jar" ] && continue
    curl -fsSL -o "$out/tools/jacoco${t#*:}.jar" \
      "https://repo1.maven.org/maven2/org/jacoco/org.jacoco.${t#*:}/$jacoco/org.jacoco.${t#*:}-$jacoco-${t%:*}.jar"
  done
  # the baseline for "fork lines": an empty file at the path of every .nf / .config of the tree, so that every
  # executable line of the tree is a fork line (= its own code); rebuilt on every call so it follows the tree
  rm -rf "$baseline"; mkdir -p "$baseline"
  (cd "$pipe" && find . \( -name .git -o -name work -o -name .nextflow -o -name .nf-test \) -prune -o \
      \( -name '*.nf' -o -name '*.config' \) -type f -print) | while read -r f; do
    mkdir -p "$baseline/$(dirname "$f")"; : > "$baseline/$f"
  done
}

# The two class-name patterns cover every pipeline script and config file: Script_<hash> (.nf),
# Script<MD5> (includeConfig'd files) and _nf_config_<hash> (nextflow.config, -c files). Nextflow's own
# classes must stay uninstrumented: instrumenting everything crashes the launcher.
agent() { echo "-javaagent:$out/tools/jacocoagent.jar=destfile=$out/exec/$1.exec,classdumpdir=$out/classes,inclnolocationclasses=true,includes=Script*:_nf_config_*"; }

# A run whose data holds no Script_* class recorded config code only: the agent's includes filter no longer
# matches the script classes. Nextflow 26.x (strict parser) names them Main / _nf_script_<hash> instead, and
# the run still exits 0, so without this check the report would silently shrink to config lines
# (docs/dev-practices/nextflow_branch_counting/nf26/RESULTS.md).
check_scripts_recorded() {   # <exec file>
  [ -s "$1" ] || return 0
  $cli execinfo "$1" 2>/dev/null | grep -q ' Script_' && return 0
  { echo "FAILED: $(basename "$1") holds no Script_* class - the run recorded config classes only."
    echo "  Likely cause: Nextflow $NXF_VER names the script classes differently (26.x strict: Main, _nf_script_<hash>),"
    echo "  so the agent's includes=Script*:_nf_config_* filter misses them. Needed changes: docs/dev-practices/nextflow_branch_counting/nf26/RESULTS.md"; } >&2
  return 1
}

note() { printf '%s\t%s\t%s\n' "$1" "$2" "$3" >> "$out/RUN_INFO.txt"; echo "  $1: exit $2, ${3}s"; }

# the compiler behind the branch counts (docs/dev-practices/nextflow_branch_counting.md): Groovy is merged into
# Nextflow's one-jar, which exists once that version has been launched; "?" when it has not
groovy_version() {
  local jar="${NXF_HOME:-$HOME/.nextflow}/framework/$NXF_VER/nextflow-$NXF_VER-one.jar"
  [ -f "$jar" ] && python -c 'import sys, zipfile
p = dict(l.split("=", 1) for l in zipfile.ZipFile(sys.argv[1]).read("META-INF/groovy-release-info.properties").decode().splitlines() if "=" in l and not l.startswith("#"))
print(p.get("ImplementationVersion", "?"))' "$jar" 2>/dev/null || echo "?"
}
java_version() { java -version 2>&1 | sed -n '1s/.*"\([^"]*\)".*/\1/p' | grep . || echo "?"; }

run_info_header() {
  { echo "date	$(date -u +%Y-%m-%dT%H:%MZ)"
    echo "tree	$pipe ($ref); tests $tests_dir; profile $profile"
    echo "report	$repo/tests/nf_coverage_report.py at $(git -C "$repo" rev-parse --short HEAD)$(git -C "$repo" status --porcelain --untracked-files=no -- tests/nf_coverage_report.py | grep -q . && echo ' + uncommitted changes')"
    echo "versions	nextflow $NXF_VER, groovy $(groovy_version), java $(java_version), $(nf-test version 2>/dev/null | grep -m1 -oE 'nf-test [0-9.]+' || echo nf-test), JaCoCo $jacoco, baseline: empty files (every line of the tree is own code)"
    echo "run	exit	seconds"; } > "$out/RUN_INFO.txt"
}

# a direct pipeline run from its own directory, so the tree's .nextflow/history stays clean
pipeline_run() {   # <set name> <extra args...>
  local name=$1; shift; local d="$out/runs/$name" rc=0 start=$SECONDS
  rm -rf "$d" "$out/exec/$name.exec"; mkdir -p "$d"
  (cd "$d" && NXF_JVM_ARGS=$(agent "$name") nextflow run "$pipe/main.nf" -profile "$profile" \
      --outdir out -w work -ansi-log false "$@" > run.log 2>&1) || rc=$?
  cp "$d/.nextflow.log" "$out/logs/$name.nextflow.log"
  check_scripts_recorded "$out/exec/$name.exec" || rc=1
  note "$name" "$rc" $((SECONDS - start))
  [ "${KEEP_WORK:-0}" = 1 ] || rm -rf "$d/work" "$d/out"
  return $rc
}

nftest_run() {     # <test name>
  local t=$1 rc=0 start=$SECONDS f="$tests_dir/$t.nf.test"
  [ -f "$f" ] || { echo "no such test: $f" >&2; exit 1; }
  rm -rf "$out/nft/$t" "$out/exec/t_$t.exec" "$out"/logs/t_"$t"__*.nextflow.log
  (cd "$pipe" && NFT_WORKDIR="$out/nft/$t" NXF_JVM_ARGS=$(agent "t_$t") \
      nf-test test ${NFT_CONFIG:+-c "$NFT_CONFIG"} --profile "$profile" "${f#$pipe/}" > "$out/logs/t_$t.nftest.log" 2>&1) || rc=$?
  for l in "$out/nft/$t"/tests/*/meta/nextflow.log; do      # the class -> file map of each launch
    if [ -f "$l" ]; then cp "$l" "$out/logs/t_${t}__$(basename "$(dirname "$(dirname "$l")")").nextflow.log"; fi
  done
  check_scripts_recorded "$out/exec/t_$t.exec" || rc=1
  note "t_$t" "$rc" $((SECONDS - start))
  [ "${KEEP_WORK:-0}" = 1 ] || rm -rf "$out/nft/$t"
  return $rc
}

report() {
  tools
  ls "$out"/exec/*.exec >/dev/null 2>&1 || { echo "no coverage data in $out/exec - run first" >&2; exit 1; }
  $cli merge "$out"/exec/*.exec --destfile "$out/all.exec" > /dev/null
  rm -f "$out"/xml/*.xml
  local sets=() e n
  for e in "$out"/exec/*.exec "$out/all.exec"; do
    n=$(basename "$e" .exec)
    $cli report "$e" --classfiles "$out/classes" --xml "$out/xml/$n.xml" > /dev/null
    sets+=("$n")
  done
  local py=(python "$repo/tests/nf_coverage_report.py" --root "$pipe" --dump "$out/classes" --logs "$out/logs/*.nextflow.log" --upstream "$baseline")
  local all=() s
  for s in "${sets[@]}"; do all+=(--xml "$s=$out/xml/$s.xml"); done     # every run set is a column
  "${py[@]}" "${all[@]}" --files --tsv "$out/coverage.tsv" --lcov "all:$out/lcov.info" > "$out/tables.txt"
  "${py[@]}" --xml "all=$out/xml/all.xml" --no-tables --uncovered all > "$out/uncovered.txt"
  local singles; singles=$(printf '%s\n' "${sets[@]}" | grep -v '^all$' | paste -sd,)
  "${py[@]}" "${all[@]}" --no-tables --unique "$singles" > "$out/unique.txt"
  # the same measures per test level: the nf-test type of each test file, pipeline tests split into
  # plan-only (the file passes -preview) and full run
  rm -rf "$out/levels"; mkdir -p "$out/levels"
  local t kind lvl lv=()
  for e in "$out"/exec/t_*.exec; do
    [ -f "$e" ] || continue
    t=$(basename "$e" .exec); t=${t#t_}
    kind=$(grep -m1 -oE '^nextflow_(function|process|workflow|pipeline)' "$tests_dir/$t.nf.test" 2>/dev/null || true)
    case "$kind" in
      nextflow_pipeline) if grep -q -- '-preview' "$tests_dir/$t.nf.test"; then lvl=plan_only; else lvl=full_run; fi ;;
      nextflow_*)        lvl=${kind#nextflow_} ;;
      *)                 continue ;;
    esac
    echo "$e" >> "$out/levels/$lvl.list"
  done
  for lvl in function process workflow plan_only full_run; do
    [ -f "$out/levels/$lvl.list" ] || continue
    $cli merge $(cat "$out/levels/$lvl.list") --destfile "$out/levels/$lvl.exec" > /dev/null
    $cli report "$out/levels/$lvl.exec" --classfiles "$out/classes" --xml "$out/levels/$lvl.xml" > /dev/null
    lv+=(--xml "$lvl=$out/levels/$lvl.xml")
  done
  "${py[@]}" "${lv[@]}" --xml "all=$out/xml/all.xml" > "$out/levels.txt"
  sed -n '/^## Executable lines covered - fork/,/^$/p; /^## Data-driven closures entered - fork/,/^$/p; /^## JaCoCo branch coverage/,/^$/p; /^## Fully covered decision lines/,/^$/p' "$out/tables.txt"
  # with the empty baseline the "fork lines only" totals must equal the all-code totals (files column aside)
  local tot; tot() { sed -n "/^## $1/,/^\$/p" "$out/tables.txt" | grep '^TOTAL' | sed 's/^TOTAL *[0-9]* *//'; }
  if [ "$(tot 'Executable lines covered - all code')" = "$(tot 'Executable lines covered - fork lines only')" ] &&
     [ "$(tot 'Data-driven closures entered - all code')" = "$(tot 'Data-driven closures entered - fork closures only')" ]; then
    echo "check: 'fork lines only' = all code (empty baseline): lines and closures totals identical"
  else
    echo "WARNING: 'fork lines only' totals differ from the all-code totals - the empty baseline did not cover every file" >&2
  fi
  echo "report: $out/tables.txt  levels.txt  uncovered.txt  unique.txt  coverage.tsv  lcov.info"
}

case "$cmd" in
  run)
    for x in nextflow nf-test java javap python curl; do command -v "$x" >/dev/null || { echo "$x not on PATH" >&2; exit 1; }; done
    tools; failed=0
    if [ $# -eq 0 ]; then
      rm -rf "$out"/exec/* "$out"/classes/* "$out"/logs/* "$out"/javap_l.txt "$out"/javap_cl.txt
      run_info_header
      pipeline_run preview -preview || failed=1
      set -- ${BENCH_TESTS:-default}
    fi
    for t in "$@"; do nftest_run "$t" || failed=1; done
    report
    [ "$failed" -eq 0 ] || { echo "a run or test FAILED (see $out/RUN_INFO.txt and logs/) - its coverage is still in the report" >&2; exit 1; }
    ;;
  pipeline)
    [ $# -ge 1 ] || usage
    for x in nextflow java javap python curl; do command -v "$x" >/dev/null || { echo "$x not on PATH" >&2; exit 1; }; done
    tools; [ -f "$out/RUN_INFO.txt" ] || run_info_header
    name=$1; shift; failed=0
    pipeline_run "$name" "$@" || failed=1
    report
    [ "$failed" -eq 0 ] || { echo "the run FAILED (see $out/RUN_INFO.txt and logs/) - its coverage is still in the report" >&2; exit 1; }
    ;;
  report)   report ;;
  annotate)
    [ $# -eq 2 ] || usage
    python "$repo/tests/nf_coverage_report.py" --root "$pipe" --dump "$out/classes" --logs "$out/logs/*.nextflow.log" \
      --upstream "$baseline" --xml "$1=$out/xml/$1.xml" --annotate "$1:$2"
    ;;
  *) usage ;;
esac
