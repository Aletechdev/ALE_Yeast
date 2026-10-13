# How JaCoCo counts branches for Groovy / Nextflow conditions

The measured basis for reading the branch-coverage figure of
[`nextflow_code_coverage.md`](nextflow_code_coverage.md). Probe run 2026-10-13 on the dev VM, against
the coverage data recorded on 2026-10-02 (code `438a9dc`). Sources, scripts and the per-line data are in
[`nextflow_branch_counting/`](nextflow_branch_counting/); build output (classes, `.exec`, XML reports,
`javap` dumps) is not committed and comes back with the commands under [Reproduce](#reproduce).

## In short

JaCoCo reports **2 branches per conditional jump in the bytecode**, and Groovy 4.0.28 emits more jumps
than javac for the same source. Measured, identical under groovyc and inside Nextflow 25.10.4:

- A simple decision (`if (x)`, `x ?: y`, `a ? x : y`, `==`, `in`, `instanceof`, `<`, `>`, one `case`)
  is 2 branches: standard ISTQB decision coverage.
- `&&` / `||` give one pair **per operand** (short-circuit, as in Java), so a compound line is closer to
  condition coverage than to decision coverage. On top of that Groovy **materialises the boolean and
  tests it again**: one extra pair when the compound feeds an `if` / ternary, one extra pair per operator
  beyond the first (left-nesting), and one extra pair per `!`. `if (a && b)` is 6 (Java 4),
  `if (a && b && c)` is 10 (Java 6), `if (!a)` is 4 (Java 2), `if (!(a && b))` is 8 (Java 4).
- `?.` produces **no branch at all** (the null check is inside the invokedynamic call site).
- `switch` is 2 per `case` line and nothing for `default` (an `isCase` chain, no `tableswitch`).
- Nextflow's `branch` operator turns a `name: true` default into a jump on a constant, attributed to the
  previous criterion's line: 2 branches, **one of which can never be taken**. Five such defaults in fork code,
  four of them counted; the fifth sits in a criteria closure compiled without a line table and is invisible.
- Everything else Groovy generates (`$getStaticMetaClass`, with two jumps) is filtered out by JaCoCo.

On the recorded fork data (`output_coverage/`, code `438a9dc`) the compound lines are 78 of the 254
branch-carrying lines but 530 of the 920 branches (57.6 %). The compiler artefacts are an inferred
192 of 920 (20.9 %). They add no information, since they are covered exactly when the operand branches
are, so they shift the headline ratio only a little; they do give a two-operand `if` three times the
weight of a plain one instead of twice. Recommendation: **footnote, do not adjust** (reasons at the end).

## Set-up (all measured)

| Item | Value |
|---|---|
| Groovy bundled with Nextflow 25.10.4 | **4.0.28** (`META-INF/groovy-release-info.properties` in `~/.nextflow/framework/25.10.4/nextflow-25.10.4-one.jar`; a shadow jar, Groovy is merged in, there is no separate groovy jar) |
| groovyc | not installed on the VM; `org.codehaus.groovy.tools.FileSystemCompiler` run from that jar is the same compiler (`java -cp nextflow-25.10.4-one.jar org.codehaus.groovy.tools.FileSystemCompiler -d classes Probe.groovy`) |
| JaCoCo | 0.8.12 agent + CLI from `output_coverage/tools/` (what `tests/nf_coverage.sh` uses) |
| Java | OpenJDK 17.0.15 (nf-env); javac 17 for the Java reference |
| Nextflow run | `NXF_VER=25.10.4`, `NXF_JVM_ARGS` with the agent string of `tests/nf_coverage.sh`: `destfile=…,classdumpdir=…,inclnolocationclasses=true,includes=Script*:_nf_config_*`; report with `jacococli report --classfiles <dump> --xml` |
| Recorded pipeline data | `output_coverage/` from 2026-10-02, code `438a9dc` (`RUN_INFO.txt`, doc Provenance). Since then only `nextflow.config` and `modules/local/generate_index/main.nf` changed; Step 3 reads sources with `git show 438a9dc:<path>` so lines match the recorded classes |

Files, all in `nextflow_branch_counting/`: `Probe.groovy` (step 1), `ProbeJ.java` (Java reference),
`main.nf` (step 2, the same functions as a Nextflow script) and `probe.config` (the same operators in a
`-c` config file, run with that `main.nf`), `xml_lines.py` (per-line mb/cb from a JaCoCo XML),
`make_branch_dump.py`, which writes `branch_dump.py`: **a modified copy of `tests/nf_coverage_report.py`**
with three additions and nothing removed (`--at-commit REV` reads every source from `git show REV:path`,
`--branch-dump SET` prints one row per line with branches, `--fork-dump` prints every fork line); the
pipeline script itself is untouched, and the copy is regenerated after any change to it.
`branch_lines_all.tsv` is the step-3 data (one row per line with branches, fork and upstream: file, line,
mb, cb, fork, group, text; 250 KB), `classify.py` and `artefacts.py` read it. The fork-line dump
(`--fork-dump`, 290 KB) is not committed.

## Step 1 + Step 2: construct table

"Outcomes by hand": decision outcomes / condition outcomes (each atomic condition true and false).
Java = javac 17 on `ProbeJ.java`. Groovy = groovyc 4.0.28 on `Probe.groovy`.
Nextflow = the same functions in `main.nf`, class `Script_<hash>`. Numbers are JaCoCo's
`mb + cb` for the line that holds the decision.

| Construct (one per function, decision on its own line) | Outcomes by hand | JaCoCo Java | JaCoCo Groovy | JaCoCo Nextflow | Groovy = Nextflow |
|---|---|---|---|---|---|
| `if (a)` | 2 / 2 | 2 | 2 | 2 | yes |
| `if (a && b)` | 2 / 4 | 4 | **6** | 6 | yes |
| `if (a \|\| b)` | 2 / 4 | 4 | **6** | 6 | yes |
| `if (a && b && c)` | 2 / 6 | 6 | **10** | 10 | yes |
| `x ?: y` (Elvis) | 2 / 2 | 2 (`x != null ? x : y`) | 2 | 2 | yes |
| `x ?: y ?: z` (chained Elvis) | 4 / 4 (two decisions) | n/a | 4 | 4 | yes |
| `a ? x : y` (ternary) | 2 / 2 | 2 | 2 | 2 | yes |
| `x?.size()` (safe navigation) | 2 / 2 | n/a | **0** | 0 | yes |
| closure `{ p, q -> if (p && q) … }` | 2 / 4 | 4 (lambda) | 6 | 6 | yes |
| `switch` with 3 cases | 4 (3 cases + default) | 4, on the `switch` line | **6**: 2 per `case` line, 0 for default | 6 | yes |
| `if (!a)` | 2 / 2 | 2 | **4** | 4 | yes |
| `if (a == b)` | 2 / 2 | 2 | 2 | 2 (other bytecode, see below) | yes |
| `if (a in [1, 2])` | 2 / 2 | n/a | 2 | 2 | yes |
| `if (a instanceof String)` | 2 / 2 | n/a | 2 | 2 | yes |
| `if (a > 1)` | 2 / 2 | n/a | 2 | 2 (other bytecode) | yes |
| `r = a && b` (value, no `if`) | 4 condition | 4 | 4 | 4 | yes |
| `r = a && b && c` (value) | 6 condition | 6 | **8** | 8 | yes |
| `if (a \|\| b \|\| c)` | 2 / 6 | 6 | **10** | 10 | yes |
| `if (!(a && b))` | 2 / 4 | 4 | **8** | 8 | yes |
| `r = a && b ? 1 : 0` | 2 / 4 | 4 | **6** | 6 | yes |
| Nextflow `.filter { a, b -> if (a && b) … }` | 2 / 4 | | | 6 | same as a function |
| Nextflow `.map { a, b -> a ?: b }` | 2 / 2 | | | 2 | same as a function |
| config `if (params.pa && params.pb)` (top level) | 2 / 4 | | | 6 | same as `.nf` |
| config `ext.args = { a && b ? 'x' : 'y' }` | 2 / 4 | | | 6 | same |
| config `ext.when = { a \|\| b }` | 4 condition | | | 4 | same |
| config `ext.prefix = { x ?: y ?: 'z' }` | 4 | | | 4 | same |

Coverage side (how the one-way drives came out) behaves as expected and identically in both builds:
`or2(false,false)` 3/6, `and3(T,T,T)` 5/10, `elvis3('x',…)` 1/4 (the second `?:` never evaluated, 0/2),
`sw(1); sw(2)` 2/2, 1/2, 0/2 on the three `case` lines, `safeNav` nothing to cover.

**Rule that reproduces every row** (and 50 of the 59 "clean" fork lines, see Step 3):
branches on a line = 2 × conditional jumps, where the jumps are one per atomic test (an `if` on one
operand, each `&&` / `||` operand, `?:`, `? :`, `case`) **plus one re-test per materialised boolean**:
each operator beyond the first in a chain, each `!`, and one more when a compound or negated boolean is
the test of an `if` / `while` / ternary. For a chain of n operands in an `if` that is 2n − 1 jumps =
4n − 2 branches (Java: 2n); as a value, 2n − 2 jumps = 4n − 4 (Java: 2n).

### Step 2 versus Step 1: differences found

- **Branch counts: none.** Every line matches. The script class is `Script_<hash>` (a `BaseScript`), the
  functions are its instance methods, the workflow body is `_runScript_closure2` (0 branches), operator
  closures are nested `_closureN` classes with the same counts as a function. A `-c` config file compiles
  to `_nf_config_<hash>` with the same counts (`probe.config`).
- **Bytecode: identical for 18 of 20 methods** after dropping offsets and constant-pool indexes. The two
  that differ, `==` and `>`, are Nextflow's comparison rewrite through `nextflow.util.LangHelpers` (an
  `invokedynamic invoke` + `cast` instead of `ScriptBytecodeAdapter.compareEqual`); more instructions,
  the same single `ifeq`, so no effect on branches.
