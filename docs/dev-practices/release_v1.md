v0.1.0-alpha    ← already shipped (your existing tag)
v1.0.0          ← first production release

Now        → v1.0.0 on Sarek 3.5.1 (ship what works)
+2-3 weeks → v1.1.0 on Sarek 3.8.1 (upgrade + patch queue setup)
Ongoing    → v1.x.y follows the rebuild workflow for future upgrades

What to document for v1.0.0:

Samplesheet extensions — you've adapted the input CSV for ALE metadata (timepoints, ancestor/evolved labels, ploidy). Document what columns you added and why.
Variant calling configuration — you're using HaplotypeCaller with variable ploidy for yeast, skipping BQSR (--skip_tools baserecalibrator), and using hard filtering instead of VQSR. Document the specific filter thresholds and the rationale.
Any custom modules — the VARIANTFILTRATION_FALLBACK process, anything ALE-specific for post-variant-calling analysis.
Reference genome handling — how users provide yeast references without dbSNP/known_indels.
Test-data on a new VM — `data/ottilie/samplesheet_test.csv` holds machine-specific *absolute* FASTQ paths and is gitignored. On a new machine, run `docs/benchmarking/ottilie_xenobiotic_ale/01_data_retrieval/download_test_data.sh`; it fetches the data from the public blob (no creds) and **rewrites the samplesheet with that machine's paths** — never copy or hand-edit the CSV between machines. The blob-URL samplesheet (`samplesheet_test_blob.csv`, on blob) is separate and only for Seqera/streaming. Full flow + base URL: `docs/benchmarking/ottilie_xenobiotic_ale/DATA_PROVENANCE.md`; storage provisioning: `infra/azure/`.
