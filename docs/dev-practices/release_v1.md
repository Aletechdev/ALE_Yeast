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
