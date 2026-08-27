# SV Merge Chain (SURVIVOR) — Maintainer Reference

Mechanics of how per-sample Manta + TIDDIT structural-variant calls are merged into
the cohort SV matrix. This is the **maintainer** view (parameters, `SUPP_VEC`,
`proximity_match`, CSV schema, gotchas).

> **Keep in sync** with the user-facing "SV event matrix (Manta + TIDDIT)" section of
> the report Methodology in `docs/igvreports/templates/index.html.j2` (~L547-620).
> That section explains *how to read* the matrix; this doc explains *how it is built*.
> The two are intentionally separate sources today — a single shared Jinja include is
> deferred (see `docs/dev-practices/roadmap.md`). If you change the merge parameters,
> `SUPP_VEC` convention, or CSV columns here, update the report Methodology too.

## The chain

```
SURVIVOR_SV_MERGE      (per-sample: Manta + TIDDIT → 2-char SUPP_VEC)
   → BGZIPTABIX_SV_*         (publish data/sv_merged/<sample>/<sample>.survivor.<mode>.vcf.gz)
   → SURVIVOR_COHORT_MERGE   (cross-sample: N samples → N-char SUPP_VEC)
   → BGZIPTABIX_SV_COHORT_*  (publish data/sv_cohort_merged_<mode>.vcf.gz — the joint SV VCF)
   → BUILD_SV_MATRIX         (parse + proximity_match → sv_cohort_matrix_{union,union_pass}.csv)
```

Wired in `subworkflows/local/mutation_report/main.nf` (the SV section, ~L191-262). Two
**fully parallel** paths run this chain end to end:

| Mode | Per-sample input | Meaning |
|------|------------------|---------|
| `union_pass` | Manta + TIDDIT after `bcftools view -f PASS` | union of PASS-only calls |
| `union` | Manta + TIDDIT decompressed, **no** filter | union of all raw calls |

Files:
- `modules/local/survivor_sv_merge/main.nf` — `SURVIVOR_SV_MERGE`
- `modules/local/survivor_cohort_merge/main.nf` — `SURVIVOR_COHORT_MERGE`
- `modules/nf-core/tabix/bgziptabix` — aliased `BGZIPTABIX_SV_{PASS,UNION}` (per-sample) and
  `BGZIPTABIX_SV_COHORT_{PASS,UNION}` (cohort); the only publish points of the chain
- `bin/sv_cohort_matrix.py` — `BUILD_SV_MATRIX` (the parser + matrix builder)
- `conf/modules/mutation_report.config` — process config (`ext.min_callers`, prefixes, publishDir)

Published outputs (all under `<outdir>/mutation_reports/data/`):

| File | Producer | Content |
|------|----------|---------|
| `sv_merged/<sample>/<sample>.survivor.{union,union_pass}.vcf.gz` (+ `.tbi`) | `BGZIPTABIX_SV_*` | per-sample Manta ∪ TIDDIT |
| `sv_cohort_merged_{union,union_pass}.vcf.gz` (+ `.tbi`) | `BGZIPTABIX_SV_COHORT_*` | cohort VCF — one record per event, one GT column per sample (SURVIVOR names the columns after the first sample column of each input, e.g. `Ottilie_test_CBR110-15-R3a`) |
| `sv_cohort_matrix_{union,union_pass}.csv` | `BUILD_SV_MATRIX` | the matrix (below) |
| `<sample>.{manta,tiddit}.pass_stats.tsv` | `FILTER_PASS_VCF` (not part of the merge) | `total` / `pass` record counts → Sample Overview "PASS / all" |

The cohort VCF filename is **load-bearing**: `generate_index.py` (`load_cnv_sv_data`) probes
`data/sv_cohort_merged_union_pass.vcf.gz` to decide whether to render the "VCF" download button
beside the ensemble SV table. Rename it in `mutation_report.config` and in `generate_index.py` together.

## SURVIVOR CLI parameters

Both merge steps invoke the same positional SURVIVOR call:

```
SURVIVOR merge <filelist> 1000 <min_support> 1 0 0 50 <out>
```

