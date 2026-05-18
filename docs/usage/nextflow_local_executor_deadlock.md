# Nextflow Local Executor Deadlock

## Problem

When running nf-core/sarek on a single VM with the Nextflow `local` executor,
the pipeline can deadlock during the variant calling stage. The scheduler reports:

```
!! executor local > No more task to compute -- The following nodes are still active:
```

Tasks are queued but none are submitted. The Nextflow Java process stays alive at 0% CPU indefinitely.

## When it happens

This occurs when:
1. **Multiple process types** compete for task slots (e.g., HaplotypeCaller, CNVKit, TIDDIT, ControlFREEC all run in parallel after alignment completes)
2. **`executor.memory`** is barely larger than **`process.memory`**, so only 1 task fits at a time
3. The scheduler cannot resolve which waiting process to run next

**Not affected**: HPC/cloud executors (SLURM, AWS Batch, Azure Batch, Seqera Platform) — these have independent resource pools and don't share a single memory budget.

## Example (Tier 2 run, May 2026)

```groovy
// DEADLOCKED — only 1 task fits (10 / 8 = 1)
executor { memory = '10 GB' }
process  { memory = '8 GB'  }
```

86 samples completed alignment (86/86), but variant calling stalled at 6/86 for
HaplotypeCaller, CNVKit, and TIDDIT. ControlFREEC never started (0/86).
The pipeline sat idle for 4 days before being killed manually.

## Fix

Ensure `executor.memory / process.memory >= 2` so at least 2 tasks can run concurrently:

```groovy
// FIXED — 3 tasks fit (14 / 4 = 3), breaks deadlock
executor { memory = '14 GB' }
process  { memory = '4 GB'  }

// Override for processes that actually need more
withName: 'GATK4_MARKDUPLICATES' { memory = '8 GB' }
withName: 'BWAMEM1_MEM'          { memory = '6 GB' }
withName: 'GATK4_GENOMICSDBIMPORT|GATK4_GENOTYPEGVCFS' { memory = '12 GB' }
```

## How to diagnose

1. Check if the pipeline is idle: `docker ps` shows no containers, `top` shows 0% CPU for the Nextflow Java process
2. Check the log: `grep "No more task to compute" .nextflow.log`
3. The log block lists which process nodes are `ACTIVE` with `port 0: (queue) OPEN` — these have tasks waiting but can't be scheduled

## Key takeaway

Set per-process memory based on **actual peak RSS** (from the execution trace), not worst-case guesses. Most bioinformatics tools on yeast-sized genomes use <2 GB. Over-requesting memory starves the local executor.
