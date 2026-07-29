# Setting up yAMP on a new machine

Bare Linux VM → a verified pipeline run. Follow it top to bottom.

**The pipeline needs exactly two things: Docker and Nextflow.** Every bioinformatics tool it runs
(GATK, BWA, CNVKit, Manta, TIDDIT, SnpEff, SURVIVOR, …) is pulled as a container at runtime, so
nothing else has to be installed.

> **This document is validated by being followed.** It was written on a machine that already
> worked, so some steps are marked **[unverified]** — plausible but not yet confirmed on a genuinely
> fresh box. If a step is wrong, fix it here in the same session; that is the only test this guide
> gets. See [Reporting deviations](#reporting-deviations).

---

## 0. Prerequisites

| | Requirement |
|---|---|
| **OS** | Linux **x86_64**. Apple Silicon / ARM is **not supported** — GATK and MultiQC tasks stall or hang. |
| **CPU / RAM** | 4 vCPU / 16 GB is the validated dev size. Less RAM works if you lower the clamp (step 5), but tasks run less concurrently. |
| **Disk** | **~10 GB** for the test run: ~400 MB test data + ~8 GB work dir + ~200 MB output. *(Ignore the 64 GB `data/ottilie/` on the original dev VM — that's full-depth pilot FASTQs from earlier work, not part of setup.)* |
| **Network** | Needed for: git clone, conda, the test-data download (~400 MB), the Nextflow engine self-fetch, and container pulls on first run. |
| **Privileges** | `sudo` for installing Docker. |

---

## 1. Docker

Install per the [official instructions](https://docs.docker.com/engine/install/) for your
distribution.

Then add yourself to the `docker` group so Nextflow can launch containers without `sudo`:

```bash
sudo usermod -aG docker $USER
```

⚠️ **You must start a new login session for this to take effect** — log out and back in, or run
`newgrp docker`. This is the single most common setup failure: `docker ps` works under `sudo` but
the pipeline fails with a permission error on the Docker socket.

Verify **without sudo**:

```bash
docker run --rm hello-world
```

---

## 2. Conda + the Nextflow environment

Install [Miniforge](https://github.com/conda-forge/miniforge#install) if conda isn't present, then:

```bash
git clone git@github.com:Aletechdev/ALE_Yeast.git
cd ALE_Yeast
conda env create -f environment.yml
conda activate nf-env
```

This installs Nextflow **25.10.2**, Java 17, and `nf-test` (used to verify the install in step 7).

⚠️ **Do not `conda install nextflow` unpinned.** That resolves to the latest release (26.x), which
**cannot parse this pipeline's config** — you get `Cannot read project manifest -- Config parsing
failed`, which does not mention the version. Details:
[`ale_sarek_upgrade_runbook.md`](../dev-practices/ale_sarek_upgrade_runbook.md).

> In this environment use `python`, not `python3` — the env's interpreter is at the conda prefix.

---

## 3. Fetch the test data

Public Azure Blob, no credentials, no `az login`:

```bash
bash docs/benchmarking/ottilie_xenobiotic_ale/01_data_retrieval/download_test_data.sh
```

Downloads ~400 MB into `data/ottilie/` (gitignored), verifies a SHA256 checksum, and **writes
`data/ottilie/samplesheet_test.csv` with this machine's absolute paths**.

⚠️ **Never copy that samplesheet between machines.** It contains machine-local absolute FASTQ paths;
the script regenerates it correctly per machine. Full lineage:
[`DATA_PROVENANCE.md`](../benchmarking/ottilie_xenobiotic_ale/DATA_PROVENANCE.md).

---

## 4. Tell the pipeline how big this machine is

`conf/base.config` sizes every task for the cloud target (4 vCPU / 32 GB). On a smaller machine
tasks would request more RAM than exists and never get scheduled, so you must supply a **clamp**:

```bash
cp conf/mymachine.config conf/$(hostname).config
```

Edit the two numbers in the copy:

```groovy
process {
    resourceLimits = [ cpus: <your vCPUs>, memory: '<RAM minus ~2 GB>.GB', time: '72.h' ]
}
```

Deliberately **no `executor` block** — without one, Nextflow's local executor auto-detects the host
and sizes concurrency itself. Setting a pool by hand that barely exceeds one task's request can
deadlock the scheduler ([`nextflow_local_executor_deadlock.md`](nextflow_local_executor_deadlock.md)).

Keep the file **params-free**: `-c` outranks `-profile`, so any `params.*` in it would silently
override the profile. Background:
[`compute_resources.md`](../dev-practices/compute_resources.md).

> ❌ Do **not** use `-profile azureD4as` — that profile hard-codes the original dev VM's ceilings
> and per-task tuning.

---

## 5. (Optional) swap

On a memory-tight VM, swap gives failing tasks somewhere to go instead of being OOM-killed. The dev
VM runs 8 GB: [`azure_vm_swap_setup.md`](azure_vm_swap_setup.md).

---

## 6. First run

```bash
export NXF_VER=25.10.4
nextflow -c conf/$(hostname).config run main.nf -profile ottilie_test,docker \
    --outdir ./output_ottilie_test --generate_reports
```

Expect the first run to be slower than later ones:

- `NXF_VER` makes Nextflow **download that exact engine** before starting (needs network).
- Every process pulls its container image on first use.

Runtime once warm is roughly **15 minutes** on 4 vCPU / 16 GB.

---

## 7. Verify

**Outputs exist:**

```bash
ls output_ottilie_test/mutation_reports/index.html
ls output_ottilie_test/mutation_reports/data/    # cn_cohort_*.csv, sv_cohort_matrix_*.csv
```

Open `output_ottilie_test/mutation_reports/index.html` in a browser.

**Biological truth set** — the test data has known variants in `CBR110-15-R3a`: **4 SNVs**
(chr IV:205,738 · IV:1,184,212 · VII:233,903 · XV:639,861) and a **chr I whole-chromosome
duplication**. They should appear in the sample's reports.

**Contract test** (the authoritative check — asserts file tree, cohort CSV contents, report data,
and the joint VCF):

```bash
nf-test test -c tests/nf-test-ottilie.config tests/ottilie_e2e.nf.test
```

**[unverified]** The nf-test path uses its own clamp (`tests/ottilie_nftest_resources.config`, set
to 4 cpu / 14 GB) and **ignores** your `conf/<hostname>.config`. On a machine smaller than the dev
VM you may need to lower those numbers too — see
[`compute_resources.md`](../dev-practices/compute_resources.md) § "nf-test resources".

---

## 8. Running your own data

See [the root README](../../README.md#running-your-own-data). You'll additionally need a reference
FASTA and a SnpEff cache — build both from a GenBank file with
`docs/prepare_input/process_GeneBank/process_genbank_auto.sh`.

---

## Troubleshooting

| Symptom | Cause |
|---|---|
| `Cannot read project manifest -- Config parsing failed` | Nextflow 26.x. Use 25.10.x (step 2). |
| Permission denied on the Docker socket | Not in the `docker` group, or the group hasn't taken effect — start a new login session (step 1). |
| Tasks queue but never start; `No more task to compute` | Executor pool too tight — see [`nextflow_local_executor_deadlock.md`](nextflow_local_executor_deadlock.md). |
| A task is OOM-killed | Clamp exceeds real RAM (step 4), or add swap (step 5). |
| "sample-sheet only contains normal-samples" | Usually an upstream schema/config failure, not the samplesheet — [`troubleshooting.md`](../dev-practices/troubleshooting.md). |
| Pipeline aborts without `--skip_tools baserecalibrator` | Expected. BQSR needs known-sites VCFs, which custom microbial genomes lack. The `ottilie_test` profile sets this for you. |

---

## Reporting deviations

If a step here didn't match reality, **fix this file** rather than working around it. Note which
step, what actually happened, and on what OS/VM size. The **[unverified]** markers above are the
places most likely to be wrong — they were inferred from a machine that was already configured, not
observed on a fresh one.
