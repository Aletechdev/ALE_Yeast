# How MultiQC Calculates Median Coverage from Mosdepth

## Summary
The **Median Coverage (Mosdepth)** in MultiQC reports is **NOT** directly from mosdepth's summary.txt file. Instead, MultiQC **calculates it from the cumulative coverage distribution** data.

## Mosdepth Output Files

Mosdepth generates several output files per sample:

### 1. **`*.mosdepth.summary.txt`** - Summary Statistics
Contains per-chromosome and total statistics:
```
chrom    length    bases         mean    min  max
total    12363194  1638524302    132.53  0    11497
```
- **Column 4 (mean)**: Arithmetic mean coverage = 132.53X
- **Does NOT include median** - MultiQC must calculate it separately

### 2. **`*.mosdepth.global.dist.txt`** - Global Coverage Distribution
Format: `chromosome  coverage_depth  proportion_of_bases`
```
chr10  237  0.00
chr10  100  0.85
chr10  50   0.95
```
This shows what **proportion of bases** have **at least** that coverage depth.

### 3. **`*.mosdepth.region.dist.txt`** - Regional Coverage Distribution
Same format as global.dist.txt but for specific regions (if `--by` parameter used).

## How MultiQC Calculates Median Coverage

### Step 1: Parse Distribution Data
MultiQC reads the `*.global.dist.txt` files and creates a **cumulative coverage distribution** for each sample.

Example from your data (`mosdepth_cumcov_dist.txt`):
```
Sample          0     1     2     ...  130   131   132   133   134
A1-F6-I1-R1.md  100.0 100.0 100.0 ... 15.0  14.0  14.0  14.0  13.0
```

This means:
- 100% of bases have ≥0X coverage
- 100% of bases have ≥1X coverage
- 15% of bases have ≥130X coverage
- 14% of bases have ≥132X coverage
- 13% of bases have ≥134X coverage

### Step 2: Find the 50th Percentile (Median)
MultiQC finds the coverage depth where **50% of bases** have at least that coverage:

```python
# Pseudocode for median calculation
for coverage_depth in sorted_depths:
    if cumulative_percentage[coverage_depth] <= 50.0:
        median_coverage = coverage_depth
        break
```

For sample A1-F6-I1-R1:
- Looking at the cumulative distribution, we find where it crosses 50%
- From the data: 50% is between coverage depths where cumulative % = 50%
- **Median ≈ the coverage where cumulative % crosses 50%**

### Step 3: Store in General Statistics
The calculated median is added to MultiQC's **General Statistics table** with the label:
```
Median Coverage (Mosdepth)
```

## Files in `multiqc_data/` Folder

Your MultiQC output contains these mosdepth files:

### 1. **`mosdepth_cov_dist.txt`** - Coverage Distribution
- Shows **percentage of bases** at each coverage depth (0-300X)
- Format: percentage values for each coverage level
- Used for coverage distribution plots
- **NOT cumulative** - shows actual distribution

### 2. **`mosdepth_cumcov_dist.txt`** - Cumulative Coverage Distribution ⭐
- Shows **cumulative percentage** of bases with ≥X coverage
- **This is what MultiQC uses to calculate median**
- Format: Same columns as above but values are cumulative (decreasing from 100% to 0%)
- Example: If 50% at coverage=100X, then 50% of bases have ≥100X coverage

### 3. **`mosdepth_perchrom.txt`** - Per-Chromosome Mean Coverage
- Mean coverage for each chromosome
- Extracted from the "mean" column in summary.txt
- Used for per-chromosome coverage plots

### 4. **`mosdepth-coverage-per-contig-multi.txt`** - Multi-Sample Contig View
- Combined view of per-contig coverage across samples

### 5. **`mosdepth-cumcoverage-dist-id.txt`** - Sample-Specific Cumulative Distributions
- Individual sample cumulative distributions for plots

## Why Not Use Mean from summary.txt?

MultiQC **could** extract the mean (132.53X) directly from `*.summary.txt`, but:

1. **Median is more robust** to coverage outliers (e.g., mitochondrial DNA with 7059X coverage)
2. **Median better represents typical coverage** across the genome
3. **MultiQC calculates median by default** from distribution data for all coverage tools

## Enabling Mean Coverage Display

The configuration we added enables **both metrics**:

```yaml
# In assets/multiqc_config.yml
table_columns_visible:
  mosdepth:
    mean_coverage: True  # NEW: Shows mean from summary.txt
    # median_coverage is already visible by default
```

After this change, your MultiQC report will show **both**:
- **Median Coverage (Mosdepth)** - calculated from distribution (already present)
- **Mean Coverage (Mosdepth)** - extracted from summary.txt "total" line (now enabled)

## Example Comparison

For sample A1-F6-I1-R1:

| Metric | Value | Source |
|--------|-------|--------|
| **Mean Coverage** | 132.53X | Direct from `summary.txt` "total" row, column 4 |
| **Median Coverage** | ~100-110X (estimated) | Calculated from cumulative distribution where 50% of bases have ≥X coverage |

The difference occurs because:
- **Mean** is skewed by high-coverage regions (e.g., mitochondrial DNA at 7059X)
- **Median** represents the middle point of the distribution, less affected by outliers

## Verification - Finding the Median Manually

To understand where the median comes from, look at `mosdepth_cumcov_dist.txt`:

```bash
# For sample A1-F6-I1-R1.md, find where cumulative % ≈ 50%
# From the file, we can see:
# Coverage 50X: 50.0% of bases have ≥50X
# Coverage 51X: 49.0% of bases have ≥51X
# Therefore, median ≈ 50X
```

The median is the coverage depth where the cumulative distribution crosses 50%.

## Key Takeaway

**Median (Mosdepth)** = Coverage depth at which 50% of genome bases have at least that much coverage
- **Calculated from**: `*.global.dist.txt` cumulative distribution
- **Stored in**: `multiqc_data/mosdepth_cumcov_dist.txt`
- **Displayed in**: General Statistics table (by default)

**Mean (Mosdepth)** = Average coverage across all bases
- **Extracted from**: `*.mosdepth.summary.txt` file, "total" row, column 4
- **Now enabled via**: `table_columns_visible: mosdepth: mean_coverage: True`
- **Will appear in**: General Statistics table (after configuration change)
