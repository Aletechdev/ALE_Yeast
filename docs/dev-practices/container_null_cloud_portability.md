# TODO: Replace `container null` with mulled containers for cloud portability

## Problem

Some local modules use `container null` because no single biocontainer has all required tools. This works on our Azure VM (conda always available) but **will fail on Seqera Cloud** or any pure container-based execution environment where conda is not installed.

## Affected Processes

### BUILD_SV_COHORT (`modules/local/build_sv_cohort/main.nf`)
```groovy
conda 'bioconda::survivor=1.0.7 bioconda::bcftools=1.20 conda-forge::pandas'
container null  // No single biocontainer has all three; use conda
```
Needs: SURVIVOR + bcftools + pandas (Python)

## Solution Options

### Option A: Mulled container (preferred)
Generate a BioContainers mulled image with all required tools:
```bash
# Install mulled-build (galaxy-tool-util)
pip install galaxy-tool-util

# Generate mulled container hash
mulled-build build-and-test \
    --packages survivor=1.0.7,bcftools=1.20,pandas \
    --namespace biocontainers
```
Then reference the mulled image in the `container` directive.

### Option B: Split process
Break multi-tool processes into single-tool steps (like we did with SURVIVOR_SV_MERGE → TABIX_BGZIPTABIX). More verbose but each process uses a standard biocontainer.

For BUILD_SV_COHORT this would mean:
1. SURVIVOR merge (SURVIVOR container) — already separate
2. sv_cohort_matrix.py (pandas container) — Python-only, reads gzipped VCFs
3. bcftools sort+index (bcftools container) — only needed for cohort VCF output

### Option C: Custom Dockerfile
Build a project-specific image with all tools. More maintenance overhead but full control.

## Priority

Low — only relevant when deploying to Seqera Cloud. Current Azure VM workflow uses conda and works correctly.

## Related

- `SURVIVOR_SV_MERGE` was split into merge (SURVIVOR container) + compress/index (nf-core `TABIX_BGZIPTABIX` with htslib container) to avoid this same issue.
- nf-core best practice: one tool per container, use mulled images for multi-tool needs.
