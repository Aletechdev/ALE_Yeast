#!/usr/bin/env python3
"""
Comprehensive comparison: breseq vs GATK HaplotypeCaller for yeast ALE.
Covers: resource usage, variant counts, and position-level concordance.
"""

import csv
import glob
import os
import re
import subprocess
import sys
from collections import defaultdict

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
BRESEQ_DIR = os.path.join(BASE, "output_all/variant_calling/breseq")
HC_SOFT_VCF = os.path.join(BASE, "output_all/variant_calling/haplotypecaller/joint_variant_calling/HaplotypeCaller_joint_calling_soft_filtered.vcf.gz")
HC_FILTERED_DIR = os.path.join(BASE, "output_all/variant_calling_filtered/haplotypecaller/individual_from_joint")
TRACE_DIR = os.path.join(BASE, "output_all/pipeline_info")
OUTPUT_DIR = os.path.join(BASE, "output_all/tool_comparison")

SAMPLES = [
    "A0-F0-I1-R1", "A0-F0-I2-R1",
    "A1-F6-I1-R1", "A1-F6-I2-R1", "A1-F6-I3-R1",
    "A3-F3-I1-R1", "A3-F3-I2-R1", "A3-F3-I3-R1",
    "A4-F5-I1-R1", "A4-F5-I2-R1", "A4-F5-I3-R1",
    "A5-F4-I1-R1", "A5-F4-I2-R1", "A5-F4-I3-R1",
    "A6-F6-I1-R1", "A6-F6-I2-R1", "A6-F6-I3-R1",
]
CLONAL = {"A0-F0-I1-R1", "A0-F0-I2-R1", "A1-F6-I1-R1", "A3-F3-I1-R1",
           "A4-F5-I1-R1", "A5-F4-I1-R1", "A6-F6-I1-R1"}


def sample_comment(sample):
    """Return a short population description. Only applies to non-clonal (population) samples."""
    if sample in CLONAL:
        return ""
    if "-I2-" in sample:
        return "10 tolerant spores"
    elif "-I3-" in sample:
        return "10 sensitive spores"
    return ""


def run_cmd(args, timeout=60):
    try:
        r = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
        return r.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return ""


def parse_duration(s):
    """Parse Nextflow duration string like '1h 28m 11s' or '14m 14s' to seconds."""
    total = 0
    for match in re.finditer(r'(\d+(?:\.\d+)?)\s*(h|m|s|ms|d)', s):
        val, unit = float(match.group(1)), match.group(2)
        if unit == 'd': total += val * 86400
        elif unit == 'h': total += val * 3600
        elif unit == 'm': total += val * 60
        elif unit == 's': total += val
        elif unit == 'ms': total += val / 1000
    return total


def parse_memory(s):
    """Parse memory string like '4 GB' or '15.1 GB' to GB."""
    m = re.match(r'([\d.]+)\s*(GB|MB|KB|TB)', s, re.IGNORECASE)
    if not m:
        return 0
    val, unit = float(m.group(1)), m.group(2).upper()
    if unit == 'TB': return val * 1024
    if unit == 'GB': return val
    if unit == 'MB': return val / 1024
    if unit == 'KB': return val / (1024 * 1024)
    return 0


def fmt_duration(seconds):
    if seconds >= 3600:
        return f"{seconds/3600:.1f}h"
    elif seconds >= 60:
        return f"{seconds/60:.1f}m"
    return f"{seconds:.0f}s"


# ─── 1. RESOURCE COMPARISON ───

