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

Adapted from nf-sarek input table, it was developed for human cancer research, experiment is used as patient within the nf-Sarek pipeline (considered as Experiment ID for this project), status 0 for starting strain (normal tissue for Sarek), 1 for mutent (tumor tissue for Sarek)

For each experiment (patient) there **has to be one normal sample** (status: 0), as I am planning to use tumor-normal pairing mode of sarek, example below, but should accodimate for the edge cases where **only tumor samples are provided**, the files will be processed under a different nf-Sarek channel: `BAM_VARIANT_CALLING_TUMOR_ONLY_ALL`

TODO: also need a column of sex chromosome (XX) for some CNV tools, auto-fill this info??
```tex
experiment,sample,status,clonal_or_population,ploidy,lane,fastq_1,fastq_2
ALE_Exp1,A4-F5-I1-R1,1,clonal,2,L001,SubSampleA4-5_S11_L001_R1_001.fastq.gz,SubSampleA4-5_S11_L001_R2_001.fastq.gz
ALE_Exp1,A4-F5-I1-R1,1,clonal,2,L003,SubSampleA4-5_S11_L003_R1_001.fastq.gz,SubSampleA4-5_S11_L003_R2_001.fastq.gz
ALE_Exp1,A0-F0-I1-R1,0,clonal,2,L001,SubSampleCENPK113-7D-N_S53_L001_R1_001.fastq.gz,SubSampleCENPK113-7D-N_S53_L001_R2_001.fastq.gz
ALE_Exp1,A0-F0-I1-R1,0,clonal,2,L002,SubSampleCENPK113-7D-N_S53_L002_R1_001.fastq.gz,SubSampleCENPK113-7D-N_S53_L002_R2_001.fastq.gz

```

### Production Strategies for Deliverable 1

Variant calling tools: FreeBayes and GATK Mutect2

Annotation tool: SnpEff, the snpeff_df is generated externally by `bin/prepare_input/process_GeneBank/generate_cache/gen_cache.sh`

Issue: for channel `BAM_VARIANT_CALLING_SOMATIC_ALL` the meta data structure cheanged.

The filter of FreeBayes and Mutect2 somatic variants, not super elegent but need to index the normal and treated samples:
FreeBayes: `nf-core-sarek_3.5.1/3_5_1/conf/modules/custom_freebayes_filter.config` and `nf-core-sarek_3.5.1/3_5_1/subworkflows/local/vcf_filter_freebayes/bcftools/filter_somatic/main.nf`
Mutect2: `nf-core-sarek_3.5.1/3_5_1/conf/modules/custom_mutect2_filter.config` and `nf-core-sarek_3.5.1/3_5_1/subworkflows/local/vcf_filter_mutect2/bcftools/filter_somatic/main.nf`

### **⚠️ Note: BaseRecalibrator Not Applied**

The pipeline **no longer uses GATK’s BaseRecalibrator** for base quality score recalibration (BQSR). Since our in-house reference genome lacks any curated --known-sites variant VCFs, BaseRecalibrator cannot run. it mandates at least one known-sites database to distinguish true variation from sequencing errors. https://janis.readthedocs.io/en/latest/tools/bioinformatics/gatk4/gatk4baserecalibrator.html?utm_source=chatgpt.com

In future, if we generate a reliable set of high-confidence variants (e.g., through bootstrapped calls), we may revisit and enable BQSR. Until then, BaseRecalibrator is retained in code base for reference only and is **not used in current analyses**.

### ⚠️ Mutect2 with custom genome, omitting panel-of-normal (vcf) and germline resource (vcf)

```
WARN: No Panel-of-normal was specified for Mutect2.
It is highly recommended to use one: https://gatk.broadinstitute.org/hc/en-us/articles/5358911630107-Mutect2
For more information on how to create one: https://gatk.broadinstitute.org/hc/en-us/articles/5358921041947-CreateSomaticPanelOfNormals-BETA-
WARN: If Mutect2 is specified without a germline resource, no filtering will be done.
It is recommended to use one: https://gatk.broadinstitute.org/hc/en-us/articles/5358911630107-Mutect2
```

#### 1.**--germline-resource**

* **Purpose** : Filters out common population variants (SNPs) that are unlikely to be somatic mutations
* **For yeast ALE** : You're looking for ANY mutations that arise during evolution, including what would be "germline" variants in cancer terms
* **Reality** : No comprehensive yeast population databases exist like gnomAD for humans
* **Recommendation** : **Omit this parameter entirely**
* As --germline-resource is omitted, the parameter `--af-of-alleles-not-in-resource / -default-af` **is also omitted**.

#### 2.**--panel-of-normals (PoN)**

* **Purpose** : Identifies systematic artifacts from sequencing/sample prep that appear across multiple "normal" samples
* **For yeast ALE** : Could theoretically be useful if you have multiple ancestral strain replicates
* **Reality** : The effort to create a PoN may not be justified for yeast experiments
* **Recommendation** :** ****Omit unless you have systematic artifacts to filter**


### **⚠️ Note: VCFTOOLS Not Run If Ploidy > 2**

```yaml
# Docs/NF_ALE/nf-core-sarek_3.5.1/3_5_1/conf/modules/modules.config
# Got error tesing with ploidy = 3 and 4 with FreeBayes: Error: Polyploidy found, and not supported by vcftools
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
### ⚠️ Control-FREEC Warnings and Limitations

#### Case 1: No SNP Database Provided
**Warning: No SNP information provided for Control-FREEC analysis**
- BAF (B-Allele Frequency) files will **not be generated**
- Copy number analysis will proceed using **read depth only**
- This occurs when running without a SNP database (e.g., dbSNP)
- **Expected behavior** for custom reference genomes without curated variant databases

#### Case 2: Haploid Strains (Ploidy=1)
**Empty CNVs file causing ASSESS_SIGNIFICANCE failure**
- Haploid strains typically produce **empty `*.gz_CNVs` files**
- ASSESS_SIGNIFICANCE process fails with "no lines available in input" error
- **Solution**: ASSESS_SIGNIFICANCE is **automatically skipped** when `ploidy=1`
- Copy number analysis still proceeds using read depth ratios

### ⚠️ Control-FREEC ASSESS_SIGNIFICANCE Skipped for Haploid Strains (ploidy =1)

Control-FREEC's `ASSESS_SIGNIFICANCE` step is **automatically skipped when ploidy=1** because haploid strains typically produce empty `*.gz_CNVs` files, causing the R script to fail with "no lines available in input" error.

**Configuration**: `conf/modules/controlfreec.config` includes:
```yaml
withName: 'ASSESS_SIGNIFICANCE' {
    ext.when = { !(meta.ploidy == null || meta.ploidy.toString().toInteger() == 1) }
    # ... rest of config
}
```

This prevents the process from running on samples with ploidy=1, allowing the pipeline to complete successfully for haploid yeast strains. 

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
