#!/usr/bin/env bash
# Download Ottilie et al. supplementary data files (truth set for benchmarking).
#
# Source: https://pmc.ncbi.nlm.nih.gov/articles/PMC8837787/
# Paper:  Ottilie et al., Commun Biol 5:128 (2022)
#
# Usage:
#   cd <repo_root>
#   bash docs/benchmarking/ottilie_xenobiotic_ale/01_data_retrieval/download_truth_set.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../../.." && pwd)"
OUTDIR="$REPO_ROOT/data/ottilie/supplementary"
mkdir -p "$OUTDIR"

BASE_URL="https://pmc.ncbi.nlm.nih.gov/articles/instance/8837787/bin"

# Supplementary Data 4: 1,405 mutations (1,286 SNVs + 119 INDELs) — primary truth set
# Supplementary Data 5: 24 CNVs (11 aneuploidies + 13 intrachromosomal amplifications)
# Supplementary Data 7: CRISPR/Cas9 validation (61 tested, 45 confirmed causal)
declare -A FILES=(
    ["sup_4_42003_2022_3076_MOESM6_ESM.xlsx"]="42003_2022_3076_MOESM6_ESM.xlsx"
    ["sup_5_42003_2022_3076_MOESM7_ESM.xlsx"]="42003_2022_3076_MOESM7_ESM.xlsx"
    ["sup_7_42003_2022_3076_MOESM9_ESM.xlsx"]="42003_2022_3076_MOESM9_ESM.xlsx"
)

TOTAL=${#FILES[@]}
COUNT=0
for LOCAL_NAME in "${!FILES[@]}"; do
    REMOTE_NAME="${FILES[$LOCAL_NAME]}"
    COUNT=$((COUNT + 1))
    echo "[$COUNT/$TOTAL] $LOCAL_NAME"

    if [[ -f "$OUTDIR/$LOCAL_NAME" ]]; then
        echo "  Already exists, skipping."
        continue
    fi

    curl -fSL -o "$OUTDIR/$LOCAL_NAME" "$BASE_URL/$REMOTE_NAME"
    echo "  Downloaded: $(ls -lh "$OUTDIR/$LOCAL_NAME" | awk '{print $5}')"
done

echo ""
echo "All $TOTAL truth set files in: $OUTDIR"
ls -lh "$OUTDIR"/sup_*.xlsx
