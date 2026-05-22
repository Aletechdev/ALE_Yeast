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
- For Ottilie (diploid S288C, ploidy=2): baseline cn=2 correctly hidden, DELs/DUPs emitted as expected

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
1. Enhance `cnv_concordance.py` (CNVKit-only, dynamic mapping)
2. Create `sv_characterization.py`
3. Create `validate_all.py`
4. Run on pilot (`output_ottilie`) — verify all 3 sections
5. Run on Tier 2 (`output_ottilie_tier2`) — full 86-sample validation

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
