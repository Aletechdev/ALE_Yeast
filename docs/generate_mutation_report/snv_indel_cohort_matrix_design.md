# Unified Mutation Cohort Matrix Design

## Motivation

CN and SV already have cohort-wide matrices (wide-format CSV, one column per sample).
SNV/INDELs lack an equivalent — only per-sample VCFs and concordance summaries exist.

This script fills that gap with a **unified matrix covering SNPs, INDELs, and SVs**,
tracking which of the three available callers (HaplotypeCaller, Manta, TIDDIT) detected
each event. This captures the overlap zone where the same event (e.g. a 50-80bp insertion)
is detected by both an INDEL caller and an SV caller.

---

## Observed Cross-Tool Overlap (Ottilie Pilot)

Evidence from `CBR110-15-R3a` that HC and Manta detect the same event:

| Locus | HC Call | Manta Call |
|-------|--------|------------|
| `VII:530034` | 84bp insertion (`A` → `ATCATCATC...`) | `INS` SVLEN=84 |

HC INDEL size distribution for this sample:
- SNP: 154, INDEL 1-9bp: 106, INDEL 10-49bp: 4, INDEL 50bp+: 3
- The 7 INDELs >= 10bp are in the overlap zone with SV callers

---

## Output Formats

The script produces **two output files** from the same data — a compact packed format
for analysis and a flat expanded format for dashboards. Both are generated in a single
run; user feedback will determine which the dashboard uses.

### File 1: `snv_indel_sv_cohort_matrix.csv` (Packed — for analysis)

One column per sample metric, per-caller values packed with `:` separator.
Compact, easy to scan in a terminal or spreadsheet. Requires splitting for
programmatic filtering by individual caller.

### File 2: `snv_indel_sv_cohort_matrix_flat.csv` (Expanded — for dashboards)

One column per sample × caller, no packing. Directly sortable/filterable in
Tabulator.js without parsing. More columns but each cell is a simple value.

---

## Format 1 (Packed): `snv_indel_sv_cohort_matrix.csv`

### Per-Sample Cell Format

Each sample gets **two columns** with packed per-caller values separated by `:`:

```
{sample}_GT   →  HC_GT:Manta_GT:TIDDIT_GT
{sample}_AF   →  HC_AF:Manta_AF:TIDDIT_AF
```

Missing values use `.` (standard VCF convention):

| Scenario | `{sample}_GT` | `{sample}_AF` | Interpretation |
|----------|---------------|---------------|----------------|
| HC only | `0/1:.:. ` | `0.45:.:. ` | SNP/small INDEL, SV callers didn't call it |
| Manta+TIDDIT | `.:0/1:0/1` | `.:.:. ` | SV detected by both, no HC call |
| HC+Manta | `0/1:0/1:.` | `0.45:.:. ` | Large INDEL in overlap zone |
| All three | `1/1:0/1:0/1` | `1.00:.:. ` | High-confidence event |
| Not detected | `.` | `.` | Absent in this sample |

A third column tracks caller presence compactly:

```
{sample}_callers  →  HC+Manta, HC, Manta+TIDDIT, etc.
```

### Full Schema

| Column | Type | Description |
|--------|------|-------------|
| `chrom` | str | Chromosome |
| `pos` | int | Position (1-based) |
| `ref` | str | Reference allele (literal for SNV/INDEL, `.` for SV symbolic alleles) |
| `alt` | str | Alternate allele (literal for SNV/INDEL, `<DEL>`, `<INS>`, `<DUP>`, `<INV>` for SVs) |
| `type` | str | `SNP`, `INDEL`, `DEL`, `INS`, `DUP`, `INV`, `BND` |
| `svlen` | int | SV length in bp (0 for SNPs, indel length for INDELs) |
| `gene` | str | Gene name from SnpEff `ANN` field |
| `effect` | str | SnpEff effect (e.g. `missense_variant`, `structural_interaction_variant`) |
| `impact` | str | `HIGH`, `MODERATE`, `LOW`, `MODIFIER` |
| `filter` | str | FILTER column (e.g. `PASS`, `QD_filter`) |
| `{sample}_GT` | str | Packed genotype: `HC_GT:Manta_GT:TIDDIT_GT` |
| `{sample}_AF` | str | Packed allele freq: `HC_AF:Manta_AF:TIDDIT_AF` |
| `{sample}_callers` | str | Caller summary: `HC`, `Manta`, `HC+Manta+TIDDIT`, `-` |