| Position | Value | Meaning |
|----------|-------|---------|
| max_dist | `1000` | breakpoints within 1000 bp are the same event |
| min_support | `1` | minimum callers/samples supporting an event |
| take_type | `1` | require same SVTYPE to merge |
| take_strand | `0` | strand not required to match |
| estimate_dist | `0` | do not estimate distance |
| min_size | `50` | ignore SVs < 50 bp |

**`min_support = 1` in BOTH steps.** Per-sample it comes from `ext.min_callers = 1`
(`conf/modules/mutation_report.config:43`); cohort uses the literal `1`
(`survivor_cohort_merge/main.nf:28`). Consequences:

- ⚠️ **`union_pass` is a UNION, not a caller-intersection.** There is **no** 2-of-2
  Manta∩TIDDIT consensus anywhere in the chain. The `_pass` suffix only means the
  *inputs* were `bcftools view -f PASS` filtered — not that an event passed in both callers.
- The cohort merge with min_support 1 keeps every event present in ≥1 sample.

## Post-merge sort (no input-sort guard)

Both modules sort **after** SURVIVOR, on `merged_raw.vcf`:

```bash
grep '^#' merged_raw.vcf > header.vcf
grep -v '^#' merged_raw.vcf | sort -k1,1d -k2,2n > body.vcf
cat header.vcf body.vcf > <out>.vcf
```

(POSIX `sort`, deliberately avoiding the GNU `-V` flag for container portability.)

⚠️ **There is no guard that the *input* VCFs are coordinate-sorted.** SURVIVOR assumes
sorted input, which holds here because Manta/TIDDIT + `bcftools view` emit sorted VCFs.
This is a latent robustness gap: an unsorted input would not be caught.

## SUPP_VEC — support vector

SURVIVOR writes an `INFO/SUPP_VEC` bit-string, one character per input VCF, in the order
the VCFs appear in `filelist.txt`.

- **Per-sample VCF (`SURVIVOR_SV_MERGE`): 2-char.** The filelist is written in fixed order
  (`survivor_sv_merge/main.nf:26-27`): `echo "${manta_vcf}"` then `echo "${tiddit_vcf}"`.
  So **position 0 = Manta, position 1 = TIDDIT**.
- **Cohort VCF (`SURVIVOR_COHORT_MERGE`): N-char**, one position per sample. Order follows
  `ls *.vcf` (`survivor_cohort_merge/main.nf:25`).

⚠️ The Manta/TIDDIT labels are **hardcoded to match the filelist echo order** — the parser
(`sv_cohort_matrix.py:58-62`) decodes `supp_vec[0]→Manta`, `supp_vec[1]→TIDDIT`. If the
`echo` order in the module ever changes, the parser labels silently invert. Keep them coupled.

## Which coordinates the merged record keeps — last file in the list wins

When SURVIVOR collapses several calls into one record, the record's `POS`/`END`/`ID` (and so
the `pos`/`end` in the CSV) are copied from **one** member of the cluster: the call from the
**last input file in `filelist.txt`** that supports the event. It is *not* the larger position,
the higher QUAL, or a consensus. Verified 2026-08-26 on the ottilie 2-sample outputs — of the 32
shared cohort events whose two samples disagreed on coordinates, all 32 took the second file's
(NODRUG-GM2's) values, 12 of them the *smaller* position. The other members' offsets survive only
as `CIPOS`/`CIEND` and in each column's `FORMAT/CO`.

| Merge step | File-list order | Whose coordinates end up in the record |
|------------|-----------------|----------------------------------------|
| Per sample (Manta ∪ TIDDIT) | Manta, then TIDDIT (fixed `echo` order) | **TIDDIT's** whenever TIDDIT called the event; Manta's only when TIDDIT did not |
| Cohort (samples) | `ls *.vcf` → alphabetical by sample id | the **alphabetically last sample** carrying the event |

Consequences:

- Matrix rows for shared events show the last sample's breakpoints, never the first sample's own
  call, even when the first sample's call is the better-supported one (e.g. the XV:722257 DEL row
  carries TIDDIT's `722257-722440`, not Manta's split-read `722249-722439`).
