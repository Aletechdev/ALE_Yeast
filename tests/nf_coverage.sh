#!/bin/bash
# Coverage of the pipeline's own Nextflow code (.nf and .config files) by the owned test suite
# (docs/dev-practices/nextflow_code_coverage.md: what is measured, how to read it, what it cannot show).
#
# A JaCoCo agent is attached to the Nextflow HEAD JVM (NXF_JVM_ARGS), where every pipeline script and
# config file runs as compiled Groovy. Tasks, containers and the shell inside `script:` blocks are not
# seen. A measurement, not a test: it asserts nothing and is not part of the commit gate.
#
#   tests/nf_coverage.sh run                  everything, about 35 min on the dev VM: a plan-only run
#                                             (-preview), a --qc_only run, then every tests/*.nf.test,
#                                             each under the agent; then the report
#   tests/nf_coverage.sh run <test> [...]     only these test files (names without .nf.test), added to
#                                             the data already there; then the report
#   tests/nf_coverage.sh report               rebuild the report from the recorded data
#   tests/nf_coverage.sh annotate <set> <path-suffix>
#                                             one source file line by line, e.g.  annotate all workflows/sarek/main.nf
#                                             (sets: all, preview, qc_only, e2e, t_<test>)
#
# Output: $COV_DIR, default output_coverage/ at the repo root (gitignored):
#   tables.txt     lines / closures / branches per code group, for a plan-only run, the QC-only run,
#                  the e2e alone and everything merged; all code and fork lines only
#   uncovered.txt  fork lines, closures and one-sided conditions that nothing executed
#   levels.txt     the same tables per test level: process, workflow, plan-only pipeline, full-run pipeline
#   unique.txt     what each test file covers that no other does
#   coverage.tsv   per-file counts          lcov.info  for editor gutters / genhtml / Codecov
#   RUN_INFO.txt   commit, versions, the result and duration of every run
#   exec/ classes/ logs/ xml/               the raw data the report is built from
#
# A full `run` starts from an empty $COV_DIR/exec and classes; a partial run adds to them, so after a
# change to pipeline code do a full run (two versions of one class make the report step fail).
# A failing test still records coverage; it is listed in RUN_INFO.txt and the script exits 1.
# Requires on PATH: nextflow, nf-test, java + javap (JDK), python, curl; docker; the local test data
# (data/ottilie, see README). First use downloads JaCoCo and the pristine sarek tree into $COV_DIR/tools.
set -euo pipefail

