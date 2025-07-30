# NF_ALE Project Notes

## Environment-Specific Configurations

### Apple Silicon (Local Development)
- **Commit**: `cbe4a0bd1d33cb6cd3b5994d12476e1490a5baae`
- **Profile**: `arm,docker`
- **Notes**: Required for Apple Silicon compatibility
- **Limitations**: Some tools like `manta` may not work on ARM

### Azure Linux VM (Production)
- **Profile**: `docker` (standard)
- **All tools supported**: Including `manta`
- **Recommended**: Use original configuration for production deployment

## Deployment Strategy
1. For local Apple Silicon development: Use current ARM-compatible settings
2. For production Azure deployment: Revert Docker profile to remove ARM-specific configurations
3. Test both environments before major releases

## Key Files
- `bin/CENPK_run_sarek.sh`: Main execution script
- `bin/nextflow.config`: Pipeline configuration
- `bin/prepare_input/process_GeneBank/generate_cache/gen_cache.sh`: Cache generation script