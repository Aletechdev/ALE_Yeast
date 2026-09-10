# Launching with a params file

A params file is one YAML (or JSON) document holding every `--parameter` of a launch. It replaces a
long command line, it is the record of exactly what was launched, and it is the way to set the
parameters the Seqera launch form hides. Copy the template, fill in the six dataset lines, launch.

**Template:** [`params_template.yml`](params_template.yml) — every launch-form field in launch-form
order, at the validated Tier-1 recipe values, plus the hidden parameters a Tier-1 run needs. It is
generated from the pipeline schema and the recipe config by `bin/make_params_template.py`, so it
cannot drift from the form; do not edit it in place, copy it.

## 1. Fill the template

The six `<-- SET` lines are the dataset. Everything else is the recipe; leave it, or delete the lines
you do not change (a deleted line falls back to the pipeline default, which is the same value).

```yaml
# my_project_2026-09-10-01.yml — a real dataset, Tier-1 recipe
input: "/data/my_project/samplesheet.csv"            # absolute paths inside the CSV too
outdir: "/data/my_project/results/2026-09-10-01"     # new directory for every run
fasta: "/data/references/my_strain/my_strain.fa"
snpeff_cache: "/data/references/my_strain/snpeff_cache"  # the directory that CONTAINS <db>/
snpeff_db: "my_strain"                                  # the <db> directory name
report_gff3: "/data/references/my_strain/my_strain.gff3"     # optional gene track for the report

tools: "snpeff,cnvkit,tiddit,manta,haplotypecaller"
joint_germline: true
joint_manta: true
generate_reports: true

skip_tools: "baserecalibrator"      # hidden on the form, required on a custom genome
genome: null
igenomes_ignore: true
split_haplotypecaller_joint_vcf: true
```

Cloud paths (`az://`, `s3://`, `gs://`) work in every line, including `snpeff_cache`, as long as the
run's credential can read them (Azure Batch has one extra rule, see
[`azure_batch_execution.md`](../dev-practices/azure_batch_execution.md)). Date the file name or the
`outdir` per run: `publishDir` overwrites files but never deletes the ones a later version stops
producing, so a reused `outdir` silently mixes runs.

## 2. Launch it — three ways

| Where | How | Notes |
|---|---|---|
| Command line | `nextflow -c conf/mymachine.config run main.nf -profile docker -params-file my_project.yml` | Machine resources still come from the config file, not from params ([README → Fitting the run to your machine](../../README.md#fitting-the-run-to-your-machine)). |
| Seqera launch form | **Upload params file**, or paste into the **Params file view** (YAML or JSON) | The upload replaces the form's parameters box; the form view then shows the values. Hidden parameters in the file are applied even though the form does not display them. |
| Seqera CLI | `tw launch <pipeline> --params-file my_project.yml -p docker` | `tw launch` has no per-parameter flag; the params file is the only way to set one. |

The Seqera form injects the schema default of some parameters into the submitted params. A value in
your file replaces the default before submission, so every parameter that matters belongs in the
file, not only in a profile ([`azure_batch_execution.md` §13](../dev-practices/azure_batch_execution.md)).

## 3. Precedence

Highest first. Measured on Nextflow 25.10.4 (2026-09-10):

1. Command-line `--parameter` flags.
2. `-params-file` (on Seqera: the parameters box, which an uploaded file becomes).
3. Config files and profiles (`-c`, `-profile`).
4. `nextflow.config` defaults.

So `nextflow run … -params-file my.yml --outdir /elsewhere` publishes to `/elsewhere`, and a
profile cannot override anything the file sets.

## 4. Traps

- **`null` on the command line is a string.** `--genome null` sets `genome` to the text `"null"`;
  in a YAML file `genome: null` is a real null. Worse, an empty value (`--genome ''`) becomes
  boolean `true`. Put nulls in the file.
- **`snpeff_cache` is a directory**, the one that contains `<snpeff_db>/`. A `.tar.gz` is not
  accepted. On a Seqera launch it must be reachable from the head job, so a blob path, not a local
  one ([README → Running the SnpEff cache from cloud storage](../../README.md#running-the-snpeff-cache-from-cloud-storage)).
- **Every path must exist at launch**, and samplesheet paths must be absolute: they are checked
  when the workflow graph is built, and relative ones resolve against the launch directory.
- **`outdir` reuse.** New directory per run, see §1. A `-resume` must be given the original
  `outdir` explicitly or it publishes into a new one.
- **`skip_tools: "baserecalibrator"` is not optional** on a custom genome. Dropping it aborts the run
  with a Nextflow join error, not a GATK message
  ([`haplotypecaller_workflow_analysis.md`](../variant-calling/haplotypecaller/haplotypecaller_workflow_analysis.md#4-the-known-sites-starvation-pattern-custom-genomes)).
- **JSON is accepted, but without comments.** Nextflow rejects `//` and `/* */` in a JSON params
  file. Use YAML when you want the annotations.
- **Hidden parameters are still parameters.** Anything under "Show hidden params" on the form, or
  in `nextflow run main.nf --help_full`, can be set in the file. The template lists the ones a
  Tier-1 run needs; the rest are documented per topic, for example the UMI and split-FASTQ options in
  [`read_preprocessing.md`](read_preprocessing.md).

## Keeping the template current

`python bin/make_params_template.py --check` fails when the committed template no longer matches the
schema or `conf/test/ottilie_common.config`. Run the script without `--check` to regenerate, and
commit the result with the change that made it stale, as with `bin/apply_schema_overlay.py`.
