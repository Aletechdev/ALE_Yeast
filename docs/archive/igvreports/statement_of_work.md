# D1.2 Extend nf-core/Sarek QC Reports for Viewing and Filtering Mutations

## Description

nf-core/Sarek generates MultiQC reports summarizing raw read quality, alignment statistics, and detected mutation counts. For ALE experiments, biologists also need to review individual mutations with read-level evidence — similar to BreSeq's offline HTML report. The QC reporting is extended using a three-tier approach: offline HTML reports (igv-reports), programmatic analysis (Jupyter), and interactive genome browsing (Desktop IGV).

## Acceptance Criteria

- [x] Review listing mutations by BreSeq's gdtools, nf-core/igvreports, custom HTML
- [x] Review visualization of alignment around mutations by BreSeq's gdtools, IGV preview/app, nf-core/igvreports
- [x] Design solutions and plans for improving mutation QC through iterations and user feedback

## Exit Criteria

- [ ] Mutation QC production design approved by stakeholders
- [ ] QC view mutations list function approved by stakeholders
- [ ] QC view alignment function approved by stakeholders

---

## Three-Tier Variant Review Strategy

Tiers are ordered by barrier to entry — biologists start with the simplest tool and only move to more complex tools when needed. See [check_mutations.md](../../igvreports/check_mutations.md) for full technical details.

### Tier 1: igv-reports HTML — Zero-Code Variant Review [DONE]

- **Purpose**: Filter/sort variants, inspect read pileups, share reports
- **Barrier**: None — open an HTML file in any browser
- **Status**: Implemented and tested with 6 I1 yeast ALE samples
- **Key features**: Filterable cohort table, per-sample alignment reports, cross-linking cohort → sample at exact variant, filter export/import, CSV/VCF download

### Tier 2: Jupyter Studio — Programmatic VCF Analysis & Plots [PLANNED]

- **Purpose**: Cross-sample comparison, statistical analysis, publication figures
- **Platform**: Seqera Cloud Studios (Jupyter template + Conda)
- **Barrier**: Basic Python — run pre-written cells, modify parameters
- **Key features**: VAF distributions, mutation spectra, gene burden heatmaps, multi-tool concordance

### Tier 3: Desktop IGV via Xpra Studio — Interactive Exploration [PLANNED]

- **Purpose**: Free-form genome browsing, multi-track visualization, ad-hoc investigation
- **Platform**: Seqera Cloud Studios (Xpra template)
- **Barrier**: Platform setup — launch Studio, configure tracks
- **Key features**: Full IGV desktop in browser, BAM/CRAM via Fusion mounts, no embedding limits

---

## Planned Improvements (Tier 1)

- [ ] Column documentation: tooltips/help for non-VCF-expert users
- [ ] Cohort coverage track: total-depth bigWig in IGV panel
- [ ] Performance optimization: lazy-load IGV, compress embedded data
- [ ] Modern UI: dark mode, IMPACT color-coding, keyboard navigation
- [ ] Visual indicator for clickable sample cells in cohort table

## Deliverables

| Deliverable | Description | Format |
|-------------|-------------|--------|
| Cohort HTML report | All joint-called variants, filterable table with cross-links | HTML |
| Per-sample HTML reports | Individual variants with read pileup alignment | HTML |
| Jupyter template notebook | Cross-sample analysis and publication plots | .ipynb |
| IGV Desktop setup guide | Xpra Studio configuration for alignment browsing | Documentation |
