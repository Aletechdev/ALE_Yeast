# NF_ALE Project TODO List

## Current Tasks

### fix version error: nf-core-sarek_3.5.1/3_5_1/subworkflows/nf-core/utils_nfcore_pipeline/main.nf
it could have some things to do with the filter functions do not have version report??
ERROR ~ Could not find which method load() to invoke from this list:
  public java.lang.Object org.yaml.snakeyaml.Yaml#load(java.io.InputStream)
  public java.lang.Object org.yaml.snakeyaml.Yaml#load(java.io.Reader)
  public java.lang.Object org.yaml.snakeyaml.Yaml#load(java.lang.String)
  public java.lang.Object org.yaml.snakeyaml.Yaml#load(java.io.File)
  public java.lang.Object org.yaml.snakeyaml.Yaml#load(java.nio.file.Path)

 -- Check script '/home/azureuser/Docs/NF_ALE/nf-core-sarek_3.5.1/3_5_1/subworkflows/nf-core/utils_nfcore_pipeline/main.nf' at line: 97 or see '.nextflow.log' file for more details
ERROR ~ Pipeline failed. Please refer to troubleshooting docs: https://nf-co.re/docs/usage/troubleshooting

 -- Check '.nextflow.log' file for details

### change mutect2 calling parameters for yeast genomes:
Key parameters to focus on instead:
--af-of-alleles-not-in-resource: Set this based on your expected mutation rate (default 5e-8 is reasonable for most microbes)
--initial-tumor-lod: Lower this (e.g., to 0.5-1.0) if you want to detect very low-frequency variants early in evolution
--max-population-af: Set to 1.0 to allow any allele frequency (important for evolution experiments)
--downsampling-stride: Consider disabling downsampling (set to 1) for smaller yeast genomes

### update freebayes and mutect2 filter parameters

### update controlfreec parameters, e.g., window for yeast
### move this repo to org's github repo



### Better tracking of versioning

## Completed Tasks
- ✅ Fixed FreeBayes filtering configuration and output publishing
- ✅ Simplified FreeBayes somatic filtering subworkflow structure
- ✅ Resolved config pattern matching for BCFTOOLS_FILTER parameters
