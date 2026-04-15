# Nextflow WGS Pipeline Benchmark

## Project Plan: Validation Against Published IVIEWGA Dataset

*Reference: Ottilie et al., Communications Biology 5:128 (2022)*

*Draft — April 2026*

---

## 1. Background and Motivation

The ALE (Adaptive Laboratory Evolution) software team maintains ALEdb.org and its associated computational pipelines. The current standard tool for analysing ALE whole-genome sequencing data is breseq, which was designed primarily for bacterial (prokaryotic) genomes. As ALE experiments increasingly involve eukaryotic organisms such as *Saccharomyces cerevisiae*, we need to evaluate whether breseq alone is sufficient or whether a Nextflow-based pipeline running on Azure can provide more comprehensive variant detection.

This project uses a published, manually curated dataset from Ottilie et al. (2022) as ground truth. The study performed in vitro evolution and whole-genome analysis (IVIEWGA) on 355 *S. cerevisiae* clones selected against 80 compounds, identifying 1,405 high-quality mutations (1,286 SNVs + 119 INDELs) and 24 copy number variant events. This curated dataset provides an ideal benchmark for pipeline validation.

## 2. Objectives

- Benchmark the current Nextflow WGS pipeline against a curated truth set of SNVs, INDELs, and CNVs from a eukaryotic ALE experiment.
- Quantify detection sensitivity and specificity for each variant class (SNVs, INDELs, whole-chromosome duplications, intrachromosomal amplifications).
- Document limitations of the current pipeline, particularly for CNV detection in eukaryotic genomes.
- Provide evidence-based recommendations to colleagues on why relying solely on breseq may be insufficient for eukaryotic ALE experiments.
- Establish a phased improvement roadmap for the Nextflow pipeline.

## 3. Reference Dataset Summary

The Ottilie et al. study used the ABC16-Green Monster strain of *S. cerevisiae* (16 ABC transporters deleted) and sequenced resistant clones to ~55× average coverage using short-read Illumina sequencing. Their analysis pipeline consisted of:

- Alignment to *S. cerevisiae* S288C reference genome (R64-2-1)
- Variant calling with GATK HaplotypeCaller
- Filtering: removal of variants shared between parent and resistant clones
- Annotation with SnpEff v4.3 and SGD metadata
- CNV detection via GATK DiagnoseTargets coverage-based algorithm (≥2–3× coverage, ≥3 consecutive genes)
- Statistical enrichment testing (Bonferroni-corrected hypergeometric test)

## 4. Benchmarking Strategy

The SNV/INDEL truth set and the CNV truth set draw from largely non-overlapping sample pools (only 3 of 23 CNV clones have SNV entries). Rather than constraining sample selection to the small overlap, the benchmark is structured as **two parallel tracks** that run together within each phase:

- **SNV/INDEL track:** Selects clones from Supplementary Data 4 (sub_4), prioritising high-mutation-count clones for maximum variant coverage per sample.
- **CNV track:** Selects clones from Supplementary Data 5 (sup_5), covering both whole-chromosome duplications and intrachromosomal amplifications.

All samples require the parent clone (ABC16-Green Monster) as baseline.

## 5. Phase 1: Baseline Benchmark (~30 SNV clones + 6 CNV clones)

### 5.1 SNV/INDEL Track: 30 Clones, ~306 Mutations

The top 30 clones by mutation count from sub_4, providing 306 mutations (22% of the full dataset) with coverage across all major effect types:

| Effect Type | Count | % of Full Dataset |
|-------------|-------|-------------------|
| Missense | 172 | 21% (of 830) |
| Intergenic | 79 | 29% (of 271) |
| Synonymous | 29 | 23% (of 127) |
| Stop gained | 13 | 13% (of 102) |
| Frameshift | 10 | 23% (of 43) |
| Splice / other | 3 | — |

The 30 clones selected (ranked by mutation count):

