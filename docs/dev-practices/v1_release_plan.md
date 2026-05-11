# v1.0.0 Release Plan — ALE Sarek 3.5.1

**Goal**: Ship a working, documented pipeline that runs identically on local Nextflow and Seqera Cloud Launchpad.

**Base**: Forked nf-core/sarek 3.5.1 with ALE customizations already in place.

---

## Task 1: Update `nextflow_schema.json` defaults for ALE

Change schema defaults so Seqera Launchpad pre-fills ALE-correct values instead of human-genomics defaults. Local runs are unaffected (schema only controls validation and UI).

| Parameter | Current default | ALE default | Reason |
|---|---|---|---|
| `genome` | `GATK.GRCh38` | `null` | Custom yeast reference, not iGenomes |
| `igenomes_ignore` | `false` | `true` | No iGenomes lookup |
| `split_fastq` | `50000000` | `0` | No FASTQ splitting for yeast |
| `joint_germline` | `false` | `true` | Standard for ALE experiments |
| `hard_filter_haplotypecaller_joint` | `false` | `true` | VQSR unavailable without known-sites |
| `split_haplotypecaller_joint_vcf` | `false` | `true` | Per-sample VCFs from joint calling |

Additionally, mark irrelevant params as `"hidden": true`:
- `ascat_*` (human cancer CNV tool)
- `sentieon_*` (licensed tool, not used)
- `vep_*`, `dbnsfp_*` (human annotation databases)
- `igenomes_base` (not used with custom genome)

## Task 2: Update `manifest` block in `nextflow.config`

Change pipeline identity so it no longer shows as `nf-core/sarek` in Seqera Cloud:

- `manifest.name` — e.g. `ALE/sarek`
- `manifest.description` — ALE-specific description
- `manifest.homePage` — point to your repo

## Task 3: Document v1.0.0 scope

Update `release_v1.md` with:
- Samplesheet extensions (ploidy, clonal_or_population columns)
- Variant calling config (HaplotypeCaller joint germline, no BQSR, hard filtering fallback)
- Custom modules (VARIANTFILTRATION_FALLBACK, SPLIT_JOINT_VCF, AF-based somatic filters)
- Reference genome handling (custom FASTA + SnpEff cache, no dbSNP/known-sites)

## Task 4: nf-test for custom subworkflows

Write nf-test cases for the custom subworkflows used by v1.0.0 tools, extending the existing 3.5.1 test suite.

**Existing infrastructure** (already on `main`):
- `nf-test.config` — configured with plugins (`nft-bam@0.4.0`, `nft-utils@0.0.3`), points to `conf/test.config`
- `tests/` — 20 upstream pipeline-level `.nf.test` files with snapshots (human test data)
- `tests/csv/` — test samplesheets, `tests/config/` — test configs
- `tests/variant_calling_controlfreec.nf.test` — upstream Control-FREEC test to use as template

**Setup:**
- Install nf-test: `conda install -c bioconda nf-test`
- No custom fixtures needed — tests use nf-core remote test data (human chr21), same as existing upstream tests

**Test data strategy**: Custom subworkflows are organism-agnostic (VCF/BAM manipulation). Using nf-core test data validates the code logic without maintaining separate yeast fixtures. ALE-specific biology is validated separately in Task 5 (E2E smoke test).

**Tests to write** (pipeline-level, following existing 3.5.1 pattern):

1. **`tests/joint_germline_split_filter.nf.test`** (~medium)
   - Runs `main.nf` from `variant_calling` step with `--tools haplotypecaller --joint_germline --split_haplotypecaller_joint_vcf --hard_filter_haplotypecaller_joint`
   - Exercises: `SPLIT_JOINT_VCF` + `VCF_FILTER_HAPLOTYPECALLER_JOINT` in one test (hard filter runs downstream of split)
   - Input: existing `tests/csv/3.0/recalibrated_*.csv` with nf-core human test CRAMs
   - Assertions: `workflow.success`, output file tree snapshot, VCF file presence
   - Template: `tests/variant_calling_controlfreec.nf.test`

