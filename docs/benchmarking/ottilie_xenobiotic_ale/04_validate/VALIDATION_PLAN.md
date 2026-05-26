# Comprehensive Validation Script for Ottilie Benchmark

## Context
We have SNV/INDEL concordance (98.8% on Tier 2) validated, but no systematic review across all variant callers. The goal is a single script that runs all validations, produces a unified report, and works on both `output_ottilie` (4 pilot samples) and `output_ottilie_tier2` (86 samples).

## What exists
| Script | Covers | Status |
|--------|--------|--------|
| `snv_indel_concordance.py` | HaplotypeCaller vs Sup Data 4 | Production-ready |
| `cnv_concordance.py` | CNVKit + Control-FREEC vs Sup Data 5 | Pilot-only (hardcoded `PILOT_CNV_SAMPLES`) |

## Scope decisions
- **Control-FREEC**: Skip — did not complete all samples in Tier 2
- **CNV truth set**: Only 1 sample in pilot (CBR110-15-R3a), 2 in Tier 2 (Diethylstilbestrol--15A, BMS983970-2R1e) — report truth concordance + characterization for all samples
- **SV**: No truth set — characterization only (SURVIVOR merge Manta+TIDDIT), lower priority

## Implementation plan

### Step 1: Enhance `cnv_concordance.py` (CNVKit-only)
**File**: `docs/benchmarking/ottilie_xenobiotic_ale/04_validate/cnv_concordance.py`

Changes:
- Remove Control-FREEC code (`load_controlfreec_ratios`, elevated chromosome reporting)
- Add `--dictionary` arg (reuse `sample_name_dictionary.csv`)
- Build dynamic `sup5_map` from dictionary + available cnvkit dirs (same pattern as `build_sup4_map` in snv_indel_concordance.py, using `clone_name_sup5` column)
- Add `--csv` output for machine-readable results
- `--all-samples` characterizes all non-truth-set samples too (report non-diploid segments)

**CNVKit diploid-scale caveat** (from `docs/variant-calling/cnvkit/cnvkit_ploidy_cn_scale.md`):
- CNVKit always reports cn=2 as baseline regardless of `--ploidy` flag
- Default thresholds: log2 ≤ -1.1 → cn=0, ≤ -0.25 → cn=1, ≤ 0.2 → cn=2 (baseline), ≤ 0.7 → cn=3
- For haploid samples: cn=2 = normal, cn=3 = gain, cn=1 = loss
- Script must: (a) note this in the report header, (b) use `absolute_cn = cn - 2 + ploidy` when reporting, (c) detect gains as cn > 2 (not cn > ploidy)

**CNVKit VCF export format asymmetry** (investigated 2026-05-21):
- `cnvkit.py export vcf --ploidy N` only emits records where `cn != ploidy`
- **DUP records** (cn > ploidy): FORMAT = `GT:GQ:CN:CNQ` — CN field present
- **DEL records** (cn < ploidy): FORMAT = `GT:GQ` — **no CN field**, must infer: `1/1` → cn=0, `0/1` → cn=ploidy-1
- Segments where cn == ploidy are **silently dropped** from VCF

  Ploidy-dependent behavior (verified on CENPK data):
  | Ploidy | cn=0 | cn=1 | cn=2 (baseline) | cn=3+ |
  |--------|------|------|------------------|-------|
  | 1 | DEL (GT:GQ) | **hidden** (==ploidy) | DUP (GT:GQ:CN:CNQ) — false DUP | DUP |
  | 2 | DEL | DEL (GT:GQ) | **hidden** (==ploidy) | DUP (GT:GQ:CN:CNQ) |

- **Recommendation**: Use `.call.cns` as primary data source — has explicit CN for all segments regardless of ploidy, no format asymmetry

**✅ RESOLVED: CNVKit `--ploidy` pipeline configuration** (2026-05-22):

Ploidy experiment (`04_validate/cnvkit_ploidy_experiment/`) confirmed that `.call.cns` CN values are ploidy-independent (cn=3 for chr I duplication across ploidy=1,2,3), but VCF output is drastically affected:

