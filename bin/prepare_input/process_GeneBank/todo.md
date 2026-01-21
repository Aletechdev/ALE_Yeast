# GenBank Processing TODO

## Ogataea polymorpha GenBank Processing Issues (2025-08-27)

### ✅ Successfully Completed:
- FASTA conversion: 7 sequences created from GenBank
- GFF3 conversion: 8,374 features extracted
- Organism info extraction: Fixed name parsing (removed leading underscores)
- Docker-based processing pipeline working
- **Chromosome name mismatch: FIXED** - GFF3 now strips `.1` version suffix to match FASTA
- **SnpEff database build: FIXED** - Successfully generates `snpEffectPredictor.bin`

### ✅ All Issues Resolved (2026-01-21)

Verified output in `assets/genebank/processed/`:
- FASTA chromosome names: `AECK01000001` (no version suffix)
- GFF3 chromosome names: `AECK01000001` (matching FASTA)
- SnpEff cache: Successfully built with all 7 chromosome sequence files

### ⚠️ Minor Warnings (Non-blocking):
- BioPython "malformed locus line" warnings - cosmetic only
- SnpEff transcript/gene structure warnings - expected for GenBank conversion

### 📁 Generated Files Location:
```
assets/genebank/processed/
├── ogataea_polymorpha.fasta      ✅
├── ogataea_polymorpha.gff3       ✅
├── organism_info.sh              ✅
├── PROCESSING_SUMMARY.md         ✅
└── snpeff_cache/                 ✅
    ├── ogataea_polymorpha/       ✅ (snpEffectPredictor.bin present)
    └── data/ogataea_polymorpha/  ✅
```

### 🎯 Ready for Pipeline Integration
Use these parameters in nextflow:
```
--fasta        assets/genebank/processed/ogataea_polymorpha.fasta
--snpeff_cache assets/genebank/processed/snpeff_cache
--snpeff_db    ogataea_polymorpha
```
