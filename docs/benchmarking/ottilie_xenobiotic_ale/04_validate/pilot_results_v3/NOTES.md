# Pilot validation v3 — the current recipe (2026-09-09)

Re-score of the 4-sample full-depth pilot after two recipe changes: fastp adapter + 3′ tail trimming
on by default (`948163c`, 2026-09-04) and the per-sample HaplotypeCaller hard filter out of the ALE
recipe (`4acec56`, 2026-09-08). `pilot_results_v2/` (2026-08-26, untrimmed reads, hard filter on) is
kept intact; this directory is generated the same way from a fresh run. Read v2's `NOTES.md` for the
two hard sites and the CN interpretation — nothing there changed.

## Run

| | |
|---|---|
| Pipeline output | `output_ottilie_pilot_2026-09-09/` (local VM, `azureD4as,docker`) |
| Launcher | `03_pipeline/run_ottilie_pilot.sh` — fresh run, no `-resume`; recipe from `conf/test/ottilie_common.config` (`--hard_filter_haplotypecaller_joint` no longer passed) |
| Pipeline code | commit `d4efac9`; Nextflow 25.10.4 |
| Tasks / wall time | **287** succeeded, 0 failed, 1 h 15 min, 4.3 CPU-h (v2's run: 324; the 2026-09-02 run: 315 — the 28-task drop is the hard-filter family, 7 tasks × 4 samples) |
| Truth set | `data/ottilie/pilot_truth_set.csv` — unchanged (43 events, Sup Data 4 + 5) |
| Validation | `04_validate/run_validate_all_pilot_v3.sh` = the v2 wrapper with only the output/results dirs changed: `validate_all.py --output-dir output_ottilie_pilot_2026-09-09 --results-dir pilot_results_v3 --ploidy 1 --save-vcfs`, then `snv_indel_concordance.py --pass-only` |

## Result — sensitivity unchanged (measured)

| | v2 (untrimmed, hard filter on) | **v3 (current recipe)** |
|---|---|---|
| SNV/INDEL, all variants | 41/42 (97.6 %) — SNP 21/21, INDEL 20/21 | **41/42 (97.6 %)** — SNP 21/21, INDEL 20/21 |
| SNV/INDEL, PASS-only | 40/42 (95.2 %) | **40/42 (95.2 %)** |
| Undetected | `Mito:53278` 14-bp deletion (not in the reads — v2 NOTES) | same one site |
| PASS-only extra miss | `XIV:781921` PAU6 G>A, soft-filtered (multi-mapper locus) | same |
| CNV (Sup Data 5) | 1/1 — chr I, cn = 3, log2 0.329, 100 % of chromosome | 1/1 — chr I, cn = 3, **log2 0.328**, 100 % |

Per sample (all variants → PASS-only; precision = evolved-minus-parent calls found in Sup Data 4):

| Sample | Truth | v2 | v3 | Precision v2 → v3 (all / PASS) |
|---|---|---|---|---|
| CBR110-15-R3a | 4 | 4/4 → 4/4 | 4/4 → 4/4 | 9.1 % → **9.5 %** / 12.5 % → 12.5 % |
| Carmaphycin-R9-2 | 15 | 15/15 → 15/15 | 15/15 → 15/15 | 25.4 % → **25.9 %** / 32.6 % → **30.6 %** |
| Doxorubicin16-R2b | 23 | 22/23 → 21/23 | 22/23 → 21/23 | 18.3 % → **19.8 %** / 19.1 % → **20.4 %** |

What trimming moved (measured, `snv_indel_concordance.csv` v2 vs v3): total HaplotypeCaller calls per
evolved sample fell by 2–12 (343→331, 267→265, 306→296) and evolved-unique calls by 1–9 (120→111,
44→42, 59→58) with no truth event lost, so precision rose slightly. The joint VCF has 451 records
(391 PASS; 49 `MQ_filter`, 5 `SOR_FS_filter`, 2 `QD_filter`, the rest combinations).

**SV matrix shrank 426 → 385 rows** (`sv_cohort_matrix.csv`; TRA 178→152, INV 168→154, DUP 42→39,
DEL 36→39, INS 2→1). The pilot truth set carries no SVs, so this is not scored; the direction matches
the audit's finding that adapter read-through manufactures breakpoint evidence
(`docs/dev-practices/fastq_preprocessing_audit.md` §1.3) — **inferred**, not verified at read level
here. Per-sample SV counts: `sv_characterization.csv`.

## Provenance note

Every number in v2 was measured on untrimmed reads with the hard filter on; every number here on the
current recipe. Cite v3 for the pipeline as shipped; v2 remains the record of the earlier recipe. The
cloud reference baseline was re-cut on the same recipe the day before (`2W0uOsPYt03NAL`,
`deploy/azure/seqera-sp/RUNBOOK.md`).