| Ploidy | VCF behavior (Ottilie haploid samples) |
|--------|----------------------------------------|
| 1 (was production) | 18–22 **false DUPs** per sample — every baseline cn=2 segment emitted as DUP |
| **2 (new production)** | **Only real CNVs** — baseline cn=2 hidden, gains/losses correctly reported |
| 3 | 16–19 **false DELs** per sample — baseline cn=2 < ploidy=3 |

**Decision**: Change `--ploidy` to 2 in `conf/modules/cnvkit.config` for `CNVKIT_CALL` and `CNVKIT_EXPORT`. This reverts to the original nf-core/sarek default (the pipeline originally did not accept ploidy as a parameter — ploidy support was added later for ALE). Since CNVKit's internal CN scale is always diploid, passing `--ploidy 2` aligns the VCF export with the CN scale and produces clean output. The `.call.cns` is unaffected by this change.

**Note**: This means the VCF "lies" about biological ploidy for haploid samples, but the CN values are correct on the diploid scale. For biological interpretation, use continuous CN from `.cnr` bin-level data: `absolute_cn = ploidy × 2^log2` (preferred — preserves subclonal/mosaic signals), or integer CN from `.call.cns`: `absolute_cn = cn - 2 + ploidy` (loses fractional signal). See `docs/variant-calling/cnvkit/cnvkit_cn_calculation.md` for full derivation and `04_validate/cnvkit_ploidy_experiment/ploidy_comparison.md` for experiment results.

### Step 2: Create `sv_characterization.py`
**File**: `docs/benchmarking/ottilie_xenobiotic_ale/04_validate/sv_characterization.py`

Functions (reuse patterns from `docs/benchmarking/marko_sv/sv_comparison/generate_dashboard.py`):
- `run_survivor_merge(manta_vcf, tiddit_vcf, workdir)` — SURVIVOR merge union (min_callers=1) + consensus (min_callers=2), max_dist=1000
- `parse_survivor_vcf(vcf_path)` — extract SVTYPE, SVLEN, SUPP_VEC
- `characterize_sample(sample, output_dir)` — per-sample SV summary
- `subtract_parent(evolved_svs, parent_svs, max_dist=1000)` — flag shared SVs
- Output CSV: `sample, manta_total, manta_pass, tiddit_total, tiddit_pass, consensus_count, evolved_unique_consensus, sv_types`

### Step 3: Create `validate_all.py` orchestrator
**File**: `docs/benchmarking/ottilie_xenobiotic_ale/04_validate/validate_all.py`

- Imports/calls SNV/INDEL concordance, CNV concordance, SV characterization
- Single `--output-dir` flag to switch between pilot and tier2
- Writes unified markdown report + CSVs to results directory
- Args: `--output-dir`, `--results-dir`, `--parent`

