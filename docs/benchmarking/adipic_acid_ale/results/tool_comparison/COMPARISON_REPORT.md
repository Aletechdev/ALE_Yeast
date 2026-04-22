# breseq vs HaplotypeCaller Comparison Report

## Key Differences

| Aspect | breseq | HaplotypeCaller |
|--------|--------|----------------|
| Mode | Per-sample; clonal (default) or population (`-p`) | Joint calling across all samples; variant quality scored at cohort level (INFO fields aggregated across all samples) |
| Min AF detected | 5% (default `--polymorphism-frequency-cutoff 0.05` in `-p` mode) | ~10% theoretical floor (1 copy / ploidy=10); lower possible with high depth |
| Output | VCF + GenomeDiff + HTML evidence | Multi-sample VCF |
| Annotation | Built-in (gene, AA change) | Requires SnpEff |
| Avg runtime | 1.7h/sample | 25.8m/sample |
| Peak RAM | 4.4 GB | 7.3 GB |

## Variant Counts

| Sample | Type | Comment | breseq | HC PASS AF>=5% | HC PASS AF>=10% | HC PASS AF>=90% |
|--------|------|---------|--------|----------------|----------------|----------------|
| A0-F0-I1-R1 | clonal |  | 11 | 91 | 91 | 40* |
| A0-F0-I2-R1 | clonal |  | 8 | 88 | 88 | 42* |
| A1-F6-I1-R1 | clonal |  | 23 | 106 | 106 | 44* |
| A1-F6-I2-R1 | population | 10 tolerant spores | 823 | 349* | 283 | 35 |
| A1-F6-I3-R1 | population | 10 sensitive spores | 838 | 295* | 255 | 36 |
| A3-F3-I1-R1 | clonal |  | 20 | 99 | 99 | 47* |
| A3-F3-I2-R1 | population | 10 tolerant spores | 834 | 311* | 262 | 22 |
| A3-F3-I3-R1 | population | 10 sensitive spores | 865 | 322* | 268 | 25 |
| A4-F5-I1-R1 | clonal |  | 23 | 97 | 97 | 43* |
| A4-F5-I2-R1 | population | 10 tolerant spores | 860 | 300* | 266 | 36 |
| A4-F5-I3-R1 | population | 10 sensitive spores | 885 | 297* | 253 | 37 |
| A5-F4-I1-R1 | clonal |  | 24 | 113 | 113 | 53* |
| A5-F4-I2-R1 | population | 10 tolerant spores | 822 | 287* | 195 | 38 |
| A5-F4-I3-R1 | population | 10 sensitive spores | 911 | 299* | 258 | 33 |
| A6-F6-I1-R1 | clonal |  | 28 | 101 | 101 | 55* |
| A6-F6-I2-R1 | population | 10 tolerant spores | 822 | 285* | 254 | 31 |
| A6-F6-I3-R1 | population | 10 sensitive spores | 876 | 309* | 269 | 35 |

\* For clonal samples, HC PASS AF>=90% is used for concordance comparison with breseq. For population samples, HC PASS AF>=5% is used for concordance comparison with breseq.

## Concordance: breseq vs HC

Clonal samples use HC PASS AF>=90%; population samples use HC PASS AF>=5%.

