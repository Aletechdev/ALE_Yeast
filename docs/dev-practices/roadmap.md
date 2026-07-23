# ALE pipeline roadmap (post-v1.0.0 future work)

Ad-hoc future-work items migrated from the old `TODO.md` at v1.0.0. Priorities are `[high|med|low]`.
Full project history lives in `git log` and `CHANGELOG.md`; resolved items are summarized at the bottom.

> For the **test-coverage** roadmap (ploidy 1/2/3 scenarios, per-custom-module nf-tests), see WP6 in the
> release plan — not duplicated here.

---

## Variant calling — HaplotypeCaller

- **[low] Rename `SPLIT_JOINT_VCF` → `SPLIT_HAPLOTYPECALLER_JOINT_VCF`** (cosmetic). The subworkflow
  (`subworkflows/local/split_joint_vcf/`, workflow `SPLIT_JOINT_VCF`) is HaplotypeCaller-specific but
  named generically. A rename touches the dir, the workflow name, the imports in
  `bam_variant_calling_germline_all/main.nf`, and the schema doc — defer unless already editing the area.
- **[med] Joint-germline filter strategy + flag fixed / convergent mutations.** Refine the soft-filter
  thresholds on the joint HC VCF (`VARIANTFILTRATION_FALLBACK`, `conf/modules/joint_germline.config`) and
  add flags for *fixed* (≈100% AF) and *convergent* (recurrent across independent lineages) mutations —
  the key selective signals in an ALE experiment.

## Variant calling — Mutect2

- **[med] Rename filtered VCF → `filter_annotated`.** `conf/modules/mutect2.config:48` uses
  `ext.prefix = {"${meta.id}.mutect2.filtered"}`; rename to `…mutect2.filter_annotated` for consistency
  with HaplotypeCaller's `…_soft_filtered` (both are soft filters that annotate FILTER, not remove).
  Check downstream refs + docs after renaming.
- **[med] Yeast-tuned Mutect2 params.** With no germline resource (custom yeast genome), consider adding
  to `conf/modules/mutect2.config`: `--max-population-af 1.0` (allow any AF — important for evolution),
  `--af-of-alleles-not-in-resource 1/(ploidy·N)`, `--initial-tumor-lod 0.5–1.0` (catch low-freq early),
  `--downsampling-stride 1` (small genome). See the GATK Mutect2 docs. Investigation-heavy — validate on
  the benchmark set.
- **[low] More stringent Mutect2 filtering options.** Mutect2 yields ~30% more variants than FreeBayes;
  TLOD/AF-difference/depth thresholds could tighten. Deprioritized — the ALE strategy keeps more calls
  and ranks for fixed/convergent rather than hard-pruning.

## Variant calling — FreeBayes (Tier 2)

- **[med] Joint FreeBayes population calling.** Add a `--joint_freebayes` param + a
  `subworkflows/local/bam_joint_calling_freebayes/` (bcftools merge of individual germline VCFs), mirroring
  the HaplotypeCaller joint pattern in `bam_variant_calling_germline_all/main.nf`. Filter individuals
  first, then merge, so allele frequencies are population-correct.
- **[med] FreeBayes AF miscalculation for multi-allelic sites (real bug).** After `bcftools norm -m-`
  splits a multi-allelic record, `AO` is split per row but `RO` is not, so `AF = AO/(AO+RO)` uses a wrong
  denominator. Fix: compute `AF = sum(AO)/(sum(AO)+RO)` **before** splitting, then split. See
  `subworkflows/local/vcf_filter_freebayes/`.
- **[low] FreeBayes population table / single-VCF report.** Aggregate all samples' FreeBayes output into
  one population VCF/table for cross-sample comparison.

## CNV — Control-FREEC / CNVKit

- **[low] Control-FREEC yeast `cf_window` tuning.** `nextflow.config` sets `cf_window = null` (auto). Tune
  `window` / `breakpointthreshold` for small yeast chromosomes. Coupled with the ploidy=1 item below.
- **[low] Investigate ASSESS_SIGNIFICANCE skip for ploidy=1.** `conf/modules/controlfreec.config:19` skips
  it for haploid samples (Control-FREEC emits empty `*_CNVs`, R script fails). Determine whether this is
  inherent (no gain/loss relative to a haploid baseline) or a window/config issue that yeast-tuned
  parameters would resolve.

## Robustness / infrastructure

- **[med] Better exception handling in `samplesheet_to_channel`.** The bare
  `input_sample.filter{…}.ifEmpty{ error(…) }` at
  `subworkflows/local/samplesheet_to_channel/main.nf:146-166` surfaces a misleading "sample-sheet only
  contains normal-samples" error when the *real* cause is an upstream schema/config failure. Wrap with a
  contextual error (Option 3 in the diagnostic guide). **The debugging guide is preserved at
  [`troubleshooting.md`](troubleshooting.md).**
- **[low] Sample-table "starting strain" column.** Add a column naming the ancestral strain per sample;
  test that one ancestral name (e.g. `A0-F0-I1-R1`) can map to multiple samples across different
  experiments.
