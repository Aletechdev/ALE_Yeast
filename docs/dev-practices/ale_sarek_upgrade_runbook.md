# ALE-Sarek Upgrade Runbook

> ⚠️ **The "Architecture", "Repo Layout", "Upgrade Steps", and "Current Patches" sections below
> describe a PROPOSED patch-and-rebuild workflow for a future sarek rebase. It is NOT how the repo is
> built today.** As of v1.0.0 the fork is a **direct, in-place fork** of sarek 3.5.1 at the repo root —
> there is no `_upstream/` directory, no `patches/`, no `rebuild.sh`, and no `conf/ale.config`. The
> actual, as-built change inventory is [`SAREK_MODIFICATIONS.md`](SAREK_MODIFICATIONS.md).
>
> The parts of this document that describe **current reality** are
> [Known Blocker: Nextflow 26.x](#known-blocker-nextflow-26x-couples-with-a-future-rebase),
> "Current Additive Files", and "Key Principles".

## Architecture (proposed)

The proposal: maintain a **single repo** that Seqera Cloud launches directly. `main.nf` must be at repo root. Customizations would be managed via:

- **Patches** (`_upstream/patches/*.patch`): minimal unified diffs that modify upstream Sarek files (main.nf wiring, schema, samplesheet parsing). These are disposable — regenerate when they break.
- **Additive files** (`modules/local/`, `subworkflows/local/`, `conf/ale.config`): our own code that never conflicts with upstream.
- **Spec markdowns** (`_upstream/specs/*.md`): semantic descriptions of *what* and *why* we customized. These are the source of truth. When a patch breaks, use the spec to regenerate it.

## Repo Layout

```
ale-sarek/
├── main.nf                         # Patched Sarek main.nf
├── nextflow.config
├── nextflow_schema.json            # Patched with ALE params
├── modules/
│   ├── nf-core/                    # Upstream, don't touch
│   └── local/                      # Upstream local + OUR additions
├── subworkflows/
│   ├── nf-core/                    # Upstream, don't touch
│   └── local/                      # Upstream local + OUR additions
├── conf/
│   └── ale.config                  # Our overrides (additive)
├── _upstream/
│   ├── SAREK_VERSION               # Pinned version string, e.g. "3.8.1"
│   ├── patches/                    # Ordered .patch files
│   ├── specs/                      # Decision record markdowns
│   ├── ale_modules/                # Source copies of our additive modules
│   ├── ale_subworkflows/           # Source copies of our additive subworkflows
│   └── rebuild.sh                  # Rebuild script
```

## Upgrade Steps

### 1. Prep: identify the new version

```bash
# Check latest Sarek release
git ls-remote --tags https://github.com/nf-core/sarek.git | tail -5

# Update pin
echo "3.9.0" > _upstream/SAREK_VERSION
```

### 2. Run rebuild script

```bash
bash _upstream/rebuild.sh
```

This script:
1. Clones clean upstream Sarek at the pinned version
2. Applies each patch in order
3. Copies additive ALE modules/subworkflows into place
4. Syncs result back to repo root (preserving `_upstream/`)

Then regenerate the launch-form schema from the overlay (see the note under *Current Patches*):

```bash
python bin/apply_schema_overlay.py          # heed its warnings — they flag params renamed upstream
python bin/apply_schema_overlay.py --check
```

### 3. If a patch fails

The script stops and tells you which patch broke. To fix:

1. Read the corresponding spec in `_upstream/specs/` to understand the intent
2. Look at what changed upstream in the affected file
3. Regenerate the patch against the new upstream
4. Re-run `rebuild.sh`

### 4. Run verification checklist

Each spec markdown contains a verification checklist. Walk through them:
- Do FastP defaults still match our expectations?
- Is the variant filtering fallback wired correctly?
- Do samplesheet extensions parse correctly?

### 5. Test

```bash
# Minimal local test
nextflow run . -profile test,docker --skip_tools baserecalibrator

# Full ALE test dataset
nextflow run . -profile test_ale,docker --input test_data/ale_samplesheet.csv
```

### 6. Commit and tag

```bash
git add -A
git commit -m "Upgrade to Sarek 3.9.0 + ALE patches"
git tag ale-sarek-3.9.0-v1
git push origin main --tags
```

## Known Blocker: Nextflow 26.x (couples with a future rebase)

**The pipeline is pinned to the Nextflow 25.10.x line** (`manifest.nextflowVersion = '!>=24.04.2, <26.0.0'`).
A move to Nextflow 26.x / Seqera 26.1.x is **not a runtime bump — it is an nf-core template
migration** and should be done together with a nf-core/sarek 4.x rebase, not on its own.

Why: Nextflow 26's stricter config DSL cannot parse the current `nextflow.config` (inherited
nf-core 3.5.1 template boilerplate). This was investigated on 26.04.6 (2026-07-13, re-verified
2026-07-22) and is an **iceberg** — fixing the first error only exposes the next layer. All four
blockers below must be resolved before the pipeline launches on 26.x.

