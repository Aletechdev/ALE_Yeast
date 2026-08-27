# CNVKit: Small Chromosome Exclusion in WGS Mode

## Summary

CNVKit may silently exclude chromosomes shorter than ~150kb from copy number results when running in WGS mode. This is expected behavior due to a hardcoded telomeric skip heuristic in antitarget bin generation.

## Why Small Chromosomes Are Excluded

In WGS mode without an explicit access file (`-g`), `cnvkit.py batch` skips the first ~150,000 bp of each chromosome (assumed telomeric). Chromosomes entirely below this threshold receive **zero antitarget bins** and are dropped from the final output.

### What happens step by step

1. **Target bins**: Coverage bins are generated for all chromosomes (present in `.targetcoverage.cnn`)
2. **Antitarget bins**: Chromosomes below the 150kb telomeric skip get no antitarget bins (absent from `.antitargetcoverage.cnn`)
3. **Reference**: These chromosomes end up with zero spread in `reference.cnn`
4. **Fix step**: `cnvkit.py fix` drops bins with zero spread (can't normalize) → absent from `.cnr` and `.cns`

### Additional regex-based exclusion

CNVKit also excludes chromosomes matching non-canonical name patterns, including `chrM` and `MT` (mitochondrial). This is separate from the size-based exclusion above. Note that non-standard names like `Mito` do not match these patterns.

## Example: Yeast S288C (Ottilie pipeline)

> **Correction (2026-08-27).** For our WGS + flat-reference runs the Mito exclusion is **not**
> caused by this mechanism: the antitarget files are empty for *every* contig in WGS mode and
> `reference.cnn` has `spread = 0` for every bin, yet only the Mito bins are dropped. The verified
> cause is the hard-coded **GC mask** in `cnvkit.py fix` (bins outside 0.30–0.70 GC; yeast mtDNA is
> ~17 % GC) — see [`cnvkit_gc_bin_mask.md`](cnvkit_gc_bin_mask.md). The outcome described below
> (Mito absent from `.cnr`/`.cns`) is real; the attribution to the 150 kb threshold is superseded
> for this pipeline. Nuclear chromosomes (chr I at 230 kb the smallest) are unaffected either way.

```
# Mito present in target coverage (coverage calculated)
$ grep Mito CBR110-15-R3a.md.targetcoverage.cnn | head -2
Mito    0       5045    -       80.0172 6.32224
Mito    5045    10091   -       155.168 7.27768

# Mito absent from antitarget coverage
$ grep Mito CBR110-15-R3a.md.antitargetcoverage.cnn
(no output)

# Mito in reference with zero spread
$ grep Mito reference.cnn | head -2
Mito    0       5045    -       0       1       0.155203        0       0
Mito    5045    10091   -       0       1       0.152002        0       0

# Mito absent from final output
$ cut -f1 CBR110-15-R3a.md.cnr | sort -u | grep Mito
(no output)
```

## Workaround

To include small chromosomes, provide an explicit access file:

```bash
cnvkit.py access reference.fa -o access.bed
# Verify the chromosome is in access.bed, then pass to batch:
cnvkit.py batch ... -g access.bed
```

This bypasses the internal 150kb heuristic.

## Reference

- CNVKit antitarget source: https://cnvkit.readthedocs.io/en/stable/_modules/cnvlib/antitarget.html