def parse_resources():
    traces = sorted(glob.glob(os.path.join(TRACE_DIR, "execution_trace_*.txt")))
    if not traces:
        return []
    trace_file = traces[-1]

    breseq_stats = []
    hc_stats = []

    with open(trace_file) as f:
        header = f.readline().strip().split('\t')
        col = {h.strip(): i for i, h in enumerate(header)}

        for line in f:
            fields = line.strip().split('\t')
            if len(fields) < len(col):
                continue
            name = fields[col.get('name', col.get('process', 0))].strip()
            status = fields[col.get('status', 0)].strip()
            if status not in ('COMPLETED', 'CACHED'):
                continue

            duration = parse_duration(fields[col.get('duration', 0)].strip())
            peak_rss = parse_memory(fields[col.get('peak_rss', 0)].strip()) if 'peak_rss' in col else 0
            peak_vmem = parse_memory(fields[col.get('peak_vmem', 0)].strip()) if 'peak_vmem' in col else 0

            if ':BRESEQ (' in name:
                # Match only the main BRESEQ process, not GDTOOLS_CONVERT or other subprocesses
                breseq_stats.append({"duration": duration, "peak_rss": peak_rss, "peak_vmem": peak_vmem})
            elif 'HAPLOTYPECALLER' in name and 'JOINT' not in name and 'SPLIT' not in name and 'FILTER' not in name:
                hc_stats.append({"duration": duration, "peak_rss": peak_rss, "peak_vmem": peak_vmem})

    results = []
    for label, stats in [("breseq", breseq_stats), ("HaplotypeCaller", hc_stats)]:
        if not stats:
            continue
        durations = [s["duration"] for s in stats]
        rss_vals = [s["peak_rss"] for s in stats if s["peak_rss"] > 0]
        vmem_vals = [s["peak_vmem"] for s in stats if s["peak_vmem"] > 0]
        results.append({
            "tool": label,
            "n_tasks": len(stats),
            "avg_duration": fmt_duration(sum(durations) / len(durations)),
            "min_duration": fmt_duration(min(durations)),
            "max_duration": fmt_duration(max(durations)),
            "total_duration": fmt_duration(sum(durations)),
            "avg_peak_rss_gb": f"{sum(rss_vals)/len(rss_vals):.1f}" if rss_vals else "N/A",
            "max_peak_rss_gb": f"{max(rss_vals):.1f}" if rss_vals else "N/A",
        })
    return results


# ─── 2. VARIANT COUNTS ───

def count_breseq_variants(sample):
    vcf = os.path.join(BRESEQ_DIR, sample, f"{sample}.vcf.gz")
    if not os.path.exists(vcf):
        return 0
    out = run_cmd(["bcftools", "view", "-H", vcf])
    return len(out.split("\n")) if out else 0


def get_hc_variants_for_sample(sample, af_threshold=0.05):
    """Get HC variants for a sample using AD-based AF filtering."""
    vcf_sample = f"ALE_Exp1_{sample}"
    out = run_cmd([
        "bcftools", "view", "-f", "PASS", "-s", vcf_sample, HC_SOFT_VCF
    ], timeout=30)
    if not out:
        return [], 0

    ad_out = run_cmd([
        "bash", "-c",
        f"bcftools view -f PASS -s {vcf_sample} {HC_SOFT_VCF} | bcftools query -f '%CHROM\\t%POS\\t%REF\\t%ALT\\t[%AD]\\n'"
    ], timeout=30)
    if not ad_out:
        return [], 0

    variants = []
    count = 0
    for line in ad_out.split("\n"):
        if not line.strip():
            continue
        fields = line.split("\t")
        if len(fields) < 5:
            continue
        chrom, pos, ref, alt, ad = fields[0], fields[1], fields[2], fields[3], fields[4]
        ad_parts = ad.split(",")
        if len(ad_parts) < 2:
            continue
        try:
            ref_depth = int(ad_parts[0])
            alt_depth = int(ad_parts[1])
        except ValueError:
            continue
        total = ref_depth + alt_depth
        if total == 0:
            continue
        af = alt_depth / total
        if af >= af_threshold:
            count += 1
            variants.append({
                "chrom": chrom, "pos": int(pos), "ref": ref,
                "alt": alt.split(",")[0],  # first alt
                "af": af
            })
    return variants, count


def count_hc_filtered(sample):
    """Count variants in HC hard-filtered individual VCFs."""
    pattern = os.path.join(HC_FILTERED_DIR, sample, "*.hard_filtered.vcf.gz")
    files = glob.glob(pattern)
    if not files:
        # try non-hard-filtered
        pattern = os.path.join(HC_FILTERED_DIR, sample, "*.vcf.gz")
        files = [f for f in glob.glob(pattern) if not f.endswith(".tbi")]
    if not files:
        return None
    out = run_cmd(["bcftools", "view", "-H", files[0]])
    return len(out.split("\n")) if out else 0


