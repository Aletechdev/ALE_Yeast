# Input samplesheet — format & conventions

Canonical reference for the ALE input samplesheet (`--input`). The format is adapted from nf-core/sarek
(originally human cancer), with ALE-specific columns and an **all-samples-are-normal** convention.
CLAUDE.md carries the short version; this doc has the full column reference + the notes that only matter
to non-Tier-1 tools.

## Columns

| Column | Meaning |
|--------|---------|
| `experiment` | Experiment ID (maps to Sarek's "patient"). Groups samples for joint calling. |
| `sample` | Sample ID in ALE format, e.g. `A1-F6-I1-R1`. |
| `status` | `0` = normal/germline, `1` = tumor. **ALE treats every sample as normal (`0`)** so HaplotypeCaller runs in joint-germline mode. `1` (tumor) is not used — see [`docs/archive/sarek_fork_ideas.md`](../archive/sarek_fork_ideas.md). |
| `clonal_or_population` | `clonal` for clonal isolate sequencing; `population` for bulk/pooled sequencing. Drives the AF thresholds in the joint HC hard filter. |
| `ploidy` | `1` = haploid, `2` = diploid (higher supported). Passed to HaplotypeCaller (`--sample-ploidy`), Control-FREEC, FreeBayes, TIDDIT. |
| `sex` | `XX` / `XY`. **Only consumed by non-Tier-1 tools** — see below. Defaults to `NA` if omitted. |
| `lane` | Sequencing lane, e.g. `L001`. Multiple lanes per sample are merged. |
| `fastq_1`, `fastq_2` | Paired-end FASTQ paths (local, or blob URLs for Azure Batch). |

**Requirement:** each `experiment` must have at least one normal sample (`status = 0`) — always satisfied
under the all-normal convention.

## Example

```csv
experiment,sample,status,clonal_or_population,ploidy,sex,lane,fastq_1,fastq_2
Ottilie_test,NODRUG-GM2,0,clonal,1,XX,L001,…/NODRUG-GM2_R1.fastq.gz,…/NODRUG-GM2_R2.fastq.gz
Ottilie_test,CBR110-15-R3a,0,clonal,1,XX,L001,…/CBR110-15-R3a_R1.fastq.gz,…/CBR110-15-R3a_R2.fastq.gz
```

## Notes for non-Tier-1 tools

Some columns/behaviours exist for tools outside the v1.0.0 Tier-1 set
(HaplotypeCaller, CNVKit, TIDDIT, Manta, snpeff) and are **inert on a Tier-1 run**:

### `sex` — Control-FREEC / ASCAT only

- **The Tier-1 tools never read `sex`** (CNVKit, Manta, TIDDIT, HaplotypeCaller ignore it). A Tier-1 run
  works regardless of the value, and never validates it.
- It is consumed **only** by **Control-FREEC** (Tier-2 — `meta.sex` → the FREEC `config.txt`,
  `modules/nf-core/controlfreec/freec/main.nf`) and **ASCAT** (not used in ALE).
- **Enforcement:** Sarek errors on a missing value (`sex == 'NA'`) **only when `--tools` includes
  `ascat` or `controlfreec`** (`subworkflows/local/samplesheet_to_channel/main.nf`). Otherwise `NA` is fine.
- **Yeast convention: `XX`.** Yeast has no sex chromosomes; `XX` excludes chr Y from the analysis and
  avoids annotating a single copy of X/Y as a loss (see `docs/yAMP_docs/yAMP_design.md`). The ottilie test
  samplesheet and `generate_test_data.sh` set `sex=XX` for all samples.
- **Open convenience item:** there is no auto-fill/default-to-`XX` — the value is typed per row. Since it
  only matters for Control-FREEC (Tier-2), auto-filling is a Tier-2 convenience, not a Tier-1 gap.
