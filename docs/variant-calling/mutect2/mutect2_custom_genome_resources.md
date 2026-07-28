# Mutect2 on a custom genome — missing population resources

**Tier-2 (functional, not release-validated for ALE).** Mutect2 runs on the custom yeast genome
**without** its two optional population resources: `--germline-resource` and `--panel-of-normals`.
Neither exists for a custom, non-human genome, and neither is needed for the ALE use case. This is
expected, not a defect.

## `--germline-resource`

- **Purpose:** filter out common population variants (e.g. gnomAD SNPs) that are germline, not somatic.
- **For yeast ALE:** *all* mutations are of interest — there is no population database (no gnomAD
  equivalent), and evolved variants are exactly what we want to keep.
- **Decision:** omit entirely. This also omits `--af-of-alleles-not-in-resource` (its companion).

## `--panel-of-normals` (PoN)

- **Purpose:** flag systematic sequencing/library-prep artifacts seen across a panel of normal samples.
- **For yeast ALE:** *could* be useful if built from multiple ancestral-strain replicates, but the
  effort isn't justified for current experiments.
- **Decision:** omit.

## Effect

Mutect2 still runs and calls, just without population-based pre-filtering. Downstream, the ALE-specific
AF-based filters do the noise reduction — see [`../tier2_af_filters.md`](../tier2_af_filters.md).

## References

- Mutect2: https://gatk.broadinstitute.org/hc/en-us/articles/5358911630107-Mutect2
- CreateSomaticPanelOfNormals: https://gatk.broadinstitute.org/hc/en-us/articles/5358921041947-CreateSomaticPanelOfNormals-BETA-
