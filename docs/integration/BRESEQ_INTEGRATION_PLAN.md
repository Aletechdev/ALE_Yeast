# Plan: Add breseq 0.39.0 Subworkflow to Sarek Pipeline

## Context

breseq is the standard tool for ALE (Adaptive Laboratory Evolution) mutation detection. It uses its own internal aligner (bowtie2-based) and requires a GenBank reference (not FASTA). Currently breseq is only used outside the pipeline for QC comparisons. Adding it as a parallel Nextflow process after trimming means it runs alongside the existing BWA/GATK pathway, giving integrated variant calling from both approaches in a single pipeline run.

**Container verified**: `quay.io/biocontainers/breseq:0.39.0--hdcf5f25_2` (breseq + gdtools included, no bgzip/tabix)

## Architecture

```
Input FASTQs → FASTP (trimming)
                  ├──→ BWA alignment → MarkDup → HaplotypeCaller / FreeBayes / Mutect2 → VCF
                  └──→ BRESEQ (parallel) → GenomeDiff (.gd) → gdtools CONVERT → VCF
```

breseq branches from `FASTP.out.reads` (pre-split, per-lane). A subworkflow groups lanes per sample, then runs breseq. Population samples (`meta.clonal_or_population == 'population'`) automatically get the `-p` (polymorphism) flag.

## Files to Create

### 1. `modules/local/breseq/main.nf` — BRESEQ process
- Container: `quay.io/biocontainers/breseq:0.39.0--hdcf5f25_2`
- Conda: `bioconda::breseq=0.39.0`
- Input: `tuple val(meta), path(reads)` + `path(genbank)`
- Auto `-p` flag when `meta.clonal_or_population == 'population'`
- `-j ${task.cpus}` for parallelism
- Output: `output/output.gd`, `data/annotated.gd`, `output/index.html`, `output/summary.json`

### 2. `modules/local/gdtools/convert/main.nf` — GD→VCF conversion
- Same container as BRESEQ (gdtools is bundled)
- Input: annotated.gd + genbank reference
- Output: `*.breseq.vcf` (uncompressed — no bgzip in breseq container)

### 3. `subworkflows/local/fastq_variant_calling_breseq/main.nf` — Orchestration
Steps:
1. **Group lanes per sample** — `groupTuple()` on `(patient, sample)` to collect all lane FASTQs
2. **BRESEQ** — Run per sample (all lanes as input)
3. **GDTOOLS_CONVERT** — Convert annotated.gd → VCF
4. **TABIX_BGZIP** (nf-core module) — bgzip the VCF
5. **TABIX_TABIX** (nf-core module) — Index the .vcf.gz

Lane grouping follows the existing pattern at `sarek/main.nf:289-296`:
```groovy
reads.map { meta, reads -> [ meta.subMap('patient', 'sample', 'sex', 'status', 'ploidy', 'clonal_or_population'), reads ] }
    .groupTuple()
    .map { meta, reads_nested -> [ meta + [id: meta.sample, variantcaller: 'breseq'], reads_nested.flatten() ] }
```

### 4. `conf/modules/breseq.config` — Publishing config
- BRESEQ output → `${params.outdir}/variant_calling/breseq/${meta.id}/`
- Publish: output.gd, annotated.gd, index.html, summary.json, .breseq.vcf.gz, .breseq.vcf.gz.tbi

## Files to Modify

### 5. `nextflow.config` — Add parameters
```groovy
genbank       = null   // Reference for breseq in GenBank, GFF3, or FASTA format
breseq_args   = ''     // Additional breseq arguments
```
Add `includeConfig 'conf/modules/breseq.config'`

### 6. `workflows/sarek/main.nf` — Integration point

**Add include** (around line 91):
```groovy
include { FASTQ_VARIANT_CALLING_BRESEQ } from '../../subworkflows/local/fastq_variant_calling_breseq/main'
```

**Add genbank channel** (inside `main:`, around line 161):
```groovy
genbank = params.genbank ? Channel.fromPath(params.genbank, checkIfExists: true).collect() : Channel.empty()
```

**Add breseq branch after FASTP** (after line 283, before "STEP 1: MAPPING"):
```groovy
if (params.tools && params.tools.split(',').contains('breseq') && params.genbank) {
    def reads_for_breseq = (params.trim_fastq || params.split_fastq > 0)
        ? FASTP.out.reads : reads_for_fastp

    FASTQ_VARIANT_CALLING_BRESEQ(reads_for_breseq, genbank)
    versions = versions.mix(FASTQ_VARIANT_CALLING_BRESEQ.out.versions)
}
```

**Warn if breseq enabled without genbank**:
```groovy
if (params.tools && params.tools.split(',').contains('breseq') && !params.genbank) {
    log.warn "breseq enabled in --tools but --genbank not provided. breseq will be skipped."
}
```

### 7. `conf/modules/modules.config` — Skip VCFtools for breseq
Add `(meta.variantcaller != 'breseq')` to the VCFtools `ext.when` condition (breseq VCF lacks FORMAT/GT field).

## Implementation Order

1. Create `modules/local/breseq/main.nf`
2. Create `modules/local/gdtools/convert/main.nf`
3. Create `conf/modules/breseq.config`
4. Add config include + params to `nextflow.config`
5. Create `subworkflows/local/fastq_variant_calling_breseq/main.nf`
6. Integrate into `workflows/sarek/main.nf`
7. Update VCFtools skip in `conf/modules/modules.config`
8. Update `bin/test_nf.sh` to add `breseq` to `--tools` and add `--genbank`

## Key Decisions

- **No annotation integration**: breseq VCF will NOT be fed into `vcf_to_annotate` for SnpEff (breseq has its own GenBank-based annotation in the .gd file). Keep it separate.
- **Resource label**: `process_medium` for BRESEQ (yeast genome ~12MB is small). Can tune later.
- **TABIX modules**: Reuse existing nf-core `tabix/bgzip` and `tabix/tabix` modules (already in pipeline) for compressing+indexing since breseq container lacks bgzip.

## Verification

1. Add `breseq` to `--tools` and `--genbank` to `bin/test_nf.sh`
2. Run `bash bin/test_nf.sh` with the test dataset
3. Check output: `output_test_001/variant_calling/breseq/A1-F6-I1-R1/` should contain output.gd, annotated.gd, index.html, .breseq.vcf.gz
4. Verify population sample (A1-F6-I2-R1) ran with `-p` flag in `.nextflow.log`
5. Confirm clonal sample ran without `-p` flag
