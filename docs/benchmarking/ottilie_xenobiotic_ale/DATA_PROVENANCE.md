# Ottilie Test Data — Provenance & Lineage

How the ottilie benchmark/test data is produced, from public SRA reads down to the
2-sample nf-test dataset. Every stage below has a tracked script; the large data
artifacts are gitignored (see [Storage & durability](#storage--durability)).

## Source

- **Publication:** Ottilie et al., *Commun Biol* 5:128 (2022) — https://doi.org/10.1038/s42003-022-03076-z
- **BioProject:** PRJNA590203 (363 yeast ALE runs)
- **Run table:** `data/ottilie/PRJNA590203_runinfo.csv` (all SRR accessions)
- **Test samples (2):**
  | Sample | SRR | Role |
  |--------|-----|------|
  | NODRUG-GM2 | SRR10985539 | parent (ancestral) |
  | CBR110-15-R3a | SRR10985585 | evolved |

## Truth set (must stay detectable through any subsampling)

- **CNV:** Chr I whole-chromosome duplication (cn=3, log2≈0.329) in CBR110-15-R3a
- **SNVs (4):**
  | Position | Change | Gene |
  |----------|--------|------|
  | IV:205738 | C>A | RPO21 |
  | IV:1184212 | G>T | TRR1 |
  | VII:233903 | G>A | ROG1 |
  | XV:639861 | G>T | YRR1 |

## Lineage

```
BioProject PRJNA590203
  │  PRJNA590203_runinfo.csv  (+ resolve_sra_accessions.py: sample ↔ SRR)
  ▼
[1] download_all_fastq.sh ──────────────► data/ottilie/fastq/     (full FASTQs, ~90 samples)
    (SRA fetch, batched)             └───► Azure Blob             (off-machine archive)
  │
  ▼
[2] run_ottilie_pilot.sh (--save_mapped) ► output_ottilie/preprocessing/markduplicates/*.cram
    (full pipeline run, 4 pilot samples)   (aligned CRAMs — 4 samples incl. the 2 test samples)
  │
  ▼
[3] generate_test_data.sh ──────────────► data/ottilie/fastq_test/     (chr I/IV/VII/XV subset)
    (chr-subset extraction)          └───► data/ottilie/samplesheet_test.csv   (auto-written)
  │
  ▼
[4] conf/test/ottilie_test.config  +  tests/ottilie_e2e.nf.test   (the nf-test)
```

## Stages

### [1] Download raw FASTQs — `01_data_retrieval/download_all_fastq.sh`
Reads SRR accessions from `PRJNA590203_runinfo.csv`, downloads from SRA in batches
(`prefetch`/`fasterq-dump`), and **uploads each batch to Azure Blob** (keeps local disk
under control). Sample↔SRR mapping via `resolve_sra_accessions.py`. Subset variants:
`download_pilot_fastq.sh`, `download_tier2_fastq.sh`, `download_tier2_from_blob.sh`.
- Output: `data/ottilie/fastq/` (full FASTQs) — gitignored; archived to Azure Blob.

### [2] Full pipeline run → CRAMs — `03_pipeline/run_ottilie_pilot.sh`
Runs the ALE pipeline on the 4 pilot samples (`samplesheet_pilot.csv`) with `--save_mapped`,
which publishes the aligned/dedup CRAMs. This is what produced `output_ottilie/`.
Canonical command (from `run_ottilie_pilot.sh`):
```bash
nextflow run main.nf -profile azureD4as,docker \
  -w work_ottilie \
  --input data/ottilie/samplesheet_pilot.csv \
  --outdir output_ottilie \
  --genome null --igenomes_ignore \
  --fasta data/ottilie/S288C_reference/S288C_R64.fa \
  --chr_dir data/ottilie/S288C_reference/chromosomes \
  --genbank data/ottilie/S288C_reference/S288C_R64_ensembl_chrnames.gb \
  --snpeff_db R64-1-1.105 --snpeff_cache data/ottilie/S288C_reference/snpeff_cache \
  --skip_tools baserecalibrator \
  --tools snpeff,cnvkit,tiddit,manta,controlfreec,haplotypecaller \
  --split_fastq 0 --joint_germline --save_mapped \
  --split_haplotypecaller_joint_vcf --hard_filter_haplotypecaller_joint \
  -c bin/nextflow.config -resume
```
- Output: `output_ottilie/preprocessing/markduplicates/{CBR110-15-R3a,Carmaphycin-R9-2,Doxorubicin16-R2b,NODRUG-GM2}/*.md.cram` — gitignored.
- The 2 test samples' CRAMs (CBR110-15-R3a ~245 MB, NODRUG-GM2 ~218 MB) are the fast-path input for stage [3].

### [3] Generate test dataset — `01_data_retrieval/generate_test_data.sh`
Extracts reads on chromosomes I/IV/VII/XV for the 2 test samples and subsets the
S288C reference to match. Two modes:
- `--from-cram` (default): extract from the stage-[2] CRAMs (fast; needs `output_ottilie/`).
- `--from-sra`: fully reproducible — download from SRA → align → extract (no local deps).
- Fallback: if the CRAMs are gone but the full FASTQs (`data/ottilie/fastq/`) are present, it realigns from those.
- **Also writes** `data/ottilie/samplesheet_test.csv` with `$REPO_ROOT`-based absolute paths
  (machine-portable; regenerate on any machine — see [WP3 test-data portability]).
- Outputs (gitignored): `data/ottilie/fastq_test/` (~356 MB), `data/ottilie/S288C_reference_test/`, `data/ottilie/samplesheet_test.csv`.

### [4] nf-test — `conf/test/ottilie_test.config` + `tests/ottilie_e2e.nf.test`
The `ottilie_test` profile points at the stage-[3] outputs. Run:
```bash
nf-test test -c tests/nf-test-ottilie.config tests/ottilie_e2e.nf.test
```

## Storage & durability

| Artifact | Location | Gitignored? | Off-machine backup |
|----------|----------|-------------|--------------------|
| Full FASTQs (~90 samples) | `data/ottilie/fastq/` | yes | ✅ Azure Blob (via `download_all_fastq.sh`) |
| Pilot CRAMs (4 samples) | `output_ottilie/…/markduplicates/` | yes | ❌ regenerable from FASTQs or SRA |
| Test FASTQs (2 samples, chr-subset) | `data/ottilie/fastq_test/` | yes | ❌ regenerable via `generate_test_data.sh` |
| Reference (test subset) | `data/ottilie/S288C_reference_test/` | yes | ❌ regenerable |
| Samplesheet | `data/ottilie/samplesheet_test.csv` | yes | ❌ regenerated by `generate_test_data.sh` |

**Ultimate source of truth:** SRA (PRJNA590203). Everything downstream is reproducible via
`--from-sra`. The raw FASTQs are additionally archived on Azure Blob. The CRAMs are the only
intermediate with no dedicated backup, but they are cheaply regenerated from the FASTQs (stage [2])
or SRA.

## Notes / TODO

- **CI/cloud (post-v1.0.0):** GitHub Actions / Seqera Cloud can't use these local paths (data
  gitignored; two files >100 MB). Needs a blob-URL samplesheet variant + hosted data. See the
  v1.0.0 plan's "CI / cloud portability" task.
  - **Decision:** host the current 356 MB `fastq_test/` on blob (do NOT shrink) — keeps the
    validated truth set, zero empty-output risk. Intra-Azure streaming is fast.
  - **Bonus (v1.0.0 nice-to-have):** a **public read-only** blob container for `fastq_test/` +
    test reference, so anyone can reproduce the ottilie test with no Azure credentials
    (nf-core/test-datasets style). Record the container URL here once created.
- **CI-tier dataset (post-v1.0.0):** 356 MB is large for per-run CI. A `generate_ci_test_data.sh`
  doing chr-subset **+ calibrated read-subsampling with a truth-set validation gate** (assert the
  4 SNVs + chr I dup remain detectable) would give a fast CI dataset. SNV depth is the binding
  constraint — subsample only as far as the truth SNVs stay callable.
