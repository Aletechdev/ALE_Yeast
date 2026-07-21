# Test fixtures

Small, committed fixtures for the nf-test unit tests under `tests/`. All are derived from a real
ottilie pipeline run (`output_ottilie_test/`); the commands below make them regenerable.

## SPLIT_JOINT_VCF (`tests/split_joint_vcf.nf.test`)

Both fixtures are the **un-annotated soft-filtered joint VCF** — the actual channel
`SPLIT_JOINT_VCF` consumes in the pipeline (`BAM_JOINT_CALLING_GERMLINE_GATK.out.genotype_vcf`),
not the downstream annotated cohort copy. Samples are haploid (single-allele GTs), so the fixture
meta uses `ploidy:1`.

### `joint_soft_filtered.vcf.gz` (+ `.tbi`) — 2-sample, faithful

A verbatim copy of the real joint VCF (2 samples, 100 records; splits to CBR 69 / NODRUG 89 non-ref):

```bash
SRC=output_ottilie_test/variant_calling/haplotypecaller/joint_variant_calling/HaplotypeCaller_joint_calling_soft_filtered.vcf.gz
cp "$SRC" tests/fixtures/joint_soft_filtered.vcf.gz
bcftools index -t -f tests/fixtures/joint_soft_filtered.vcf.gz
```

### `joint_soft_filtered_single_sample.vcf.gz` (+ `.tbi`) — 1-column, **synthetic**

A single-column subset of the 2-sample VCF above (CBR only, 100 sites; splits to 69 non-ref),
used to exercise the single-column-joint code path (`.combine` with a 1-element cram channel):

```bash
bcftools view -s Ottilie_test_CBR110-15-R3a --force-samples "$SRC" \
    -Oz -o tests/fixtures/joint_soft_filtered_single_sample.vcf.gz
bcftools index -t -f tests/fixtures/joint_soft_filtered_single_sample.vcf.gz
```

> **Caveat — this is a column subset, NOT a genuine single-sample joint-calling run.**
> `bcftools view -s` keeps every cohort site (including sites only variant in the other sample,
> where CBR is reference), so it has the same 100 sites as the 2-sample VCF. A real one-sample
> GATK joint run would call its own site set. This fixture validates SPLIT_JOINT_VCF's *plumbing*
> on a 1-column input; it does not reproduce the real single-sample-joint scenario (that case is
> hand-verified in `docs/compare_single_pop_HpCaller/README.md`).
