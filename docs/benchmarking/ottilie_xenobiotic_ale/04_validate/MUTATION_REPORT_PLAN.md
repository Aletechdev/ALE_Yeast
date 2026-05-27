# Mutation Overview Report — Planning Notes

**Date**: 2026-05-27
**Status**: Pre-planning — reviewing data available before designing the report

## Goal

Generate a cohort-level mutation overview report (HTML dashboard) that summarizes
SNV/INDEL, CNV, and SV across all samples. Similar to the IGV reports dashboard
(`docs/igvreports/demo/index.html`) but focused on cohort-wide patterns.

## Pipeline Integration Path

```
Pipeline output (per-sample VCFs/CNS)
    │
    ├── build_cn_matrix.py ──────► cn_matrices/*.csv
    │                                    │
    │                              cn_cohort_matrix.py ──► cn_cohort_matrix.csv
    │
    ├── sv_characterization.py ──► sv_merged/*.vcf.gz
    │                                    │
    │                              sv_cohort_matrix.py ──► sv_cohort_matrix.csv
    │
    └── snv_indel (existing) ────► annotated VCFs
                                         │
                                    ┌────┴────┐
                                    ▼         ▼
                            generate_report.py + Jinja2 template
                                    │
                                    ▼
                          Mutation Overview Report (HTML)
                          ├── SNV/INDEL variant table (existing)
                          ├── CN heatmap (samples × chromosomes)
                          ├── SV event matrix (samples × events)
                          └── MultiQC alignment stats (existing)
```

---

## Data Inventory: What's Available Now

### 1. CN Cohort Matrix (`cn_cohort_matrix.csv`)

**Source chain**: CNVKit `.call.cns` + `.cnr` → `build_cn_matrix.py` → `cn_cohort_matrix.py`

**Columns**: `chromosome, start, end, {sample}_log2, {sample}_cn, {sample}_diploid_cn`

- `{sample}_log2` — continuous log2 ratio from `.cnr` bins (~5kb resolution, 2,414 rows)
- `{sample}_cn` — continuous absolute CN (`ploidy × 2^log2`), fractional
- `{sample}_diploid_cn` — **integer** CN from segment-level calls, mapped onto bins via bisect

**CN scale note**: CNVKit always uses cn=2 as baseline regardless of biological ploidy.
cn=2 = normal, cn>2 = gain, cn<2 = loss.

**Upstream matrices also available** (in `cn_matrices/`):
| File | Level | Rows (pilot) | Key columns |
|------|-------|-------------|-------------|
| `cn_chr_summary_sensitive.csv` | chromosome | 16 × N samples | log2, diploid_cn per chr |
| `cn_chr_summary_stringent.csv` | chromosome | 16 × N samples | same, CI-filtered |
| `cn_segments_sensitive.csv` | segment | ~74 | sample, chrom, start, end, log2, diploid_cn, p_ttest |
| `cn_segments_stringent.csv` | segment | ~74 | same, from `.germline.call.cns` |
| `cn_sensitive_vs_stringent.csv` | comparison | ~74 | shows where two methods disagree |
| `cn_bins_continuous.csv` | bin (~5kb) | 2,414 | chromosome, start, end, {sample}_log2, {sample}_cn |

**For the report, most useful levels**:
- **Chromosome summary** → heatmap table (samples × 16 chromosomes, color by CN)
- **Segments** → detailed CNV event table (filterable)
- **Bins** → genome-wide CN profile plot (if we add visualization)

### 2. SV Cohort Matrix (`sv_cohort_matrix.csv`)

**Source chain**: Manta + TIDDIT VCFs → `sv_characterization.py` (SURVIVOR merge per sample) → `sv_cohort_matrix.py` (SURVIVOR merge across samples)

**Columns**: `chrom, pos, chrom2, end, svtype, svlen, {sample1}, {sample2}, ...`

Sample cells contain: `Manta`, `TIDDIT`, `Manta+TIDDIT`, or `-`

**Current filtering level**: Uses **per-sample union VCFs** (unfiltered, min_callers=1).
This is the most inclusive — all Manta + TIDDIT calls, no PASS filter.

**Available per-sample SURVIVOR VCFs** (4 types per sample):

| VCF type | Description | Callers required | Input filter |
|----------|-------------|-----------------|--------------|
| `union.vcf.gz` | **Currently used** — all calls | 1 (either caller) | None |
| `consensus.vcf.gz` | High-confidence | 2 (both callers) | None |
| `union_pass.vcf.gz` | All calls, PASS only | 1 | PASS filter |
| `consensus_pass.vcf.gz` | Most stringent | 2 | PASS filter |

**Pilot stats** (4 samples):
- Union (current): 426 cohort events, 115 shared, 311 private
- Not yet generated for other filtering levels

**For the report, key questions**:
- Show all 426 union events? Or filter to consensus (both callers agree)?
- Show separate tabs/layers for different confidence levels?
- SV types in pilot: DEL, DUP, INV, TRA (translocations have chrom2 ≠ chrom)

### 3. SNV/INDEL (existing)

Already handled by `snv_indel_concordance.py` and the IGV reports dashboard.
Annotated VCFs available from FreeBayes (germline), Mutect2 (somatic), HaplotypeCaller (joint + individual).

### 4. SV Characterization Summary (`sv_characterization.csv`)

Per-sample SV summary (not cohort-wide):
- Columns: `sample, manta_total, manta_pass, tiddit_total, tiddit_pass, union, consensus, ...`
- Includes parent subtraction stats (evolved-unique counts)
- Useful for a sample-level SV burden table in the report

---

## Open Questions for Report Design

### Q1: SV filtering level for the report
- **Option A**: Show union (all calls) — maximally inclusive, may have noise
- **Option B**: Show consensus (both callers) — higher confidence, fewer events
- **Option C**: Show both as tabs/layers — let user toggle
- **Option D**: Add `--sv-source` flag to `sv_cohort_matrix.py` to select input VCF type

### Q2: CN display granularity
- **Option A**: Chromosome-level heatmap only (16 rows × N samples) — compact
- **Option B**: Segment-level table (filterable, shows breakpoints) — detailed
- **Option C**: Both — heatmap for overview, expandable segment detail

### Q3: Parent subtraction
- Should the report show raw events or parent-subtracted (evolved-unique) events?
- SV characterization already does parent subtraction per sample
- CN matrices don't currently subtract parent — all samples shown equally

### Q4: What constitutes "one report"?
- One HTML file per pipeline run (cohort-level)?
- Per-sample reports + cohort summary?
- Match the existing IGV reports structure?

---

## Dependencies

- `cn_cohort_matrix.py` — done, tested on pilot
- `sv_cohort_matrix.py` — done, tested on pilot
- `build_cn_matrix.py` — done, tested on pilot
- `sv_characterization.py` — done, tested on pilot
- IGV reports template system — exists at `docs/igvreports/templates/`
- Marko SV dashboard CSS — exists at `docs/benchmarking/marko_sv/sv_comparison/report/`

## Next Steps

1. Review this plan and decide on filtering/display options
2. Design HTML template mockup
3. Implement `generate_report.py`
4. Add Nextflow process definitions (`BUILD_CN_MATRIX`, `SV_COHORT_MATRIX`, `MUTATION_REPORT`)
