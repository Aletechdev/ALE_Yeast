# Testing Best Practices for Forked nf-core/Sarek Pipeline

## Overview

This document outlines a testing strategy for the ALE_nextflow fork of nf-core/Sarek 3.5.1 before releasing.

---

## 1. Tiered Testing Strategy

### Unit Tests (per-module)
- **nf-test**: The nf-core standard for module-level testing. Each module in `modules/nf-core/` can have a `tests/` directory with `main.nf.test` files.
- Test individual processes with minimal inputs (e.g., does `BCFTOOLS_FILTER` produce expected output format?)
- Use **nf-test snapshots** to catch regressions in output structure

### Integration Tests (subworkflow-level)
- Test custom subworkflows end-to-end: `vcf_filter_mutect2`, `vcf_filter_freebayes`, `split_joint_vcf`
- Verify channel wiring — especially custom joins (e.g., the FilterMutectCalls fix, channel-based metadata propagation)

### System/Pipeline Tests (full workflow)
- Run the full pipeline with a **small test dataset** (subset of yeast data)
- Validate all expected output files exist and are non-empty

---

## 2. Test Data

- **Minimal test profile**: Create a `test` profile in `nextflow.config` with:
  - Downsampled FASTQs (e.g., 10K–100K reads per sample)
  - Small reference (single chromosome or region)
  - Custom SnpEff cache
- **Deterministic inputs**: Pin exact test data versions (store on Azure Blob or use nf-core test-datasets pattern)
- Include edge cases: haploid samples, multi-lane samples, samples that trigger the VCFtools skip logic

---

## 3. What to Validate

| Layer | Check |
|-------|-------|
| **Process exit codes** | All processes exit 0 |
| **Output existence** | Expected VCFs, indices, CSVs all present |
| **VCF integrity** | `bcftools stats` on outputs, validate headers |
| **Variant counts** | Regression check — counts shouldn't wildly change between releases |
| **Filter logic** | Known variants pass/fail as expected (truth set) |
| **Metadata propagation** | Ploidy, status, sex survive through channels |
| **Conditional logic** | VCFtools skipped for Mutect2/ploidy>2, ASSESS_SIGNIFICANCE skipped for ploidy=1 |

---

## 4. CI/CD Approach

```bash
# Minimal CI test (GitHub Actions or Azure DevOps)
nextflow run main.nf \
  -profile test,docker \
  --outdir results_test \
  --tools 'haplotypecaller,freebayes,mutect2,snpeff' \
  --joint_germline \
  --split_haplotypecaller_joint_vcf \
  -resume
```

- Run on every PR to `main`
- Use `-resume` with cached work dirs for speed
- Fail on: non-zero exit, missing outputs, `bcftools view` errors on VCFs

---

## 5. nf-core Conventions to Follow

- **`nf-test`** (replaces pytest-workflow): install via `nf-core tools`
- **Linting**: `nf-core pipelines lint` — won't pass 100% on a fork but catches structural issues
- **`nextflow_schema.json`**: Validate custom params (`--split_haplotypecaller_joint_vcf`, ploidy column) are documented
- **`CHANGELOG.md`**: Track what diverges from upstream Sarek 3.5.1

---

## 6. Regression/Truth Set Testing

For ALE use case specifically:

1. **Create a truth set**: Run the pipeline on test data, manually review outputs, freeze as "known good"
2. **Compare on each release**:
   ```bash
   bcftools isec -p comparison/ truth_set.vcf.gz new_run.vcf.gz
   # Check for unexpected gains/losses
   ```
3. Track variant counts per sample/tool in a simple CSV — diff against previous release

---

## 7. Pre-Release Checklist

- [ ] All test profiles pass (`test`, `test_full` if available)
- [ ] `nf-core pipelines lint` has no critical errors
- [ ] Custom modules have nf-test coverage
- [ ] CHANGELOG documents all changes from upstream
- [ ] Docker/container images pinned to specific versions
- [ ] `nextflow_schema.json` updated for new params
- [ ] README documents fork-specific features and divergences
- [ ] Run full dataset at least once before tagging a release

---

## 8. Quick Start: Setting Up nf-test

```bash
# Install nf-test
conda install -c bioconda nf-test

# Initialize tests for a custom module
cd nf-core-sarek_3.5.1/3_5_1
nf-test init

# Generate test for custom filter module
nf-test generate process \
  modules/local/vcf_filter_mutect2/bcftools/filter_somatic/main.nf

# Run all tests
nf-test test
```

