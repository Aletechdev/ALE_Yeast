# Code coverage of the Nextflow code (JaCoCo on the head JVM)

Which lines of our `.nf` and `.config` files does the test suite actually execute? This page records
how that is measured, what the first measurement found, and what the numbers cannot tell.

> **Status (2026-10-02): a measurement, not a gate.** `tests/nf_coverage.sh run` produces the report
> in about 35 minutes. Nothing in the commit gate or CI depends on it, and no threshold is proposed.
> Every number on this page comes from one run (see [Provenance](#provenance)) and is labelled
> *measured*, *inferred* or *assumed* where the difference matters
> ([`testing_best_practices.md` §13](testing_best_practices.md#13-benchmark-claims--provenance-evidence-labels-script-before-numbers)).

## In short

- **It works.** A JaCoCo agent on the Nextflow head JVM records per-line execution of every pipeline
  script and config file, through `nf-test` as well as through a direct `nextflow run`. All nine
  test files pass with the agent attached, the e2e contract test against its snapshot.
- **Line coverage alone says little.** A plan-only run (`-preview`, zero tasks) already executes
  71 % of our own lines, because workflow code runs once at start-up to wire the steps together.
- **Closure coverage separates wiring from work.** Counting only the closures that run when data
  arrives, the same plan-only run scores 2 % and the whole suite 80 %.
- **Branch counters show which conditions were only ever seen one way.** 80 of our 254 conditions
  have been exercised in every direction. This is the measured cousin of the "option coverage" that
  [issue #13](https://github.com/Aletechdev/ALE_Yeast/issues/13) proposes, not the same count: option
  coverage counts the launch form's switches, conditions count the `if`s and `?:`s in the code. One
  switch can sit behind several conditions, and many conditions depend on the data or on module
  boilerplate rather than on a switch.
- **The e2e carries almost all line and closure coverage.** What the other tests add is branches.
  [What no test executes](#what-no-test-executes) is the actionable list.

## What is measured, and where

One `.nf` file runs in three places. The agent sees the first.

| Where | What runs there | Seen by this measurement |
|---|---|---|
| Nextflow head JVM | Workflow bodies, channel operator closures, process definitions, the Groovy part of a `script:` block (`def args = …`, string interpolation), every config file | **yes** |
| The task's shell | The rendered command of a `script:` block | no: the whole block is one line here |
| The tool in the container | GATK, Manta, our Python and bash in `bin/` | no: Python needs its own coverage (`coverage.py`), a separate track |

Nextflow compiles each script and config file to JVM classes whose line tables point back at the
source. *Measured* on this run: 7 055 executable lines in 245 files, none of them on a blank or
comment line.

### Three measures

| Measure | Counts | Why it is here |
|---|---|---|
| **Lines** | Executable lines with at least one executed instruction | The familiar number. High floor: wiring runs without data. |
| **Data-driven closures** | Closures that only run when a channel item or a task arrives: operator bodies (`.map { }`), a process's `script:` / `when:` / directive closures, lazy config values (`ext.args = { }`) | Zero in a plan-only run for process and config code, so it measures work, not wiring. A process's `script:` closure is entered when a task is created for it. |
| **Conditions seen every way** | Lines carrying branches (an `if`, `?:`, `&&`) with no branch missed | A plain `if (flag)` has two branches. A suite that only ever runs with the flag on leaves one untaken. |

Each is also reported for **fork lines only**: lines that are not in pristine nf-core/sarek 3.5.1,
the surface §11 of the testing guide calls "our own modifications". nf-core modules the fork
installed that sarek 3.5.1 does not ship (`bcftools/view`, `bcftools/filter`,
`gatk4/variantfiltration`, `manta/convertinversion`) have no baseline here and are counted as
upstream code.

## Running it

```bash
conda activate nf-env
tests/nf_coverage.sh run                       # everything: plan-only run, --qc_only run, all tests/*.nf.test
tests/nf_coverage.sh run split_joint_vcf       # one test file, added to the recorded data
tests/nf_coverage.sh report                    # rebuild the report only
tests/nf_coverage.sh annotate all subworkflows/local/bam_joint_calling_germline_gatk/main.nf
```

`run <test>`, `report` and `annotate` are valid only while no `.nf` or `.config` file has changed
since the last full run. After such a change, do a full run ([Limits](#limits)).

Output goes to `output_coverage/` at the repo root (gitignored; `COV_DIR` overrides):

| File | Content |
|---|---|
| `tables.txt` | The three measures per code group, for the plan-only run, the QC-only run, the e2e alone and everything merged: all code, then fork lines only, then a per-file list |
| `uncovered.txt` | Fork lines that never ran, closures never entered, conditions seen one way only |
| `levels.txt` | The same tables per test level: process tests, subworkflow tests, plan-only pipeline tests, full-run pipeline tests |
| `unique.txt` | What each test file covers that no other does |
| `coverage.tsv`, `lcov.info` | Per-file counts; LCOV tracefile (for editor gutters, `genhtml`, Codecov; written, not yet tried in any of them) |
| `RUN_INFO.txt` | Commit, versions, result and duration of every run |

`annotate` prints one source file with a mark per line:

```
+           49     GATK4_GENOMICSDBIMPORT(gendb_input, false, false, false)
+ c         83         fasta.map{ meta, fasta -> [ fasta ] },
- c        105         .map{ meta, vcf, tbi, recal, index, tranche -> [ meta + [ id:'recalibrated_…' ], … ] }
+Fc 2/4    149         vcf_out = recal_vcf ?: fallback_vcf ?: joint_vcf
```

`+` ran · `-` never ran (line 105 is the VQSR path, which the custom genome never takes) · `~` the
line ran but a closure on it was never entered · `F` fork line · `c` inside a data-driven closure ·
`2/4` two of four branches never taken (line 149: the three-way choice of output VCF went the same
way every time).

The recipe underneath, for use outside the script:

```bash
NXF_JVM_ARGS="-javaagent:jacocoagent.jar=destfile=cov.exec,classdumpdir=classes,inclnolocationclasses=true,includes=Script*:_nf_config_*" \
  nextflow run main.nf …            # or: nf-test test … (the variable reaches every launch a test makes)
java -jar jacococli.jar report cov.exec --classfiles classes --xml report.xml
```

Two things that do not work, both *measured*: `JAVA_TOOL_OPTIONS` (the `nextflow` launcher unsets
it), and an agent without the `includes` filter (instrumenting Nextflow's own classes crashes the
launcher with `NoClassDefFoundError`).

## Results (2026-10-02)

### Provenance

- **Script:** `tests/nf_coverage.sh run`, report by `tests/nf_coverage_report.py`.
- **Run directory:** `output_coverage/` on the dev VM (gitignored, 89 MB; raw data in `exec/`,
  `classes/`, `logs/`, `xml/`). Started 2026-10-02 11:43 UTC.
- **Code:** `438a9dc`. The run started on `51356a5` with that commit's changes in the working tree
  (a test file, the commit gate's test map, one doc line); no `.nf` or `.config` file differs
  between the two.
- **Runs:** 11, all exit 0: a plan-only run, a `--qc_only` run (18 tasks) and the nine files under
  `tests/`, on the ottilie test set. 1 882 s of run time; the e2e took 813 s. `tests/qc_gate.sh`
  (bash, outside nf-test) is not among them: the direct `--qc_only` run takes the same route,
  without the `-resume` of its part (b).
- **Versions:** Nextflow 25.10.4, nf-test 0.9.3, JaCoCo 0.8.12, fork baseline sarek 3.5.1.
- **Report:** rebuilt with `tests/nf_coverage.sh report` on 2026-10-04 from the same recorded data,
  which added `levels.txt`; no other number moved.

### Our own code (fork lines only)

| Measure | Plan only (`-preview`) | `--qc_only` | e2e alone | Everything merged |
|---|---|---|---|---|
| Executable lines | 781 / 1 106 (70.6 %) | 817 (73.9 %) | 961 (86.9 %) | 1 001 (90.5 %) |
| Data-driven closures entered | 5 / 291 (1.7 %) | 32 (11.0 %) | 231 (79.4 %) | 233 (80.1 %) |
| Conditions seen every way | 2 / 254 (0.8 %) | 2 (0.8 %) | 35 (13.8 %) | 80 (31.5 %) |

The same, everything merged, by code group:

| Group | Lines | Closures | Conditions seen every way |
|---|---|---|---|
| `conf/modules/` | 186 / 195 | 54 / 69 | 25 / 63 |
| `modules/local/` | 256 / 267 | 76 / 93 | 8 / 63 |
| `subworkflows/local/` | 378 / 451 | 77 / 101 | 41 / 99 |
| `workflows/sarek/main.nf` | 63 / 70 | 4 / 5 | 6 / 19 |

These are the four largest groups. The other four (`config (other)`, `main.nf`, `modules/nf-core`,
`subworkflows/nf-core`) add 118 / 123 lines, 22 / 23 closures and 0 / 10 conditions to reach the
totals above; all eight are in `tables.txt`.

Reading it:

- The line figure moves 20 points between doing nothing and doing everything; the closure figure
  moves 78. Quote the closure figure when the question is "did the tests exercise it".
- The five closures a plan-only run enters are closures called while the DAG is built (a `collect`
  on a plain list, a `.set { }`), not data.
- Conditions are the weak column: two thirds of our `if`s and `?:`s have only ever been evaluated
  one way. `modules/local/` scores lowest because most of its conditions are module boilerplate
  (the `task.ext.when == null || task.ext.when` guard and the container-engine choice), which one
  configuration always resolves the same way. A low score there is not a list of missing tests.
- Over all code, upstream included, the suite executes 4 353 of 7 055 lines (61.7 %) and enters 661
  of 1 831 closures (36.1 %). The rest is mostly sarek routes the ALE recipe never takes (Sentieon,
  Strelka, DeepVariant, the somatic and tumor-only callers).

### The main workflow file, all lines

`workflows/sarek/main.nf`, upstream and fork lines together:

| | Plan only | `--qc_only` | e2e alone | Everything merged |
|---|---|---|---|---|
| Lines, of 336 | 198 (58.9 %) | 226 (67.3 %) | 234 (69.6 %) | 240 (71.4 %) |
| Closures, of 54 | 1 | 10 | 28 | 28 |

This corrects a statement in issue #13 (comment of 2026-10-01), which said the same workflow lines
execute in a plan-only, a QC-only and a full run. At line level the three differ by up to 11
points; at closure level they are 1, 10 and 28.

### What each test contributes

Lines and closures that one run covers and no other does (`unique.txt`):

| Run | Lines | of which fork | Closures | of which fork |
|---|---|---|---|---|
| `ottilie_e2e` | 429 | 145 | 423 | 185 |
| `preflight` | 27 | 3 | 0 | 0 |
| `fastqc_trimmed` | 18 | 3 | 9 | 2 |
| `tools_without_annotation` | 5 | 3 | 0 | 0 |
| `report_gff3_optional` | 2 | 2 | 0 | 0 |
| `manta_experiment_grouping` | 2 | 0 | 1 | 0 |
| `fastp_preprocessing`, `preflight_reference`, `split_joint_vcf`, plan-only, `--qc_only` | 0 | 0 | 0 | 0 |

A zero here does not make a test redundant. The process and workflow tests run code the e2e also
runs; their value is what they assert about it, which coverage does not see. What the non-e2e runs
do add is directions: conditions seen every way rise from 35 with the e2e alone to 80 with
everything. The next table shows where those come from.

### By test level

The same three measures for each level of the suite on its own (`levels.txt`, fork code). A level
is the nf-test type of the test file; pipeline tests are split into plan-only (`-preview`, nothing
runs) and full run.

| Level | Classic name | Test files (cases) | Lines, of 1 106 | Closures, of 291 | Conditions seen every way, of 254 |
|---|---|---|---|---|---|
| Function | Unit | none yet | | | |
| Process | Unit | `fastp_preprocessing`, `preflight_reference` (15) | 255 | 7 | 8 |
| Subworkflow | Integration | `split_joint_vcf`, `manta_experiment_grouping`, `fastqc_trimmed` (9) | 296 | 21 | 8 |
| Pipeline, plan-only | End to end, wiring only | `preflight`, `report_gff3_optional`, `tools_without_annotation` (12) | 818 | 5 | 35 |
| Pipeline, full run | End to end | `ottilie_e2e` (1) | 961 | 231 | 35 |
| Everything merged, with the `--qc_only` run | | | 1 001 | 233 | 80 |

What each measure says at each level:

- **Unit: read the conditions, ignore the totals.** A process test loads one step, so its line and
  closure counts are small by design. What coverage adds is whether the test rendered every variant
  of that step: 7 of the 8 conditions at this level are `conf/modules/trimming.config` lines that
  the fastp cases take both ways.
- **Integration: read the closures.** These tests exist to show that data flows through the joins,
  branches and maps of a subworkflow, and an entered closure is direct evidence that an item reached
  that operator.
- **End to end, full run: lines and closures show what the recipe exercises.** One 14-minute run
  enters 231 of 291 closures. Its weak number is conditions, because one route flips each switch
  one way.
- **End to end, plan-only: conditions at almost no cost.** Twelve cases of about 40 seconds reach as
  many conditions as the full run, and almost entirely different ones (35 each, 2 in common),
  because each case flips one parameter. They enter almost no closures.

## What no test executes

From `uncovered.txt` (fork code, everything merged), grouped by what a test would have to switch on.
The measurement enables no test. It shows where one is missing, and afterwards whether a new test
reaches the lines it was written for.

**The tables below are a shortlist; `uncovered.txt` is the complete list.** They name the Tier-1
gaps judged worth a test. Module boilerplate is left out on purpose: of the 146 rows marked `b` (a
condition seen one way on a line that ran), 43 are the `task.ext.when` guard, the container-engine
choice, `publish_dir_mode ?: 'copy'` or a `task.ext.<x> ?:` default (*measured*, the commands
below). The other 28 of the 174 conditions not seen every way are on lines that never ran or inside
closures never entered, and carry those marks instead. A row of `uncovered.txt` that is neither
boilerplate nor in one of the groups below has not been triaged.

```bash
b='^ +b [0-9]+/[0-9]+ '
grep -cE "$b" output_coverage/uncovered.txt        # 146
grep -E "$b" output_coverage/uncovered.txt | grep -cE \
  'task\.ext\.when == null|workflow\.containerEngine|publish_dir_mode \?:|task\.ext\.[a-z_0-9]+ +\?:'   # 43
```

The Tier-1 gaps fall in two groups.

**Confirmed: gaps §11 of the testing guide already names.** The measurement adds the line
references.

| Switch or input never exercised | Code that never ran, or only ever went one way |
|---|---|
| `--hard_filter_haplotypecaller_joint` on | All of `subworkflows/local/vcf_filter_haplotypecaller_joint/main.nf` (13 lines) and its `bcftools/hard_filter` subworkflow; the four closures of `conf/modules/custom_haplotypecaller_joint_filter.config`, including the clonal-versus-population AF threshold; the branch at `bam_variant_calling_germline_all/main.nf:200` |
| `--manta_high_sensitivity` on | `conf/modules/manta_ale.config:21`, `workflows/sarek/main.nf:809` |
| Ploidy unset, and ploidy above 2 | The `meta.ploidy ?: 2` fallbacks (`gatk4/haplotypecaller/main.nf:44`, `conf/modules/split_joint_vcf.config:53`, `conf/modules/tiddit.config:19`); the VCFtools polyploidy skip (`modules/nf-core/vcftools/main.nf:89-90`, `conf/modules/modules.config:148`) |
| `GENERATE_INDEX` without its optional inputs (MultiQC report, CNV/SV data, prepared VCF) | 11 conditions seen one way, `modules/local/generate_index/main.nf:42-56` |
| `MUTATION_REPORT` with a reduced tool list (no SV caller, no HaplotypeCaller, no CNVKit) | `subworkflows/local/mutation_report/main.nf:67-71`, `:249`, `:366`, `:380`, `:396` and its `else` at `:541`; without CNVKit the closure at `:490`, which no item has entered |
| `processVersionsFromYAML` given text instead of a path, or an empty document | `subworkflows/nf-core/utils_nfcore_pipeline/main.nf:99`, `:119` |

**New: not written down before this measurement.**

| Switch or input never exercised | Code that never ran, or only ever went one way |
|---|---|
| `SPLIT_JOINT_VCF` with more than one experiment | One branch of `if (match)` never taken, `subworkflows/local/split_joint_vcf/main.nf:33-34`: every sample has always belonged to the joint VCF it was offered |
| `--joint_manta` off; `--split_haplotypecaller_joint_vcf` off | `bam_variant_calling_germline_all/main.nf:260` and `:182` |
| `--joint_manta` off with two or more samples in an experiment | `SVDB_MERGE_MANTA`, the across-sample Manta merge: submitted in none of the 11 runs (*measured*, the runs' logs). It shows only as the `multi` branch at `subworkflows/local/mutation_report/main.nf:304`; the module file reads as covered through its other two aliases (see [Limits](#limits)) |
| `--joint_germline` off (per-sample HaplotypeCaller) | `bam_variant_calling_germline_all/main.nf:238`, the `hc_kind: 'sample_single'` tag the mutation report keys on |
| `snpeff_cache` pointing at a missing directory; an `az://` cache path | `subworkflows/local/annotation_cache_initialisation/main.nf:35` (8 of 16 branches never taken): the start-up error for a missing cache, and the skip of that check for cloud paths. Every Azure run takes the cloud branch; none is measured |
| The igv-reports steps without `report_gff3` | `igvreports_cohort/main.nf:26`, `igvreports_sample/main.nf:26`, `igvreports_sv_cnv/main.nf:33-36`. `report_gff3_optional` is a plan-only test, so no task has run without a GFF3 |
| `adapter_sequence`, `adapter_sequence_r2` set | `conf/modules/trimming.config:26-27` |
| `fastqc` in `--skip_tools` | `conf/modules/modules.config:40`, `workflows/sarek/main.nf:309`, the `--qc_only` warning at `utils_nfcore_sarek_pipeline/main.nf:270-271` |
| `--qc_only` with `cleanup = true` | The hard error at `utils_nfcore_sarek_pipeline/main.nf:266-267`, the only one of the five preflight errors without a test case |
| `--multiqc_title` set; `--generate_reports false` | `conf/modules/modules.config:63-71`; `workflows/sarek/main.nf:1020` |

**Not visible here at all:** the guide's first priority, the soft-filter step
(`VARIANTFILTRATION_FALLBACK`). The e2e executes it, so it reads as covered; its risk is an
expression that runs and matches nothing (see [Limits](#limits)).

### Choosing the test for a gap

Use the level table above to pick the cheapest test that can close an entry of `uncovered.txt`.

| The entry is | Cheapest test that closes it | Why |
|---|---|---|
| `b m/n` on a line of one step or of its `conf/modules` block (an optional input, a ploidy fallback, an `ext.args` choice) | A case in a process test; stub mode when only the rendered command matters | The closure runs when a task is created, so one small task per variant is enough |
| `c`, a closure never entered inside a subworkflow | A subworkflow test that sends an item down that path, stub mode where the tool's output does not matter | Only data reaching the operator enters it; no plan-only run will |
| `b m/n` on an `if` over a parameter in a workflow body | A plan-only pipeline case that flips the parameter | Workflow bodies run while the DAG is built; 40 seconds |
| Lines that never ran behind a switch, with closures among them | A plan-only case for the wiring, plus a subworkflow test for the closures | The two halves need different levels; a second full route only when the outputs themselves are in question |

After writing the test, `tests/nf_coverage.sh run <test>` adds it to the recorded data and
`tests/nf_coverage.sh annotate all <file>` shows whether the lines turned from `-` or `b` to `+`.
Raising a number is not the goal: a new test earns its place by what it asserts.

**Off the Tier-1 route, as expected:** all breseq code (`conf/modules/breseq.config`, two modules,
`subworkflows/local/fastq_variant_calling_breseq/main.nf`, `workflows/sarek/main.nf:346-353`), the
fork's lines in the Mutect2 subworkflow (12), the FreeBayes ploidy argument.

**Not gaps:** four preflight `error(...)` lines (`utils_nfcore_sarek_pipeline/main.nf:261`, `264`,
`388`, `396`) are listed as never run although `tests/preflight.nf.test` asserts on each message:
see the first limit below.

**Probably dead code, to delete rather than test** (*inferred* from reading the code, not tried):
the `experiment` to `patient` remap at `utils_nfcore_sarek_pipeline/main.nf:139-141` never ran,
although the e2e samplesheet uses the `experiment` header. `assets/schema_input.json` writes that
column straight to `meta.patient`, and nothing sets `meta.experiment`, so the condition cannot be
true in a pipeline run. The `?: meta.experiment` fallbacks at `samplesheet_to_channel/main.nf:42`
and `split_joint_vcf/main.nf:29` are in the same position.

## How a class is mapped to its file

| Source | Class name | Rule | Checked (*measured*) |
|---|---|---|---|
| `.nf` file | `Script_<16 hex>` | Listed with its path in `.nextflow.log` (nf-test: `<workdir>/tests/<hash>/meta/nextflow.log`) | 214 of 214 classes mapped |
| `includeConfig`'d file | `Script<32 HEX>` | The MD5 of the file's text, upper case | 44 of 44 files. Two more classes carry such a name without being files: one-line texts evaluated at run time, one of them empty |
| `nextflow.config`, `-c` files | `_nf_config_<8 hex>` | Hash not derived; matched by line numbers to the files in the log's `Parsing config file:` lines | Both files of this run. *Assumed* to stay unambiguous with more `-c` files |

Two properties make merging across runs safe, both *measured*: the same source compiles to the same
bytecode in every run (all 1 896 `.nf` classes, closures included, had identical ids in two
separate runs; execution data recorded on 2026-10-01 matched the classes dumped a day later), and a
plan-only run repeated a day later reproduced every count.

The wiring-versus-data split is derived from the class structure: a process definition and a
workflow body are the outer closures, everything nested inside them needs data. In a config file a
scope block (`process { }`, `withName: { }`) is told from a lazy value by whether it contains other
closures and by how it is opened. *Measured* check: of 491 lazy config closures, the plan-only run
entered none.

## Limits

- **A line that throws reads as not executed** (*measured*). JaCoCo records a block when it ends, so
  an `error(...)` line shows as never run even when a test asserts on its message. The condition
  above it does show the branch as taken, which is how the four tested preflight errors are told
  from the untested one.
- **A `script:` block is one line**, and nothing inside a container is seen. The inventory in issue
  #13 counts 364 of the 667 Nextflow lines in our own steps as shell.
- **A one-line closure makes its line look covered.** `ch.map { … }` written on one line is marked
  by the wiring; only the closure measure and the `~` mark tell the difference.
- **A module included under several names is one class** (*measured*). `SVDB_MERGE` is included as
  `SVDB_MERGE_MANTA`, `SVDB_MERGE_TIDDIT` and `SVDB_MERGE_CALLERS`. No run submitted the Manta alias,
  yet `modules/nf-core/svdb/merge/main.nf` and the `withName` block it shares with the TIDDIT alias
  read as covered, and the line that calls it (`mutation_report/main.nf:307`) reads as run, because
  the call is wiring. An entered `script:` closure says that some alias of the step ran, not which.
- **Coverage is not correctness.** The e2e executes the soft-filter step's `ext.args`, yet a JEXL
  expression that matches nothing would execute just the same (§11, layer 2).
- **A killed head job loses its data** (*assumed*, not tried): the agent writes at JVM exit. A run
  that ends in a pipeline error does record (*measured*: the error cases of `preflight`).
- **The recorded data belongs to one version of the code.** `report`, `annotate` and `run <test>`
  read the current `.nf` and `.config` files against the classes and line numbers of the last full
  run, and nothing checks that the two still match. After a change to such a file, `annotate` prints
  the recorded marks against the new text, and an `includeConfig`'d file, whose class is named by
  the MD5 of its text, no longer maps and leaves the counts without a message (*inferred* from the
  mapping rule, not tried). Do a full run first. A partial run on unchanged code is safe
  (*measured* 2026-10-04 at `b4c447d`, on a copy of the run directory since discarded:
  `run split_joint_vcf`, 76 s, `tables.txt`, `levels.txt`, `uncovered.txt` and `unique.txt`
  byte-identical).
- **Not tried under the strict (v2) parser.** `nextflow.config` does not parse there, and the class
  names are an implementation detail of Nextflow 25.10 that a later version may change.
- **Overhead is small** (*measured*, single runs on the dev VM): a plan-only run took 40 s with the
  agent and 38 s without; the e2e took 813 s with it. No same-day e2e without the agent was run.

## Open questions

- Whether to run this on a schedule or before a release, and whether any of the three measures
  deserves a floor. None is proposed here.
- Python coverage of `bin/` (`coverage.py` inside the task) is the larger half of what we wrote and
  is not covered by any of this.
- The issue #13 comment of 2026-10-01 needs a correction pointing here.
