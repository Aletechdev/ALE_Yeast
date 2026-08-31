# Comparing pipeline outputs — what is a real difference, and what is noise

Two audiences, one problem:

- **Test authors** deciding what may be snapshotted byte-for-byte and what must go in
  [`tests/.nftignore`](../../tests/.nftignore).
- **Anyone diffing two runs** — cloud vs local, before vs after a change, two Azure Batch runs — and
  needing to know whether a difference is a regression.

The underlying question is the same: **which outputs of this pipeline are deterministic?** Fewer than
you would hope. This page lists the classes, the cause of each, and how to compare anyway.

> Worked example throughout: the 2026-08-06 comparison of a Seqera Platform run against the verified
> local-head-job baseline — 529 files in common, **464 byte-size identical, 65 differing, 0 regressions**.
> See [`azure_batch_execution.md` §11](azure_batch_execution.md).

---

## 1. The rule: compare deliverables byte-for-byte, everything else by content

**The acceptance criterion is the nine cohort deliverables (all CSV, listed below)**, because they are
what the pipeline exists to produce and they are genuinely deterministic. Elsewhere in these docs they
are referred to by the shorthand **"cohort deliverables"** — *cohort* separates them from per-sample
outputs, *deliverable* marks them as the thing that must be byte-identical:

```
mutation_reports/data/cn_cohort_collapsed.csv        mutation_reports/data/sv_cohort_matrix_union.csv
mutation_reports/data/cn_cohort_full.csv             mutation_reports/data/sv_cohort_matrix_union_pass.csv
mutation_reports/data/cn_matrices/cn_matrices/cn_bins_continuous.csv
mutation_reports/data/cn_matrices/cn_matrices/cn_chr_summary_{call,germline}.csv
mutation_reports/data/cn_matrices/cn_matrices/cn_segments_{call,germline}.csv
```

All nine were **byte-identical** across local and cloud. If one of those differs, it is a real finding.
Everything else needs normalising before it means anything.

---

## 2. Classes of non-determinism, and how to normalise each

### 2.1 Embedded timestamps and command lines — VCFs

VCF headers record when and how they were made. Strip before comparing:

```bash
zcat a.vcf.gz | grep -vE '^##(fileDate|source|SnpEffCmd|SnpEffVersion|bcftools_|GATKCommandLine)' > a.norm
zcat b.vcf.gz | grep -vE '^##(fileDate|source|SnpEffCmd|SnpEffVersion|bcftools_|GATKCommandLine)' > b.norm
diff a.norm b.norm
```

⚠️ **`##TIDDITcmd` embeds the thread count**, so TIDDIT VCFs can *never* be byte-identical between runs
with different `cpus`. A local `azureD4as` run (2 CPUs) vs Azure Batch `Standard_E4ds_v4` (4 CPUs) once
produced 8 "differences" that were purely `--threads 2` vs `--threads 4`, with zero variant-record
deltas. Strip that line or expect a false alarm.

### 2.2 gzip / bgzf framing — `.vcf.gz`, `.tbi`

Compressed containers differ by a few bytes even when the payload is identical (compressor version,
block boundaries, embedded mtime). Deltas of **1–7 bytes** on a `.vcf.gz` or `.tbi` are the signature.
**Always decompress before comparing** — never trust the `.gz` bytes.

The framing can also flip **run-to-run on the same machine** when the compressor is multithreaded:
mosdepth's `.regions.bed.gz` produced identical bytes on two consecutive runs (so a recorded md5
snapshot passed its determinism re-run) and then a different — content-identical — byte stream days
later, purely from thread scheduling (caught 2026-08-31). Two consecutive agreeing runs therefore do
NOT prove a `.gz` is byte-stable; snapshot compressed files by name only (`tests/.nftignore`) and
compare their content decompressed.

### 2.3 Absolute paths embedded in outputs

Sarek writes the output directory into its own bookkeeping CSVs:

```
csv/markduplicates_no_table.csv      csv/variantcalled.csv
```

So a longer `outdir` string produces a bigger file. In the worked example
`seqera-runs/2026-08-06-04` vs `ottilie-azurebatch-out` accounted **exactly** for the +12 and +33 byte
deltas. Same for `pipeline_info/params_*.json`. Normalise by rewriting the path, or ignore these files.

### 2.4 Render non-determinism — MultiQC plots and data

`multiqc/multiqc_plots/{svg,pdf,png}/*` and several `multiqc_data/*` files differ between runs on the
same inputs (font metrics, dict ordering, embedded creation dates). PDFs can differ by **tens of KB**,
which looks alarming and is not. Compare the underlying numbers instead, never the render.

### 2.5 Embedded base64 blobs — igv-reports HTML

`mutation_reports/samples/*_report.html` embeds a `sessionDictionary`: a base64-encoded gzip of IGV
alignment views, non-deterministic across gzip runs. File sizes differ slightly between identical runs.

**Compare the variant table instead** — that is the actual content:

```bash
grep -o 'const tableJson = .*' report.html | head -1 > a.tablejson
```

This is how all 17 reports (16 per-sample + cohort) were verified equivalent between pipeline versions.

### 2.6 Provenance that *should* differ — `versions.yml`

```
Aletechdev/ALE_Yeast: v1.0.0            # run from a local directory
Aletechdev/ALE_Yeast: v1.0.0-g86c4672   # run from a Git clone (Seqera Platform, nextflow run <org/repo>)
```

