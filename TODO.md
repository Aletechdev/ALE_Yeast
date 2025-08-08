# NF_ALE Project TODO List

## Current Tasks

### [Pending] Mutect2 VCF Investigation
- **Issue**: vcf_mutect2 from `BAM_VARIANT_CALLING_SOMATIC_MUTECT2.out.vcf_filtered` is empty with current input data
- **Impact**: Prevents Mutect2 VCFs from being sent to annotation pipeline
- **Location**: `subworkflows/local/bam_variant_calling_somatic_all/main.nf:223`
- **Status**: Needs investigation

## Completed Tasks
- ✅ Fixed FreeBayes filtering configuration and output publishing
- ✅ Simplified somatic filtering subworkflow structure
- ✅ Resolved config pattern matching for BCFTOOLS_FILTER parameters