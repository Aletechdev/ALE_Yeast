# TIDDIT Ploidy Behavior (v3.6.1)

## Summary

TIDDIT's `-n` flag sets the expected organism ploidy (default=2). It affects both
coverage normalization and SV genotyping thresholds. The VCF GT field always uses
diploid notation (`0/1`, `1/1`) regardless of ploidy setting.

## Pipeline Configuration

In `conf/modules/tiddit.config`:
```groovy
ext.args = { (bwa_index ? '' : '--skip_assembly') + (meta.ploidy ? " -n ${meta.ploidy}" : '') }
```

For our Ottilie pilot (ploidy=1), this produces:
```
tiddit --sv --skip_assembly -n 1 --threads 4 --bam sample.cram --ref ref.fa -o sample.tiddit
```

## How `-n` is Used (Source Code Analysis)

Verified from TIDDIT 3.6.1 Cython source (`tiddit_coverage_analysis.pyx`, `tiddit_variant.pyx`).

### 1. Coverage Normalization → `ploidies.tab`

**File**: `tiddit_coverage_analysis.pyx` — `determine_ploidy()`

```python
library["contig_ploidy_{}".format(chromosome)] = \
    int(round(ploidy * avg_coverage_contig / library["avg_coverage"]))
```

Each chromosome's ploidy is computed as:
```
contig_ploidy = round(n * median_coverage_chr / median_coverage_genome)
```

With `-n 1`, a chromosome at ~1x genome-average coverage → `contig_ploidy = 1`.
This is written to `{prefix}.ploidies.tab`.

**Example output** (Carmaphycin-R9-2, haploid yeast):
```
Chromosome  Ploidy              Ploidy_rounded  Mean_coverage
I           1.0101809997124158  1               160.74
II          0.9992458510554746  1               159.00
...
Mito        2.4371543560858466  2               387.80
```

### 2. SV Genotyping Thresholds

**File**: `tiddit_variant.pyx` — `define_variant()`

The per-chromosome ploidy (`library["contig_ploidy_<chr>"]`) influences GT assignment:

| SV Type | GT = `1/1` when | GT = `0/1` when |
|---------|----------------|-----------------|
| **DUP** | `cn >= 2 * contig_ploidy` | Otherwise |
| **DEL** | `cn == 0` | Otherwise |
| **BND/INV** | Ref reads < 10% of supporting reads | Otherwise |

**Impact of `-n 1` on DUP calls:**
- Haploid (`-n 1`): `1/1` when cn ≥ 2 (i.e., duplication detected)
- Diploid (`-n 2`): `1/1` when cn ≥ 4 (much higher threshold)

For BND and INV, genotyping is based on read evidence ratios, not ploidy.

### 3. `--force_ploidy` Flag

By default, TIDDIT normalizes coverage per chromosome independently (so e.g.
mitochondrial DNA gets its own ploidy estimate). The `--force_ploidy` flag
skips this normalization and applies `-n` uniformly across all chromosomes.

Our pipeline does **not** use `--force_ploidy`, allowing per-chromosome estimation.

## VCF GT Format

TIDDIT always outputs diploid-style GT notation regardless of `-n`:
- `0/1` — SV detected, lower confidence or partial evidence
- `1/1` — SV detected, high confidence / complete
- `./.` — insufficient evidence

This is standard SV-VCF convention. For haploid organisms, interpret as:
- `1/1` → SV is present (the single copy is affected)
- `0/1` → SV detected but with ambiguous/lower evidence

## How ploidies.tab Feeds into the VCF

The per-chromosome ploidy estimates from `ploidies.tab` are **not** written into
the VCF as annotations. They influence the VCF indirectly through two mechanisms:

### 1. `Ploidy` FILTER

```
##FILTER=<ID=Ploidy,Description="Intrachromosomal variant on a chromosome having 0 ploidy">
```

Chromosomes with `Ploidy_rounded = 0` (e.g. negligible coverage) cause all their
intrachromosomal SVs to be flagged. With `-n 1` and normal coverage, all
chromosomes get `Ploidy_rounded = 1`, so this filter is not triggered.

### 2. `UnexpectedCoverage` FILTER

The `--max_coverage` filter (default 4x) compares local coverage against the
chromosome average. Since `-n` changes how per-chromosome average coverage is
calculated, it indirectly shifts which variants get flagged.

### 3. GT thresholds (DUP/DEL)

As described above, `contig_ploidy` from `ploidies.tab` sets the DUP homozygous
threshold (`cn >= 2 * contig_ploidy`).

### Verification (CBR110-15-R3a, Ottilie pilot)

All chromosomes at `Ploidy_rounded = 1` (including Mito) → 0 variants with
`Ploidy` filter. Filter distribution across 170 variants:

| Filter | Count |
|--------|-------|
| UnexpectedCoverage | 83 |
| BelowExpectedLinks | 57 |
| PASS | 30 |

## Comparison with Other SV Tools

| Tool | `-n` / ploidy flag | Affects GT? | GT format |
|------|-------------------|-------------|-----------|
| TIDDIT | `-n` (default=2) | Yes (DUP/DEL thresholds) | Always diploid |
| Manta | None | N/A | Always diploid |
| CNVKit | `--ploidy` removed (see [cnvkit_ploidy_behavior.md](../cnvkit/cnvkit_ploidy_behavior.md)) | N/A | Always diploid |

## References

- TIDDIT source: https://github.com/SciLifeLab/TIDDIT (tag TIDDIT-3.6.1)
- Docker image: `quay.io/biocontainers/tiddit:3.6.1--py38h24c8ff8_0`
