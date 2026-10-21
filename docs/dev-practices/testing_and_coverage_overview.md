# Testing and code coverage of yAMP: overview

*Status 2026-10-20. The short version; the engineering records are
[`testing_best_practices.md`](testing_best_practices.md) (what we test and why) and
[`nextflow_code_coverage.md`](nextflow_code_coverage.md) (how coverage is measured, full results, limits).*

**Context, for readers from outside this repository.** yAMP is a fork of nf-core/sarek 3.5.1 for yeast
adaptive laboratory evolution (ALE) experiments: one production route (joint germline HaplotypeCaller, CNVKit,
Manta + TIDDIT, SnpEff) where sarek ships many. "Fork code" means the lines that are not in pristine sarek 3.5.1,
and every figure on this page is measured on those lines, with the 2-sample, 4-chromosome test set that ships with
the repository. Terms: e2e, the one end-to-end full run; QC, read quality control; DAG, the graph of steps Nextflow builds
before any task runs; VQSR, GATK's variant-quality recalibration; JaCoCo, the Java code-coverage agent; nf-test,
the test framework of nf-core pipelines.

## Documents

Five documents, in reading order. Each answers one question.

1. [`testing_and_coverage_overview.md`](testing_and_coverage_overview.md) (this page): what we test, at which levels, what we measure and what the numbers mean. Start here.
2. [`testing_best_practices.md`](testing_best_practices.md) §10–§14: the rules in force: the test infrastructure we have, the four nf-test layers to fill, what counts as validated (the contract-test rule and the commit gate), how a benchmark number earns its provenance, and where cross-session state lives. §1–§9 are the pre-1.0.0 plan, kept for the record.
3. [`nextflow_code_coverage.md`](nextflow_code_coverage.md): how coverage is measured (JaCoCo on the Nextflow head JVM), how to run it, the dated results and the list of fork code no test executes.
4. [`test_inventory_2026-10-19.md`](test_inventory_2026-10-19.md): which of the files the fork added or changed a test reaches, per scope, against pristine sarek 3.5.1.
5. [`sarek_351_benchmark_2026-10-20.md`](sarek_351_benchmark_2026-10-20.md): the same method on upstream's own test: how much of sarek 3.5.1 its default route covers, beside our figures.

## Results so far

Fork code, everything merged; each row links to its section of the coverage document, which holds the provenance.