---

## 9. Priority Items for This Fork

The highest-value testing items are:

1. **Minimal test profile with yeast data** — catches configuration issues
2. **Regression variant counts** — ensures filter logic hasn't drifted
3. **nf-test on custom subworkflows** — filter logic, split joint VCF, channel joins

These cover the most likely breakage points when updating or refactoring.

---

## 10. Existing Test Infrastructure

See also:
- `bin/test_ottilie.sh` — ALE end-to-end test launcher (ottilie 2-sample dataset)
- `bin/CENPK_run_sarek_351_all.sh` — production execution script (reference for params)

### nf-test file categories (what we own vs. what stays untouched)

Three categories of `*.nf.test` files exist in the repo; only the first is ours to curate:

| Category | Location | Tests | Policy |
|----------|----------|-------|--------|
| **ALE suite (ours)** | `tests/*.nf.test` | the fork's own tests, at *any* nf-test layer — currently `ottilie_e2e` (`nextflow_pipeline`) and `split_joint_vcf` (`nextflow_workflow`) | **maintained.** All of ours live here regardless of layer — including component-level ones — see [Why our component tests live in `tests/`](#why-our-component-tests-live-in-tests-not-co-located) below |
| **Upstream pipeline-level** | `tests/*.nf.test` (inherited) | whole-pipeline scenarios on human test data | triaged out — see the next section |
| **Upstream component-level** | `modules/nf-core/*/tests/`, `subworkflows/*/tests/` | one module/subworkflow in isolation | **leave untouched** — co-located with upstream code; deleting them creates a rebase patch per upgrade, and they don't fail from our fork changes |

### Updating the snapshot after an intentional pipeline change

`tests/ottilie_e2e.nf.test.snap` (~790 lines of JSON) is the recorded expectation for the e2e run:
the published file tree (`stable_name`), content hashes for the files not excluded by
`tests/.nftignore` (`stable_path`), and the joint-VCF `variantsMD5`. Any change to pipeline output —
a new published file, a renamed directory, different variant records — makes the test fail by design.

**First, decide which kind of failure it is.** The snapshot cannot tell you; only you can:

| The diff shows | Meaning |
|---|---|
| Exactly the files/values your change should have touched | Intentional → re-record |
| Anything else moving too | **Stop.** A regression, or non-determinism the `.nftignore` doesn't cover |

Re-recording is the *last* step, never the first response to a red test.

```bash
# 1. See what moved (run normally; do NOT pass --update-snapshot yet)
NXF_VER=25.10.4 nf-test test -c tests/nf-test-ottilie.config tests/ottilie_e2e.nf.test

# 2. Only once every difference is explained, re-record
NXF_VER=25.10.4 nf-test test -c tests/nf-test-ottilie.config tests/ottilie_e2e.nf.test \
    --update-snapshot

# 3. Review the diff as source code, then commit test + snapshot together
git diff tests/ottilie_e2e.nf.test.snap
```

`--update-snapshot` re-records **every** snapshot that fails in that run, so a genuine regression
sitting alongside your intended change is silently blessed. Reviewing `git diff` on the `.snap` is the
only thing standing between you and a permanently wrong expectation. A worked example of a good diff:
the v1.0.0 `manifest.name` change moved exactly one line (`versions.yml`: `nf-core/sarek: v3.5.1` →
`Aletechdev/AMP: v1.0.0`) — see the status note in [`../../CLAUDE.md`](../../CLAUDE.md).

**Keep the engine pinned when re-recording.** The snapshot stores the toolchain that produced it:

```json
"meta": { "nf-test": "0.9.3", "nextflow": "25.10.4" }
```

Re-recording under a different Nextflow or nf-test bakes that into the committed expectation. Use the
same `NXF_VER=25.10.4` prefix as every other invocation ([`../usage/new_machine_setup.md`](../usage/new_machine_setup.md) § 7).

> `meta` is **provenance, not an assertion** — nf-test does not compare it, so running on a different
> engine than the one recorded does not by itself fail the test. Verified 2026-07-30: the suite passes
> on Nextflow 25.10.2 against this snapshot recorded on 25.10.4, so output is stable across the
> 25.10.x patch line. Don't "fix" a version mismatch here by re-recording — that discards the real
> expectation to sync a field nothing checks.