### Caller Field Order Convention

The `:` separated fields always follow this fixed order:

```
Position 1: HaplotypeCaller (HC)
Position 2: Manta
Position 3: TIDDIT
```

This order is fixed regardless of which callers are available. Missing callers always
show `.`. The field order is documented in a header comment in the CSV:

```csv
## Caller field order: HC:Manta:TIDDIT (. = not called)
## Per-sample columns: {sample}_GT, {sample}_AF, {sample}_callers
chrom,pos,ref,alt,type,svlen,gene,effect,impact,filter,CBR110-15-R3a_GT,...
```

### Example Output

```csv
## Caller field order: HC:Manta:TIDDIT (. = not called)
## Per-sample columns: {sample}_GT, {sample}_AF, {sample}_callers
chrom,pos,ref,alt,type,svlen,gene,effect,impact,filter,CBR110-15-R3a_GT,CBR110-15-R3a_AF,CBR110-15-R3a_callers,NODRUG-GM2_GT,NODRUG-GM2_AF,NODRUG-GM2_callers
IV,387201,A,G,SNP,0,YDR150W,missense_variant,MODERATE,PASS,0/1:.:.,0.45:.:.,HC,0/0:.:.,0.00:.:.,HC
III,84801,.,<DEL>,DEL,7679,YCR024C,structural_interaction_variant,HIGH,PASS,.:0/1:0/1,.:.:.,Manta+TIDDIT,.:.:.,.:.:.,-
VII,530034,A,ATCATC...,INS,84,YGL058W,frameshift_variant,HIGH,PASS,0/1:0/1:.,0.45:.:.,HC+Manta,.:.:.,.:.:.,-
XV,159660,.,<DEL>,DEL,33214,.,gene_variant,MODIFIER,PASS,.:0/1:.,.:.:.,Manta,.:0/1:0/1,.:.:.,Manta+TIDDIT
```

---

## Format 2 (Flat): `snv_indel_sv_cohort_matrix_flat.csv`

### Per-Sample Columns (Expanded)

Each sample × caller combination gets its own column:

| Column | Example | Description |
|--------|---------|-------------|
| `{sample}_HC_GT` | `0/1` | HaplotypeCaller genotype |
| `{sample}_HC_AF` | `0.45` | HaplotypeCaller allele frequency |
| `{sample}_Manta_GT` | `0/1` | Manta genotype |
| `{sample}_Manta_AF` | `.` | Manta allele frequency (often unavailable) |
| `{sample}_TIDDIT_GT` | `.` | TIDDIT genotype |
| `{sample}_TIDDIT_AF` | `.` | TIDDIT allele frequency |
| `{sample}_callers` | `HC+Manta` | Summary (same as packed format) |

### Example Output

```csv
chrom,pos,ref,alt,type,svlen,gene,effect,impact,filter,CBR110-15-R3a_HC_GT,CBR110-15-R3a_HC_AF,CBR110-15-R3a_Manta_GT,CBR110-15-R3a_Manta_AF,CBR110-15-R3a_TIDDIT_GT,CBR110-15-R3a_TIDDIT_AF,CBR110-15-R3a_callers,NODRUG-GM2_HC_GT,...
IV,387201,A,G,SNP,0,YDR150W,missense_variant,MODERATE,PASS,0/1,0.45,.,.,.,.,HC,0/0,...
VII,530034,A,ATCATC...,INS,84,YGL058W,frameshift_variant,HIGH,PASS,0/1,0.45,0/1,.,.,.,HC+Manta,.,...
III,84801,.,<DEL>,DEL,7679,YCR024C,structural_interaction_variant,HIGH,PASS,.,.,0/1,.,0/1,.,Manta+TIDDIT,.,...
```

