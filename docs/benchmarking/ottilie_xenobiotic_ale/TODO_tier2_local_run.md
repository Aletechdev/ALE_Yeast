# TODO: Tier 2 Local Run

> **⚠️ ON HOLD (2026-08):** Tier 2 is deferred and may be retired. Current focus is the 2-sample
> chr-subset test set, with the 4-sample full-depth pilot (already staged on Azure) next. Do not
> action this checklist until Tier 2 is re-confirmed — see the tier table in [README.md](README.md).

## 1. Free Up Storage

Current: 242 GB free, need ~380 GB for Tier 2 (FASTQs + work dir + output).

- [ ] **Upload Methanol archive to blob** (~7-10 GB tar.gz)
      `aledata / aledata / Yeast/archive-projects/Methanol.tar.gz`
      Compression in progress.
- [ ] **Delete local Methanol** after upload verified (`~/Docs/ALE_projects/Methanol/`, 119 GB)
- [ ] **Remove old Nextflow work dirs** (~198 GB total):
  - [ ] `work_CENPK/` (133 GB)
  - [ ] `work_CENPK_allNormal/` (41 GB)
  - [ ] `work_CENPK_allNormal_changePloidy/` (21 GB)
  - [ ] `work_test_001/` (2.6 GB) + `work_CENPK_subset/` (1.5 GB) + `work/` (2.9 GB)
- [ ] **Docker prune** unused images (~18 GB): `docker image prune`
- [ ] **Remove `Docs/tmp_repo/`** (6.5 GB) — temp sarek + aledb clones
- [ ] **Optional**: Remove `Docs/LongRead/` (9.6 GB) if no longer needed
- [ ] **Optional**: Archive `Rhodo_coumarate_full/` (129 GB) to blob — same approach as Methanol

**Target**: ~550+ GB free after cleanup (plenty for Tier 2).

## 2. Download Tier 2 FASTQs

- [ ] **Download 86 samples from Azure Blob** (~40 GB, ~15-30 min)
      ```bash
      bash docs/benchmarking/ottilie_xenobiotic_ale/01_data_retrieval/fastq/download_tier2_from_blob.sh
      ```
      Source: `aledata/aledata/Yeast/ottilie_xenobiotic_ale/fastq/`
      8 already downloaded, 78 remaining.

- [ ] **Verify FASTQ integrity** — spot-check file sizes, count read pairs
      ```bash
      ls -lh data/ottilie/fastq/*.fastq.gz | wc -l  # expect 172 files (86 x R1+R2)
      du -sh data/ottilie/fastq/                      # expect ~40 GB
      ```

## 3. Prepare Tier 2 Pipeline Run

- [ ] **Generate Tier 2 samplesheet** (`data/ottilie/samplesheet_tier2.csv`)
      Adapt from pilot samplesheet — 86 samples, all status=0, ploidy=1.
      Script needed or manual from `tier2_crispr_validated_clones.csv`.

- [ ] **Create `run_ottilie_tier2.sh`** in `03_pipeline/`
      Based on `run_ottilie_pilot.sh`, adjusted for:
      - Tier 2 samplesheet
      - Output dir: `output_ottilie_tier2/`
      - Work dir: `work_ottilie_tier2/`
      - Same tools: haplotypecaller, cnvkit, controlfreec, tiddit, snpeff
      - `--joint_germline --split_haplotypecaller_joint_vcf`

- [ ] **Verify disk space** before launch (~380 GB needed)

## 4. Run Tier 2 Pipeline

- [ ] **Launch pipeline**
      ```bash
      bash docs/benchmarking/ottilie_xenobiotic_ale/03_pipeline/run_ottilie_tier2.sh
      ```
      Expected runtime: ~2-3 days (single node, 4 CPU, serial).

- [ ] **Monitor progress** — check `work_ottilie_tier2/` growth, Nextflow logs

### Fallback: Joint Calling OOM on D4as (16 GB)

If HaplotypeCaller joint genotyping fails due to memory (86 GVCFs loaded simultaneously),
move the run to a larger VM using Nextflow `-resume`:

1. **Compress work dir + inputs** and upload to blob:
   ```bash
   tar cf - work_ottilie_tier2/ | pigz > work_ottilie_tier2.tar.gz
   azcopy copy work_ottilie_tier2.tar.gz "https://aledata.blob.core.windows.net/aledata/tmp/"
   # Also upload data/ottilie/ if not already on blob
   ```
2. **Provision a D16as_v5** (16 vCPU / 64 GB RAM) — only needed temporarily for joint calling.
3. **Restore to the same absolute path** (`/home/azureuser/Docs/ALE_nextflow/`) so `-resume` cache matches.
4. **Add a larger VM profile** to `nextflow.config`:
   ```groovy
   azureD16as {
       params.max_cpus = 16
       params.max_memory = '60.GB'
       params.max_time = '72.h'
   }
   ```
5. **Re-run with** `-profile azureD16as,docker -resume` — all completed per-sample tasks are skipped,
   only the joint calling step re-runs.

Per-sample steps (alignment, individual variant calling, CNV) all fit within 16 GB.
Only joint calling loads all GVCFs at once. A D8as_v5 (32 GB) may suffice; D16as_v5 (64 GB) is safe.

## 5. Validate Results

- [ ] **Run SNV/INDEL concordance** against Sup Data 4
      ```bash
      python docs/benchmarking/ottilie_xenobiotic_ale/04_validate/snv_indel_concordance.py
      ```

- [ ] **Run CNV concordance** against Sup Data 5
      ```bash
      python docs/benchmarking/ottilie_xenobiotic_ale/04_validate/cnv_concordance.py
      ```

---

**Storage budget** (after cleanup):

| Item | Size |
|------|------|
| Tier 2 FASTQs | ~40 GB |
| Tier 2 work dir | ~280 GB |
| Tier 2 output | ~60 GB |
| **Total** | **~380 GB** |
