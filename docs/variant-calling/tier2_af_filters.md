# Tier-2 AF-based somatic filters (Mutect2 & FreeBayes)

**Tier status: Tier-2 (functional, not release-validated for ALE).** Mutect2 and FreeBayes
are *somatic* callers designed for cancer genomics. On ALE data they are too sensitive/noisy
(FreeBayes somatic mode alone produced 248,248 variants vs 10,965 in germline mode), so the
custom AF-based filters below exist to tame that noise but have not been validated as a
release deliverable. **HaplotypeCaller is the Tier-1 SNV/INDEL deliverable** — prefer it for
production ALE variant calling.

This document consolidates the AF-filter, strand-bias, FreeBayes-mode, and FilterMutectCalls
material for these two callers.

---

## AF-based somatic filtering (Mutect2 + FreeBayes)

Migration from GT-based to AF-based filtering for somatic variant detection.

### Mutect2 filtering

- **Module**: `vcf_filter_mutect2/bcftools/filter_somatic/main.nf`
- **Config**: `conf/modules/custom_mutect2_filter.config`
- **Strategy**: Direct AF field usage from `FORMAT/AF[sample]`
- **Criteria**: Normal AF < 0.10, Tumor AF > 0.05, AF difference > 0.05, Depth (tumor ≥ 10, normal ≥ 8)

### FreeBayes filtering

- **Module**: `vcf_filter_freebayes/bcftools/filter_somatic/main.nf`
- **Config**: `conf/modules/custom_freebayes_filter.config`
- **Strategy**: Multi-allelic splitting (`bcftools norm -m-`) + calculated AF via AWK
- **Criteria**: Same AF thresholds as Mutect2

### Multi-allelic handling example

```
Before splitting (AECK01000002:547636):
  REF: AGTATAC  ALT: TGTGTAT,AGTGTAC  (AO=12,5 and AO=0,1)

After bcftools norm -m-:
  Record 1: AGTATAC → TGTGTAT  (AO=12, AO=0)
  Record 2: AGTATAC → AGTGTAC  (AO=5, AO=1)
```

**Benefits:**
- Eliminates AO subfield complexity
- Processes all alternate alleles individually
- Consistent AF thresholds across tools
- More sensitive low-frequency detection

---

## Mutect2 AF vs AD discrepancy

**Observation**: Mutect2's `FORMAT/AF` ≠ simple `AD[alt]/DP` calculation.

**Root cause**: Bayesian allele frequency estimation incorporating base quality, mapping
quality, and local assembly.

**Impact**:
- Using `FORMAT/AF` in filters is correct for Mutect2.
- May show discrepancies when compared to FreeBayes AO/(AO+RO).
- More sensitive due to Bayesian uncertainty.

---

## Strand bias filtering (Mutect2)

**Impact**: Removes > 50% of raw Mutect2 calls (23,847 / 45,139 variants).

**Implementation**: `FORMAT/F1R2[1:1] > 0 && FORMAT/F2R1[1:1] > 0`

**Pipeline chain:**
```
Raw: 45,139 → Quality filters → Strand bias (-52.8%) → AF filters → Final: ~4,200 (90.7% reduction)
```

**Significance**: Eliminates PCR artifacts and sequencing errors critical for ALE experiments.

---

## FreeBayes somatic mode disabled

The `BAM_VARIANT_CALLING_FREEBAYES` channel is disabled in the workflow
`subworkflows/local/bam_variant_calling_somatic_all/main.nf`.

**Rationale**: FreeBayes somatic mode is designed for cancer genomics, inappropriate for ALE.

**Evidence**:
- Somatic mode: 248,248 variants (excessive noise)
- Germline mode: 10,965 variants (biologically relevant)

**Current strategy**:
- **FreeBayes**: Germline mode only
- **Mutect2**: Somatic mode with custom filtering
- **HaplotypeCaller**: Joint and individual germline

**Channel logic**: All samples processed as "normal" status (`cram_variant_calling_status_normal`).

**Pending review**: Structural variant tools (Manta, Strelka, TIDDIT) — germline vs somatic
mode optimization needed.

---

## GATK FilterMutectCalls

### Channel join fix (Dec 2024)

**Issue**: FilterMutectCalls was skipped when no `--germline_resource` was provided.

**Root cause**: Empty contamination channels → `vcf.join(Channel.empty())` = empty result.

**Fix** (`bam_variant_calling_somatic_mutect2/main.nf:177-199`):
```nextflow
// Replaced Channel.empty() with placeholder channels
calculatecontamination_out_seg = vcf.map{ meta, vcf -> [ meta, [] ] }
calculatecontamination_out_cont = vcf.map{ meta, vcf -> [ meta, [] ] }
```

**Results**:
- `*.mutect2.filtered.vcf.gz` now generated
- `*.filteringStats.tsv` now available
- `*.mutect2.artifactprior.tar.gz` now utilized
- Read orientation bias + quality filtering applied
- Contamination/population frequency filtering unavailable (as expected)

### Dual filtering strategy

Available workflows:
1. **GATK FilterMutectCalls**: Standard cancer genomics filtering (`*.mutect2.filtered.vcf.gz`)
2. **Custom Mutect2**: AF-based ALE-optimized filtering (`vcf_filter_mutect2/`)
3. **Custom FreeBayes**: Multi-allelic splitting + AF filtering (`vcf_filter_freebayes/`)

**Recommendation**: Layered QC — GATK for technical artifacts, custom for biological interpretation.

### FilterMutectCalls parameters

**Current**: GATK defaults only (no custom `ext.args`):
- `--normal-p-value-threshold 0.001` (very stringent)
- `--false-discovery-rate 0.05`
- **Pass rate**: 54 / 8,825 variants (0.6%)

**Filter distribution**:
- base_qual;normal_artifact;orientation;strand_bias: 1,925
- multiallelic;normal_artifact;slippage: 749
- normal_artifact;slippage: 619
- **PASS**: 54 only

**TODOs**:
- Review parameter relaxation for ALE (e.g., `--normal-p-value-threshold 0.01`)
- Generate PASS-only VCF extraction workflow
- Evaluate dual-filtering optimal balance

---

## Related bug fix: YAML processing error (custom VCF filters)

**Issue**: Groovy method resolution ambiguity in `processVersionsFromYAML()`.

**Solution**: Used explicit `java.io.FileInputStream(path.toFile())`; added null/empty file
validation and existence checks; maintained backward compatibility.

**File**: `subworkflows/nf-core/utils_nfcore_pipeline/main.nf`

**Impact**: `VCF_FILTER_FREEBAYES` and `VCF_FILTER_MUTECT2` processes now work correctly.
</content>
</invoke>
