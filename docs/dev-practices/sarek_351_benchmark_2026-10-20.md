# Benchmark: pristine nf-core/sarek 3.5.1 under the yAMP coverage method (issue #14, item 5)

*Measured 2026-10-20 on the dev VM. A measurement, not a test: nothing in the pipeline changed, and the recorded
yAMP data (`output_coverage_d3dc805/`) was read, not re-run. The script that produced the sarek rows is committed next
to this file, [`sarek_351_benchmark_2026-10-20/nf_coverage_bench.sh`](sarek_351_benchmark_2026-10-20/nf_coverage_bench.sh)
(testing guide §13: scripts before numbers); the run directory, `~/bench/output_sarek351/` on the dev VM, is not in the
repo. Every number below is* measured *unless stated otherwise.*

## 1. The question, and what "comparable" means here

Issue #14, item 5: "Benchmark: pristine sarek 3.5.1 `test,docker` under the same JaCoCo method, compared
pipeline-level to pipeline-level". The three-row form of the benchmark ("sarek's own test route" / "ours,
pipeline-level only" / "ours, all levels") is not written in any repo doc; the definition applied here was agreed in
the session of 2026-10-20:

- **Each tree is measured by its own tests on its own code.** For pristine sarek, its own code is every `.nf` and
  `.config` file of the tree (the fork-vs-upstream split of `tests/nf_coverage_report.py` does not apply; see §4 for
  how the script was given that denominator without being changed). For yAMP, its own code is the fork lines: lines
  not in pristine sarek 3.5.1, as in every published yAMP figure.
- **Same method settings:** Nextflow 25.10.4, Groovy 4.0.28, Java 17.0.15, JaCoCo 0.8.12 with the same agent line and
  includes filter, nf-test 0.9.3, the same report script (`tests/nf_coverage_report.py` at `67b4784`, unchanged since
  the d3dc805 measurement), the same constant-jump exclusion. Resource caps are similar: sarek's `test` profile caps at
  4 CPUs / 15 GB; our tests run under `tests/ottilie_nftest_resources.config` on the same 4-vCPU VM.
- **Same test level:** sarek's one full-run pipeline test (`tests/default.nf.test`) against our one full-run
  pipeline test (`tests/ottilie_e2e.nf.test`). Sarek's plan-only run against our plan-only run is the floor pair.
- **Not the same route or parameters, by decision** (2026-10-20): running sarek with the ALE recipe would measure how
  much of sarek the ALE recipe exercises, which our all-code figures already approximate (§3, last table), not how
  well sarek's own suite covers sarek.

## 2. The three rows

| Row | Tree, ref | Runs in the row | Executable lines | Data-driven closures | **Branch coverage** | Fully covered decision lines |
|---|---|---|---|---|---|---|
| **sarek default route** | nf-core/sarek 3.5.1, release tarball (GitHub archive of tag `3.5.1`) | `tests/default.nf.test`: 2 cases (the `test` profile full run, 23 tasks; a samplesheet-rejection case), nf-test 0.9.3 | 3 353 / 6 275 (53.4 %) | 297 / 1 549 (19.2 %) | **794 / 5 806 (13.7 %)** | 9 / 1 614 (0.6 %) |
| **ours, pipeline-level only** | Aletechdev/ALE_Yeast `d3dc805` | `tests/ottilie_e2e.nf.test`: 1 case (the `full_run` level of `levels.txt`) | 974 / 1 124 (86.7 %) | 233 / 294 (79.3 %) | **386 / 920 (42.0 %)** | 38 / 256 (14.8 %) |
| **ours, all levels** | Aletechdev/ALE_Yeast `d3dc805` | 13 runs: plan-only, `--qc_only`, 11 test files (`all` of `tables.txt`) | 1 019 / 1 124 (90.7 %) | 236 / 294 (80.3 %) | **522 / 920 (56.7 %)** | 87 / 256 (34.0 %) |

Denominators: for sarek, all of its own code that compiled in at least one recorded run (208 files; see §4 on the
count); for yAMP, fork lines (59 files with fork lines). Each row names its denominator in the cell.

**Supplementary lines**, same method, for the floor and for the other definitions of "pipeline-level":

