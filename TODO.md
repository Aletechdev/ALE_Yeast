# NF_ALE Project TODO List

## Current Tasks

### add ploidy to cnvkit
documentations:
https://cnvkit.readthedocs.io/en/stable/pipeline.html#call

### change mutect calling parameters for yeast genomes:
Key parameters to focus on instead:
--af-of-alleles-not-in-resource: Set this based on your expected mutation rate (default 5e-8 is reasonable for most microbes)
--initial-tumor-lod: Lower this (e.g., to 0.5-1.0) if you want to detect very low-frequency variants early in evolution
--max-population-af: Set to 1.0 to allow any allele frequency (important for evolution experiments)
--downsampling-stride: Consider disabling downsampling (set to 1) for smaller yeast genomes

### update freebayes and mutect2 filter parameters
### reset freebayes vcf filter parameters
### update controlfreec parameters, e.g., window for yeast
### move this repo to org's github repo



### Better tracking of versioning

## Completed Tasks
- ✅ Fixed FreeBayes filtering configuration and output publishing
- ✅ Simplified FreeBayes somatic filtering subworkflow structure
- ✅ Resolved config pattern matching for BCFTOOLS_FILTER parameters
