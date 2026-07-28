# ALE pipeline roadmap (post-v1.0.0 future work)

Ad-hoc future-work items migrated from the old `TODO.md` at v1.0.0. Priorities are `[high|med|low]`.
Full project history lives in `git log` and `CHANGELOG.md`; resolved items are summarized at the bottom.

> For the **test-coverage** target (the four nf-test layers over our custom code, ploidy 1/2/3
> scenarios, per-custom-module tests), see `testing_best_practices.md` §11 — the target lives there
> and is not duplicated here. This file carries only the prioritized *scheduling* item for it
> (under Robustness / infrastructure).

---

## Variant calling — HaplotypeCaller

- **[low] Rename `SPLIT_JOINT_VCF` → `SPLIT_HAPLOTYPECALLER_JOINT_VCF`** (cosmetic). The subworkflow
  (`subworkflows/local/split_joint_vcf/`, workflow `SPLIT_JOINT_VCF`) is HaplotypeCaller-specific but
  named generically. A rename touches the dir, the workflow name, the imports in
  `bam_variant_calling_germline_all/main.nf`, and the schema doc — defer unless already editing the area.
- **[med] Joint-germline filter strategy + flag fixed / convergent mutations.** Refine the soft-filter
  thresholds on the joint HC VCF (`VARIANTFILTRATION_FALLBACK`, `conf/modules/joint_germline.config`) and
  add flags for *fixed* (≈100% AF) and *convergent* (recurrent across independent lineages) mutations —
  the key selective signals in an ALE experiment. Evidence now exists for the retune: on Ottilie Tier 2
  only **4 of the 9 declared filters ever fire** (MQ/SOR/QD/FS); the other five tag nothing. Handle
  `QUAL_filter` separately — it is redundant *by construction*, not by threshold (GenotypeGVCFs'
  default `-stand-call-conf 30` already removes everything it targets; observed min QUAL 30.14), so it
  should be dropped or re-tied to `stand-call-conf` rather than retuned. Per-filter counts and the
  RankSum annotation-coverage gap: `docs/variant-calling/haplotypecaller/SOFT_FILTER_HAPLOTYPECALLER_JOINT.md`.

## Variant calling — Mutect2 (Tier 2)

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

## CNV — Control-FREEC (Tier 2) / CNVKit

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
- **[med, post-1.0.0] Build out nf-test coverage over custom code (all four layers).** v1.0.0 ships two
  owned tests (`ottilie_e2e` pipeline + `split_joint_vcf` subworkflow); the 19 `modules/local/` and the
  other custom subworkflows have no isolated coverage, so a regression only surfaces as a diff in the e2e
  snapshot. Target, priorities and per-layer candidates are in `testing_best_practices.md` §11 — start
  with the VQSR-fallback pair (`VARIANTFILTRATION_FALLBACK` ext.args + the three-tier output selection in
  `bam_joint_calling_germline_gatk`), whose failure modes are silent and unreachable by the e2e snapshot;
  then the rest of the process layer, then subworkflow, then ploidy 1/2/3 pipeline scenarios (these want
  the CI item below to land first). Also decide the fixtures convention (committed-small vs. Azure Blob)
  before `tests/fixtures/` grows.
- **[low, post-1.0.0] Adopt incremental nf-test (`--changed-since`) in CI.** The `triggers` change-detection
  deps are already declared on `tests/nf-test-ottilie.config` (2026-07-24), so the ottilie suite re-runs
  when `nextflow.config` / `conf/test/ottilie_test.config` / `tests/.nftignore` / the ottilie configs change.
  Wiring `nf-test test --changed-since <ref>` into CI is deferred to the post-1.0.0 CI/cloud-portability work
  (WP3 "Level 2" — same bucket as the blob-URL `ottilie_test_ci` profile + GitHub Actions). Until then a plain
  full `nf-test test` is the gate and `triggers` is inert.

## Documentation

- **[low] Single-source the report Methodology + SV maintainer doc (option B).** The user-facing
  methodology lives in `docs/igvreports/templates/index.html.j2` (§ "SV event matrix"); the
  maintainer mechanics doc for the SURVIVOR internals is `docs/variant-calling/sv_merge.md`. The two
  are kept in **sync by hand** (a "keep in sync" note in each). Future: factor the methodology into a
  shared Jinja `{% include %}` partial so GENERATE_INDEX can render both the report section **and** a
  `mutation_reports/README.md` from one source.

