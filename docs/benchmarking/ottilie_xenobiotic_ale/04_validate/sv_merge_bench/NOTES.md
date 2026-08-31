# SVDB vs Jasmine on joint Manta + per-sample TIDDIT — bench 2026-08-28

> **Repo copy (2026-08-31).** Scripts + final merged VCFs only (`<dataset>/cohort_{union,pass}_inv.vcf`
> = the recommended SVDB recipe; `cohort_1kb_normtype_nostrand.vcf` = Jasmine's best config, kept for the
> comparison record). Inputs and intermediates were left in the session scratchpad (ephemeral): inputs
> regenerate from `output_ottilie_pilot_2026-08-26/variant_calling/tiddit/`, the joint-Manta audit VCF in
> `../pilot_results_v2/manta_joint_audit/default/`, and the nf-test e2e output — provenance below. Rerun
> ≈1 min via `run.sh` + the second-pass commands described in the findings.


Inputs: `test2/in/` = joint Manta (nf-test run 4c5e2458…, columns CBR110,NODRUG) + TIDDIT per sample
(44/23 rec); `pilot4/in/` = joint Manta from `manta_joint_audit/default/` (**columns reordered to
alphabetical with `bcftools view -s`** — the audit VCF predates the groupTuple sort fix) + pilot TIDDIT
(170/378/116/170). Images: svdb 2.8.2 mulled (`quay.io/biocontainers/mulled-v2-375a75…`), jasminesv
1.1.5, manta 1.6.0 (for `convertInversion.py`; `bin/samtools` is a faidx shim because the manta image
has no samtools). `run.sh` = first pass; second pass commands are in the shell history / below.

## Row counts

| output | test2 | pilot4 |
|---|---|---|
| SVDB raw inputs, union (`--no_intra --same_order --priority manta,tiddit`) | 62 | 604 |
| SVDB raw inputs, `--pass_only` (NOT a PASS view — see F2) | 70 | 623 |
| SVDB, breakend pairs collapsed in every input, union | 41 | 371 |
| SVDB, collapsed, PASS view (inputs pre-filtered `.,PASS`) | 23 | 103 |
| SVDB, `convertInversion` + collapsed, union / PASS | 41 / 23 | 370 / 103 |
| Jasmine default | 70 | 656 |
| Jasmine `max_dist=1000 --nonlinear_dist --normalize_type --ignore_strand` | 62 | 618 |

ADH1-star rows (XV:159.4–159.9 kb touched): raw union 15 / 33 → collapsed 8 / 18 → PASS 8 / 10.

## Findings

F1. **XV:722 kb DEL** = one record `DEL PASS set=Intersection FOUNDBY=2`, Manta coords (722249),
    `tiddit_POS=722257`, both samples 1/1, in every SVDB configuration. (SURVIVOR: swallowed into INV.)
F2. **`--pass_only` means "only PASS records may merge"; non-PASS records are still emitted** (70 > 62).
    raredisease gets its PASS view by `bcftools view --apply-filters .,PASS` on the INPUTS. Do the same.
F3. **SVDB treats a breakend as an unordered (chrA:posA, chrB:posB) pair and `--no_intra` only stops a
    cluster being SEEDED from one file, not JOINED by it.** Raw inputs → one Manta mate absorbs both
    TIDDIT mates (ID `…:manta|SV_6_1:CBR|SV_3_1:NODRUG|SV_3_2:NODRUG:tiddit|SV_6_2:tiddit`) and its own
    mate stays `set=manta` → asymmetric provenance between mates. **Fix: collapse pairs in every input
    before any merge** (`collapse_pairs.py`: Manta drop record whose MATEID already emitted; TIDDIT drop
    `SV_<n>_2`). Then one row per junction, provenance consistent, nothing lost (mate carries same GT/PR/SR).
F4. **MATEID survives** both levels (14/14, 22/22 raw). After collapsing only the kept mate has it (7/11);
    it is informational only from then on.
