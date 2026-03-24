# SNV Calling Benchmarking Summary

## Executive Summary

Both variant calling tools in the pipeline — **breseq** and **GATK HaplotypeCaller** (joint germline mode) — achieve **100% recall** on a curated set of 24 SNVs across 5 ALE lineages, spanning allele frequencies from 17% to 100%. Neither tool produced false positives on 3 negative-control loci. Observed allele frequencies closely match expected values from spore-seq segregation (Pearson r = 1.000 for breseq, r = 0.997 for HaplotypeCaller). The pipeline is reliable for detecting SNVs in yeast ALE experiments.

Beyond the curated truth set, the two tools show low position-level concordance genome-wide (~10% of breseq mutations in population samples exactly match HaplotypeCaller calls, ~25% within ±50 bp), reflecting fundamentally different alignment strategies (bowtie2 vs BWA-MEM) and variant calling models. Cross-validating mutations across both methods is essential for high-confidence calls, and investing in a starting-strain reference genome would further reduce alignment-driven discordance.

## Recall by Frequency Bin

| Frequency Bin | N (truth) | breseq TP | breseq Recall | HC TP | HC Recall |
|---------------|-----------|-----------|---------------|-------|-----------|
| Fixed (>=90%) | 7 | 7 | 100.0% | 7 | 100.0% |
| High (60-89%) | 12 | 12 | 100.0% | 12 | 100.0% |
| Medium (35-59%) | 18 | 18 | 100.0% | 18 | 100.0% |
| Low (1-34%) | 8 | 8 | 100.0% | 8 | 100.0% |
| TOTAL (present) | 45 | 45 | 100.0% | 45 | 100.0% |
| Absent (0%) | 3 | 0 | 0/3 FP | 0 | 0/3 FP |

Lowest-frequency variant detected by both tools: **MNR2** (chr11:340306) at **17.0% expected AF** in sample A6-F6-I3-R1.

## Truth Set