### igvreports follow-ups (migrated from `docs/igvreports/README.md` TODO, 2026-07)

- **[low] (igvreports) Upgrade to igv-reports >= 1.15.0 for the Tabulator template.** The nf-core module
  ships v1.12.0, which lacks the `--tabulator` flag; v1.15.0+ adds a filterable/sortable Tabulator template
  (closest UX to BreSeq's mutation table). Override the module container to >= 1.15.0 (or a custom image),
  then add `--tabulator --filter-config filter_config.yaml` to `ext.args`. (Largely superseded by the custom
  templates in `generate_demo_reports.nf`; revisit only if reverting to the built-in template.)
- **[low] (igvreports) Add per-sample allele frequency.** HaplotypeCaller emits `FORMAT/AD` but not AF.
  Pre-process the VCF with `bcftools +fill-tags -- -t FORMAT/AF` (adds `AF = AD[alt]/(AD[ref]+AD[alt])`)
  before igvreports and expose it via `--sample-columns … AF`. Alternatives: SnpSift or dashboard-side compute.
- **[low] (igvreports) Review INFO columns for ALE relevance.** Current: `FILTER AC AF AN DP FS MQ QD SOR`.
  Consider adding `ExcessHet BaseQRankSum MQRankSum ReadPosRankSum` (QC), dropping `AN` (constant for joint
  calling) and `AC` (redundant with per-sample GT), and deciding INFO-level vs per-sample `AF`.
- **[low] (igvreports) Demo reports missing soft-filter INFO columns.** `generate_demo_reports.nf` uses
  `--info-columns ANN VCF_FILTER ORIG_ALT AC AF DP QD MQ`, but the joint-germline soft filter
  (`VARIANTFILTRATION_FALLBACK`, `conf/modules/joint_germline.config`) also evaluates `FS SOR MQRankSum
  ReadPosRankSum` — without these columns reviewers can't see *why* a variant was flagged. Add them to
  `--info-columns` in both `IGVREPORTS_COHORT`/`IGVREPORTS_SAMPLE` and to the filter config YAML.
- **[low] (igvreports) Review and deliver SV IGVReports.** A pilot SV report exists for the Marko benchmark
  (`docs/benchmarking/marko_sv/generate_igvreport.sh`): SNP/InDel from HaplotypeCaller + SV from the SURVIVOR
  union VCF. Review output, refine columns/flanking, and integrate SV IGVReports into the main pipeline.
- **[low] (igvreports) CRAM-track feasibility on D4as (16 GB).** Full-cohort CRAM embedding OOMs; to make
  with-CRAM runs viable, pre-filter to PASS-only (`bcftools view -f PASS`), limit to 2–3 key samples
  (ancestral + 1–2 evolved), and use `--subsample 0.5 --flanking 200`.

### igvreports dashboard follow-ups (migrated from the igvreports reporting plan, 2026-07)

- **[low] (igvreports reporting plan) Shared template extraction.** Factor shared CSS/JS (theme system,
  Tabulator config, badge definitions) out of the IGV dashboard and Marko SV report into a reusable partial
  (Jinja `{% include %}` or a standalone `dashboard_base.css`/`.js`). Only worthwhile if a third dashboard
  is planned.
- **[low] (igvreports reporting plan) CSV/VCF download links over `file://`.** The SV Ensemble table's
  download buttons only trigger a save dialog over HTTP; via `file://` a click opens the file in a new tab.
  Fix via a local HTTP server, JS Blob-based download, or accept current behavior for local use.
- **[low] (igvreports reporting plan) Benchmarking re-run.** Update the adipic-acid benchmarking scripts from
  the AF 90% → 80% threshold (see `docs/benchmarking/adipic_acid_ale/README.md` TODO).
- **[low] (igvreports reporting plan) `COUNT_VARIANTS` cleanup.** Remove the dead `COUNT_VARIANTS` process and
  the `--variant-counts-json` parameter from `generate_demo_reports.nf` (replaced by the MultiQC source).
- **[med] (igvreports reporting plan) Fix GENERATE_INDEX race condition.** In `generate_demo_reports.nf`,
  `GENERATE_INDEX` runs `generate_index.py` before the `samples/` symlinks exist, so the NF-generated index
  has null `igv_link` values (broken sample click-through). Currently worked around by a standalone
  `generate_index.py` call at the end of `generate_ottilie_reports.sh`. Fix: create symlinks before the
  Python call inside the process, or pass sample-report paths as explicit process inputs.

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

- **[v1.0.0 — before release] Mutation-report params: schema + defaults (rescoped 2026-07-23).** Only
  the 2 params a user actually sets get **schema** entries; the fixed-default machinery params are kept
  out of the UI via the **ignore list** (a config param absent from the schema still WARNs even with a
  default — so the ignore list, not omission, is what keeps it clean). Plan:
  - **SHOWN in schema:** `generate_reports` (in `variant_calling`, next to the other ALE toggles;
    default `true`); `report_gff3` (in `reference_genome_options`, next to `genbank` — per-genome
    annotation *file* for the report gene track; help_text notes the report purpose).
  - **`genbank` → flip `hidden: true`** — breseq-only (Tier-2), keep out of the Tier-1 form.
  - **`validation.defaultIgnoreParams` +=** `report_container`, `report_outdir`, `report_filter_config`,
    `report_cohort_template`, `report_sample_template`, `report_index_script`, `report_templates_dir`
    (out of UI, no WARN).
  - **`nextflow.config`:** `generate_reports` false→true; real `${projectDir}/docs/igvreports/…` defaults
    on the 5 static file params (read via `file(params.X)` with no null guard → would `file(null)`-break
    at `generate_reports=true`; assets git-tracked → resolve on Seqera); remove dead `report_multiqc_path`.
  - **`ottilie_test.config`:** remove `report_multiqc_path`; drop the 5 static overrides (now == defaults).
  - Validate with `nf-core pipelines schema lint` + e2e re-run. (Tracked as WP4 Step 2d in the release plan.)
- **[low, post-1.0.0] Fix the pre-existing `split_fastq` schema-lint error.** `nf-core pipelines schema
  lint` fails with *"Default parameters are invalid: 50000000 is valid under each of {'type':'integer'},
  {'type':'integer','minimum':250}"*. This is **upstream sarek 3.5.1 boilerplate** (confirmed identical on
  the pristine schema — not introduced by ALE): `split_fastq` carries both a top-level `"type":"integer"`
  and a `oneOf` (`{minimum:250}` / `{minimum:0,maximum:0}`), and the default `50000000` matches more than
  one, which nf-core's stricter lint rejects. **Lint-only — runtime nf-schema validation passes** (the
  pipeline runs fine), so it does not block v1.0.0. Fix = restructure the `split_fastq` schema (drop the
  redundant top-level type or re-model the "≥250 or exactly 0" constraint). Best done as part of a
  template/schema refresh (couples with the nf-core 4.x / sarek-4.x migration — see
  `ale_sarek_upgrade_runbook.md`), not a standalone patch.
