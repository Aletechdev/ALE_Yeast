# NF_ALE Project Notes

## Environment-Specific Configurations

### ~~Apple Silicon (Local Development, not maintained)~~

- **Profile**: `arm,docker`
- **Notes**: Nf-sarek is using some tools that stalled with Docker on Apple Silicon, e.g. multiQC, Mutect2, thus development is moved to a Azure VM. Running on Mac also causes more failed jobs could be file system optimization related...

### Azure Linux VM (Remote dev, Production)

- **Profile**: `AzureD4as,docker` (standard)
- **Recommended**: Use original configuration for production deployment

## Deployment Strategy

1. Remote development on an Azure VM, size: D4as
2. Selected nf-sarek's tools: [Prefer Mutect2 over Haptypocaller](reference_scripts/compass_artifact_wf-b8f488cc-c606-4f9a-8630-103f7c12f2bf_text_markdown.md)
3. Additional parameters: ploidy, added to the sample table as column ploidy, **TODO: pass it to FreeBayes**.
4. **TODO:** Additional NextFlow processes: VCF filter, customized for each variant calling tool, e.g. mutect alraedy subtracted control's variants, FreeBaye just show all variants from treated + control.

### Key Files

- `data`: test data folder with gb and fastq files, **does not** come with this git repo, on Azure: https://aledata.blob.core.windows.net/aledata/Yeast/dicarboxylic_acids_all_clones/REDACTED-CUSTOMER-ID/ANP_Dev_2025Q3/data/
- `bin/CENPK_run_sarek_351.sh`: Main execution script for the test data
- `bin/nextflow.config`: Pipeline configuration, with D4as profile for VM local run resources config
- `bin/prepare_input/process_GeneBank/generate_cache/gen_cache.sh`: Cache generation script from the given gff3 file (given draft_ref52.gb is already in gff3 format)
- `nf-core-sarek_3.5.1` forked from nf-core, when looking for documentation, should use the version for 3.5.1

### Input sample table:

Adapted from nf-sarek input table, it was developed for human cancer research thus there terminologies such as patient (considered as Experiment ID for this project), sex, status (0 for normal, 1 for tumor )

For each experiment (patient) there **has to be one normal sample** (status: 0), as I am planning to use tumor-normal mode of sarek, example below, but should accodimate for the edge cases where **only tumor samples are provided**, it will be under a different channel: `BAM_VARIANT_CALLING_TUMOR_ONLY_ALL`

```tex
patient,sex,status,sample,lane,fastq_1,fastq_2
patient1,XX,0,normal_sample,lane_1,test_L001_1.fastq.gz,test_L001_2.fastq.gz
patient1,XX,0,normal_sample,lane_2,test_L002_1.fastq.gz,test_L002_2.fastq.gz
patient1,XX,0,normal_sample,lane_3,test_L003_1.fastq.gz,test_L003_2.fastq.gz
patient1,XX,1,tumor_sample,lane_1,test2_L001_1.fastq.gz,test2_L001_2.fastq.gz
patient1,XX,1,tumor_sample,lane_2,test2_L002_1.fastq.gz,test2_L002_2.fastq.gz
patient1,XX,1,relapse_sample,lane_1,test3_L001_1.fastq.gz,test3_L001_2.fastq.gz
```

### Production Strategies for Deliverable 1

Variant calling tools: FreeBayes and GATK Mutect2

Annotation tool: SnpEff, the snpeff_df is generated externally by `bin/prepare_input/process_GeneBank/generate_cache/gen_cache.sh`

Issue: for channel `BAM_VARIANT_CALLING_SOMATIC_ALL` the meta data structure cheanged.

TODO: add filter for FreeBayes from Somatic Call

### **⚠️ Note: BaseRecalibrator Not Applied**

The pipeline **no longer uses GATK’s BaseRecalibrator** for base quality score recalibration (BQSR). Since our in-house reference genome lacks any curated --known-sites variant VCFs, BaseRecalibrator cannot run—it mandates at least one known-sites database to distinguish true variation from sequencing errors . https://janis.readthedocs.io/en/latest/tools/bioinformatics/gatk4/gatk4baserecalibrator.html?utm_source=chatgpt.com

In future, if we generate a reliable set of high-confidence variants (e.g., through bootstrapped calls), we may revisit and enable BQSR. Until then, BaseRecalibrator is retained in documentation for reference only and is **not used in current analyses**.

### **⚠️ Note: VCFTOOLS Not Run If Ploidy > 2**

```yaml
# Docs/NF_ALE/nf-core-sarek_3.5.1/3_5_1/conf/modules/modules.config
# Got error tesing with ploidy = 3 and 4: Error: Polyploidy found, and not supported by vcftools
# Tested working fine with ploidy = 1 and 2
withName: 'VCFTOOLS_.*' {
        ext.prefix = { variant_file.baseName - ".vcf" }
        ext.when   = { !(params.skip_tools && params.skip_tools.split(',').contains('vcftools')) && 
                      (meta.ploidy == null || meta.ploidy.toString().toInteger() <= 2) }
        publishDir = [
            mode: params.publish_dir_mode,
            path: { "${params.outdir}/reports/vcftools/${meta.variantcaller}/${meta.id}/" },
            saveAs: { filename -> filename.equals('versions.yml') ? null : filename }
        ]
    }
```

### Basic VCF Filtering Implementation, ***deprecated***, for idea of folders involved for making nf-sarek changes

#### Integration Point (REVISED)

- **Location**: `nf-core-sarek_3.5.1/3_5_1/workflows/sarek/main.nf` around line 801
- **Target**: Filter `vcf_to_annotate` channel (before annotation)
- **Rationale**: More flexible during custom SnpEff/VEP database testing, will add breseq gdtools for annotation, where the output will be in .gb format

#### Implementation Steps

1. **Add BCFTOOLS_FILTER module** from nf-core: `nf-core modules install bcftools/filter`
2. **Create filter configuration** at `conf/modules/bcftools_filter.config`
3. **New channel vcf_filtered** for downstream QC and annotation
4. **Output structure**: `variant_calling_filtered/{tool}/{sample}/`

#### Integration Code Location

```nextflow
// Around line 801 in main.nf, after:
vcf_to_annotate = vcf_to_annotate.mix(BAM_VARIANT_CALLING_SOMATIC_ALL.out.vcf_all)

// ADD FILTERING HERE:
include { BCFTOOLS_FILTER } from '../modules/nf-core/bcftools/filter/main'
BCFTOOLS_FILTER(vcf_to_annotate)
vcf_filtered = BCFTOOLS_FILTER.out.vcf

```

#### Filter Configuration

```bash
# Basic quality filters (no annotation dependency)
--include "QUAL>=20 && INFO/DP>=10"
```

#### Benefits of Basic Pre-Annotation Filtering

- **Independent of annotation setup** - Works regardless of SnpEff/VEP configuration
- **Quality-based filtering** - Focus on high-confidence variants
- a bigger vcf channel `vcf_to_annotate.mix(vcf_to_annotate_filtered)` is created for annotation, due to the pipeline is under development, and the unfiltered but annotatied vcf files will be valuable for troubleshooting.
- **TODO**: decide when to filter the VCF files, before or after the VCF annotation

###
