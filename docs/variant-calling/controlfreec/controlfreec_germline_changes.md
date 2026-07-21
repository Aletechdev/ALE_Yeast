# Control-FREEC Germline Mode — Implementation Review

**Branch**: `worktree-controlfreec-germline`
**Date**: 2026-04-13

## Context

Control-FREEC previously only ran in somatic (tumor/normal pair) and tumor-only workflows. For ALE experiments where all samples are treated as germline (`status=0`), no CNV analysis from Control-FREEC was available. This change adds single-sample Control-FREEC to the germline workflow so every sample gets CNV analysis alongside SNV calling.

**Design decision**: Each sample runs independently (single-sample mode, same as tumor-only). No paired normal/control is used.

**Ploidy support**: `meta.ploidy` from the samplesheet flows through to FREEC's config via `ext.args["general"]["ploidy"]`. Both ploidy=1 (clonal/haploid) and ploidy=2 (population/diploid) are supported. `ASSESS_SIGNIFICANCE` auto-skips for ploidy=1 (existing behavior — haploid samples produce empty CNV files).

---

## Files Changed

### 1. NEW: `nf-core-sarek_3.5.1/3_5_1/subworkflows/local/bam_variant_calling_germline_controlfreec/main.nf`

New subworkflow copied from the tumor-only template. Key differences:
- Workflow name: `BAM_VARIANT_CALLING_GERMLINE_CONTROLFREEC`
- FREEC module alias: `FREEC_GERMLINE` (instead of `FREEC_TUMORONLY`)
- Same post-processing chain: ASSESS_SIGNIFICANCE → FREEC2BED → FREEC2CIRCOS → MAKEGRAPH2

```groovy
include { CONTROLFREEC_FREEC as FREEC_GERMLINE } from '../../../modules/nf-core/controlfreec/freec/main'
// ... same post-processing modules as tumor-only

workflow BAM_VARIANT_CALLING_GERMLINE_CONTROLFREEC {
    take:
    controlfreec_input       // [meta, [], pileup, [], [], [], []]
    fasta                    // path (unwrapped)
    fasta_fai                // path (unwrapped)
    dbsnp                    // path
    dbsnp_tbi                // path
    chr_files                // path
    mappability              // path
    intervals_bed            // path or []

    main:
    FREEC_GERMLINE(controlfreec_input, fasta, fasta_fai, [], dbsnp, dbsnp_tbi, chr_files, mappability, intervals_bed, [])
    // ... post-processing identical to tumor-only
}
```

---

### 2. EDITED: `nf-core-sarek_3.5.1/3_5_1/conf/modules/controlfreec.config`

Added `FREEC_GERMLINE` config block between `FREEC_TUMORONLY` and `FREEC_SOMATIC`. Parameters are identical to `FREEC_TUMORONLY` (single-sample, no `[control]` section):

```groovy
// GERMLINE_VARIANT_CALLING (single-sample, no control)
    withName: 'FREEC_GERMLINE' {
        ext.args   = { [
                "sample":[ inputformat: 'pileup', mateorientation: 'FR' ],
                "general" :[
                    ploidy: meta.ploidy,          // from samplesheet
                    sex: meta.sex,                // from samplesheet
                    window: params.cf_window ?: "",
                    // ... same WGS/WES conditionals as FREEC_TUMORONLY
                ],
                "BAF":[ /* same BAF params */ ]
        ] }
    }
```

**Note**: The existing `withName: 'FREEC_.*'` wildcard (line 27) already covers `ext.when` and `publishDir` for any process matching `FREEC_*`, so `FREEC_GERMLINE` automatically inherits:
- `ext.when = { params.tools && params.tools.split(',').contains('controlfreec') }`
- `publishDir` to `variant_calling/controlfreec/${meta.id}/`

---

### 3. EDITED: `nf-core-sarek_3.5.1/3_5_1/subworkflows/local/bam_variant_calling_germline_all/main.nf`

Three changes:

**a) Import** (line 18):
```groovy
include { BAM_VARIANT_CALLING_GERMLINE_CONTROLFREEC } from '../bam_variant_calling_germline_controlfreec/main'
```

**b) New `take:` parameters** (lines 54-56):
```groovy
    chr_files                         // channel: [optional]  controlfreec chromosome files
    mappability                       // channel: [optional]  controlfreec mappability file
    wes                               // boolean: [mandatory] [default: false] whether targeted data is processed
```

