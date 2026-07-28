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

The Tabulator filter config (`filter_config.yaml`) defines per-column filter types:
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
