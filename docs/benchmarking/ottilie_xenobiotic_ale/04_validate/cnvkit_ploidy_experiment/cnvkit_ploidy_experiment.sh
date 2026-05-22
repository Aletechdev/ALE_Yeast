#!/usr/bin/env bash
# CNVKit Ploidy Experiment: How does --ploidy affect CN reporting?
#
# Runs cnvkit.py call + export vcf with ploidy=1,2,3 on the 4 Ottilie
# pilot samples, using the existing .cns segmentation files.
#
# The upstream steps (batch, coverage, fix, reference, segment) do NOT
# accept --ploidy. Only `call` and `export vcf` do. So the log2 ratios
# and segmentation are ploidy-agnostic — we just re-run the final two
# steps with different ploidy values.
#
# Pipeline commands (from conf/modules/cnvkit.config):
#   CNVKIT_CALL:          cnvkit.py call $cns --ploidy ${meta.ploidy}
#   CNVKIT_CALL germline: cnvkit.py call $cns --filter ci --ploidy ${meta.ploidy}
#   CNVKIT_EXPORT:        cnvkit.py export vcf --ploidy ${meta.ploidy} $cns
#   CNVKIT_BATCH:         cnvkit.py batch ... --method wgs  (no --ploidy)
#
# Usage:
#   bash docs/benchmarking/ottilie_xenobiotic_ale/cnvkit_ploidy_experiment.sh
#
# Requires: docker (cnvkit 0.9.10 image), python3
#
# Date: 2026-05-21

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
INPUT_DIR="${REPO_ROOT}/output_ottilie/variant_calling/cnvkit"
OUTPUT_DIR="${REPO_ROOT}/docs/benchmarking/ottilie_xenobiotic_ale/cnvkit_ploidy_experiment"
CNVKIT_IMAGE="quay.io/biocontainers/cnvkit:0.9.10--pyhdfd78af_0"
SAMPLES=("CBR110-15-R3a" "Carmaphycin-R9-2" "Doxorubicin16-R2b" "NODRUG-GM2")
PLOIDIES=(1 2 3)

mkdir -p "${OUTPUT_DIR}"

echo "============================================================"
echo "CNVKit Ploidy Experiment"
echo "============================================================"
echo "Input:   ${INPUT_DIR}"
echo "Output:  ${OUTPUT_DIR}"
echo "Image:   ${CNVKIT_IMAGE}"
echo "Samples: ${SAMPLES[*]}"
echo "Ploidies: ${PLOIDIES[*]}"
echo ""

# ── Step 1: Run cnvkit.py call + export vcf for each ploidy ──────

for sample in "${SAMPLES[@]}"; do
    cns="${INPUT_DIR}/${sample}/${sample}.md.cns"
    if [ ! -f "${cns}" ]; then
        echo "WARN: ${cns} not found, skipping ${sample}"
        continue
    fi

    for ploidy in "${PLOIDIES[@]}"; do
        outdir="${OUTPUT_DIR}/${sample}/ploidy${ploidy}"
        mkdir -p "${outdir}"

        echo "── ${sample} ploidy=${ploidy} ──"

        # cnvkit.py call: assigns integer CN from log2 segments
        docker run --rm \
            -v "${INPUT_DIR}/${sample}:/input:ro" \
            -v "${outdir}:/output" \
            "${CNVKIT_IMAGE}" \
            cnvkit.py call "/input/${sample}.md.cns" \
                --ploidy "${ploidy}" \
                -o "/output/${sample}.call.cns"

        # cnvkit.py export vcf: converts .call.cns to VCF
        docker run --rm \
            -v "${outdir}:/data" \
            "${CNVKIT_IMAGE}" \
            cnvkit.py export vcf "/data/${sample}.call.cns" \
                --ploidy "${ploidy}" \
                -o "/data/${sample}.cnvcall.vcf"

        # Quick stats (use header to find cn column — ploidy=3 adds ci_hi/ci_lo)
        total_segs=$(tail -n +2 "${outdir}/${sample}.call.cns" | wc -l)
        cn_col=$(head -1 "${outdir}/${sample}.call.cns" | tr '\t' '\n' | grep -n '^cn$' | cut -d: -f1)
        non_baseline=$(awk -F'\t' -v col="${cn_col}" 'NR>1 && $col!=2' "${outdir}/${sample}.call.cns" | wc -l)
        vcf_del=$(grep -c '<DEL>' "${outdir}/${sample}.cnvcall.vcf" 2>/dev/null || true)
        vcf_dup=$(grep -c '<DUP>' "${outdir}/${sample}.cnvcall.vcf" 2>/dev/null || true)
        echo "  .call.cns: ${total_segs} segments, ${non_baseline} non-baseline (cn!=2)"
        echo "  VCF: DEL=${vcf_del:-0} DUP=${vcf_dup:-0}"
    done
    echo ""