| Line | Lines | Closures | Branches | Decision lines |
|---|---|---|---|---|
| sarek, plan-only (`-profile test,docker -preview`) | 3 044 / 6 275 (48.5 %) | 5 / 1 549 (0.3 %) | 462 / 5 806 (8.0 %) | 3 / 1 614 (0.2 %) |
| sarek, joint-germline route (`tests/test_joint_germline.yml` command, run directly; 26 tasks) | 3 119 / 6 275 (49.7 %) | 229 / 1 549 (14.8 %) | 684 / 5 806 (11.8 %) | 9 / 1 614 (0.6 %) |
| sarek, the three runs merged | 3 524 / 6 275 (56.2 %) | 383 / 1 549 (24.7 %) | 969 / 5 806 (16.7 %) | 28 / 1 614 (1.7 %) |
| ours, plan-only (`preview` column of `tables.txt`) | 791 / 1 124 (70.4 %) | 5 / 294 (1.7 %) | 162 / 920 (17.6 %) | 2 / 256 (0.8 %) |
| ours, nf-test pipeline tests only (3 plan-only files + e2e) | 1 011 / 1 124 (89.9 %) | 233 / 294 (79.3 %) | 500 / 920 (54.3 %) | 71 / 256 (27.7 %) |
| ours, every pipeline-level run (those + direct preview + `--qc_only`) | 1 011 / 1 124 (89.9 %) | 233 / 294 (79.3 %) | 505 / 920 (54.9 %) | 75 / 256 (29.3 %) |

The last two lines are JaCoCo merges of the recorded d3dc805 `.exec` files (read-only), written to
`~/bench/ours_d3dc805_pipeline_level/`; `levels.txt` itself has no merged pipeline-level column.

## 3. Reading it

- **At the matched level, sarek's suite covers 13.7 % of sarek's branches; ours covers 42.0 % of ours.** The
  denominators differ by a factor of six (5 806 against 920): sarek's test must cover a whole pipeline with every
  route it ships (Sentieon, DeepVariant, Strelka, Mutect2, the somatic and tumor-only paths, three aligners, UMI
  handling, three annotators), one route per run, while our fork code is the ALE recipe plus its reports. A route
  test can only ever take one direction of every route switch, which is what the two decision-line figures say:
  9 of 1 614 lines for sarek, 38 of 256 for us, at the same level.
- **The floor is where the two trees differ most.** A plan-only run already executes 48.5 % of sarek's lines and 70.4 %
  of ours: both pipelines evaluate most of their wiring and every parameter `if` while the DAG is built, which is why
  neither project should quote line coverage (`testing_and_coverage_overview.md` §3).
- **One route test adds about 5 points of branches in both trees** (sarek: 8.0 → 13.7 %; ours, e2e over plan-only:
  17.6 → 42.0 %, which is more because the fork code is the route that runs). The per-group table in `tables.txt`
  shows where sarek's default run goes: `workflows/sarek/main.nf` 80 / 224 branches, `conf/modules/` 215 / 1 014,
  `modules/nf-core/` 169 / 3 106 (one hundred modules, most never instantiated on the Strelka route).
- **Sarek's second route (joint germline) is the one closest to ours.** It covers 684 branches alone and adds 175 to
  the default route's 794 when merged (969); its unique code is the HaplotypeCaller / GenomicsDB / joint-calling
  subworkflows (`unique.txt`). This is the pair to look at for the question "how much of the joint-germline
  machinery does each suite exercise": sarek's own tests take it one way on human test data, our fork tests take the
  VQSR-less branch of it both ways (`vcf_out` 4 / 4 since `f3e9109`).
- **The all-levels row is the one the small tests move.** Ours goes 42.0 → 56.7 % branches and 38 → 87 decision lines
  from the module, subworkflow and plan-only tests. Sarek 3.5.1 has no component tests of its own above the nf-core
  module fixtures (its `tests/` holds 20 pipeline-level nf-test files and 29 pytest-workflow routes), so its
  equivalent of "all levels" is its 20 + 29 routes, which this benchmark did not run. The three sarek runs here are
  2 of those 49, and already reach 16.7 %.
