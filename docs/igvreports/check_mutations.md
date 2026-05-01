# IGVReports Architecture for ALE Variant Review

## Proposed Architecture: Index Page + Per-Sample Reports

### Option 1: Index page only (simplest, ~30 min of work)
Don't try to link from inside the cohort table. Instead, write a tiny index.html that lists samples and links to their pages, alongside a link to the cohort table page. Users navigate cohort ↔ index ↔ sample.

```
index.html
├── "View cohort variant table" → cohort.html
└── "Per-sample reports"
    ├── sample_01 → samples/sample_01.html
    ├── sample_02 → samples/sample_02.html
    └── ...
```

The index is a one-shot Nextflow process that takes the list of sample IDs and renders an HTML template. Maybe 15 lines of Python with Jinja2, or even pure Groovy in a Nextflow script: block.

**Pros**: trivial, robust, no igv-reports internals touched.
**Cons**: no direct "click variant in cohort → see that sample's alignment at that position" — users have to manually navigate.

For ALE this is honestly fine. Cross-sample variant scanning happens at the table level; alignment review happens per-sample, separately. The two tasks aren't tightly interleaved in practice.

---

## POC Results (April 2026)

### Single-sample report: validated
- **Sample**: A1-F6-I1-R1 (evolved clone)
- **Variants**: 113 (from individual_from_joint VCF)
- **Time**: ~30 seconds
- **Size**: 11 MB HTML
- **Includes**: IGV read pileups, per-sample GT/AD/DP/GQ/VAF

### Cohort table (no tracks): validated
- **Variants**: 1,748 (joint HaplotypeCaller)
- **Time**: ~10 seconds
- **Size**: 8.9 MB HTML
- **Includes**: FILTER, INFO fields, per-sample GT/AD/DP/GQ (all 17 samples)

### Full cohort with all CRAMs: NOT feasible on D4as
- **Terminated** after 1h18m, 10 GB / 12 GB RAM (83% memory)
- 17 CRAMs × 1,748 variants = too much data to embed

---

## Performance Optimization for HTML Load Time

### Problem
The no-tracks cohort report (8.9 MB, 1,748 variants × 17 samples) can be slow to load in browser due to:
- Large DOM: 1,748 rows × ~170 columns (17 samples × 10 fields each)
- All data embedded inline in the HTML
- Default template renders all rows at once (no virtual scrolling)

### Solutions (ordered by impact)