nf-core appends the short commit when a commit id exists. **Not a regression** — it is provenance, and
it means `versions.yml` can never be byte-compared across those two launch modes.

⚠️ The verified Azure Batch baseline at `az://aletest/ottilie-azurebatch-out/` was produced under the
old `manifest.name` (`Aletechdev/AMP`), so that line differs there too. See
[`CLAUDE.md` → Pipeline Identity & Naming](../../CLAUDE.md).

### 2.7 Per-execution filenames — `pipeline_info/`

`execution_report_<timestamp>.html`, `execution_timeline_*`, `execution_trace_*`, `pipeline_dag_*`,
`params_*.json`, `manifest_*.bco.json` are timestamped per execution, so the **file names** differ and
the **counts** differ if one side was run more than once. In the worked example this fully explained
540 vs 534 files. Compare by *class*, not by name.

### 2.8 Everything else seen once

- **CRAM ±1 byte** — header metadata.
- **snpEff QC summaries** (`reports/snpeff/*`) — embedded run date.
- **FastQC html/zip**, samtools/picard stats — embedded dates and paths.

### 2.9 Identifiers and column order derived from input file order — **NOT noise, fix it**

The one class in this list that must **never** be normalised away or added to `.nftignore`: a
difference caused by the *order* in which files were handed to a tool. `groupTuple()` and `collect()`
emit in channel-arrival order, which depends on which upstream task finished first; a tool that reads
that order into its output makes every run different by chance.

Seen 2026-08-28 (fixed in `6892309`): `MANTA_GERMLINE` builds `--bam a --bam b …` from the grouped
CRAM list, and Manta numbers its record IDs (`MantaBND:52:1:3:…` vs `…:1:4:…`), the `MATEID`s pairing
breakends, and the joint VCF's **sample-column order** from it. Two runs then produce the same
variants, genotypes, filters and coordinates under different names — which propagates to every
downstream hash (the igv-report `tableJson` is what caught it).

**How to recognise it:** the bodies are identical apart from ID-like strings, or the `#CHROM` sample
columns are permuted. Compare the two VCFs with the header stripped; check `##cmdline` for the input
order. **How to fix it:** sort the grouped list — `groupTuple(sort: { it.name })` — never ignore the
file. **How to test for it:** re-running the same input proves nothing (with N samples the same order
recurs by chance); run once with the samplesheet rows **reversed**. Full lesson, and why the repo's
other `groupTuple` calls are safe: [`testing_best_practices.md`](testing_best_practices.md)
§"`groupTuple` order is not deterministic".

---

## 3. Method: comparing two runs directly

Three tiers, cheapest first. Do not skip to hashing everything — most differences are explained at
tier 1 or 2.

### Tier 1 — names

Which files exist on each side. Catches missing outputs, the failure that matters most.

```bash
az storage blob list -c <container> --prefix <run>/ --account-name <acct> --auth-mode login \
  --num-results 10000 --query "[].{n:name,s:properties.contentLength}" -o json > run.json
```

Then set-difference the names. Expect differences only in `pipeline_info/` (§2.7). **Anything else
present on one side only is a real finding.**

### Tier 2 — sizes

`contentLength` is free (already in the listing) and rules out most files without downloading anything.
Equal size is not proof of equality, but **different size is proof of difference** — and the *magnitude*
of the delta usually identifies the class (1–7 bytes → §2.2; tens of KB on a PDF → §2.4).

### Tier 3 — hashes, on the files that must be identical

Download only the deliverables from §1 and `md5sum` them.

> ⚠️ **`contentMd5` is NOT populated on blobs published by Nextflow** — verified 0/534. Azure stores it
> only when the uploader supplies it, and Nextflow's publish path does not. Any comparison plan built on
> "read `Content-MD5` from the blob listing" **will silently compare nothing**: every value is `null`,
> so a naive equality test reports zero differences. Download and hash instead.

### The failure mode to design against

A check that asserts on **exit status** rather than on **content** produces false confidence. This has
already happened here once: a staging test passed because the command exited 0 while zero files had
actually arrived. **Assert on what landed** — counts, sizes, hashes — never on the exit code alone.

---

## 4. Implications for nf-test design

- **Snapshot the deliverables, ignore the renders.** [`tests/.nftignore`](../../tests/.nftignore) already
  excludes `multiqc/multiqc_plots/**`, `pipeline_info/*`, `csv/*.csv`, `annotation/**/*.vcf.gz` and the
  rest of the classes above. This page is the *why* behind those entries — consult it before adding or
  removing one.
- **Prefer content assertions over byte snapshots** for anything in §2. Assert on variant counts, on
  parsed CSV values, on `tableJson` — not on file bytes.
- **A new ignore entry needs a stated cause.** If you cannot name which class in §2 it belongs to, the
  difference is probably a real bug, and ignoring it hides the bug permanently.
- **Review the `.snap` diff as source code.** `--update-snapshot` re-records *every* failing snapshot,
  so a genuine regression sitting next to an intended change is silently blessed. See
  [`testing_best_practices.md` §10](testing_best_practices.md).

---

## 5. Open item

Everything above is done by hand. A run-comparison helper implementing tiers 1–3 with the
normalisations in §2 would make cloud-vs-local comparison repeatable rather than a one-off. **No such
script exists yet** — deliberately not referenced by path here, so nothing points at a file that isn't
there. Until it is written, budget an hour and follow this page.
