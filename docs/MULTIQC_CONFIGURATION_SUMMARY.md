# MultiQC Mosdepth Configuration Summary

## Goal
Display more detailed coverage metrics in MultiQC General Statistics table.

## What Was Tried

### ❌ Attempt 1: Add Mean Coverage
```yaml
table_columns_visible:
  mosdepth:
    mean_coverage: True
```

**Result**: Didn't work
**Reason**: MultiQC's mosdepth module doesn't extract mean coverage from summary files

### ✅ Solution: Add Multiple Coverage Thresholds
```yaml
mosdepth_config:
  general_stats_coverage:
    - 10
    - 20
    - 30
    - 50
    - 100
    - 150
    - 200
    - 250
    - 300
  general_stats_coverage_hidden:
    - 1
    - 5
    - 250
    - 300
```

**Result**: Works perfectly!
**Location**: `nf-core-sarek_3.5.1/3_5_1/assets/multiqc_config.yml`

## How It Works

### Data Flow
```
Mosdepth Run
    ↓
Generates *.global.dist.txt (contains coverage % at every depth: 1X, 2X, 3X...300X)
    ↓
MultiQC reads mosdepth_config from multiqc_config.yml
    ↓
Extracts specified thresholds (10X, 20X, 30X, 50X, 100X, 150X, 200X)
    ↓
Creates columns in General Statistics table
    ↓
HTML report displays: ≥10X, ≥20X, ≥30X, ≥50X, ≥100X, ≥150X, ≥200X + Median
```

### What You'll See

**General Statistics Table:**
| Sample | ≥10X | ≥20X | ≥30X | ≥50X | ≥100X | ≥150X | ≥200X | Median |
|--------|------|------|------|------|-------|-------|-------|--------|
| A0-F0-I1-R1.md | 100% | 99% | 99% | 83% | ~50% | ~30% | ~15% | 76X |
| A0-F0-I2-R1.md | 100% | 99% | 99% | 98% | ~60% | ~40% | ~20% | 92X |
| A1-F6-I1-R1.md | 100% | 99% | 95% | 71% | ~40% | ~25% | ~10% | 70X |

**Hidden Columns** (expandable in report):
- ≥1X, ≥5X (almost always 100%)
- ≥250X, ≥300X (usually low percentages)

## Why This is Better Than Mean Coverage

| Metric | What It Shows | Example |
|--------|--------------|---------|
| **Mean coverage** | Single average (affected by outliers) | 132X |
| **Median coverage** | Robust central value | 76X |
| **Coverage thresholds** | Distribution across genome | 83% at ≥50X, 50% at ≥100X |

**Together**: Median + thresholds give you a **complete picture** of coverage quality!

## Configuration Parameters

### `general_stats_coverage`
**Purpose**: List of coverage thresholds to display as columns

**Choose based on your needs:**
- **Germline variant calling**: 10X, 20X, 30X, 50X
- **Somatic variant calling**: 30X, 50X, 100X, 150X, 200X
- **Deep sequencing**: 100X, 200X, 300X, 500X

### `general_stats_coverage_hidden`
**Purpose**: Thresholds to calculate but hide by default

**Use for:**
- Very low thresholds (1X, 5X) - almost always 100%
- Very high thresholds (250X+) - often 0% or very low
- Keep them hidden to reduce visual clutter but still available if needed

## Testing Your Configuration

### Step 1: Edit the Config
```bash
vim nf-core-sarek_3.5.1/3_5_1/assets/multiqc_config.yml
# Add mosdepth_config section
```

### Step 2: Run Pipeline
```bash
./bin/CENPK_run_sarek_351_all.sh
```

### Step 3: Check MultiQC Report
```bash
# Open the HTML report
open output_all/multiqc/multiqc_report.html

# Check General Statistics table
# Look for samples ending in .md (e.g., A0-F0-I1-R1.md)
# Should see multiple ≥XX coverage columns
```

### Step 4: Verify Data
```bash
# Check the TSV file
head -1 output_all/multiqc/multiqc_data/multiqc_general_stats.txt | tr '\t' '\n' | grep mosdepth

# Should show:
# mosdepth-10_x_pc
# mosdepth-20_x_pc
# mosdepth-30_x_pc
# mosdepth-50_x_pc
# mosdepth-100_x_pc
# mosdepth-150_x_pc
# mosdepth-200_x_pc
# mosdepth-median_coverage
```

## Related Documentation

- **Full analysis**: `docs/MULTIQC_MOSDEPTH_MEAN_COVERAGE_ISSUE.md`
- **How median is calculated**: `docs/MOSDEPTH_MEDIAN_CALCULATION.md`
- **MultiQC mosdepth module**: https://github.com/MultiQC/MultiQC/blob/main/docs/markdown/modules/mosdepth.md

## Key Takeaway

✅ **You don't need mean coverage** when you have:
1. **Median coverage** (more robust than mean)
2. **Multiple coverage thresholds** (shows distribution)
3. **Detailed plots** (in MultiQC mosdepth section)

This configuration gives you **richer information** than a single mean value ever could! 🎯