#### 1. Upgrade to igv-reports >= 1.15.0 for Tabulator template (HIGH IMPACT)
The `--tabulator` template uses [Tabulator.js](http://tabulator.info/) with **virtual scrolling** — only visible rows are rendered in the DOM. This is the single biggest improvement for browser load time with many variants. It also adds **per-column filtering** in the table header (dropdown, substring search, numeric range).

**Generation command** (from [igv-reports run_examples.sh](https://github.com/igvteam/igv-reports/blob/master/run_examples.sh)):
```bash
create_report input.vcf.gz --fasta ref.fa \
    --tabulator \
    --filter-config filter_config.yaml \
    --info-columns ANN VCF_FILTER AC AF DP QD MQ \
    --sample-columns GT AD DP GQ VAF \
    --flanking 500 \
    --output cohort_report.html
```

**`--filter-config` YAML format** — defines per-column filter behavior:
```yaml
columns:
  GENE:
    type: string
    filter: contains        # substring search box
  IMPACT:
    type: string
    filter: list            # dropdown with all unique values
  VCF_FILTER:
    type: string
    filter: list            # dropdown: PASS, QD_filter, MQ_filter, etc.
  AF:
    type: number
    filter: range           # min/max numeric slider
  DP:
    type: number
    filter: threshold       # numeric cutoff (e.g., DP >= 10)
    threshold: 10
```

Supported filter types: `contains` (substring), `list` (dropdown), `exact` (precise match), `range` (min/max), `threshold` (numeric cutoff).

**Status**: nf-core module ships v1.12.0; need to override container to >= 1.15.0
**Reference**: [Tabulator example](https://igvteam.github.io/igv-reports/examples/example_vcf_tabulator.html) | [filter_config.yaml](https://github.com/igvteam/igv-reports/blob/master/test/data/variants/filter_config.yaml)

#### 2. Pre-filter to PASS-only variants (HIGH IMPACT)
Reduces 1,748 → ~737 variants (58% reduction), roughly halving HTML size and DOM nodes.

```bash
bcftools view -f PASS joint_calling.vcf.gz -Oz -o pass_only.vcf.gz
bcftools index -t pass_only.vcf.gz
```

#### 3. Per-sample architecture instead of all-in-one (HIGH IMPACT)
Split into: cohort table (lightweight, no per-sample columns) + individual sample reports (with CRAMs, ~100 variants each).

| Report Type | Variants | Samples | Size | Load Time |
|-------------|----------|---------|------|-----------|
| Cohort table (all) | 1,748 | 17 | 8.9 MB | Slow |
| Cohort table (PASS) | ~737 | 17 | ~4 MB | Moderate |
| Per-sample report | ~100 | 1 | 11 MB | Fast |

#### 4. Reduce embedded data per variant (MODERATE IMPACT)
- **`--flanking 200`** instead of 500 — less reference sequence per variant
- **Trim INFO columns** — remove `AN` (constant), `AC` (redundant with GT)
- **Limit `--sample-columns`** — e.g., just `GT VAF` for cohort overview

#### 5. `--no-embed` for server deployment (MODERATE IMPACT)
Available in v1.16.0. References external FASTA/tracks via URLs instead of embedding.
Requires serving from a web server (not a standalone file).

```bash
create_report input.vcf.gz --fasta ref.fa --no-embed --tracks aligned.cram
```

#### 6. Increase variant table height (QUICK FIX)
The default template limits the variant table to 350px (`max-height: 350px` in the collapsible CSS). Post-process the generated HTML to increase it:

```bash
sed -i 's/max-height: 350px;/max-height: 800px;/' cohort_report.html
```

No `create_report` CLI option exists for this. The `--tabulator` template (v1.15.0+) may handle this better with virtual scrolling.

#### 7. Split by chromosome (LOW IMPACT for yeast)
Generate one report per chromosome. More useful for large genomes.
For yeast with 52 contigs and ~1,748 variants total, not worth the complexity.

### Recommended Strategy for ALE

```
docs/igvreports/output/
├── index.html                          # Navigation hub (generated)
├── cohort_pass_only.html               # PASS variants, Tabulator template, no tracks
└── samples/
    ├── A0-F0-I1-R1.html               # Per-sample: ~100 variants + CRAM pileups
    ├── A1-F6-I1-R1.html
    └── ...
```

**Generation time estimate**: ~10s (cohort) + 17 × ~30s (samples) ≈ 9 minutes total

---

## Per-Sample VAF (Variant Allele Frequency)

### Problem
HaplotypeCaller outputs `FORMAT/AD` (allelic depths) but not allele frequency.

### Solution: `bcftools +fill-tags -- -t FORMAT/VAF`
Adds `VAF = AD[alt] / (AD[ref] + AD[alt])` as a new FORMAT field.

```bash
bcftools +fill-tags input.vcf.gz -Oz -o with_vaf.vcf.gz -- -t FORMAT/VAF
bcftools index -t with_vaf.vcf.gz
# Then use --sample-columns GT AD DP GQ VAF
```

**Note**: The tag is `FORMAT/VAF` (not `FORMAT/AF`). INFO/AF remains unchanged — it represents population-level allele frequency from joint calling, not per-sample fraction.

| Field | Level | Source | Example | Meaning |
|-------|-------|--------|---------|---------|
| INFO/AF | Cohort | Joint calling | 0.047 | Alt allele frequency across all 17 samples |
| FORMAT/VAF | Sample | bcftools fill-tags | 0.667 | This sample's alt read fraction: AD[alt]/sum(AD) |

---

## Multi-Allelic Variants and Splitting

### Problem
Joint calling with HaplotypeCaller produces 1,135 multi-allelic sites out of 7,433 total (15%). These are overwhelmingly **+1/-1 bp indels** (93% multi-indel) — classic homopolymer stutter from PCR/sequencing in repeat regions. Only 12% pass quality filters vs 9.3% for biallelic (similar quality profile).

Multi-allelic FORMAT fields like VAF are comma-separated strings (e.g., `0.64,0.083`), which breaks numeric filtering in Tabulator.js.

### Solution: `bcftools norm -m-` with `--old-rec-tag`

```bash
bcftools norm -m- --old-rec-tag ORIG_ALT --force input.vcf.gz -Oz -o split.vcf.gz
```

- Splits each multi-allelic site into separate biallelic rows
- `--old-rec-tag ORIG_ALT` preserves the original record as `INFO/ORIG_ALT=chr10|4920|G|GA,GAA|1` (format: `CHR|POS|REF|ALT|USED_ALT_IDX`)
- `--force` required because HaplotypeCaller PL fields have wrong cardinality for high-ploidy multi-allelic sites (known GATK issue)
- After splitting, all FORMAT fields (VAF, AD, DP, GQ) become scalar → numeric Tabulator filters work

### Caveats

1. **SnpEff ANN not split**: `bcftools norm -m-` does NOT split the ANN field — both split rows carry all annotations for all original ALTs. Options:
   - Re-annotate with SnpEff after splitting (cleanest)
   - Use `SnpSift extractFields` to filter ANN by allele
   - Accept duplicate annotations (acceptable for review — igvreports shows all anyway)

2. **Row count increases**: 7,433 → ~8,568 rows (+15%)

3. **ORIG_ALT as INFO column**: Add `--info-columns ORIG_ALT` to igvreports to show the original multi-allelic context in the table. Useful for identifying split records during review.

### Recommended pipeline order

```
bcftools norm -m- --old-rec-tag ORIG_ALT --force  # split multi-allelics
→ AWK (copy FILTER → VCF_FILTER)                  # fix FILTER column
→ bcftools +fill-tags -- -t FORMAT/VAF             # add per-sample VAF
→ create_report --tabulator                        # generate report
```

---

## SnpEff ANN Column Display

igv-reports has **built-in ANN parsing** (`varianttable.py:107-115`). When `--info-columns ANN` is passed, it automatically extracts into 7 readable columns: GENE, EFFECTS, IMPACT, TRANSCRIPT, GENE_ID, PROTEIN ALTERATION, DNA ALTERATION. No `bcftools +split-vep` or manual parsing needed.

---

## FILTER Column in igvreports

### Problem
`--info-columns FILTER` produces an empty column. igvreports only reads `variant.info[h]` (INFO dict), not the fixed FILTER column (VCF column 7).

### Solution
Pre-process VCF with AWK to copy FILTER → `INFO/VCF_FILTER`, then use `--info-columns VCF_FILTER`:

```bash
bcftools view input.vcf.gz \
    | awk 'BEGIN{OFS="\t"}
        /^##/{print; next}
        /^#CHROM/{
            print "##INFO=<ID=VCF_FILTER,Number=1,Type=String,Description=\"Original VCF FILTER value\">"
            print; next
        }
        {
            filt=$7
            gsub(/;/, ",", filt)   # semicolons conflict with INFO delimiter
            $8="VCF_FILTER=" filt ";" $8
            print
        }' \
    | bgzip > prepared.vcf.gz
```

**Note**: FILTER values like `MQ_filter;SOR_filter` contain semicolons that are INFO field delimiters. The AWK replaces them with commas.

---

## GFF3 Gene Track

The GFF3 from snpeff_cache (`draft_ref52.gff3`, 14 MB) works as an IGV track via `--tracks genes.sorted.gff3.gz`. It must be sorted, bgzipped, and tabix-indexed first.

The GFF3 contains overlapping feature types (gene + mRNA + CDS) for the same loci, which renders as duplicate tracks in the IGV view. For yeast (minimal splicing), this is cosmetic — both tracks show the same gene boundaries.

---

## Known Limitation: 3-Frame Amino Acid Translation

### Problem
The igvteam example ([example_vcf_tabulator.html](https://igvteam.github.io/igv-reports/examples/example_vcf_tabulator.html)) shows 3-frame amino acid translation below the reference sequence. This uses `--genome hg38`, which triggers igv.js's built-in genome configuration with `showTranslation: true`.

### Status: NOT supported for custom genomes

When using `--fasta` (custom reference), igv-reports creates a minimal reference config with only `fastaURL` — no `showTranslation` flag. The igv.js viewer does not render amino acid translation.

**Attempted fix**: Monkey-patched `report.create_session_dict()` to inject `"showTranslation": true` into the reference config within session data URIs. The injection succeeded technically but the translation **did not render** in the browser.

**Root cause**: igv.js likely requires additional genome metadata (cytobands, chromosome aliases) or a different reference config structure to enable translation for custom genomes.

**Workaround**: The SnpEff ANN field already provides PROTEIN ALTERATION and DNA ALTERATION columns in the variant table, which covers the primary use case of identifying amino acid changes at variant positions.

---

## Full Workflow Results (April 2026)

### Nextflow workflow: `generate_all_reports.nf`
- **Runtime**: 18m 48s (37 tasks)
- **Architecture**: PREPARE_GFF3 → PREPARE_VCF (×18) → IGVREPORTS_COHORT + IGVREPORTS_SAMPLE (×17) → GENERATE_INDEX
- **Input**: SnpEff-annotated VCFs (non-hard-filtered, ~113 variants/sample)

### Output sizes
| Report | Variants | Size |
|--------|----------|------|
| Cohort (all samples, no tracks) | 7,433 | 17 MB |
| Per-sample I1 replicates | ~113 | 6–16 MB |
| Per-sample I2/I3 replicates | ~113 | 135–196 MB |

Large I2/I3 report sizes are due to higher ploidy configuration that reports lower frequency mutations.

### Columns displayed
- **INFO columns**: ANN (auto-parsed → 7 sub-columns), VCF_FILTER, AC, AF, DP, QD, MQ
- **FORMAT columns**: GT, AD, DP, GQ, VAF

---

## References

- [igv-reports GitHub](https://github.com/igvteam/igv-reports)
- [Tabulator template example](https://igvteam.github.io/igv-reports/examples/example_vcf_tabulator.html)
- [igv-reports paper (bioRxiv 2025)](https://www.biorxiv.org/content/10.1101/2025.10.29.685397v1.full.pdf)
- [BAM size limits discussion](https://github.com/igvteam/igv-reports/issues/23)
- [igv-reports v1.16.0 README](https://github.com/igvteam/igv-reports/blob/v1.16.0/README.md)