def get_breseq_variants(sample):
    """Get breseq variant positions for concordance."""
    vcf = os.path.join(BRESEQ_DIR, sample, f"{sample}.vcf.gz")
    if not os.path.exists(vcf):
        return []
    out = run_cmd(["bcftools", "query", "-f", "%CHROM\t%POS\t%REF\t%ALT\t%INFO/AF\n", vcf])
    variants = []
    for line in out.split("\n"):
        if not line.strip():
            continue
        fields = line.split("\t")
        if len(fields) >= 5:
            try:
                variants.append({
                    "chrom": fields[0], "pos": int(fields[1]),
                    "ref": fields[2], "alt": fields[3],
                    "af": float(fields[4])
                })
            except ValueError:
                continue
    return variants


# ─── 3. CONCORDANCE ───

def compute_concordance(sample):
    breseq_vars = get_breseq_variants(sample)
    breseq_keys = {(v["chrom"], v["pos"], v["alt"]) for v in breseq_vars}

    result = {"breseq_total": len(breseq_keys)}
    for label, threshold in [("af5", 0.05), ("af10", 0.10), ("af90", 0.90)]:
        hc_vars, _ = get_hc_variants_for_sample(sample, af_threshold=threshold)
        hc_keys = {(v["chrom"], v["pos"], v["alt"]) for v in hc_vars}
        result[f"hc_total_{label}"] = len(hc_keys)
        result[f"concordant_{label}"] = len(breseq_keys & hc_keys)
        result[f"breseq_only_{label}"] = len(breseq_keys - hc_keys)
        result[f"hc_only_{label}"] = len(hc_keys - breseq_keys)

    return result


def compute_proximity_concordance(sample, window=50, af_threshold=0.05):
    """Concordance where positions within +/-window bp on same chrom are considered matching."""
    breseq_vars = get_breseq_variants(sample)
    hc_vars, _ = get_hc_variants_for_sample(sample, af_threshold=af_threshold)

    # Build position index by chrom for HC
    hc_by_chrom = defaultdict(list)
    for v in hc_vars:
        hc_by_chrom[v["chrom"]].append(v["pos"])
    for chrom in hc_by_chrom:
        hc_by_chrom[chrom].sort()

    # For each breseq variant, check if any HC variant is within window
    breseq_matched = 0
    hc_matched_positions = set()
    for bv in breseq_vars:
        chrom = bv["chrom"]
        pos = bv["pos"]
        matched = False
        for hc_pos in hc_by_chrom.get(chrom, []):
            if abs(hc_pos - pos) <= window:
                matched = True
                hc_matched_positions.add((chrom, hc_pos))
            elif hc_pos > pos + window:
                break
        if matched:
            breseq_matched += 1

    breseq_total = len(breseq_vars)
    hc_total = len(hc_vars)
    hc_matched = len(hc_matched_positions)

    return {
        "breseq_total": breseq_total,
        "hc_total": hc_total,
        "breseq_near_hc": breseq_matched,
        "breseq_unique": breseq_total - breseq_matched,
        "hc_near_breseq": hc_matched,
        "hc_unique": hc_total - hc_matched,
    }


# ─── MAIN ───

