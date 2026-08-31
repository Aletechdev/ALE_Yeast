# Git history rewrite — 2026-08-31

The repository history was rewritten with `git filter-repo` on 2026-08-31, immediately before
open-sourcing, to remove private experiment data that had been committed during development.
**Every commit SHA changed** (old tip `d071489` → new tip `d568377`). Any SHA recorded before
this date — in old issues, run logs, notes, or the Azure-baseline `versions.yml` provenance
line (`v1.0.0-g86c4672`) — refers to the *pre-rewrite* history.

## Translating old SHAs

The full old→new map (one line per commit, `<old-full-sha> <new-full-sha>`) is committed
alongside this file: [`history_rewrite_2026-08_commit_map.txt`](history_rewrite_2026-08_commit_map.txt).
Abbreviated old SHAs can be resolved by prefix-matching the first column. Commits absent from
the map were either unreachable from `main` before the rewrite or pruned because they touched
only purged paths.

All SHA references in the docs at the rewrite tip were translated to the new history in the
same change that added this file, with one deliberate exception: `86c4672` is what the verified
Azure Batch baseline **printed** into its `versions.yml`, so those quotations keep the old SHA
verbatim (its post-rewrite equivalent is `ecd1e5b`).

## What was purged

Paths removed from **all** of history (`--invert-paths`):

| Path | Reason |
|------|--------|
| `assets/reads/` | Subsampled FASTQs + samplesheets of the private CEN.PK / dicarboxylic-acids dataset |
| `assets/references/`, `assets/genebank/` | `draft_ref52` reference, SnpEff caches, Ogataea GenBank — private-era references, unused by current runs |
| `data/dicarboxylic_acids/`, `data/data_a_paper/` | Private dataset files incl. third-party ScienceDirect PDFs |
| `docs/igvreports/demo/`, `docs/igvreports/output_no_tracks/` | igv-reports HTML with private-sample variant calls (deleted from HEAD 2026-07-27, still in history) |
| `docs/prepare_input/sarek_csv_to_XPMD/Dicarboxylic_acids_XPMD.csv`, `.../dipic_acid_sarek_samplesheet.csv` | Private sample manifests |
| `docs/compare_single_pop_HpCaller/samplesheet.csv`, `.../samplesheet_onesample.csv` | Private sample manifests |
| `docs/prepare_input/process_XPMD/test/Yeast_Methanol_XPMD_final_fixed.csv` | Real sample rows from the archived methanol project |

Text scrub (`--replace-text`): the customer identifier `iLoop_Chalmers_yunc-…` was replaced with
`REDACTED-CUSTOMER-ID` in every blob of every commit.

Legacy scripts that *referenced* the purged files were deliberately kept ("minimal purge") —
they now contain dangling paths and are retained as documentation of the old workflows.

## Consequences to remember

- Runs launched from a Git clone stamp the **new** short commit into `versions.yml`
  (`v1.0.0-g<new sha>`); the verified Azure baseline says `v1.0.0-g86c4672`. This is a
  known-expected difference, not a regression.
- Pre-rewrite clones must be re-cloned, not pulled; the pre-rewrite history survives only in
  offline copies.
