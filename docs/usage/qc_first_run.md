# QC-first run — look at the reads before the expensive part runs

`--qc_only` turns a launch into a **two-run idiom**: run 1 stops after read QC and exits 0; you look
at the reports and sign them off; run 2 is the *same command* without the flag plus `-resume`, and
continues from alignment with every read-QC task a cache hit. Nothing is computed twice and nothing
is guessed — the second run is the run you would have launched anyway.

```
raw FASTQ ─┬─► FastQC (raw)                                        ┐
           └─► fastp ─► FastQC (after preprocessing) ─► MultiQC    │  run 1: --qc_only  (minutes)
   + preflight checks, reference preparation, GFF3 index           ┘
                       │
                       ▼   the gate: alignment input emptied under --qc_only
             bwa-mem ─► duplicate marking ─► callers ─► annotation ─► mutation report      run 2: -resume
```

## The two runs

**Run 1** — your normal launch plus `--qc_only` (locally, in a params file, or the *QC-first run*
box on the Seqera launch form):

```bash
nextflow -c conf/mymachine.config run main.nf -profile docker -params-file my_project.yml --qc_only
```

It validates the **complete** parameter set (schema, sarek's own checks, the
[`[yAMP preflight]`](preflight_checks.md) checks), prepares the reference, runs FastQC on the raw
reads, fastp, FastQC on the fastp output and MultiQC, and ends with:

```
[yAMP qc_only] QC-only run finished — nothing past read QC was run.
[yAMP qc_only]   MultiQC report : <outdir>/multiqc/yAMP-QC-only-run_multiqc_report.html
[yAMP qc_only]   FastQC / fastp : <outdir>/reports/  (preflight verdicts: grep 'yAMP preflight' .nextflow.log)
[yAMP qc_only]   To continue, run the same command without --qc_only and with -resume <session id>
[yAMP qc_only]   (same work directory and --outdir; every read-QC task is a cache hit):
[yAMP qc_only]     nextflow … -resume <session id>
[yAMP qc_only]   On Seqera Platform: open this run → Resume → set qc_only to false.
```

**Run 2** — the printed command: identical `--input`, `--outdir`, work directory, profile and
revision, `--qc_only` dropped, `-resume <session id>` added. Pass the **session id** the message
prints, not a bare `-resume`: a bare `-resume` resumes whatever ran last in that directory
(`azure_batch_execution.md` → `-resume` hazards). If `qc_only` came from a params file or config
rather than the command line, the message says so — set it to `false` there.

On **Seqera Platform**: open the finished run → *Resume* → clear `qc_only` → launch. Same compute
environment and work directory; the resumed run reuses the QC tasks.

## What to look at before signing off

