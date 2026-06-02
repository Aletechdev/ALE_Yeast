# VCF Downloads

Pre-normalization annotated VCF files organized by variant caller.
These are the canonical variant calls suitable for sharing and downstream analysis.

## haplotypecaller/

- **cohort_haplotypecaller_annotated.vcf.gz**: Joint HaplotypeCaller VCF (all samples),
  soft-filtered (GATK VariantFiltration), annotated with SnpEff.
- **{sample}_haplotypecaller_annotated.vcf.gz**: Per-sample VCFs extracted from the joint
  VCF. Non-reference genotypes only (ref-homozygous sites removed). SnpEff annotated.
  No hard filter applied — all variants where the sample has a non-ref genotype are included.

### Processing chain for per-sample VCFs:
1. Joint calling (GATK HaplotypeCaller → GenotypeGVCFs)
2. Soft filtering (GATK VariantFiltration: QD, FS, SOR, MQ filters)
3. Sample extraction (bcftools view -s)
4. Ref-genotype removal (bcftools filter: keep GT != 0/0)
5. Annotation (SnpEff)

## cnvkit/

- **{sample}_cnvkit.vcf.gz**: CNVKit copy number calls, SnpEff annotated.

## manta/

- **{sample}_manta.vcf.gz**: Manta structural variant calls (diploid_sv), SnpEff annotated.

## tiddit/

- **{sample}_tiddit.vcf.gz**: TIDDIT structural variant calls, SnpEff annotated.

## IGV Report Display VCFs

The IGV reports use a _post-processed_ version of these VCFs for the interactive table:
1. `bcftools norm -m-` (multi-allelic splitting — increases row count)
2. FILTER column promoted to INFO/VCF_FILTER
3. `bcftools +fill-tags FORMAT/VAF` added

These display VCFs are internal to the reports and not published here.
To reproduce, see the methodology section in index.html.