| Sample | Type | HC AF threshold | breseq | HC | Both | breseq-only | HC-only |
|--------|------|-----------------|--------|-----|------|-------------|--------|
| A0-F0-I1-R1 | clonal | >=90% | 11 | 40 | 0 | 11 | 40 |
| A0-F0-I2-R1 | clonal | >=90% | 8 | 42 | 0 | 8 | 42 |
| A1-F6-I1-R1 | clonal | >=90% | 23 | 44 | 4 | 19 | 40 |
| A1-F6-I2-R1 | population | >=5% | 821 | 349 | 76 | 745 | 273 |
| A1-F6-I3-R1 | population | >=5% | 824 | 295 | 94 | 730 | 201 |
| A3-F3-I1-R1 | clonal | >=90% | 20 | 47 | 8 | 12 | 39 |
| A3-F3-I2-R1 | population | >=5% | 828 | 311 | 102 | 726 | 209 |
| A3-F3-I3-R1 | population | >=5% | 854 | 322 | 95 | 759 | 227 |
| A4-F5-I1-R1 | clonal | >=90% | 23 | 43 | 9 | 14 | 34 |
| A4-F5-I2-R1 | population | >=5% | 853 | 300 | 83 | 770 | 217 |
| A4-F5-I3-R1 | population | >=5% | 876 | 297 | 88 | 788 | 209 |
| A5-F4-I1-R1 | clonal | >=90% | 24 | 53 | 10 | 14 | 43 |
| A5-F4-I2-R1 | population | >=5% | 809 | 287 | 64 | 745 | 223 |
| A5-F4-I3-R1 | population | >=5% | 906 | 299 | 97 | 809 | 202 |
| A6-F6-I1-R1 | clonal | >=90% | 28 | 55 | 11 | 17 | 44 |
| A6-F6-I2-R1 | population | >=5% | 809 | 285 | 83 | 726 | 202 |
| A6-F6-I3-R1 | population | >=5% | 867 | 309 | 94 | 773 | 215 |

## Proximity Concordance (±50bp)

Positions within 50bp on the same chromosome are considered matching (accounts for different variant representations).
Clonal samples use HC PASS AF>=90%; population samples use HC PASS AF>=5%.

| Sample | Type | HC AF threshold | breseq | HC | breseq near HC | breseq-only | HC near breseq | HC-only |
|--------|------|-----------------|--------|-----|---------------|-------------|---------------|--------|
| A0-F0-I1-R1 | clonal | >=90% | 11 | 40 | 4 | 7 | 4 | 36 |
| A0-F0-I2-R1 | clonal | >=90% | 8 | 42 | 5 | 3 | 5 | 37 |
| A1-F6-I1-R1 | clonal | >=90% | 23 | 44 | 14 | 9 | 14 | 30 |
| A1-F6-I2-R1 | population | >=5% | 823 | 349 | 203 | 620 | 155 | 194 |
| A1-F6-I3-R1 | population | >=5% | 838 | 295 | 222 | 616 | 148 | 147 |
| A3-F3-I1-R1 | clonal | >=90% | 20 | 47 | 14 | 6 | 14 | 33 |
| A3-F3-I2-R1 | population | >=5% | 834 | 311 | 254 | 580 | 164 | 147 |
| A3-F3-I3-R1 | population | >=5% | 865 | 322 | 231 | 634 | 155 | 167 |
| A4-F5-I1-R1 | clonal | >=90% | 23 | 43 | 12 | 11 | 12 | 31 |
| A4-F5-I2-R1 | population | >=5% | 860 | 300 | 210 | 650 | 145 | 155 |
| A4-F5-I3-R1 | population | >=5% | 885 | 297 | 213 | 672 | 156 | 141 |
| A5-F4-I1-R1 | clonal | >=90% | 24 | 53 | 20 | 4 | 20 | 33 |
| A5-F4-I2-R1 | population | >=5% | 822 | 287 | 163 | 659 | 108 | 179 |
| A5-F4-I3-R1 | population | >=5% | 911 | 299 | 204 | 707 | 145 | 154 |
| A6-F6-I1-R1 | clonal | >=90% | 28 | 55 | 21 | 7 | 21 | 34 |
| A6-F6-I2-R1 | population | >=5% | 822 | 285 | 195 | 627 | 138 | 147 |
| A6-F6-I3-R1 | population | >=5% | 876 | 309 | 227 | 649 | 153 | 156 |

## Notes

- breseq clonal mode reports only consensus mutations; the AF field in its VCF is rounded to 1 (100%), but actual read support by AD/DP is typically 79–91% due to reference-spanning reads and alignment ambiguity at indel sites
- breseq population mode (`-p`) reports polymorphisms down to 5% AF (breseq default `--polymorphism-frequency-cutoff 0.05`)
- HC variant counts use AD-based AF filtering (bcftools GT filters broken for polyploid)
- HC joint VCF: `HaplotypeCaller_joint_calling_soft_filtered.vcf.gz` (FILTER populated)
- Exact concordance based on chrom+pos+alt match
- Proximity concordance based on chrom+pos within ±50bp (alt not compared)
