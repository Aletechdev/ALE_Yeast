# Fix 6: MultiQC tar path length error — `bin/compare_mutect2_HpCaller/`

**Date**: 2026-04-20
**Error**: `java.lang.IllegalArgumentException: file name '...' is too long ( > 100 bytes)`
**Process**: `NFCORE_SAREK:SAREK:MULTIQC`

---

## Error message

```
Apr-20 12:11:46.262 [Actor Thread 52] DEBUG nextflow.processor.TaskProcessor - Handling unexpected condition for
  task: name=NFCORE_SAREK:SAREK:MULTIQC; work-dir=null
  error [java.lang.IllegalArgumentException]: file name 'usr/local/bin/compare_mutect2_HpCaller/CENPK_all/paper_a_benchmark/ALE_Exp1_A1-F6-I1-R1_benchmark.csv' is too long ( > 100 bytes)
```

## Root cause

Nextflow automatically stages **all files in `bin/`** into every task's working directory. This is by design — `bin/` is for pipeline helper scripts that processes can call.

The directory `bin/compare_mutect2_HpCaller/CENPK_all/paper_a_benchmark/` contains benchmark CSV files that are **not pipeline executables** — they're analysis/comparison data that was placed in `bin/` by mistake.

When Nextflow stages these files, the full path (`usr/local/bin/compare_mutect2_HpCaller/CENPK_all/paper_a_benchmark/ALE_Exp1_A1-F6-I1-R1_benchmark.csv` = 103 bytes) exceeds the **100-byte POSIX tar header limit**, causing a `java.lang.IllegalArgumentException` in the MULTIQC task.

## Affected files

```
bin/compare_mutect2_HpCaller/
└── CENPK_all/
    └── paper_a_benchmark/
        ├── ALE_Exp1_A1-F6-I1-R1_benchmark.csv   (103 bytes path)
        ├── ALE_Exp1_A3-F3-I1-R1_benchmark.csv
        ├── ALE_Exp1_A4-F5-I1-R1_benchmark.csv
        ├── ALE_Exp1_A5-F4-I1-R1_benchmark.csv
        ├── ALE_Exp1_A6-F6-I1-R1_benchmark.csv
        └── README.md
```

## All affected directories in `bin/`

The tar path length error is the immediate blocker, but **all non-script content in `bin/` causes unnecessary staging overhead** — every file is copied into every task's working directory on Azure Batch.

| Directory | Content type | Path length risk | Should move to |
|-----------|-------------|-----------------|----------------|
| `bin/compare_mutect2_HpCaller/` | Benchmark CSVs | **>100 bytes (breaks)** | `docs/` |
| `bin/benchmarking/adipic_acid_ale/results/` | Result CSVs, reports | 87 bytes (close to limit) | `docs/` |
| `bin/investigate_filter/` | Analysis Python scripts | 85 bytes (close) | `docs/` |
| `bin/prepare_input/` | One-time prep scripts (cache gen, samplesheet conversion) | 77 bytes | `docs/` or `scripts/` |
| `bin/compare_single_pop_HpCaller/` | Run scripts + samplesheets | 57 bytes | `docs/` |
| `bin/test/test_bcftools/` | Test VCF files | 55 bytes | `tests/` |

### Impact beyond path length

Even directories below 100 bytes cause problems:
- **Staging overhead**: Every Azure Batch task uploads/downloads all `bin/` files — adds latency to every task start
- **Storage waste**: Each of ~100+ pipeline tasks gets a full copy of benchmark data it never uses
- **Clutter**: Non-executable files in PATH produce confusing `command not found` noise in logs

## Fix

Move all non-pipeline-script content out of `bin/`:

```bash
git mv bin/compare_mutect2_HpCaller docs/compare_mutect2_HpCaller
git mv bin/benchmarking docs/benchmarking
git mv bin/investigate_filter docs/investigate_filter
git mv bin/prepare_input docs/prepare_input
git mv bin/compare_single_pop_HpCaller docs/compare_single_pop_HpCaller
git mv bin/test tests/
```

### What should remain in `bin/`

Only scripts that are **called by Nextflow processes** at runtime:

```
bin/
├── create_research_dashboard.py      # if used in VARIANT_DASHBOARD process
├── create_variant_dashboard.py       # if used in a process
├── summarize_variants.py             # if used in a process
├── organize_results.sh               # if used in a process
├── quick_variant_check.sh            # if used in a process
├── upload_test_data_azure.sh         # not a process script — move to scripts/
├── CENPK_run_sarek_351.sh            # pipeline launcher — move to scripts/
└── nextflow.config                   # local profile config — keep (loaded by NF)
```

**TODO**: Verify which `bin/*.py` and `bin/*.sh` scripts are actually referenced in process `script:` blocks before deciding final layout.

## Why `bin/` is special in Nextflow

From the Nextflow docs: files in the pipeline's `bin/` directory are automatically added to the `PATH` of every process execution. This means:
- Every file in `bin/` is copied/staged into every task's working directory
- Only executable scripts belong in `bin/`
- Data files, benchmarks, and analysis outputs should live elsewhere (`docs/`, `assets/`, `scripts/`, etc.)