> ⚠️ The `<26.0.0` version guard is a **secondary** net. On 26.x the parse error (blocker 1) occurs
> *before* Nextflow can read the manifest, so the guard never fires — you get
> `Cannot read project manifest -- Config parsing failed`, not a clean version message. The
> **primary** defense is pinning the runtime: `export NXF_VER=25.10.4` (already set in the launch
> scripts `bin/CENPK_run_sarek_351_all.sh` + `bin/test_ottilie.sh`; pin the Seqera CE the same way).

**The four blockers (26.04.6 strict config DSL), verified against the current `nextflow.config`:**

1. **Top-level `def` mixed with config statements** — `def trace_timestamp = new java.util.Date()...`
   (~L386) is rejected: *"Variable declarations cannot be mixed with config statements."* Inlining the
   date into each consuming GString clears this one but exposes the layers below.
2. **`Invalid include source`** — 26.x validates `includeConfig` paths at parse time. The
   `markduplicates_bam` / `markduplicates_cram` / `prepare_recalibration_bam` /
   `prepare_recalibration_cram` profiles (~L317-322) `includeConfig` `conf/test/*.config` files that
   **do not exist** in this fork. (Same latent bug the roadmap flags for removal; these are upstream
   restart-test profiles ALE doesn't use — deleting them is the preferred fix.)
3. **`manifest is not defined` (×6)** — `${manifest.name/version/doi}` GStrings in the help/completion
   blocks (~L437, L454, L457, L462) are not resolvable under strict config.
4. **`validation is not defined` (×2)** — `validation.help.beforeText` / `afterText` (~L466-467),
   from the nf-schema plugin, not resolvable under strict config.

**Seqera compatibility (verified 2026-07-13):** Seqera Platform 25.3.x → Nextflow 25.10.2 (same line,
works); Seqera 26.1.x → Nextflow 26.04 (breaks on the above). So the pipeline runs on Seqera **only**
on a 25.3.x compute environment until the 26.x migration is done.

Line numbers drift as the config changes — match on the construct, not the number.

## Current Patches (maintain this list)

| Patch | Modifies | Purpose | Spec |
|-------|----------|---------|------|
| `001-samplesheet-ale-columns.patch` | samplesheet_to_channel/, schema | Add ALE metadata columns to input CSV | `specs/samplesheet_extensions.md` |
| `002-main-nf-fallback-wiring.patch` | main.nf | Wire VARIANTFILTRATION_FALLBACK after joint genotyping | `specs/variant_filtering.md` |
| `003-schema-ale-params.patch` | nextflow_schema.json | Add ALE-specific params to Seqera launch UI | `specs/samplesheet_extensions.md` |

> **Schema visibility is NOT patched** (since 2026-09): the launch-form hidden/visible state and the
> ALE-owned help texts live in `conf/schema_overlay.yml`, applied by `bin/apply_schema_overlay.py`.
> After applying patches to a new upstream `nextflow_schema.json`, re-run
> `python bin/apply_schema_overlay.py` (then `--check` in verification) — see
> `SAREK_MODIFICATIONS.md` → root files → `nextflow_schema.json`.

## Current Additive Files (these never conflict) — as built

Purely additive, so a rebase carries them over untouched. Full list and per-file rationale in
[`SAREK_MODIFICATIONS.md`](SAREK_MODIFICATIONS.md).

- **`modules/local/`** (16 added) — `breseq/`, `gdtools/`, `build_cn_matrix/`, `build_cn_cohort/`,
  `build_sv_matrix/`, `survivor_sv_merge/`, `survivor_cohort_merge/`, `igvreports_cohort/`,
  `igvreports_sample/`, `igvreports_sv_cnv/`, `prepare_gff3/`, `prepare_vcf/`, `generate_index/`,
  `cnr_to_bedgraph/`, `filter_pass_vcf/`, `publish_vcfs/`.
- **`subworkflows/local/`** (6 added) — `mutation_report/`, `fastq_variant_calling_breseq/`,
  `split_joint_vcf/`, `vcf_filter_haplotypecaller_joint/`, `vcf_filter_mutect2/`, `vcf_filter_freebayes/`.
- **`conf/`** (added) — `conf/modules/mutation_report.config`, `conf/modules/breseq.config`,
  `conf/modules/custom_haplotypecaller_joint_filter.config`, `conf/modules/custom_mutect2_filter.config`,
  `conf/modules/custom_freebayes_filter.config`, `conf/test/ottilie_test.config`,
  `conf/azured4as.config`, `conf/seqera_azure.config`.

The hard-filter fallback is **not** a local module: it reuses the nf-core module
`modules/nf-core/gatk4/variantfiltration/`, aliased as `VARIANTFILTRATION_FALLBACK` inside
`subworkflows/local/bam_joint_calling_germline_gatk/` (a *modified* upstream subworkflow, so it does
carry rebase cost).

## Key Principles

- **Patches are small and disposable.** Each patch should be <100 lines of diff. All real logic lives in additive files.
- **Specs are the source of truth.** If a patch is lost or broken beyond repair, the spec contains enough detail to rewrite it from scratch.
- **Additive files never touch upstream code.** They only get `include`-d by patched files.
- **Skip releases you don't need.** Only upgrade when a new Sarek version has features or fixes relevant to ALE.