### Column Count Comparison

| Dataset | Samples | Callers | Packed Columns | Flat Columns |
|---------|---------|---------|---------------|-------------|
| Ottilie | 4 | 3 (HC/Manta/TIDDIT) | 9 shared + 12 = **21** | 9 shared + 28 = **37** |
| CEN.PK | 17 | 3 | 9 shared + 51 = **60** | 9 shared + 119 = **128** |
| CEN.PK | 17 | 5 (+ FB/DV) | 9 shared + 51 = **60** | 9 shared + 187 = **196** |

The flat format grows faster but remains practical for Tabulator.js (which handles
wide tables well with horizontal scrolling and column visibility toggles).

### Trade-offs

| Aspect | Packed | Flat |
|--------|--------|------|
| Column count | Lower (3 per sample) | Higher (2×callers+1 per sample) |
| Sort/filter by caller AF | Needs string split | Direct column sort |
| Terminal/Excel scanning | Compact, readable | Wide, needs scrolling |
| Tabulator.js dashboard | Needs custom formatter | Works out-of-the-box |
| Programmatic analysis (pandas) | One-liner split | Ready to use |

### Dashboard Recommendation

Start with the **flat format** for the Tabulator.js dashboard — it allows direct
column sorting (e.g. "sort by HC_AF descending") and per-caller column visibility
toggles without custom cell parsers. The packed format is better for export/sharing
and quick manual review.

---

## Input Sources

### Available Callers (Ottilie Pilot)

| Caller | Type | Path Pattern |
|--------|------|-------------|
| HaplotypeCaller | SNP + INDEL | `annotation/haplotypecaller/{sample}/` |
| Manta | SV (DEL, INS, DUP, INV, BND) | `variant_calling/manta/{sample}/` |
| TIDDIT | SV (DEL, DUP, INV, BND) | `variant_calling/tiddit/{sample}/` |

### Future Callers (CEN.PK / expanded runs)

| Caller | Type | Path Pattern |
|--------|------|-------------|
| FreeBayes | SNP + INDEL | `annotation/freebayes/{sample}/` |
| DeepVariant | SNP + INDEL | `annotation/deepvariant/{sample}/` |

When additional SNV/INDEL callers are added, the packed format extends:

```
## Caller field order: HC:FB:DV:Manta:TIDDIT
0/1:0/1:1/1:.:. | 0.45:0.52:0.98:.:. | HC+FB+DV
```

### VCF File Naming

```
# HC (annotated, from joint calling)
annotation/haplotypecaller/{sample}/{sample}.haplotypecaller.from_joint_calling_snpEff.ann.vcf.gz

# Manta (raw variant calling output)
variant_calling/manta/{sample}/{sample}.manta.diploid_sv.vcf.gz

# TIDDIT (raw variant calling output)
variant_calling/tiddit/{sample}/{sample}.tiddit.vcf.gz

# Manta/TIDDIT annotated (if available)
annotation/manta/{sample}/{sample}.manta.diploid_sv_snpEff.ann.vcf.gz
annotation/tiddit/{sample}/{sample}.tiddit_snpEff.ann.vcf.gz
```

---

## Algorithm

### 1. Discover Samples and Callers

```
output_dir/
├── annotation/
│   ├── haplotypecaller/{sample}/                   → HC annotated VCFs
│   ├── manta/{sample}/                             → Manta annotated VCFs (preferred)
│   └── tiddit/{sample}/                            → TIDDIT annotated VCFs (preferred)
└── variant_calling/
    ├── manta/{sample}/                             → Manta raw VCFs (fallback)
    └── tiddit/{sample}/                            → TIDDIT raw VCFs (fallback)
```