2. **`tests/variant_calling_germline_controlfreec.nf.test`** (~medium)
   - Runs `main.nf` from `variant_calling` step with `--tools controlfreec`
   - Exercises: `BAM_VARIANT_CALLING_GERMLINE_CONTROLFREEC` (single-sample, no normal)
   - Input: existing nf-core test samplesheet + `--chr_dir` from nf-core test data (same as upstream somatic test)
   - Assertions: `workflow.success`, CNV ratio files exist, BED output
   - Template: `tests/variant_calling_controlfreec.nf.test` (swap somatic → germline params)

## Task 5: E2E smoke test with subsampled yeast data

Package the subsampled pipeline run as an nf-test under `tests/e2e/`, validating ALE-specific biology + config end-to-end.

**Why separate from Task 4**: Task 4 tests code logic with nf-core data. Task 5 tests the full ALE pipeline with real yeast data — correct references, SnpEff cache, ploidy handling, all tools together.

**Implementation:**

- **Test file**: `tests/e2e/smoke_ottilie.nf.test`
- **Config**: `conf/test_ottilie.config` — captures ALE params from `run_ottilie_pilot_subsampled.sh` as Nextflow config (genome, tools, reference paths, SnpEff DB, etc.)
- **Data**: `data/ottilie/fastq_subsampled/` (4 samples, 1M reads each, ~575 MB)
- **Samplesheet**: `data/ottilie/samplesheet_pilot_subsampled.csv`
- **Runtime**: ~20-30 min on D4as
- **Validates**: All tools (HaplotypeCaller, CNVKit, TIDDIT, Control-FREEC, SnpEff), joint germline, split joint VCF, hard filter fallback

**Test data storage**: Local paths for v1.0.0 — data already on VM at `data/ottilie/fastq_subsampled/` (`.gitignore`d, too large for GitHub at ~575 MB). The test config documents the expected data location and download instructions. Future: upload to Azure Blob (`aledata.blob.core.windows.net`) and swap local paths to URLs to enable GitHub Actions CI.

**Assertions:**
1. `workflow.success` — all processes exit 0
2. Output file tree snapshot — expected VCFs, annotations, MultiQC exist
3. VCF file presence checks for key outputs

**Running tests separately:**
```bash
nf-test test tests/                  # Fast: module tests with nf-core data
nf-test test tests/e2e/              # Slow: full ALE pipeline with yeast data (local only)
```

## Task 6: Full Tier 1 benchmark (parallel)

Run `run_ottilie_pilot.sh` with full-depth reads to produce baseline results for benchmarking against Ottilie truth set. This runs independently and produces the reference outputs for future regression testing.

---

## Out of scope for v1.0.0

- **Seqera Cloud deployment** — schema defaults will be ALE-correct (benefits Launchpad), but a validated cloud run is not a v1.0.0 deliverable. Expect further iterations on Launchpad UI, Azure Batch compute env, and cloud-path fixes. Tracked separately in `docs/seqera_cloud/`.
- Pipeline code trimming (unused Sarek modules) — deferred to v1.1.0 upgrade
- Sarek 3.8.1 upgrade — separate effort per `ale_sarek_upgrade_runbook.md`
- Tier 2/3 benchmark execution — depends on cloud compute or larger disk
- breseq integration — still in development
- Merge `worktree-seqera-cloud` into `main` — do this when Seqera deployment is validated, not before

## Order of work

```
Task 1 (schema defaults)  ──→  Task 5 (subsampled smoke test)  ──→  Tag v1.0.0
Task 2 (manifest)         ──/
Task 3 (documentation)    ──/
Task 4 (nf-test)          ──/

Task 6 (full Tier 1 benchmark)  ──  runs in parallel, independent
```

Tasks 1-4 are independent and can be done in parallel. Task 5 is the final smoke test (~30 min). Task 6 runs alongside for benchmarking but doesn't block the release.
