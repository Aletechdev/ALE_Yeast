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
samplesheet. The check runs in seconds, also under `-preview`. A second, task-level check reads the
reference files themselves once the run starts — see *Reference files* below; it follows the same
rule (prints only when something is wrong) but, being a task, does not run under `-preview`.

## In the MultiQC reports — the *yAMP input checks* table

Every check that passed or warned is also a row of the **yAMP input checks** table, the first section
of all three MultiQC reports (read-QC, alignment-QC, complete-QC — [`qc_first_run.md`](qc_first_run.md)
→ *The three MultiQC reports*). A run's verdicts can therefore be read without opening its log — on
Seqera Platform from the run's *Outputs* tab, while the run is still going.

| Row | OK says | WARN says |
|---|---|---|
| `Samplesheet: experiment ids` | how many samples, in which experiments | — (a missing id is an error) |
| `Samplesheet: input files listed once` | how many files in how many rows | — (a repeated file is an error) |
| `Samplesheet: ploidy and clonal flag per experiment` | the values seen | which experiment mixes which values |
| `Parameters: Tier-1 recipe` | every recipe setting matches | each deviation |
| `Parameters: --qc_only` (QC-only runs only) | the run stops after read QC | only fastp's report is produced |
| `FASTA vs GFF3 contig names` | see *Reference files* below | — |

Rows are sorted by name. An ERROR row never appears: a failed check stops the run before any report
exists, so errors are read on the console (on Seqera, in the run's error message). The same rows are
kept in `<outdir>/reports/preflight/` — `preflight_samplesheet_params_mqc.tsv` for the start-up
checks, `preflight_reference_mqc.tsv` for the reference task.

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

## Reference files — checked by the first task

The reference files themselves are read by one small task, `PREFLIGHT_REFERENCE`, which runs before
alignment at every `--step` and in a QC-only run — as a task rather than at DAG build so that cloud
paths (`az://`, `s3://`) are staged like any other input. It writes one row per check to the MultiQC
reports (a row of the *yAMP input checks* table) and to
`<outdir>/reports/preflight/preflight_reference_mqc.tsv`. On the console it prints only a failed
verdict, with the same `[yAMP preflight]` prefix, so a clean reference still prints nothing.
An ERROR stops the run at once (exit 65, no retry).

| Check | ERROR — the run stops | OK, with a note | Skipped when |
|---|---|---|---|
| **FASTA vs GFF3 contig names** — the GFF3 given as `--report_gff3` is the gene track of the mutation report, so its contig names must be the FASTA's (the first token of each header). | No name is shared: the gene track would be empty and nothing else would complain. The typical cause is Ensembl-style `I` in one file and SGD/NCBI-style `chrI` in the other; rename the contigs of one file ([`prepare_reference.md`](prepare_reference.md)). | Some GFF3 contigs have no FASTA sequence: the row says which, and their features are simply not shown — the normal picture for a chromosome-subset reference such as the ottilie test set (4 chromosomes against the full-genome GFF3). FASTA contigs without annotation (cassettes, plasmids) are not reported. | `--report_gff3` is not set — the row reads SKIPPED. |

An embedded `##FASTA` section in the GFF3 (SGD and GenBank-converted files carry one) is ignored.
**Not checked here**, by decision (one check shipped, more added as real input errors turn up): a
naming mismatch on part of the genome (`Mito` vs `chrM` with the chromosomes matching) — visible only
as the note, not an error; the
SnpEff cache's contig names and version — a mismatch there fails, or annotates nothing, only at the
annotation step ([`prepare_reference.md`](prepare_reference.md) → chromosome names); a
user-supplied `--fasta_fai` or `--dict` from another FASTA version — fails inside GATK after alignment;
and FASTA syntax (duplicate headers, CRLF line endings) — fails in reference preparation within minutes.

Where they live: `validateAleRecipe()`, `validateAleSamplesheet()` and `validateQcOnly()` in
`subworkflows/local/utils_nfcore_sarek_pipeline/main.nf` (their table rows: `preflightTable()`, whose
header must stay identical to the reference script's), test `tests/preflight.nf.test`; the reference
task in `modules/local/preflight_reference/` runs `bin/preflight_reference.sh` (gawk), configured by
`conf/modules/preflight.config`, test `tests/preflight_reference.nf.test`.
