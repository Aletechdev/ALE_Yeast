# breseq Behavior at Low Coverage (~1x)

## Observation

When running breseq on subsampled test data (~2,000 reads per lane, ~1x average coverage), breseq reports **whole-chromosome deletions** for all 16 yeast chromosomes plus mitochondria. These are artifacts of insufficient coverage, not real biological events.

## Test Data Summary

| Sample | Avg Coverage | Total Reads | Aligned % | DELs | SNPs | UN (Unassigned) |
|--------|-------------|-------------|-----------|------|------|-----------------|
| A0-F0-I1-R1 | 1.13x | 15,982 | 85.5% | 16 | 0 | 2,133 |
| A1-F6-I1-R1 | 1.15x | 15,983 | 85.9% | 17 | 0 | 1,186 |
| A6-F6-I1-R1 | 1.15x | 15,979 | 91.3% | 16 | 0 | 1,231 |
| A1-F6-I2-R1 | 1.62x | 15,974 | 92.7% | 17 | 0 | 0 |
| A1-F6-I3-R1 | 1.60x | 15,986 | 92.0% | 17 | 0 | 0 |

Test data: 2,000 reads/lane subsampled from full-depth FASTQ files (~12 Mbp yeast genome).

## Why This Happens

breseq uses a **missing coverage (MC) evidence** model to detect deletions. At ~1x coverage:

1. **Most positions have 0 coverage** — With ~16,000 reads of ~150 bp across a 12 Mbp genome, only ~0.2 Mbp total bases are covered. Most of the genome has zero reads.

2. **breseq interprets contiguous zero-coverage as deletions** — When large regions lack any mapped reads, breseq's deletion detection algorithm calls them as DEL mutations spanning from position 1 to the chromosome length.

3. **The "deletions" span entire chromosomes** — Example from `annotated.gd`:
   ```
   DEL  1  19  chr1  1  241271  gene_name=TDA8–YAR075W_CDS
   ```
   This says chr1 is deleted from position 1 for 241,271 bp — the entire chromosome length.

4. **UN (Unassigned) evidence** — breseq also generates many UN entries, representing regions with ambiguous or missing coverage that couldn't be resolved into specific mutation calls.

## Impact on VCF Output

`gdtools CONVERT` translates these whole-chromosome DELs into VCF records where:
- **REF** = the entire chromosome sequence (hundreds of thousands of bases)
- **ALT** = a single base

This produces a ~12 MB uncompressed VCF with only 17 records — bloated and unusable by standard VCF tools. The VCF output is essentially meaningless at this coverage level.

## Population Mode Differences

The population samples (A1-F6-I2-R1, A1-F6-I3-R1) show **0 UN entries** despite similar coverage (~1.6x). This is because population mode (`-p` flag) uses a polymorphism-aware model with different thresholds for calling missing coverage as unassigned.

## Minimum Coverage Requirements

For meaningful breseq results:

| Analysis Type | Minimum Coverage | Recommended |
|--------------|-----------------|-------------|
| Clonal (consensus) | **20-30x** | 50-100x |
| Population (`-p`) | **50x** | 100-200x |

At adequate coverage, breseq reliably detects:
- **SNPs** — Single nucleotide polymorphisms
- **Small INDELs** — Insertions and deletions (typically < 50 bp)
- **IS element insertions** (MOB) — Mobile element movements
- **Large deletions** — Real deletions with clear coverage drop-offs
- **Gene amplifications** (AMP) — Copy number increases
- **New junctions** (JC) — Evidence of structural rearrangements

## Implications for Testing

The subsampled test data validates that the **pipeline mechanics work correctly** (lane grouping, process execution, output publishing, MultiQC integration) even though the biological results are artifacts. For validating mutation detection accuracy, use full-depth sequencing data.

## Related Files

- Test script: `bin/test_nf.sh`
- Subsample script: `bin/prepare_input/run_subset_fastq.sh` (2,000 reads/lane, seed=18)
- breseq module: `nf-core-sarek_3.5.1/3_5_1/modules/local/breseq/main.nf`
- Example output: `output_test_001/variant_calling/breseq/*/output/`
