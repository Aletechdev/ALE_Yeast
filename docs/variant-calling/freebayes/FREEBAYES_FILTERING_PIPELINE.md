# FreeBayes Variant Filtering Pipeline

## Summary
FreeBayes variants are filtered through a **custom quality filtering subworkflow** that removes low-quality variants before annotation. The pipeline uses `bcftools view` with germline-optimized filters designed for yeast ALE experiments.

## Pipeline Architecture

### 1. Workflow Integration Point
**Location**: `workflows/sarek/main.nf:828`

```nextflow
// After variant calling and tabix indexing
VCF_FILTER_FREEBAYES(vcf_with_tbi)
versions = versions.mix(VCF_FILTER_FREEBAYES.out.versions)

// Filtered VCFs go to annotation
vcf_to_annotate = vcf_to_annotate.mix(
    VCF_FILTER_FREEBAYES.out.vcf_filtered.map{ meta, vcf, tbi -> [ meta, vcf ] }
)
```

### 2. Custom Subworkflow
**Location**: `subworkflows/local/vcf_filter_freebayes/main.nf`

**Key Operations**:
- Filters only FreeBayes VCFs (`meta.variantcaller == 'freebayes'`)
- Adds `.quality_filtered` suffix to sample ID
- Applies germline quality filters via `BCFTOOLS_FILTER_NORMAL`
- Outputs filtered VCF with index

```nextflow
// Filter FreeBayes VCFs only
ch_freebayes_vcfs = ch_vcf_tbi.filter{ meta, vcf, tbi ->
    meta.variantcaller == 'freebayes' || vcf.name.contains('freebayes')
}

// Update metadata
ch_freebayes_vcfs.map{ meta, vcf, tbi ->
    def new_id = vcf.name - '.vcf.gz'
    [meta + [id: "${new_id}.quality_filtered"], vcf, tbi]
}.set{ ch_for_basic_filter }

// Apply filters
BCFTOOLS_FILTER_NORMAL(ch_for_basic_filter)
```

### 3. Filter Implementation
**Location**: `subworkflows/local/vcf_filter_freebayes/bcftools/filter_normal/main.nf`

**Process**: `BCFTOOLS_FILTER_NORMAL`
- **Container**: bcftools 1.21
- **Label**: process_low
- **Input**: `[meta, vcf, tbi]`
- **Output**: `*.normal.vcf.gz` and `*.normal.vcf.gz.tbi`

**Command**:
```bash
bcftools view \
    --include '<filter_expression>' \
    --output-type z \
    -o ${prefix}.normal.vcf.gz \
    $vcf

bcftools index -t ${prefix}.normal.vcf.gz
```

## Filter Criteria

### Configuration Location
**File**: `conf/modules/custom_freebayes_filter.config:21-28`

### Applied Filters
```bash
--include "QUAL>=15                      # Minimum variant quality score
           & INFO/DP>=8                  # Minimum total sequencing depth
           & INFO/DP<=500                # Maximum depth (avoid repeats/CNVs)
           & INFO/SAF>0 & INFO/SAR>0    # Strand bias: require forward+reverse reads
           & INFO/AO>=2                  # Minimum alternate allele observations
           & INFO/MQM>=20 & INFO/MQMR>=20"  # Good mapping quality (alt & ref)
```

### Filter Explanations

| Filter | Threshold | Purpose | Notes |
|--------|-----------|---------|-------|
| **QUAL** | ≥15 | Variant confidence | Relaxed from 20 for low-coverage data |
| **DP** | ≥8, ≤500 | Total read depth | Lower: noise; Higher: repeats/CNVs |
| **SAF & SAR** | >0 each | Strand bias detection | Requires reads from both DNA strands |
| **AO** | ≥2 | Alternate observations | Relaxed from 3 for sensitivity |
| **MQM & MQMR** | ≥20 each | Mapping quality | Filters mismapped reads |

