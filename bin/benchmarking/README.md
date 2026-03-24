# Benchmarking

Variant calling benchmarking studies comparing tools in the ALE Nextflow pipeline.

Each subfolder is a self-contained benchmark study with its own scripts, results, and data provenance documentation.

## Studies

| Study | Organism | Data | Tools Compared | Status |
|-------|----------|------|----------------|--------|
| [adipic_acid_ale](adipic_acid_ale/) | *S. cerevisiae* CEN.PK113-7D | Private (Azure) | breseq vs HaplotypeCaller | Complete |

## Adding a New Study

1. Create a subfolder: `bin/benchmarking/<study_name>/`
2. Add numbered scripts: `01_*.py`, `02_*.py`, etc.
3. Include `README.md` with study details, execution order, and conventions
4. Commit result snapshots to `results/` with `README_DATA_PROVENANCE.md`
5. Update this table

## Common Structure

```
<study_name>/
├── README.md                    # Study docs, execution order, conventions
├── 01_precision_recall.py       # Truth set comparison
├── 02_tool_comparison.py        # Cross-tool concordance
├── 03_summary_report.py         # Executive summary generator
└── results/
    ├── README_DATA_PROVENANCE.md  # Data sources, access, citation
    ├── BENCHMARKING_SUMMARY.md    # Generated report
    └── *.csv                      # Result tables
```
