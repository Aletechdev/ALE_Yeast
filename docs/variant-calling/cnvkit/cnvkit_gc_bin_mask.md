# CNVKit: the hard-coded GC bin mask (why Mito never appears)

**Verified 2026-08-27** by re-running `cnvkit.py fix` in the pipeline's container
(`quay.io/biocontainers/cnvkit:0.9.10--pyhdfd78af_0`) on the pilot's own coverage files.

## Summary

`cnvkit.py fix` silently drops every bin whose **reference GC fraction is outside 0.30–0.70**.
The bounds are constants in `cnvlib/params.py` (`GC_MIN_FRACTION = 0.3`, `GC_MAX_FRACTION = 0.7`,
commented "should not change between runs") and there is **no CLI override** — `--no-gc` skips the
GC *correction*, not this mask. Yeast mtDNA is ~17 % GC (our nuclear bins average 38 %), so **all
17 Mito bins are dropped in every sample, in every run**. From `.cnr` onward — segments, collapsed
CN windows, chromosome summaries, the CNV VCF, the IGV log2 track — the mitochondrial contig does
not exist for CNVKit. An empty `Mito` row in `cn_chr_summary_*.csv` means "never evaluated", not
"no change".

## The mechanism, traced

`cnvlib/fix.py::load_adjust_coverages` → `mask_bad_bins(ref_matched)` flags bins where

```python
(ref.log2 < -5) | (ref.log2 > 5) | (ref.spread > 1.0)
  | (ref.depth == 0)
  | (ref.gc > 0.7) | (ref.gc < 0.3)      # <-- the one that fires for Mito
```

Evidence from the pilot (4 samples, flat reference):

- `target.bed` / `targetcoverage.cnn`: 2,431 bins **including 17 Mito bins with real depths**
  (30–190×) — coverage *is* measured.
- `reference.cnn` (flat): `log2 = 0`, `depth = 1`, `spread = 0` for **every** bin, nuclear and
  Mito alike — so neither log2, depth, nor spread can discriminate. Mito bins carry
  `gc = 0.152–0.247`; nuclear bins ~0.34–0.38.
- Re-running `fix` verbatim prints `Keeping 2414 of 2431 bins` — exactly the 17 Mito bins gone;
  `--no-gc` / `--no-edge` / `--no-rmask` change nothing.
- Test set (4 nuclear chromosomes, no Mito in the reference): 788 of 788 bins kept — the mask
  drops nothing nuclear in S288C.

## Consequences

- **CNVKit cannot report mitochondrial copy number in this pipeline, ever.** The pilot's one
  unmatched truth event (Doxorubicin16-R2b's petite-type mtDNA loss, TIDDIT contig ploidy
  10.1 → 0.34) was invisible to every CNVKit view for this reason — see
  `docs/benchmarking/ottilie_xenobiotic_ale/04_validate/pilot_results_v2/NOTES.md`.
- The mask is not Mito-specific: any nuclear region below 30 % or above 70 % GC vanishes the same
  silent way. For S288C that is zero nuclear bins; for AT-rich genomes it could be substantial.
- **Where to read Mito instead**: the report's "Contig Copy Number — TIDDIT whole-contig coverage"
  table (`data/contig_copy_number.csv`, from `<sample>.tiddit.ploidies.tab`), added 2026-08-27.

## Relation to the 150 kb small-chromosome exclusion

`cnvkit_small_chr_exclusion.md` describes an antitarget-based exclusion and used Mito as its
example. In our WGS + flat-reference configuration that attribution does not hold: the antitarget
files are **empty for every contig** (WGS mode) and `spread = 0` everywhere, yet only Mito is
dropped — the GC mask is the operative mechanism. The 150 kb telomeric-skip behaviour may still
matter in other CNVKit configurations; that doc now points here for the Mito case.

## Workarounds (not adopted)

Patching `params.py` in a custom container, or post-processing `targetcoverage.cnn` directly.
Rejected: the TIDDIT contig table provides the number without forking CNVKit. Do not expect
`cnvkit.py` output for `Mito` in any configuration of this pipeline.
