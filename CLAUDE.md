# NF_ALE Project Notes

## Environment-Specific Configurations

### Apple Silicon (Local Development)
- **Commit**: `cbe4a0bd1d33cb6cd3b5994d12476e1490a5baae`
- **Profile**: `arm,docker`
- **Notes**: Required for Apple Silicon compatibility

### Azure Linux VM (Production)
- **Profile**: `docker` (standard)
- **Recommended**: Use original configuration for production deployment

## Deployment Strategy
1. For local Apple Silicon development: Use current ARM-compatible settings
2. For production Azure deployment: Revert Docker profile to remove ARM-specific configurations
3. Test both environments before major releases

## Key Files
- `bin/CENPK_run_sarek_351.sh`: Main execution script
- `bin/nextflow.config`: Pipeline configuration
- `bin/prepare_input/process_GeneBank/generate_cache/gen_cache.sh`: Cache generation script

## VCF Filtering Implementation

### Integration Point (REVISED)
- **Location**: `nf-core-sarek_3.5.1/3_5_1/workflows/sarek/main.nf` around line 801
- **Target**: Filter `vcf_to_annotate` channel (before annotation)
- **Rationale**: More flexible during custom SnpEff/VEP database testing

### Implementation Steps
1. **Add BCFTOOLS_FILTER module** after building vcf_to_annotate channel
2. **Create filter configuration** at `conf/modules/bcftools_filter.config`
3. **Use filtered VCFs** for downstream QC and annotation
4. **Output structure**: `variant_calling_filtered/{tool}/{sample}/`

### Integration Code Location
```nextflow
// Around line 801 in main.nf, after:
vcf_to_annotate = vcf_to_annotate.mix(BAM_VARIANT_CALLING_SOMATIC_ALL.out.vcf_all)

// ADD FILTERING HERE:
include { BCFTOOLS_FILTER } from '../modules/nf-core/bcftools/filter/main'
BCFTOOLS_FILTER(vcf_to_annotate)
vcf_filtered = BCFTOOLS_FILTER.out.vcf

// Replace vcf_to_annotate with vcf_filtered in downstream processes:
// - VCF_QC_BCFTOOLS_VCFTOOLS(vcf_filtered, intervals_bed_combined)
// - VCF_ANNOTATE_ALL uses vcf_filtered instead of vcf_to_annotate
```

### Filter Configuration
```bash
# Basic quality filters (no annotation dependency)
--include "QUAL>=20 && INFO/DP>=10"

# Freebayes-specific depth filters
--include "QUAL>=20 && INFO/DP>=10 && INFO/AO>=5"

# Tool-specific configurations possible via meta.variantcaller
```

### Benefits of Pre-Annotation Filtering
- **Independent of annotation setup** - Works regardless of SnpEff/VEP configuration
- **Faster annotation** - Fewer variants to annotate
- **Flexible testing** - Can iterate on filters without re-annotation
- **Quality-based filtering** - Focus on high-confidence variants