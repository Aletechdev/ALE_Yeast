# BCFTools Normalization Comparison Analysis

## Input Data
- **File**: A0-F0-I2-R1_vs_A0-F0-I1-R1.freebayes.vcf.gz
- **Total multi-allelic sites**: 15,758 variants
- **Test subset**: 5 representative multi-allelic variants

## Test Commands
1. `bcftools norm -m-` - Split multi-allelic sites
2. `bcftools norm -a --atom-overlaps .` - Atomize overlapping variants

## Results Summary

| Operation | Input Variants | Output Variants | Change |
|-----------|----------------|-----------------|--------|
| Original  | 5              | 5               | 0      |
| norm -m-  | 5              | 10              | +5     |
| norm -a   | 5              | 12              | +7     |

## Detailed Analysis by Variant

### 1. chr10:6435 (GCG → GGACG,GTACG)
**Original**: Complex insertion with 2 alleles
- `norm -m-`: Split into 2 separate records (GCG→GGACG, GCG→GTACG)
- `norm -a`: Split into 2 records, but simplified representation (G→GGA, G→GTA)

**Key Difference**: 
- `-m-` preserves the exact original ALT representation
- `-a` creates minimal representations by trimming common bases

### 2. chr10:7173 (CCC → ACA,ACC)
**Original**: Complex substitution with mixed types
- `norm -m-`: Split into 2 records (CCC→ACA, CCC→ACC)
- `norm -a`: Split into 2 records, but atomized each position (C→A at 7173, C→A at 7175)

**Key Difference**: 
- `-a` further decomposes complex variants into atomic changes at individual positions

### 3. chr10:7211 (A → C,G)
**Original**: Simple SNP with 2 alleles
- Both methods: Split identically into A→C and A→G

### 4. chr10:7748 (CCCCCTG → GCCAACCCTG,TCCAACCCTG)
**Original**: Complex insertion/substitution
- `norm -m-`: Split into 2 records preserving full sequences
- `norm -a`: Split and atomized into 3 records (C→G, C→T, C→CCAA)

**Key Difference**: 
- `-a` decomposes the complex variant into individual atomic changes at different positions

### 5. chr10:7832 (AACCA → CACCC,ACCCA)
**Original**: Complex multi-base change
- `norm -m-`: Split into 2 records (AACCA→CACCC, AACCA→ACCCA)
- `norm -a`: Atomized into 3 records (A→C at 7832, A→C at 7833, A→C at 7836)

**Key Difference**: 
- `-a` identifies individual base changes within the complex variant

## Behavioral Differences

### `bcftools norm -m-` (Multi-allelic Split)
- **Purpose**: Simply splits multi-allelic records into separate bi-allelic records
- **Preserves**: Original ALT representations exactly
- **Use case**: When you need to process each allele separately but maintain original representation
- **Output**: 2x variants per multi-allelic site (typically)

### `bcftools norm -a --atom-overlaps .` (Atomization)
- **Purpose**: Decomposes variants into their most basic atomic components
- **Creates**: Minimal variant representations (left-aligned, trimmed)
- **Use case**: When you need the simplest possible variant representation for analysis
- **Output**: Variable number of variants depending on complexity

## Practical Implications

### For FreeBayes Somatic Filtering (Your Use Case):
1. **`-m-` is recommended** for somatic filtering because:
   - Maintains clear allele counts (AO values) for each alternative
   - Simpler filtering logic: each record has exactly one alternative allele
   - Preserves the biological context of the original variant call

2. **`-a` may be problematic** because:
   - Creates artificial atomic variants that weren't directly called
   - May split complex variants in ways that lose biological meaning
   - More complex to filter (variants at different positions from same original call)

### Example for Your Pipeline:
```bash
# Current approach (recommended)
bcftools norm -m- input.vcf | bcftools view -i "FORMAT/AO[0:0]/(FORMAT/AO[0:0]+FORMAT/RO[0:0]) < 0.10"

# vs atomization (more complex)
bcftools norm -a --atom-overlaps . input.vcf  # Creates position-shifted variants
```

## Conclusion

For **somatic variant filtering in FreeBayes data**, `bcftools norm -m-` is the appropriate choice because:
- It maintains 1:1 correspondence with original allele observations (AO/RO fields)
- Each split variant can be independently filtered using AF calculations
- It preserves the biological context of the variant calls
- It's computationally simpler and more predictable

The atomization approach (`-a`) is more suited for variant annotation, population genetics, or when you need the most minimal variant representation possible.