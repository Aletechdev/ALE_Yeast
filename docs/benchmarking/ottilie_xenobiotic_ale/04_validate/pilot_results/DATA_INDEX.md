# Pilot Results — Data Index

**Samples**: CBR110-15-R3a, Carmaphycin-R9-2, Doxorubicin16-R2b, NODRUG-GM2 (parent)
**Pipeline**: nf-core/sarek 3.5.1 (forked), CNVKit + Manta + TIDDIT
**CN scale**: CNVKit uses cn=2 as baseline (diploid scale). cn=2 = normal, cn>2 = gain, cn<2 = loss.

## CN Tables

| File | Rows | Source | Description |
|------|------|--------|-------------|
| `cn_chr_summary_sensitive.csv` | 16 | `.call.cns` (re-centered, has p_ttest) | One row per chromosome. Columns: chromosome, length, {sample}_diploid_cn, {sample}_log2, {sample}_absolute_cn. Best for a compact chromosome × sample heatmap. |
| `cn_chr_summary_stringent.csv` | 16 | `.germline.call.cns` (CI-filtered, no re-centering) | Same format as sensitive. Higher confidence — segments with CI spanning zero are dropped. |
| `cn_cohort_collapsed_sensitive.csv` | 22 | `.call.cns` segments mapped onto ~5kb bins, collapsed | Adjacent bins with identical diploid_cn across all samples merged into regions. Columns: chromosome, start, end, {sample}_log2, {sample}_cn (continuous), {sample}_diploid_cn (integer). Shows exact CNV boundaries. |
| `cn_cohort_collapsed_stringent.csv` | 22 | `.germline.call.cns` segments mapped onto ~5kb bins, collapsed | Same format as sensitive collapsed. One CN difference vs sensitive: CBR110 chr VI (cn=2 sensitive vs cn=3 stringent — re-centering threshold flip at log2≈0.2). |

### Sensitive vs Stringent

- **Sensitive** (`.call.cns`): Re-centered log2, retains all segments, includes p_ttest. Better for ALE mixed-population samples where subclonal signals are weak.
- **Stringent** (`.germline.call.cns`): CI-filtered, no re-centering. Fewer false positives, matches VCF export. Better for clonal ALE samples with clear signal.
- **Pilot difference**: Only 1 CN call differs — CBR110-15-R3a chr VI (cn=2 vs cn=3).

## SV Tables

| File | Rows | Source | Description |
|------|------|--------|-------------|
| `sv_cohort_matrix_union.csv` | 426 | Per-sample SURVIVOR union VCFs (all Manta + TIDDIT, no PASS filter) | One row per SV event. Columns: chrom, pos, chrom2, end, svtype, svlen, {sample}. Sample cells: `Manta`, `TIDDIT`, `Manta+TIDDIT`, or `-`. Most inclusive — contains low-confidence calls. |
| `sv_cohort_matrix_union_pass.csv` | 105 | Per-sample SURVIVOR union_pass VCFs (all Manta + TIDDIT, PASS-filtered input) | Same format. ~75% noise reduction vs union. Recommended default for the report. |
| `sv_cohort_merged_union.vcf.gz` | 426 | Cohort-level SURVIVOR merge VCF | Standard VCF format with N-sample SUPP_VEC. For IGV/bcftools compatibility. Indexed (.tbi). |
| `sv_cohort_merged_union_pass.vcf.gz` | 105 | Cohort-level SURVIVOR merge VCF (PASS-filtered) | Same format, PASS-filtered input. Indexed (.tbi). |

### SV Filtering Tiers

| Tier | Callers required | PASS filter | Pilot events | Notes |
|------|-----------------|-------------|-------------|-------|
| `union` | 1 (either) | No | 426 | All calls, most inclusive |
| `union_pass` | 1 (either) | Yes | 105 | PASS-filtered, good balance |
| `consensus` | 2 (both) | No | not yet generated | High confidence |
| `consensus_pass` | 2 (both) | Yes | not yet generated | Most stringent |

### SV Type Distribution (union_pass, 105 events)

| Type | Description |
|------|-------------|
| DEL | Deletion |
| DUP | Duplication |
| INV | Inversion |
| TRA | Translocation (chrom2 ≠ chrom) |

## Other Files

| File | Description |
|------|-------------|
| `snv_indel_concordance.csv` | SNV/INDEL concordance vs Ottilie Sup Data 4 (98.8% on Tier 2) |
| `cnv_concordance.csv` | CNV concordance vs Ottilie Sup Data 5 truth set |
| `sv_characterization.csv` | Per-sample SV summary (Manta/TIDDIT counts, parent subtraction) |
| `cn_cohort_matrix.csv` | Full bin-level matrix (2,414 rows) — not collapsed, with diploid_cn overlay |
| `VALIDATION_REPORT.md` | Unified validation report |
