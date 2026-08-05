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
   | *(no obvious exception)* — DAG aborts while building an optional input | a `file(params.x)` on a **null** param. `file(null)` throws during workflow construction, before any task runs | make the param optional with the `[]` idiom (see below), or set it |

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
- **A null optional param** — with `generate_reports` true (its default) and `--report_gff3` unset,
  `file(params.report_gff3)` threw while the DAG was being built, and the abort surfaced as
  *"only contains tumor-samples … expect at least one normal-sample : haplotypecaller"*. The
  samplesheet was fine. This one cost a long debugging session on the first Azure Batch run, because
  the message points at the input while the cause is in the report wiring.
  **Fixed (2026-08-04)** — `report_gff3` is now genuinely optional; reports build without the gene
  track. Verified end-to-end: 30 reports, `PREPARE_GFF3` skipped, cohort report carries a full
  variant table.

### Making an optional file param actually optional

The fix generalises. Pass **`[]`**, never `null` and never a placeholder filename:

```groovy
// workflow: [] declares no file at all
params.report_gff3 ? file(params.report_gff3, checkIfExists: true) : []

// module: an absent path is falsy, so build the flag conditionally
def tracks_arg = gff3_gz ? "--tracks ${gff3_gz}" : ''
```

Two traps this avoids:

- **`file(null)` throws at DAG-construction time**, producing the misdirection above rather than a
  message naming the param.
- **A placeholder filename (`file('NO_SUCH_FILE')`) breaks on remote work dirs.** It works locally —
  Nextflow symlinks it and `ln -s` to a missing target succeeds — but with `az://`/`s3://` every input
  is physically copied, so FilePorter fails with `Can't stage file … -- file does not exist`. `[]`
  declares nothing to stage. See [`azure_batch_execution.md`](azure_batch_execution.md) §5.

⚠️ For a value consumed as `tuple path(a), path(b)`, pass `[[], []]` — one `[]` per path.

### The real fix (roadmap)

The console message should distinguish a genuine sample-sheet issue from an upstream failure. Preferred
approach: wrap the sample-validation logic so unrelated exceptions re-throw with context instead of being
reported as a tumor/normal problem. Tracked in [`roadmap.md`](roadmap.md) (Robustness / infrastructure).

---

## Closures in a config file — `Unknown method invocation … on _parse_closureN type`

Groovy closure-scoping, not a Nextflow-specific quirk. Applies to any config that defines a helper
closure; in this repo that is only [`conf/azure_batch.config`](../../conf/azure_batch.config) (`req()`,
the env-var guard).

The config parser wraps the file body in generated closures (`_parse_closureN`) to turn `azure { … }`
into config sections. A bare name followed by `(…)` inside one is dispatched as a **method** on the
config-builder delegate. Whether that resolves depends on how the closure was declared. Measured on
25.10.4:

| Declaration / call | `nextflow run` | `nextflow config` |
|---|---|---|
| `def req = { … }` then `req('X')` — **current** | ✅ | ❌ |
| `req = { … }` — no `def` | ❌ | ❌ |
| `req.call('X')` — explicit invocation | ✅ | ❌ |
| `System.getenv('X')` — static method | ✅ | ✅ |
| `def v = 'x'` then `params.foo = v` — no invocation | ✅ | ✅ |

Two consequences:

- ⚠️ **Keep the `def`.** It makes `req` a *local* the `azure { … }` closure captures lexically. Without
  it `req` lands in the script binding, dispatch falls back to the delegate, and **`nextflow run` breaks
  too**. Looks like harmless tidying; breaks the Azure Batch path.
- ⚠️ **`nextflow config` cannot read such a file** — at any nesting depth, and `.call()` is not a
  workaround. The error says the file is broken; the accurate statement is that the command can't read
  it. Failure is at parse time, so there is no process name or work dir in the message. Validate with a
  preview run instead:

  ```bash
  nextflow run main.nf -c conf/azure_batch.config -params-file conf/params_ottilie_blob.yml -preview
  ```

Whether the `nextflow config` behaviour is deliberate or an upstream bug has not been investigated.

**Scope.** [`conf/azure_batch.config`](../../conf/azure_batch.config) is the only config in this repo
that defines a closure — `req()`, the environment-variable guard — so it is the only file affected.
Whether this is a deliberate `nextflow config` limitation or an upstream bug has not been investigated;
it has only been observed on 25.10.4.