| Clone | Compound | Mutations |
|-------|----------|-----------|
| Doxorubicin-16--R2b | doxorubicin | 23 |
| GNFpf1618--6R2a | GNF-Pf-1618 | 16 |
| Carmaphycin--R9-2 | carmaphycin B | 15 |
| MMV000442--17-R5a | MMV000442 | 15 |
| MMV665882--16_R4a | MMV665882 | 15 |
| GNFpf445--1-R3b | GNF-Pf-445 | 11 |
| MMV665794--10R9c | MMV665794 | 11 |
| GNFpf2740--15_R5a | GNF-Pf-2740 | 10 |
| GNFpf445--2-R3b | GNF-Pf-445 | 10 |
| HygromycinB--36R8a | hygromycin B | 10 |
| Meb--1Res2a | mebendazole | 10 |
| MMV665794--7R9c | MMV665794 | 10 |
| Carmaphycin--R7-2 | carmaphycin B | 9 |
| GNFpf3891--3_R3a | GNF-Pf-3891 | 9 |
| GNFpf445--4-R3a | GNF-Pf-445 | 9 |
| MMV306025--R1-2 | MMV306025 | 9 |
| MMV403679--R9-2 | MMV403679 | 9 |
| MMV667491--R5b-2 | MMV667491 | 9 |
| DS33--R8-2 | GNF-Pf-5129 | 8 |
| HygromycinB--32R8a | hygromycin B | 8 |
| HygromycinB--35R8a | hygromycin B | 8 |
| MMV000442--15-R5a | MMV000442 | 8 |
| DS30MMV006389--R2-2 | MMV006389 | 8 |
| MMV007224--AR1a | MMV007224 | 8 |
| MMV306025--R4-2 | MMV306025 | 8 |
| MMV396736--12Res2a | MMV396736 | 8 |
| MMV665882--13_R4a | MMV665882 | 8 |
| CBR113--7-R4a | CBR113 | 8 |
| CBR110--8-R4a | CBR110 | 8 |
| TCMDC124263--10R3a | TCMDC-124263 | 8 |

### 5.2 CNV Track: 6 Clones, 6 CNV Events

Six clones selected to cover both CNV types (aneuploidy and intrachromosomal amplification) at varying sizes:

| Clone | Compound | CNV Type | CNV Chromosome |
|-------|----------|----------|----------------|
| BMS983970-2R1e | BMS-983970 | Aneuploidy | ChrX |
| Doxorubicin-24R3a | Doxorubicin | Aneuploidy | ChrIX |
| CBR110-15R3a | CBR110 | Aneuploidy | ChrI |
| Wortmannin-13R3a | Wortmannin | Amplification | ChrXV (~49 genes, includes YRR1 + YRM1) |
| MMV665794-8R9c | MMV665794 | Amplification | ChrXVI (~8 genes, ARR1 region) |
| GNF-Pf-1618-7R2b | GNF-Pf-1618 | Amplification | ChrXVI (~44 genes, large) |

Note: 3 of these CNV clones (BMS983970-2R1e, Doxorubicin-24R3a, CBR110-15R3a) also have SNV entries in sub_4 (6 SNVs total), providing a small set of samples testable on both tracks simultaneously.

### 5.3 Phase 1 Total Sample Count

- **~35 unique evolved clones** (30 SNV track + 6 CNV track, minus overlap)
- **1 parent clone** (ABC16-Green Monster)
- **~312 benchmark variants** (306 SNVs/INDELs + 6 CNV events)

### 5.4 Data Retrieval

#### Supplementary Truth Set Files

The benchmark truth sets are derived from supplementary data files published with the paper. These are pre-downloaded in `data/ottilie/supplementary/` for reproducibility, but can be re-fetched with:

```bash
mkdir -p data/ottilie/supplementary
cd data/ottilie/supplementary

# Supplementary Data 4: Full mutation list (1,405 SNVs + INDELs)
curl -L -o sup_4_42003_2022_3076_MOESM6_ESM.xlsx \
  "https://static-content.springer.com/esm/art%3A10.1038%2Fs42003-022-03076-7/MediaObjects/42003_2022_3076_MOESM6_ESM.xlsx"

# Supplementary Data 5: Copy number variants (24 CNV events)
curl -L -o sup_5_42003_2022_3076_MOESM7_ESM.xlsx \
  "https://static-content.springer.com/esm/art%3A10.1038%2Fs42003-022-03076-7/MediaObjects/42003_2022_3076_MOESM7_ESM.xlsx"

# Supplementary Data 7: CRISPR/Cas9 validation (nice-to-have)
curl -L -o sup_7_42003_2022_3076_MOESM9_ESM.xlsx \
  "https://static-content.springer.com/esm/art%3A10.1038%2Fs42003-022-03076-7/MediaObjects/42003_2022_3076_MOESM9_ESM.xlsx"
```

