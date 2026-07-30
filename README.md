# yAMP — yeast Automated Mutation Pipeline

A variant-calling pipeline for **Adaptive Laboratory Evolution (ALE)** experiments in microbial
genomes, forked from [nf-core/sarek 3.5.1](https://nf-co.re/sarek/3.5.1).

yAMP keeps Sarek's GATK4 best-practice preprocessing and adds ALE-specific calling: joint-germline
HaplotypeCaller with per-sample ploidy, CNV/SV calling with cohort matrices, SnpEff annotation from a
custom cache, and an integrated igv-reports mutation dashboard.

📖 **Full documentation index: [`docs/README.md`](docs/README.md)** ·
📋 [`CHANGELOG.md`](CHANGELOG.md) ·
🔀 [Changes vs upstream Sarek](docs/dev-practices/SAREK_MODIFICATIONS.md)

---

## Requirements

- **Linux x86_64.** Apple Silicon (ARM) is **not supported** — GATK/MultiQC tasks stall or fail.
  Development and validation run on an Azure D4as_v5 VM (4 vCPU / 16 GB).
- **Docker** — [install](https://docs.docker.com/engine/install/).
- **Nextflow 25.10.x**, plus the pipeline's dev toolchain. ⚠️ **Do not `conda install nextflow`
  unpinned** — that installs the latest release (26.x), which **cannot parse this config**. Use:
  ```bash
  conda env create -f environment.yml && conda activate nf-env
  ```
  The launch scripts then `export NXF_VER=25.10.4`, which makes Nextflow self-fetch that exact
  engine on first run (so the first launch needs network access). Why 26.x is blocked:
  [`ale_sarek_upgrade_runbook.md`](docs/dev-practices/ale_sarek_upgrade_runbook.md).
- **Disk** — ~10 GB for the test run (≈400 MB test data + ~8 GB work dir + ~200 MB output).

Setting up a machine from scratch: [`docs/usage/new_machine_setup.md`](docs/usage/new_machine_setup.md).

## Quick start

```bash
git clone git@github.com:Aletechdev/ALE_Yeast.git
cd ALE_Yeast

# fetch the 2-sample test dataset from public blob storage (no credentials needed)
bash docs/benchmarking/ottilie_xenobiotic_ale/01_data_retrieval/download_test_data.sh
```

**Step 1 — tell the pipeline how big your machine is.** `conf/base.config` sizes every task for the
cloud target (4 vCPU / 32 GB), so on a smaller machine tasks would request more RAM than exists and
never get scheduled. Copy the template and edit two numbers:

```bash
cp conf/mymachine.config conf/$(hostname).config
# then set:  cpus = <your vCPUs>,  memory = '<RAM minus ~2 GB>.GB'
```

**Step 2 — run it.**

```bash
export NXF_VER=25.10.4
nextflow -c conf/$(hostname).config run main.nf -profile ottilie_test,docker \
    --outdir ./output_ottilie_test --generate_reports
```

Results land in `output_ottilie_test/`; open `output_ottilie_test/mutation_reports/index.html`.

> On the **16 GB Azure dev VM** there is a shortcut — a registered profile plus a launcher that pins
> the Nextflow version for you:
> ```bash
> bash bin/test_ottilie.sh     # == -profile ottilie_test,azureD4as,docker
> ```
> `azureD4as` hard-codes that VM's ceilings and per-task tuning, so **don't use it on other
> hardware** — use your own `-c` file as above.

### The test dataset

2 samples (parent `NODRUG-GM2` + evolved `CBR110-15-R3a`) from *S. cerevisiae* S288C, subset to
4 chromosomes (I, IV, VII, XV). Truth set: **4 SNVs + a chr I whole-chromosome duplication**
(Ottilie et al., *Commun Biol* 5:128, 2022). The data lives under `data/ottilie/` (gitignored) and is
described in
[`docs/benchmarking/ottilie_xenobiotic_ale/DATA_PROVENANCE.md`](docs/benchmarking/ottilie_xenobiotic_ale/DATA_PROVENANCE.md).

The profile is `conf/test/ottilie_test.config`, and the same run is the pipeline's automated contract
test (`tests/ottilie_e2e.nf.test`).

## Running your own data

### Where to put it — run from your own directory, not the repo

Nextflow doesn't need to be launched from the pipeline directory. Keep each project in its own
folder and point at `main.nf` by path:

```
~/projects/myproject/
├── data/              # FASTQs (or leave them wherever they already are)
├── ref/               # FASTA + SnpEff cache, from process_genbank_auto.sh
├── samplesheet.csv    # ABSOLUTE paths to the FASTQs
├── run.sh
├── work/              # created here, not in the repo
└── output/
```

```bash
cd ~/projects/myproject
export NXF_VER=25.10.4
nextflow -c /path/to/ALE_Yeast/conf/$(hostname).config \
    run /path/to/ALE_Yeast/main.nf -profile docker \
    --input samplesheet.csv --outdir ./output   # …plus the params in "Launch" below
```

`work/` and outputs land in the project folder, so `git status` on the pipeline stays clean, a
finished project is one `rm -rf`, and `git pull` never touches your data.

Use the in-repo layout (`data/<name>/`, a launcher in `bin/`) only for things that should ship *with*
the pipeline — a shared benchmark or test set, like `data/ottilie/`. Note `bin/` is not a general
script folder: Nextflow puts it on `PATH` inside every task container, and it is git-tracked.

> **Samplesheet paths must be absolute** — they're validated at launch (`exists: true`), and relative
> ones would resolve against whatever directory you happened to launch from. That makes the
> samplesheet machine-specific, so **generate it rather than hand-maintaining it** (`"$PWD"/data/…`),
> the same way `download_test_data.sh` regenerates the ottilie one per machine.

### Fitting the run to your machine

Same `-c` file as in the quick start — [`conf/mymachine.config`](conf/mymachine.config) is a
commented template; the load-bearing part is three lines:

```groovy
process {
    resourceLimits = [ cpus: 8, memory: '28.GB', time: '72.h' ]   // vCPUs, RAM − ~2 GB headroom
}
```

`resourceLimits` is a **clamp** applied after every other mechanism — including the retry escalation
`{ 16.GB * task.attempt }` — so it caps requests wherever they came from. That's why it's the one
setting you must get right; the rest is optional throughput tuning.

Notes:

- **It has to be a file.** `resourceLimits` cannot be set on the command line — `-process.` can't
  express a map, and there is no `--max_memory` param in this pipeline.
- **No `executor` block on purpose.** Without one, Nextflow's local executor auto-detects the host's
  CPUs and RAM and sizes concurrency itself. Hand-setting a pool that barely exceeds a single task's
  request can deadlock the scheduler — see
  [`docs/usage/nextflow_local_executor_deadlock.md`](docs/usage/nextflow_local_executor_deadlock.md).
- **Keep the file params-free.** `-c` outranks `-profile`, so any `params.*` in it will override the
  profile's settings.

If you'll reuse a machine often, promote the file to a named profile
(`<machine> { includeConfig 'conf/<machine>.config' }` in `nextflow.config`) — that's what
`azureD4as` is. Full precedence rules, both porting options, and the cloud story:
[`docs/dev-practices/compute_resources.md`](docs/dev-practices/compute_resources.md).

### Launch

```bash
nextflow -c conf/mymachine.config run main.nf -profile docker \
    --input samplesheet.csv --outdir ./output \
    --fasta ref.fasta --snpeff_cache ./snpeff_cache --snpeff_db <genome_name> \
    --genome null --igenomes_ignore \
    --skip_tools baserecalibrator \
    --tools snpeff,haplotypecaller,cnvkit,manta,tiddit \
    --joint_germline --split_haplotypecaller_joint_vcf --generate_reports
```

`--skip_tools baserecalibrator` is **required**: BQSR needs known-sites VCFs, which custom microbial
references don't have. Omitting it aborts the run.

### Input samplesheet

| Column | Description |
|--------|-------------|
| `experiment` | Experiment ID (maps to Sarek's "patient"); groups samples for joint calling |
| `sample` | Sample ID in ALE format (e.g. `A1-F6-I1-R1`) |
| `status` | `0` = normal. ALE treats **all** samples as normal so HaplotypeCaller runs joint-germline |
| `clonal_or_population` | `clonal` for isolate sequencing, `population` for bulk/pooled |
| `ploidy` | `1` = haploid, `2` = diploid (higher supported) |
| `sex` | `XX` for yeast — only read by Control-FREEC/ASCAT (Tier 2); inert otherwise |
| `lane` | Sequencing lane (e.g. `L001`); multiple lanes per sample are merged |
| `fastq_1`, `fastq_2` | Paired-end FASTQ paths (absolute, or `az://` blob URLs) |

```csv
experiment,sample,status,clonal_or_population,ploidy,sex,lane,fastq_1,fastq_2
Ottilie_test,NODRUG-GM2,0,clonal,1,XX,L001,/data/NODRUG-GM2_R1.fastq.gz,/data/NODRUG-GM2_R2.fastq.gz
Ottilie_test,CBR110-15-R3a,0,clonal,1,XX,L001,/data/CBR110-15-R3a_R1.fastq.gz,/data/CBR110-15-R3a_R2.fastq.gz
```

Full column reference and conventions:
[`docs/usage/input_samplesheet.md`](docs/usage/input_samplesheet.md).

### Preparing a reference from GenBank

`docs/prepare_input/process_GeneBank/process_genbank_auto.sh` converts a `.gbk`/`.gb` file into
everything the pipeline needs — reference FASTA (`--fasta`), GFF3 annotations, and a SnpEff cache
(`--snpeff_cache` / `--snpeff_db`):

```bash
bash docs/prepare_input/process_GeneBank/process_genbank_auto.sh <input.gbk> [output_dir]
```

`--snpeff_db` is the genome name derived from the GenBank `ORGANISM` field (lowercase, spaces →
underscores) — e.g. `Ogataea polymorpha` → `ogataea_polymorpha`, matching the
`snpeff_cache/ogataea_polymorpha/` subdirectory. The script prints the exact parameters to use and
records the name in `organism_info.sh`. Only GenBank inputs are tracked in git; processed outputs are
generated locally. To (re)build only the SnpEff cache, use
`docs/prepare_input/process_GeneBank/generate_cache/gen_cache.sh`.

## Variant calling tools

**Tier 1 — validated for ALE in v1.0.0** (exactly what the contract test exercises):

| Tool | Type | Ploidy support | Notes |
|------|------|----------------|-------|
| HaplotypeCaller | SNV / INDEL | `--sample-ploidy` per sample | Joint germline; cohort + per-sample VCFs; soft-filter fallback where VQSR can't run |
| CNVKit | CNV | Diploid baseline | `--ploidy` not passed; use `fold_change = 2^log2`. See [`cnvkit_ploidy_behavior.md`](docs/variant-calling/cnvkit/cnvkit_ploidy_behavior.md) |
| TIDDIT | SV | `-n` ploidy | Affects coverage normalization and DUP/DEL GT thresholds. See [`tiddit_ploidy_behavior.md`](docs/variant-calling/tiddit/tiddit_ploidy_behavior.md) |
| Manta | SV | Diploid only | Breakpoint caller — no ploidy parameter by design; used for cross-validation |
| SnpEff | Annotation | — | Custom cache built from GenBank |

**Tier 2 — functional but not release-validated for ALE:** Control-FREEC, breseq, Mutect2, FreeBayes,
DeepVariant, Strelka. Enable via `--tools`; see
[`docs/variant-calling/tier2_af_filters.md`](docs/variant-calling/tier2_af_filters.md).

## Output

```
<outdir>/
├── preprocessing/            # markduplicates CRAMs
├── variant_calling/          # per-caller VCFs (haplotypecaller, cnvkit, manta, tiddit)
├── variant_calling_filtered/ # hard-filtered HC VCFs
├── annotation/               # SnpEff-annotated VCFs
├── reports/ multiqc/         # QC (fastqc, mosdepth, samtools, bcftools, snpeff) + MultiQC
├── mutation_reports/         # the ALE dashboard — start at index.html
└── pipeline_info/            # execution report, timeline, trace, software versions
```

The **mutation report bundle** is the ALE-specific deliverable — start at its `index.html`:

```
mutation_reports/
├── index.html               # entry point — links everything below
├── cohort_report.html       # cross-sample igv-report
├── samples/                 # <sample>_{hc,cnvkit,manta,tiddit}_report.html
├── data/                    # cn_cohort_{full,collapsed}.csv, sv_cohort_matrix_union{,_pass}.csv,
│                            # cn_matrices/, sv_merged/, *.tiddit.pass_stats.tsv
└── vcf/                     # curated per-caller VCFs (see vcf/README.md in the bundle)
```

How the reports are built and how to read them:
[`docs/README.md#output--reporting`](docs/README.md#output--reporting).

## Testing

```bash
nf-test test tests/ottilie_e2e.nf.test -c tests/nf-test-ottilie.config
```

See [`docs/dev-practices/testing_best_practices.md`](docs/dev-practices/testing_best_practices.md).

## Cloud deployment

Seqera Platform + Azure Batch is supported via `conf/seqera_azure.config`. Checklist and known issues:
[`docs/seqera_cloud/seqera_cloud_deployment_checklist.md`](docs/seqera_cloud/seqera_cloud_deployment_checklist.md).

## Credits

yAMP is a fork of [nf-core/sarek](https://nf-co.re/sarek) 3.5.1; upstream credits and tool citations
are retained in [`CITATIONS.md`](CITATIONS.md).
