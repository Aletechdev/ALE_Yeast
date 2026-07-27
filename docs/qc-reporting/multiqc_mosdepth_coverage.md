# MultiQC mosdepth coverage — median, mean, and thresholds

How coverage metrics from **mosdepth** appear in the MultiQC General Statistics table, why "mean
coverage" is *not* shown, and how the pipeline configures the coverage-threshold columns. Config lives
in [`assets/multiqc_config.yml`](../../assets/multiqc_config.yml).

## Key facts

- MultiQC's mosdepth module shows **median coverage**, **not mean** — it does **not** extract mean from
  `*.mosdepth.summary.txt` at all. Adding `table_columns_visible: mosdepth: mean_coverage: True` does
  nothing: that only toggles *visibility* of columns MultiQC already parsed, and mean was never parsed.
- **Median is the right metric anyway**: robust to the high-coverage outliers common in this data
  (e.g. mitochondrial DNA at thousands of ×), unlike the mean.
- Instead of chasing mean, the pipeline displays **median + a spread of coverage thresholds** (`≥Nx`),
  which is more informative than a single average.

## How MultiQC computes median coverage

Mosdepth does not emit a median. MultiQC derives it from the **cumulative** coverage distribution:

1. Reads `*.mosdepth.global.dist.txt` (`chrom  depth  proportion_of_bases_≥depth`) and builds a
   cumulative distribution per sample (100 % at 0×, decreasing as depth rises).
2. The **median** is the depth at which the cumulative proportion crosses **50 %** (50 % of bases have
   at least that coverage).
3. Stored in `multiqc_data/mosdepth_cumcov_dist.txt`; shown as "Median Coverage (Mosdepth)".

## The applied configuration (coverage thresholds)

`mosdepth` already computes the `≥Nx` percentage for every integer depth in `*.global.dist.txt`;
`mosdepth_config` just selects which to surface as columns. No custom parsing. Current config
([`assets/multiqc_config.yml`](../../assets/multiqc_config.yml)):

```yaml
mosdepth_config:
  general_stats_coverage:          # thresholds extracted as ≥Nx columns
    - 5
    - 10
    - 20
    - 30
    - 40
    - 50
    - 60
    - 70
    - 80
    - 90
    - 100
    - 150
    - 200
    - 250
    - 300
  general_stats_coverage_hidden:   # extracted but hidden by default (expandable)
    - 1
    - 5
    - 10
    - 30
    - 50
    - 70
    - 90
    - 150
    - 250
    - 300
```

`general_stats_coverage` = the thresholds to display; `general_stats_coverage_hidden` = extracted but
collapsed (reduces clutter from near-100 % low thresholds and near-0 % very-high ones). Tune per assay
(e.g. germline cares about 10–50×; deep sequencing about 100–300×).

## If you really need mean coverage

It's in the raw mosdepth output — `*.mosdepth.summary.txt`, `total` row, column 4:

```bash
grep '^total' <sample>.md.mosdepth.summary.txt | awk '{print $4}'   # e.g. 132.53
```

## Mosdepth output files (reference)

| File | Contents |
|------|----------|
| `*.mosdepth.summary.txt` | per-chrom + total stats incl. **mean** (col 4); no median |
| `*.mosdepth.global.dist.txt` | cumulative coverage distribution — the source MultiQC uses for median + `≥Nx` |
| `*.mosdepth.region.dist.txt` | same, per region (if `--by` used) |
| `multiqc_data/mosdepth_cumcov_dist.txt` | MultiQC's parsed cumulative distribution |

## References

- MultiQC mosdepth module: https://github.com/MultiQC/MultiQC/blob/main/docs/markdown/modules/mosdepth.md
- Config: [`assets/multiqc_config.yml`](../../assets/multiqc_config.yml)