#### SRA Sequencing Data

Raw sequencing data for all 363 clones is deposited under NCBI BioProject **[PRJNA590203](https://www.ncbi.nlm.nih.gov/bioproject/PRJNA590203)**. Each clone has an internal "EAW clone #" identifier (visible in sub_4, column 3) that can be matched to SRA run accessions.

**EAW IDs for Phase 1 SNV-track clones:**

| Clone | EAW ID | Clone | EAW ID |
|-------|--------|-------|--------|
| Doxorubicin-16--R2b | EAW304 | MMV306025--R1-2 | EAW045 |
| GNFpf1618--6R2a | EAW248 | MMV403679--R9-2 | EAW014 |
| Carmaphycin--R9-2 | EAW131 | MMV667491--R5b-2 | EAW505 |
| MMV000442--17-R5a | EAW221 | DS33--R8-2 | EAW082 |
| MMV665882--16_R4a | EAW199 | HygromycinB--32R8a | EAW355 |
| GNFpf445--1-R3b | EAW412 | HygromycinB--35R8a | EAW357 |
| MMV665794--10R9c | EAW945 | MMV000442--15-R5a | EAW218 |
| GNFpf2740--15_R5a | EAW211 | DS30MMV006389--R2-2 | EAW038 |
| GNFpf445--2-R3b | EAW202 | MMV007224--AR1a | EAW932 |
| HygromycinB--36R8a | EAW305 | MMV306025--R4-2 | EAW048 |
| Meb--1Res2a | EAW152 | MMV396736--12Res2a | EAW157 |
| MMV665794--7R9c | EAW323 | MMV665882--13_R4a | EAW196 |
| Carmaphycin--R7-2 | EAW129 | CBR113--7-R4a | EAW439 |
| GNFpf3891--3_R3a | EAW190 | CBR110--8-R4a | EAW451 |
| GNFpf445--4-R3a | EAW200 | TCMDC124263--10R3a | EAW309 |

**EAW IDs for CNV-track clones with sub_4 overlap:** BMS983970-2R1e → EAW722, Doxorubicin-24R3a → EAW702, CBR110-15R3a → EAW744. The 3 CNV-only clones (Wortmannin-13R3a, MMV665794-8R9c, GNF-Pf-1618-7R2b) must be matched by clone name in the SRA metadata.

#### Sample Name Dictionary

Clone names differ between sup_4, sup_5, and SRA (e.g. double-dash `MMV665794--10R9c` in sup_4/SRA vs single-dash `MMV665794-10R9c` in sup_5; underscores vs dashes `GNFpf3891--3_R3a` vs `GNFpf3891--3-R3a`; abbreviations `Tavabarole-9Res2c` in sup_5 vs `Tav--9Res2c` in SRA). A cross-source mapping is pre-generated at `data/ottilie/sample_name_dictionary.csv` and can be regenerated with:

```bash
conda activate ottilie-benchmark
# Download RunInfo (if not present)
esearch -db sra -query PRJNA590203 | efetch -format runinfo > data/ottilie/PRJNA590203_runinfo.csv
# Build dictionary
python bin/benchmarking/ottilie_xenobiotic_ale/resolve_sra_accessions.py
```

Match rates: 352/355 sup_4 clones, 23/23 sup_5 clones, 1 parent clone. Three SRA-only samples (`DDD1035522--1R2a`, `CBR--14-R5a`, `MMV665794--R6-2`) have no sup_4 entries and are excluded from benchmarking.

**Parent clone (resolved):** The un-evolved ABC16-Green Monster parent is `NODRUG--GM2` → **SRR10985539** (3.2M read pairs, ~55x coverage).

#### Stage A Pilot SRR Accessions

| Sample | SRR Accession | EAW ID | Role | Read Pairs | Coverage | FASTQ Size |
|--------|---------------|--------|------|-----------|----------|------------|
| NODRUG--GM2 | SRR10985539 | — | Parent (baseline) | 3,216,392 | 53x | 549M |
| Doxorubicin-16--R2b | SRR10985527 | EAW304 | SNV track (23 mutations) | 6,997,828 | 116x | 1.1G |
| Carmaphycin--R9-2 | SRR10985678 | EAW131 | SNV track (15 mutations) | 12,911,855 | 213x | 1.6G |
| CBR110-15-R3a | SRR10985585 | EAW744 | CNV track (ChrI aneuploidy) | 6,280,120 | 104x | 787M |

All samples: paired-end 100bp reads. Coverage estimated against *S. cerevisiae* S288C (~12.1 Mb). Total compressed FASTQ: ~4 GB.

#### Downloading FASTQ Files

All tools are in the `ottilie-benchmark` conda environment (see `bin/benchmarking/ottilie_xenobiotic_ale/environment_data_retrieval.yml`):

```bash
conda env create -f bin/benchmarking/ottilie_xenobiotic_ale/environment_data_retrieval.yml
conda activate ottilie-benchmark
```

**Pilot download script** (downloads, converts to paired-end FASTQ, compresses):

```bash
cd <repo_root>
bash bin/benchmarking/ottilie_xenobiotic_ale/download_pilot_fastq.sh
```

The script uses `fasterq-dump` (streaming, no prefetch needed), skips already-downloaded samples, and cleans up partial files on retry. Requires `sra-tools=3.2.1` (3.4.1 has segfault bugs).

**Manual download for any single sample:**

```bash
mkdir -p data/ottilie/fastq
fasterq-dump SRR10985539 --split-files --outdir data/ottilie/fastq --threads 4
gzip data/ottilie/fastq/SRR10985539_1.fastq
gzip data/ottilie/fastq/SRR10985539_2.fastq
```

### 5.5 Pipeline Execution

The current compute environment is a single Azure VM used for development and processing. Phase 1 is split into two stages to validate the pipeline before committing to a larger production run:

**Stage A: Dev VM pilot (3–5 samples)**

Run a small subset on the existing dev VM to verify the pipeline works end-to-end with yeast data before scaling up:
- Pick 2–3 high-mutation SNV clones (e.g. Doxorubicin-16--R2b, Carmaphycin--R9-2) plus 1–2 CNV clones (e.g. CBR110-15R3a for aneuploidy, Wortmannin-13R3a for intrachromosomal amplification) and the parent clone.
- Run the full Nextflow pipeline with default parameters against *S. cerevisiae* S288C R64-2-1.
- Verify SNV/INDEL calls against the truth set; run both CNVkit and Control-FREEC and visually inspect coverage plots.
- Identify any parameter tuning needed for yeast (window sizes, ploidy settings, etc.).
- Estimate per-sample runtime and storage to project costs for the full batch.

**Stage B: Production run (all ~36 samples)**

Once Stage A confirms the pipeline works, scale up to the full Phase 1 sample set. Two options to evaluate:
- **Azure Batch:** Configure the Nextflow pipeline to submit jobs to Azure Batch for parallel processing, keeping the dev VM as the head node.
- **Seqera Cloud (Tower):** Set up the pipeline on Seqera Platform with an Azure Batch compute environment, providing a managed UI for monitoring runs, re-launching failed samples, and cost tracking.

The choice between Azure Batch (self-managed) and Seqera Cloud (managed) will depend on team preference and whether the organisation already has a Seqera licence. Either way, the goal is to avoid running 36+ samples sequentially on a single VM.

**For both stages:**
- Compare pipeline output (VCF, coverage summaries) against the truth sets defined above.
- Calculate sensitivity (% of truth set variants detected) per variant class and effect type.
- Document any additional variants called by the pipeline that are not in the truth set (potential false positives or novel findings).

### 5.6 CNV Tool Evaluation: CNVkit vs Control-FREEC

The original study used GATK DiagnoseTargets with a custom coverage-based algorithm for CNV detection. The current Nextflow pipeline does not include this specific tool, but **CNVkit and Control-FREEC are already integrated** as available processes. Both will be evaluated against the sup_5 truth set to determine which performs better for ALE-style eukaryotic CNV detection.

**CNVkit** (https://cnvkit.readthedocs.io/)
- Designed for hybrid capture and WGS data; supports a "flat" reference for WGS without a panel of normals.
- Uses the parent clone BAM as the normal reference to compute log2 copy ratios.
- Outputs segmented copy number calls per genomic bin; can detect both whole-chromosome and sub-chromosomal events.
- Key commands:
```bash
# Build reference from parent clone
cnvkit.py batch evolved.bam --normal parent.bam \
    --method wgs --fasta reference.fa \
    --output-dir cnvkit_out/

# Visualise per-chromosome coverage (useful for aneuploidy)
cnvkit.py scatter cnvkit_out/evolved.cnr -s cnvkit_out/evolved.cns
cnvkit.py diagram cnvkit_out/evolved.cnr -s cnvkit_out/evolved.cns
```

**Control-FREEC** (http://boevalab.inf.ethz.ch/FREEC/)
- Designed for WGS; automatically computes GC-content normalisation and mappability corrections.
- Can run with or without a matched normal (parent clone).
- Outputs predicted copy number per window and calls gains/losses with significance values.
- Key config parameters for yeast (small genome):
```
[general]
chrLenFile = S288C_R64-2-1.len
ploidy = 1
window = 1000
coefficientOfVariation = 0.05

[sample]
mateFile = evolved.bam

[control]
mateFile = parent.bam
```

**Evaluation criteria for both tools:**

| Criterion | What to measure |
|-----------|----------------|
| Aneuploidy detection | Can it flag ChrX, ChrIX, ChrI as duplicated (~2× coverage)? |
| Amplification detection | Can it identify the ChrXV and ChrXVI sub-chromosomal amplifications? |
| Boundary accuracy | How closely do called amplification boundaries match the gene lists in sup_5? |
| False positive rate | Does it call CNVs on chromosomes with no expected events? |
| Ease of use | How much parameter tuning is needed for yeast's small (~12 Mb) genome? |

Both tools will be run on all 6 CNV-track clones using the parent clone as the matched normal. Results will be compared side-by-side to determine which tool (or combination) to recommend as the default for eukaryotic ALE experiments, and whether parameter tuning is needed in Phase 3.

### 5.7 Known Limitations to Document

Beyond CNV detection, the current Nextflow pipeline is expected to have additional gaps that should be explicitly documented:

- **Parent-vs-evolved filtering:** The pipeline may not natively support pairwise comparison of evolved clones against a matched parent, which is essential for ALE experiments to distinguish selected mutations from background.
- **Yeast-specific annotation:** The pipeline may lack organism-specific annotation databases (SGD, Saccharomyces Genome Deletion Project essentiality data) that were used in the original study.
- **Small genome considerations:** Default tool parameters may be tuned for human-scale genomes; yeast's ~12 Mb genome may require adjusted window sizes, bin counts, or statistical thresholds for both variant calling and CNV detection.

### 5.8 Deliverables

- Benchmark report with concordance tables (pipeline calls vs. truth set) for each variant class and effect type.
- Sensitivity summary: "Pipeline detected X/172 missense, Y/79 intergenic, Z/13 stop-gained..." etc.
- **CNVkit vs Control-FREEC comparison report:** Detection rates for aneuploidy and intrachromosomal amplification, boundary accuracy, false positive rates, and recommendation for pipeline integration.
- Documentation of pipeline limitations with specific examples from the benchmark.
- Comparison table: Nextflow pipeline vs. breseq capabilities for eukaryotic ALE data.

## 6. Phase 2: Expanded Benchmark (~50 SNV clones + all CNV clones)

Phase 2 expands the sample set to strengthen the statistical evidence and cover additional edge cases.

### 6.1 SNV/INDEL Track Expansion

Expand from 30 to **50 clones**, increasing the truth set to **~446 mutations (32% of the full dataset)**:

| Effect Type | Phase 1 (30 clones) | Phase 2 (50 clones) | Full Dataset |
|-------------|---------------------|---------------------|--------------|
| Missense | 172 | 244 | 830 |
| Intergenic | 79 | 117 | 271 |
| Synonymous | 29 | 40 | 127 |
| Stop gained | 13 | 21 | 102 |
| Frameshift | 10 | 17 | 43 |
| Start lost | 0 | 3 | 8 |
| Other | 3 | 4 | 24 |
| **Total** | **306** | **446** | **1,405** |

Additional sample selection priorities for the 20 new clones:
- **Intergenic mutation clones:** Include clones with mutations in promoter regions (e.g. ERG9 upstream mutations) to verify annotation accuracy.
- **Mixed allele frequency clones:** The 8 "mixed" mutations in the dataset (non-clonal, <90% AF) are a useful test for caller sensitivity at lower allele fractions.
- **Diverse compounds:** Ensure coverage across different compound families to test for any compound-specific biases.

### 6.2 CNV Track Expansion

Expand to **all 23 CNV clones** from sup_5 (all 24 events), adding the remaining 17 clones:
- 8 additional aneuploidy clones
- 9 additional intrachromosomal amplification clones (including the remaining chr XVI ARR1-region amplifications at varying sizes)

### 6.3 Deliverables

- Expanded concordance matrix with confidence intervals for detection rates per variant class.
- Core evidence matrix: "breseq detects X%, Nextflow detects Y%" broken down by variant class — this is the key deliverable for communicating to colleagues.

## 7. Phase 3: Pipeline Improvements

Informed by gaps identified in Phases 1 and 2, Phase 3 focuses on extending the Nextflow pipeline to handle eukaryotic ALE data. Anticipated improvements include:

- **CNV detection optimisation:** Based on Phase 1 evaluation results, tune parameters of the better-performing tool (CNVkit, Control-FREEC, or both) for yeast-scale genomes. Establish recommended defaults for ALE experiments and validate against the full sup_5 truth set (all 24 events across 23 clones). If neither tool achieves acceptable sensitivity, implement the GATK DiagnoseTargets coverage-based approach used in the original study as a new Nextflow process.
- **Parent-vs-evolved filtering:** Implement a pairwise comparison step that subtracts parental variants from evolved clone calls, matching the IVIEWGA methodology.
- **Annotation enrichment:** Integrate SnpEff or VEP with organism-specific databases (SGD for yeast) and add statistical enrichment analysis for recurrently mutated genes.
- **Azure optimisation:** Profile compute costs and parallelisation for the expanded pipeline on Azure Batch.

## 8. Indicative Timeline

| Phase | Key Tasks | Deliverables | Est. Duration |
|-------|-----------|-------------|---------------|
| Phase 1a | Pilot pipeline on dev VM with 3–5 samples, verify end-to-end, tune parameters | Pilot results, per-sample cost estimate, parameter adjustments | 1–2 weeks |
| Phase 1b | Production run on all ~36 samples via Azure Batch or Seqera Cloud | Baseline benchmark report, CNVkit vs Control-FREEC comparison, breseq comparison table | 2–3 weeks |
| Phase 2 | Expand to ~50 SNV clones + all 23 CNV clones, stress-test edge cases | Expanded concordance matrix with confidence intervals | 2–3 weeks |
| Phase 3 | Tune CNV tools / add GATK DiagnoseTargets, parent filtering, annotation | Updated Nextflow pipeline with eukaryotic ALE support | 4–6 weeks |

## 9. Success Criteria

- **Phase 1a:** Pipeline runs end-to-end on yeast data; pilot SNVs detected; CNV tools produce interpretable coverage output; per-sample cost and runtime estimated.
- **Phase 1b:** Sensitivity reported per effect type across 306 mutations. CNV detection gaps clearly documented with specific examples from both aneuploidy and intrachromosomal amplification clones. Azure Batch or Seqera Cloud successfully used for parallel processing.
- **Phase 2:** Detection rates reported with confidence intervals across 446+ mutations and all 24 CNV events. Clear evidence matrix showing where breseq falls short on eukaryotic data.
- **Phase 3:** Pipeline detects both aneuploidy and intrachromosomal amplifications with ≥80% sensitivity against the full sup_5 truth set.

## 10. Risks and Mitigations

- **Raw data availability:** The original FASTQ files may not be publicly deposited. Mitigation: check SRA/ENA for the BioProject; if unavailable, contact authors or simulate reads from the published variant calls.
- **Parent clone identity:** The exact parent clone sequencing data must match what was used in the study. Mitigation: verify by checking for the 16 ABC transporter deletions in the Green Monster strain.
- **Single-person team:** As the sole FTE on the ALE software team, timeline may shift if other priorities arise. Mitigation: Phase 1 is scoped with clear deliverables; the two tracks (SNV and CNV) can be run in parallel or sequentially depending on availability.
- **Compute cost and scaling:** The dev VM can handle the Stage A pilot but not 36+ samples efficiently. Mitigation: Stage A provides per-sample cost estimates to forecast Azure Batch or Seqera Cloud costs before committing to the production run. Azure Batch setup or Seqera Cloud onboarding may take additional time if not already configured.
