# `container null` and cloud portability — ✅ RESOLVED (kept as design rationale)

> **Status: resolved before v1.0.0.** **Option B (split process)** was implemented: `BUILD_SV_COHORT`
> no longer exists — it was split into `modules/local/survivor_cohort_merge/` (SURVIVOR container) +
> `modules/local/build_sv_matrix/` (pandas container). No module under `modules/local/` uses
> `container null` any more. This page is retained for the rationale behind the split and as the
> checklist to apply if a future multi-tool process is added.
>
> **Update 2026-08-03 — the original check was incomplete.** Grepping for `container null` misses the
> other way a process ends up without an image: **declaring no `container` line at all**.
> `CNR_TO_BEDGRAPH` did exactly that (`// Pure awk — no container needed`) and passed every local test,
> because with the local executor Nextflow runs such a command directly on the host, where `awk` and
> `sort` exist. The first Azure Batch run failed at submission:
>
> ```
> No container image specified for process NFCORE_SAREK:SAREK:MUTATION_REPORT:CNR_TO_BEDGRAPH
> ```
>
> **Every cloud task must run in a container — "no tools needed" is not an exemption.** Fixed with
> `quay.io/biocontainers/gawk:5.3.0`, matching the module's conda spec. Deliberately **not** a generic
> `ubuntu` image: those ship *mawk*, which would make the conda path (gawk) and the container path
> (mawk) different tools and make the module's `versions.yml` mislabel mawk as gawk — its `sed` parses
> GNU Awk output. Pick the image that matches the declared conda package, not the smallest one.
> Use the audit below, which catches both failure modes:
>
> ```bash
> # processes with NO container line, or an explicit null
> for f in $(find modules/local -name main.nf); do
>     grep -qE '^\s*container\s' "$f" || echo "NO CONTAINER: $f"
> done
> grep -rn 'container null' modules/
> ```

## Problem (as it stood)

Some local modules use `container null` because no single biocontainer has all required tools. This works on our Azure VM (conda always available) but **will fail on Seqera Cloud** or any pure container-based execution environment where conda is not installed.

## Affected Processes

### BUILD_SV_COHORT (the former `modules/local/build_sv_cohort/main.nf`, since split)
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

## Outcome

**Option B was chosen and implemented** during v1.0.0 release prep (commit `6933123`):
`SURVIVOR_COHORT_MERGE` (survivor container) + `BUILD_SV_MATRIX` (pandas container), validated to
produce identical SV cohort matrices. The remaining `bcftools sort+index` step was not needed.

## Related

- `SURVIVOR_SV_MERGE` was split into merge (SURVIVOR container) + compress/index (nf-core `TABIX_BGZIPTABIX` with htslib container) to avoid this same issue.
- nf-core best practice: one tool per container, use mulled images for multi-tool needs.
