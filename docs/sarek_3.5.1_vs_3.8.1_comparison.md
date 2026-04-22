# Sarek 3.5.1 vs 3.8.1 Comparison

## Overview

Sarek 3.8.1 (Feb 2025) introduces significant architectural changes from 3.5.1.
This document focuses on impacts to our custom yeast ALE pipeline.

**Source**: [nf-co.re/sarek/3.8.1](https://nf-co.re/sarek/3.8.1)

---

## Critical Breaking Changes for Our Pipeline

### 1. Custom VCF Filtering Removed

Our AF-based filtering subworkflows no longer exist in 3.8.1:

| Our Custom Module | Status in 3.8.1 | Replacement |
|---|---|---|
| `vcf_filter_freebayes/` | Removed | Varlociraptor framework |
| `vcf_filter_mutect2/` | Removed | Varlociraptor framework |
| `custom_haplotypecaller_joint_filter` | Removed | Built-in VQSR fallback |
| `custom_freebayes_filter.config` | Removed | `varlociraptor.config` |
| `custom_mutect2_filter.config` | Removed | `varlociraptor.config` |

**Migration options:**
- Adopt Varlociraptor for Bayesian variant filtering
- Re-implement custom subworkflows in `subworkflows/local/`
- Use simpler `--filter_vcfs` + `--bcftools_filter_criteria` params (new in 3.8.1)

### 2. Germline ControlFreec Removed

- **3.5.1**: `bam_variant_calling_germline_controlfreec` subworkflow exists
- **3.8.1**: Removed entirely — ControlFreec only in somatic/tumor-only workflows
- **Impact**: Our germline-mode ControlFreec for single haploid samples won't work
- **Workaround**: Use tumor-only mode or stick with CNVKit for germline CNV

### 3. Split Joint VCF Removed

- **3.5.1**: Our `split_joint_vcf/` subworkflow + `--split_haplotypecaller_joint_vcf` param
- **3.8.1**: Both removed (these were our custom additions, not upstream)
- **Impact**: Would need to re-add if upgrading

### 4. Breseq Support (Our Custom Addition)

- `--genbank` and `--breseq_args` parameters are our custom additions — never existed in vanilla Sarek
- `breseq.config` is our custom config
- Would need to be re-added to any 3.8.1-based fork

### 5. Nextflow Version Requirement

- **3.5.1**: `!>=24.04.2`
- **3.8.1**: `!>=25.10.2`

---

## Improvements Worth Adopting

### 1. VQSR Fallback (Already in our 3.5.1 fork)

3.8.1 added GATK VariantFiltration as fallback when VQSR fails — we already implemented
this in our fork (`VARIANTFILTRATION_FALLBACK`). Validates our approach.

### 2. Post-Variant Calling Framework (New)

New `POST_VARIANTCALLING` subworkflow with:
- **VCF normalization**: `--normalize_vcfs` — automatic `bcftools norm`
- **VCF filtering**: `--filter_vcfs` + `--bcftools_filter_criteria "-f PASS,."`
- **Consensus calling**: `--snv_consensus_calling` — multi-caller agreement

### 3. Null-Safety Improvements

3.8.1 adds null checks throughout:
```groovy
// 3.5.1
if (tools.split(',').contains('cnvkit'))
// 3.8.1
if (tools && tools.split(',').contains('cnvkit'))
```

### 4. Dual VCF+TBI Outputs

3.8.1 emits separate TBI channels for all variant callers, better for downstream joins.

---

## New Tools & Parameters

### New Variant Callers
| Tool | Type | Relevance to ALE |
|---|---|---|
| MuSE | Somatic | Low — cancer-focused |
| Sentieon TNscope | Somatic | Low — commercial, cancer-focused |
| Varlociraptor | Classification | Medium — could replace our custom filtering |

### New Parameters (37 total, key ones below)

```
# Post-variant calling
--filter_vcfs                    # Enable bcftools filtering
--bcftools_filter_criteria       # Filter expression (default: "-f PASS,.")
--normalize_vcfs                 # Run bcftools norm
--snv_consensus_calling          # Multi-caller consensus
--consensus_min_count            # Min callers agreeing (default: 2)

# Varlociraptor
--varlociraptor_scenario_germline   # Germline scenario YAML
--varlociraptor_scenario_somatic    # Somatic scenario YAML
--varlociraptor_chunk_size          # Chunk size for processing

# UMI support
--umi_in_read_header / --umi_location / --umi_length / --umi_base_skip

# Contamination filtering
--bbsplit_fasta_list / --bbsplit_index

# Annotation (VEP plugins)
--vep_condel / --vep_mastermind / --vep_phenotypes
--snpsift_databases

# Variant calling
--gatk_pcr_indel_model           # Default: CONSERVATIVE
--freebayes_filter               # Quality filter threshold (default: 30)
```

### Removed Parameters (upstream, existed in vanilla 3.5.1)
```
--filter_freebayes               # Replaced by --filter_vcfs
--freebayes_qual_threshold       # Replaced by --freebayes_filter
--freebayes_dp_threshold
--freebayes_af_threshold
--freebayes_high_impact
```

### Our Custom Parameters (never in vanilla Sarek, would need re-adding)
```
--genbank                          # Breseq GenBank reference input
--breseq_args                      # Breseq CLI arguments
--split_haplotypecaller_joint_vcf  # Split joint VCF into per-sample
--hard_filter_haplotypecaller_joint  # VQSR fallback soft filtering
```

---

## Architectural Differences

### Preprocessing
- **3.5.1**: All preprocessing steps in `main.nf` (~800 lines)
- **3.8.1**: Abstracted into `FASTQ_PREPROCESS_GATK` or `FASTQ_PREPROCESS_PARABRICKS` (~640 lines)

### Variant Filtering Paradigm
- **3.5.1**: Per-tool custom filters (our AF-based approach)
- **3.8.1**: Unified Varlociraptor framework + simple bcftools pass filter

### Profile Changes
- **Removed**: `arm` profile (Apple Silicon)
- **Added**: `arm64`, `emulate_amd64`, `gpu` profiles

### Plugin Changes
- **Added**: `nf-core-utils@0.4.0`, `nf-fgbio@1.0.0`
- **Updated**: `nf-schema` 2.2.1 → 2.6.1

### Dependency Updates
| Tool | 3.5.1 | 3.8.1 |
|---|---|---|
| GATK | 4.5.0.0 | 4.6.1.0 |
| VEP | 111.0 | 115.0 |
| MultiQC | 1.25.1 | 1.31 |

---

## Upgrade Decision Matrix

### Stay on 3.5.1 (Current Recommendation)

**Pros:**
- All our custom modifications work (AF filtering, germline ControlFreec, split joint VCF, breseq)
- Stable, tested with our yeast genomes
- No migration effort

**Cons:**
- Missing Varlociraptor, consensus calling, VCF normalization
- Older tool versions (GATK 4.5, VEP 111)
- Won't get upstream bug fixes

### Upgrade to 3.8.1

**Pros:**
- Latest tool versions
- Better post-variant calling framework
- Multi-caller consensus
- Active upstream maintenance

**Cons:**
- Must re-implement: AF filtering, germline ControlFreec, split joint VCF, breseq
- Must update Nextflow to >=25.10.2
- Significant testing effort

### Hybrid Approach (Recommended for Future)

Cherry-pick specific improvements from 3.8.1 into our 3.5.1 fork:
1. Null-safety improvements
2. VCF normalization post-processing
3. Consensus calling logic
4. Updated GATK/VEP containers

---

## Priority Assessment (April 2026)

**Verdict: Upgrade is NOT urgent. Stay on 3.5.1 fork.**

Our 3.5.1 fork is functional and tested on yeast data. Nothing in 3.8.1 unblocks
capabilities we need today. The following active workstreams are higher priority:

### Higher Priority Items

1. **Benchmarking variant callers** (ottilie-benchmark worktree)
   - Directly validates biological accuracy of our pipeline
   - Informs which tools to keep, tune, or drop
   - Must complete before any upgrade makes sense — no point migrating tools we might not keep

2. **Breseq as proper nf-core module**
   - Currently a custom bolt-on in our fork
   - Making it a proper module benefits both pipelines (AMP v1 merger question)
   - Prerequisite for community sharing and long-term maintainability
   - Effort is the same whether on 3.5.1 or 3.8.1

3. **Seqera Cloud deployment** (seqera-cloud worktree)
   - Enables scalable runs of the full Ottilie benchmark dataset (363 samples)
   - Feeds directly into benchmarking results (#1)
   - Cloud config is pipeline-version-independent

### When Upgrade Becomes Relevant

- If Varlociraptor proves better than our AF-based filtering for yeast ALE data
- If a GATK 4.6+ bugfix affects our variant calls
- If upstream stops maintaining 3.5.x containers (security/compatibility)
- If consensus calling (`--snv_consensus_calling`) adds value after benchmarking confirms which callers to trust

### Recommended Path Forward

1. **Now**: Complete benchmarking on 3.5.1 fork, deploy to Seqera Cloud
2. **After benchmarking**: Evaluate if Varlociraptor or consensus calling would improve results
3. **If upgrade justified**: Use hybrid approach — cherry-pick features, don't do full migration
4. **Long-term**: If starting a fresh project, use 3.8.1 as base and port our custom modules

---

## File Reference

```
nf-core-sarek_3.5.1/3_5_1/    # Our customized fork
nf-core-sarek_3.8.1/          # Vanilla 3.8.1 for comparison
```