### Multi-Allelic Site Handling
**Important**: Multi-allelic sites are **preserved** (not split).

For comma-separated INFO fields (`AO=9,1`), bcftools checks if **ANY allele** passes the threshold:
- `AO>=2` with `AO=9,1` → **PASS** (first allele meets requirement)
- `AO>=2` with `AO=1,1` → **FAIL** (first allele fails)

## Output Structure

```
output/variant_calling_filtered/freebayes/
├── A0-F0-I1-R1.freebayes.quality_filtered/
│   ├── A0-F0-I1-R1.freebayes.quality_filtered.normal.vcf.gz
│   └── A0-F0-I1-R1.freebayes.quality_filtered.normal.vcf.gz.tbi
├── A4-F5-I1-R1.freebayes.quality_filtered/
│   ├── A4-F5-I1-R1.freebayes.quality_filtered.normal.vcf.gz
│   └── A4-F5-I1-R1.freebayes.quality_filtered.normal.vcf.gz.tbi
└── ...
```

**Published Directory**: `${params.outdir}/variant_calling_filtered/freebayes/${meta.id}/`

## Pipeline Context

### FreeBayes Mode: Germline Only
**Per CLAUDE.md**: FreeBayes runs in **germline mode only** (somatic mode disabled)

**Rationale**:
- FreeBayes somatic mode: 248,248 variants (excessive noise)
- FreeBayes germline mode: 10,965 variants (biologically relevant)
- Somatic calling handled by Mutect2 instead

**Channel**: All samples processed through `cram_variant_calling_status_normal`

### Comparison with Mutect2 Filtering
Both FreeBayes and Mutect2 have **parallel custom filtering workflows**:

| Tool | Subworkflow | Filter Type | Output Suffix |
|------|-------------|-------------|---------------|
| FreeBayes | `VCF_FILTER_FREEBAYES` | Germline quality | `.quality_filtered.normal.vcf.gz` |
| Mutect2 | `VCF_FILTER_MUTECT2` | Somatic AF-based | `.somatic_filtered.vcf.gz` |

## Filter Performance Notes

### Expected Behavior with Test Data
**Note**: Small test datasets (subsampled data) may have few or no variants passing stringent filters. This is expected behavior and filters should be evaluated on full production data.

### Checking Filter Performance
```bash
# Source conda environment
source ~/miniforge3/etc/profile.d/conda.sh
conda activate nf-env

# Compare original vs filtered variant counts
original="output/variant_calling/freebayes/${sample}/${sample}.freebayes.vcf.gz"
filtered="output/variant_calling_filtered/freebayes/${sample}.freebayes.quality_filtered/${sample}.freebayes.quality_filtered.normal.vcf.gz"

echo "Original: $(bcftools view -H $original | wc -l) variants"
echo "Filtered: $(bcftools view -H $filtered | wc -l) variants"
echo "Retention rate: $((100 * $(bcftools view -H $filtered | wc -l) / $(bcftools view -H $original | wc -l)))%"
```

### Evaluating Individual Filter Criteria
To understand which filters are most restrictive:
```bash
vcf="path/to/original.vcf.gz"

echo "Total variants: $(bcftools view -H $vcf | wc -l)"
echo "QUAL>=15: $(bcftools view -H --include 'QUAL>=15' $vcf | wc -l)"
echo "DP>=8: $(bcftools view -H --include 'INFO/DP>=8' $vcf | wc -l)"
echo "SAF>0 & SAR>0: $(bcftools view -H --include 'INFO/SAF>0 & INFO/SAR>0' $vcf | wc -l)"
echo "AO>=2: $(bcftools view -H --include 'INFO/AO>=2' $vcf | wc -l)"
```

### Adjusting Filters (If Needed)
Filter parameters can be adjusted in `conf/modules/custom_freebayes_filter.config` for specific experimental needs:

