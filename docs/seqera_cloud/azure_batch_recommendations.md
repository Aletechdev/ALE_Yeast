# Azure Batch VM Size Recommendations for nf-core/sarek

## Official nf-core Sarek Documentation

### Default Configuration

**nf-core/sarek (all versions including 3.5.1) uses Azure Batch Ddv4-series VMs by default.**

The official Azure Batch profile (`azurebatch`) in nf-core/configs includes the `azurebatch_pools_Ddv4.config` configuration file.

### Ddv4 Pool Configuration

The official nf-core/sarek Azure Batch configuration defines **four compute pools** with escalating capacity:

| Pool Label | VM Type | vCPUs | Memory | Use Case |
|-----------|---------|-------|--------|----------|
| `process_low` | Standard_D8d_v4 | 8 | 32 GB | Small/quick processes |
| `process_medium` | Standard_D16d_v4 | 16 | 64 GB | Alignment, variant calling |
| `process_high` | Standard_D32d_v4 | 32 | 128 GB | Multi-sample operations |
| `process_high_memory` | Standard_D64d_v4 | 64 | 256 GB | Memory-intensive operations |

### Auto-Scaling Configuration

- **Initial VM count per pool**: 2 instances
- **Maximum VM count per pool**:
  - Standard pools: 20 instances
  - High-memory pool: 10 instances
- **Scaling enabled**: Dynamic auto-scaling manages pool size based on pending tasks

### Important Note

> "You might need to adjust vmCount and maxVmCount depending on your Batch account quotas."

This is critical for Azure subscription planning. Standard Azure Batch accounts have quota limits per region and VM type.

---

## Comparison: nf-core Official vs Your Current Setup

### Your Current Configuration

**File**: `/home/azureuser/Docs/ALE_nextflow/bin/nextflow.config`

Your `azureD4as` profile uses:
- **Executor**: Local (not Azure Batch)
- **VM Type**: D4as_v5 series (4 vCPUs, 14 GB RAM)
- **Default process memory**: 8 GB
- **Default process CPUs**: 2 cores
- **Maximum time**: 72 hours

```nextflow
executor {
  name = 'local'
  cpus = 4
  memory = '14 GB'
}

process {
  memory = '8 GB'
  cpus = 2
  time = '24h'
  resourceLimits {
    cpus = 4
    memory = '14 GB'
    time = '72h'
  }
}
```

### nf-core Official Configuration

**File**: `conf/pipeline/sarek/azurebatch_pools_Ddv4.config` (in nf-core/configs)

Official configuration uses:
- **Executor**: Azure Batch (distributed)
- **VM Types**: Ddv4-series (8-64 vCPUs, 32-256 GB RAM)
- **Pool-based routing**: Tasks assigned by label (process_low/medium/high/high_memory)
- **Auto-scaling**: Dynamic VM provisioning

---

## Key Differences

### 1. Executor Model

| Aspect | Your Setup | Official nf-core |
|--------|-----------|------------------|
| **Type** | Local executor | Azure Batch executor |
| **Parallelism** | Limited by VM capacity | Unlimited, auto-scaled |
| **Scaling** | Manual (VM resize) | Automatic |
| **Cost** | Fixed (VM always running) | Dynamic (pay per task) |

### 2. Resource Strategy

**Your approach** (Conservative):
- Single D4as_v5 VM as bottleneck
- Fixed resource allocation
- Suitable for: Sequential workflows or testing
- Limitation: Cannot parallelize large workloads

**Official approach** (Scalable):
- Multiple pool tiers
- Automatic task routing by resource needs
- Suitable for: Large-scale genome analysis
- Benefit: Cost-efficient scaling (idle pools shrink)

### 3. Memory Per Process

| Tool | Your Config | Recommended (Low) | Recommended (Medium) |
|------|------------|-------------------|----------------------|
| BWA | 4 cores × 8 GB = 32 GB | 8 cores × 4 GB = 32 GB | 16 cores × 4 GB = 64 GB |
| GATK Mutect2 | 4 cores × 14 GB = 56 GB | 8 cores × 4 GB = 32 GB | 16 cores × 4 GB = 64 GB |
| HaplotypeCaller | Default from base.config | ~4 GB per core (low pool) | ~4 GB per core (medium pool) |

---

## Migration Path: Local to Azure Batch

### Option 1: Minimal Change (Recommended for production)

Use official nf-core Azure Batch profile:

```bash
# Instead of:
nextflow run nf-core/sarek -profile azureD4as,docker ...

# Use:
nextflow run nf-core/sarek -profile azurebatch,docker \\
  --az_location westus2 \\
  --batch_name your_batch_account \\
  --batch_key your_batch_key \\
  --storage_name your_storage_account \\
  --storage_key your_storage_key
```