The MultiQC report of run 1 has two FastQC sections — *FastQC (raw)* and *FastQC (after
preprocessing)* — with fastp between them, and both sets of General Stats columns on the same sample
rows ([`read_preprocessing.md` → Post-trim QC](read_preprocessing.md#post-trim-qc)).

| Look at | Where | What a problem looks like |
|---|---|---|
| Per-base quality after trimming | FastQC (after preprocessing) → *Per base sequence quality* | a 3′ tail still below Q20: raise `trim_quality_mean` or use `trim_quality_3prime right` |
| Residual adapter content | FastQC (after preprocessing) → *Adapter content* | any rising curve: fastp did not detect the kit — pass `--adapter_sequence` / `--adapter_sequence_r2` |
| Reads surviving fastp | fastp → *Filtered reads*; General Stats `% Pass filter` | more than a few % lost: a low-quality library or an over-tight `filter_quality_*` / `length_required` |
| Duplication estimate | fastp → *Duplication*; FastQC → *Sequence duplication levels* | far above the other samples: low-complexity library or PCR over-amplification |
| GC distribution | FastQC → *Per sequence GC content* | a second peak or a shifted mode: contamination, or reads from the wrong organism |
| Reference files agree | *yAMP preflight: reference* table (first section) | an ERROR row is never seen here (it has already stopped the run); read the OK row's note — GFF3 contigs without a FASTA sequence are listed there, the expected picture for a chromosome-subset reference such as the test set ([`preflight_checks.md`](preflight_checks.md)) |
| Expected depth | General Stats: bases after filtering ÷ genome size | below what the experiment needs — the coverage check itself is behind the gate (it needs alignment) |

Run 1 shows **no** mapping rate, coverage or mitochondrial depth and cannot tell reads from the wrong
*strain* apart — alignment is the expensive part and stays behind the gate (decision 2026-09-21). A
later "stop after alignment" level would be a separate parameter.

## What run 1 does and does not do

Runs (and is cached for run 2): preflight checks · the reference preflight task (FASTA vs GFF3 contig
names, [`preflight_checks.md`](preflight_checks.md) → *Reference files*) · FastQC on the raw reads ·
fastp · FastQC on the fastp output · MultiQC · reference preparation (bwa index, `.fai`, sequence
dictionary, intervals, the CNVKit flat reference) · the GFF3 index for the mutation report. On the
ottilie test set that is 18 tasks and about five minutes (measured 2026-09-28).

Does **not** run: alignment and everything downstream — duplicate marking, every caller, annotation,
the mutation report. **breseq** (Tier-2, `--tools breseq --genbank …`) reads the fastp output
directly rather than the alignment, so it is gated separately and is likewise not run. Not checked by
run 1 either: the SnpEff cache (contig names, snpEff version) — it is read only at the annotation
step, in run 2 ([`prepare_reference.md`](prepare_reference.md) → chromosome names).

The QC-only MultiQC report is titled *yAMP QC-only run*, which MultiQC turns into the file name
`yAMP-QC-only-run_multiqc_report.html` (plus `…_report_data/` and `…_report_plots/`), so it stays in
`<outdir>/multiqc/` next to the final run's plain `multiqc_report.html` instead of being overwritten
by it. A `--multiqc_title` of your own wins — but it then names **both** runs' reports the same, so
run 2 replaces run 1's report. Leave `multiqc_title` unset if you want to keep the QC-only copy (it
is unset by default and hidden on the Seqera launch form).

## Rules and errors

`qc_only` is a boolean, default `false`. Combinations that would make the follow-up impossible or the
QC run pointless are refused at start-up (`[yAMP preflight]` errors, run in seconds, also under
`-preview`):

| Combination | Why it is an error |
|---|---|
| `--qc_only` with `--step` other than `mapping` | read QC is the first stage of the mapping step; a run starting later has no reads to QC |
| `--qc_only` with `multiqc` in `--skip_tools` | there would be no report to sign off |
| `--qc_only` with `cleanup = true` in the config | Nextflow would delete the work directory when the QC run completes, so run 2 could not resume it |

`--qc_only` with `fastqc` in `--skip_tools` runs (warning): only fastp's report is produced.

Hash stability: run 2 reuses run 1's tasks only if their inputs and scripts are unchanged. Change
nothing between the two runs except the flag — not the samplesheet, the reference, the trimming
parameters or the pipeline revision. (MultiQC is the one task that runs again: its inputs grow.)

## How it works, and the test that guards it

The gate is a single point in `workflows/sarek/main.nf`: under `--qc_only` the channel that feeds
alignment is emptied, and every process downstream of it starves — a process with no input never
runs — so nothing further down is wrapped and the DAG is identical to a full run. The one thing that
would break this silently is a future process downstream of alignment whose inputs can all be
satisfied on empty input (`toList()`, `ifEmpty(...)`, a value channel or a plain file). Two tests pin
the property (`docs/dev-practices/testing_best_practices.md` §11):

- `tests/qc_gate.sh a` — minutes: a QC-only run of the test set must execute *exactly* the
  allow-listed processes (the list is in the script);
- `tests/qc_gate.sh b <one-shot outdir>` — one e2e: the resumed run must cache every run-1 task,
  execute the same task list as a one-shot run, and produce the same deliverables
  (`tests/qc_gate_compare.py`).

The rebase rule lives in [`SAREK_MODIFICATIONS.md`](../dev-practices/SAREK_MODIFICATIONS.md) →
`workflows/sarek/main.nf` → the `--qc_only` gate.