Prefer annotated VCFs (have SnpEff gene/effect), fall back to raw VCFs for SV callers.

### 2. Normalize and Key Variants

**For HC (SNP/INDEL):**
1. `bcftools norm -m-` — split multi-allelics into biallelic records
2. Parse SnpEff `ANN` field for gene/effect/impact
3. Key by `(chrom, pos, ref, alt)` — exact match

**For Manta/TIDDIT (SV):**
1. Parse SVTYPE, SVLEN, END from INFO
2. Key by `(chrom, pos, svtype)` — position-based matching with tolerance window
3. For cross-tool matching (Manta vs TIDDIT): use SURVIVOR-style proximity
   (default 1000bp window, same SVTYPE)

### 3. Cross-Type Matching (HC INDEL ↔ SV)

The overlap zone where HC INDELs and Manta/TIDDIT SVs describe the same event:

```
HC:    VII  530034  A  ATCATCATC...  (84bp insertion, explicit sequence)
Manta: VII  530034  .  <INS>         (SVLEN=84, symbolic allele)
```

**Matching criteria for HC-INDEL ↔ SV linkage:**
- Same chromosome
- Position within ±10bp (accounts for left-alignment differences)
- Compatible type: HC insertion ↔ SV INS/DUP, HC deletion ↔ SV DEL
- Size within 50% of each other (e.g. HC 84bp ↔ Manta 84bp)

**When matched:**
- Merge into single row
- Use HC's literal REF/ALT (more informative than symbolic `<INS>`)
- Record both callers in the packed GT/AF fields

**When not matched:**
- Keep as separate rows (HC INDEL row and SV row)

### 4. Build Wide-Format Matrix

- Rows: union of all variants across all samples and callers
- Columns: shared fields + per-sample packed fields
- Sort by chrom (natural chromosome order), pos

### 5. Annotation Priority

When multiple callers provide different SnpEff annotations:
- Prefer annotation with highest impact rank: HIGH > MODERATE > LOW > MODIFIER
- Tie-break: prefer HC (most detailed annotation from joint calling)
- For SV-only events: use Manta annotation if available, else TIDDIT

---

## CLI Interface

```bash
python bin/snv_indel_sv_cohort_matrix.py \
    --output-dir output_ottilie \
    --csv results/snv_indel_sv_cohort_matrix.csv \
    [--annotation-dir output_ottilie/annotation]       # default: {output-dir}/annotation
    [--variant-calling-dir output_ottilie/variant_calling]  # default: {output-dir}/variant_calling
    [--callers haplotypecaller,manta,tiddit]            # default: auto-detect
    [--pass-only]                                       # only include PASS variants
    [--min-callers 1]                                   # minimum callers to include a row
    [--sv-match-window 10]                              # bp tolerance for HC↔SV matching
    [--exclude-parent NODRUG-GM2]                       # exclude ancestral sample
```

**Always produces both files:**
- `{csv}` → packed format (e.g. `snv_indel_sv_cohort_matrix.csv`)
- `{csv_stem}_flat.csv` → expanded format (e.g. `snv_indel_sv_cohort_matrix_flat.csv`)

### Options

| Flag | Default | Description |
|------|---------|-------------|
| `--output-dir` | required | Pipeline output directory |
| `--csv` | required | Output CSV path |
| `--annotation-dir` | `{output-dir}/annotation` | Base annotation directory |
| `--variant-calling-dir` | `{output-dir}/variant_calling` | Base variant calling directory |
| `--callers` | auto-detect | Comma-separated list of callers to include |
| `--pass-only` | false | Only include variants with FILTER=PASS |
| `--min-callers` | 1 | Minimum callers (across all types) to include a variant row |
| `--sv-match-window` | 10 | bp tolerance for HC INDEL ↔ SV position matching |
| `--exclude-parent` | none | Sample name(s) to exclude (e.g. ancestral strain) |

---

## Consistency with Existing Matrices

