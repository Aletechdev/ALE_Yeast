# GenBank Processing TODO

## Ogataea polymorpha GenBank Processing Issues (2025-08-27)

### ✅ Successfully Completed:
- FASTA conversion: 7 sequences created from GenBank
- GFF3 conversion: 8,374 features extracted
- Organism info extraction: Fixed name parsing (removed leading underscores)
- Docker-based processing pipeline working

### ❌ Critical Issue: SnpEff Database Build Failed
**Problem:** Chromosome name mismatch between files
- **GFF3 uses:** `AECK01000001.1` (with .1 version suffix)  
- **FASTA uses:** `AECK01000001` (without version suffix)
- **Error:** "Most Exons do not have sequences! Please check that chromosome names in both files match"

### 🔧 Required Fix:
1. **Standardize chromosome names** - Remove `.1` suffixes from GFF3 to match FASTA format
2. **Update GFF3 processing** in `process_genbank_auto.sh` to strip version numbers
3. **Re-run SnpEff cache generation** after fix

### ⚠️ Minor Warnings (Non-blocking):
- BioPython "malformed locus line" warnings - cosmetic only
- SnpEff transcript/gene structure warnings - expected for GenBank conversion

### 📁 Generated Files Location:
```
/home/azureuser/Docs/ALE_nextflow/data/Yeast_methanol_RWTH/Ogataea_polymorpha_NCYC495/processed/
├── ogataea_polymorpha.fasta ✅
├── ogataea_polymorpha.gff3 ✅ (needs chromosome name fix)
└── snpeff_cache/ ❌ (failed due to name mismatch)
```

### 🎯 Next Actions:
1. Fix chromosome naming consistency in GFF3 generation
2. Re-run SnpEff cache generation 
3. Test with Sarek pipeline integration