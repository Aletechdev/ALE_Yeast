# ALE-Sarek Upgrade Runbook

## Architecture

We maintain a **single repo** (`ale-sarek/`) that Seqera Cloud launches directly. `main.nf` must be at repo root. Customizations are managed via:

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

## Current Patches (maintain this list)

| Patch | Modifies | Purpose | Spec |
|-------|----------|---------|------|
| `001-samplesheet-ale-columns.patch` | samplesheet_to_channel/, schema | Add ALE metadata columns to input CSV | `specs/samplesheet_extensions.md` |
| `002-main-nf-fallback-wiring.patch` | main.nf | Wire VARIANTFILTRATION_FALLBACK after joint genotyping | `specs/variant_filtering.md` |
| `003-schema-ale-params.patch` | nextflow_schema.json | Add ALE-specific params to Seqera launch UI | `specs/samplesheet_extensions.md` |

## Current Additive Files (these never conflict)

- `modules/local/variantfiltration_fallback/` — hard filtering for non-model organisms
- `subworkflows/local/ale_post_calling/` — ALE-specific post-variant-calling logic
- `conf/ale.config` — ext.args overrides, Azure Batch tuning, FastP config

## Key Principles

- **Patches are small and disposable.** Each patch should be <100 lines of diff. All real logic lives in additive files.
- **Specs are the source of truth.** If a patch is lost or broken beyond repair, the spec contains enough detail to rewrite it from scratch.
- **Additive files never touch upstream code.** They only get `include`-d by patched files.
- **Skip releases you don't need.** Only upgrade when a new Sarek version has features or fixes relevant to ALE.
