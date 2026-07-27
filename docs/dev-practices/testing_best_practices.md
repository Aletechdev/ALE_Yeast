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

Two categories of `*.nf.test` files exist in the repo; only the first is ours to curate:

| Category | Location | Tests | Policy |
|----------|----------|-------|--------|
| **Pipeline-level** | `tests/*.nf.test` | whole-pipeline scenarios | our ALE tests (`ottilie_e2e`, `split_joint_vcf`) are maintained; inapplicable upstream ones are triaged out |
| **Component-level** | `modules/nf-core/*/tests/`, `subworkflows/*/tests/` | one module/subworkflow in isolation | **leave untouched** — co-located with upstream code; deleting them creates a rebase patch per upgrade, and they don't fail from our fork changes |

### Upstream pipeline-test triage — one-time cleanup (WP4 Step 3b)

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

## TODO

- [ ] Create downsampled test FASTQs and upload to Azure Blob
- [ ] Write nf-test cases for `vcf_filter_mutect2`, `vcf_filter_freebayes`, `split_joint_vcf`
- [ ] Create `test` profile in nextflow.config
- [ ] Establish truth set from current validated run
- [ ] Set up CI (GitHub Actions or Azure DevOps)
- [ ] Document fork divergences in CHANGELOG.md
