# IGVReports - Interactive Variant Review

Standalone test of the [nf-core igvreports](https://nf-co.re/modules/igvreports) module for generating self-contained HTML reports from VCFs.

## Quick Start

```bash
# Fast run — VCF table only (no read pileups), ~10 seconds
bash docs/igvreports/run_igvreports_no_tracks.sh

# Full run — with CRAM tracks for IGV read pileups (very slow, see notes)
bash docs/igvreports/run_igvreports.sh
```

## What It Produces

A single HTML file with:
- **Variant table**: Sortable/filterable columns for CHROM, POS, REF, ALT, FILTER, INFO fields
- **Per-sample columns**: GT, AD, DP, GQ for all 17 samples (via `--sample-columns`)
- **IGV browser** (with tracks only): Embedded read pileups for each variant site

## Configuration

Report columns are controlled via `ext.args` in `nextflow.config`:
- `--info-columns FILTER AC AF AN DP FS MQ QD SOR` — INFO fields shown in table
- `--sample-columns GT AD DP GQ` — Per-sample FORMAT fields
- `--flanking 500` — Genomic region around each variant

## Performance Notes (April 2026)

| Run Type | Samples | Variants | Time | Peak RAM | HTML Size |
|----------|---------|----------|------|----------|-----------|
| No tracks (VCF only) | 17 | ~1,748 | ~10s | <1 GB | 8.9 MB |
| With 17 CRAMs | 17 | ~1,748 | >1h (killed) | ~10 GB | N/A |

**With-CRAMs run was terminated** after 1h18m CPU time at 10 GB / 12 GB RAM (83% memory).
The tool extracts read pileups for every variant site × every CRAM track, which scales
poorly with many samples. Consider:
- Subsetting to PASS-only variants first (`bcftools view -f PASS`)
- Running with 2-3 representative samples instead of all 17
- Using `--subsample 0.5` to reduce alignment data
- Using `--flanking 200` (default) instead of 500

## TODO — Follow-Up Work

### 1. Upgrade to igv-reports >= 1.15.0 for Tabulator Template

The nf-core module ships v1.12.0 which lacks the `--tabulator` flag.
v1.15.0+ adds a **Tabulator template** with filterable/sortable column headers
(closest UX to BreSeq's mutation summary table).

- **Flag**: `--tabulator` + `--filter-config filter_config.yaml`
- **Example**: https://igvteam.github.io/igv-reports/examples/example_vcf_tabulator.html
- **Releases**: https://github.com/igvteam/igv-reports/releases (v1.15.0+)

The filter config YAML defines per-column filter types:
```yaml
# Example filter_config.yaml for ALE data
- field: GENE
  type: string
  filter: contains
- field: FILTER
  type: string
  filter: list
- field: "sample:DP"
  type: number
  filter: range
  min: 0
  max: 500
- field: "sample:GQ"
  type: number
  filter: threshold
  value: 30
```

**Action**: Either update the nf-core module container to >= 1.15.0 or use a custom
container. Then add `--tabulator --filter-config` to `ext.args`.

### 2. Add Per-Sample Allele Frequency

HaplotypeCaller FORMAT fields include AD (allelic depths) but not AF.
Need to compute AF = AD[alt] / (AD[ref] + AD[alt]) per sample.

Options:
- **Pre-process VCF**: Use `bcftools +fill-tags -- -t FORMAT/AF` to add per-sample AF
  before passing to igvreports (easiest, adds FORMAT/AF field)
- **Post-process**: Calculate in the dashboard scripts instead
- **SnpSift**: `SnpSift extractFields` can compute on the fly

Example pre-processing:
```bash
bcftools +fill-tags input.vcf.gz -Oz -o with_af.vcf.gz -- -t FORMAT/AF
# Then pass with_af.vcf.gz to igvreports with --sample-columns GT AD DP GQ AF
```

### 3. Review INFO Columns for ALE Relevance

Current columns: `FILTER AC AF AN DP FS MQ QD SOR`

Consider adding/removing:
- **Add**: `ExcessHet`, `BaseQRankSum`, `MQRankSum`, `ReadPosRankSum` (useful QC)
- **Remove**: `AN` (always same for joint calling), `AC` (redundant with per-sample GT)
- **Review**: Whether INFO-level `AF` vs per-sample `AF` is more useful

### 4. Demo Reports Missing Soft-Filter INFO Columns

The demo report workflow ([generate_demo_reports.nf](generate_demo_reports.nf) lines 130, 178) uses
`--info-columns ANN VCF_FILTER ORIG_ALT AC AF DP QD MQ`, but the joint germline soft filter
(`VARIANTFILTRATION_FALLBACK` in `conf/modules/joint_germline.config`) evaluates these INFO fields:

| Field | In demo report? | Soft filter usage |
|-------|-----------------|-------------------|
| QD | Yes | `QD < 2.0` |
| MQ | Yes | `MQ < 40.0` |
| FS | **No** | `FS > 60.0` (SNP), `FS > 200.0` (INDEL) |
| SOR | **No** | `SOR > 3.0` (SNP), `SOR > 10.0` (INDEL) |
| MQRankSum | **No** | `MQRankSum < -12.5` |
| ReadPosRankSum | **No** | `ReadPosRankSum < -8.0` |

Without these columns, reviewers cannot see *why* a variant was flagged in the FILTER column.

**Action**: Add `FS SOR MQRankSum ReadPosRankSum` to `--info-columns` in both `IGVREPORTS_COHORT`
and `IGVREPORTS_SAMPLE` processes, and add corresponding entries to the Tabulator filter config YAML.

### 5. Review and Deliver SV IGVReports

A pilot SV report was generated for the Marko benchmark (`docs/benchmarking/marko_sv/generate_igvreport.sh`).
It produces two reports for E. coli K-12 sample SRR6281661:
- SNP/InDel report from HaplotypeCaller
- SV report from SURVIVOR merged union VCF (DEL/INV breakpoints with CRAM pileups)

**Action**: Review the SV report output, refine column selection and flanking region, and integrate
SV IGVReports into the main pipeline for delivery alongside SNP/InDel reports.

### 6. CRAM Track Feasibility

To make with-CRAMs runs viable on D4as (16 GB):
- Pre-filter to PASS-only: `bcftools view -f PASS` (~737 variants vs 1,748)
- Limit to 2-3 key samples (ancestral + 1-2 evolved)
- Use `--subsample 0.5` and `--flanking 200`

## Files

- `run_igvreports.nf` — Workflow with CRAM tracks
- `run_igvreports_no_tracks.nf` — Workflow without tracks (fast)
- `run_igvreports.sh` / `run_igvreports_no_tracks.sh` — Launch scripts
- `nextflow.config` — Shared config (Docker, publishDir, ext.args)

## References

- [nf-core igvreports module](https://nf-co.re/modules/igvreports)
- [igv-reports GitHub](https://github.com/igvteam/igv-reports)
- [Tabulator template example](https://igvteam.github.io/igv-reports/examples/example_vcf_tabulator.html)
- [igv-reports paper (bioRxiv 2025)](https://www.biorxiv.org/content/10.1101/2025.10.29.685397v1.full)
