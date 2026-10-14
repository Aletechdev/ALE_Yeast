#!/usr/bin/env bash
# Nextflow 26.x companion of ../main.nf (nextflow_branch_counting.md): runs this strict-syntax probe under
# the JaCoCo agent, once with the includes filter of tests/nf_coverage.sh and once without, then reports.
# usage: run_probe.sh <NXF_VER>   -- writes out/<ver>/ (class dump, .exec, probe.xml, lines_*.txt, javap.txt; not committed)
# needs: nf-env (java, python), output_coverage/tools/ from `tests/nf_coverage.sh` (jacocoagent.jar, jacococli.jar)
set -u
ver=$1
here=$(cd "$(dirname "$0")" && pwd)
repo=$(cd "$here/../../../.." && pwd)
tools=$repo/output_coverage/tools
out=$here/out/$ver; rm -rf "$out"; mkdir -p "$out/classes" "$out/run_incl" "$out/run_noincl"
agent="-javaagent:$tools/jacocoagent.jar=destfile=$out/probe.exec,classdumpdir=$out/classes,inclnolocationclasses=true,includes=Script*:_nf_config_*"
agent_noincl="-javaagent:$tools/jacocoagent.jar=destfile=$out/probe_noincl.exec,classdumpdir=$out/classes_noincl,inclnolocationclasses=true"
export NXF_VER=$ver
echo "== run with includes filter"
(cd "$out/run_incl" && NXF_JVM_ARGS="$agent" nextflow run "$here/main.nf" -c "$here/probe.config" > stdout.txt 2> stderr.txt; echo "exit=$?" | tee exit.txt)
tail -5 "$out/run_incl/stdout.txt"
echo "== run WITHOUT includes filter"
(cd "$out/run_noincl" && NXF_JVM_ARGS="$agent_noincl" nextflow run "$here/main.nf" -c "$here/probe.config" > stdout.txt 2> stderr.txt; echo "exit=$?" | tee exit.txt)
tail -3 "$out/run_noincl/stdout.txt"; grep -m3 -i "NoClassDefFound\|Exception\|error" "$out/run_noincl/stderr.txt" "$out/run_noincl/stdout.txt" "$out/run_noincl/.nextflow.log" 2>/dev/null | head -5
echo "== dumped classes"
ls "$out/classes" | head -20; echo "count: $(ls "$out/classes" | wc -l)"
echo "== log mapping lines"
grep -E "Script_\w+: /" "$out/run_incl/.nextflow.log" | head; grep -c "_nf_config_" "$out/run_incl/.nextflow.log"
echo "== report"
java -jar "$tools/jacococli.jar" report "$out/probe.exec" --classfiles "$out/classes" --xml "$out/probe.xml" --html "$out/html" > /dev/null && echo xml ok
echo "== per-line main.nf"
python "$here/../xml_lines.py" "$out/probe.xml" "$here/main.nf" | tee "$out/lines_main.txt"
echo "== per-line probe.config"
python "$here/../xml_lines.py" "$out/probe.xml" "$here/probe.config" | grep -v "^# method" | tee "$out/lines_config.txt"
echo "== javap of dumped classes"
(cd "$out/classes" && javap -c -l -p $(find . -name '*.class' | sed 's#^\./##') > "$out/javap.txt" 2>/dev/null); wc -l "$out/javap.txt"