done

# ── Step 2: Generate comparison report ───────────────────────────

REPORT="${OUTPUT_DIR}/ploidy_comparison.md"

python3 - "${OUTPUT_DIR}" "${REPORT}" << 'PYEOF'
import sys
from pathlib import Path

output_dir = Path(sys.argv[1])
report_path = Path(sys.argv[2])
samples = ["CBR110-15-R3a", "Carmaphycin-R9-2", "Doxorubicin16-R2b", "NODRUG-GM2"]
ploidies = [1, 2, 3]

lines = []
lines.append("# CNVKit Ploidy Experiment Results\n")
lines.append("**Date**: 2026-05-21\n")
lines.append("**Input**: Ottilie pilot `.md.cns` segmentation files (ploidy-independent)\n")
lines.append("**Varied**: `cnvkit.py call --ploidy N` + `cnvkit.py export vcf --ploidy N`\n")
lines.append("**Image**: `quay.io/biocontainers/cnvkit:0.9.10--pyhdfd78af_0`\n")
lines.append("")
lines.append("## Key question")
lines.append("")
lines.append("CNVKit upstream steps (batch → coverage → fix → segment) have **no --ploidy flag**.")
lines.append("Only `call` and `export vcf` accept it. How does ploidy change the CN integer")
lines.append("assignment and VCF output for the same underlying log2 ratios?\n")
lines.append("")