- **Source**: Table S8 — manually curated SNVs from spore-seq segregation analysis (adipic acid samples from https://www.sciencedirect.com/science/article/pii/S1096717619302824?via%3Dihub)
- **24 SNVs** with defined ref/alt across 5 ALE lineages (A1.6, A3.3, A4.5, A5.4, A6.6)
- **21 genes** affected: ARO80, COG3, COS3, DIG1, ESL2, FRK1, GCD6, GDH2, GPI2, HRD1, HRD3, IZH3, LEU3, MNR2, NHA1, REV1, RXT3, SET2, SPC25, WAR1, YFH1
- Each SNV tested in 2 spore-seq strains (tolerant or sensitive to adipic acid) → **48 variant×sample entries**
  - 45 expected-present (AF 17–100%)
  - 3 expected-absent (negative controls, expected AF = 0%)
- **Caveat:** 2 repeat-expansion mutations excluded (no simple ref/alt for VCF matching), synthetic data required for more in-depth analysis of structural mutations recalling.

## Specificity (False Positive Check)

- **3 negative-control entries** (variant expected in one spore segregant but absent in the sibling)
- **breseq false positives: 0/3**
- **HaplotypeCaller false positives: 0/3**

**Caveat**: This tests specificity only at known loci (3 positions). It does not measure the genome-wide false positive rate, which would require synthetic spike-in or orthogonal validation.

## Allele Frequency Accuracy

Comparison of observed AF (from VCF) vs expected AF (from spore-seq segregation):

| Metric | breseq | HaplotypeCaller |
|--------|--------|----------------|
| Pearson r (vs expected) | 1.000 | 0.997 |
| Mean absolute error | 0.005 | 0.013 |
| Pearson r (breseq vs HC) | 0.997 | 0.997 |

Both tools produce allele frequency estimates that closely track the expected values and agree with each other.

## Tool Complementarity

### Variant Counts by Sample Type

| Sample Type | N samples | breseq (avg) | HC PASS AF>=90% (avg) | HC PASS AF>=5% (avg) |
|-------------|-----------|-------------|----------------------|---------------------|
| Clonal (I1) | 7 | 20 | **46** | 99 |
| Population (I2/I3) | 10 | 854 | 33 | **305** |

**Why counts differ**:

- **Clonal samples (breseq=20)**: breseq reports only consensus mutations (AF rounded to 1 in VCF, actual AD/DP typically 79–91%). HC at AF>=90% finds ~2x more (46) due to different aligner and algorithm (BWA-MEM + joint genotyping vs breseq's bowtie2 + read-evidence model).
- **Population samples (breseq=854)**: breseq `-p` mode reports variants down to ~5% AF, making it ~2.8x more sensitive than HC at AF>=5% (305).

### Position-Level Concordance

Exact match requires identical chromosome, position, and alt allele. Proximity (±50bp) considers positions within 50bp on the same chromosome as matching, accounting for different variant representations (e.g., left- vs right-aligned indels).

**Clonal samples** (avg across 7 samples; breseq consensus vs HC PASS AF>=90%):

| Metric | Exact match | Proximity (±50bp) |
|--------|-------------|-------------------|
| Concordant (both tools) | 6 | 13 |
| breseq-only | 14 | 7 |
| HC-only | 40 | 33 |

**Population samples** (avg across 10 samples; breseq `-p` vs HC PASS AF>=5%):

| Metric | Exact match | Proximity (±50bp) |
|--------|-------------|-------------------|
| Concordant (both tools) | 88 | 212 (breseq→HC) / 147 (HC→breseq) |
| breseq-only | 757 | 641 |
| HC-only | 218 | 159 |

Proximity matching roughly doubles concordance compared to exact matching, indicating many shared calls differ only in variant representation. Low overall overlap is expected — the tools use fundamentally different algorithms (breseq: read-evidence + polymorphism model; HC: haplotype assembly + joint genotyping) and have different sensitivity profiles at low allele frequencies. Critically, the two tools also use **different read aligners**: breseq performs its own internal alignment (bowtie2), while HaplotypeCaller operates on BWA-MEM alignments produced by the Sarek pipeline. This means read depth and allele counts at the same genomic position can differ substantially between tools, due to differences in alignment algorithms, mapping quality assignment, and potential divergence between the reference genome and the actual ancestral strain used in the ALE experiment.

**Example — chr12:431553 in A0-F0-I1-R1 (clonal)**: breseq called A→T with AD=392, DP=494 (AD/DP=79.4%), but the BWA-MEM alignment (used by HC) shows only 115 ALT reads out of 3,422 total (3.4%). HC correctly did not call this position. The discrepancy arises because breseq performs its own internal read alignment (bowtie2), which can produce substantially different depth and allele counts at the same genomic position.

Cross-validating mutations across independent methods is therefore essential for high-confidence ALE variant calls. Investing in a high-quality reference genome for the actual starting strain (rather than relying on a published assembly that may diverge at strain-specific loci) would further reduce alignment-driven discordance and improve concordance between tools.

### Resource Usage

| Tool | Avg Runtime/Sample | Peak RAM |
|------|--------------------|----------|
| breseq | 1.7h | 4.4 GB |
| HaplotypeCaller | 25.8m | 7.3 GB |

## Limitations & Caveats

1. **SNV-only benchmark**: Repeat expansions (2 mutations) and structural variants (chr2 duplications/triplications) are excluded from this analysis
2. **Small truth set**: 24 unique loci across 5 lineages — representative but not exhaustive
3. **No genome-wide FP measurement**: Only 3 negative-control loci tested; genome-wide specificity would require spike-in or orthogonal sequencing
4. **Ploidy handling**: HC was run with ploidy=10 for population samples only (clonal samples use default ploidy=2); genotype fields (GT) require AD-based allele frequency interpretation rather than standard GT parsing
5. **Population vs clonal mode**: breseq variant counts depend critically on whether `-p` flag is set (controlled by `clonal_or_population` column in samplesheet)