**Other flags worth knowing:**

- `--ci` — fails instead of auto-storing when a snapshot is *missing*. Use in CI so a deleted or
  absent snapshot can never silently pass as a freshly recorded one.
- `--wipe-snapshot` — drops obsolete entries (after renaming or deleting a test case).

> Output that changes run-to-run belongs in `tests/.nftignore`, not in a re-recorded snapshot. The
> file already excludes timestamped/non-deterministic artifacts (igv-reports HTML with its
> non-deterministic `sessionDictionary`, SnpEff summaries carrying a date stamp, samtools stats
> embedding the CRAM path). If a re-record keeps producing a fresh diff on an unchanged pipeline, the
> fix is an `.nftignore` pattern — each one there was verified with a controlled probe, per the
> comments in that file.

### Why our component tests live in `tests/`, not co-located

nf-core convention puts a component test next to its component
(`subworkflows/local/<name>/tests/main.nf.test`), and the upstream category above follows exactly
that. Our own component tests deliberately do **not**: `split_joint_vcf.nf.test` sits in `tests/`
even though it tests `subworkflows/local/split_joint_vcf/`. Reasons, strongest first:

1. **Test discovery is scoped to `tests/`.** `tests/nf-test-ottilie.config` sets `testsDir "tests"`,
   deliberately, so the ALE suite isn't polluted by the 99 upstream component tests (and their
   duplicates under `.claude/worktrees/`). A co-located test falls outside that scope and silently
   drops out of a bare `nf-test test -c tests/nf-test-ottilie.config` — it would still run if named
   explicitly on the command line (verified: paths outside `testsDir` are honoured), but it would no
   longer be part of the default gate. Restoring it costs either `testsDir "."` (which pulls in all
   the upstream tests) or a multi-path invocation that must be re-edited for every new test and
   threaded into CI.
2. **`tests/` is now the fork-owned suite.** With the inherited upstream pipeline tests triaged out,
   what remains is a coherent ALE unit sharing one config (`nf-test-ottilie.config`: profile,
   `resourceLimits`, plugins, `triggers`). Splitting it across two trees buys nothing at this size.
3. **Fixtures live there.** `tests/fixtures/` holds the committed joint VCFs (+ README) that
   `split_joint_vcf.nf.test` consumes. Co-locating the test would either separate it from its data
   or require moving the fixtures too.

**Counter-argument, for the record:** `subworkflows/local/split_joint_vcf/` is 100% ours and would
survive a future re-fork / sarek migration intact, whereas `tests/` receives upstream content again
and needs re-triage. Co-location would let the test travel with its code. That is a real benefit —
it is just outweighed today by (1).

> ⚠️ **Not a fixed decision.** `tests/` is an upstream directory too, so this is a judgement call
> about *this* fork at *this* size, not a principle. Revisit if any of these change: our component
> tests outgrow a handful of files; a re-fork makes `tests/` re-triage expensive enough to dominate;
> CI moves to `--changed-since`/`--related-tests` (where co-location gives better change detection);
> or we adopt a discovery setup that can scope to `tests/` *and* `*/local/**/tests/` at once. If it
> flips, move the fixtures with the tests and update `testsDir` in `tests/nf-test-ottilie.config`.

### Upstream pipeline-test triage — one-time cleanup (v1.0.0)

The `tests/` dir inherited 20 pristine upstream sarek pipeline-level tests, all 0-diff vs upstream
and **never adapted for this fork**. Each was written against a scenario/toolset ALE does not run:

- **Cancer / paired modes** we don't use — `tumor-normal-pair` (needs a tumor sample; the fork's
  all-normal mode breaks it), `variant_calling_strelka`/`_bp`, `variant_calling_controlfreec`.
- **Aligners / tools we don't use** — `sentieon`, `aligner-dragmap` (we run bwa-mem), the VEP/bcfann
  annotation variants (`annotation_vep`, `annotation_bcfann`, `annotation_merge`).
- **Steps / output modes we don't use** — `save_output_as_bam`, `saved_mapped`, and the restart-entry
  tests `start_from_markduplicates` / `start_from_preparerecalibration` / `start_from_recalibration`,
  plus `alignment_from_everything` / `alignment_to_fastq`.
- **Generic upstream defaults** on human test data — `default`, `aligner-bwa-mem`(`2`),
  `annotation_snpeff`.