- **Not reproduced in the probe, found in the recorded data:** the `branch` operator default (below).

## Compiler-generated branches, with bytecode

All excerpts from `javap -c -l -p` of the groovyc build of `Probe.groovy` (not committed, see Reproduce); the Nextflow dump is instruction-for-instruction the same.

**1. `&&` materialise-then-retest** (`if (a && b)`, 3 jumps → 6 branches; javac emits only the first two):
```
       1: invokestatic  DefaultTypeTransformation.booleanUnbox:(Ljava/lang/Object;)Z
       4: ifeq          18          // a false  -> jump 1 (operand a)
       8: invokestatic  DefaultTypeTransformation.booleanUnbox:(Ljava/lang/Object;)Z
      11: ifeq          18          // b false  -> jump 2 (operand b)
      14: iconst_1
      15: goto          19
      18: iconst_0                  // the boolean is materialised ...
      19: ifeq          27          // ... and tested again -> jump 3 (artefact, 2 branches)
```
`r = a && b` stops after offset 18 (4 branches). `if (a && b && c)` nests `(a && b)` as the left operand:
its result is materialised and re-tested at `19: ifeq 33` before `c`, then the whole is re-tested by the
`if` (5 jumps, 10 branches). `r = a && b && c` keeps the nesting re-test and drops the `if` one (8).