for sample in samples:
    lines.append(f"## {sample}\n")

    # Collect .call.cns data for each ploidy
    all_chroms = []  # preserve order from file
    seen_chroms = set()
    cns_data = {}
    for ploidy in ploidies:
        cns_path = output_dir / sample / f"ploidy{ploidy}" / f"{sample}.call.cns"
        cns_data[ploidy] = {}
        if not cns_path.exists():
            continue
        with open(cns_path) as f:
            header = f.readline().strip().split('\t')
            col = {name: i for i, name in enumerate(header)}
            for line in f:
                p = line.strip().split('\t')
                chrom = p[col['chromosome']]
                if chrom not in seen_chroms:
                    all_chroms.append(chrom)
                    seen_chroms.add(chrom)
                if chrom not in cns_data[ploidy]:
                    cns_data[ploidy][chrom] = []
                cns_data[ploidy][chrom].append({
                    'start': int(p[col['start']]), 'end': int(p[col['end']]),
                    'log2': float(p[col['log2']]), 'cn': int(p[col['cn']]),
                    'depth': float(p[col['depth']])
                })

    # Collect VCF data for each ploidy
    vcf_data = {}
    for ploidy in ploidies:
        vcf_path = output_dir / sample / f"ploidy{ploidy}" / f"{sample}.cnvcall.vcf"
        vcf_data[ploidy] = []
        if not vcf_path.exists():
            continue
        with open(vcf_path) as f:
            for line in f:
                if line.startswith('#'):
                    continue
                p = line.strip().split('\t')
                info = dict(kv.split('=', 1) for kv in p[7].split(';') if '=' in kv)
                fmt = dict(zip(p[8].split(':'), p[9].split(':')))
                vcf_data[ploidy].append({
                    'chrom': p[0], 'pos': int(p[1]),
                    'end': int(info.get('END', 0)),
                    'svtype': info.get('SVTYPE', '?'),
                    'cn': fmt.get('CN', None),
                    'gt': fmt.get('GT', '?'),
                    'fold_change_log': float(info.get('FOLD_CHANGE_LOG', 0)),
                })

    # Table 1: .call.cns CN comparison — ALL segments
    lines.append("### .call.cns — CN by ploidy (all segments)\n")
    lines.append("| Chromosome | log2 | depth | cn (p=1) | cn (p=2) | cn (p=3) |")
    lines.append("|------------|------|-------|----------|----------|----------|")

    if 1 in cns_data and cns_data[1]:
        for chrom in all_chroms:
            segs_p1 = cns_data.get(1, {}).get(chrom, [])
            for seg in segs_p1:
                cn_vals = []
                for pl in ploidies:
                    matching = [s for s in cns_data.get(pl, {}).get(chrom, [])
                                if s['start'] == seg['start'] and s['end'] == seg['end']]
                    cn_vals.append(str(matching[0]['cn']) if matching else '?')

                span_kb = (seg['end'] - seg['start']) / 1000
                label = f"{chrom}:{seg['start']}-{seg['end']} ({span_kb:.0f}kb)"
                # Bold rows where CN differs across ploidies
                if len(set(cn_vals)) > 1:
                    cn_cells = [f"**{v}**" for v in cn_vals]
                else:
                    cn_cells = cn_vals
                lines.append(f"| {label} | {seg['log2']:.3f} | {seg['depth']:.1f} | "
                             f"{cn_cells[0]} | {cn_cells[1]} | {cn_cells[2]} |")

    # Table 2: VCF records comparison
    lines.append("\n### VCF — records by ploidy\n")
    lines.append("| Ploidy | DEL | DUP | Total | Hidden (cn==ploidy) |")
    lines.append("|--------|-----|-----|-------|---------------------|")
    for ploidy in ploidies:
        recs = vcf_data.get(ploidy, [])
        dels = sum(1 for r in recs if r['svtype'] == 'DEL')
        dups = sum(1 for r in recs if r['svtype'] == 'DUP')
        total_segs = len(cns_data.get(ploidy, {}).get(all_chroms[0], [])) if all_chroms else 0
        # Count total segments across all chroms
        total_cns = sum(len(segs) for segs in cns_data.get(ploidy, {}).values())
        hidden = total_cns - (dels + dups)
        lines.append(f"| {ploidy} | {dels} | {dups} | {dels+dups} | {hidden} |")

    # Table 3: VCF detail — all records for each ploidy
    lines.append("\n### VCF — all records by ploidy\n")
    for ploidy in ploidies:
        recs = vcf_data.get(ploidy, [])
        if recs:
            lines.append(f"**Ploidy={ploidy}** ({len(recs)} records):\n")
            lines.append("| Chrom | SVTYPE | CN/GT | log2 |")
            lines.append("|-------|--------|-------|------|")
            for r in recs:
                cn_str = f"CN={r['cn']}" if r.get('cn') else f"GT={r['gt']}"
                lines.append(f"| {r['chrom']}:{r['pos']}-{r['end']} | {r['svtype']} | {cn_str} | {r['fold_change_log']:.3f} |")
            lines.append("")

    lines.append("---\n")

with open(report_path, 'w') as f:
    f.write('\n'.join(lines))

print(f"\nReport written to {report_path}")
PYEOF

echo ""
echo "============================================================"
echo "Done. Results in: ${OUTPUT_DIR}"
echo "Report: ${OUTPUT_DIR}/ploidy_comparison.md"
echo "============================================================"
