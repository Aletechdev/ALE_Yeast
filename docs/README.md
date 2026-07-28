# yAMP documentation

**yAMP** — *yeast Automated Mutation Pipeline* — is a variant-calling pipeline for **Adaptive
Laboratory Evolution (ALE)** experiments in microbial genomes, forked from
[nf-core/sarek 3.5.1](https://nf-co.re/sarek/3.5.1). It keeps Sarek's GATK4 best-practice
preprocessing and adds ALE-specific calling, variable ploidy, and an integrated mutation-report
dashboard.

This page is the **index** to `docs/`. Start here:

| If you want to… | Read |
|---|---|
| Install and run the pipeline | [Quick start](#quick-start) below, then [`usage/input_samplesheet.md`](usage/input_samplesheet.md) |
| Know what changed vs upstream Sarek | [`dev-practices/SAREK_MODIFICATIONS.md`](dev-practices/SAREK_MODIFICATIONS.md) |
| Know what's in this release | [`../CHANGELOG.md`](../CHANGELOG.md) |
| Understand a specific tool's behavior | [Variant calling & CNV/SV](#variant-calling--cnvsv) below |
| Interpret the outputs | [Output](#output) below |
| Work on the pipeline code | [Development & maintenance](#development--maintenance) below |

---

## Pipeline summary

Reads → alignment → duplicate marking → variant calling → annotation → reports.

| Stage | Tools | Notes |
|---|---|---|
| Preprocessing | FastQC, BWA-MEM, GATK MarkDuplicates | BQSR is **skipped** — custom genomes have no known-sites VCFs (`--skip_tools baserecalibrator` is required) |
| SNV / INDEL | **GATK HaplotypeCaller** (joint germline) | Cohort VCF + per-sample split; soft-filter fallback where VQSR can't run |
| CNV | **CNVKit** | `fold_change = 2^log2` matrices (ploidy-agnostic) |
| SV | **Manta + TIDDIT** | Merged with SURVIVOR into per-sample + cohort matrices |
| Annotation | **SnpEff** | Custom cache built from a GenBank file |
| Reporting | MultiQC + **MUTATION_REPORT** | igv-reports HTML dashboard, CN/SV cohort matrices, linked index |

### Tool support tiers

**Tier 1 — validated for ALE in v1.0.0** (exactly what `conf/test/ottilie_test.config` runs, and what
the end-to-end contract test asserts): `snpeff, cnvkit, tiddit, manta, haplotypecaller` + joint
germline, joint-VCF split, hard filter, and MUTATION_REPORT.

**Tier 2 — functional, not release-validated for ALE:** Control-FREEC, breseq, Mutect2, FreeBayes,
DeepVariant, Strelka. These run through the standard Sarek pathways and can be enabled via `--tools`,
but are not covered by the release test. See [`variant-calling/tier2_af_filters.md`](variant-calling/tier2_af_filters.md).

---

## Quick start

Requirements: Linux x86_64 (Apple Silicon is **not** supported), Docker, and Nextflow **25.10.x**
(the launchers pin `NXF_VER=25.10.4`; 26.x cannot parse this config — see
[`dev-practices/ale_sarek_upgrade_runbook.md`](dev-practices/ale_sarek_upgrade_runbook.md)).

```bash
# 1. fetch the 2-sample test dataset (public blob, no credentials)
bash docs/benchmarking/ottilie_xenobiotic_ale/01_data_retrieval/download_test_data.sh

# 2. tell the pipeline your machine's size (copy the template, edit cpus + memory)
cp conf/mymachine.config conf/$(hostname).config

# 3. run the test profile
nextflow -c conf/$(hostname).config run main.nf -profile ottilie_test,docker \
    --outdir ./output_ottilie_test --generate_reports
```

Step 2 matters because `conf/base.config` sizes tasks for the cloud target (4 vCPU / 32 GB) — on a
smaller machine, tasks request more RAM than exists and never schedule.
[`conf/mymachine.config`](../conf/mymachine.config) is a commented template; only
`process.resourceLimits` is load-bearing. On the **16 GB Azure dev VM** only, `bash bin/test_ottilie.sh`
is a shortcut for `-profile ottilie_test,azureD4as,docker` — `azureD4as` hard-codes that VM's ceilings,
so don't use it elsewhere. Details: [`dev-practices/compute_resources.md`](dev-practices/compute_resources.md).

For your own data, the minimum is a samplesheet, a reference FASTA, and a SnpEff cache:

```bash
nextflow -c conf/mymachine.config run main.nf -profile docker \
    --input samplesheet.csv --outdir ./output \
    --fasta ref.fasta --snpeff_cache ./snpeff_cache --snpeff_db <genome_name> \
    --genome null --igenomes_ignore \
    --skip_tools baserecalibrator \
    --tools snpeff,haplotypecaller,cnvkit,manta,tiddit \
    --joint_germline --split_haplotypecaller_joint_vcf --generate_reports
```

### Input & preparation

| Doc | What it covers |
|---|---|
| [`usage/input_samplesheet.md`](usage/input_samplesheet.md) | Samplesheet columns (`experiment`, `status`, `ploidy`, `clonal_or_population`, …), conventions, and the one-normal-per-experiment rule |
| [`prepare_input/process_GeneBank/`](prepare_input/) | GenBank → FASTA + GFF3 + SnpEff cache (`generate_cache/gen_cache.sh`) |
| [`prepare_input/sarek_csv_to_XPMD/README.md`](prepare_input/sarek_csv_to_XPMD/README.md) | Samplesheet conversion to XPMD format |
| [`benchmarking/ottilie_xenobiotic_ale/DATA_PROVENANCE.md`](benchmarking/ottilie_xenobiotic_ale/DATA_PROVENANCE.md) | Test-data lineage, truth set, and how to regenerate or download it |

### Running & deployment

| Doc | What it covers |
|---|---|
| [`dev-practices/compute_resources.md`](dev-practices/compute_resources.md) | Resource model, `resourceLimits` clamp, per-VM porting, cloud notes |
| [`seqera_cloud/seqera_cloud_deployment_checklist.md`](seqera_cloud/seqera_cloud_deployment_checklist.md) | Seqera Platform + Azure Batch deployment checklist |
| [`seqera_cloud/azure_batch_recommendations.md`](seqera_cloud/azure_batch_recommendations.md) | Azure Batch VM sizing |
| [`usage/azure_vm_swap_setup.md`](usage/azure_vm_swap_setup.md) · [`usage/azure_blob_large_file_upload.md`](usage/azure_blob_large_file_upload.md) | VM swap; uploading >50 GB files to blob |
| [`usage/nextflow_local_executor_deadlock.md`](usage/nextflow_local_executor_deadlock.md) | Local-executor deadlock and how to avoid it |
| [`dev-practices/troubleshooting.md`](dev-practices/troubleshooting.md) | Common run failures (starting with misleading samplesheet errors) |

---

## Output

```
<outdir>/
├── preprocessing/           # markduplicates CRAMs (+ index)
├── variant_calling/         # per-caller VCFs: haplotypecaller, cnvkit, manta, tiddit
├── variant_calling_filtered/# hard-filtered HC VCFs (intermediate)
├── annotation/              # SnpEff-annotated VCFs per caller
├── reports/                 # fastqc, mosdepth, samtools, bcftools, vcftools, snpeff
├── multiqc/                 # multiqc_report.html
├── mutation_reports/        # the ALE dashboard (see below)
├── csv/                     # machine-readable run manifests
└── pipeline_info/           # execution report/timeline/trace, software versions
```

The **mutation report bundle** is the ALE-specific deliverable:

```
mutation_reports/
├── index.html               # entry point — links everything below
├── cohort_report.html       # cross-sample igv-report
├── samples/                 # <sample>_{hc,cnvkit,manta,tiddit}_report.html
├── data/                    # cn_cohort_{full,collapsed}.csv, sv_cohort_matrix_union{,_pass}.csv,
│                            # cn_matrices/, sv_merged/, *.tiddit.pass_stats.tsv
└── vcf/                     # curated per-caller VCFs (see vcf/README.md in the bundle)
```

| Doc | What it covers |
|---|---|
| [`igvreports/README.md`](igvreports/README.md) | igv-reports report structure, templates, and the static assets the pipeline consumes |
| [`igvreports/check_mutations.md`](igvreports/check_mutations.md) | How the report is assembled for ALE variant review |
| [`generate_mutation_report/README.md`](generate_mutation_report/README.md) | MUTATION_REPORT integration design |
| [`generate_mutation_report/generate_index_container.md`](generate_mutation_report/generate_index_container.md) | The `ale-reports` container (pandas + jinja2) used by GENERATE_INDEX |
| [`qc-reporting/multiqc_mosdepth_coverage.md`](qc-reporting/multiqc_mosdepth_coverage.md) | How to read MultiQC/mosdepth coverage numbers |
| [`manual_vcf_operations.md`](manual_vcf_operations.md) | bcftools recipes for slicing pipeline VCFs by hand |

---

## Variant calling & CNV/SV

### SNV / INDEL — HaplotypeCaller (Tier 1)

| Doc | What it covers |
|---|---|
| [`variant-calling/haplotypecaller/haplotypecaller_workflow_analysis.md`](variant-calling/haplotypecaller/haplotypecaller_workflow_analysis.md) | Joint vs individual calling; the known-sites starvation pattern on custom genomes (why BQSR/VQSR are off) |
| [`variant-calling/haplotypecaller/SOFT_FILTER_HAPLOTYPECALLER_JOINT.md`](variant-calling/haplotypecaller/SOFT_FILTER_HAPLOTYPECALLER_JOINT.md) | `VARIANTFILTRATION_FALLBACK` — thresholds, FILTER tags, PASS extraction |
| [`variant-calling/haplotypecaller/HARD_FILTER_HAPLOTYPECALLER_JOINT.md`](variant-calling/haplotypecaller/HARD_FILTER_HAPLOTYPECALLER_JOINT.md) | `--hard_filter_haplotypecaller_joint` (clonal/population AF thresholds) |
| [`variant-calling/haplotypecaller/SPLIT_JOINT_VCF_PIPELINE.md`](variant-calling/haplotypecaller/SPLIT_JOINT_VCF_PIPELINE.md) | `--split_haplotypecaller_joint_vcf` — per-sample extraction, channel flow |
| [`compare_single_pop_HpCaller/README.md`](compare_single_pop_HpCaller/README.md) | Single-sample vs joint calling comparison |

### CNV — CNVKit (Tier 1)

| Doc | What it covers |
|---|---|
| [`variant-calling/cnvkit/cnvkit_cn_calculation.md`](variant-calling/cnvkit/cnvkit_cn_calculation.md) | **Canonical** CN-matrix reference — `fold_change = 2^log2`, cohort collapse, column schema |
| [`variant-calling/cnvkit/cnvkit_ploidy_behavior.md`](variant-calling/cnvkit/cnvkit_ploidy_behavior.md) | Why integer `cn` is always diploid-baseline regardless of ploidy; VCF export |
| [`variant-calling/cnvkit/cnvkit_sarek_dual_call.md`](variant-calling/cnvkit/cnvkit_sarek_dual_call.md) | `.call.cns` vs `.germline.call.cns` |
| [`variant-calling/cnvkit/cnvkit_small_chr_exclusion.md`](variant-calling/cnvkit/cnvkit_small_chr_exclusion.md) | Small-chromosome exclusion in WGS mode |

### SV — Manta + TIDDIT + SURVIVOR (Tier 1)

| Doc | What it covers |
|---|---|
| [`variant-calling/sv_merge.md`](variant-calling/sv_merge.md) | **Maintainer reference** for the SURVIVOR merge chain — CLI params, `SUPP_VEC`, `proximity_match`, CSV schema, gotchas |
| [`variant-calling/tiddit/tiddit_ploidy_behavior.md`](variant-calling/tiddit/tiddit_ploidy_behavior.md) | TIDDIT `-n` ploidy effects on normalization and GT thresholds |
| [`variant-calling/manta/manta_filter_vs_ft.md`](variant-calling/manta/manta_filter_vs_ft.md) | `FILTER` vs `FORMAT/FT` in single-sample Manta |

### Tier 2 tools

| Doc | What it covers |
|---|---|
| [`variant-calling/tier2_af_filters.md`](variant-calling/tier2_af_filters.md) | AF-based somatic filters for Mutect2 & FreeBayes, and why they're Tier 2 |
| [`variant-calling/mutect2/mutect2_custom_genome_resources.md`](variant-calling/mutect2/mutect2_custom_genome_resources.md) | Running Mutect2 without germline-resource / panel-of-normals |
| [`variant-calling/mutect2/MUTECT2_JOINT_CALLING_TIMEOUT.md`](variant-calling/mutect2/MUTECT2_JOINT_CALLING_TIMEOUT.md) | Joint-Mutect2 timeout behavior |
| [`variant-calling/freebayes/FREEBAYES_FILTERING_PIPELINE.md`](variant-calling/freebayes/FREEBAYES_FILTERING_PIPELINE.md) | FreeBayes filtering chain (germline mode only) |
| [`variant-calling/controlfreec/controlfreec_germline_changes.md`](variant-calling/controlfreec/controlfreec_germline_changes.md) | Control-FREEC single-sample germline mode |
| [`variant-calling/breseq/BRESEQ_LOW_COVERAGE_BEHAVIOR.md`](variant-calling/breseq/BRESEQ_LOW_COVERAGE_BEHAVIOR.md) | ⚠️ breseq calls **false whole-chromosome deletions** on low-coverage / subsampled data — read before trusting any breseq output |
| [`variant-calling/breseq/BRESEQ_INTEGRATION_PLAN.md`](variant-calling/breseq/BRESEQ_INTEGRATION_PLAN.md) | breseq subworkflow design & integration record (as-built) |
| [`investigate_filter/mutect2_filter/README.md`](investigate_filter/mutect2_filter/README.md) | Mutect2 filtering-strategy investigation |
| [`compare_mutect2_HpCaller/CENPK_all/paper_a_benchmark/README.md`](compare_mutect2_HpCaller/CENPK_all/paper_a_benchmark/README.md) | VCF filtering guidelines from the Mutect2-vs-HC benchmark |

### Background reading

[`usage/variantcalling/`](usage/variantcalling/) — a general variant-calling tutorial
([introduction](usage/variantcalling/introduction.md) · [theory](usage/variantcalling/theory.md) ·
[Sarek](usage/variantcalling/sarek.md) · [interpretation](usage/variantcalling/interpretation.md)).

---

## Development & maintenance

| Doc | What it covers |
|---|---|
| [`dev-practices/release_process.md`](dev-practices/release_process.md) | **SOP for cutting a release** — checklist, tag → container-image flow, verification, and the CI/registry gotchas |
| [`dev-practices/check_docs.py`](dev-practices/check_docs.py) | Doc consistency checker (broken markdown links + stale backticked repo paths); used by the release checklist |
| [`dev-practices/SAREK_MODIFICATIONS.md`](dev-practices/SAREK_MODIFICATIONS.md) | Full inventory of fork changes vs pristine sarek 3.5.1 |
| [`dev-practices/ale_sarek_upgrade_runbook.md`](dev-practices/ale_sarek_upgrade_runbook.md) | How to rebase onto a newer sarek; the Nextflow 26.x blocker inventory |
| [`dev-practices/testing_best_practices.md`](dev-practices/testing_best_practices.md) | nf-test strategy, what is (and isn't) tested here, coverage targets |
| [`dev-practices/compute_resources.md`](dev-practices/compute_resources.md) | Resource model and config layout |
| [`dev-practices/roadmap.md`](dev-practices/roadmap.md) | Prioritized post-1.0.0 work |
| [`dev-practices/troubleshooting.md`](dev-practices/troubleshooting.md) | Debugging guide |
| [`dev-practices/container_null_cloud_portability.md`](dev-practices/container_null_cloud_portability.md) | Replacing `container null` processes for cloud portability |
| [`pipeline-guides/NEXTFLOW_EXT_PREFIX_GUIDE.md`](pipeline-guides/NEXTFLOW_EXT_PREFIX_GUIDE.md) | How `ext.prefix` works in nf-core module configs |
| [`fixes/`](fixes/) | Write-ups of individual resolved defects (MultiQC versions map, `bin/` staging tar paths, VM resource limits) |
| [`yAMP_docs/yAMP_design.md`](yAMP_docs/yAMP_design.md) | Design overview / project write-up |

Project-level operational notes for contributors live in [`../CLAUDE.md`](../CLAUDE.md).

---

## Benchmarking & validation

| Doc | What it covers |
|---|---|
| [`benchmarking/README.md`](benchmarking/README.md) | Index of benchmark studies and their conventions |
| [`benchmarking/ottilie_xenobiotic_ale/README.md`](benchmarking/ottilie_xenobiotic_ale/README.md) | The release benchmark — *S. cerevisiae* S288C xenobiotic ALE (Ottilie et al. 2022); truth set = 4 SNVs + a chr I duplication |
| [`benchmarking/ottilie_xenobiotic_ale/DATA_PROVENANCE.md`](benchmarking/ottilie_xenobiotic_ale/DATA_PROVENANCE.md) | SRA → CRAM → test-FASTQ lineage and durability |
| [`benchmarking/adipic_acid_ale/README.md`](benchmarking/adipic_acid_ale/README.md) | breseq vs HaplotypeCaller on CEN.PK113-7D |

---

## Archive

[`archive/`](archive/) holds superseded designs and closed investigations, kept for provenance only —
they do **not** describe current behavior. Notably
[`archive/variant_dashboard_system.md`](archive/variant_dashboard_system.md) (the pre-MUTATION_REPORT
dashboard design), [`archive/sarek_fork_ideas.md`](archive/sarek_fork_ideas.md) (deferred fork ideas),
and per-tool investigation notes under `archive/cnvkit/` and `archive/igvreports/`.

---

## Credits

yAMP is a fork of [nf-core/sarek](https://nf-co.re/sarek) 3.5.1 — all upstream credits and tool
citations are retained in [`../CITATIONS.md`](../CITATIONS.md). ALE-specific development is by the
Aletech team (https://github.com/Aletechdev/ALE_Yeast).