**2. `!` materialises too** (`if (!a)`, 2 jumps → 4 branches; javac: 1 jump):
```
       1: invokedynamic cast:(Ljava/lang/Object;)Z
       6: ifne          13          // jump 1: the negation itself
       9: iconst_1
      10: goto          14
      13: iconst_0
      14: ifeq          22          // jump 2: the if re-tests the materialised !a
```
`if (!(a && b))` stacks the three: operands (2 jumps), `!` (1), `if` (1) → 8.

**3. `switch` is an `isCase` chain**, one `ifeq` per `case`, attributed to the `case` line; `default` has
no jump. (The `nop nop athrow` after each `areturn` is dead code JaCoCo counts as missed *instructions*
on the `return` line; it does not touch lines or branches.)
```
       7: invokestatic  ScriptBytecodeAdapter.isCase:(Ljava/lang/Object;Ljava/lang/Object;)Z
      10: ifeq          19          // case 1
      13: ldc           String one
      15: areturn
      16: nop / nop / athrow
      24: invokestatic  ScriptBytecodeAdapter.isCase ...
      27: ifeq          36          // case 2
```

**4. `?.` has no jump**: `x?.size()` is one `invokedynamic invoke` with the safe-navigation flag; the null
check runs inside the call site.
```
       1: invokedynamic invoke:(Ljava/lang/Object;)Ljava/lang/Object;
       6: astore_2
```

