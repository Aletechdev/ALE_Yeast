# Preflight checks — what the pipeline verifies before the first task

At start-up, while the workflow graph is being built and before any task is submitted, yAMP runs a
set of ALE-specific checks on the parameters and the samplesheet. They come on top of the checks
inherited from nf-core/sarek (schema validation, tool/step consistency, missing reference
resources). Every line they print starts with **`[yAMP preflight]`**, so a run's verdicts can be
pulled from the console or `.nextflow.log` with one grep:

```bash
grep '\[yAMP preflight\]' .nextflow.log
```

A run with **no** `[yAMP preflight]` line is on the validated Tier-1 recipe with a consistent
samplesheet. The check runs in seconds, also under `-preview`.

## Errors — the run stops

| Check | Why it is an error |
|---|---|
| **No experiment id** for one or more samples | The samplesheet header must use an `experiment` column. A `patient` header is accepted by the schema but parsed as *empty*, and the run would proceed with read group `SM:[]_<sample>` and every experiment merged into one joint-calling cohort. The pipeline-written `csv/*.csv` restart sheets carry a `patient` header and hit this too: re-run from the original samplesheet — a finished run resumes with `-resume`. |
| **The same input file in more than one row** | A copy-paste slip that aligns one library twice under two names and doubles its evidence in every cohort table. The message names the file(s). |
| **`--qc_only` with `--step` other than `mapping`** | Read QC is the first stage of the mapping step; a run starting later has no reads to QC ([`qc_first_run.md`](qc_first_run.md)). |
| **`--qc_only` with `multiqc` in `--skip_tools`** | There would be no QC report to sign off. |
| **`--qc_only` with `cleanup = true`** | Nextflow would delete the work directory when the QC run completes, so the follow-up run could not `-resume` it. |

## Warnings — the run proceeds

| Check | What it means |
|---|---|
| **Recipe drift** — one line per parameter that differs from the validated Tier-1 recipe (`tools`, `joint_germline`, `split_haplotypecaller_joint_vcf`, `joint_manta`, `manta_high_sensitivity`, and the read-preprocessing parameters `trim_adapter`, `trim_quality_3prime`, `trim_quality_5prime`, `trim_quality_window`, `trim_quality_mean`, `length_required`, `filter_quality`, `clip_r1/r2`, `three_prime_clip_r1/r2`), then a summary line with the count | Any other configuration is allowed — it just is not the one the ottilie contract test and the Azure baseline validate, so its outputs are not covered by them. `tools` is compared as a set: missing Tier-1 callers and extra tools are listed separately. |
| **Mixed `ploidy` or `clonal_or_population` within an experiment** | Legal, but joint calling genotypes every sample of an experiment together and the thresholds are per sample, so a mixed experiment is usually a typo. |
| **`--qc_only` with `fastqc` in `--skip_tools`** | The QC-only run then produces only fastp's report. |

The Tier-1 recipe is the parameter set in `conf/test/ottilie_common.config` plus the read-preprocessing
defaults of `nextflow.config` ([`read_preprocessing.md`](read_preprocessing.md)). The checks keep a
copy of it, and the test suite requires the ottilie profile to produce zero warnings, which is what
keeps the copy honest.

Where they live: `validateAleRecipe()`, `validateAleSamplesheet()` and `validateQcOnly()` in
`subworkflows/local/utils_nfcore_sarek_pipeline/main.nf`; test `tests/preflight.nf.test`.