- The choice **depends on sample naming**: rename a sample so it sorts differently and shared-row
  coordinates shift by a few bp although the events are unchanged. Byte-comparisons of
  `sv_cohort_matrix_*.csv` across runs are only meaningful with identical sample ids.
- With >2 inputs the expectation is "last supporting file"; verified here for two inputs only.

## BUILD_SV_MATRIX — how cells are populated

`sv_cohort_matrix.py` parses the cohort VCF and each per-sample VCF using
**only** `INFO/SVTYPE, SVLEN, END, CHR2, SUPP_VEC`. It **ignores** the VCF `ID` column and
all FORMAT subfields (`GT`, `CO`, `QV`) — so there is no per-caller breakpoint or genotype
propagation into the matrix.

For every cohort event, each sample's cell is resolved by an **independent
`proximity_match`** against that sample's own per-sample VCF (not by decoding the cohort
`SUPP_VEC`). The gate (`sv_cohort_matrix.py:85-104`):

```
same chrom  AND  same svtype  AND  same chrom2  AND  |Δpos| ≤ 1000  AND  |Δend| ≤ 1000
```

Best match = smallest `|Δpos| + |Δend|`. The cell then shows that per-sample record's
callers, decoded from **its** 2-char `SUPP_VEC`: `Manta`, `TIDDIT`, `Manta+TIDDIT`, or `-`
if no per-sample event matches.

⚠️ **The cohort `SUPP_VEC` and the per-sample `proximity_match` can disagree.** The cohort
`SUPP_VEC` feeds **only** the printed `n_shared` / `n_private` summary counts
(`sv_cohort_matrix.py:173-176`); it does not drive the matrix cells. The matrix cells come
from the independent per-sample proximity matches.

**Both breakpoints must agree** (`|Δpos| ≤ 1000` **and** `|Δend| ≤ 1000`) — the same rule
SURVIVOR applied when it created the cohort event, so the lookup can never be looser than the
merge it annotates. Until 2026-08-25 the gate was **OR** (one close breakpoint sufficed), which
cross-credited distinct events that share an anchor: on the ottilie 2-sample test set,
NODRUG-GM2's private ADH1↔AUS1 inversion (XV:159644–349748) was stamped `Manta` for
CBR110-15-R3a because that sample's *own* ADH1↔PDR5 inversion (XV:159651–619873) starts 7 bp
away — right ends 270 kb apart. In `union` mode the same bug also cross-credited TIDDIT
telomere↔telomere TRA calls between chr I and chr XV. Genuine matches agree within tens of bp
at both ends, so the AND gate loses nothing.

## CSV schema

`sv_cohort_matrix_{union,union_pass}.csv` — column order (`sv_cohort_matrix.py:153`):

```
chrom, pos, chrom2, end, svtype, svlen, <sample_1>, <sample_2>, ...
```

Note **`chrom2` sits before `end`**. Rows are sorted by yeast chromosome order
(`I`…`XVI`, `sv_cohort_matrix.py:28-29`), then `pos`, `end`, `svtype`. Each sample column
holds `Manta` / `TIDDIT` / `Manta+TIDDIT` / `-`.

## Known issue — revisit: cross-type swallowing in `union` mode (found 2026-08-26)

`take_type=1` does **not** stop SURVIVOR from folding a DEL into a breakend-derived INV/TRA
cluster. Observed on the ottilie 2-sample test set, `union` (raw) mode, chr XV ~722 kb:

```
NODRUG-GM2 raw TIDDIT:  722257-722440 <DEL>  QUAL 80  PASS                  ← real event
                        721969<->722440 BND  QUAL 15  BelowExpectedLinks     ← junk breakend pair
NODRUG-GM2 raw Manta:   722249-722439 DEL    QUAL 999 PASS

per-sample union record:  POS=721969  SVTYPE=INV  SUPP_VEC=11
     TIDDIT column: TY=INV,DEL,INV  CO=XV_721969-XV_722440,XV_722257-XV_722440,XV_722440-XV_721969
     (all three TIDDIT records + the Manta DEL collapsed into ONE record that took the breakend's identity)

cohort union record:      POS=721969  SVTYPE=INV  — CBR110-15-R3a's clean DEL (722257-722440,
     PASS in both callers, 112 split reads) was merged into it too, despite take_type=1.

sv_cohort_matrix_union.csv:  XV,721969,XV,722440,INV,259,-,Manta+TIDDIT
     CBR110-15-R3a shows "-" because proximity_match requires svtype equality (DEL != INV).
```

Net effect: in the `union` matrix a sample's PASS, two-caller deletion is invisible. `union_pass`
(the dashboard table) is unaffected *here* only because the breakend pair is non-PASS; the mechanism
is latent for `union_pass` whenever a PASS breakend sits within `max_dist` of a real event.

Nothing is lost **across the two VCF levels together**, but neither level alone holds everything:

- **Per-sample VCF** (where the clustering happened): the TIDDIT column keeps all three clustered
  records comma-joined in `TY=INV,DEL,INV`, `CO=…721969-722440,…722257-722440,…722440-721969`,
  `QV=15,80,15` — so NODRUG's deletion (`722257-722440`, QUAL 80) is recoverable here. Only `TY`,
  `CO`, `QV` are joined; `ID`, `LN`, `GT` carry the representative's value only (`ID=SV_1_2`).
- **Cohort VCF**: each sample column carries just that sample's *representative*. CBR110's column
  still says `TY=DEL CO=XV_722257-XV_722440 ID=SV_1_1` (its deletion identity survives), but
  NODRUG's column says `TY=INV CO=XV_721969-XV_722440` — NODRUG's deletion is **not** in the
  cohort VCF; you must drop to its per-sample VCF to see it.

So this is a matrix-derivation problem for CBR110 (the cohort VCF knows it is a DEL; the CSV
blanks it), and a representative-selection problem for NODRUG (its DEL is one level down).

Options on the table (decision deferred — see `docs/dev-practices/roadmap.md`):

1. **Decode cells from the cohort VCF's per-sample `PSV`** (`10`→Manta, `01`→TIDDIT, `11`→both,
   `./.`→`-`) instead of re-deriving them with `proximity_match`. Removes the proximity heuristic
   and its `max_dist` entirely, and makes the CSV agree with SURVIVOR's merge by construction; the
   swallowed sample would read `Manta+TIDDIT`. The sample's own `TY`/`CO` could go in a companion
   long-format CSV (one row per event × sample × caller) so a DEL-inside-an-INV-row is visible.
2. Drop non-PASS breakends before the raw `union` merge (or retire `union` mode).
3. Keep as is and treat `union` as an exploratory download only (current state).

Until this is revisited: **trust `union_pass` for counts; treat `union` cells as approximate.**

## Not part of this chain

`PREPARE_VCF` and `FILTER_PASS_VCF` serve the **igv-reports display VCFs**, not the SURVIVOR
merge. Do not place them in the merge path.

## Gotchas summary

- `union_pass` is a **union of PASS inputs**, not a 2-caller intersection.
- **No input-sort guard** — relies on Manta/TIDDIT + bcftools emitting sorted VCFs.
- Caller labels (`Manta`/`TIDDIT`) are coupled to the filelist **echo order** in
  `survivor_sv_merge/main.nf`, not read from the VCF.
- Cohort `SUPP_VEC` (summary counts) and per-sample `proximity_match` (matrix cells) are
  **independent** and can diverge.
- Proximity gate is **AND** on the two endpoints (since 2026-08-25; was OR — see above). Keep
  it at least as strict as SURVIVOR's own `max_dist` merge rule.
- `union` mode: a junk breakend pair within `max_dist` can absorb a real DEL and retype the
  cluster INV/TRA; the matrix then hides the DEL sample (svtype check). See "Known issue".
- Manta BND-type events (TRA, INV) are **breakend pairs** — two VCF records per junction, both
  kept by SURVIVOR — so one event is **two matrix rows** (`pos`/`end` swapped).