They all target human test data and fork-incompatible assumptions, so most fail/error → negative
value. Everything reusable in them (the `stable_name` / `stable_path` / `.nftignore` snapshot idiom)
was already copied into `ottilie_e2e.nf.test`. They are deleted (with their orphaned `.snap`) as a
**one-time cleanup**, keeping only our ALE contract tests.

**`ottilie_e2e.nf.test` is the end-to-end case for the v1.0.0 release** (the full ALE workflow on the
ottilie 2-sample dataset via the `ottilie_test` profile); `split_joint_vcf.nf.test` is the one
subworkflow unit test. Those two are what we maintain.

**Legacy pytest-workflow stack removed in the same triage.** The `tests/` dir also inherited the
upstream **pytest-workflow** apparatus — nf-core's *older* test framework (`- name:` / `command:` /
`files: md5sum:`, run by `pytest --tag`), which **nf-test superseded**. It is a set of interlocking
files, all removed together:

| File(s) | Role |
|---------|------|
| `tests/test_*.yml` (29) | the test definitions |
| `tests/tags.yml` | tag → source-file globs |
| `tests/config/pytesttags.yml` | tag → test-file map (CI change filter) |
| `tests/requirements.txt` | Python deps (`pytest-workflow`, `cryptography`) |

Three independent reasons this is correct, not a divergence:

1. **The runner never came with the fork.** The harness that runs these — upstream's
   `.github/workflows/pytest.yml` (`pip install -r tests/requirements.txt` → `pytest --tag …`, using
   `tests/config/pytesttags.yml` + `tests/csv/`) — **does not exist in our `.github/workflows/`** (we
   have only the container build). So these YAMLs were inert scaffolding here with nothing to run them.
2. **Deprecated framework, zero reuse value** — unlike the `.nf.test` files (whose idioms we copied
   into `ottilie_e2e`), we'd never author a pytest-workflow test. They're also unrelated to the
   `.nf.test` files (no cross-reference) and cover inapplicable upstream scenarios (sentieon,
   deepvariant, mutect2, umi, msisensorpro, lofreq, …) on human data.
