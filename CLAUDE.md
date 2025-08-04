# NF_ALE Project Notes

## Environment-Specific Configurations

### Apple Silicon (Local Development, not maintained)
- **Profile**: `arm,docker`
- **Notes**: Required for Apple Silicon compatibility, lower priority for Apple Silicon machines local run

### Azure Linux VM (Production)
- **Profile**: `AzureD4as,docker` (standard)
- **Recommended**: Use original configuration for production deployment

## Deployment Strategy
1. For local Apple Silicon development: Use current ARM-compatible settings
2. For production Azure deployment: 

## Key Files
- `bin/CENPK_run_sarek_351.sh`: Main execution script
- `bin/nextflow.config`: Pipeline configuration
- `bin/prepare_input/process_GeneBank/generate_cache/gen_cache.sh`: Cache generation script

## VCF Filtering Implementation

### Integration Point (REVISED)
- **Location**: `nf-core-sarek_3.5.1/3_5_1/workflows/sarek/main.nf` around line 801
- **Target**: Filter `vcf_to_annotate` channel (before annotation)
- **Rationale**: More flexible during custom SnpEff/VEP database testing, will add breseq gdtools for annotation, where the output will be in .gb format

### Implementation Steps
1. **Add BCFTOOLS_FILTER module** from nf-core: `nf-core modules install bcftools/filter`
2. **Create filter configuration** at `conf/modules/bcftools_filter.config`
3. **New channel vcf_filtered** for downstream QC and annotation
4. **Output structure**: `variant_calling_filtered/{tool}/{sample}/`

### Integration Code Location
```nextflow
// Around line 801 in main.nf, after:
vcf_to_annotate = vcf_to_annotate.mix(BAM_VARIANT_CALLING_SOMATIC_ALL.out.vcf_all)

// ADD FILTERING HERE:
include { BCFTOOLS_FILTER } from '../modules/nf-core/bcftools/filter/main'
BCFTOOLS_FILTER(vcf_to_annotate)
vcf_filtered = BCFTOOLS_FILTER.out.vcf

```

### Filter Configuration
```bash
# Basic quality filters (no annotation dependency)
--include "QUAL>=20 && INFO/DP>=10"

# Freebayes-specific depth filters
--include "QUAL>=20 && INFO/DP>=10 && INFO/AO>=5"

# Tool-specific configurations possible via meta.variantcaller
```

### Benefits of Basic Pre-Annotation Filtering
- **Independent of annotation setup** - Works regardless of SnpEff/VEP configuration
- **Quality-based filtering** - Focus on high-confidence variants
- a bigger vcf channel `vcf_to_annotate.mix(vcf_to_annotate_filtered)` is created for annotation, due to the pipeline is under development, and the unfiltered but annotatied vcf files will be valuable for troubleshooting.
- **TODO**: decide when to filter the VCF files, before or after the VCF annotation



Next feature for development: VCF files merging for normal samples,