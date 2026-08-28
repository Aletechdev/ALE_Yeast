# ALE Modifications vs. nf-core/sarek 3.5.1

**Purpose:** the authoritative inventory of every change the ALE fork makes on top of pristine
nf-core/sarek 3.5.1. This is the primary reference for a future sarek rebase (see
[`ale_sarek_upgrade_runbook.md`](ale_sarek_upgrade_runbook.md)) and for onboarding.

**Guiding principle** (from the runbook): keep modifications *additive* and *isolated*. New files
(local subworkflows/modules, configs) don't conflict on rebase. In-place edits to upstream files —
especially the 3 patched `modules/nf-core/` modules and `workflows/sarek/main.nf` — are the real
rebase cost; each is called out below.

## How to regenerate this diff

```bash
# Pristine 3.5.1 lives at /tmp/sarek_upstream_351/3_5_1 (or the sarek-compare worktree).
# Re-download with: nf-core pipelines download sarek --revision 3.5.1  (nf-env conda)
U=/tmp/sarek_upstream_351/3_5_1
diff -qr subworkflows/local "$U/subworkflows/local"
diff -qr modules/local      "$U/modules/local"
diff -qr modules/nf-core    "$U/modules/nf-core" | grep -v '/tests\|environment.yml\|meta.yml'
diff -qr conf               "$U/conf"
for f in main.nf nextflow.config nextflow_schema.json workflows/sarek/main.nf; do diff -q "$f" "$U/$f"; done
```

## Summary

| Category | Added | Modified (in-place — rebase cost) |
|----------|-------|-----------------------------------|
| Root files | — | `main.nf`, `nextflow.config`, `nextflow_schema.json` |
| Core workflow | — | `workflows/sarek/main.nf` ⚠️ heaviest |
| `subworkflows/local/` | 7 | 11 |
| `modules/local/` | 16 | 0 |
| `modules/nf-core/` | 5 (installed) | **3 patched** ⚠️ |
| `conf/` | 9 | 7 |

---

## Root files (modified in place)

- **`workflows/sarek/main.nf`** ⚠️ — the largest edit surface. ALE additions: custom VCF filtering
  channels (FreeBayes/Mutect2 AF filters via `TABIX_TABIX` + `vcf_with_tbi`), and the **inline
  MUTATION_REPORT** call at the end of the MultiQC block with the `ch_report_vcfs` annotated-or-raw
  fallback (commit `246dd7b`). Record the report's channel contract here on every rebase.
- **`main.nf`** — removed the old outer MUTATION_REPORT path-discovery call (superseded by the inline
  call); otherwise close to upstream.
- **`nextflow.config`** — ALE params (report_* / generate_reports / split & hard-filter HC), extra
  `includeConfig`s, ALE profiles.
- **`nextflow_schema.json`** — schema entries for the new params.

### New params (nextflow.config / schema)

`joint_manta` (upstream-shaped, PR candidate), `generate_reports`, `split_haplotypecaller_joint_vcf`, `hard_filter_haplotypecaller_joint`,
`report_gff3`, `report_filter_config`, `report_cohort_template`, `report_sample_template`,
`report_index_script`, `report_templates_dir`, `report_outdir`, `report_multiqc_path`.

---

## `subworkflows/local/` — ADDED (7, additive — low rebase cost)

| Subworkflow | Purpose |
|-------------|---------|
| `mutation_report` | Multi-caller dashboard (CN/SV matrices + igv-reports + index). Channel-based. |
| `split_joint_vcf` | Split joint germline VCF → per-sample VCFs (channel-based metadata). |
| `vcf_filter_haplotypecaller_joint` | Hard-filter per-sample VCFs from joint calling. |
| `vcf_filter_freebayes` | AF-based somatic-style filter for FreeBayes (dev/troubleshooting). |
| `vcf_filter_mutect2` | AF-based filter for Mutect2 (dev/troubleshooting). |
| `bam_variant_calling_germline_controlfreec` | Single-sample Control-FREEC (germline). |
| `fastq_variant_calling_breseq` | breseq path (AMP-v1 legacy integration, not Tier 1). |

## `subworkflows/local/` — MODIFIED (11, in place)

