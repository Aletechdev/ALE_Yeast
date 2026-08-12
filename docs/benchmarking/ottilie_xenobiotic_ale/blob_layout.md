# `az://aletest/ottilie/` — which dataset is which

Canonical copy of the note published at `az://aletest/ottilie/README.md`. **Edit this file, then
re-upload** (command at the bottom) so the two never drift.

> ⚠️ **Two ottilie datasets share this prefix, and they are NOT interchangeable.** One is a
> chromosome subset of two samples; the other is four samples at full depth across all chromosomes.
> Mixing them yields results that look plausible and mean nothing — a variant "missing" because its
> chromosome was never in the input, or a runtime that reflects 356 MB when you thought it was 4 GB.

## The two datasets

| | **Test set** — 2 samples, 4 chromosomes | **Pilot set** — 4 samples, all chromosomes |
|---|---|---|
| FASTQs | `ottilie/v1/fastq_test/` | `ottilie/v1/fastq_pilot_full/` |
| Reference | `ottilie/v1/S288C_reference_test/` | `ottilie/v1/S288C_reference/` |
| Samplesheet | `ottilie/v1/samplesheet_test_az.csv` | `ottilie/v1/samplesheet_pilot_az.csv` |
| Samples | `NODRUG-GM2`, `CBR110-15-R3a` | those two **+** `Doxorubicin16-R2b`, `Carmaphycin-R9-2` |
| Chromosomes | **I, IV, VII, XV only** | all 16 |
| Size | ~356 MB FASTQ · ~41 MB reference | ~4.0 GB FASTQ · ~79 MB reference |
| Truth set | 4 SNVs + a chr I duplication | — not a contract test |
| Purpose | the **release contract test** | benchmarking · the cold-pool disk measurement |
| Also published publicly? | ✅ yes, see *Access* below | ❌ **no** — private only |

**Telling them apart at a glance.** Every file names its own dataset. Test-set files carry `_test` or
the chromosome list (`NODRUG-GM2_chrI_IV_VII_XV_R1.fastq.gz`, `S288C_R64_test.fa`); pilot FASTQs carry
the sample name, the SRA accession and `_allchr`:

```
fastq_test/       NODRUG-GM2_chrI_IV_VII_XV_R1.fastq.gz          ← 4 chromosomes
fastq_pilot_full/ NODRUG-GM2_SRR10985539_allchr_R1.fastq.gz      ← full depth, all 16
```

⚠️ **Never stage pilot FASTQs under their bare SRA names.** `SRR10985539_1.fastq.gz` says nothing
about sample, depth or chromosome coverage — it is the one naming that could sit beside the test
files without looking wrong. [`upload_pilot_data.sh`](01_data_retrieval/upload_pilot_data.sh) does the
renaming; use it rather than uploading by hand.

## What the pilot reference does and does not contain

| Consumed as | File | |
|---|---|---|
| `fasta` | `S288C_R64.fa` | 12 MB |
| `genbank` | `S288C_R64_ensembl_chrnames.gb` | 32 MB |
| `snpeff_cache` | `snpeff_cache/R64-1-1.105/` | 23 MB |
| `chr_dir` | `chromosomes/` (17 files) | 12 MB — Control-FREEC only; optional |
| `report_gff3` | `S288C_R64.gff3` | 5.5 MB — was already here, shared with the test run |

⚠️ **The bwa-mem2 indices are deliberately absent** (`.0123`, `.bwt.2bit.64`, `.amb`, `.ann`, `.pac`,
and `.fai`/`.dict`). The validated cloud run does not pass `fasta_fai`/`bwa`/`dict` as params, so Sarek
builds them in-run. Uploading them changes nothing unless they are *also* passed — and passing them
would alter the task graph, breaking comparability with the run being measured against.

## Lineage — the two sets are not independent

```
SRA PRJNA590203 ─► 4 pilot samples, full depth ─► pipeline run with --save_mapped ─► CRAMs
                                                        │
                                                        ▼  2 of the 4 CRAMs, 4 chromosomes extracted
                                                   test set (356 MB)
```

So the test set is a **chromosome subset, not a read-subsample**: per-base depth on the retained
chromosomes is the pilot's depth, which is why the two share sample names. Full lineage:
[`DATA_PROVENANCE.md`](DATA_PROVENANCE.md).

## Access

| Account / container | Public? | Holds |
|---|---|---|
| `aledata` / `aletest` | **private** | everything above, plus `workDir` and run outputs |
| `aletestdatapublic` / `releases` | **public, no SAS** | the **test set only**, for credential-free onboarding |

⚠️ **Nothing else belongs on the public account** — in particular no real project data (dicarboxylic
acids / CENPK), which is not public. The pilot set stays private too. `upload_pilot_data.sh` refuses
to run against the public account or any container whose `publicAccess` is not `None`;
[`publish_test_data.sh`](01_data_retrieval/publish_test_data.sh) is the only script that writes there.

⚠️ **`workDir` must live in this same container** whenever a run uses the Entra service principal:
Nextflow mints one container-scoped SAS and reuses it for every blob URL, so a node cannot read
another container even in the same account. See
[`azure_batch_execution.md` §3](../../dev-practices/azure_batch_execution.md).

## Re-uploading this note

```bash
az storage blob upload --account-name aledata -c aletest --auth-mode login --overwrite \
    --name ottilie/README.md \
    --file docs/benchmarking/ottilie_xenobiotic_ale/blob_layout.md
```