here=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
export NXF_VER=${NXF_VER:-25.10.4}
out=${COV_DIR:-$here/output_coverage}
jacoco=0.8.12
upstream=3.5.1
cmd=${1:-}; [ $# -gt 0 ] && shift

usage() { sed -n '2,/^set -euo/p' "$0" | sed '$d; s/^# \{0,1\}//'; exit 1; }
[ -n "$cmd" ] || usage

mkdir -p "$out"/{tools,exec,classes,logs,xml,runs}
cli="java -jar $out/tools/jacococli.jar"

tools() {
  for t in runtime:agent nodeps:cli; do
    [ -s "$out/tools/jacoco${t#*:}.jar" ] && continue
    curl -fsSL -o "$out/tools/jacoco${t#*:}.jar" \
      "https://repo1.maven.org/maven2/org/jacoco/org.jacoco.${t#*:}/$jacoco/org.jacoco.${t#*:}-$jacoco-${t%:*}.jar"
  done
  if [ ! -d "$out/tools/sarek-$upstream" ]; then      # the baseline for "fork lines"
    mkdir -p "$out/tools/sarek-$upstream"
    curl -fsSL "https://github.com/nf-core/sarek/archive/refs/tags/$upstream.tar.gz" | tar xz -C "$out/tools/sarek-$upstream" --strip-components=1
  fi
}

# The two class-name patterns cover every pipeline script and config file: Script_<hash> (.nf),
# Script<MD5> (includeConfig'd files) and _nf_config_<hash> (nextflow.config, -c files). Nextflow's own
# classes must stay uninstrumented: instrumenting everything crashes the launcher.
agent() { echo "-javaagent:$out/tools/jacocoagent.jar=destfile=$out/exec/$1.exec,classdumpdir=$out/classes,inclnolocationclasses=true,includes=Script*:_nf_config_*"; }

note() { printf '%s\t%s\t%s\n' "$1" "$2" "$3" >> "$out/RUN_INFO.txt"; echo "  $1: exit $2, ${3}s"; }

# a direct pipeline run from its own directory, so the repo's .nextflow/history stays clean
pipeline_run() {   # <set name> <extra args...>
  local name=$1; shift; local d="$out/runs/$name" rc=0 start=$SECONDS
  rm -rf "$d" "$out/exec/$name.exec"; mkdir -p "$d"
  (cd "$d" && NXF_JVM_ARGS=$(agent "$name") nextflow run "$here/main.nf" -profile ottilie_test,docker \
      -c "$here/tests/ottilie_nftest_resources.config" --outdir out -w work -ansi-log false "$@" > run.log 2>&1) || rc=$?
  cp "$d/.nextflow.log" "$out/logs/$name.nextflow.log"
  note "$name" "$rc" $((SECONDS - start))
  [ "${KEEP_WORK:-0}" = 1 ] || rm -rf "$d/work" "$d/out"
  return $rc
}

nftest_run() {     # <test name>
  local t=$1 rc=0 start=$SECONDS
  [ -f "$here/tests/$t.nf.test" ] || { echo "no such test: tests/$t.nf.test" >&2; exit 1; }
  rm -rf "$out/nft/$t" "$out/exec/t_$t.exec" "$out"/logs/t_"$t"__*.nextflow.log
  (cd "$here" && NFT_WORKDIR="$out/nft/$t" NXF_JVM_ARGS=$(agent "t_$t") \
      nf-test test -c tests/nf-test-ottilie.config "tests/$t.nf.test" > "$out/logs/t_$t.nftest.log" 2>&1) || rc=$?
  for l in "$out/nft/$t"/tests/*/meta/nextflow.log; do      # the class -> file map of each launch
    if [ -f "$l" ]; then cp "$l" "$out/logs/t_${t}__$(basename "$(dirname "$(dirname "$l")")").nextflow.log"; fi
  done
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
  local py=(python "$here/tests/nf_coverage_report.py" --dump "$out/classes" --logs "$out/logs/*.nextflow.log" --upstream "$out/tools/sarek-$upstream")
  local head=() all=() s
  for s in preview qc_only t_ottilie_e2e all; do        # the headline columns, when recorded
    [ -f "$out/xml/$s.xml" ] && head+=(--xml "$( [ "$s" = t_ottilie_e2e ] && echo e2e || echo "$s" )=$out/xml/$s.xml")
  done
  for s in "${sets[@]}"; do all+=(--xml "$s=$out/xml/$s.xml"); done
  "${py[@]}" "${head[@]}" --files --tsv "$out/coverage.tsv" --lcov "all:$out/lcov.info" > "$out/tables.txt"
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
    kind=$(grep -m1 -oE '^nextflow_(function|process|workflow|pipeline)' "$here/tests/$t.nf.test" 2>/dev/null || true)
    case "$kind" in
      nextflow_pipeline) if grep -q -- '-preview' "$here/tests/$t.nf.test"; then lvl=plan_only; else lvl=full_run; fi ;;
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
  sed -n '/^## Executable lines covered - fork/,/^$/p; /^## Data-driven closures entered - fork/,/^$/p; /^## Conditions seen every way/,/^$/p' "$out/tables.txt"
  echo "report: $out/tables.txt  levels.txt  uncovered.txt  unique.txt  coverage.tsv  lcov.info"
}

case "$cmd" in
  run)
    for x in nextflow nf-test java javap python curl; do command -v "$x" >/dev/null || { echo "$x not on PATH" >&2; exit 1; }; done
    tools; failed=0
    if [ $# -eq 0 ]; then
      rm -rf "$out"/exec/* "$out"/classes/* "$out"/logs/* "$out"/javap_l.txt
      { echo "date	$(date -u +%Y-%m-%dT%H:%MZ)"
        echo "commit	$(git -C "$here" rev-parse --short HEAD)$(git -C "$here" status --porcelain --untracked-files=no | grep -q . && echo ' + uncommitted changes')"
        echo "versions	nextflow $NXF_VER, $(nf-test version 2>/dev/null | grep -m1 -oE 'nf-test [0-9.]+' || echo nf-test), JaCoCo $jacoco, fork baseline sarek $upstream"
        echo "run	exit	seconds"; } > "$out/RUN_INFO.txt"
      pipeline_run preview -preview || failed=1
      pipeline_run qc_only --qc_only || failed=1
      set -- $(cd "$here/tests" && ls *.nf.test | sed 's/\.nf\.test$//')
    fi
    for t in "$@"; do nftest_run "$t" || failed=1; done
    report
    [ "$failed" -eq 0 ] || { echo "a run or test FAILED (see $out/RUN_INFO.txt and logs/) - its coverage is still in the report" >&2; exit 1; }
    ;;
  report)   report ;;
  annotate)
    [ $# -eq 2 ] || usage
    s=$1; [ "$s" = e2e ] && s=t_ottilie_e2e
    python "$here/tests/nf_coverage_report.py" --dump "$out/classes" --logs "$out/logs/*.nextflow.log" \
      --upstream "$out/tools/sarek-$upstream" --xml "$1=$out/xml/$s.xml" --annotate "$1:$2"
    ;;
  *) usage ;;
esac
