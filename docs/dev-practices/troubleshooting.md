# Troubleshooting

Debugging notes for confusing pipeline failures.

## The misleading "sample-sheet only contains normal/tumor-samples" error

**Symptom.** The console shows something like:

```
The sample-sheet only contains normal-samples, but the following tools expect
at least one tumor-sample: controlfreec, mutect2, msisensorpro
```

…but your samplesheet clearly has the right `status` values. **Do not trust this message** — it is
almost always a *downstream symptom* of an unrelated upstream failure, not a real sample-status problem.

### Why it lies

The `input_sample` channel fails to populate whenever **any** earlier error occurs (schema validation,
a config syntax error, a workflow wiring bug). The germline/somatic split then hits an empty channel:

```groovy
// subworkflows/local/samplesheet_to_channel/main.nf (~146-166)
input_sample.filter { it[0].status == 1 }.ifEmpty { error("... expect at least one tumor-sample ...") }
```

The `.ifEmpty{}` fires on the empty channel and prints the tumor/normal error, while the **real**
exception is only in `.nextflow.log`. Three layers stack up: (1) the wrong console message, (2) a
possibly-misleading validation message in the log, (3) the actual root cause.

### Find the real error

1. **Read `.nextflow.log`, earliest exception first** (not the tumor/normal one):
   ```bash
   grep -nE "Exception|ERROR" .nextflow.log | head -20
   ```
2. **Match it to a real cause:**

   | Log error | Real cause | Fix |
   |-----------|-----------|-----|
   | `SchemaValidationException: file or directory '…' does not exist` (but the file *does* exist) | samplesheet paths are **relative**, validated from a different working dir | use **absolute paths** in the samplesheet |
   | `Process XXX declares N input channels but M were specified` | process-invocation bug in workflow code (nothing to do with the samplesheet) | fix the process call to match its input signature |
   | `No such variable` / `Unknown method` | config syntax error or missing import | check recently edited `.config` files (e.g. a missing comma) |
   | `Missing or unknown field in csv file header` | genuine samplesheet header error | fix the column names |

3. **Sanity-check the samplesheet is actually valid:**
   ```bash
   awk -F, 'NR>1 {print $3}' samplesheet.csv | sort | uniq -c   # status counts (0=normal, 1=tumor)
   head -5 samplesheet.csv | tail -4 | awk -F, '{print $8}' | xargs ls -lh   # do the FASTQs resolve?
   ```
4. **Bisect recent features.** If you just added a workflow/flag (e.g. `--split_haplotypecaller_joint_vcf`),
   disable it to isolate whether the failure is in the new path.

### Real cases seen

- **Relative FASTQ paths** — samplesheet used `../data/…/file.fastq.gz`; nf-validation resolved them from
  a different directory → "file does not exist" for a file that exists. Absolute paths fixed it.
- **Config syntax** — a missing comma in `custom_freebayes_filter.config` surfaced only as the tumor/normal
  error.
- **Workflow wiring** — `BCFTOOLS_VIEW declares 4 input channels but 1 were specified` (a SPLIT_JOINT_VCF
  input mismatch) masqueraded as a sample-status error.

### The real fix (roadmap)

The console message should distinguish a genuine sample-sheet issue from an upstream failure. Preferred
approach: wrap the sample-validation logic so unrelated exceptions re-throw with context instead of being
reported as a tumor/normal problem. Tracked in [`roadmap.md`](roadmap.md) (Robustness / infrastructure).