- **[med, post-1.0.0] Full launch-form curation.** `hidden: true` on the advanced/Tier-2 tool params
  (ascat_*, sentieon_*, mutect2/controlfreec extras, tumor-only knobs); set Tier-1 defaults
  (`--tools snpeff,cnvkit,tiddit,manta,haplotypecaller`, joint-germline + report flags on) so a user
  can launch with minimal edits; tidy `$defs` groups. Validate with a Seqera launch preview. **Keep
  `--tools` free-text (do NOT add an `enum`)** — an enum must be re-applied on every rebase and can
  reject valid upstream tool combos; default it to Tier-1 and document Tier-2 as advanced/unvalidated
  instead of hard-blocking it.
- **[post-1.0.0] Cherry-pick `worktree-seqera-cloud` into `main`** once the Seqera cloud run is
  validated. Not a strict/clean merge — cherry-pick the cloud-specific changes as needed. The branch
  lives on `Aletechdev/ALE_Yeast`; don't merge before cloud validation (avoids pulling unvalidated
  cloud-path changes into `main`). Carried over from the now-removed pre-WP release plan's out-of-scope list.

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
- **CNVKit results in MultiQC** — documented in `docs/archive/cnvkit/CNVKIT_MULTIQC_INTEGRATION.md`
  (resolved; slated for archive in the docs-consolidation step).
