# NF_ALE Project TODO List

## Current Tasks

### ✅ RESOLVED: YAML load() method ambiguity error - Groovy method resolution issue

**Root Cause**: Groovy method resolution ambiguity (not Java version issue - Nextflow officially supports Java up to 24)
- Environment: Nextflow 25.04.6 + Java 23.0.2 (within supported range)
- Issue: `yaml_file` parameter has ambiguous type (could be Path, File, String, etc.), causing Groovy to fail method resolution
- Trigger: Custom VCF filtering processes producing version files with different input types than expected
- Location: `/nf-core-sarek_3.5.1/3_5_1/subworkflows/nf-core/utils_nfcore_pipeline/main.nf:113`

**Solution Implemented**: Used explicit FileInputStream approach with proper error handling:
```groovy
def processVersionsFromYAML(yaml_file) {
    // Handle null or empty files
    if (!yaml_file || yaml_file.toString().isEmpty() || yaml_file.toString() == "[]") {
        return ""
    }
    
    def yaml = new org.yaml.snakeyaml.Yaml()
    def path = yaml_file instanceof java.nio.file.Path ? yaml_file : java.nio.file.Paths.get(yaml_file.toString())
    
    // Check if file exists before trying to read it
    if (!java.nio.file.Files.exists(path)) {
        return ""
    }
    
    def versions = yaml.load(new java.io.FileInputStream(path.toFile())).collectEntries { k, v -> [k.tokenize(':')[-1], v] }
    // ... rest of function
}
```

**Status**: ✅ Fixed - Forces specific `yaml.load(InputStream)` method, eliminates ambiguity

### ⭐ Integrate Variant Analysis Dashboard as NextFlow Process

**Status**: Research dashboard system developed and tested successfully
**Current implementation**: Standalone Python scripts in `bin/` folder
**Goal**: Convert to NextFlow process for automated dashboard generation

**Key Components Developed**:
- ✅ `bin/create_research_dashboard.py` - Main research tool (tested with 2,968 variants)
- ✅ `bin/summarize_variants.py` - Quick variant overview
- ✅ `bin/organize_results.sh` - Manual review structure
- ✅ Analysis-ready CSV outputs (sample_summary, gene_analysis, priority_variants)

**Integration Tasks**:
1. **Fix Mutect2 parsing**: Handle different VCF format (TLOD vs QUAL scores)
2. **Create NextFlow process**: `VARIANT_DASHBOARD` with proper input/output channels
3. **Add to main workflow**: Integration point after annotation, before reporting
4. **CNV integration**: Include Control-FREEC results in dashboard
5. **Documentation**: Update parameter documentation for dashboard options

**Expected Output**: 
- `research_dashboard/` directory with analysis tables
- Cross-sample variant comparison matrices
- Gene-level mutation burden analysis  
- Publication-ready CSV exports

**Priority**: High - Transforms raw VCFs into research-ready data following community best practices

### change mutect2 calling parameters for yeast genomes:
with yeast genome, there is no mutation resources, As --germline-resource is omitted, the parameter `--af-of-alleles-not-in-resource / -default-af` **is also omitted**.
Key parameters to focus on instead:
--af-of-alleles-not-in-resource: Set this based on your expected mutation rate (default 5e-8 is reasonable for most microbes)
--initial-tumor-lod: Lower this (e.g., to 0.5-1.0) if you want to detect very low-frequency variants early in evolution
--max-population-af: Set to 1.0 to allow any allele frequency (important for evolution experiments)
--downsampling-stride: Consider disabling downsampling (set to 1) for smaller yeast genomes


### update controlfreec parameters, e.g., window for yeast
### move this repo to org's github repo



### Better tracking of versioning

## Completed Tasks
- ✅ Fixed FreeBayes filtering configuration and output publishing
- ✅ Simplified FreeBayes somatic filtering subworkflow structure
- ✅ Resolved config pattern matching for BCFTOOLS_FILTER parameters
