# Sarek CSV to XPMD Format Converter

This directory contains scripts to convert nf-core/sarek samplesheet format into the legacy ALE pipeline XPMD format.

## Overview

The conversion script transforms:
- **Input**: Sarek samplesheet CSV (`experiment,sample,status,clonal_or_population,ploidy,sex,lane,fastq_1,fastq_2`)
- **Output**: XPMD format CSV with 35 columns including project metadata, experimental details, and file paths

## Files

- `convert_sarek_to_xpmd.py` - Main conversion script
- `Yeast_Methanol_XPMD_final_fixed.csv` - Reference XPMD format example
- `README.md` - This file

## Usage

### Basic Usage

```bash
cd bin/prepare_input/sarek_csv_to_XPMD

python convert_sarek_to_xpmd.py <input_sarek.csv> <output_xpmd.csv>
```

### Example

```bash
# Convert the generated samplesheet to XPMD format
python convert_sarek_to_xpmd.py \
  ../../../data/data_a_paper/dipic_acid_sarek_samplesheet.csv \
  Dicarboxylic_acids_XPMD.csv
```

## Configuration

Edit the `config` dictionary in `convert_sarek_to_xpmd.py` to customize project metadata:

```python
config = {
    'project': 'ZL_dev_Tolerance to Dicarboxylic acids in S cerevisiae',
    'project_description': 'Adaptive laboratory evolution for tolerance to dicarboxylic acids',
    'starting_strain': 'CENPK113-7D',
    'reference_file_name': 'Saccharomyces_cerevisiae_S288C.gbk',
    'reference_url': 'https://www.ncbi.nlm.nih.gov/assembly/GCF_000146045.2/',
    'medium_base': 'YPD',
    'carbon_source': 'glucose(20 g/L)',
    'taxonomy_id': '4932',  # S. cerevisiae
    'owner': 'Your Name',
    'owner_email': 'your.email@example.com',
    # ... additional fields
}
```

## Conversion Logic

### Sample Name Parsing

Sarek sample names follow the format: `A{lineage}-F{flask}-I{individual}-R{replicate}`

Example: `A1-F6-I2-R1` is parsed as:
- A (lineage): 1
- F (flask): 6
- I (individual): 2
- R (replicate): 1

### Lane Grouping

The script automatically groups all lanes for each sample:
- **First lane** (L001): Goes to `filename` and `filename2` columns
- **Additional lanes** (L002-L004): Comma-separated in `additional read files` column

Example:
```
filename:  ../data/data_a_paper/A1-6_S2_L001_R1_001.fastq.gz
filename2: ../data/data_a_paper/A1-6_S2_L001_R2_001.fastq.gz
additional read files:
  ../data/data_a_paper/A1-6_S2_L002_R1_001.fastq.gz,
  ../data/data_a_paper/A1-6_S2_L002_R2_001.fastq.gz,
  ../data/data_a_paper/A1-6_S2_L003_R1_001.fastq.gz,
  ...
```

### Sample Type Mapping

- **Clonal**: Bulk sequencing samples (I=1)
- **Population**: Spore seq samples (I=2 for POS, I=3 for NEG)

The script preserves the `clonal_or_population` field from the Sarek samplesheet.

## Output Format

The XPMD format includes 35 columns:

### Core Metadata
1. `project` - Project name
2. `project description` - Project description
3. `experiment/subproject` - Experiment identifier

### Sample Identifiers (A-F-I-R)
4. `A` - Lineage number
5. `F` - Flask number
6. `I` - Individual number (1=bulk, 2=POS, 3=NEG)
7. `R` - Replicate number

### Experimental Details
8. `experiment details` - DOI or experiment notes
9. `sample type` - "clonal" or "population"

### Files
10. `filename` - R1 file from first lane
11. `filename2` - R2 file from first lane
12. `additional read files` - Comma-separated R1/R2 from remaining lanes
13-15. `indexfile`, `indexfile2`, `additional index files` - Index files (optional)

### Strain and Reference
16. `starting strain` - Ancestral strain name
17. `reference file name(s)` - GenBank file name
18. `reference file url(s)` - Reference URL or "other"

### Media and Environment
19. `medium derived from` - Base medium (e.g., YPD)
20. `medium modifications` - Key-value pairs of modifications
21. `carbon source` - Carbon source with concentration
22. `medium description` - Additional notes
23. `environmental condition modifications` - Temperature, aeration, etc.

### Taxonomy and Metadata
24. `taxonomy id` - NCBI taxonomy ID
25. `ploidy` - Sample ploidy
26. `accession` - NCBI accession number

### Project Management
27. `ALE module` - ALE type (e.g., "ALE", "TALE")
28. `owner` - Project owner
29. `owner email` - Contact email

### Cultivation Details
30. `pre culture details` - Pre-culture notes
31. `cultivation details` - Cultivation process notes

### Sequencing Details
32. `sequencing library prep kit manufacturer` - Kit manufacturer
33. `sequencing library prep kit` - Kit name
34. `sequencing library prep kit cycles` - PCR cycles
35. `sequencing library layout` - "single" or "paired-end"
36. `read length` - Read length in bp

## Sample Statistics

For the test dataset (`dipic_acid_sarek_samplesheet.csv`):

```
Total samples: 17
├─ Clonal samples: 7
│  ├─ Ancestral (A0): 2 samples
│  └─ Bulk evolved (A1-A6): 5 samples
└─ Population samples: 10
   ├─ Spore POS (I=2): 5 samples
   └─ Spore NEG (I=3): 5 samples
```

## Notes

- Lines 2-37 in the reference XPMD file are comment rows describing column meanings. These are **not** included in the generated output as requested.
- File paths are preserved exactly as they appear in the Sarek samplesheet (relative paths like `../data/data_a_paper/...`)
- Empty fields are left blank (empty string) in the output
- Multi-line fields (like environmental conditions) are properly quoted in the CSV

## Validation

To verify the conversion:

```bash
# Check sample counts
python -c "
import csv
with open('output_xpmd.csv') as f:
    rows = list(csv.DictReader(f))
    print(f'Total samples: {len(rows)}')
    print(f'Clonal: {len([r for r in rows if r[\"sample type\"] == \"clonal\"])}')
    print(f'Population: {len([r for r in rows if r[\"sample type\"] == \"population\"])}')
"
```

## Author

Created for the NF_ALE project to bridge nf-core/sarek and legacy ALE pipeline formats.

Date: 2025-10-10
