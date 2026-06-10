4.3.0 Current yAMP design: 
yAMP is a forked version of nf-core/Sarek-3.5.1:
Originally developed for cancer research. Sarek preprocesses Illumina short-read data with GATK4 best-practice. For mutation calling it provides Germline (normal), Tumor-Only, and Tumor-Normal with a selection of variant calling tools.
For calling single-nucleotide polymorphisms (SNPs) and small insertions/deletions (indels): GATK-HaplotypeCaller cohort level joint genotyping mode is configured to generate both cohort and sample level Variant Call Format (VCF) files. 

For SVs detection: due to the lack of industry standard cohort genotyping solutions, CNVKit, TIDDIT were customized to generate per-sample VCF output for each tool. The VCF files can be annotated by SnpEff if the annotation cache is provided. yAMP generates a MultiQC report to summarize results from different processes: raw read quality stats, alignment results stats, and numbers of mutations reported by each tool.

Input:
Sample CSV table (adapted from nf-sarek):
Field
Description
experiment
Experiment ID (maps to "patient" in Sarek)
sample
Sample ID in standardized ALE format (e.g., A1-F6-I1-R1)
status
0 = normal/germline sample. Treat all samples as normal (0) unless for debugging unreleased variant calling tools.
clonal_or_population
clonal for clonal sample sequencing, population fosr bulk seq.
ploidy
Sample ploidy (1 = haploid, 2 = diploid)
sex
Required for Control-FREEC: "sex=XX" will exclude chr Y from the analysis
"sex=XY" will not annotate one copy of chr X and Y as a loss.
lane
Sequencing lane (e.g., L001)
fastq_1, fastq_2
Path to FASTQ files (relative to where nextflow is run, or blob path for Azure Batch)

Requirement: Each experiment must have one normal sample (status: 0)

Reference genome: (if the genome is not registered on https://github.com/nf-core/sarek/blob/3.5.1/conf/igenomes.config): provide reference genome (--fastq), SnpEff cache (--snpeff_cache), and SnpEff database name (--snpeff_db) 

ALE customized filter:
Variable allele frequency filter for HaplotypeCaller variants ( --split_haplotypecaller_joint_vcf --hard_filter_haplotypecaller_joint, custom_haplotypecaller_joint_filter.config:26):
AF>=5% for population samples
AF>=80% for clonal samples (relaxed from 90% in June 2026; see HARD_FILTER_HAPLOTYPECALLER_JOINT.md)
Enabling population mode for BreSeq (Not released): for population samples run `-p` polymorphism mode.

Next release variant calling candidates (Not fully customized/validated):
FreeBayes (SNP + InDel): lacks HaplotypeCaller’s joint calling mode, custom cohort joint VCF too noisy (multi-allelic sites normalization issues)
Control-FREEC (CNV): lacks standard VCF output, thus no functional annotation by SnpEff. Also crashes on some samples (std::length_error in v11.6b). See `docs/variant-calling/controlfreec/controlfreec_germline_changes.md`
  - Ottilie pilot (4 samples, S288C R64): no Control-FREEC crashes
  - Ottilie Tier 2 (86 samples, S288C R64): 4 samples crashed (exit 134 / SIGABRT), all `std::length_error` during copy number annotation:
    - `BMS983970-2R1e` (failed 3 times: initial + 2 retries)
    - `CBR868--15R3a`
    - `DDD01027481--11_R3a`
    - `MMV306025--R1-2`
    - Work dirs: `work_ottilie_tier2/{94,a3,76}/` (BMS983970), `26/` (CBR868), `f5/` (DDD01027), `c6/` (MMV306025)
    - Root cause: excessive breakpoint density triggers C++ vector overflow (e.g., mitochondrial chr)
    - Pipeline stopped after retry (global `errorStrategy = 'retry'`, `maxRetries = 1` in `bin/nextflow.config`)
    - TODO: set `errorStrategy = { task.exitStatus == 134 ? 'ignore' : 'retry' }` for `FREEC_.*` in `conf/modules/controlfreec.config` so pipeline continues past deterministic crashes
Always diploid: DeepVariant (SNP + InDel), Manta (SV), Mutect2 (SNP + InDel, too sensitive compared to HaplotypeCaller)
Always haploid: BreSeq (SNP, InDel, SV; docker build for only internal usage, not sub-processes optimized nor released)

Next iteration feature candidates:
Filter mutations by user defined frequency threshold
Filter mutations not detected by user defined starting strain sample