The unified matrix **replaces** the need for separate SV and SNV/INDEL matrices
in the dashboard context. The existing standalone matrices remain for detailed analysis:

| Matrix | Script | Purpose | Status |
|--------|--------|---------|--------|
| **CN** | `build_cn_matrix.py` + `cn_cohort_matrix.py` | Copy number (separate axis) | Keep as-is |
| **SV** | `sv_cohort_matrix.py` | SV-only detail with SURVIVOR merge | Keep for SV-specific analysis |
| **Unified** | `snv_indel_sv_cohort_matrix.py` (NEW) | All mutations in one table | New, covers SNP+INDEL+SV |

The CN matrix stays separate because copy number is a fundamentally different
measurement (continuous log2 ratios, not discrete variant calls).

---

## Pipeline Integration

### Standalone (immediate use)

```bash
eval "$(conda shell.bash hook 2>/dev/null)" && conda activate nf-env
python bin/snv_indel_sv_cohort_matrix.py \
    --output-dir output_ottilie \
    --csv docs/igvreports/ottilie_4samples/data/snv_indel_sv_cohort_matrix.csv
```

### Nextflow Process (Phase 2)

```nextflow
process BUILD_MUTATION_MATRIX {
    tag "snv_indel_sv_cohort_matrix"
    label 'process_low'

    input:
    path annotation_dir
    path variant_calling_dir

    output:
    path "snv_indel_sv_cohort_matrix.csv",      emit: csv_packed
    path "snv_indel_sv_cohort_matrix_flat.csv", emit: csv_flat
    path "versions.yml",                   emit: versions

    script:
    """
    snv_indel_sv_cohort_matrix.py \
        --annotation-dir ${annotation_dir} \
        --variant-calling-dir ${variant_calling_dir} \
        --csv snv_indel_sv_cohort_matrix.csv

    cat <<-END_VERSIONS > versions.yml
    "${task.process}":
        snv_indel_sv_cohort_matrix: 1.0
        bcftools: \$(bcftools --version | head -1 | sed 's/bcftools //')
    END_VERSIONS
    """
}
```

### Dashboard Integration

`generate_index.py` would load the unified CSV:

| Dashboard Section | Source CSV |
|-------------------|-----------|
| CN Heatmap | `cn_chr_summary_*.csv`, `cn_cohort_collapsed_*.csv` |
| Mutation Table (NEW) | `snv_indel_sv_cohort_matrix.csv` (SNP + INDEL + SV unified) |
| SV Detail (existing) | `sv_cohort_matrix_union*.csv` (kept for SURVIVOR-level analysis) |

---

## Dependencies

- `bcftools` (normalization, VCF parsing)
- `pysam` or `cyvcf2` (Python VCF parsing)
- Standard library: `csv`, `argparse`, `pathlib`, `collections`

All available in `nf-env` conda environment.

---

## Open Questions

1. **Parent sample**: Include as column (shows `0/0` / `.` at evolved sites, useful for
   reference) or exclude? Recommendation: include, consistent with CN/SV matrices.

2. **BND events**: Manta/TIDDIT BND (translocation breakends) have two records per event
   and no single position. Include them? Options:
   - Include as-is (two rows per BND pair) — complete but potentially confusing
   - Collapse BND pairs into one row with `chrom2:pos2` column — cleaner
   - Exclude BNDs from unified matrix, keep only in SV-specific matrix — simplest

3. **Annotation source for SVs**: Prefer annotated SV VCFs (`annotation/manta/`) when
   available, fall back to raw VCFs (`variant_calling/manta/`). Should we require
   annotated VCFs or always support both?

4. **Future caller expansion**: When FreeBayes/DeepVariant are added, the packed format
   grows from 3 to 5 fields (`HC:FB:DV:Manta:TIDDIT`). This is still manageable but
   gets wide. Alternative: keep SNV callers and SV callers in separate packed groups?
   e.g. `{sample}_snv_GT` = `HC:FB:DV` and `{sample}_sv_GT` = `Manta:TIDDIT`
