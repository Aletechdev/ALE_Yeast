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

### `joint_manta_diploid_sv.vcf.gz` (+ `.tbi`) — 2-sample joint Manta, **two edited genotypes**

The `--joint_manta` diploid SV VCF of the 2-sample set (18 records, all PASS, both samples
genotyped at every record), with two CBR110 genotypes hand-edited so the Manta split's drop rule is
exercised (the real file has no hom-ref row): `I:206105` → `0/0:HomRef`, `IV:465972` → `./.`.
Splits to CBR 16 / NODRUG 18; CBR keeps its two genuine `0/1 FT=MinGQ GQ=10` breakends, which the
split promotes to `FILTER=MinGQ`.

```bash
# joint run, e.g.: nextflow run main.nf -profile ottilie_test,azureD4as,docker --step variant_calling \
#   --tools manta --joint_manta --joint_germline false --input <cram samplesheet>
SRC=<outdir>/variant_calling/manta/Ottilie_test/Ottilie_test.manta.diploid_sv.vcf.gz
python - "$SRC" <<'PY'
import gzip, sys
out, n = [], 0
for l in gzip.open(sys.argv[1], "rt").read().splitlines():
    if l.startswith("#"): out.append(l); continue
    f = l.split("\t"); n += 1
    s = f[10].split(":")                       # column 11 = Ottilie_test_CBR110-15-R3a
    if n == 1: s[0], s[1] = "0/0", "HomRef"
    if n == 2: s[0] = "./."
    f[10] = ":".join(s); out.append("\t".join(f))
open("joint_manta_diploid_sv.vcf", "w").write("\n".join(out) + "\n")
PY
bcftools view -Oz -o tests/fixtures/joint_manta_diploid_sv.vcf.gz joint_manta_diploid_sv.vcf
bcftools index -t -f tests/fixtures/joint_manta_diploid_sv.vcf.gz
```
