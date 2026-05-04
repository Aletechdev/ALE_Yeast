D1.1 Evaluate And Modify The nf-core/Sarek Pipeline
Description: The open source nf-core/Sarek pipeline was originally developed for cancer research for mutations calling using different variant calling tools. The evaluation of different mutation calling tools and settings is essential for selecting the tools for ALE mutation calling. For reference genome without extensive knowledge (e.g., genomes not registered on iGenome, without pre-calculated db for GATK’s BQSR and its downstream VQSR), custom Nextflow (sub)processes are required to generate the output VCF files.

Acceptance Criteria:
[ ] Review and select at least 1 SNP / InDel calling tool
[ ] Review and select at least 1 structural variant calling tool
[ ] Document the changes
[ ] Modify the nf-core/Sarek Pipeline

Exit Criteria:
[ ] Test data from D1.1 used to review and confirm full concordance
[ ] Documentation accessible on the GitHub repo and reviewed by stakeholders

---

## D1.1.1 Validate Pipeline Against Ottilie et al. (2022)

Description: Validate the customized nf-core/sarek 3.5.1 pipeline against published variant calls from
[Ottilie et al. (2022)](https://doi.org/10.1038/s42003-022-03076-7), a large-scale yeast ALE study
with 363 drug-resistant clones and CRISPR-validated causal mutations. This fulfills the D1.1 exit criterion:
*"Test data from D1.1 used to review and confirm full concordance."*

See [RESEARCH_CONTEXT.md](RESEARCH_CONTEXT.md) for full study details and tier rationale.

### Validation Tasks

#### Task 1: SNV/INDEL Concordance (HaplotypeCaller)

- **Truth set**: Sup. Data 4 — 1,405 mutations (1,286 SNVs + 119 INDELs) across 355 clones
- **Pipeline tool**: GATK HaplotypeCaller (joint germline, ploidy=1)
- **Metrics**:
  - [ ] Sensitivity (recall): fraction of Sup 4 mutations detected by HaplotypeCaller
  - [ ] Precision: fraction of HaplotypeCaller calls present in Sup 4
  - [ ] Per-sample concordance: identify samples with high/low agreement
- **Tier 1 scope**: 4 pilot samples (38 expected mutations)
- **Tier 2 scope**: 85 samples with CRISPR-validated mutations — highest-confidence subset
- **Notes**: Ottilie used breseq (+ manual curation) as their primary caller. Differences may reflect tool sensitivity, not pipeline errors.

#### Task 2: CRISPR-Validated Mutation Recovery

- **Truth set**: Sup. Data 7 — 45 CRISPR/Cas9-confirmed causal alleles in 37 genes
- **Scope**: 64 Tier 2 clones carrying these mutations (matched via gene + AA change)
- **Metrics**:
  - [ ] Recovery rate: fraction of CRISPR-validated mutations detected per tool
  - [ ] Per-gene breakdown: which genes/mutations are missed and why
- **Significance**: These are the highest-confidence variants — any missed call warrants investigation

#### Task 3: CNV Concordance (CNVKit + Control-FREEC)

- **Truth set**: Sup. Data 5 — 24 CNV events (11 aneuploidies + 13 amplifications) across 23 clones
- **Pipeline tools**: CNVKit and Control-FREEC
- **Metrics**:
  - [ ] Aneuploidy detection rate: whole-chromosome gains/losses
  - [ ] Amplification detection rate: intrachromosomal events (more challenging)
  - [ ] CNVKit vs Control-FREEC agreement
- **Tier 2 scope**: 23 CNV clones (21 CNV-only + 2 overlapping with CRISPR set)
- **Notes**: Ottilie used read depth ratio analysis; our tools use different algorithms (CBS segmentation, read count windows). Exact breakpoint concordance is not expected — focus on event-level agreement.

#### Task 4: Filter Parameter Evaluation

- **Scope**: Joint germline VariantFiltration fallback (since VQSR unavailable for custom genome)
- **Metrics**:
  - [ ] PASS rate vs truth set: are true mutations being filtered out?
  - [ ] Filter flag distribution: which filters remove the most true positives?
  - [ ] Recommend parameter adjustments for yeast ALE (current thresholds are GATK human defaults)
- **Deliverable**: Optimized filter thresholds for non-model organism ALE experiments

### Deliverables

| Deliverable | Description | Format |
|-------------|-------------|--------|
| Concordance report | Per-tool, per-sample variant agreement with truth set | CSV + summary |
| CNV benchmark report | CNVKit and Control-FREEC vs Sup 5 events | CSV + plots |
| CRISPR recovery table | Per-mutation detection status across tools | CSV |
| Parameter recommendations | Optimized filter thresholds for yeast ALE | Documentation |

### Optional: breseq Concordance (Future — Post Dev/Test/Deploy)

- **Truth set**: Sup. Data 4 (same as Task 1)
- **Pipeline tool**: breseq (integrated into Sarek fork)
- **Metrics**:
  - [ ] Sensitivity and precision vs Sup 4
  - [ ] Head-to-head: breseq vs HaplotypeCaller agreement and unique calls
- **Expected**: Higher concordance since Ottilie's truth set was generated with breseq
- **Notes**: breseq outputs GD format — need gdtools-based comparison or VCF conversion
- **Prerequisite**: breseq integration follows best-practice dev, test, and deploy workflow before inclusion in release
- **Rationale**: Current release scope focuses on GATK-based callers; breseq integration requires additional testing infrastructure

### Optional: Tier 3 — Full Cohort Replication (Nice to Have)

- **Scope**: All 363 sequenced clones from PRJNA590203
- **Purpose**: Scalability validation and population-level concordance statistics
- **Platform**: Seqera Cloud — tests cloud executor integration and parallel scheduling at scale
- **Metrics**:
  - [ ] Cohort-wide sensitivity/precision vs Sup 4 (1,405 mutations across 355 clones)
  - [ ] Mutation frequency spectrum comparison (pipeline vs published)
  - [ ] Seqera Cloud execution metrics (cost, runtime, scaling efficiency)
- **Prerequisite**: D1.1.1 Tasks 1–4 completed with Tier 2
- **Resources**: ~3.7 TB disk, ~1–2 days on cloud (see README resource estimates)

### Acceptance Criteria (Benchmark-Specific)

- [ ] ≥90% sensitivity for CRISPR-validated mutations (Task 2)
- [ ] ≥80% sensitivity for Sup 4 SNVs in Tier 2 samples (Task 1)
- [ ] ≥75% aneuploidy detection rate (Task 3)
- [ ] Documented explanation for any missed high-confidence variants
- [ ] Reproducible: all comparison scripts committed to `04_comparison/`