| Subworkflow | ALE change (why) |
|-------------|------------------|
| `bam_variant_calling_germline_all` | ⚠️ Core ALE wiring: CNVKit `.cnr/.cns` emits + 4 `hc_kind` lineage tags; FreeBayes somatic disabled; Control-FREEC germline; split/hard-filter HC. |
| `bam_variant_calling_germline_manta` | `joint_manta` input + one `groupTuple` branch (per-patient multi-sample run). Deliberately mirrors upstream `joint_mutect2`; new lines in 3.10 strict-syntax dialect, no versions plumbing → pastes onto sarek `dev` unchanged. **Upstream PR candidate** — keep free of ALE-specific logic. |
| `bam_variant_calling_cnvkit` | Ploidy passthrough; emit `cnr`/`cns_batch` for the report. |
| `bam_joint_calling_germline_gatk` | `VARIANTFILTRATION_FALLBACK` when VQSR can't run (custom genomes, no known-sites). |
| `samplesheet_to_channel` | ALE metadata columns (ploidy; all-samples-as-normal). |
| `utils_nfcore_sarek_pipeline` | YAML `processVersionsFromYAML()` fix for custom VCF filters. |
| `bam_variant_calling_somatic_all` | FreeBayes somatic channel disabled (noise for ALE). |
| `bam_variant_calling_somatic_mutect2` | FilterMutectCalls placeholder-channel fix (runs without germline resource/PoN). |
| `annotation_cache_initialisation` | Custom SnpEff cache handling. |
| `bam_variant_calling_somatic_controlfreec`, `bam_variant_calling_tumor_only_controlfreec` | Ploidy/germline adjustments. |

## `modules/local/` — ADDED (16, additive)

Report/analysis modules (all consumed by `mutation_report`): `build_cn_matrix`, `build_cn_cohort`,
`build_sv_matrix`, `cnr_to_bedgraph`, `filter_pass_vcf`, `generate_index`, `igvreports_cohort`,
`igvreports_sample`, `igvreports_sv_cnv`, `prepare_gff3`, `prepare_vcf`, `publish_vcfs`,
`survivor_cohort_merge`, `survivor_sv_merge`. Legacy/other: `breseq`, `gdtools`.

---

## `modules/nf-core/` — PATCHED (3 — ⚠️ highest rebase risk)

These are in-place edits to upstream nf-core modules. On rebase, re-apply or re-evaluate each:

| Module | ALE change |
|--------|------------|
| `gatk4/haplotypecaller/main.nf` | `--sample-ploidy ${meta.ploidy}` for variable-ploidy yeast (Tier 1). |
| `vcftools/main.nf` | Conditional-skip guards (ploidy>2, Mutect2 phased GT, joint-calling segfault). |
| `controlfreec/freec/main.nf` | Ploidy / custom-genome adjustments. |

## `modules/nf-core/` — ADDED (5, via `nf-core modules install`)

`bcftools/filter`, `bcftools/query`, `bcftools/view`, `gatk4/variantfiltration`, `igvreports`.
Upstream-managed modules (clean installs, low rebase cost).

---

## `conf/` — ADDED (9)

- **Report/filter:** `modules/mutation_report.config`, `modules/custom_freebayes_filter.config`,
  `modules/custom_mutect2_filter.config`, `modules/custom_haplotypecaller_joint_filter.config`,
  `modules/breseq.config`.
- **Profiles/params:** `test/ottilie_test.config` (the ALE test dataset + tool set),
  `seqera_azure.config`, `params_seqera_381.yml`, `params_seqera_test.yml`.

## `conf/` — MODIFIED (7, in place)

`base.config`, `modules/cnvkit.config` (ploidy on call+export; germline CNVKIT_CALL prefix),
`modules/controlfreec.config` (ASSESS_SIGNIFICANCE skip on ploidy=1), `modules/joint_germline.config`
(VARIANTFILTRATION_FALLBACK params, SPLIT_JOINT_VCF publish), `modules/freebayes.config`,
`modules/tiddit.config`, `modules/modules.config` (vcftools conditional `ext.when`).

---

## Rebase guidance

1. **Additive files** (added subworkflows/modules/configs) carry forward with no conflict — copy them in.
2. **The 3 patched nf-core modules + `workflows/sarek/main.nf`** are the real work: re-apply each edit
   against the new upstream, then re-run the ALE contract test (`tests/ottilie_e2e.nf.test`) to confirm
   the deliverables still match. If a deliverable shifts, the CSV/tree assertions pinpoint it.
3. **Do NOT** surgically delete unused upstream tools (sentieon, ascat, dragmap, tumor-only) — leaving
   them inert is more upgrade-friendly than a delete-patch that conflicts forever (see runbook).
4. Upstream-provided `*.diff` patches (dragmap, gatk4/intervallisttobed, bcftools/annotate,
   controlfreec/assesssignificance) ship with sarek — retain them, they are not ALE changes.
