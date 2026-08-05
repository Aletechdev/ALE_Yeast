# NF_ALE Project Notes

> **Maintenance convention.** This file holds operational summaries + pointers into `docs/`; the
> linked doc is the source of detail. When you change pipeline behavior, update **both** the summary
> here and the linked doc so they stay in sync. Keep inline notes to *stable* facts (tool tiers,
> thresholds, paths); push volatile detail to `docs/`. Pointers must resolve even if the target doc
> isn't yet complete.

## Table of Contents
1. [Pipeline Identity & Naming](#pipeline-identity--naming)
2. [Environment Setup](#environment-setup)
3. [Input Configuration](#input-configuration)
4. [Variant Calling Strategy](#variant-calling-strategy)
5. [Implementation Details](#implementation-details)
6. [Tool-Specific Notes](#tool-specific-notes)
7. [Variant Analysis Dashboard System](#variant-analysis-dashboard-system)
8. [Pipeline Merger Decision - Reminder](#pipeline-merger-decision---reminder)

---

## Pipeline Identity & Naming

Three names refer to the same thing — kept distinct on purpose:

| What | Value | Notes |
|------|-------|-------|
| **Brand** (this version) | **yAMP** — *yeast Automated Mutation Pipeline* | Product name; future majors → AMPv3, … Lives in `manifest.description`. |
| **`manifest.name`** | **`Aletechdev/AMP`** | Stable `org/repo`-form pipeline identity (drives the console banner, MultiQC header, versions `id:`, Seqera launch title). `org/repo` form keeps `nextflow run <name>` viable if ever open-sourced. |
| **GitHub repo (handle/URL)** | **`Aletechdev/ALE_Yeast`** → https://github.com/Aletechdev/ALE_Yeast | The real repo; `worktree-seqera-cloud` lives here. Also `manifest.homePage`. |

**`manifest.name` (`Aletechdev/AMP`) intentionally ≠ the repo handle (`Aletechdev/ALE_Yeast`)** — the
brand stays clean while the repo keeps its existing name. Both may be reconciled/renamed later. The
`description` (brand) evolves per version; `manifest.name` (identity) stays stable so it isn't churned.

> **Status:** ✅ applied 2026-07-27 (v1.0.0 release prep). `manifest.name`, `version = '1.0.0'`, `description`,
> `homePage`, and `doi = ''` set in `nextflow.config`; ottilie e2e re-snapshotted — the only output delta
> was the `versions.yml` Workflow line (`nf-core/sarek: v3.5.1` → `Aletechdev/AMP: v1.0.0`).

---

## Environment Setup

User-facing install/run instructions live in [`README.md`](README.md); a bare-machine walkthrough is
[`docs/usage/new_machine_setup.md`](docs/usage/new_machine_setup.md). Only the facts a contributor
needs in-session are repeated here.

- **Toolchain**: `conda activate nf-env` (spec: [`environment.yml`](environment.yml) — nextflow 25.10.4,
  nf-test 0.9.3, nf-core 3.5.1, openjdk 17, python 3.13). Use `python`, **not** `python3`.
- **Nextflow version**: run on **25.10.4** — `environment.yml` and the launchers' `NXF_VER` are
  deliberately the same version, so an unpinned shell inside `nf-env` runs the engine everything else
  assumes. Keep them in sync. `NXF_VER` still wins wherever it is set (it self-fetches that engine
  regardless of what conda installed). **26.x cannot parse `nextflow.config`** —
  see [`ale_sarek_upgrade_runbook.md`](docs/dev-practices/ale_sarek_upgrade_runbook.md).
- **Resources**: `-profile azureD4as` is **on dev VM only** (4 vCPU / 16 GB). On any other machine
  copy [`conf/mymachine.config`](conf/mymachine.config) and pass it with `-c` — never reuse
  `azureD4as`. Model + precedence rules: [`compute_resources.md`](docs/dev-practices/compute_resources.md).
- **Apple Silicon is NOT supported** — tools stall/hang under ARM (MultiQC, Mutect2) plus
  filesystem-optimization problems. The `arm,docker` profile is retained for reference only.

### Cloud execution — Azure Batch

Opt-in only: `-c conf/azure_batch.config` (deliberately **not** a profile) plus
`-params-file conf/params_ottilie_blob.yml`; launcher `bin/test_ottilie_azure_batch.sh`. Azure service
principal + RBAC provisioning lives in [`deploy/azure/`](deploy/azure/) (per-resource grants only, never
resource-group-wide). **Status: validated end-to-end for a LOCAL head job** (2026-08-03 — 138 tasks,
540 blobs published). Outputs are **not yet diffed against a local run**, and a **Seqera Platform
launch is a separate, unproven step**.

**Before changing any Azure setting, read the orientation section** —
[`azure_batch_execution.md` → why this config isn't the five-line example](docs/dev-practices/azure_batch_execution.md#orientation--why-this-config-isnt-the-five-line-example).
Only 4 settings differ from the stock tutorial config (auth, `vmType`, image pin, `workDir`
placement); 3 are forced by the account or by the service-principal auth, not chosen. The
non-obvious rules, each learned by running it — full detail in the same doc:

- **With an Entra/SP credential, `workDir` must be in the same blob *container* as the inputs** — same
  storage account is not enough. Nextflow mints **one** container-scoped SAS (`sr=c`) for the work-dir
  container and reuses it for every blob URL, so a Batch node cannot read another container even in the
  same account; the task exits 1 with empty stderr. **This tracks the CREDENTIAL, not local-vs-cloud** —
  a shared-key credential gives nodes account-wide access and has no such rule (verified: the
  `aledev4test_e4ds_v4` CE runs `workDir` and inputs in different containers). Granting the SP more RBAC
  does **not** help: it already holds `Storage Blob Data Contributor` on the whole account; the limit is
  what Nextflow *delegates*, not what the SP *may* do. **`outdir` is exempt** — `publishDir` runs in the
  head process using the full credential (verified for a local head job; unproven under Platform).
- **Every declared input path must exist.** `file('SENTINEL')` for a missing file works locally
  (symlink) but fails on a remote work dir, which must physically copy. Use `checkIfExists: true`.
  `projectDir` assets are fine — nf-core relies on them too.
- **Pin the newest `verified` `ubuntu-hpc` LTS**, named by node *agent* SKU (`batch.node.ubuntu 24.04`),
  not image sku. Nextflow's default (22.04) has aged out service-wide — re-pin at each LTS. Stay on
  `ubuntu-hpc`: the only verified family with a container runtime.
- **Pool ids are content-addressed** (`nf-pool-<hash>-<vmType>` over the `pools` block), so
  `deletePoolsOnCompletion` breaks `-resume`. Idle pools cost nothing; keep them.
- **Bare `-resume` resumes the *last* run in `.nextflow/history`** — any `-preview` or unrelated test in
  the same directory hijacks the chain. Pass an explicit session id.
- **Optional file params must be passed as `[]`**, never `null` (`file(null)` throws while the DAG is
  built) and never a placeholder filename (fails to stage on a remote work dir). This bit
  `report_gff3`, which aborted with a bogus "sample-sheet only contains tumor-samples" error until it
  was made properly optional (2026-08-04). The dangling `ifEmpty` that produces that misdirection is
  still there for *other* early aborts — [`troubleshooting.md`](docs/dev-practices/troubleshooting.md).

---

## Input Configuration

### Key Files and Locations

- **Test data (ottilie)** — the release test set: 2 samples (parent + evolved), 4 chromosomes; truth =
  4 SNVs + a chr I duplication. Lives under `data/ottilie/` (gitignored). Profile:
  [`conf/test/ottilie_test.config`](conf/test/ottilie_test.config) → run
  `nextflow run main.nf -profile ottilie_test,azureD4as,docker`. Generate locally with
  `docs/benchmarking/ottilie_xenobiotic_ale/01_data_retrieval/generate_test_data.sh`; on a fresh machine
  fetch from the public blob (no creds) with `download_test_data.sh`. Full lineage/prep:
  [`docs/benchmarking/ottilie_xenobiotic_ale/DATA_PROVENANCE.md`](docs/benchmarking/ottilie_xenobiotic_ale/DATA_PROVENANCE.md).
- **Launchers**: `bin/test_ottilie.sh` (minimal 2-sample test) · `bin/test_ottilie_blob.sh` (same test, `ottilie_test_ci` profile — inputs streamed from the public blob, **no local `data/ottilie/`**; `snpeff_cache` is a directory param and can't come from an https URL, so the script untars the published `snpeff_cache.tar.gz` locally first) · `docs/benchmarking/ottilie_xenobiotic_ale/03_pipeline/run_ottilie_pilot.sh` (full-depth **4-sample** run, same S288C data). The 2-sample test set is a **chromosome subset** (chr I/IV/VII/XV) of **2 of** the pilot's 4 `--save_mapped` CRAMs, extracted by `generate_test_data.sh` — not a read-subsample. Both use `-profile azureD4as,docker`.
- **Resources config**: [`conf/azured4as.config`](conf/azured4as.config) (the `azureD4as` local-VM profile;
  use `-profile azureD4as`, no `-c` needed). See [`docs/dev-practices/compute_resources.md`](docs/dev-practices/compute_resources.md).
- **SnpEff cache generation**: `docs/prepare_input/process_GeneBank/generate_cache/gen_cache.sh`.
- **Fork base**: nf-core/sarek 3.5.1 — the fork tree lives at the **repo root** (`main.nf`, `conf/`,
  `workflows/`, `modules/`, `subworkflows/`); consult the upstream 3.5.1 docs for base behavior.
  A pristine copy for diffing sits in the `sarek-compare` worktree (see `docs/dev-practices/SAREK_MODIFICATIONS.md`).
- **Production/example data (CENPK, dicarboxylic acids)** — real-experiment dataset, not the test set:
  `https://aledata.blob.core.windows.net/aledata/Yeast/dicarboxylic_acids_all_clones/REDACTED-CUSTOMER-ID/ANP_Dev_2025Q3/data/`

### Sample Table Format

Canonical column reference, conventions, and non-Tier-1 notes:
[`docs/usage/input_samplesheet.md`](docs/usage/input_samplesheet.md). A worked example is in
[`README.md`](README.md). The **ALE-specific invariants** worth knowing without opening either:

- **All samples are normal (`status = 0`)** — that is what puts HaplotypeCaller in joint-germline
  mode. Tumor/`1` is unused; tumor-only mode is a deferred fork idea
  ([`docs/archive/sarek_fork_ideas.md`](docs/archive/sarek_fork_ideas.md)).
- **`experiment`** maps to Sarek's `patient` and groups samples for joint calling.
- **`ploidy`** and **`clonal_or_population`** are ALE additions — ploidy feeds
  `--sample-ploidy`/FreeBayes/TIDDIT/Control-FREEC; clonal-vs-population drives the joint HC
  hard-filter AF thresholds.
- **`sex`** is inert on a Tier-1 run — only Control-FREEC/ASCAT read it. Not auto-filled (open
  convenience item, Tier-2 only).

---

## Variant Calling Strategy

### Tier-1 tools — v1.0.0 deliverable (validated by the ottilie contract test)

- **SNV/INDEL — GATK HaplotypeCaller**: joint (cohort) + individual germline calling; joint-germline is the ALE default.
- **CNV — CNVKit**: `fold_change`-based CN matrices — see the [CNVKit section](#cnvkit-tier-1-cnv-deliverable).
- **SV — Manta + TIDDIT**: merged via SURVIVOR into per-sample + cohort matrices.
- **Annotation — SnpEff**: custom cache (`docs/prepare_input/process_GeneBank/generate_cache/gen_cache.sh`).

### Tier-2 tools — functional, not release-validated for ALE

- **GATK Mutect2** (somatic; runs without `--germline-resource`/`--panel-of-normals` on the custom
  genome — see [`mutect2_custom_genome_resources.md`](docs/variant-calling/mutect2/mutect2_custom_genome_resources.md)) and **FreeBayes**
  (germline mode only; somatic disabled — too noisy) — SNV/INDEL. AF-based filters for both:
  [`docs/variant-calling/tier2_af_filters.md`](docs/variant-calling/tier2_af_filters.md).
- **Control-FREEC** (germline CNV — see the [Control-FREEC section](#control-freec-tier-2-cnv)) · **breseq** (bacterial, not released).

**Ploidy Support:**
- Passed to: HaplotypeCaller (`--sample-ploidy`), `controlfreec`, `FreeBayes`, `Tiddit`
- **Manta**: has **no** ploidy parameter — it's an SV breakpoint caller (no genotype-by-ploidy), so it's excluded by design, not an omission.
- **Note**: `bcftools mpileup` still uses ploidy=1 in `conf/modules/ngscheckmate.config`
- **CNVKit**: does **not** take `--ploidy` (reverted May 2026 → defaults to 2; CN scale is always `cn=2` baseline regardless). Use `fold_change`/log2 for true signal — see the [CNVKit section](#cnvkit-tier-1-cnv-deliverable) and [`docs/variant-calling/cnvkit/cnvkit_ploidy_behavior.md`](docs/variant-calling/cnvkit/cnvkit_ploidy_behavior.md).

---

## Implementation Details

### Tier-2 somatic AF filters (Mutect2 / FreeBayes)

**Tier-2 (functional, not release-validated for ALE).** Mutect2 and FreeBayes are somatic
callers — too sensitive/noisy for ALE (FreeBayes somatic mode alone gave 248,248 variants vs
10,965 germline). Custom AF-based filters (Normal AF < 0.10, Tumor AF > 0.05, diff > 0.05,
depth tumor ≥ 10 / normal ≥ 8), multi-allelic `bcftools norm -m-` splitting, strand-bias
filtering, FreeBayes-somatic disabled, and the FilterMutectCalls channel-join fix all live in
[`docs/variant-calling/tier2_af_filters.md`](docs/variant-calling/tier2_af_filters.md).
**HaplotypeCaller is the Tier-1 SNV/INDEL deliverable.**

### Bug Fixes

#### ✅ YAML Processing Error (Custom VCF Filters)

Groovy method-resolution ambiguity in `processVersionsFromYAML()`
(`subworkflows/nf-core/utils_nfcore_pipeline/main.nf`) fixed via
explicit `java.io.FileInputStream(path.toFile())` + null/empty validation, so
`VCF_FILTER_FREEBAYES` / `VCF_FILTER_MUTECT2` work correctly.

---

## Tool-Specific Notes

### Read preprocessing — BQSR skipped

BQSR (BaseRecalibrator — a read-recalibration **preprocessing** step, before any variant calling) is
skipped: the custom yeast reference has no `--known-sites` VCFs, which BQSR requires. This is a
**required manual opt-out, not automatic** — every ALE config sets `skip_tools = 'baserecalibrator'`
(`conf/test/ottilie_test.config` + the run scripts), and **dropping it aborts the run**. The missing
known-sites resource *starves* the BaseRecalibrator channel, surfacing as a Nextflow join error (not a
GATK error). The same starvation gates VQSR (which has the soft-filter fallback — see the HaplotypeCaller
section below) and FilterVariantTranches. Full mechanism:
[`haplotypecaller_workflow_analysis.md` → known-sites starvation](docs/variant-calling/haplotypecaller/haplotypecaller_workflow_analysis.md#4-the-known-sites-starvation-pattern-custom-genomes).


### GATK HaplotypeCaller (joint germline)

The Tier-1 SNV/INDEL caller. Two ALE-specific customizations on the joint-germline path:

#### Soft-filter fallback (VQSR unavailable)

VQSR is unavailable for the custom yeast genome (no known-sites resources). As a fallback, GATK
`VARIANTFILTRATION_FALLBACK` **soft-filters** the joint VCF — it populates the FILTER column
(`PASS` or named tags like `QD_filter`) but **does not remove variants**. Output:
`HaplotypeCaller_joint_calling_soft_filtered.vcf.gz`. Extract PASS-only downstream with
`bcftools view -f PASS`. Details, filter thresholds, and trigger conditions:
[`docs/variant-calling/haplotypecaller/SOFT_FILTER_HAPLOTYPECALLER_JOINT.md`](docs/variant-calling/haplotypecaller/SOFT_FILTER_HAPLOTYPECALLER_JOINT.md).

#### Split joint VCF into individual sample VCFs

The `SPLIT_JOINT_VCF` subworkflow extracts per-sample VCFs from the joint calling output using
channel-based metadata propagation (no string parsing). Enable with
`--joint_germline --split_haplotypecaller_joint_vcf`. Output:
`variant_calling/haplotypecaller/individual_from_joint/<sample>/<sample>.haplotypecaller.from_joint_calling.vcf.gz`
(+ `.tbi`). Full architecture, channel flow, and manual bcftools recipe:
[`docs/variant-calling/haplotypecaller/SPLIT_JOINT_VCF_PIPELINE.md`](docs/variant-calling/haplotypecaller/SPLIT_JOINT_VCF_PIPELINE.md).

### CNVKit (Tier-1 CNV deliverable)

CNVKit is the **Tier-1 CNV deliverable**. No explicit `--ploidy` is passed (that was reverted
May 2026 — CNVKit defaults to 2); CN matrices use `fold_change = 2^log2` (ploidy-agnostic depth
ratio). **Caveat**: CNVKit's integer `cn` always uses `cn=2` as baseline regardless of ploidy,
so use `fold_change`/`log2` for the true signal. Details:
[`docs/variant-calling/cnvkit/`](docs/variant-calling/cnvkit/).

### VCFtools Compatibility

#### ⚠️ Conditional Skipping

VCFtools **conditionally skipped** due to compatibility issues:

**1. Ploidy > 2**
- Error: "Polyploidy found, and not supported by vcftools"
- Works: ploidy 1-2, Fails: ploidy ≥ 3

**2. Mutect2 Phased Genotypes**
- Issue: Mutect2 outputs phased (0|0, 0|1) instead of unphased (0/0, 0/1)
- Impact: VCFtools expects standard format

**3. Joint Calling Segmentation Fault**
- Issue: VCFtools 0.1.16 crashes on joint_variant_calling.vcf.gz (exit 139)
- Root cause: Memory corruption with GATK joint calling format

**Configuration** (`conf/modules/modules.config`):
```yaml
ext.when = { !(params.skip_tools.contains('vcftools')) &&
             (meta.ploidy == null || meta.ploidy <= 2) &&
             (meta.variantcaller != 'mutect2') &&
             !(meta.id ==~ /.*joint_variant_calling.*/) }
```

**VCFtools runs for**:
- ✅ FreeBayes individual (ploidy ≤ 2)
- ✅ HaplotypeCaller individual
- ❌ Mutect2 (all)
- ❌ Joint variant calling
- ❌ Ploidy > 2

### Control-FREEC (Tier-2 CNV)

**Tier-2 (functional, not release-validated for ALE).** Not the Tier-1 CNV deliverable because:
no SNP database → no BAF (copy number from read depth only); no standard VCF output → no SnpEff
annotation; `ASSESS_SIGNIFICANCE` fails for haploid (ploidy=1) samples (empty `*.gz_CNVs` → R
script error, auto-skipped via `conf/modules/controlfreec.config`); and it crashes on some
samples with `std::length_error`. **CNVKit is the Tier-1 CNV deliverable instead.** Single-sample
germline mode (April 2026) is implemented — see
[`docs/variant-calling/controlfreec/controlfreec_germline_changes.md`](docs/variant-calling/controlfreec/controlfreec_germline_changes.md).

## Variant Analysis Dashboard System

**Superseded.** The original `bin/` dashboard scripts (`create_research_dashboard.py`,
`summarize_variants.py`, `organize_results.sh`, `quick_variant_check.sh`, `create_variant_dashboard.py`)
were removed during the v1.0.0 code cleanup. Their role — cross-sample / multi-tool variant tables, cohort matrices, and gene /
tool-comparison views — is now delivered by the **`MUTATION_REPORT` subworkflow + `GENERATE_INDEX`**
(igv-reports HTML dashboard backed by `cn_cohort_matrix.csv` / `sv_cohort_matrix_*.csv` /
`cn_segments_*.csv`). See [`docs/igvreports/`](docs/igvreports/) and
[`subworkflows/local/mutation_report/`](subworkflows/local/mutation_report/main.nf). The original design
writeup (kept for future mutation-report work) is archived at
[`docs/archive/variant_dashboard_system.md`](docs/archive/variant_dashboard_system.md).

## Pipeline Merger Decision - Reminder
### Two Pipeline Architectures
#### AMP v1 (Legacy ALE Pipeline)

Input: Individual CSV files per sample
Annotation: GenBank (.gb) files
Tools: breseq + GATK + CNVnator
Target: Bacterial ALE experiments (haploid)
Deployment: Azure Batch → migrating to Nextflow

#### Customer Sarek Pipeline

Input: Population CSV table
Annotation: SnpEff cache + FASTQ
Tools: Standard Sarek workflow (GATK-based)
Target: Eukaryotic ALE experiments
Deployment: Nextflow
Decision Required

#### ⚠️ INVESTIGATE BEFORE PROCEEDING:

Merger Feasibility: Can GenBank and SnpEff annotation systems coexist?
Tool Integration: How to incorporate breseq into Sarek architecture?
Input Standardization: Worth converging to population CSV format?
Maintenance Trade-offs: One complex pipeline vs two focused pipelines?