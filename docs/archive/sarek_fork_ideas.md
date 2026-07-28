# Sarek fork — deferred ideas

Capabilities the upstream nf-core/sarek base supports but this fork does **not** route — kept as ideas,
not active roadmap items. The fork's design choice is to treat **all samples as normal/germline**
(`status=0`) so HaplotypeCaller runs in joint-germline mode (see the "Sample Table Format" section of
`CLAUDE.md`). These upstream paths are left **inert, not deleted**, for upgrade-friendliness.

## Tumor-only mode (not routed)

Upstream Sarek has a `BAM_VARIANT_CALLING_TUMOR_ONLY_ALL` channel/path for samples with no matched
normal. This fork does not use it — every sample is processed as normal/germline. If a future use case
needs tumor-only calling (a sample treated as tumor without a paired normal), re-routing that channel is
the entry point. No code change is needed to *keep* it inert; it simply isn't wired into the all-normal
flow today.
