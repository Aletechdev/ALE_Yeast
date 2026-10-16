# Stub-mode placeholders — empty on purpose

Zero-byte files used only by the stub-mode subworkflow tests (`tests/manta_experiment_grouping.nf.test`,
`tests/joint_calling_output_selection.nf.test`): the tools never execute, so nothing reads these. They
exist because Nextflow still *stages* declared inputs, and because joint mode groups several files into
one task — which means each sample needs a **distinct file name** or the task dies with an input file
name collision. The same rule gives `ref.fasta`, `ref.fasta.fai` and `ref.dict` three names, and
`chrI.bed` (the one interval), `known_sites.vcf.gz` + `.tbi` (a stand-in VQSR resource) theirs.

Do not use these for anything that actually reads a CRAM, VCF, FASTA or BED.