**5. Nextflow `branch` operator default.** From the recorded dump,
`subworkflows/local/mutation_report/main.nf:304-305` (`multi: vcfs.size() > 1` / `single: true`), class
`Script_737a811b28110a96$…$_closure64.doCall`. The rewrite emits one test per criterion; the `true`
default becomes `iconst_1; ifeq`, whose false side is unreachable, and the line table keeps only the
first criterion's line (304; 305 is absent), so the line reads 4 branches, at most 3 coverable:
```
      15: invokedynamic cast:(Ljava/lang/Object;)Z
      20: ifeq          51          // multi: vcfs.size() > 1
      42: invokedynamic init:(... TokenBranchChoice ...)   47: areturn
      51: iconst_1
      52: ifeq          80          // single: true  -> one branch that can never be taken
      74: invokedynamic init:(... TokenBranchChoice ...)   79: areturn
      80: aconst_null   81: areturn
```
Fork code has five such defaults (`mutation_report/main.nf:177, 272, 305, 410, 471`). Four are counted, on
the previous criterion's line: 176, 304, 409 and 470 show `4` where every other criterion shows `2`, 8
branches of which 4 are uncoverable; 176, 409 and 470 read 3/4 covered and can never be fully covered. The fifth
(272) is the case below. Since 2026-10-13 `tests/nf_coverage_report.py` excludes the untakeable side of
these jumps from every branch view (found as `iconst_0` / `iconst_1` straight into `ifeq` / `ifne` with
the jump not a jump target; `--no-constant-filter` restores JaCoCo's raw numbers, which is what
`branch_lines_all.tsv` holds).

**5b. A criteria closure with no line table.** The `branch` at `mutation_report/main.nf:270-273`
(`ch_collapsed = COLLAPSE_SV_PAIRS.out.vcf.branch { meta, vcf -> tiddit: … / other: true }`) ran (line
270 reads `+`), its criteria class `…$_closure22$_closure63` is in the dump with both tests (`ifeq` on
`meta.caller == 'tiddit'`, then `iconst_1; ifeq` for the default), yet the class has **zero
LineNumberTable entries**. JaCoCo attributes its instructions and 4 branches to no line, so lines 271-272
own no bytecode, the closure is not counted by the closure measure either (it needs a first line), and
the uncoverable branch is absent from the denominator. It is the only such case in the recorded data:
of 2 864 classes in the dump, 136 have no line table, 134 of them Nextflow's wrapper closures around
`branch` / `multiMap` bodies (no user code) and one the script-level `_runScript_closure1`. Why this one
closure lost its lines (the other four `branch` sites kept them) was not pursued; the Nextflow `branch`
transform is the only difference between it and a plain closure.

**6. Filtered, not counted.** Groovy's generated `$getStaticMetaClass` holds an `if_acmpeq` and an
`ifnonnull`; the method is absent from JaCoCo's XML (method list of the probe class: the probe
functions, `<init>`, `main`, `doCall` only). JaCoCo 0.8.12 ships no Groovy-specific filter; its
`SyntheticFilter` / `AnnotationGeneratedFilter` (`@groovy.transform.Generated`) take care of it.

## Step 3: size of the effect on the recorded fork numbers

Source: `nextflow_branch_counting/branch_lines_all.tsv`, produced by `branch_dump.py --at-commit 438a9dc` from
`output_coverage/xml/all.xml` + `classes/` + `logs/`. **Tie-out:** fork rows sum to 514/920 and every
group row equals the branch table of `tables.txt` (titled *Branches taken - fork lines only* in the
recorded file, *JaCoCo branch coverage* since; conf/modules 133/194, modules/local
81/236, modules/nf-core 9/34, subworkflows/local 220/342, subworkflows/nf-core 4/8, workflows 67/106);
254 fork lines carry branches, the denominator of *Fully covered decision lines*; fork executable lines
1106 per file as in the table. Read against the working tree instead, the dump loses four
`nextflow.config` lines (all upstream, so the fork totals do not move) and prints the "unmapped config
class" message the memory note describes.

### Where the 920 come from (measured; `classify.py`)

| Construct on the line | Lines | Branches | Covered | Share of 920 |
|---|---|---|---|---|
| compound: `&&` / `\|\|` on the line (79 fork lines have one; 78 carry branches, 95 operators) | 78 | 530 | 248 | 57.6 % |
| plain `if` / `case` / `branch` criterion / other, no operator | 68 | 160 | 127 | 17.4 % |
| ternary `? :` | 66 | 140 | 102 | 15.2 % |
| single `?:` | 39 | 78 | 32 | 8.5 % |
| chained `?:` (2 or more) | 3 | 12 | 5 | 1.3 % |
| `?.` | 0 | 0 | 0 | 0 (no fork line contains `?.`: `grep` over modules/local, subworkflows/local, workflows, conf/modules, main.nf) |