- **Zero constant-condition branches in sarek.** The report's exclusion line reads `0 branches on constant conditions
  excluded`, as `nextflow_code_coverage.md` predicted: sarek's `branch` calls use explicit criteria. Our 4 excluded
  branches are the fork's `mutation_report` catch-alls.

**All code to all code** (a fourth comparison, not one of the three rows): our whole tree, pristine sarek lines
included, on the same empty-baseline denominator as the sarek rows. This is the figure a `genhtml` index of our
`lcov.info` shows (roadmap: *Review and decide how coverage is reported*) and it is what "sarek on the ALE
recipe" would come close to, since 95 % of our tree is pristine sarek code:

| Our whole tree, all code, d3dc805 | Lines / 7 073 | Closures / 1 834 | Branches / 6 862 | Decision lines / 1 898 |
|---|---|---|---|---|
| plan-only | 3 634 (51.4 %) | 10 | 640 (9.3 %) | 4 |
| e2e alone | 4 280 (60.5 %) | 653 | 1 422 (20.7 %) | 48 |
| every pipeline-level run | 4 346 (61.4 %) | 653 | 1 601 (23.3 %) | 97 |
| everything merged | 4 411 (62.4 %) | 694 | 1 682 (24.5 %) | 114 |

Against sarek's own default route on its own tree (53.4 % lines, 13.7 % branches, 9 decision lines): one ALE e2e run
over the same code base reaches 60.5 % lines, 20.7 % branches and 48 decision lines, because the ALE route runs more
of the shared machinery (joint calling, CNVKit, Manta, TIDDIT, SnpEff, the reports) than the Strelka test route does.
The 24.5 % branch figure equals the lcov branch rate quoted in the roadmap row, which confirms the two renderings
agree on the all-code denominator.

## 4. Method notes specific to this benchmark

- **The script.** [`sarek_351_benchmark_2026-10-20/nf_coverage_bench.sh`](sarek_351_benchmark_2026-10-20/nf_coverage_bench.sh),
  a copy of `tests/nf_coverage.sh` that was run from `~/bench/` on the dev VM. Unchanged:
  JaCoCo 0.8.12, the agent line (`includes=Script*:_nf_config_*`, `inclnolocationclasses=true`), `NXF_VER=25.10.4`,
  `check_scripts_recorded`, and the report script, which is read from the repo. Changed: the tree (`PIPE_DIR`), test
  dir (`TESTS_DIR`) and profile (`PROFILE=test,docker`) come from the environment; nf-test runs from the tree's root
  with sarek's own `nf-test.config` (`-c conf/test.config`, plugins nft-bam 0.4.0 and nft-utils 0.0.3, `--profile
  test,docker` replacing its `test`, the way sarek's CI appends `+docker`); no `--qc_only` run; a `pipeline <name>
  <args>` command records one direct `nextflow run` for routes that have no nf-test file. Diff against the original:
  `diff -u tests/nf_coverage.sh docs/dev-practices/sarek_351_benchmark_2026-10-20/nf_coverage_bench.sh` (about 150 lines, mostly
  the header).
- **"Own code = all code" without changing the report script.** The report prints the branch and decision-line tables
  for "fork lines" only, and a file with no baseline counterpart under `modules/nf-core/` or `subworkflows/nf-core/`
  is treated as upstream with zero fork lines. The bench therefore builds a baseline of *empty files* at the path of
  every `.nf` / `.config` of the measured tree (`tools/empty_baseline/`). Every executable line then diffs as a fork
  line, and the "… - fork lines only" tables of `~/bench/output_sarek351/tables.txt` are the all-code tables. The
  report step checks this (the all-code and fork-only totals for lines and closures must be identical; they are:
  `check: 'fork lines only' = all code`). The same trick on our own recorded d3dc805 data reproduced the recorded
  all-code totals exactly (4 411 / 7 073 lines, 694 / 1 834 closures), which is how the all-code table in §3 was made.
- **The sarek denominator counts files that compiled in a recorded run**: 208 `.nf` / `.config` files, of the tree's
  333. The other 125 are mostly the nf-core module test fixtures (95 files under `*/tests/`), plus routes never
  included (Sentieon modules' nested includes, profiles not loaded). The a + b report alone had 207 files / 6 269
  lines / 1 548 closures; the joint-germline run added `conf/test/targeted.config` (6 lines, 1 closure), hence
  6 275 / 1 549. The branch denominator (5 806) and the decision-line denominator (1 614) did not move. Our 1 124
  fork lines are the same rule (files compiled in a recorded run: 246 of our 415) restricted to fork lines.
- **Tags.** Sarek 3.5.1's nf-test files carry only `pipeline` and `pipeline_sarek`; the default route is selected by
  file name (`tests/default.nf.test`), not by a `default` tag. `joint_germline` is a pytest-workflow tag
  (`tests/test_joint_germline.yml`, run in sarek's CI by `pytest --tag`, excluded there on `latest-everything`); its
  first case's command line was run directly under the agent, with `-profile test,targeted,docker`.
- **nf-test version.** Sarek's CI pinned 0.9.2 and its snapshot was recorded on 0.9.0 / Nextflow 24.04.4; the run here
  used 0.9.3 (our recorded runs' version). Both cases PASSED and the snapshot matched, so no re-run on 0.9.2 was
  needed. The coverage data comes from the Nextflow head JVM and does not depend on the nf-test version.
- **Known caveat carried over:** `_nf_config_` classes are matched to files by line numbers (`nextflow_code_coverage.md`,
  *How a class is mapped to its file*); here two files are parsed that way (`nextflow.config`, `conf/test.config`).

## 5. Runs and provenance

| Run | Command (dev VM, from `~/bench`, `PIPE_DIR=~/bench/sarek-3.5.1 COV_DIR=~/bench/output_sarek351`) | Exit | Seconds | Tasks | Notes |
|---|---|---|---|---|---|
| a. `preview` | `nf_coverage_bench.sh run` (first half): `nextflow run main.nf -profile test,docker -preview` | 0 | 48 | 0 | "Pipeline completed successfully" |
| b. `t_default` | `nf_coverage_bench.sh run` (second half): `nf-test test --profile test,docker tests/default.nf.test` | 0 | 216 | 23 | 2 / 2 PASSED, snapshot matched; one harmless `CRAMFileReader` index-age warning; the nf-test discovery warnings about missing module-test dependencies (`spring/compress`, `sentieon/bwaindex`, …) are sarek's tree, not this run |
| c. `joint_germline`, attempt 1 | `PROFILE=test,targeted,docker nf_coverage_bench.sh pipeline joint_germline --input tests/csv/3.0/mapped_joint_bam.csv …` | 1 | 39 | 0 | **Setup error, mine:** the bench runs each pipeline from its own run directory, so the relative `--input` of the pytest-workflow command did not resolve; parameter validation stopped the run before any task. Its data was replaced by the retry (the `.exec` is rewritten per run); the line stays in `RUN_INFO.txt`. Log kept as `logs/joint_germline_attempt1_failed.run.log` |
| c. `joint_germline`, retry (the one allowed) | same, with the absolute `--input ~/bench/sarek-3.5.1/tests/csv/3.0/mapped_joint_bam.csv` | 0 | 126 | 26 | "Pipeline completed successfully"; HaplotypeCaller × 8 intervals × 2 samples, GenomicsDB import, GenotypeGVCFs, bcftools / vcftools QC, MultiQC |

No container pull or network stall occurred; nothing was cancelled.

- **Run directory:** `~/bench/output_sarek351/` on the dev VM, not in the repo (raw data in `exec/`, `classes/`, `logs/`, `xml/`; the report in
  `tables.txt`, `levels.txt`, `uncovered.txt`, `unique.txt`, `coverage.tsv`, `lcov.info`; the a + b report before the
  joint-germline run was added is kept in `snapshot_ab/`; the three shell logs are `bench_run_ab.log`,
  `bench_run_c.log`, `bench_run_c_retry.log`).
- **Versions** (`RUN_INFO.txt`): Nextflow 25.10.4, Groovy 4.0.28, Java 17.0.15-internal, nf-test 0.9.3, JaCoCo 0.8.12,
  baseline: empty files. Identical to the d3dc805 measurement's versions, so the branch denominators are comparable
  (`nextflow_code_coverage.md`, *Limits*: the denominator depends on the Groovy compiler).
- **Sarek tree:** `~/bench/sarek-3.5.1`, a copy of `output_coverage/tools/sarek-3.5.1/` (the coverage script's own
  download of the GitHub archive of tag `3.5.1`, release published 2025-02-18). Not a git clone, so no commit hash;
  the tag is the reference.
- **Our rows:** `output_coverage_d3dc805/tables.txt` and `levels.txt` (measured 2026-10-19 14:59 UTC on `d3dc805`,
  clean tree, 13 runs all exit 0), not re-run. The merged pipeline-level lines and the all-code table are read-only
  derivations from that directory's `exec/`, `classes/` and `logs/`, written to `~/bench/ours_d3dc805_pipeline_level/`
  (`tables.txt`, `tables_allcode.txt`).
- **Report script:** `tests/nf_coverage_report.py` at `67b4784`, with the constant-jump exclusion; the same file was
  used for the d3dc805 run.
- **Sarek CI timings** could not be found: the GitHub API no longer lists any sarek workflow run from February 2025
  (the oldest `ci.yml` run still listed is from 2025-09-17). The times above are this VM's.

## 6. What this does not show

- Coverage of the Nextflow layer only: `script:` blocks count as one line, nothing inside a container is seen, for
  either tree (`nextflow_code_coverage.md`, *What is measured*).
- Sarek's full suite was not run: 2 of its 49 routes (20 nf-test files, 29 pytest-workflow yml files). The
  "sarek default route" row is the benchmark the issue asked for; a "sarek, all routes" figure would need the other
  47 runs on human test data (several hours, several Sentieon routes need a licence).
- Coverage is not correctness, in both trees: an entered closure says the step ran, not what it produced.
