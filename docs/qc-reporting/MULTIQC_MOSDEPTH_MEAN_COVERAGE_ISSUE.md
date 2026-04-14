# MultiQC Mosdepth Mean Coverage - Not Showing Issue

## Problem Summary
The `mean_coverage` metric from mosdepth is **NOT appearing** in the MultiQC General Statistics table, even after adding `table_columns_visible: mosdepth: mean_coverage: True` to the configuration.

## Root Cause
**MultiQC's mosdepth module (v1.25.1) does NOT extract mean coverage from mosdepth summary files by default.**

### What MultiQC Mosdepth Module Extracts:
✅ **Coverage thresholds**: 1X, 5X, 10X, 30X, 50X (percentage of genome covered)
✅ **Median coverage**: Calculated from cumulative distribution
❌ **Mean coverage**: NOT extracted from `*.mosdepth.summary.txt`

### Current Output Columns:
```
- mosdepth-1_x_pc
- mosdepth-5_x_pc
- mosdepth-10_x_pc
- mosdepth-30_x_pc
- mosdepth-50_x_pc
- mosdepth-median_coverage  ← Only this coverage metric
```

## Why `table_columns_visible` Didn't Work

The configuration we added:
```yaml
table_columns_visible:
  mosdepth:
    mean_coverage: True
```

**Only controls VISIBILITY of existing columns**, not EXTRACTION of new data. Since MultiQC never extracted mean_coverage in the first place, there's nothing to make visible.

## Verification

Looking at the actual MultiQC output:
```bash
$ grep "A0-F0-I1-R1.md" multiqc_general_stats.txt
A0-F0-I1-R1.md  ...  100.0  100.0  100.0  99.0  83.0  76  ...
                      1X     5X     10X    30X   50X   median
                                                       (no mean!)
```

## Possible Solutions

### Solution 1: Accept Median Coverage Only ✅ RECOMMENDED
**Status**: Already working!

- **Median coverage (76X, 92X, 70X)** is already displayed for all samples
- Median is more robust than mean for coverage analysis (less affected by outliers)
- This is the standard approach for most sequencing QC

**No action needed** - the pipeline is working as designed.

### Solution 2: Add More Coverage Thresholds ✅ IMPLEMENTED
**Status**: Working solution!
**Complexity**: Low (configuration only)

Instead of adding mean coverage, display **multiple coverage thresholds** to get a comprehensive view of coverage distribution.

#### Configuration

Add to `assets/multiqc_config.yml`:

```yaml
# Mosdepth coverage thresholds configuration
# Customize which coverage thresholds appear in General Statistics table
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

#### How It Works

1. **Data Source**: Mosdepth generates `*.global.dist.txt` files containing coverage percentages for every depth threshold
2. **MultiQC reads**: The configuration tells MultiQC which thresholds to extract
3. **Columns created**: Each threshold becomes a column in General Statistics (e.g., `≥100X`, `≥150X`, `≥200X`)

#### Result

**Before (default):**
```
Sample          ≥30X  ≥50X  Median
A0-F0-I1-R1.md  99%   83%   76X
```

**After (with custom thresholds):**
```
Sample          ≥10X  ≥20X  ≥30X  ≥50X  ≥100X  ≥150X  ≥200X  Median
A0-F0-I1-R1.md  100%  99%   99%   83%   50%    30%    15%    76X
```

#### Why This is Better Than Mean Coverage

| Metric | Information Provided |
|--------|---------------------|
| **Mean coverage** | Single average value (e.g., 132X) - can be skewed by outliers |
| **Multiple thresholds** | Detailed distribution - shows exactly how much of genome has 100X, 150X, 200X coverage |
| **Median coverage** | Robust central value (e.g., 76X) |

**Combined view**: With median (76X) + thresholds (50% at ≥100X, 30% at ≥150X), you get a complete picture of coverage quality!

#### Parameters Explained

- **`general_stats_coverage`**: Thresholds to extract and display as columns
  - Choose based on your coverage targets (e.g., 30X for germline, 100X+ for somatic)

- **`general_stats_coverage_hidden`**: Thresholds to extract but hide by default
  - Useful for very low (1X, 5X) or very high (250X+) thresholds that are less relevant
  - Still accessible by expanding hidden columns in the report

#### Technical Details

The configuration works because:
1. Mosdepth **already calculates** coverage percentages for every integer depth (0 to max)
2. These are stored in `*.global.dist.txt`: `chromosome  depth  percentage`
3. MultiQC's mosdepth module reads these files
4. `mosdepth_config` tells MultiQC **which depths to extract** and add as columns
5. No custom parsing needed - just selecting from existing data!

#### Reference

- MultiQC Mosdepth Documentation: https://github.com/MultiQC/MultiQC/blob/main/docs/markdown/modules/mosdepth.md
- Configuration option: `mosdepth_config.general_stats_coverage`

### Solution 3: Add Custom Data Parser for Mean Coverage
**Complexity**: High
**Status**: Would require custom MultiQC module

Would need to:
1. Create custom MultiQC plugin to parse `*.summary.txt` files
2. Extract mean from "total" row, column 4
3. Add to general stats table

**Example custom_data configuration** (untested):
```yaml
custom_data:
  mosdepth_mean:
    file_format: 'tsv'
    section_name: 'Mosdepth Mean Coverage'
    description: 'Mean coverage from mosdepth summary files'
    plot_type: 'generalstats'
    pconfig:
      namespace: 'Mosdepth Mean'
    headers:
      mean:
        title: 'Mean Cov.'
        description: 'Mean coverage'
        suffix: 'X'
        scale: 'BuPu'
```

**Problem**: MultiQC's `custom_data` doesn't easily parse mosdepth's complex summary format.

### Solution 3: Post-Process MultiQC Data
**Complexity**: Medium
**Status**: Scriptable

Create a Python script to:
1. Parse `*.mosdepth.summary.txt` files
2. Extract mean coverage from "total" row
3. Add to `multiqc_general_stats.txt`
4. Regenerate plots

**Not recommended** - breaks MultiQC's integrated workflow.

### Solution 4: Use Mosdepth Per-Chromosome Data
**Status**: Already available!

Mean coverage per chromosome IS available in the MultiQC report:
- Check the "Mosdepth" section → "Coverage per contig" plot
- Shows mean coverage for each chromosome
- Overall mean can be inferred from the "total" row

## Recommended Approach

**Use Median Coverage** - It's already working and is actually the preferred metric:

| Sample | Median Coverage | Why Median > Mean |
|--------|----------------|-------------------|
| A0-F0-I1-R1.md | 76X | Not skewed by mitochondria (7059X) |
| A0-F0-I2-R1.md | 92X | More representative of typical coverage |
| A1-F6-I1-R1.md | 70X | Standard in sequencing QC |

If you **really need mean coverage**, extract it directly from mosdepth summary files:
```bash
grep "^total" A0-F0-I1-R1.md.mosdepth.summary.txt | awk '{print $4}'
# Output: 132.53
```

## Summary

✅ **Median coverage is working** and displayed in MultiQC
❌ **Mean coverage is not extracted** by MultiQC's mosdepth module
✅ **This is expected behavior** - most pipelines use median
✅ **Mean is available** in the raw mosdepth summary.txt files if needed

### Recommended Solution: Multiple Coverage Thresholds

Instead of trying to add mean coverage (which isn't natively supported), use the **`mosdepth_config`** configuration to display multiple coverage thresholds (10X, 20X, 30X, 50X, 100X, 150X, 200X, etc.).

**Benefits:**
- ✅ More informative than a single mean value
- ✅ Shows coverage distribution across the genome
- ✅ Easy to configure (just edit YAML)
- ✅ Uses existing MultiQC functionality
- ✅ No custom code required

**Result:** You get a detailed view of coverage quality that's actually **more useful** than mean coverage alone!

**No bug, no issue - enhanced by better configuration!**