The three chained-Elvis lines are `bam_joint_calling_germline_gatk/main.nf:149` and `:158`
(`recal_vcf ?: fallback_vcf ?: joint_vcf`, 4 each) and `split_joint_vcf/main.nf:29` (4). The
`task.ext.when == null || task.ext.when` guard is 21 lines × 4 = 84 branches (9.1 %), 17 covered.
Compound lines are 31 % of the lines and 58 % of the branches: a two-operand `if` weighs 6 against a
plain `if`'s 2.

### Artefact share (inferred from the rule, validated on the measured totals; `artefacts.py`)

Validation: on the 49 fork lines with exactly one `&&`/`||` and no `?:`/ternary, the rule predicts the
measured total on 44; on the 10 lines with two or more operators, on 6. The 9 misses are lines that carry
more than the chain (a one-line closure on the same line, a second statement, or an expression continued
from the previous line, e.g. `mutation_report/main.nf:152-153`).

Applied to all 254 lines: **192 of 920 branches (20.9 %) are re-tests of an already computed boolean**,
on 50 lines: 84 from the `if` / ternary re-test of a compound or negated condition, 74 from `!` (32 fork
lines carry a `!`), 34 from left-nesting of 3+ operand chains. Not included: the 8 branches of the four
counted `branch` defaults (4 uncoverable). Without the 192 the denominator would be about 728. The ratio moves
less than the denominator: an artefact pair is covered whenever its operand pairs are, and sometimes when
they are not, so the headline 514/920 = 55.9 % would read roughly 58-61 % (inferred; JaCoCo's XML has
per-line counts only, so the exact per-jump split is not available without a bytecode-level analysis).

### The two unpublished numbers in `output_coverage/tables.txt`

| Table | preview | qc_only | e2e | all |
|---|---|---|---|---|
| Named functions entered - fork functions only | 8/8 100 % | 8/8 | 8/8 | 8/8 |
| JaCoCo branch coverage - fork lines only (per conditional jump); titled *Branches taken* in the recorded file | 162/920 17.6 % | 197/920 21.4 % | 384/920 41.7 % | 514/920 55.9 % |

The 8 functions are 7 in `subworkflows/local` (one file, `utils_nfcore_sarek_pipeline`) and 1 in
`subworkflows/nf-core` (`utils_nfcore_pipeline`); all are called while the DAG is built, so a plan-only
run already enters every one and the row cannot distinguish the sets. The branch row is the number this
probe is about; at the time of the probe the doc published *Fully covered decision lines* (80/254, 31.5 %;
titled *Conditions seen every way* in the recorded file) instead.

## Conclusion

The reported "branch coverage" is **per conditional jump in Groovy bytecode**. For the simple decisions
that make up 42 % of the fork denominator it equals ISTQB decision coverage (2 per decision). For the
58 % on `&&` / `||` lines it is per operand, closer to condition coverage, exactly as JaCoCo behaves on
Java, **plus compiler artefacts**: Groovy materialises every compound or negated boolean and tests it
again, which adds about a fifth of the fork denominator (192 of 920, inferred; the rule is measured on 26
constructs and reproduces 50 of 59 clean fork lines). The artefacts carry no information of their own
(covered iff the operands are) but triple the weight of a two-operand `if` relative to a plain one, and
let partially covered compound lines read a little higher than their operands justify. Two constructs
are miscounted outright: `?.` contributes nothing, and a `branch` default `name: true` contributes a
branch no run can take (4 counted in fork code; a fifth `branch` closure lost its line table and is
invisible to every per-line measure). Nextflow adds nothing of its own beyond the `branch` transform: the
bytecode is groovyc's, and config files count the same way.

**Footnote rather than adjust.** A correction would need per-jump data and a bytecode pattern match
that tracks Groovy's code generation across versions, for a shift of a few points in a number the doc
already declines to publish; and *Fully covered decision lines*, the measure the doc does publish, is per
line, so operator weighting does not touch it. Three concrete footnotes, if the owner agrees:

1. In the doc's "Three measures" table, after "A plain `if (flag)` has two branches": *JaCoCo counts two
   per conditional jump; Groovy gives `if (a && b)` six (one pair per operand, one for re-testing the
   result), `if (!a)` four, `x?.y` none.* Same for `uncovered.txt`'s `b m/n` column.
2. In Limits: *the `branch` operator's `name: true` default adds one branch that can never be taken,
   on the previous criterion's line; four fork lines (`mutation_report/main.nf:176, 304, 409, 470`)
   can therefore never be fully covered. One `branch` criteria closure (`:270-273`) was compiled
   without line numbers and is outside every per-line count.*
3. If the branch table is ever published: label it "JaCoCo branch coverage (per conditional jump, Groovy
   4.0.28)", not plain "branch coverage".

## Reproduce

All from the repo root, in `nf-env`, with `output_coverage/tools/` populated by a previous
`tests/nf_coverage.sh` run (JaCoCo 0.8.12 and the sarek 3.5.1 baseline). `W` is a scratch directory for
the build output.

```bash
P=docs/dev-practices/nextflow_branch_counting; T=$PWD/output_coverage/tools; W=/tmp/branch_probe; mkdir -p $W/{g,j,nf}
J=~/.nextflow/framework/25.10.4/nextflow-25.10.4-one.jar          # Groovy 4.0.28 is inside this jar
# Step 1, plain Groovy (seconds): groovyc = FileSystemCompiler from the Nextflow jar
java -cp $J org.codehaus.groovy.tools.FileSystemCompiler -d $W/g/classes $P/Probe.groovy
java -javaagent:$T/jacocoagent.jar=destfile=$W/g/probe.exec,includes=Probe* -cp $W/g/classes:$J Probe
java -jar $T/jacococli.jar report $W/g/probe.exec --classfiles $W/g/classes --sourcefiles $P --xml $W/g/probe.xml
python $P/xml_lines.py $W/g/probe.xml $P/Probe.groovy
javap -c -l -p $W/g/classes/Probe.class > $W/g/javap_Probe.txt                      # the bytecode excerpts
# Java reference (seconds)
javac -g -d $W/j/classes $P/ProbeJ.java
java -javaagent:$T/jacocoagent.jar=destfile=$W/j/probe.exec,includes=ProbeJ* -cp $W/j/classes ProbeJ
java -jar $T/jacococli.jar report $W/j/probe.exec --classfiles $W/j/classes --sourcefiles $P --xml $W/j/probe.xml
python $P/xml_lines.py $W/j/probe.xml $P/ProbeJ.java
# Step 2, inside Nextflow (about 20 s; add  -c $P/probe.config  for the config-file probe, which then
# shows up as a second sourcefile, _nf_config_<hash>, in the same XML)
( cd $W/nf && NXF_VER=25.10.4 NXF_JVM_ARGS="-javaagent:$T/jacocoagent.jar=destfile=$W/nf/probe.exec,classdumpdir=$W/nf/classes,inclnolocationclasses=true,includes=Script*:_nf_config_*" \
    nextflow run $OLDPWD/$P/main.nf -ansi-log false )
java -jar $T/jacococli.jar report $W/nf/probe.exec --classfiles $W/nf/classes --xml $W/nf/probe.xml
python $P/xml_lines.py $W/nf/probe.xml $P/main.nf
# Step 3, the recorded pipeline data (about 20 s): regenerate the copy, then the dump and the two analyses
python $P/make_branch_dump.py
python $P/branch_dump.py --dump output_coverage/classes --logs 'output_coverage/logs/*.nextflow.log' \
  --upstream output_coverage/tools/sarek-3.5.1 --xml all=output_coverage/xml/all.xml --no-tables --at-commit 438a9dc \
  --no-constant-filter --branch-dump all > $W/branch_lines_all.tsv       # raw JaCoCo counts, as the TSV was recorded
python $P/branch_dump.py --dump output_coverage/classes --logs 'output_coverage/logs/*.nextflow.log' \
  --upstream output_coverage/tools/sarek-3.5.1 --xml all=output_coverage/xml/all.xml --no-tables --at-commit 438a9dc \
  --fork-dump > $W/fork_lines.tsv
python $P/classify.py $W/branch_lines_all.tsv $W/fork_lines.tsv
python $P/artefacts.py $W/branch_lines_all.tsv
```
