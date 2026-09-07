# Stub-mode placeholders — empty on purpose

Zero-byte files used only by `tests/manta_experiment_grouping.nf.test`, which runs in stub mode:
Manta never executes, so nothing reads these. They exist because Nextflow still *stages* declared
inputs, and because joint mode groups several CRAMs into one task — which means each sample needs a
**distinct file name** or the task dies with an input file name collision.

Do not use these for anything that actually reads a CRAM.