**Example adjustments**:
```yaml
# More lenient for discovery-mode analysis
'"QUAL>=10 & INFO/DP>=5 & (INFO/SAF>0 | INFO/SAR>0) & INFO/AO>=2"'

# More stringent for high-confidence calls
'"QUAL>=20 & INFO/DP>=10 & INFO/SAF>1 & INFO/SAR>1 & INFO/AO>=3"'
```

## Validation & Quality Control

### Inspecting Filtered Variants
```bash
# Source conda environment
source ~/miniforge3/etc/profile.d/conda.sh
conda activate nf-env

# View filtered variant details
filtered="output/variant_calling_filtered/freebayes/${sample}.freebayes.quality_filtered/${sample}.freebayes.quality_filtered.normal.vcf.gz"

# Summary statistics
bcftools stats $filtered | grep "^SN"

# View variant details
bcftools query -f '%CHROM:%POS\t%QUAL\t%INFO/DP\t%INFO/AO\t%INFO/SAF\t%INFO/SAR\n' $filtered | head
```

### Comparing Filtered vs Unfiltered
```bash
# Get variants that were filtered out
original="output/variant_calling/freebayes/${sample}/${sample}.freebayes.vcf.gz"
filtered="output/variant_calling_filtered/freebayes/${sample}.freebayes.quality_filtered/${sample}.freebayes.quality_filtered.normal.vcf.gz"

bcftools isec -C -w1 $original $filtered -o removed_variants.vcf

# Inspect removed variants
echo "Removed variants: $(bcftools view -H removed_variants.vcf | wc -l)"
bcftools query -f '%CHROM:%POS\t%QUAL\t%INFO/DP\t%INFO/AO\n' removed_variants.vcf | head
```

## Integration with Downstream Processes

### 1. Annotation
Filtered VCFs are added to the `vcf_to_annotate` channel:
```nextflow
vcf_to_annotate = vcf_to_annotate.mix(
    VCF_FILTER_FREEBAYES.out.vcf_filtered.map{ meta, vcf, tbi -> [ meta, vcf ] }
)
```

### 2. SnpEff Annotation
- Filtered VCFs annotated with custom yeast SnpEff cache
- Output: `output/reports/snpeff/freebayes/${sample}.quality_filtered/`

### 3. bcftools Stats
- Quality metrics generated for filtered VCFs
- Output: `output/reports/bcftools/freebayes/${sample}.quality_filtered/`

## Key Differences from Original Sarek

### Custom Implementation
✅ **Added**: Custom FreeBayes filtering subworkflow
✅ **Added**: Germline-optimized filter parameters
✅ **Added**: ALE-specific quality thresholds
✅ **Disabled**: FreeBayes somatic mode (see CLAUDE.md)

### Design Rationale
1. **Germline-only mode**: ALE experiments compare evolved vs ancestral strains (not tumor/normal)
2. **Quality-based filtering**: Remove technical artifacts before annotation
3. **Parallel with Mutect2**: Dual filtering strategies for different variant types
4. **Pre-annotation filtering**: Reduces annotation time and focuses on high-quality variants

## References

### Pipeline Files
- Main workflow: `workflows/sarek/main.nf:828`
- Subworkflow: `subworkflows/local/vcf_filter_freebayes/main.nf`
- Filter process: `subworkflows/local/vcf_filter_freebayes/bcftools/filter_normal/main.nf`
- Configuration: `conf/modules/custom_freebayes_filter.config:11-39`

### Related Documentation
- See `CLAUDE.md` section: "✅ FreeBayes Somatic Mode Disabled"
- See `CLAUDE.md` section: "✅ Allele Frequency-Based Somatic Filtering"
- FreeBayes documentation: https://github.com/freebayes/freebayes

### Filter Design Notes
Filters optimized for:
- Yeast genome (small size, ~12 Mb)
- ALE experiments (evolved vs ancestral comparisons)
- Illumina short-read sequencing
- Diploid/polyploid strains (ploidy-aware)

**Status**: ✅ Production-ready (may need parameter adjustment for low-coverage datasets)
