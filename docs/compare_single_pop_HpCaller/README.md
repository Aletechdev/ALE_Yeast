# Single-sample vs joint HaplotypeCaller comparison

Quick check of how HaplotypeCaller behaves for germline calling when the cohort
has different sample counts, and whether joint calling still runs with a single sample.

## Scripts

| Script | Samplesheet | Scenario |
|--------|-------------|----------|
| `run_individual.sh` | `samplesheet.csv` | Per-sample individual HaplotypeCaller |
| `run_joint.sh` | `samplesheet.csv` | Joint germline calling, multi-sample cohort |
| `run_joint_onesample.sh` | `samplesheet_onesample.csv` | Joint germline calling with a **single** sample |

All use `-c ../../bin/nextflow.config` (the `azureD4as` local profile).

## Finding

**Joint calling mode (`--joint_germline`) still runs with a single sample** — it does
not require ≥2 samples. The single-sample run completes through GenomicsDBImport →
GenotypeGVCFs → the VariantFiltration soft-filter fallback, producing the same
`HaplotypeCaller_joint_calling_soft_filtered.vcf.gz` output as a multi-sample cohort.

Practical implication: experiments with one evolved clone (no replicates) can still
use the joint-germline pathway; no special single-sample handling is needed.

## Note

The full run outputs (`output_inde/`, `.nextflow.log*`, work dirs — ~47 GB) were kept
transiently under `bin/compare_single_pop_HpCaller/` and removed during v1.0.0 cleanup.
Re-run the scripts above to regenerate if needed.