### Option 2: Enhanced Local Configuration (Testing)

Keep local executor but align resource requests with Ddv4 pools:

```nextflow
profiles {
  azureD4asEnhanced {
    process {
      // Align with process_medium tier expectations
      cpus = 4
      memory = '16 GB'

      withLabel: 'process_low' {
        cpus = 2
        memory = '8 GB'
      }

      withLabel: 'process_medium' {
        cpus = 4
        memory = '16 GB'
      }

      withLabel: 'process_high' {
        cpus = 8
        memory = '32 GB'
      }
    }
  }
}
```

### Option 3: Hybrid (Advanced)

Use Azure Batch for compute-intensive tasks, local for testing:

```bash
# Testing with local D4as
nextflow run nf-core/sarek -profile azureD4as,docker -resume

# Production with Azure Batch
nextflow run nf-core/sarek -profile azurebatch,docker
```

---

## Important Considerations

### Azure Batch Setup Requirements

Before switching to Azure Batch profile, ensure:

1. **Azure Batch Account**: Created and active
   - Verify quotas for Ddv4 series (especially D32d_v4 and D64d_v4)
   - Standard quota: 20 vCPU max (may need increase for D32/D64)

2. **Azure Storage Account**: For input/output files
   - SAS token generation (48-72 hour validity for long runs)
   - Blob containers for working directory

3. **Nextflow Configuration**:
   - Install/use nf-core/configs repository
   - Configure Azure credentials (batch key, storage key/SAS)

### Cost Implications

**D4as_v5 (Your current)**:
- Single VM running 24/7: ~$0.35/hour ≈ $255/month

**Azure Batch Ddv4 with auto-scaling**:
- D8d_v4 on-demand: ~$0.35/hour
- D16d_v4 on-demand: ~0.69/hour
- D32d_v4 on-demand: ~1.39/hour
- D64d_v4 on-demand: ~2.77/hour
- Idle pools: $0 (auto-scale down)

**Annual cost comparison**:
- D4as_v5 (fixed): ~$3,000/year
- Azure Batch (variable): $0-2,500/year (depends on usage)

### Quota Considerations for Your Experiments

For 363 yeast ALE clones (from ottilie_benchmark):
- **Alignment phase**: ~50 parallel BWA jobs = 400 vCPUs needed
  - Ddv4 pools can scale to 800+ vCPUs total
  - May require quota increase from standard 20→64 vCPU limit

- **Variant calling phase**: ~50 parallel HaplotypeCaller = 400+ GB RAM
  - Distributed across medium/high pools automatically
  - More efficient than single D4as VM

---

## Recommendations

### For Current Testing (D4as_v5)
✓ Continue using azureD4as profile for:
- Small sample validation
- Pipeline debugging
- Quick iteration cycles

### For Production (363 Clones)
✓ Migrate to Azure Batch azurebatch profile:
- Parallelization needed for 363 samples
- Cost-efficient with auto-scaling
- Follows nf-core best practices
- Easier horizontal scaling

### Resource Tuning Strategy
1. **Start with official Ddv4 config** (proven by nf-core community)
2. **Monitor actual usage** via Azure Batch analytics
3. **Adjust pool counts/sizes** based on your quota and budget
4. **Consider spot instances** for 70% cost savings (add to config)

---

## References

- [nf-core/configs: Azure Batch Profile](https://github.com/nf-core/configs/blob/master/docs/azurebatch.md)
- [nf-core/sarek: Usage Documentation](https://nf-co.re/sarek/3.5.1/)
- [nf-core/sarek: Sarek.config](https://github.com/nf-core/configs/blob/master/pipeline/sarek.config)
- [Azure Batch: VM Sizes Overview](https://learn.microsoft.com/en-us/azure/virtual-machines/sizes-general)
- [Azure Dv4 Series: Technical Specifications](https://learn.microsoft.com/en-us/azure/virtual-machines/dv4-dsv4-series)

---

## Summary Table

| Factor | Your Setup (D4as_v5) | nf-core Azure Batch (Ddv4) |
|--------|----------------------|---------------------------|
| **Default VM** | Single D4as_v5 | Auto-scaled pool |
| **Max Parallelism** | Limited by 4 vCPUs | Scales to 60+ vCPUs |
| **Memory/Core** | 3.5 GB/core | 4 GB/core (aligned) |
| **Auto-scaling** | Manual | Automatic |
| **Suitable for** | Testing <10 samples | Production 100+ samples |
| **Cost (annual)** | ~$3,000 fixed | ~$0-2,500 variable |
| **Setup Complexity** | Minimal | Moderate |