def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # --- 1. Resources ---
    print("=== 1. RESOURCE COMPARISON ===")
    resources = parse_resources()
    if resources:
        res_path = os.path.join(OUTPUT_DIR, "resource_comparison.csv")
        with open(res_path, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=resources[0].keys())
            w.writeheader()
            w.writerows(resources)

        print(f"{'Tool':<20} {'Tasks':>6} {'Avg':>8} {'Min':>8} {'Max':>8} {'Total':>10} {'Avg RSS':>10} {'Max RSS':>10}")
        print("-" * 82)
        for r in resources:
            print(f"{r['tool']:<20} {r['n_tasks']:>6} {r['avg_duration']:>8} {r['min_duration']:>8} {r['max_duration']:>8} {r['total_duration']:>10} {r['avg_peak_rss_gb']:>8} GB {r['max_peak_rss_gb']:>8} GB")
    else:
        print("  No execution trace found")

    # --- 2. Variant Counts ---
    print("\n=== 2. VARIANT COUNTS PER SAMPLE ===")
    counts = []
    for sample in SAMPLES:
        sample_type = "clonal" if sample in CLONAL else "population"
        breseq_n = count_breseq_variants(sample)
        _, hc_pass_5 = get_hc_variants_for_sample(sample, af_threshold=0.05)
        _, hc_pass_10 = get_hc_variants_for_sample(sample, af_threshold=0.10)
        _, hc_pass_90 = get_hc_variants_for_sample(sample, af_threshold=0.90)
        hc_filt = count_hc_filtered(sample)

        counts.append({
            "sample": sample,
            "type": sample_type,
            "breseq": breseq_n,
            "hc_pass_af5": hc_pass_5,
            "hc_pass_af10": hc_pass_10,
            "hc_pass_af90": hc_pass_90,
            "hc_hard_filtered": hc_filt if hc_filt is not None else "N/A",
        })

    counts_path = os.path.join(OUTPUT_DIR, "variant_counts_per_sample.csv")
    with open(counts_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=counts[0].keys())
        w.writeheader()
        w.writerows(counts)

    print(f"{'Sample':<16} {'Type':<12} {'breseq':>8} {'HC AF>=5%':>10} {'HC AF>=10%':>11} {'HC AF>=90%':>11} {'HC filtered':>12}")
    print("-" * 84)
    for c in counts:
        print(f"{c['sample']:<16} {c['type']:<12} {c['breseq']:>8} {c['hc_pass_af5']:>10} {c['hc_pass_af10']:>11} {c['hc_pass_af90']:>11} {str(c['hc_hard_filtered']):>12}")

    # Averages by type
    for stype in ["clonal", "population"]:
        subset = [c for c in counts if c["type"] == stype]
        n = len(subset)
        avg_b = sum(c["breseq"] for c in subset) / n
        avg_h5 = sum(c["hc_pass_af5"] for c in subset) / n
        avg_h10 = sum(c["hc_pass_af10"] for c in subset) / n
        avg_h90 = sum(c["hc_pass_af90"] for c in subset) / n
        print(f"  {stype} avg: breseq={avg_b:.0f}, HC AF>=5%={avg_h5:.0f}, HC AF>=10%={avg_h10:.0f}, HC AF>=90%={avg_h90:.0f}")

    # --- 3. Concordance ---
    print("\n=== 3. POSITION-LEVEL CONCORDANCE ===")
    conc_results = []
    for sample in SAMPLES:
        c = compute_concordance(sample)
        c["sample"] = sample
        c["type"] = "clonal" if sample in CLONAL else "population"
        conc_results.append(c)

    conc_path = os.path.join(OUTPUT_DIR, "concordance_summary.csv")
    fieldnames = ["sample", "type", "hc_af_threshold", "breseq_total",
                  "hc_total", "concordant", "breseq_only", "hc_only"]
    with open(conc_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for c in conc_results:
            is_clonal = c["sample"] in CLONAL
            suffix = "af90" if is_clonal else "af5"
            w.writerow({
                "sample": c["sample"],
                "type": c["type"],
                "hc_af_threshold": ">=90%" if is_clonal else ">=5%",
                "breseq_total": c["breseq_total"],
                "hc_total": c[f"hc_total_{suffix}"],
                "concordant": c[f"concordant_{suffix}"],
                "breseq_only": c[f"breseq_only_{suffix}"],
                "hc_only": c[f"hc_only_{suffix}"],
            })

    for label, suffix in [("HC PASS AF>=5%", "af5"), ("HC PASS AF>=10%", "af10"), ("HC PASS AF>=90%", "af90")]:
        print(f"\n  --- Concordance: breseq vs {label} ---")
        print(f"  {'Sample':<16} {'Type':<12} {'breseq':>7} {'HC':>7} {'Both':>6} {'breseq-only':>12} {'HC-only':>8}")
        print(f"  {'-' * 72}")
        for c in conc_results:
            print(f"  {c['sample']:<16} {c['type']:<12} {c['breseq_total']:>7} {c[f'hc_total_{suffix}']:>7} {c[f'concordant_{suffix}']:>6} {c[f'breseq_only_{suffix}']:>12} {c[f'hc_only_{suffix}']:>8}")

    # --- 4. Proximity Concordance ---
    print("\n=== 4. PROXIMITY CONCORDANCE (±50bp) ===")
    prox_all = {}
    for af_label, af_thresh in [("af5", 0.05), ("af90", 0.90)]:
        prox_results = []
        for sample in SAMPLES:
            p = compute_proximity_concordance(sample, window=50, af_threshold=af_thresh)
            p["sample"] = sample
            p["type"] = "clonal" if sample in CLONAL else "population"
            prox_results.append(p)
        prox_all[af_label] = prox_results

        af_pct = f"{int(af_thresh*100)}%"
        print(f"\n  --- Proximity ±50bp, HC PASS AF>={af_pct} ---")
        print(f"  {'Sample':<16} {'Type':<12} {'breseq':>7} {'HC':>7} {'breseq→HC':>10} {'breseq-only':>12} {'HC→breseq':>10} {'HC-only':>8}")
        print(f"  {'-' * 84}")
        for p in prox_results:
            print(f"  {p['sample']:<16} {p['type']:<12} {p['breseq_total']:>7} {p['hc_total']:>7} {p['breseq_near_hc']:>10} {p['breseq_unique']:>12} {p['hc_near_breseq']:>10} {p['hc_unique']:>8}")

    prox_path = os.path.join(OUTPUT_DIR, "proximity_concordance_50bp.csv")
    prox_fields = ["sample", "type", "hc_af_threshold", "breseq_total", "hc_total",
                   "breseq_near_hc", "breseq_unique", "hc_near_breseq", "hc_unique"]
    prox_by_sample_af5 = {p["sample"]: p for p in prox_all["af5"]}
    prox_by_sample_af90 = {p["sample"]: p for p in prox_all["af90"]}
    with open(prox_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=prox_fields)
        w.writeheader()
        for sample in SAMPLES:
            is_clonal = sample in CLONAL
            row = dict(prox_by_sample_af90[sample] if is_clonal else prox_by_sample_af5[sample])
            row["hc_af_threshold"] = ">=90%" if is_clonal else ">=5%"
            w.writerow({k: row[k] for k in prox_fields})

    # --- Write report ---
    report_path = os.path.join(OUTPUT_DIR, "COMPARISON_REPORT.md")
    with open(report_path, "w") as f:
        f.write("# breseq vs HaplotypeCaller Comparison Report\n\n")

        f.write("## Key Differences\n\n")
        f.write("| Aspect | breseq | HaplotypeCaller |\n")
        f.write("|--------|--------|----------------|\n")
        f.write("| Mode | Per-sample; clonal (default) or population (`-p`) | Joint calling across all samples; variant quality scored at cohort level (INFO fields aggregated across all samples) |\n")
        f.write("| Min AF detected | 5% (default `--polymorphism-frequency-cutoff 0.05` in `-p` mode) | ~10% theoretical floor (1 copy / ploidy=10); lower possible with high depth |\n")
        f.write("| Output | VCF + GenomeDiff + HTML evidence | Multi-sample VCF |\n")
        f.write("| Annotation | Built-in (gene, AA change) | Requires SnpEff |\n")
        if resources:
            for r in resources:
                if r["tool"] == "breseq":
                    f.write(f"| Avg runtime | {r['avg_duration']}/sample | ")
                elif r["tool"] == "HaplotypeCaller":
                    f.write(f"{r['avg_duration']}/sample |\n")
                    f.write(f"| Peak RAM | ")
            for r in resources:
                if r["tool"] == "breseq":
                    f.write(f"{r['max_peak_rss_gb']} GB | ")
                elif r["tool"] == "HaplotypeCaller":
                    f.write(f"{r['max_peak_rss_gb']} GB |\n")

        f.write("\n## Variant Counts\n\n")
        f.write("| Sample | Type | Comment | breseq | HC PASS AF>=5% | HC PASS AF>=10% | HC PASS AF>=90% |\n")
        f.write("|--------|------|---------|--------|----------------|----------------|----------------|\n")
        for c in counts:
            is_clonal = c['sample'] in CLONAL
            af5  = f"{c['hc_pass_af5']}*"  if not is_clonal else str(c['hc_pass_af5'])
            af90 = f"{c['hc_pass_af90']}*" if is_clonal     else str(c['hc_pass_af90'])
            f.write(f"| {c['sample']} | {c['type']} | {sample_comment(c['sample'])} | {c['breseq']} | {af5} | {c['hc_pass_af10']} | {af90} |\n")
        f.write("\n\\* For clonal samples, HC PASS AF>=90% is used for concordance comparison with breseq. "
                "For population samples, HC PASS AF>=5% is used for concordance comparison with breseq.\n")

        f.write("\n## Concordance: breseq vs HC\n\n")
        f.write("Clonal samples use HC PASS AF>=90%; population samples use HC PASS AF>=5%.\n\n")
        f.write("| Sample | Type | HC AF threshold | breseq | HC | Both | breseq-only | HC-only |\n")
        f.write("|--------|------|-----------------|--------|-----|------|-------------|--------|\n")
        for c in conc_results:
            is_clonal = c['sample'] in CLONAL
            suffix = "af90" if is_clonal else "af5"
            af_label = ">=90%" if is_clonal else ">=5%"
            f.write(f"| {c['sample']} | {c['type']} | {af_label} | {c['breseq_total']} | {c[f'hc_total_{suffix}']} | {c[f'concordant_{suffix}']} | {c[f'breseq_only_{suffix}']} | {c[f'hc_only_{suffix}']} |\n")

        f.write("\n## Proximity Concordance (±50bp)\n\n")
        f.write("Positions within 50bp on the same chromosome are considered matching (accounts for different variant representations).\n")
        f.write("Clonal samples use HC PASS AF>=90%; population samples use HC PASS AF>=5%.\n\n")
        f.write("| Sample | Type | HC AF threshold | breseq | HC | breseq near HC | breseq-only | HC near breseq | HC-only |\n")
        f.write("|--------|------|-----------------|--------|-----|---------------|-------------|---------------|--------|\n")
        prox_by_sample = {p["sample"]: p for p in prox_all["af5"]}
        prox_by_sample_90 = {p["sample"]: p for p in prox_all["af90"]}
        for sample in SAMPLES:
            is_clonal = sample in CLONAL
            p = prox_by_sample_90[sample] if is_clonal else prox_by_sample[sample]
            af_label = ">=90%" if is_clonal else ">=5%"
            f.write(f"| {p['sample']} | {p['type']} | {af_label} | {p['breseq_total']} | {p['hc_total']} | {p['breseq_near_hc']} | {p['breseq_unique']} | {p['hc_near_breseq']} | {p['hc_unique']} |\n")

        f.write("\n## Notes\n\n")
        f.write("- breseq clonal mode reports only consensus mutations; the AF field in its VCF is rounded to 1 (100%), but actual read support by AD/DP is typically 79–91% due to reference-spanning reads and alignment ambiguity at indel sites\n")
        f.write("- breseq population mode (`-p`) reports polymorphisms down to 5% AF (breseq default `--polymorphism-frequency-cutoff 0.05`)\n")
        f.write("- HC variant counts use AD-based AF filtering (bcftools GT filters broken for polyploid)\n")
        f.write("- HC joint VCF: `HaplotypeCaller_joint_calling_soft_filtered.vcf.gz` (FILTER populated)\n")
        f.write("- Exact concordance based on chrom+pos+alt match\n")
        f.write("- Proximity concordance based on chrom+pos within ±50bp (alt not compared)\n")

    print(f"\nOutputs written to: {OUTPUT_DIR}/")
    print(f"  resource_comparison.csv")
    print(f"  variant_counts_per_sample.csv")
    print(f"  concordance_summary.csv")
    print(f"  proximity_concordance_50bp.csv")
    print(f"  COMPARISON_REPORT.md")


if __name__ == "__main__":
    main()
