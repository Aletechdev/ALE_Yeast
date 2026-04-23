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

## Files

- `run_igvreports.nf` — Workflow with CRAM tracks
- `run_igvreports_no_tracks.nf` — Workflow without tracks (fast)
- `run_igvreports.sh` / `run_igvreports_no_tracks.sh` — Launch scripts
- `nextflow.config` — Shared config (Docker, publishDir, ext.args)