| Measurement | Commit | Branch coverage | Fully covered decision lines | Output-selection line (`vcf_out = recal_vcf ?: fallback_vcf ?: joint_vcf`), branches taken |
|---|---|---|---|---|
| [2026-10-13](nextflow_code_coverage.md#results-2026-10-13) | `99aef57` | 514 / 916 (56.1 %) | 83 / 254 | 2 / 4 |
| [2026-10-16](nextflow_code_coverage.md#results-2026-10-16-after-the-joint-calling-output-selection-test), after the output-selection test | `84e8274` | 516 / 916 (56.3 %) | 83 / 254 | 3 / 4 |
| [2026-10-19](nextflow_code_coverage.md#results-2026-10-19-after-the-join-fix-and-the-soft-filter-test), after the join fix and the soft-filter test | `d3dc805` | 522 / 920 (56.7 %) | 87 / 256 | 4 / 4 |

For scale, measured the same way on 2026-10-20: nf-core/sarek 3.5.1's own default test covers 13.7 % of sarek's
branches (794 / 5 806); our one e2e covers 42.0 % of fork code (386 / 920). Each tree is measured by its own tests on
its own code, and the denominators differ six-fold, so this compares two suites, not two pipelines
([`sarek_351_benchmark_2026-10-20.md`](sarek_351_benchmark_2026-10-20.md) §3).

## 1. Three questions, three tools

| Question                                   | Tool                                                         | Gives                                                 |
| ------------------------------------------ | ------------------------------------------------------------ | ----------------------------------------------------- |
| Does the pipeline behave correctly?        | nf-test, plus one bash gate with two parts: `--qc_only` and `-resume` | pass / fail: exit status, output names, md5 of stable files, VCF records, counts in reports, console messages |
| Which components have a test of their own? | `nf-test coverage`                                           | ⚠️ an inventory only: the share of `.nf` files that some test file names (51 % here, almost all of it the upstream tests). It runs no case, executes no line and does not follow calls |
| Which code did the tests actually execute? | JaCoCo attached to the Nextflow process during the same test runs | closure[^closure], line and branch coverage of the Nextflow layer[^layer] |

[^closure]: A closure is a `{ }` block that runs only when data arrives: an operator body such as `.map { }`, a process's `script:` block, a lazy config value such as `ext.args = { }`.
[^layer]: A `script:` block counts as one line, and the Python scripts in `bin/` still need their own pytest + coverage.py track (§4).

## 2. Test levels

| Level       | nf-test type                        | What one test checks                                         | We have                 |
| ----------- | ----------------------------------- | ------------------------------------------------------------ | ----------------------- |
| Unit        | function test                       | one Groovy helper, no tool, no run                           | none yet                |
| Unit        | module test (nf-test: "process")    | one module: its command line, config and outputs, with the real tool as an unmocked dependency | 2 modules, 15 cases     |
| Integration | subworkflow test                    | several modules wired together; stub mode runs the wiring without the tools | 4 subworkflows, 13 cases |
| System      | pipeline test, dry run (`-preview`) | the pipeline builds and start-up logic behaves under a parameter change; no tasks, ~40 s | 3 files, 12 cases       |
| System      | pipeline test, full run             | one complete route against a committed snapshot (names, md5s, report tables, VCF records); 15–25 min | `ottilie_e2e`           |
| System      | QC-first gate (bash)                | a `--qc_only` run executes exactly the QC steps and nothing downstream; `-resume` equals a one-shot run | `tests/qc_gate.sh`      |

The 100 upstream test files that ship with the vendored modules and subworkflows test unmodified nf-core and sarek code and are not counted here.

## 3. What we measure, and the scope

We measure the code we wrote or changed. Unmodified nf-core and sarek code is excluded, the same way a
vendor folder would be; the implementation is a line-by-line comparison with pristine sarek 3.5.1.

Four measures, from "did data reach the step" to "what is left to test":

| Measure                      | Counts                                               | Fork code, 2026-10-19 (`d3dc805`)          | Use                                             |
| ---------------------------- | ---------------------------------------------------- | ------------------------------------------ | ----------------------------------------------- |
| Closures entered             | steps and closures that only run when data arrives   | 80.3 % (236 / 294)                         | did data reach every step                       |
| Lines executed               | executable lines run at least once                   | 90.7 % (1 019 / 1 124), of which 70 % before any task runs | context only; see below                         |
| **Branch coverage**          | every direction of every decision (`if`, `?:`, `&&`) | **56.7 %** (522 / 920)                     | **the figure we report and track**              |
| Fully covered decision lines | lines with no direction left untaken                 | 87 / 256                                   | the list of what to test next (`uncovered.txt`) |

Lines executed is the broad measure. The other three each take a subset of those lines and ask more of it:

- **Closures entered**: the lines inside data-driven closures. A line counts as executed once the closure is
  created; it counts as entered only when the body runs on an item.
- **Branch coverage**: the 256 decision lines. Executed means reached; covered means every direction taken.
- **Fully covered decision lines**: the same branches, read per line instead of per direction.

**Why line coverage misleads here.** A Nextflow pipeline first builds its whole graph (every workflow body
runs, every parameter `if` is evaluated) and only then executes tasks. Building alone executes 70 % of our
lines. Python has no such phase. So branch coverage is the number we read.

**What each test level adds.** Branch coverage from the full e2e alone is 42.0 %; with all tests merged it is
56.7 %. One route takes every switch one way; the small tests flip them.

## 4. Limits of the measurement

- It sees the Nextflow/Groovy layer: wiring, channel logic, configuration. Each step's `script:` block
  counts as one line; the bash inside it and the tools in containers are not seen. The Python in `bin/` needs
  its own track (pytest + coverage.py), not yet started.
- Coverage is not correctness. The soft-filter step runs in every e2e and reads as covered, yet a filter
  expression that silently matched nothing would run the same and mark every variant PASS. Only a test that
  checks the FILTER values catches that.
- Not every missed branch is a gap: some are module boilerplate that one configuration always resolves the same
  way, some are routes we keep for upstream compatibility. Each entry of the worklist is triaged: write a
  test, accept as unused, or delete.
- Branches are counted two per conditional jump in the compiled bytecode; compound conditions count each
  part, so the figure is slightly stricter than textbook. The denominator depends on the Nextflow/Groovy
  version, which is recorded with every result. A probe on Nextflow 26.10 (strict parser, Groovy 4.0.33)
  gave the same per-construct counts; the pipeline itself has not been measured there, since it does not
  yet parse under the strict syntax.

## 5. Decisions

- Branch coverage is the headline; no target is set. The number to watch is the change after each new test.
- First tests to add, both on the joint-calling path (the fork's largest change: VQSR skipped for lack of a
  known-variant resource, replaced by a soft filter and a three-way output selection): a subworkflow test
  for the output selection (added 2026-10-16, three cases; before it every run took the soft-filter outcome
  and JaCoCo reported 2 of 4 branches; the raw-joint outcome needed a join fix, made 2026-10-19, see
  `testing_best_practices.md` §11 layer 3), then a module test for the soft filter.
- CI in the same pattern as nf-core/sarek: lint and the changed tests on every PR before merge; the full
  e2e and the coverage run on a schedule; a coverage floor only once the number is stable.
- Reference: sarek 3.5.1 and 3.10 run lint and tests on every PR with binary acceptance, and report no
  coverage and no numeric threshold (read from the `.github/workflows/` files of nf-core/sarek, 2026-10-15).
  Measured on 2026-10-20 under our method, sarek 3.5.1's own default route covers 13.7 % of its own branches
  (794 / 5 806) against our e2e's 42.0 % of fork code; each tree on its own-code denominator
  ([`sarek_351_benchmark_2026-10-20.md`](sarek_351_benchmark_2026-10-20.md)).
- Upgrades (sarek 3.10, Nextflow 26, the strict syntax) are separate tasks and do not change this strategy.[^upgrades]

[^upgrades]: Nextflow 26.10 with the strict parser was probed on 2026-10-14: the JaCoCo agent still attaches
    there, four tooling changes are listed and ready, and the branch counts are identical
    ([`ale_sarek_upgrade_runbook.md`](ale_sarek_upgrade_runbook.md), *Coverage tooling on Nextflow 26*). The pipeline
    itself needs the strict-syntax migration first (432 lint errors in 94 files). Sarek 3.10 has not been tried; its
    rebase hazards are in the same runbook, and its own CI is the nf-test pattern this doc adopts, so the levels and
    measures carry over. The e2e snapshot will be re-recorded at either upgrade, as after any output change.

## 6. Running it

From a clean clone, with Docker on the machine:

```bash
conda env create -f environment.yml && conda activate nf-env      # nextflow 25.10.4, nf-test 0.9.3, java 17
bash docs/benchmarking/ottilie_xenobiotic_ale/01_data_retrieval/release/download_test_data.sh
                                                         # once per machine: the test set, public blob, no credentials
nf-test test -c tests/nf-test-ottilie.config tests/     # the suite
tests/qc_gate.sh a                                       # the QC-first gate
tests/nf_coverage.sh run                                 # coverage, ~35 min; report in output_coverage/
```

## 7. What transfers to another Nextflow pipeline

The method is general; the figures and two of the tools are ours.

- **Transfers as is.** The three questions and their tools (§1); the test levels, which are nf-test's own types (§2);
  the measurement itself: a JaCoCo agent attached to the Nextflow head JVM through `NXF_JVM_ARGS`, which sees every
  `.nf` and `.config` file as compiled Groovy, works through `nf-test` and through a direct `nextflow run`, and needs
  no change to the pipeline (the agent line is in [`nextflow_code_coverage.md`](nextflow_code_coverage.md) →
  *Running it*); the reading rules: branch coverage over line coverage, because DAG build alone executes most lines
  (§3), coverage is not correctness (§4), and the JaCoCo branch counts for Groovy constructs, which hold for any
  Nextflow code ([`nextflow_branch_counting.md`](nextflow_branch_counting.md)).
- **Specific to this repository.** The fork-versus-pristine denominator: a pipeline that is not a fork measures all
  of its own code, as the sarek benchmark does. The commit gate, the contract-test rule and the test-set names.
- **The scripts.** `tests/nf_coverage.sh` (the runs and the agent) and `tests/nf_coverage_report.py` (the tables) can
  be lifted, but they assume this repository: the `tests/` layout, the pristine-sarek download that drives the fork
  split, `output_coverage/` at the root. Lifting them means editing those three things; they are not packaged.
