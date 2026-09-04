# ALE Yeast pipeline: change log

## Unreleased

### Repository

- **Git history rewritten (2026-08-31)** with `git filter-repo` to purge private experiment data
  before open-sourcing. Every commit SHA changed; SHAs recorded before this date refer to the
  pre-rewrite history. Purge list + full old→new commit map:
  `docs/dev-practices/history_rewrite_2026-08.md`.

### Added

- **Read preprocessing organised as four steps** (schema group "Read preprocessing", user page
  `docs/usage/read_preprocessing.md`): step 0 UMI consensus (hidden) → fastp step 1 adapter trimming
  `trim_adapter` (+ `adapter_sequence`, `adapter_sequence_r2` for kits fastp cannot infer;
  `trim_fastq` kept as a deprecated alias) → step 2 quality trimming per read end
  `trim_quality_3prime` (`tail` | `right`) / `trim_quality_5prime` with shared `trim_quality_mean` (20)
  and `trim_quality_window` (4) — a variable number of bases by quality, Trimmomatic
  `TRAILING`/`SLIDINGWINDOW`/`LEADING` analogues → step 3 read filtering `filter_quality` (on, as
  upstream) with visible thresholds `filter_quality_phred` (15) / `filter_quality_percent` (40) and
  `length_required`. Parameter descriptions carry their step; UMI and split-publish params are hidden.
  The FASTP gate also fires on the quality-trimming params. Recommended ALE recipe
  `--trim_adapter --trim_quality_3prime tail` (not the default). Design + measurements:
  `docs/dev-practices/fastq_preprocessing_audit.md` §2. Module test: `tests/fastp_preprocessing.nf.test`.

- **TIDDIT soft filters for the SV pass view** (`TIDDIT_SV_FILTER`): three Manta-inspired named
  vetoes — `LowSupport` (<6 pairs+splits), `LowQual` (TIDDIT QUAL <40), `HighMQ0` (>40% low-MAPQ
  reads at a breakend) — appended softly to the per-sample SV-merge input. The pass matrix/VCF
  excludes them; the union view keeps every record with its reason; published caller VCFs are
  untouched. Calibrated on the no-SV pilot truth set (56/86 TIDDIT-only pass rows removed, 0
  Manta-corroborated rows affected); thresholds are config (`conf/modules/mutation_report.config`).
  The matrix now also folds TIDDIT's `DUP:INV` (like `DUP:TANDEM`) into `DUP`.
- SVDB SV merge chain: Manta `convertInversion` →
  breakend-pair collapse (both callers) → `svdb --merge` across samples (TIDDIT; and Manta when not
  joint) → `svdb --merge --priority manta,tiddit` across callers, in `union` and `union_pass`
  (input-pre-filtered) views. Cohort VCFs publish at the canonical
  `data/sv_cohort_merged_{union,union_pass}.vcf.gz` names; intermediates under
  `data/sv_merge_inputs/`. Recipe validated in `docs/benchmarking/ottilie_xenobiotic_ale/04_validate/sv_merge_bench/`.
  New local modules `COLLAPSE_SV_PAIRS` and `CHECK_SV_SAMPLE_ORDER` (sample-column guard for
  `--same_order`); nf-core `manta/convertinversion` installed; `svdb/merge` updated (2.8.2 → 2.8.4,
  versions now emitted via topic channels only).
- **`--joint_manta`** — Manta germline calling in joint (multi-sample) mode: one run per patient
  (= ALE `experiment`) over all of its samples, so every sample is genotyped at every candidate SV
  instead of an event with weak evidence being absent from that sample's VCF. Default `false`
  (per-sample runs, unchanged output). Output: `variant_calling/manta/{patient}/{patient}.manta.diploid_sv.vcf.gz`.
  Written in the shape of upstream `--joint_mutect2` (grouping inside the subworkflow, `manta.config`
  untouched) so it can be offered to nf-core/sarek.
