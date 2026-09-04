# Read preprocessing — what happens to reads before alignment

Everything between the samplesheet and bwa-mem, in run order. **The ALE default (since 2026-09-04)
is adapter trimming plus 3′ tail quality trimming**, with fastp's read filter on: `--trim_adapter
--trim_quality_3prime tail`. Each step is its own switch; for reads exactly as sequenced set
`--trim_adapter false` and leave `trim_quality_3prime` unset, and fastp then runs only if step 2 is set
or `split_fastq > 0` (FastQC reports on the raw reads either way). Parameter group in the launch form /
`--help`: **Read preprocessing**.

```
raw FASTQ → FastQC (report only)
          → step 0  UMI consensus            fgbio      only with --umi_read_structure
          → fastp:  step 1  adapter trimming             --trim_adapter
                    step 2  fixed-count clipping         --clip_r1/r2, --three_prime_clip_r1/r2
                    step 3  quality trimming per end     --trim_quality_3prime / --trim_quality_5prime
                    step 4  read filtering               --filter_quality (on), --length_required
          → bwa-mem
```

![One read of a pair through the preprocessing steps: as sequenced, adapter trimming, fixed-count clipping, quality trimming, read filtering; the ALE default path in colour](../dev-practices/figures/fastq_trimming/read_preprocessing_steps.svg)

*One read through the fastp steps in run order; coloured = the ALE default path, grey = optional. Source: `docs/dev-practices/figures/fastq_trimming/make_read_journey.py`.*

The default recipe (see [Defaults and the baseline](#defaults-and-the-baseline)):

```
--trim_adapter --trim_quality_3prime tail
```

## Step 0 — UMI consensus (fgbio)

Only when `--umi_read_structure` is given: reads carrying unique molecular identifiers are grouped
(`--group_by_umi_strategy`) and collapsed into consensus reads, which then continue into fastp. This
step is independent of the fastp steps below. **No ALE library uses UMIs**, so both parameters are
hidden in the launch form (still accepted from a params file).

## Step 1 — Adapter trimming

`--trim_adapter` runs fastp adapter removal. No adapter sequence is required: paired reads are trimmed
wherever the two mates overlap, and fastp infers the adapter sequence from the data for pairs that do
not overlap (`--detect_adapter_for_pe`). On the ottilie test set that found Nextera adapter in 11 % of
the evolved clone's reads and trimmed 10 Mb of sequence that bwa would otherwise soft-clip.

| Parameter | Default | Use |
|---|---|---|
| `trim_adapter` | off | the switch. `trim_fastq` (upstream sarek's name) is a deprecated alias with the same behaviour. |
| `adapter_sequence`, `adapter_sequence_r2` | auto | name the kit's adapter explicitly when fastp reports `unspecified` (low-adapter libraries): Nextera `CTGTCTCTTATACACATCT`, TruSeq R1 `AGATCGGAAGAGCACACGTCTGAACTCCAGTCA` / R2 `AGATCGGAAGAGCGTCGTGTAGGGAAAGAGTGT`. |
| `trim_nextseq` | 0 | any non-zero value forces poly-G tail trimming (two-colour NextSeq/NovaSeq chemistry). At 0 fastp decides by itself from the read names, as in upstream sarek: on when the first read name has a NextSeq/NovaSeq prefix (`@A00123:…`), off otherwise — so SRA-renamed data (`@SRR…`) is only trimmed if you set this. |

Step 1 behaves as upstream sarek's `--trim_fastq`: fastp's read-level quality filter (step 4) is on
unless you turn it off.

## Step 2 — Fixed-count clipping

Removes a set number of bases from a read end regardless of quality: `clip_r1`, `clip_r2` from the
5′ end and `three_prime_clip_r1`, `three_prime_clip_r2` from the 3′ end (fastp `--trim_front*` /
`--trim_tail*`). Use it only when you know the exact cycles to drop, e.g. a known bad last cycle;
otherwise leave it at 0 and let step 3 decide per read. fastp applies these clips **before** the
quality cut, so the two compose: clip the cycles you know are bad, then let the window cut adapt to
what remains. Not part of the ALE recipe.

## Step 3 — Quality trimming, per read end

Trims a **variable** number of low-quality bases from a read end — no fixed base count (that is step 2).
fastp's order between this cut and step 1's adapter detection is its own; what is guaranteed is that
step 2 runs before this cut and step 4 evaluates the fully trimmed read. fastp
slides a window (`trim_quality_window`, default 4 bases) and trims where the window's mean quality is
below `trim_quality_mean` (default Q20).

| Parameter | Default | Use |
|---|---|---|
| `trim_quality_3prime` | off | `tail`: walk in from the 3′ end, stop at the first window that passes (Trimmomatic `TRAILING`). `right`: scan 5′→3′, cut at the first window that fails and everything after it (Trimmomatic `SLIDINGWINDOW`). |
| `trim_quality_5prime` | off | same as `tail` from the 5′ end (fastp `--cut_front`, Trimmomatic `LEADING`); fastp has no second 5′ method. Combinable with the 3′ mode. |
| `trim_quality_mean`, `trim_quality_window` | 20, 4 | shared by both ends. Window 1 makes it per-base. |

<details>
<summary><b>Schematic: what each mode keeps</b> (click to expand)</summary>

![Schematic of the tail, right and front quality-trimming modes on one read](../dev-practices/figures/fastq_trimming/trim_quality_modes.svg)

`tail` removes only the 3′ decay; `right` cuts at the first dip and loses everything after it; the 5′
mode removes only a low start. Source: `docs/dev-practices/figures/fastq_trimming/make_schematic.py`.

</details>

Which 3′ mode: `tail` is the gentle choice and matches Illumina's 3′ quality decay. On the ottilie
test set it removed 0.03 % (evolved clone) to 2.2 % (parent) of bases beyond the adapters. `right` is
3–4 × more aggressive because a single mid-read dip discards the rest of the read — the parent sample
has a systematic dip at position 58 that truncates 10 % of its reads under `right`. Measurements:
[`fastq_preprocessing_audit.md` §2.4](../dev-practices/fastq_preprocessing_audit.md#24-what-each-option-does-to-the-ottilie-test-set).

## Step 4 — Read filtering

Evaluated on the read **after** steps 1–3. A pair is discarded when either mate fails.

| Parameter | Default | Use |
|---|---|---|
| `filter_quality` | **on** | fastp's read-level quality filter: discard a read when more than `filter_quality_percent` (40) of its bases are below `filter_quality_phred` (Q15), or it has more than 5 N. On by default whenever fastp runs, exactly as in upstream sarek. `--filter_quality false` keeps every read (trimming only). |
| `filter_quality_phred`, `filter_quality_percent` | 15, 40 | the two thresholds (fastp `-q`, `-u`). |
| `length_required` | 15 | discard reads shorter than this after trimming (fastp `-l`). Always applied when fastp runs. |

On the ottilie test set the quality filter removes 0.7 % (evolved clone) to 4.2 % (parent) of pairs.
The per-sample counts are in `reports/fastp/<sample>/*.fastp.json` under `filtering_result`, and in
the MultiQC fastp section.

## Not preprocessing steps

- **Parallelisation** — `split_fastq` (main options group, hidden; every ALE profile sets 0) shards
  FASTQs through the same fastp process. A non-zero value runs fastp even with steps 1–3 off; step 4's
  filter then still applies unless `--filter_quality false`.
- **Outputs** — `save_trimmed` publishes the trimmed FASTQs under `preprocessing/fastp/<sample>/`;
  `save_split_fastqs` (hidden) the shards.

## Defaults and the baseline

Since 2026-09-04 the default recipe is `--trim_adapter --trim_quality_3prime tail` with step 4's
filter on; step 2 and the 5′ cut stay off. Every ALE profile inherits it. Consequences:

- The **verified Azure Batch baseline** (`az://aletest/ottilie-azurebatch-out/`) and the Seqera runs
  compared against it were produced with **no preprocessing**, so byte-comparison against them is
  invalidated until the baseline is re-cut with the new default (a Seqera run per the RUNBOOK's
  local-vs-Seqera procedure). Until then, treat trimming as a known difference class.
- The e2e snapshot was re-recorded with the default on (2026-09-04): the 4 truth SNVs and the chr I
  duplication are recovered as before; the 4-sample pilot's truth-set sensitivity (41/42) is to be
  re-confirmed together with the baseline re-cut.
- Validation of the recipe on the 2-sample truth set:
  [`fastq_preprocessing_audit.md` §2.6](../dev-practices/fastq_preprocessing_audit.md#26-validation-performed-2026-09-02).