F5. **Manta `convertInversion.py`** (ships in the Manta image; nf-core has `manta/convertinversion`)
    turns INV3/INV5 mate pairs into `<INV>` records (test2 3, pilot 2) which THEN merge with TIDDIT's
    `<INV>` (pilot XV:159663–619773 ↔ TIDDIT XV:159561–619843, `manta-filterIntiddit`). Inter-chromosomal
    pairs stay BND on both sides and merge as BND. Do this before the collapse.
F6. **`--same_order` never checks column names.** Misaligned input (pilot arrival-order Manta) → exit 0,
    empty stderr, header from file 1, genotypes placed by POSITION → mislabelled. Assert column order
    (`bcftools query -l`) in the process, or `bcftools view -s <sorted>` both inputs first.
F7. **FORMAT is kept verbatim from the priority record** (`GT:FT:GQ:PL:PR:SR`), the other caller's
    per-sample strings land in INFO (`<sample>.tiddit_SAMPLE=…|GT:1/1|CN:0|…` propagate from L1 to L2 as
    top-level keys; `tiddit_SAMPLE` itself is just the ID for a multi-sample input). Matrix cells:
    Manta = FORMAT GT (+FT for PASS view) when `svdb_origin` contains manta; TIDDIT = `<sample>.tiddit_*`
    keys, or FORMAT when the record is tiddit-only. L1 tags are FILENAME-derived (`CBR110-15-R3a.tiddit.c`)
    — pass explicit `file:tag` at L1 so tags are sample ids.
F8. `--overlap` 0.95 (default) vs 0.8 vs 0.6 on the pilot: 371 → 368 → 368 rows, **no Manta record
    changes provenance**. `--bnd_distance` default 2000 (SURVIVOR used 1000) — set explicitly, keep 2000
    unless the pilot shows cross-junction merging (none seen at the star after collapsing).
F9. **Jasmine**: handles multi-sample input by emitting one column per input×sample
    (`0_CBR 0_NODRUG 1_CBR 2_NODRUG`), SUPP_VEC per FILE (Manta,TIDDIT-s1,TIDDIT-s2…) — a nice matrix
    shape — and with `--ignore_strand` matches both mates symmetrically. But: FORMAT reduced to
    `GT:IS:OT:DV:DR` (**FT lost**, PR/SR lost), `DUP:TANDEM` → empty SVTYPE under `--normalize_type`,
    `--ignore_type` → SVTYPE `???`, IDs rewritten (`0_MantaBND…`, `_duplicate1`) so MATEID dangles, no
    priority/pass handling, no tag-based provenance. Not adopted.

F10. **Cross-type equivalence classes checked 2026-08-31 — no per-type benchmark needed.**
    (a) `DUP` vs `DUP:TANDEM` label mismatch: SVDB normalizes — synthetic identical-coordinate pair
    merges as `set=Intersection`; real pilot case XIII:908138 (Manta SVTYPE=DUP, MaxDepth) merged with
    TIDDIT DUP:TANDEM from two samples. Non-issue.
    (b) Manta `INS` vs TIDDIT `DUP:TANDEM` (small tandem dup called INS): does not arise in this data —
    the only PASS Manta INS (VII:530034, 84 bp) has no TIDDIT DUP anywhere near it (only junk BNDs),
    and Manta itself types larger tandem dups DUP:TANDEM. Revisit only if a caller with a different
    INS/DUP convention (e.g. Delly) joins; Jasmine-style dup-to-ins normalization would be the lever.
    (c) General cross-type merging (`--no_var`) was already run (identical output on test2) and is the
    swallowing mechanism the redesign removes — deliberately NOT wanted.

## Recommended recipe (pipeline)

```
joint Manta VCF ──convertInversion──▶ collapse pairs ─┐
TIDDIT per sample ──collapse pairs──▶ svdb --merge --no_intra --vcf s1.vcf:s1 s2.vcf:s2 … --priority s1,s2,…  (L1)
                                                      └──▶ svdb --merge --no_intra --same_order --bnd_distance 2000 --priority manta,tiddit --vcf manta.vcf:manta tiddit_cohort.vcf:tiddit  (L2)
PASS view = same chain on `bcftools view --apply-filters .,PASS` inputs (not --pass_only).
Assert: bcftools query -l on both L2 inputs are identical.
```
