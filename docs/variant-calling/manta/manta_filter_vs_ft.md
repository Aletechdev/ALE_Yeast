# Manta: FILTER vs FORMAT/FT in Single-Sample Mode

**Date**: 2026-06-17

## Summary

Manta has two independent filter mechanisms:

- **FILTER** (site-level): quality flags evaluated on the locus (e.g., depth, mapping quality).
- **FORMAT/FT** (per-sample): sample-specific genotype quality checks (e.g., MinGQ, HomRef).

Even in single-sample mode, these can have different values.

## Observed Behavior (Ottilie Pilot, 4 Samples)

```
CHROM   POS       SVTYPE  FILTER      FT
IV      465921    BND     MaxDepth    PASS
XI      653082    BND     MaxDepth    PASS
XII     116434    BND     MaxDepth    PASS
XII     1065062   DEL     MaxDepth    PASS
XIV     765379    BND     MaxDepth    PASS
XV      159560    BND     MaxDepth    PASS
XV      349681    BND     MaxDepth    PASS
```

These variants fail the site-level `MaxDepth` filter ("Depth is greater than
3x the median chromosome depth near one or both variant breakends") but pass
all sample-level checks (FT=PASS).

## FT Is Always PASS in diploid_sv Output

Across all 4 Ottilie pilot samples, **every** record in the
`*.manta.diploid_sv.vcf.gz` output has `FT=PASS`:

| Sample            | Records | FT=PASS |
|-------------------|---------|---------|
| CBR110-15-R3a     | 22      | 22      |
| Carmaphycin-R9-2  | 35      | 35      |
| Doxorubicin16-R2b | 21      | 21      |
| NODRUG-GM2        | 8       | 8       |

This is because Manta removes records that fail sample-level filters
(HomRef, MinGQ) before writing the diploid_sv VCF. The `SampleFT` site-level
filter ("No sample passes all the sample-level filters") never appears in
FILTER either — confirming that all retained records have FT=PASS.

## Manta FILTER Definitions

From the VCF header:

| Filter         | Description |
|----------------|-------------|
| `MaxDepth`     | Depth > 3x median chromosome depth near breakends |
| `MaxMQ0Frac`   | Fraction of MAPQ0 reads > 0.4 (variants < 1000 bp) |
| `NoPairSupport`| No paired reads support ALT (large variants only) |
| `MinQUAL`      | QUAL < 20 |
| `Ploidy`       | Genotypes of overlapping DEL/DUP inconsistent with diploid |
| `SampleFT`     | No sample passes FORMAT/FT filters |
| `MinGQ`        | GQ < 15 (applied at sample level → FORMAT/FT) |
| `HomRef`       | Homozygous reference (applied at sample level → FORMAT/FT) |

## Decision: Do Not Show FT in IGV Reports

Since FT=PASS for all records in single-sample diploid_sv output, adding it
to the igv-report table would add a column of identical "PASS" values with no
informational value.

The existing `VCF_FILTER` column (promoted from the site-level FILTER via
`bcftools annotate`) already shows the meaningful filter status (PASS,
MaxDepth, etc.).

If Manta is ever run in multi-sample mode, FT could diverge per sample and
would be worth revisiting.
