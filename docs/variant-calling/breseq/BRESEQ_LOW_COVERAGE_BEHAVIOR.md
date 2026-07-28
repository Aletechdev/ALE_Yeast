# ⚠️ breseq at low coverage — false-positive whole-chromosome deletions

> **Warning.** On low-coverage or heavily subsampled data, **breseq reports whole-chromosome
> deletions that are not real**. Every chromosome (plus mitochondria) can come back as a `DEL`
> spanning position 1 to the chromosome length. These are coverage artifacts, not biology.
>
> If you run breseq on a downsampled test set — or on any run whose mean depth falls below the
> thresholds in [Minimum coverage](#minimum-coverage) — **do not interpret its deletion calls.**
> The run still exercises the pipeline mechanics correctly; only the biological result is invalid.

## Why it happens

breseq detects deletions with a **missing-coverage (MC) evidence** model: contiguous stretches of
zero mapped coverage are called as deleted.

1. **At low depth most positions have zero coverage.** A few thousand short reads spread over a
   ~12 Mbp yeast genome leave the large majority of bases with no read at all.
2. **breseq reads contiguous zero-coverage as a deletion.** With no reads anywhere on a
   chromosome, the deletion call spans the whole chromosome:
   ```
   DEL  1  19  chr1  1  241271  gene_name=TDA8–YAR075W_CDS
   ```
   i.e. "chr1 is deleted from position 1 for 241,271 bp" — the entire chromosome.
3. **`UN` (unassigned) evidence piles up** for regions with ambiguous or missing coverage that
   couldn't be resolved into a specific call.
4. **Population mode masks the symptom.** Samples run with `-p`
   (`meta.clonal_or_population == 'population'`) can show **zero** `UN` entries at the same depth —
   the polymorphism-aware model uses different missing-coverage thresholds. Absence of `UN` is
   therefore **not** evidence that the deletions are real.

## Downstream impact on the VCF

`gdtools CONVERT` faithfully translates a whole-chromosome `DEL` into a VCF record with:

- **REF** = the entire chromosome sequence (hundreds of thousands of bases)
- **ALT** = a single base

A handful of such records produce a multi-megabyte uncompressed VCF that standard VCF tools choke
on. At insufficient coverage the breseq VCF is effectively unusable.

## Minimum coverage

| Analysis type | Minimum | Recommended |
|---------------|---------|-------------|
| Clonal (consensus) | **20–30×** | 50–100× |
| Population (`-p`) | **50×** | 100–200× |

At adequate coverage breseq reliably detects SNPs, small INDELs (< ~50 bp), IS-element insertions
(`MOB`), *real* large deletions (with a clear coverage drop-off against surrounding depth), gene
amplifications (`AMP`), and new junctions (`JC`).

## Implications for testing

A subsampled dataset validates that the **pipeline mechanics** work — lane grouping, process
execution, clonal-vs-population `-p` selection, output publishing, MultiQC integration — while the
biological calls are artifacts. Validate mutation-detection *accuracy* only against full-depth data.

This matters for the yAMP test data specifically: the `ottilie_test` profile uses a **chromosome
subset** (chr I/IV/VII/XV) of full-depth CRAMs, so depth on the retained chromosomes is preserved —
but breseq is **not** in the `ottilie_test` tool set (it is Tier 2 and needs a GenBank reference).
Any breseq test built on a *read*-subsampled dataset will hit the behavior above.

> **Historical note.** This page was originally written from a retired 5-sample CEN.PK test set
> subsampled to 2,000 reads/lane (~1.1–1.6× mean coverage), where breseq called 16–17
> whole-chromosome deletions and 0 SNPs per sample. Those exact numbers will **not** reproduce on
> the current test data — the durable finding is the failure mode, not the counts.

## Related

- breseq module: `modules/local/breseq/main.nf`
- GD→VCF conversion: `modules/local/gdtools/convert/main.nf`
- Subworkflow: `subworkflows/local/fastq_variant_calling_breseq/`
- Publishing config: `conf/modules/breseq.config`
- Design/integration write-up: [`BRESEQ_INTEGRATION_PLAN.md`](BRESEQ_INTEGRATION_PLAN.md)