3. **Upstream is retiring them too.** The sarek CHANGELOG documents a systematic pytest→nf-test
   migration — PRs **1677** (aligner/default), **1708** (alignment/annotation), **1711** (strelka),
   **1731** (controlfreec) all *"Migrate pipeline pytest … tests to nf-test"* — and **3.8.1 ships just
   1** pytest YAML (vs 3.5.1's 29) alongside 62 `.nf.test`. Deleting them **tracks** where upstream is
   heading, so the "0-diff, redone on migration" caveat barely applies (the version we rebase onto will
   have removed them).

**Kept — not pytest-only:** `tests/csv/` and `tests/config/bcfann_test_header.txt` stay, because the
still-present, 0-diff `conf/test.config` (+ 18 upstream extra-CI profiles) reference them for the
**nf-test** default path too — they are not pytest scaffolding, and removing them would break that
pristine upstream config. (Our own bcftools-norm investigation under `tests/test/` was archived to
`docs/archive/test_bcftools/`.)

> ⚠️ **This is not a permanent state.** A future full re-fork / sarek migration copies clean upstream
> back, so the same triage must be redone then. The planned migration would obsolete these tests
> anyway, so we do **not** invest in adapting them — the minimal ALE suite (ottilie e2e +
> split_joint_vcf) is what survives a migration. The 93 module + 6 subworkflow component tests are
> **not** part of this triage (see the table above).

---

## 11. Target coverage: the four nf-test layers (post-1.0.0)

v1.0.0 ships two owned tests — `ottilie_e2e` (`nextflow_pipeline`) and `split_joint_vcf`
(`nextflow_workflow`). The long-term target is coverage of **our own modifications** at all four
nf-test layers. This section is the durable target; the *scheduling* of it lives as a single
prioritized item in `roadmap.md` (Robustness / infrastructure).

nf-test's four test types, and what each maps to in this fork:

| Layer | nf-test type | Our surface | Status |
|-------|--------------|-------------|--------|
| Function | `nextflow_function` | Groovy helpers we changed | **0 owned** |
| Process | `nextflow_process` | the 19 `modules/local/` | **0 owned** |
| Subworkflow | `nextflow_workflow` | the custom `subworkflows/local/` | **1** (`split_joint_vcf`) |
| Pipeline | `nextflow_pipeline` | supported end-to-end routes | **1** (`ottilie_e2e`) |

The 99 upstream component tests do **not** count as coverage here — they test unmodified nf-core
code (see the category table in §10). Only tests over fork-specific code do.

### Priority theme: the "no known-variants resource" modifications

The custom yeast genome has no curated known-sites VCF (no dbSNP/gnomAD equivalent), so several GATK
best-practice steps that *assume* one had to be reworked. This is the fork's most consequential
divergence from upstream and its least-covered code:

| Step | What we did | Where |
|------|-------------|-------|
| **VQSR** (joint germline) | added `VARIANTFILTRATION_FALLBACK` — a hard-filter step that soft-flags the FILTER column when VQSR can't run, plus three-tier output selection | `subworkflows/local/bam_joint_calling_germline_gatk/main.nf`, `conf/modules/joint_germline.config:87` |
| **BaseRecalibrator** | *skipped*, not replaced — `skip_tools = 'baserecalibrator'`. Not auto-skipped: drop the flag and the run **aborts** — not from GATK (it never launches; its known-sites channel is empty) but from `failOnMismatch` on the `ch_table_bqsr` join at `workflows/sarek/main.nf:567` | `conf/test/ottilie_test.config:41` and the run scripts |
| **CNNScoreVariants / FilterVariantTranches** | nothing — structurally bypassed, it's in the `else` of `if (joint_germline)` and we run joint | `bam_variant_calling_germline_all/main.nf:232` |
| **Mutect2** | `--germline-resource` / `--panel-of-normals` omitted; `FilterMutectCalls` fed placeholder contamination channels | `bam_variant_calling_somatic_mutect2/main.nf` |

Note the asymmetry: BQSR is a **config-level skip** (nothing to unit-test beyond "the skip takes
effect"), whereas the VQSR fallback is **real added logic** and is the highest-value test target in
the repo. It gets specific entries at layers 2 and 3 below.

### Layer 1 — `nextflow_function`

Deliberately the smallest layer: nearly all our logic lives in bash/Python *inside* processes, not
in Groovy. The one genuine candidate is **`processVersionsFromYAML`**
(`subworkflows/nf-core/utils_nfcore_pipeline/main.nf:95`) — we rewrote it (explicit
`FileInputStream` + null/empty guards) to fix the method-resolution ambiguity that broke the custom
VCF filters, and the co-located upstream `tests/main.function.nf.test` has **no case for it**. Since
that file is upstream-co-located, adding a case there conflicts with the "leave untouched" policy —
prefer a case in our own `tests/` file (see §10 rationale).

> Not this layer: the Python in `bin/` (`build_cn_matrix.py`, `cn_cohort_matrix.py`,
> `generate_index.py`, the dashboard scripts). Those need **pytest**, not nf-test — a separate track,
> and arguably the higher-value one given how much report logic sits there.

### Layer 2 — `nextflow_process` (biggest gap)

All 19 `modules/local/` are untested in isolation, as is the one upstream module whose *behaviour we
own via config* (`VARIANTFILTRATION_FALLBACK`). Today they're only exercised transitively through the
e2e snapshot, which tells you *that* something changed, not *what* broke. Priority order by logic
density:

1. **`VARIANTFILTRATION_FALLBACK`** — highest value in the repo, because its failure mode is
   **silent**. `conf/modules/joint_germline.config:92` records that JEXL `TYPE==SNP` / `TYPE==INDEL`
   *matches nothing* rather than erroring (hence `vc.isSNP()` / `vc.isIndel()`); a regression back to
   the intuitive syntax produces a well-formed VCF with every record marked `PASS` and no visible
   failure anywhere in the run. The e2e snapshot can't catch it either — the VCFs are `.nftignore`-
   excluded as non-deterministic. A process test pins it directly: feed a fixture with SNP and INDEL
   records straddling each threshold, assert the exact FILTER strings per record, assert the SNP-only
   filters never fire on INDELs (and vice versa), and assert the record count is **unchanged** (this
   is a soft filter — flags, never removes). The contract in one line: **without this step every
   record's FILTER is `.`**, so `bcftools view -f PASS` returns zero and the downstream hard filter
   has nothing to act on — see `docs/variant-calling/haplotypecaller/SOFT_FILTER_HAPLOTYPECALLER_JOINT.md`.
   Cheap and fully deterministic.
   *Caveat:* the module itself is stock nf-core — **our** logic is the `ext.args` JEXL, so the test
   only means anything if the config selector resolves in unit isolation. Same trap
   `split_joint_vcf.nf.test` hit (it needed the `.*SPLIT_JOINT_VCF:…` selector, no leading colon);
   `VARIANTFILTRATION_FALLBACK` uses a bare `withName:` so it should already apply — verify first.
2. **Matrix/cohort builders** — `build_cn_matrix`, `build_cn_cohort`, `build_sv_matrix`. Real
   transformation logic with known edge cases (the Jensen's-inequality collapse bug, `fold_change`
   re-derivation). Pure table-in/table-out — cheap, deterministic fixtures.
3. **SV merge** — `survivor_sv_merge`, `survivor_cohort_merge` (incl. the input-sort guard already
   on the roadmap).
4. **VCF manipulation** — `filter_pass_vcf`, `add_info_to_vcf`, `prepare_vcf`. Small fixtures,
   assertable record counts — same idiom as `split_joint_vcf.nf.test`.
5. **Report/format** — `generate_index`, `igvreports_*`, `cnr_to_bedgraph`, `prepare_gff3`. Watch
   determinism: igv-report HTML varies run-to-run; assert the `tableJson` blob, not the file hash.

### Layer 3 — `nextflow_workflow`

Channel wiring and metadata propagation — where this fork's real risk lives.

**First: `bam_joint_calling_germline_gatk` — the three-tier output selection.** The subworkflow picks
`recal_vcf ?: fallback_vcf ?: joint_vcf` (VQSR > filter-annotated > unfiltered) via two chained joins
on remapped keys. Two reasons it needs a test:

- **Only one branch is ever exercised.** No `known_snps_vqsr` / `known_indels_vqsr` / `dbsnp_vqsr` is
  set anywhere in our configs, so VQSR never runs and the fallback branch is always taken. The
  VQSR-wins branch is effectively dead code in ALE — untested, and it would only ever activate on the
  day someone supplies known sites, i.e. the worst moment to discover it's broken.
- **The joins are asymmetric.** The VQSR join uses `remainder: true`; the fallback join does not. That
  is correct *today* only because `VARIANTFILTRATION_FALLBACK` is unconditional — give it an
  `ext.when` and `genotype_vcf` goes silently empty rather than failing. Worth pinning as a contract.

A workflow test covers both by feeding the three inputs directly and asserting which VCF comes out —
no GATK run needed for the selection logic itself.

**Then**, all `subworkflows/local/`: `vcf_filter_mutect2`, `vcf_filter_freebayes`,
`vcf_filter_haplotypecaller_joint`, `mutation_report` (tool-presence branching on `params.tools`),
`fastq_variant_calling_breseq` (the `subMap` regrouping), `bam_variant_calling_germline_controlfreec`,
`prepare_reference_cnvkit`. Assert what §3 calls out: ploidy/status/sex surviving the joins, and the
conditional skips (VCFtools for Mutect2/ploidy>2, `ASSESS_SIGNIFICANCE` for ploidy=1) actually firing.

### Layer 4 — `nextflow_pipeline`

`ottilie_e2e` covers one route (haploid, joint germline, snpeff/cnvkit/tiddit/manta). The gap is
**scenario** coverage, not more assertions: **ploidy 1 / 2 / 3** variants (each hits different
conditional logic) and any additional supported route we commit to. Cost is wall-clock, so these
want the CI/`--changed-since` work to land first.

### Sequencing

Start with the VQSR-fallback pair — the `VARIANTFILTRATION_FALLBACK` process test *and* the
`bam_joint_calling_germline_gatk` selection test. They're two halves of one modification, both have
silent failure modes, and neither is reachable by the e2e snapshot. Then the rest of layer 2 (largest
gap, cheapest fixtures, fastest feedback), then 3, then the ploidy scenarios at layer 4; layer 1 is
opportunistic. Prerequisite for all of it: a fixtures convention beyond the
current hand-committed `tests/fixtures/` — decide committed-small vs. Azure Blob before the file
count grows.

---

## TODO

- [ ] Create downsampled test FASTQs and upload to Azure Blob
- [ ] Build out nf-test layers 1–4 over custom code — target and priorities in §11
- [ ] Create `test` profile in nextflow.config
- [ ] Establish truth set from current validated run
- [ ] Set up CI (GitHub Actions or Azure DevOps)
- [ ] Document fork divergences in CHANGELOG.md
