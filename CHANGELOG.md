# ALE Yeast pipeline: change log

## Unreleased

### Added

- **`--joint_manta`** — Manta germline calling in joint (multi-sample) mode: one run per patient
  (= ALE `experiment`) over all of its samples, so every sample is genotyped at every candidate SV
  instead of an event with weak evidence being absent from that sample's VCF. Default `false`
  (per-sample runs, unchanged output). Output: `variant_calling/manta/{patient}/{patient}.manta.diploid_sv.vcf.gz`.
  Written in the shape of upstream `--joint_mutect2` (grouping inside the subworkflow, `manta.config`
  untouched) so it can be offered to nf-core/sarek.
- **Per-sample split of the joint Manta VCF** (ALE-only, on by default in the ottilie profiles):
  `SPLIT_JOINT_VCF` now also handles Manta — each sample gets back
  `variant_calling/manta/{sample}/{sample}.manta.diploid_sv.vcf.gz` so annotation, IGV reports and
  the SV merge are unchanged, with hom-ref/missing rows dropped (`--min-ac 1:nref`, ploidy-agnostic)
  and Manta's per-sample `FORMAT/FT` promoted to `FILTER` (`MinGQ`), so a weak genotype is not read
  as PASS because the cohort-level record is. Split rules for all callers now live in
  `conf/modules/split_joint_vcf.config`, keyed on `meta.variantcaller`.

### Changed

- Shared SV events no longer read as clone-specific in the Manta outputs of a multi-sample
  experiment: with joint calling every sample carries a genotype at every candidate (in the
  2-sample test set, `I:206105 DEL` and `VII:530034 INS` become shared PASS calls; breakpoints are
  estimated once from pooled reads, so coordinates shift slightly vs per-sample runs).

### Fixed

- **Joint Manta output was not deterministic.** The grouped CRAM list came out of `groupTuple()` in
  channel-arrival order, and Manta derives its record IDs (and the joint VCF's sample-column order)
  from `--bam` order, so IDs, `MATEID`s and column order could differ between identical runs — visible
  downstream as changing IGV-report hashes. The CRAMs are now sorted by name before the joint call.

### Known limitations

- **Manta at its default settings (the ALE default) drops high-depth junctions and hub-adjacent
  events.** On the 4-sample pilot the joint run loses the `MaxDepth`-tagged engineered-cassette
  breakends (Manta's pooled-depth discovery skip) and a shared 343-bp delta-LTR insertion (the
  breakend-hub edge cap); per-sample calling has the same blind spot in the parent strain. Decided
  2026-08-28 to keep Manta's defaults — joint calling's noise reduction is wanted, and at the PASS
  level only one shared background insertion, one cassette junction and two 8-pair breakends are
  affected — and to expose the alternative as `--manta_high_sensitivity`. Audit, per-record effect
  and how to re-run it: `docs/benchmarking/ottilie_xenobiotic_ale/04_validate/pilot_results_v2/NOTES.md`,
  `04_validate/run_manta_joint_audit_pilot.sh <MODE>`.

## v1.0.0 — first production release (on nf-core/sarek 3.5.1)

Yeast ALE (Adaptive Laboratory Evolution) variant-calling pipeline: HaplotypeCaller joint germline
calling with variable ploidy, structural/copy-number calling, custom SnpEff annotation, and an
integrated multi-caller mutation-report dashboard. Full change inventory vs. upstream sarek:
[`docs/dev-practices/SAREK_MODIFICATIONS.md`](docs/dev-practices/SAREK_MODIFICATIONS.md).

### Tool support tiers

- **Tier 1 (tested — exercised by the ALE contract test):** HaplotypeCaller (joint + split +
  hard-filter), CNVKit, Manta, TIDDIT, SnpEff.
- **Tier 2 (functional, not release-tested):** Control-FREEC, breseq, and the FreeBayes/Mutect2
  AF-filter subworkflows (retained for dev/troubleshooting; not on the Tier-1 path).

### Added

- **MUTATION_REPORT dashboard** — per-sample + cohort igv-reports, CN cohort matrices (CNVKit),
  SV cohort matrices (SURVIVOR merge of Manta+TIDDIT), and an index.html linking MultiQC.
  Opt-in via `--generate_reports`.
- **ALE end-to-end nf-test** (`tests/ottilie_e2e.nf.test`) — pipeline-level contract test on the
  2-sample ottilie dataset; asserts the 4 cohort CSVs byte-for-byte + output structure + versions.
  Determinism proven across runs. Kept separate from the upstream sarek suite.
- **Split + hard-filter of joint HC VCFs** (`--split_haplotypecaller_joint_vcf`,
  `--hard_filter_haplotypecaller_joint`); `VARIANTFILTRATION_FALLBACK` when VQSR can't run.
- Variable-ploidy support threaded to HaplotypeCaller, CNVKit, Control-FREEC, FreeBayes, TIDDIT.
- Portable test-data provenance + samplesheet generation; container images pinned for cloud.

### Changed

- **MUTATION_REPORT is now channel-based and runs inline** in `workflows/sarek/main.nf` — consumes
  live pipeline output channels instead of re-reading `params.outdir`.
- BUILD_SV_COHORT split into single-container processes for cloud portability.
- Dead code / stale artifacts removed for release.

### Fixed

- **`--generate_reports` failed on a clean run** — the report raced `publishDir` reading published
  files from `params.outdir`. Now correct-by-construction on a fresh outdir (cloud/Seqera). (`246dd7b`)
- Per-sample SV/CNV reports were dropped by a one-to-one channel `join`; fixed with `combine(by:0)`.
- FilterMutectCalls now runs without a germline resource / panel-of-normals (placeholder channels).

### Known limitations

- **Nextflow:** run on **25.10.x** (manifest range `!>=24.04.2, <26.0.0`; launch scripts pin
  `NXF_VER=25.10.4`). **26.04+ fails to parse `nextflow.config`** (strict config DSL — starting with
  `def trace_timestamp` mixed with config statements) — a 26.x move is an nf-core template migration
  deferred to a post-1.0 sarek-4.x rebase. Full blocker inventory + Seqera notes in
  `docs/dev-practices/ale_sarek_upgrade_runbook.md`.
- **CNVKit CN scale:** `cn` is always diploid-baseline regardless of `--ploidy`; use `log2`/depth
  ratio (`fold_change`) for true signal on haploid/polyploid strains. See `docs/variant-calling/cnvkit/`.
- **VCFtools** conditionally skipped for ploidy>2, Mutect2 phased GT, and joint-calling VCFs.
- **Custom genomes:** no dbSNP / known-sites → BQSR and VQSR disabled (hard-filter fallback);
  Mutect2 runs without germline-resource / panel-of-normals; Control-FREEC has no BAF.

### Testing

- ALE contract test (nf-test) gates the deliverables; Tier-2 biological validation against the
  ottilie truth set (4 SNVs + chr I duplication, Ottilie et al. 2022) validates call correctness.

## v0.1.0-alpha:

Adapted from nf-core sarek 3-5-1, the main feature is HaplotypeCaller joint variant calling
