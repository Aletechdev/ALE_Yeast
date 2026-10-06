# Input samplesheet: format & conventions

Canonical reference for the ALE input samplesheet (`--input`). The format is adapted from nf-core/sarek
(originally human cancer), with ALE-specific columns and an **all-samples-are-normal** convention.
CLAUDE.md carries the short version; this doc has the full column reference + the notes that only matter
to non-Tier-1 tools.

## Columns

| Column | Meaning |
|--------|---------|
| `experiment` | Experiment ID (maps to Sarek's "patient"). Groups samples for joint calling. ⚠️ Use this header, not `patient`: a `patient` header passes schema validation but is parsed as *empty* (both columns map to the same field and the last declaration wins), which the start-up preflight turns into a hard error ([`preflight_checks.md`](preflight_checks.md)). |
| `sample` | Sample ID in ALE format, e.g. `A1-F6-I1-R1`. |
| `clonal_or_population` | `clonal` for clonal isolate sequencing; `population` for bulk/pooled sequencing. Drives the AF thresholds in the joint HC hard filter. |
| `ploidy` | `1` = haploid, `2` = diploid (higher supported). Passed to HaplotypeCaller (`--sample-ploidy`), Control-FREEC, FreeBayes, TIDDIT. |
| `lane` | Sequencing lane, e.g. `L001`. Multiple lanes per sample are merged. |
| `fastq_1`, `fastq_2` | Paired-end FASTQ paths (local, or blob URLs for Azure Batch). |

### Optional columns: `status` and `sex`, best left out

Two sarek columns are accepted but not needed. nf-schema fills a missing column from its default in
`assets/schema_input.json`, so a sheet without them runs exactly as one that spells them out, and is
easier to read when an input is inspected or debugged (verified 2026-10-06: a two-sample sheet without
either column parses to `status: 0, sex: NA` and builds the same DAG as the test sheet).

| Column | Default when omitted | Meaning |
|--------|----------------------|---------|
| `status` | `0` | `0` = normal/germline, `1` = tumor. **ALE treats every sample as normal (`0`)**: that is what puts HaplotypeCaller in joint-germline mode. `1` (tumor) is not used; see [`docs/archive/sarek_fork_ideas.md`](../archive/sarek_fork_ideas.md). |
| `sex` | `NA` | `XX` / `XY`. **Only consumed by non-Tier-1 tools**, see below; a Tier-1 run never reads it. |

The restart sheets the pipeline writes under `<outdir>/csv/` carry the filled-in values (`status` `0`,
`sex` `NA`); a `--step` restart from them behaves the same.

**Requirement:** each `experiment` must have at least one normal sample (`status = 0`), always satisfied
when the column is left out or is `0` throughout.

## Example

```csv
experiment,sample,clonal_or_population,ploidy,lane,fastq_1,fastq_2
Ottilie_test,NODRUG-GM2,clonal,1,L001,…/NODRUG-GM2_R1.fastq.gz,…/NODRUG-GM2_R2.fastq.gz
Ottilie_test,CBR110-15-R3a,clonal,1,L001,…/CBR110-15-R3a_R1.fastq.gz,…/CBR110-15-R3a_R2.fastq.gz
```

## Notes for non-Tier-1 tools

Some columns/behaviours exist for tools outside the v1.0.0 Tier-1 set
(HaplotypeCaller, CNVKit, TIDDIT, Manta, snpeff) and are **inert on a Tier-1 run**:

### `sex`: Control-FREEC / ASCAT only

- **Leave the column out on a Tier-1 run.** CNVKit, Manta, TIDDIT, HaplotypeCaller and snpEff never read
  it; the schema fills `NA` and nothing validates it.
- It is consumed **only** by **Control-FREEC** (Tier-2: `meta.sex` → the FREEC `config.txt`,
  `modules/nf-core/controlfreec/freec/main.nf`) and **ASCAT** (not used in ALE).
- **Enforcement:** Sarek errors on `sex == 'NA'`, so also on a missing column, **only when `--tools`
  includes `ascat` or `controlfreec`** (`subworkflows/local/samplesheet_to_channel/main.nf`). Only those
  runs need the column.
- **Yeast convention when the column is needed: `XX`.** Yeast has no sex chromosomes; `XX` excludes chr Y
  from the analysis and avoids annotating a single copy of X/Y as a loss (see `docs/yAMP_docs/yAMP_design.md`).
  The ottilie test samplesheet and `generate_test_data.sh` still write `sex=XX` for all samples.
- **Open convenience item:** the schema default is `NA`, not `XX`, so a Tier-2 Control-FREEC run still
  types the value per row. Making the default `XX` is a one-line change to `assets/schema_input.json` that
  only the `csv/` restart sheets would show; it is a Tier-2 convenience, not a Tier-1 gap.
