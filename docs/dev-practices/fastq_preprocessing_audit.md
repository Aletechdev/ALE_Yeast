# FASTQ preprocessing — audit + trimmer plan (post-v1.0.0)

Scope: everything that happens to reads **between the samplesheet and bwa-mem** — FastQC, fastp, and
the proposed Trimmomatic option. Written 2026-08-11 against `main` @ `995817f`.

Two deliverables are described here and tracked as separate items in
[`roadmap.md`](roadmap.md#read-preprocessing--fastq-qc--trimming):

1. **Audit** — what the FASTQ path actually does today, and the defects found while establishing that.
2. **Design (§2, 2026-09-02)** — opt-in fastp adapter + variable-length 3′ quality trimming, under one
   rule: *fastp changes only what a parameter asks for*. Plan B (Trimmomatic) stays a separate decision.

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

**B. Whether fastp runs is a side effect of the splitting parameter.** *(Addressed by §2.1: the
filter is now a documented, switchable parameter (`filter_quality`); its default stays on for upstream
parity — user decision 2026-09-02.)* The gate is
`trim_fastq || split_fastq > 0`, and the inherited default `split_fastq = 50000000`
([`nextflow.config:35`](../../nextflow.config#L35)) is non-zero. A run that does not override it gets
fastp as a pure splitter with `--disable_adapter_trimming` — *but still subject to fastp's default
read-level quality filters* (`-q 15`, `-u 40`, `-n 5`). Reads are therefore silently discarded on a
"no trimming" run, and whether that happens depends on a parameter nobody sets for QC reasons.

**C. No quality-based trimming is reachable.** *(Fixed by §2: `trim_quality_3prime` / `trim_quality_5prime`.)*
[`conf/modules/trimming.config:19-28`](../../conf/modules/trimming.config#L19-L28) is the complete
fastp argument list; it exposes adapter on/off, fixed-count 5′/3′ clipping, poly-G, splitting and
`length_required`. fastp's sliding-window trimmers — `--cut_front`, `--cut_tail`, `--cut_right`, with
`--cut_mean_quality` / `--cut_window_size` — are never emitted and have no parameter. The string
`cut_` does not appear anywhere in the repo. Consequence: **no base is ever removed because of its
quality score**, in any configuration of this pipeline.

**D. `trim_nextseq`'s value is silently discarded, and its comment is wrong.** *(Text fixed in
`trimming.config` and the schema overlay; the value is still only tested for truthiness — see §2.1.)*
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

## 2. Design — opt-in fastp adapter + variable-length quality trimming (2026-09-02)

Supersedes the earlier "Plan A". The ask (plan item 6): *adapter trimming, plus quality-based 3′-end
trimming that inspects the ends of the reads and removes a variable number of bases according to base
quality — not a fixed base count.* fastp already has both; the work is exposing them without letting
fastp do anything else on the side.

### 2.1 One rule: fastp changes only what a parameter asks for

Every fastp behaviour that alters or drops reads now sits under a parameter.
[`conf/modules/trimming.config`](../../conf/modules/trimming.config) emits:

| Behaviour | fastp default | Emitted unless … | Status |
|---|---|---|---|
| Adapter trimming | on | `--disable_adapter_trimming` unless `trim_adapter` (alias `trim_fastq`) | upstream |
| Read-level quality filter (`-q 15 -u 40 -n 5`) | on | `--disable_quality_filtering` when `filter_quality = false` (default **true**) | **new switch, upstream default kept** |
| Poly-G tail trimming | auto by read name | `--trim_poly_g` when `trim_nextseq` ≠ 0; nothing at 0 (fastp's read-name auto-detection applies) | upstream |
| Sliding-window quality trimming | off | `--cut_tail`/`--cut_right`/`--cut_front` only with `trim_quality_3prime` / `trim_quality_5prime` | **new** |
| Length filter | `-l 15` | `--length_required N` always (upstream default 15 = fastp default) | upstream |

Consequences:

- **`--trim_adapter` (= upstream's `--trim_fastq`, kept as alias) keeps upstream sarek 3.5.1 semantics** (user decision 2026-09-02): adapter trimming
  *plus* fastp's read-level quality filter, which drops a pair when either mate has >40 % of bases
  below Q15 or >5 N. What changed is that the filter is now named and switchable —
  `--filter_quality false` passes `--disable_quality_filtering` — and its help text states what it
  removes. The same holds for a `split_fastq > 0` run with trimming off (finding B): fastp still filters
  there, exactly as upstream, but the schema now says so and gives the switch.
- **No divergence from upstream sarek remains** (user decision 2026-09-04, poly-G parity): at
  `trim_nextseq = 0` nothing is passed, so fastp switches poly-G trimming on by itself when the first
  read name carries a NextSeq/NovaSeq instrument prefix and leaves other data alone. Verified
  empirically that this auto-detection is **read-name driven**: the same G-tailed reads are trimmed
  under `@A00123:…` names and untouched under `@SRR…` names (both pinned in
  `tests/fastp_preprocessing.nf.test`). On SRA-renamed data such as the ottilie set the auto-detection
  never fires, so `--trim_nextseq 1` is the way to force it there. The parameter's help text now says
  exactly this; earlier it claimed Trim Galore's `--nextseq=X` quality semantics.
- **The gate** at [`workflows/sarek/main.nf`](../../workflows/sarek/main.nf) is
  `trim_adapter || trim_fastq || trim_quality_3prime || trim_quality_5prime || split_fastq > 0` — without
  the quality terms, a quality-only request on an ALE config would instantiate nothing and look like "trimming ran and changed
  nothing".

### 2.2 Parameters

The user-facing organisation is **four steps in run order** — step 0 UMI consensus (fgbio, hidden),
then fastp steps 1 adapter trimming · 2 quality trimming per read end · 3 read filtering — documented
in [`docs/usage/read_preprocessing.md`](../usage/read_preprocessing.md). The schema group is retitled
"Read preprocessing", every parameter's description starts with its step, and the entries are ordered
by step (overlay `group_overrides` / `property_order`). Nine new parameters, all off by default except
step 3's filter (upstream parity):

| Step | Parameter | Default | fastp | Notes |
|---|---|---|---|---|
| 1 | `trim_adapter` | `false` | adapter trimming on | the ALE name for upstream's `trim_fastq`, which stays as a **hidden deprecated alias** (same behaviour, startup warning) so upstream-shaped params files keep working |
| 1 | `adapter_sequence`, `adapter_sequence_r2` | `null` | `--adapter_sequence[_r2]` | only with step 1; empty = auto-detect |
| 2 | `trim_quality_3prime` | `null` | `--cut_tail` / `--cut_right` | enum `tail \| right`; nf-schema rejects anything else (verified). `right` supersedes `tail` in fastp, hence one choice, not two booleans |
| 2 | `trim_quality_5prime` | `false` | `--cut_front` | combinable with the 3′ mode (Trimmomatic `LEADING` + `TRAILING`) |
| 2 | `trim_quality_mean`, `trim_quality_window` | 20, 4 | `--cut_mean_quality`, `--cut_window_size` | shared by both ends; emitted only when an end is on |
| 3 | `filter_quality` | `true` | `false` → `--disable_quality_filtering` | fastp's read-level drop filter, on by default as upstream; a failing read drops its mate |
| 3 | `filter_quality_phred`, `filter_quality_percent` | 15, 40 | `-q`, `-u` | emitted explicitly whenever the filter is on, so `.command.sh` states the thresholds |

Visible alongside them: the upstream fixed-count clips (`clip_r*`, `three_prime_clip_r*`) as step 2's
fixed-count alternative (user choice: keep visible), `trim_nextseq`, `length_required`, `save_trimmed`.
Hidden, still functional: step 0's UMI parameters, `save_split_fastqs`, the `trim_fastq` alias.
Deliberately not added: `-c` overlap correction, an exposed N-base limit.

### 2.3 Rendered argument sets

From a throwaway workflow that runs the real `FASTP` module with the pipeline's `trimming.config` on a
4 000-read pair (G-tailed, NovaSeq-style names). Every set was accepted by fastp 0.23.4; the module adds
`--detect_adapter_for_pe` itself.

| Parameters | Rendered `ext.args` | Effect on the G-tailed test pair |
|---|---|---|
| (ottilie defaults) | FASTP **not instantiated** | — |
| `--trim_adapter` (or the alias `--trim_fastq`, identical) | `--qualified_quality_phred 15 --unqualified_percent_limit 40 --length_required 15` | as upstream: adapter trimming + read filter (258 pairs dropped); poly-G tails **kept** (mean 114 bp) |
| `--trim_adapter --trim_quality_3prime tail` | `--cut_tail --cut_window_size 4 --cut_mean_quality 20 --qualified_quality_phred 15 --unqualified_percent_limit 40 --length_required 15` | the recommended recipe (§2.5) |
| `--trim_quality_5prime --trim_quality_3prime right --trim_quality_mean 25` | `--disable_adapter_trimming --cut_right --cut_front --cut_window_size 4 --cut_mean_quality 25 …` | both ends, no adapter removal |
| `--trim_adapter --filter_quality false` | `--disable_quality_filtering --length_required 15` | 4000 → 4000 reads, trimming only |
| `--trim_adapter --filter_quality_phred 20 --filter_quality_percent 30` | `… --qualified_quality_phred 20 --unqualified_percent_limit 30 …` | stricter filter: 476 pairs dropped |
| `--trim_adapter --trim_nextseq 20` | `--trim_poly_g …` | poly-G tails removed (mean 98 bp); on NovaSeq-named reads fastp does this at 0 as well |
| `--split_fastq 1000` | `--disable_adapter_trimming --qualified_quality_phred 15 --unqualified_percent_limit 40 --length_required 15 --split_by_lines 4000` | splitter; the read filter applies, as upstream |

### 2.4 What each option does to the ottilie test set

fastp 0.23.4 standalone (the pinned module container) on the 2-sample, 4-chromosome test set — HiSeq
2500, 2 × 100 bp, Nextera (Tn5) library, SRA read names. All rows except M0/M4 use
`--disable_quality_filtering`; length filter 15 unless stated.

| Sample | Mode | Pairs kept | Bases kept | Adapter-bearing reads | Pairs dropped as too short |
|---|---|---|---|---|---|
| CBR110-15-R3a (evolved) | M4 split-only, fastp defaults (= old "no trimming" `split_fastq>0`) | 99.28 % | 99.28 % | — | 0 (25 052 low-quality + 994 too-N **dropped by the read filter**) |
| | M1 adapter only | 100 % | 97.24 % | **11.4 %** (415 760; 10.0 Mb) | 0 |
| | M2 adapter, explicit Nextera sequence | 99.998 % | 97.24 % | 11.4 % (415 808) | 84 |
| | **M5 adapter + `tail` 4/20** | **100 %** | **97.21 %** | 11.4 % | 0 |
| | M7 adapter + `tail` 1/20 (per-base) | 100 % | 97.21 % | 11.4 % | 0 |
| | M6 adapter + `right` 4/20 | 98.11 % | 94.24 % | 11.4 % | 68 706 |
| | M3 adapter + `right` 4/20, length 36 | 96.71 % | 93.51 % | 11.4 % | 119 552 |
| NODRUG-GM2 (parent) | M4 split-only, fastp defaults | 95.79 % | 95.79 % | — | 0 (67 866 + 5 558 **dropped by the read filter**) |
| | M1 adapter only | 100 % | 99.94 % | 0.28 % (4 794) — auto-detection: *unspecified* | 0 |
| | M2 adapter, explicit Nextera sequence | 99.999 % | 99.93 % | 0.42 % (7 347) | 12 |
| | **M5 adapter + `tail` 4/20** | **99.39 %** | **97.69 %** | 0.23 % | 10 712 |
| | M7 adapter + `tail` 1/20 | 99.41 % | 97.85 % | 0.24 % | 10 214 |
| | M6 adapter + `right` 4/20 | 98.05 % | 90.90 % | 0.20 % | 34 034 |
| | M3 adapter + `right` 4/20, length 36 | 96.51 % | 90.08 % | 0.20 % | 60 796 |

Read from the table:

1. **Adapter content is library-specific, not dataset-wide.** The evolved clone (insert peak 135 bp)
   carries Nextera adapter in 11 % of reads — 10 Mb of sequence bwa currently soft-clips (§1.3); the
   parent (insert peak 167 bp) in 0.3 %. Either way removal costs no reads.
2. **fastp's auto-detection is not a given.** It recovered the full Nextera adapters on the evolved clone
   but returned *unspecified* on the parent; overlap analysis still caught most read-through there, and
   naming the sequence explicitly (`adapter_sequence`) found a further 0.15 % of reads. Hence the
   optional parameter; it is not needed for the recipe to work.
3. **The read-level quality filter is not free**: 0.7 % of the evolved clone's pairs and **4.2 %** of the
   parent's are discarded by it under `--trim_fastq` (and under `split_fastq > 0`), as in upstream. It
   stays on by default (user decision: upstream parity) but is now named, documented and switchable
   (`--filter_quality false`).
4. **Fixed-count clips and the quality cut compose, fixed first.** Measured on the G-tailed fixture
   (100 bp + 15 Q2 bases): `--trim_tail1 15` alone → 100 bp, `--cut_tail` alone → 96, both → 95, i.e.
   the clip is applied and the window cut then acts on the shortened read (30-bp clip: 85 / 81). The
   upstream comment claiming the 3′ clip runs *after* quality trimming was wrong and is corrected.
5. **`tail` is the variable-length 3′ trim the ask describes** and is nearly free on good data: on the
   evolved clone (Q30 = 97.7 %) it removes 0.03 % of bases beyond the adapters; on the parent
   (Q30 = 93.3 %) 2.2 % of bases and 0.6 % of pairs (trimmed below 15 bp). Window 4 vs 1 makes no
   practical difference. **`right`** is the Trimmomatic `SLIDINGWINDOW` analogue and 3–4 × more
   aggressive (a mid-read dip removes the remainder): 3–6 % more bases and ~2 % of pairs gone, rising to
   3.5 % with `length_required 36`.

### 2.5 Recommended ALE recipe — and it is not the default

```
--trim_adapter --trim_quality_3prime tail   # window 4, Q20, length_required 15; fastp's read filter on (default)
```

Adapter removal (the Mito soft-clip artefact of §1.3 disappears at source) plus gentle 3′ quality
trimming. With the default `filter_quality = true` fastp also discards its low-quality pairs
(0.7 % / 4.2 % on the test set — M0 vs M1 in §2.4); add `--filter_quality false` for trimming only.
The §2.6 validation run used `--filter_quality false`; the filter's own footprint is measured separately
in §2.4 and does not touch the truth set (all four SNVs sit at 48–149× in the evolved clone). Add `--adapter_sequence CTGTCTCTTATACACATCT`
for Nextera libraries where the auto-detection reports *unspecified*. **All defaults stay off**: the
ottilie configs, the e2e snapshot and the Azure baseline are untouched. Making this the ALE default is
open decision 3 (§4) and belongs with the next deliberate baseline re-cut.

### 2.6 Validation performed (2026-09-02)

- Rendered `ext.args` for seven parameter sets through the real module (§2.3) — flags correct, fastp
  exit 0 each time.
- `-preview` on the ottilie profile: defaults do **not** create `FASTP`; `--trim_quality_3prime tail`
  alone does (gate); `--trim_fastq` still works and prints the deprecation warning;
  `--trim_quality_3prime bogus` fails schema validation before anything runs.
- `bin/apply_schema_overlay.py --check` green; `nf-core pipelines schema lint` reports only the
  pre-existing `split_fastq` `oneOf` complaint (finding H).
- **Full 2-sample run with the §2.5 recipe** (run before the parameter regrouping, as
  `--trim_fastq --trim_quality tail --filter_quality false` (pre-regroup names), which emits the same fastp arguments as
  today's `--trim_adapter --trim_quality_3prime tail --filter_quality false`; with `--generate_reports`; 175/175 tasks, 20 min on the dev VM) compared with the
  untrimmed local test output (`output_ottilie_test/`, 2026-09-01):
  - `FASTP` `.command.sh` carries exactly the §2.3 recipe line; the in-pipeline fastp JSON counts
    (reads, bases, adapter-trimmed reads/bases, too-short pairs) are **identical** to the standalone
    M5 measurement.
  - **Truth set unchanged**: the 4 CBR110-15-R3a SNVs are `PASS` with the same QUAL and the same
    `GT:AD` in both runs (only `INFO/DP` moves by 0–4 reads, from the parent's trimmed pairs); the
    chr I duplication reads `fold_change 1.311` / TIDDIT ploidy 1.311 in both.
  - Joint HC VCF: 100 → 101 records (82 → 83 PASS). The 7 records that differ are all
    homopolymer / low-complexity indels (`C→CA`, `G→GA`, `C→CTTTT…`) plus one 44-bp cassette insertion
    at IV:1279216 that the trimmed alignment represents as two adjacent insertions — the
    read-end-dependent class, no SNV touched.
  - SV: same 12 pass rows and 41 union rows; breakend coordinates at the shared ADH1 star shift by
    1–11 bp (soft-clip boundaries move once adapter tails are gone).
  - CN: `contig_copy_number.csv` fold changes within 0.002; `cn_cohort_full.csv` per-bin fold change
    max |Δ| 0.065 (evolved) / 0.108 (parent), mean < 0.01; the collapsed table loses 2 marginal
    parent-only segments (56 → 54 rows).
  - Alignment: mean mapped read length 100 → 97/98 bp; samtools `error rate` **drops** 3.09e-3 →
    2.33e-3 (parent) and 1.07e-3 → 1.01e-3 (evolved) — the adapter and low-quality tails were the
    mismatches.
  - MultiQC gains the fastp section (14 data tables + plots); no other tree differences.
- Plain `ottilie_e2e` nf-test at defaults, with these changes in the tree: **every deterministic
  output is byte-identical to HEAD's own untrimmed run of 2026-09-01** (`output_ottilie_test/`; joint
  VCF records, all FILTER summaries, all report `tableJson` blobs, every CSV — only `##fileDate`-stamped
  files differ, and those are `.nftignore`d). The test itself reports 6 snapshot mismatches, all
  HaplotypeCaller-filter hashes, and **they are pre-existing**: the committed snapshot was last
  recorded on 2026-08-31 (`d568377`), the `SOR_FS_filter` commit of 2026-09-01 (`4c45fb8`) changed the
  FILTER column of 2 records without re-recording it. Nothing in the trimming change is visible at
  defaults. The snapshot needs its own `--update-snapshot` commit for the SOR_FS change **before** this
  work lands, so the two changes stay separable in the `.snap` history.

### 2.7 Files

`nextflow.config` (nine params) · `nextflow_schema.json` via `conf/schema_overlay.yml` (ALE entries
hand-added to the JSON; overlay allowlist, step-prefixed text overrides, `group_overrides` title and
`property_order` — the last two new in `bin/apply_schema_overlay.py`) · `docs/usage/read_preprocessing.md` ·
`tests/fastp_preprocessing.nf.test` (+ fixture) · `docs/dev-practices/figures/fastq_trimming/`
(schematic + its script) ·
`conf/modules/trimming.config` (policy args) · `workflows/sarek/main.nf` (gate, one token) ·
`SAREK_MODIFICATIONS.md` · `CHANGELOG.md` · `CLAUDE.md`.

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
   settings? If the latter, Plan B collapses to a throwaway comparison script and nothing more lands in
   the pipeline. This should be settled with the team before any module is installed — it is the
   difference between zero files and a permanent second tool with a rebase cost. Note that §2 already
   reproduces Trimmomatic's `ILLUMINACLIP` + `TRAILING`/`SLIDINGWINDOW` + `MINLEN` behaviour.
2. ~~Symmetric or asymmetric quality trimming?~~ **Resolved (§2.2):** one mode at a time via the enum;
   `front` + `tail` in a single run is not representable and was not asked for.
3. **Does the ALE default change?** Everything in §2 is opt-in. Turning `--trim_adapter --trim_quality_3prime tail`
   on by default re-cuts the Azure baseline, re-records the e2e snapshot and re-validates the ottilie
   truth set. §2.4 gives the expected footprint (0–2 % of bases, ≤ 0.6 % of pairs, 11 % of the evolved
   clone's reads shortened).

## 5. Suggested order

1. ~~Fix the pure-bug audit defects (B, D).~~ Done with §2.
2. ~~Expose fastp quality trimming.~~ Done with §2 — validation in §2.6.
3. ~~Add an nf-test over the preprocessing path (**G**).~~ Done: `tests/fastp_preprocessing.nf.test`, a
   `nextflow_process` test of `FASTP` under the pipeline's `trimming.config` on a committed 1 000-pair
   fixture (`tests/fixtures/fastp_*`), one case per step (§2.3 is the table it pins).
4. Settle open decision 1. Only then start Plan B.
5. Decide open decision 3 together with the next baseline re-cut.
