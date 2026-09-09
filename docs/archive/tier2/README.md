# Archived Tier-2 additions — FreeBayes/Mutect2 AF filters, Control-FREEC germline mode

**Removed from the pipeline on 2026-09-09** (PLAN §C, user decision). The code is not lost: every
file is in git history, and the tag **`tier2-tools-last`** (= commit `cd1a7d0`) marks the last commit
that still carries all of it. This page is the index for finding it again.

## Why removed

None of it is part of the Tier-1 ALE recipe (`snpeff,cnvkit,tiddit,manta,haplotypecaller`, all
samples germline). The AF filters were somatic-style post-filters for callers ALE does not use for
its deliverables; the Control-FREEC germline mode was superseded by CNVKit as the CNV deliverable
(no BAF on a custom genome, no VCF for SnpEff, `ASSESS_SIGNIFICANCE` fails at ploidy 1, and it
crashed on 4 of 86 tier-2 samples). Each removal shrinks the fork's rebase surface for the next sarek
upgrade (`docs/dev-practices/ale_sarek_upgrade_runbook.md`). The upstream callers themselves are
untouched: `--tools freebayes`, `mutect2` and `controlfreec` still run exactly as in sarek 3.5.1.

## What was removed, and where it lived

| Feature | Files (at `tier2-tools-last`) | Removing commit |
|---|---|---|
| FreeBayes AF filter | `subworkflows/local/vcf_filter_freebayes/` (+ `bcftools/filter_normal`), `conf/modules/custom_freebayes_filter.config`, params `freebayes_qual_threshold`, `freebayes_dp_threshold`, `freebayes_af_threshold`, `freebayes_high_impact` (never wired — "TODO: implement" in `nextflow.config`), the `TABIX_TABIX` index step in `workflows/sarek/main.nf` that fed the filters (published `tabix/*.tbi`) | see CHANGELOG "Removed" |
| Mutect2 AF filter | `subworkflows/local/vcf_filter_mutect2/` (+ `bcftools/filter_somatic`), `conf/modules/custom_mutect2_filter.config`, the `VCF_FILTER_MUTECT2` call in `workflows/sarek/main.nf` | see CHANGELOG "Removed" |
| Control-FREEC germline mode | `subworkflows/local/bam_variant_calling_germline_controlfreec/`, its wiring in `bam_variant_calling_germline_all` (`chr_files`/`mappability` takes, the `controlfreec` branch of the mpileup condition), the `conf/modules/controlfreec.config` edits (`meta.ploidy` instead of `cf_ploidy`, `FREEC_GERMLINE` block, `ASSESS_SIGNIFICANCE` skip at ploidy 1), the one-line `modules/nf-core/controlfreec/freec/main.nf` patch (`BAF` output optional), and the `MAKEGRAPH2` join relaxations in `bam_variant_calling_somatic_controlfreec` / `_tumor_only_controlfreec` — all reverted to pristine sarek 3.5.1 | see CHANGELOG "Removed" |
| Legacy launch preset | `conf/params_seqera_test.yml` (CEN.PK dataset, tools incl. freebayes + breseq, `chr_dir`/`genbank`) — superseded by the generated Launchpad box | see CHANGELOG "Removed" |

Kept on purpose: `mutect2_custom_genome_resources.md` and `MUTECT2_JOINT_CALLING_TIMEOUT.md` (about
the upstream caller, still runnable), the FilterMutectCalls channel fix in
`bam_variant_calling_somatic_mutect2` and the FreeBayes-somatic disable in
`bam_variant_calling_somatic_all` (caller-level, not filters), the `--ploidy` passthrough in
`conf/modules/freebayes.config`, the YAML `processVersionsFromYAML` fix in `utils_nfcore_pipeline`
(general cloud-path robustness, not filter-specific), and breseq (AMP-v1 merger question).

## Getting it back

```bash
git show tier2-tools-last:subworkflows/local/vcf_filter_freebayes/main.nf          # read one file
git checkout tier2-tools-last -- subworkflows/local/vcf_filter_freebayes           # restore a tree
git diff tier2-tools-last -- workflows/sarek/main.nf                                # see the wiring that went
```
Browse on GitHub: `https://github.com/Aletechdev/ALE_Yeast/tree/tier2-tools-last/<path>`.
Restoring means re-wiring against whatever `workflows/sarek/main.nf` looks like then — the tag is a
reference, not a patch that applies cleanly after a sarek upgrade.

## The docs, as they were

- [`tier2_af_filters.md`](tier2_af_filters.md) — thresholds, the multi-allelic split, why Tier 2.
- [`FREEBAYES_FILTERING_PIPELINE.md`](FREEBAYES_FILTERING_PIPELINE.md) — the FreeBayes filter chain.
- [`controlfreec_germline_changes.md`](controlfreec_germline_changes.md) — the single-sample Control-FREEC mode.