## Execution order
1. **Revert CNVKit `--ploidy` to 2** in `conf/modules/cnvkit.config`:
   - Change `--ploidy ${meta.ploidy}` → `--ploidy 2` in `CNVKIT_CALL` (line 38), germline override (line 47), and `CNVKIT_EXPORT` (line 57)
   - **Verified**: Dual `CNVKIT_CALL` config (generic line 28-43, germline override line 45-48) is **original nf-core/sarek 3.5.1 design** — diff against `.claude/worktrees/sarek-compare/nf-core-sarek_3.5.1/3_5_1/conf/modules/cnvkit.config` shows our only change was adding ploidy documentation comments (lines 30-37). The subworkflow (`bam_variant_calling_cnvkit/main.nf`) is identical to upstream.
   - **Known trade-off in sarek design**: `CNVKIT_BATCH` internally produces `.md.call.cns` (re-centered log2, has `p_ttest`, merged segments). Then `CNVKIT_CALL` re-calls from `.md.cns` (raw segmented) with `--filter ci` for germline, producing `.md.germline.call.cns` (CI-filtered, no re-centering, no `p_ttest`). The VCF is exported from `.germline.call.cns`. This is intentional — sarek likely prefers CI filtering for germline to reduce false positives (germline CNVs should be high-confidence, so segments with CI spanning zero are treated as noise).
   - **Impact**: Re-centering gap (~0.03 log2 shift) can flip CN calls at threshold boundaries (e.g., chr VI: log2=0.217→cn=3 in `.germline.call.cns` vs log2=0.187→cn=2 in `.call.cns`). High-CN overflow formula (`ceil(ploidy × 2^log2)`) also differs when `--ploidy` differs between the two calls (e.g., Carmaphycin chr XII: cn=13 in `.call.cns` vs cn=7 in `.germline.call.cns` with ploidy=1). After reverting to `--ploidy 2`, the overflow formula will match and only the re-centering difference remains.
   - **Full investigation**: See `docs/variant-calling/cnvkit/cnvkit_sarek_dual_call.md` for complete comparison with data from all 4 pilot samples.
   - **Note**: `cns[2]` in `CNVKIT_CALL` input (line 31 of subworkflow) is index-based selection from `CNVKIT_BATCH.out.cns` glob — picks `.cns` correctly (alphabetical: `.bintest.cns`[0], `.call.cns`[1], `.cns`[2]) but is fragile if file naming changes
2. **Build dual CN matrices** — generate two segment-level matrices from both `.md.call.cns` and `.md.germline.call.cns` to empirically compare:
   - **Sensitive matrix** (from `.md.call.cns`): Re-centered log2, includes `p_ttest` for user-controlled quality filtering, retains all segments. Better for mixed-population ALE where subclonal/mosaic signals are weak.
   - **Stringent matrix** (from `.md.germline.call.cns`): CI-filtered, no re-centering (cleaner calls, fewer false positives, matches VCF output). Better for clonal ALE samples with strong, unambiguous signal.
   - **Columns per sample**: log2, cn (integer from file), absolute_cn (`ploidy × 2^log2` continuous), p_ttest (sensitive matrix only)
   - **Compare**: Where do the two matrices agree/disagree? Check disagreements against known CNVs. Determine if one mode fits all ALE use cases or if clonal vs mixed-population samples need different modes.
   - **Additionally**: Build `.cnr` bin-level matrix (`ploidy × 2^log2`) for continuous CN heatmaps/clustering.
   - See `docs/variant-calling/cnvkit/cnvkit_cn_calculation.md` and `docs/variant-calling/cnvkit/cnvkit_sarek_dual_call.md` for details.
3. Enhance `cnv_concordance.py` (CNVKit-only, dynamic mapping)
4. Create `sv_characterization.py`
5. Create `validate_all.py`
6. Run on pilot (`output_ottilie`) — verify all 3 sections
7. Run on Tier 2 (`output_ottilie_tier2`) — full 86-sample validation

## Verification
```bash
source ~/miniforge3/etc/profile.d/conda.sh && conda activate nf-env

# Pilot (4 samples)
python docs/benchmarking/ottilie_xenobiotic_ale/04_validate/validate_all.py \
    --output-dir output_ottilie \
    --results-dir docs/benchmarking/ottilie_xenobiotic_ale/04_validate/pilot_results

# Tier 2 (86 samples)
python docs/benchmarking/ottilie_xenobiotic_ale/04_validate/validate_all.py \
    --output-dir output_ottilie_tier2 \
    --results-dir docs/benchmarking/ottilie_xenobiotic_ale/04_validate/tier2_results
```

Expected outputs per run:
- `snv_indel_concordance.csv`
- `cnv_concordance.csv`
- `sv_characterization.csv`
- `VALIDATION_REPORT.md` (unified)

## Dependencies
- `bcftools`, `samtools`, `SURVIVOR` 1.0.7 — all in nf-env (`conda activate nf-env`)
- Python: `openpyxl` (in nf-env)
- Existing: `sample_name_dictionary.csv`, Sup Data 4 + 5 xlsx files
