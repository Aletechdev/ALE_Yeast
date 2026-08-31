# FASTQ preprocessing — audit + trimmer plan (post-v1.0.0)

Scope: everything that happens to reads **between the samplesheet and bwa-mem** — FastQC, fastp, and
the proposed Trimmomatic option. Written 2026-08-11 against `main` @ `995817f`.

Two deliverables are described here and tracked as separate items in
[`roadmap.md`](roadmap.md#read-preprocessing--fastq-qc--trimming):

1. **Audit** — what the FASTQ path actually does today, and the defects found while establishing that.
2. **Plan** — expose fastp's quality trimming, then add Trimmomatic as an alternative trimmer.

> **Baseline warning for everything below.** The verified Azure Batch baseline at
> `az://aletest/ottilie-azurebatch-out/` was produced with **no read trimming at all**. Any change
> that alters the reads reaching bwa-mem invalidates byte-comparison against it and shifts variant
> calls. Every new option must therefore default to **off**, and the ottilie configs must stay
> untouched unless the baseline is deliberately re-cut.

---

## 1. Audit — what runs today

### 1.1 The actual path

| Stage | Process | Gate | Status on an ALE run |
|---|---|---|---|
| Raw-read QC | `FASTQC` | `!skip_tools.contains('fastqc')` | **runs** — report only |
| Trim / split | `FASTP` | `trim_fastq \|\| split_fastq > 0` ([`workflows/sarek/main.nf:266`](../../workflows/sarek/main.nf#L266)) | **never runs** |
| Alignment | `bwa-mem` | — | receives the **raw** FASTQs |

FastQC runs on the *input* FASTQs ([`main.nf:228-232`](../../workflows/sarek/main.nf#L228-L232)) with
`--quiet` as its only argument ([`modules.config:22-32`](../../conf/modules/modules.config#L22-L32)),
publishes to `reports/fastqc/<id>/`, and feeds MultiQC. Nothing downstream reads its verdicts.

### 1.2 Findings

**A. fastp never executes on any ALE run.** `trim_fastq` defaults `false`
([`nextflow.config:38`](../../nextflow.config#L38)) and every ALE config forces `split_fastq = 0` —
[`ottilie_test.config:58`](../../conf/test/ottilie_test.config#L58),
[`ottilie_test_ci.config:67`](../../conf/test/ottilie_test_ci.config#L67),
[`params_ottilie_test_blob.yml:63`](../../conf/params_ottilie_test_blob.yml#L63),
[`run_ottilie_pilot.sh:28`](../benchmarking/ottilie_xenobiotic_ale/03_pipeline/run_ottilie_pilot.sh#L28).
So no adapter removal, no clipping, no length filter, no quality filter. `params_seqera_381.yml:34`
records the rationale — *"No trimming (good quality Illumina reads assumed)"*. **This is a defensible
choice, but it is currently an unstated one**: it is implied by a splitting parameter rather than
declared.

**B. Whether fastp runs is a side effect of the splitting parameter.** The gate is
`trim_fastq || split_fastq > 0`, and the inherited default `split_fastq = 50000000`
([`nextflow.config:35`](../../nextflow.config#L35)) is non-zero. A run that does not override it gets
fastp as a pure splitter with `--disable_adapter_trimming` — *but still subject to fastp's default
read-level quality filters* (`-q 15`, `-u 40`, `-n 5`). Reads are therefore silently discarded on a
"no trimming" run, and whether that happens depends on a parameter nobody sets for QC reasons.

**C. No quality-based trimming is reachable.**
[`conf/modules/trimming.config:19-28`](../../conf/modules/trimming.config#L19-L28) is the complete
fastp argument list; it exposes adapter on/off, fixed-count 5′/3′ clipping, poly-G, splitting and
`length_required`. fastp's sliding-window trimmers — `--cut_front`, `--cut_tail`, `--cut_right`, with
`--cut_mean_quality` / `--cut_window_size` — are never emitted and have no parameter. The string
`cut_` does not appear anywhere in the repo. Consequence: **no base is ever removed because of its
quality score**, in any configuration of this pipeline.

**D. `trim_nextseq`'s value is silently discarded, and its comment is wrong.**
[`trimming.config:25`](../../conf/modules/trimming.config#L25) tests only truthiness and emits a bare
`--trim_poly_g`, so `--trim_nextseq 20` and `--trim_nextseq 1` behave identically despite the schema
declaring an integer with a default of 0. The inline comment — *"Apply the `--nextseq=X` option, to
trim based on quality after removing poly-G tails"* — describes **Trim Galore's** semantics; fastp's
`--trim_poly_g` performs no quality trimming. Inherited from upstream sarek 3.5.1, not fork damage.

**E. Discarded reads are unrecoverable.** `save_trimmed_fail` is hardcoded `false` at
[`main.nf:268`](../../workflows/sarek/main.nf#L268), so when fastp does run there is no way to inspect
*which* reads it dropped — only the aggregate counts in the JSON.

**F. No post-trim QC pass.** FastQC runs before fastp only. Post-trim visibility comes entirely from
fastp's own JSON/HTML, which are mixed into MultiQC at
[`main.nf:278-279`](../../workflows/sarek/main.nf#L278-L279) and rendered under "FastP (Read
preprocessing)" ([`multiqc_config.yml:126-127`](../../assets/multiqc_config.yml#L126-L127)). Adequate
for fastp; a gap the moment a second trimmer exists.

**G. Zero automated coverage of the preprocessing path.** No test under `tests/` exercises `FASTP` —
`ottilie_e2e` runs with `split_fastq = 0` and `trim_fastq = false`, and the `trimming` /
`split_fastq` test profiles ([`conf/test/trimming.config`](../../conf/test/trimming.config),
[`conf/test/split_fastq.config`](../../conf/test/split_fastq.config)) are upstream fixtures that
nothing in this repo runs. Any change in this area is currently unguarded.

**H. Cross-reference — the `split_fastq` schema-lint error.** `nf-core pipelines schema lint` already
fails on `split_fastq`'s `oneOf` construction (upstream boilerplate; tracked separately in
[`roadmap.md`](roadmap.md#deployment--seqera-launch-ui--schema)). Any restructuring of the
preprocessing schema should absorb that fix rather than work around it.

---

### 1.3 A concrete consequence (2026-08-27): adapter read-through masquerading as SV breakpoints

With no adapter removal, short library fragments carry Nextera adapter into the read, and bwa
soft-clips it. In the pilot clone `Doxorubicin16-R2b`, four positions on the mitochondrial contig
(46.7 / 48.2 / 58.6 / 59.5 kb) each show 150–440 reads clipped at the same base — exactly what a
rearrangement junction looks like in IGV, and what the validation notes initially took for one.
The clipped tails are `CTGTCTCTTATACACATCT…` (Tn5 mosaic end) and its partner; at the 59.5 kb
cluster 440 clipped reads fall to 12 once adapter-bearing clips are excluded, and none has a
supplementary alignment. No caller was fooled (the clips carry no mate/SA evidence), so **no call
changes today** — but anyone reading alignments by eye will be, and adapter-derived clips inflate
the soft-clip counts that SV-evidence heuristics use. Trimming (Plan A/B) would remove the
artefact at source; until then, treat soft-clip pile-ups whose tails start with the Tn5 sequence
as adapter, not breakpoints.

## 2. Plan A — expose fastp quality trimming

The cheap half. Reproduces Trimmomatic's quality behaviour without adding a tool.

### 2.1 Trimmomatic → fastp equivalence

| Trimmomatic | fastp | Semantics |
|---|---|---|
| `SLIDINGWINDOW:4:20` | `--cut_right --cut_right_window_size 4 --cut_right_mean_quality 20` | scan 5′→3′; at the first window below threshold, discard it **and the whole 3′ remainder** |
| `TRAILING:20` | `--cut_tail --cut_tail_window_size 1 --cut_tail_mean_quality 20` | trim in from the 3′ end, stop at the first passing base |
| `LEADING:20` | `--cut_front --cut_front_window_size 1 --cut_front_mean_quality 20` | same from the 5′ end |
| `MINLEN:36` | `--length_required 36` | **already exposed** as `length_required` |
| `AVGQUAL:20` | `--average_qual 20` | whole-read mean; drops rather than trims |

fastp's global defaults are already `-W 4 / -M 20`, so `--cut_right` alone **is** `SLIDINGWINDOW:4:20`.
`--cut_right` is the faithful analogue; `--cut_tail` is more permissive (a mid-read quality dip
survives it).

### 2.2 Changes

Four files, one of them the upstream workflow.

1. **[`nextflow.config`](../../nextflow.config#L37-L46)** — three params in the existing FASTP block,
   all defaulting to off:
   - `trim_quality = null` — enum `'front' | 'tail' | 'right'`
   - `trim_quality_mean = 20` → `--cut_mean_quality`
   - `trim_quality_window = 4` → `--cut_window_size`

   **An enum, not three booleans.** `cut_right` supersedes `cut_tail` and enabling both is a config
   bug fastp will not loudly reject; an enum makes the mutually-exclusive choice unrepresentable and
   renders as a dropdown in the Seqera launch form.

2. **[`nextflow_schema.json`](../../nextflow_schema.json#L175-L181)** — matching entries in
   `fastq_preprocessing`, after `length_required`. Not optional: `validate_params = true`
   ([`nextflow.config:165`](../../nextflow.config#L165)) with `nf-schema@2.2.1` means an unlisted
   param WARNs and never appears on the Launchpad.

3. **[`conf/modules/trimming.config`](../../conf/modules/trimming.config#L19-L28)** — three ternaries
   appended to `ext.args`, all gated on `params.trim_quality` so the tuning flags are absent (not
   merely ignored) when the mode is off. fastp accepts `--cut_mean_quality` with no mode enabled and
   silently ignores it, which would otherwise put dead arguments into every published `.command.sh`.

4. **[`workflows/sarek/main.nf:266`](../../workflows/sarek/main.nf#L266)** — extend the gate to
   `|| params.trim_quality`. **Without this the feature is a silent no-op** on exactly the configs
   ALE uses: `trim_fastq` false and `split_fastq` 0 means FASTP is never instantiated, so the flags go
   nowhere and the run looks like "trimming ran and changed nothing". The resulting combination
   (`--disable_adapter_trimming` + `--cut_right`) is coherent: quality trimming without adapter
   removal.

### 2.3 Validation

Run the 2-sample ottilie test with `--trim_quality right --save_trimmed` and check
`reports/fastp/<sample>/*.fastp.json`: `read1_after_filtering.total_bases` must fall against
`read1_before_filtering`, and the mean read length must drop below the fixed read length. Defaults
stay off, so `tests/ottilie_e2e.nf.test.snap` and the Azure baseline are unaffected.

---

## 3. Plan B — add Trimmomatic as an alternative trimmer

A `trimmomatic` module exists upstream in **nf-core/modules** (trimmomatic 0.39,
`quay.io/biocontainers/trimmomatic:0.39--hdfd78af_2`); it is **not installed here** — `modules.json`
currently vendors only `fastp` and `fastqc` from that repo. So this is not a from-scratch module. But
`nf-core modules install trimmomatic` at nf-core 3.5.1 pulls the **current master** module, and four
things about it collide with a sarek 3.5.1 fork. Each needs a decision before any code is written.

### 3.1 Blocker 1 — version reporting uses topic channels

The module emits versions as
`tuple val("${task.process}"), val('trimmomatic'), eval("trimmomatic -version"), topic: versions` —
the modern nf-core convention. Sarek 3.5.1 collects versions by mixing a `path "versions.yml"` output
into `ch_versions`, which this module does not produce. Installed as-is, Trimmomatic would be **absent
from `versions.yml`** — a provenance hole, and `versions.mix(TRIMMOMATIC.out.versions)` would not even
resolve.

Options: (a) patch the module to add a `versions.yml` block, which grows the patched-module list that
[`SAREK_MODIFICATIONS.md`](SAREK_MODIFICATIONS.md) tracks (currently 3) and must be re-applied at every
rebase; or (b) vendor an older module revision contemporary with sarek 3.5.1. **(a) is preferred** — a
pinned-old module rots silently, whereas a patch is already an established, documented cost here.

### 3.2 Blocker 2 — adapter clipping has no staged input

The module's input is `tuple val(meta), path(reads)` — there is **no adapter-FASTA input**. Trimmomatic
`ILLUMINACLIP` needs a real adapter file, and per the Azure Batch rule in
[`azure_batch_execution.md`](azure_batch_execution.md) an undeclared path is not staged to the node, so
a host path would fail on a remote work dir with an empty-stderr exit 1.

Options: (a) quality trimming only — `SLIDINGWINDOW`/`LEADING`/`TRAILING`/`MINLEN` need no file, and
this is the sane initial scope; (b) reference the adapter FASTAs **inside the biocontainer**
(`$CONDA_PREFIX/share/trimmomatic/adapters/TruSeq3-PE.fa`), which stages nothing but hard-codes a
container-internal path; (c) patch the module to take an adapter path input. **Start with (a)** — fastp
already does adapter removal better (`--detect_adapter_for_pe`, no adapter file needed).

### 3.3 Blocker 3 — fastp is also the splitter

`--split_by_lines` ([`trimming.config:26`](../../conf/modules/trimming.config#L26)) makes FASTP the
only implementation of `split_fastq`, and the downstream `n_fastq` re-chunking at
[`main.nf:281-286`](../../workflows/sarek/main.nf#L281-L286) consumes its output shape. Trimmomatic
cannot split. So `--trimmer trimmomatic` combined with `split_fastq > 0` must either chain
TRIMMOMATIC → FASTP(split-only) or be rejected at startup. **Reject it with a clear error** —
irrelevant for ALE (`split_fastq = 0` everywhere) and far cheaper than a two-tool chain.

### 3.4 Blocker 4 — argument ordering is semantic

Trimmomatic applies steps **in command-line order**, and the module interpolates `ext.args2` *before*
`ext.args`. Its naming implies `args2` = quality trimming, but the canonical recipe puts
`ILLUMINACLIP` first. If adapter clipping is ever added (3.2), it belongs in `args2` **despite the
name**. Worth a comment in the config, since it reads backwards.

### 3.5 Shape of the change

- New param `trimmer = 'fastp'` (enum `fastp | trimmomatic`), schema entry alongside it.
- A local subworkflow — `subworkflows/local/fastq_trim/` — owning the `if (params.trimmer == …)`
  branch and emitting one `reads` channel, so [`workflows/sarek/main.nf`](../../workflows/sarek/main.nf)
  gains **one include plus one call** instead of a second inline tool block. This matters: that file is
  already flagged as *"the largest edit surface"* in [`SAREK_MODIFICATIONS.md`](SAREK_MODIFICATIONS.md),
  and every line added there is a line to re-apply at the next sarek rebase. Consistent with
  [[prefer-isolated-config-over-shared]].
- `conf/modules/trimming.config` — a `withName: 'TRIMMOMATIC'` block mapping the same three
  `trim_quality*` params onto `SLIDINGWINDOW:<window>:<mean>` / `LEADING` / `TRAILING`, plus
  `MINLEN:${params.length_required}`, so **the two trimmers share one user-facing vocabulary** rather
  than exposing two dialects.
- `assets/multiqc_config.yml` — add `trimmomatic` to `top_modules`/`module_order` next to `fastp`
  ([lines 110-127](../../assets/multiqc_config.yml#L110-L127)). *Verify first* that MultiQC's
  Trimmomatic module parses the `-summary` output this nf-core module emits.
- The module's `unpaired_reads` output is dropped on the floor unless deliberately published —
  Trimmomatic's PE mode orphans reads that fastp would have discarded silently. Decide whether to
  publish under `save_trimmed`.

---

## 4. Open decisions

1. **Is Trimmomatic wanted as a production option, or as a one-off benchmark** to justify the fastp
   settings? If the latter, Plan B collapses to a throwaway comparison script and only Plan A lands in
   the pipeline. This should be settled with the team before any module is installed — it is the
   difference between ~4 files and a permanent second tool with a rebase cost.
2. **Symmetric or asymmetric quality trimming?** The enum in §2.2 assumes one mode at a time
   (`SLIDINGWINDOW` alone, the common recipe). Trimmomatic-style `LEADING:3 TRAILING:20` needs two
   independent params and a longer arg list.
3. **Does the ALE default change?** Everything above is opt-in. Turning trimming *on* by default is a
   separate decision that re-cuts the Azure baseline and requires re-validating the ottilie truth set
   (4 SNVs + the chr I duplication).

## 5. Suggested order

1. Fix the audit defects that are pure bugs — **D** (`trim_nextseq` value + comment) and the gate
   ambiguity in **B**. Independent of any trimmer work, no behaviour change for ALE runs.
2. Land Plan A (fastp quality trimming), with an nf-test over the preprocessing path (**G**) that also
   covers the existing `trimming` profile.
3. Settle open decision 1. Only then start Plan B.