- **`--manta_high_sensitivity`** (default `false`) — one switch that turns off Manta's two human-WGS
  repeat heuristics: the depth filters (`--exome`, Manta's only handle for them; not a data-type
  change, `--wes` stays false) and the breakend-hub edge cap (`graphNodeMaxEdgeCount = 0` via
  `assets/manta_high_sensitivity.ini`, passed through the module's `config` input). Applies to every
  Manta run, per-sample or joint. Off, Manta behaves exactly as before. On the 4-sample pilot (joint
  mode) it reports 58 records instead of 31: the engineered-cassette junctions, a shared 343-bp
  delta-LTR insertion and 16 former `MaxDepth` records become PASS; no truth-set change either way.
- **Per-sample split of the joint Manta VCF** (ALE-only, on by default in the ottilie profiles):
  `SPLIT_JOINT_VCF` now also handles Manta — each sample gets back
  `variant_calling/manta/{sample}/{sample}.manta.diploid_sv.vcf.gz` so annotation, IGV reports and
  the SV merge are unchanged, with hom-ref/missing rows dropped (`--min-ac 1:nref`, ploidy-agnostic)
  and Manta's per-sample `FORMAT/FT` promoted to `FILTER` (`MinGQ`), so a weak genotype is not read
  as PASS because the cohort-level record is. Split rules for all callers now live in
  `conf/modules/split_joint_vcf.config`, keyed on `meta.variantcaller`.

### Changed

- **`trim_nextseq` documented correctly.** Its description claimed Trim Galore's `--nextseq=X`
  quality-cutoff semantics; fastp's flag takes no value and only its non-zero-ness is used. At 0
  nothing is passed and fastp's read-name poly-G auto-detection applies, unchanged from upstream.
  `--trim_adapter` (= upstream's `--trim_fastq`) behaves as in upstream sarek 3.5.1 (adapter trimming
  plus fastp's read-level quality filter); the filter is now documented and switchable via
  `filter_quality` (default true), and its thresholds are passed explicitly.

- **`joint_manta` now defaults to `true`** (was `false`): joint multi-sample Manta is the validated
  Tier-1 recipe — the local test/pilot configs already ran it, while a Seqera launch inherited the
  old `false` default (the Launchpad preset never set it), so the two execution paths silently ran
  different Manta modes. Local ottilie runs are unchanged (their profiles pinned `true` already);
  set `--joint_manta false` for per-sample Manta on large cohorts (joint mode is one task per
  experiment whose cost grows with every sample; validated at 4).

- **Seqera launch form trimmed to the Tier-1 surface** (Tier-1 UX review, 2026-09-01): the schema
  now marks all but 26 parameters `hidden` (Seqera's "Show hidden params" toggle and `--help_full`
  still reach them; behavior, defaults and validation are unchanged). Visibility is generated from a
  new allowlist overlay — `conf/schema_overlay.yml` applied by `bin/apply_schema_overlay.py`
  (`--check` guards drift; parameters added by a future sarek upgrade are born hidden). The `tools`
  and `joint_manta` help texts are rewritten for the ALE germline-only reality. The ottilie
  profiles, blob params file and pilot/tier2 launchers stop passing `chr_dir` (Control-FREEC-only)
  and `genbank` (breseq-only) — both staged-but-unused on Tier-1 runs; the params remain available,
  hidden. Resolved-config proof: only those two values change, `-preview` DAG unaffected.

- **SURVIVOR retired**: `SURVIVOR_SV_MERGE`, `SURVIVOR_COHORT_MERGE` and the per-sample
  `data/sv_merged/<sample>/` outputs are gone. `data/sv_cohort_merged_{union,union_pass}.vcf.gz`
  keep their names but are now the SVDB cross-caller merges (provenance in `INFO/set`, `FOUNDBY`,
  `manta_*`/`tiddit_*` keys). The SV cohort matrix is a deterministic parse of those VCFs —
  `proximity_match` and its 1 kb gate are gone; rows carry Manta's split-read coordinates, one row
  per breakend junction, typed `<INV>` rows.
- Matrix/CN cohort CSVs now end lines with LF (were CRLF via the csv module default).
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
  files from `params.outdir`. Now correct-by-construction on a fresh outdir (cloud/Seqera). (`bb1439f`)
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