- **[low] Seqera launchpad schema polish.** Drop `cf_ploidy` from `params_seqera_test.yml` (schema default
  is 2 and it's ignored at runtime — ploidy comes from the sample table); set `"hidden": true` in
  `nextflow_schema.json` for `ascat_ploidy`, `ascat_purity`, `cf_window` (not used for yeast).
- **[low] SURVIVOR SV-merge input-sort guard.** `modules/local/survivor_sv_merge` and
  `survivor_cohort_merge` assume coordinate-sorted Manta/TIDDIT input but don't enforce it — the POSIX
  `sort` runs *after* `SURVIVOR merge`, so an unsorted input could silently produce a bad merge. Add a
  sort/validation before the merge. (Found in the SV-merge code audit.)

## Documentation

- **[low] Single-source the report Methodology + SV maintainer doc (option B).** The user-facing
  methodology lives in `docs/igvreports/templates/index.html.j2` (§ "SV event matrix"); the
  maintainer mechanics doc for the SURVIVOR internals is `docs/variant-calling/sv_merge.md`. The two
  are kept in **sync by hand** (a "keep in sync" note in each). Future: factor the methodology into a
  shared Jinja `{% include %}` partial so GENERATE_INDEX can render both the report section **and** a
  `mutation_reports/README.md` from one source.

## Deployment — Seqera launch UI / schema

**Policy (decided 2026-07-22): curate the surface, not the code.** Upstream sarek ships many tools
and ~141 params ALE doesn't use. Do **NOT** delete upstream calling paths or params to simplify —
that edits upstream files and creates a rebase patch that conflicts on every future sarek upgrade
(see `ale_sarek_upgrade_runbook.md`). Leave the code **inert** (a tool runs only if `--tools` names
it) and control what the user *sees* via `nextflow_schema.json` — which is exactly what the Seqera
launch form renders. Mark advanced/Tier-2 params `"hidden": true` (already done for 22/141 —
`institutional_config_options` + `generic_options`); hidden params still work (CLI / params-file /
"show hidden fields" toggle), they're just out of the default view. Ties to
[[prefer-isolated-config-over-shared]].

- **[v1.0.0 — before release] Add the 3 ALE params missing from the schema.** `generate_reports`,
  `report_container`, `report_gff3` are defined in `nextflow.config` but **absent** from
  `nextflow_schema.json`, so they don't appear in the Seqera launch form and can trip nf-schema
  validation. Add them to an appropriate group with sensible defaults; validate with
  `nf-core pipelines schema lint`. (Tracked as a WP4 pre-release step in the release plan.)
- **[med, post-1.0.0] Full launch-form curation.** `hidden: true` on the advanced/Tier-2 tool params
  (ascat_*, sentieon_*, mutect2/controlfreec extras, tumor-only knobs); set Tier-1 defaults
  (`--tools snpeff,cnvkit,tiddit,manta,haplotypecaller`, joint-germline + report flags on) so a user
  can launch with minimal edits; tidy `$defs` groups. Validate with a Seqera launch preview. **Keep
  `--tools` free-text (do NOT add an `enum`)** — an enum must be re-applied on every rebase and can
  reject valid upstream tool combos; default it to Tier-1 and document Tier-2 as advanced/unvalidated
  instead of hard-blocking it.

---

## Resolved (folded into v1.0.0)

One-liners for traceability; full detail in `git log` / `CHANGELOG.md`.

- **SPLIT_JOINT_VCF debug logging** → `log.debug` (commit `80a5a04`).
- **SPLIT_JOINT_VCF TBI emit** — emits `tbi`, consumer uses a proper channel join (dropped the
  `file("${vcf}.tbi")` workaround).
- **`hard_filter_/split_haplotypecaller_joint_vcf` param init** — both default `= false` in `nextflow.config`.
- **FilterMutectCalls channel join** without germline-resource/PoN (commit `8319ef9`).
- **Control-FREEC germline mode** — `bam_variant_calling_germline_controlfreec/` added + wired in (Apr 2026).
- **YAML `load()` ambiguity** — explicit `FileInputStream` in `utils_nfcore_pipeline`.
- **v0.1.0-alpha release prep** — tag + `README`/`CHANGELOG`/`LICENSE` present; superseded by the v1.0.0 CHANGELOG.
- **Variant Analysis Dashboard as a NF process** — *obsolete*: the `bin/` dashboard scripts were removed
  (commit `c06e7f4`); superseded by `subworkflows/local/mutation_report/` + `modules/local/generate_index/`.
- **`cram_variant_calling_status_normal` "smarter fix"** — *obsolete*: decision to keep the hard-coded
  all-samples-as-normal approach (confirmed optimal for ALE).
- **SV/CN caller ploidy support** — Tiddit (`-n ${meta.ploidy}`, `tiddit.config`), CNVKit (call+export),
  Control-FREEC; documented under `docs/variant-calling/{tiddit,cnvkit}/*_ploidy_behavior.md`. Manta has
  no ploidy CLI param (SV detection is ploidy-agnostic) — N/A, not a gap.
- **Population SV + CN cohort tables** — `build_sv_matrix`+`survivor_cohort_merge` →
  `sv_cohort_matrix_union{,_pass}.csv`; `build_cn_matrix`+`build_cn_cohort` → `cn_cohort_{full,collapsed}.csv`
  (MUTATION_REPORT deliverables). Feature done; dedicated docs = WP4 Step 6 (SV-merge guide) / Step 7b (CN).
- **CNVKit results in MultiQC** — documented in `docs/variant-calling/cnvkit/CNVKIT_MULTIQC_INTEGRATION.md`
  (resolved; slated for archive in the docs-consolidation step).