**c) Expanded mpileup conditional + controlfreec block** (lines 74-103):
```groovy
    // BCFTOOLS MPILEUP (also needed for controlfreec)
    if (tools.split(',').contains('mpileup') || tools.split(',').contains('controlfreec')) {
        BAM_VARIANT_CALLING_MPILEUP(cram, dict, fasta, intervals)
        vcf_mpileup = BAM_VARIANT_CALLING_MPILEUP.out.vcf
        versions = versions.mix(BAM_VARIANT_CALLING_MPILEUP.out.versions)
    }

    // CONTROLFREEC (depends on MPILEUP)
    if (tools.split(',').contains('controlfreec')) {
        intervals_controlfreec = wes ? intervals_bed_combined : []

        BAM_VARIANT_CALLING_GERMLINE_CONTROLFREEC(
            BAM_VARIANT_CALLING_MPILEUP.out.mpileup.map{ meta, pileup ->
                [ meta, [], pileup, [], [], [], [] ]   // 7-element tuple, no control
            },
            fasta.map{ meta, fasta -> [ fasta ] },     // unwrap meta
            fasta_fai.map{ meta, fasta_fai -> [ fasta_fai ] },
            dbsnp, dbsnp_tbi,
            chr_files, mappability,
            intervals_controlfreec
        )
        versions = versions.mix(BAM_VARIANT_CALLING_GERMLINE_CONTROLFREEC.out.versions)
    }
```

**Channel flow**:
```
cram [meta, cram, crai]
  → BAM_VARIANT_CALLING_MPILEUP → mpileup [meta, pileup]
  → remap to [meta, [], pileup, [], [], [], []]  (empty normal slot)
  → FREEC_GERMLINE → CNV, ratio, BedGraph, circos, PNG outputs
```

---

### 4. EDITED: `nf-core-sarek_3.5.1/3_5_1/workflows/sarek/main.nf`

Added 3 new arguments to `BAM_VARIANT_CALLING_GERMLINE_ALL` invocation (line 760):

```groovy
            sentieon_dnascope_model,
            chr_files,         // NEW: controlfreec chromosome files
            mappability,       // NEW: controlfreec mappability file
            params.wes)        // NEW: WGS vs WES flag
```

These channels were already available in the SAREK workflow scope (used by somatic/tumor-only).

---

### 5. EDITED: `nf-core-sarek_3.5.1/3_5_1/subworkflows/local/samplesheet_to_channel/main.nf`

Removed `controlfreec` from the `tools_tumor` validation list. Previously, the pipeline would error out if `controlfreec` was requested but no tumor samples existed in the samplesheet. Since controlfreec now supports germline mode, this check is no longer appropriate.

```diff
-            def tools_tumor = ['ascat', 'controlfreec', 'mutect2', 'msisensorpro']
+            def tools_tumor = ['ascat', 'mutect2', 'msisensorpro'] // controlfreec removed: now supports germline mode
```

---

### 6. EDITED: `bin/test_nf.sh`

Added `controlfreec` to the `--tools` list:

```diff
-    --tools snpeff,haplotypecaller,freebayes,cnvkit,tiddit,manta,breseq  \
+    --tools snpeff,haplotypecaller,freebayes,cnvkit,controlfreec,tiddit,manta,breseq  \
```

---

### 7. Follow-up: `ASSESS_SIGNIFICANCE` ploidy=1 investigation

Tracked in [`docs/dev-practices/roadmap.md`](../../dev-practices/roadmap.md) (CNV section) — why does Control-FREEC produce empty `*.gz_CNVs` files for haploid samples?

---

## Ploidy Handling Summary

| Ploidy | FREEC_GERMLINE | ASSESS_SIGNIFICANCE | FREEC2BED/CIRCOS | MAKEGRAPH2 |
|--------|---------------|---------------------|------------------|------------|
| 1 (haploid) | Runs | Skipped (empty CNVs) | Runs (uses meta.ploidy) | Runs if BAF exists |
| 2 (diploid) | Runs | Runs | Runs (uses meta.ploidy) | Runs if BAF exists |

Config controlling the skip (`controlfreec.config` line 19):
```groovy
withName: 'ASSESS_SIGNIFICANCE' {
    ext.when = { !(meta.ploidy == null || meta.ploidy.toString().toInteger() == 1) }
}
```

---

## Expected Output Structure

```
output/variant_calling/controlfreec/
├── A0-F0-I1-R1/          # ploidy=1 (haploid)
│   ├── *_ratio.BedGraph
│   ├── *_sample.cpn
│   ├── *_CNVs             # may be empty for ploidy=1
│   ├── *_info.txt
│   ├── *_ratio.txt
│   ├── *.bed
│   └── *circos.txt
├── A1-F6-I1-R1/          # ploidy=1
│   └── ...
├── A1-F6-I2-R1/          # ploidy=2 (diploid)
│   ├── ... (same as above)
│   └── *.p.value.txt     # ASSESS_SIGNIFICANCE runs
└── A1-F6-I3-R1/          # ploidy=2
    └── ...
```

---

## Verification Steps

