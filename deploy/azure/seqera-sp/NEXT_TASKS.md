# Pending: slimming the Azure docs (CE-as-code is done)

Self-contained handoff — everything needed to start a fresh session without re-reading
[`RUNBOOK.md`](RUNBOOK.md) end to end. Written 2026-08-07; Task 1 closed 2026-08-11.

---

## Where things stand

**Azure Batch works end to end, from a Seqera-hosted head job, with an Entra service principal.**
Run `3C5zYMYY5M32dO` completed 170/170 tasks with all **9 cohort deliverables byte-identical** to the
local-head-job baseline. Fusion was verified separately (also 170/170, deliverables identical).
Nothing below is a blocker — this is follow-up work.

### Live resources

| Thing | Value |
|---|---|
| Workspace | `DTU-Biosustain/RECON-ALE` = `79597273081110` |
| Azure credential | `azure_SP_cfb_ale_mutations_pipeline` (`azure_entra`) — SP secret expires **2027-07-31** |
| GitHub credential | `github_ALE_Yeast_finegrained` — `Contents: Read`, expires **2027-08-07** |
| Launchpad pipeline | `yAMP-ottilie-test` → CE `…_autoScale_manual_noFusion` |
| **CE (default, non-Fusion)** | `ale-ottilie-nf25104-bigdisk_autoScale_manual_noFusion` = `5u0qeS7p3cNmOITd5Gdhe1` |
| **CE (Fusion)** | `ale-ottilie-nf25104-bigdisk_autoScale_manual` = `6zsRCxeGmUoiae4OVOGSKO` |
| ⚠️ CEs to DELETE | `ale-ottilie-nf25104-bigdisk` (`6buIkRXLMZFgDXs5NkyuH`), `…-bigdisk_fusion` (`5acBaUVwry7j0DJmLnwyh0`) — **fixed-size**, pools manually resized to 0 |
| Verified output baseline | `az://aletest/seqera-runs/2026-08-06-04` (534 blobs) · local-head-job baseline `az://aletest/ottilie-azurebatch-out` (540) |

Create and verify CEs from code — never by hand:

```bash
./13_create_compute_env.sh <new-name> [--fusion]   # import a known-good config, then verify
./12_verify_compute_env.sh <ce-name-or-id>         # asserts autoScale, disks, NXF_VER, workDir
./13_create_compute_env.sh <name> --delete         # disposes the pools and their disks too
```

---

## ~~Task 1 — create compute environments from code~~ ✅ DONE 2026-08-11

**Not built as specified.** The task called for a raw REST creator "since the CLI cannot express the
one field that matters". That premise was wrong: `tw compute-envs export`/`import` round-trip
`autoScale` fine — neither subcommand had been tried, because the 2026-08-07 investigation stayed
inside `add ... forge`'s flag set and generalised from it. **No API client was written.**

Use [`13_create_compute_env.sh`](13_create_compute_env.sh) `<name> [--fusion|--delete]`. It patches
[`ce_import_template.json`](ce_import_template.json) (a readback of the working non-Fusion CE),
`tw compute-envs import`s it, and calls [`12_verify_compute_env.sh`](12_verify_compute_env.sh).
Verified end to end with a throwaway CE: 6/6 checks, Azure `enableAutoScale: True`, drained to `0 + 0`
after 17 min, deleted with pools disposed. Detail in [`RUNBOOK.md`](RUNBOOK.md) → *2026-08-11*.

Two things worth carrying forward:

- **`tw add ... forge` CAN set autoscale** via explicit `--head-no-auto-scale=false
  --worker-no-auto-scale=false` (undocumented; [tower-cli#658](https://github.com/seqeralabs/tower-cli/issues/658)).
  Kept as an escape hatch only — that route has **no flags** for `jobMaxWallClockTime`,
  `deleteJobsOnCompletion`, `deleteTasksOnCompletion` or `terminateJobsOnCompletion`, so it silently
  takes Platform defaults for the four job-lifecycle settings our CEs pin.
- **Upstream fix [#659](https://github.com/seqeralabs/tower-cli/pull/659) is unmerged** and 0.38.0 is
  the latest release. Re-check when it lands; the job-lifecycle gap will remain regardless.

⚠️ Still true, and still the reason to verify before launching: the Seqera API **does not validate
payloads** (a bogus `discriminator` returned HTTP 200), CEs are **immutable**, every creation costs
~5 node-minutes (`1 + 1` at first is by design — `0 + 0` after ~15 min is the proof), and a stray
fixed-size CE is the expensive mistake.

📌 `ce_reference_config.json` — the template for the abandoned REST route — was **deleted
2026-08-11**. It was never committed, and keeping two templates in different shapes would only
invite drift. [`ce_import_template.json`](ce_import_template.json) is the single template.

---

## Task 2 — slim down the Azure deployment docs

They have grown by accretion during debugging: **1,914 lines across four files.**

| File | Lines | Sections | Role |
|---|---|---|---|
| [`RUNBOOK.md`](RUNBOOK.md) | 1,047 | 35 | dated audit trail — *what was actually run* |
| [`azure_batch_execution.md`](../../../docs/dev-practices/azure_batch_execution.md) | 581 | 21 | durable gotchas — *what to know before changing anything* |
| [`output_comparison.md`](../../../docs/dev-practices/output_comparison.md) | 181 | — | which outputs are deterministic |
| [`../README.md`](../README.md) | 105 | — | SP provisioning overview |

### The convention to restore

`CLAUDE.md` states it: **operational summary + pointer in `CLAUDE.md`, detail in `docs/`, dated record
in `RUNBOOK.md`.** The split is sound; what has drifted is that **the same findings are now written out
in full in two or three places** (the disk/DiskFull story, the dual-pool autoscale incident, and the
same-container rule each appear in both the runbook and the gotchas doc).

### Suggested approach

- **`RUNBOOK.md` should shrink the most.** It is an audit trail, so entries should say *what was run,
  when, and what was concluded* — then link. Explanations belong in `azure_batch_execution.md`.
  Superseded entries (the deploy-key saga, the classic PAT, phase-by-phase narration) can be collapsed
  behind `<details>` or reduced to one line plus a pointer.
- **Keep every ⚠️ that cost real time or money.** The value of these docs is precisely the
  counter-intuitive findings; do not slim those away. Candidates to keep verbatim: the container-scoped
  SAS rule, the single-use ephemeral config, `NXF_VER` beating the launch-UI selector, dual-pool
  autoscale, `.command.err` being empty while the real error is in `.command.log`.
- **Prune what is now historical**: the plan file is closed; Phase 1–6 narration matters far less than
  the resulting rules.
- ⚠️ **Do not delete corrections.** Several entries record claims that turned out to be *wrong*
  (the "~30 GB default OS disk", concurrency as the DiskFull cause, the disk baseline that was
  measured on warm nodes). Those exist so the wrong conclusion is not re-derived — keep them, but they
  can be compressed to a line each.
- Re-run `python docs/dev-practices/check_docs.py` afterwards — **broken links must be 0**.

---

## Also open (smaller)

- 🧊 **Cold-pool disk baseline.** Peak usage measured at **65.2 G of 246.9 G (26%)**, but on *warm*
  nodes (~340 tasks across two runs), so base-OS vs pipeline-image split is unknown and the
  128-vs-256 GB sizing decision is unresolved. Rerun with [`../../../conf/disk_probe.config`](../../../conf/disk_probe.config)
  on a pool that has drained to 0. The probe now samples `/mnt` too — needed to see whether Fusion's
  local cache competes with Docker for the ephemeral disk *before* moving Docker there.
- **Does Fusion lift the same-container rule?** Non-Fusion, it does not: run `48kJmc9QY6Q3h9` with
  `workDir` in a different container from the inputs failed 0/6 tasks with `Unable to download path`.
  Repeat that exact launch on the Fusion CE — it is a clean predicted-failure baseline.
- **`outdir` in a different container under a Platform head job** — verified locally only.
- **Docker data-root → `/mnt`** via a pool start task (needs a `manual` CE, not Forge). Blocked on the
  cold-pool baseline above.
- **Swap the personal PAT for an org-owned GitHub App** when an org owner is available.