1. **Syntax check**: `nextflow run ... -preview` to validate channel wiring without executing
2. **Full test run**: `bash bin/test_nf.sh` with the updated tools list
3. **Check outputs**: Verify `variant_calling/controlfreec/<sample>/` directories created
4. **Ploidy=1**: Confirm ASSESS_SIGNIFICANCE skipped, other outputs present
5. **Ploidy=2**: Confirm ASSESS_SIGNIFICANCE runs, `*.p.value.txt` generated
6. **No regressions**: Existing somatic/tumor-only Control-FREEC paths unaffected

---

## Known Issue: FREEC_GERMLINE std::length_error Crash

**Observed**: Tier 2 run, May 2026 (sample BMS983970-2R1e)

**Error**:
```
terminate called after throwing an instance of 'std::length_error'
  what():  cannot create std::vector larger than max_size()
Aborted (core dumped) freec -conf config.txt
```

**Exit code**: 134 (SIGABRT)

**When it happens**: FREEC completes breakpoint detection for all chromosomes, then crashes during the "annotate copy numbers" step. In this case, the mitochondrial chromosome had very high breakpoint density (22 breakpoints in 133 windows), which may trigger the C++ vector overflow.

**Impact**: Minimal. With `errorStrategy = 'retry'` and `maxRetries = 1`, the retry fails the same way (deterministic bug, not memory-related). Nextflow then skips this one sample for FREEC and continues the pipeline. All other callers (HaplotypeCaller, CNVKit, TIDDIT, Manta) are unaffected.

**Workaround**: None needed — the pipeline handles it gracefully. The affected sample gets CNV results from CNVKit instead. This is a Control-FREEC 11.6b internal bug, not a configuration issue.

**⚠️ TODO (next release)**: The current `errorStrategy = 'retry'` with `maxRetries = 1` will terminate the entire pipeline when the retry fails (deterministic bug, not transient). Change to `errorStrategy = 'finish'` or add a FREEC-specific ignore rule:
```groovy
// Option 1: finish all running tasks before exiting on error
errorStrategy = 'finish'

// Option 2: ignore FREEC crash specifically (exit 134 = SIGABRT)
withName: 'FREEC_GERMLINE' {
    errorStrategy = { task.exitStatus == 134 ? 'ignore' : 'retry' }
}
```

---

## Known Limitation: Control-FREEC Lacks Standard VCF Output

Control-FREEC does not produce standard VCF output natively. Its CNV calls are in custom text format (`*_CNVs`, `*_ratio.txt`, `*.bed`), which means **SnpEff functional annotation cannot be applied** to FREEC results — unlike HaplotypeCaller, TIDDIT, and CNVKit which all emit VCF.

**Impact**: FREEC CNV regions are not annotated with gene names or functional impact. Manual cross-referencing with gene coordinates is needed for biological interpretation.

**⚠️ TODO (next release)**: Investigate converting FREEC output to standard SV-VCF format (e.g., via `freec2vcf` or custom script) so that SnpEff annotation can be applied consistently across all CNV callers.

---

## ⚠️ Investigation Needed: Missed Whole-Chromosome Duplication (Ottilie Pilot)

**Date**: 2026-05-22
**Status**: Needs investigation before promoting Control-FREEC as a supported CNV tool

### Observation

In the Ottilie pilot validation (4 samples, all haploid/ploidy=1), Control-FREEC **failed to detect** the one validated whole-chromosome CNV event: **CBR110-15-R3a chr I duplication** (confirmed in Ottilie Sup Data 5 truth set).

| Tool | Chr I detection | Evidence |
|------|----------------|----------|
| **CNVKit** (.call.cns) | cn=3 (all ploidies) | **Detected** — ploidy-independent |
| **CNVKit** (VCF, --ploidy 2) | DUP, CN=3 | **Detected** — shown because cn≠ploidy |
| **Control-FREEC** (_CNVs) | Not listed | **Missed** |
| **Control-FREEC** (.bed) | chrI segments at CN≈2.4–2.8 | Signal present but not called |

CNVKit's `.call.cns` reports chr I as cn=3 regardless of the `--ploidy` parameter (1, 2, or 3), since CN integer assignment uses fixed diploid-scale thresholds. For production, CNVKit `--ploidy` is being set to 2 (default) so that the VCF export correctly emits chr I as a DUP record (cn=3 ≠ ploidy=2). Post-VCF configuration change is in progress (see `docs/variant-calling/cnvkit/cnvkit_ploidy_cn_scale.md`).

### Action Items

- [ ] Investigate why Control-FREEC missed chr I despite signal in .bed (window size? significance threshold? mosaicism?)
- [ ] Test with relaxed parameters (`breakPointThreshold`, `coefficientOfVariation`)
- [ ] Run on Tier 2 samples with known CNVs (BMS983970-2R1e, Diethylstilbestrol--15A) to assess broader sensitivity
- [ ] Compare Control-FREEC vs CNVKit sensitivity across all truth set CNV events before deciding on tool inclusion
