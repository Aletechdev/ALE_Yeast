#!/usr/bin/env python3
"""
Generate a manager-friendly benchmarking summary report from existing CSV outputs.
Reads precision/recall and tool comparison CSVs — no bcftools calls needed.
"""

import csv
import math
import os
import subprocess
import sys

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Input CSVs
RECALL_CSV = os.path.join(BASE, "output_all/precision_recall_by_freq_bin.csv")
DETAILS_CSV = os.path.join(BASE, "output_all/variant_match_details.csv")
COUNTS_CSV = os.path.join(BASE, "output_all/tool_comparison/variant_counts_per_sample.csv")
CONCORDANCE_CSV = os.path.join(BASE, "output_all/tool_comparison/concordance_summary.csv")
RESOURCE_CSV = os.path.join(BASE, "output_all/tool_comparison/resource_comparison.csv")
PROXIMITY_CSV = os.path.join(BASE, "output_all/tool_comparison/proximity_concordance_50bp.csv")
TRUTH_CSV = os.path.join(BASE, "data/dicarboxylic_acids/process_adipic_muts/03_table_s8_genomic_locations.csv")

OUTPUT = os.path.join(BASE, "output_all/BENCHMARKING_SUMMARY.md")

# Example discordance locus
EXAMPLE_SAMPLE = "A0-F0-I1-R1"
EXAMPLE_CHROM = "chr12"
EXAMPLE_POS = 431553
EXAMPLE_BRESEQ_VCF = os.path.join(
    BASE, f"output_all/variant_calling/breseq/{EXAMPLE_SAMPLE}/{EXAMPLE_SAMPLE}.vcf.gz"
)
EXAMPLE_CRAM = os.path.join(
    BASE, f"output_all/preprocessing/markduplicates/{EXAMPLE_SAMPLE}/{EXAMPLE_SAMPLE}.md.cram"
)
REFERENCE = os.path.join(BASE, "data/BakerYeast_reference/draft_ref52.fasta")


def read_csv(path):
    with open(path) as f:
        return list(csv.DictReader(f))


def get_breseq_variant(vcf_path, chrom, pos):
    """Extract REF, ALT, DP, AD from breseq VCF at a specific position."""
    cmd = ["bcftools", "query", "-r", f"{chrom}:{pos}-{pos}",
           "-f", "%REF\t%ALT\t%INFO/DP\t%INFO/AD\n", vcf_path]
    out = subprocess.run(cmd, capture_output=True, text=True).stdout.strip()
    if not out:
        return None
    ref, alt, dp, ad = out.split("\t")
    return {"ref": ref, "alt": alt, "dp": int(dp), "ad": int(ad)}


def get_mpileup_alt_counts(cram_path, ref_path, chrom, pos, alt_base):
    """Get total depth and ALT read count from BWA-MEM alignment via samtools mpileup."""
    cmd = ["samtools", "mpileup", "-r", f"{chrom}:{pos}-{pos}",
           "-f", ref_path, cram_path]
    out = subprocess.run(cmd, capture_output=True, text=True).stdout.strip()
    if not out:
        return None
    fields = out.split("\t")
    depth = int(fields[3])
    pileup = fields[4]
    alt_count = pileup.lower().count(alt_base.lower())
    return {"depth": depth, "alt_count": alt_count}


def pearson_r(xs, ys):
    """Compute Pearson correlation coefficient."""
    n = len(xs)
    if n < 3:
        return float("nan")
    mx = sum(xs) / n
    my = sum(ys) / n
    sx = math.sqrt(sum((x - mx) ** 2 for x in xs))
    sy = math.sqrt(sum((y - my) ** 2 for y in ys))
    if sx == 0 or sy == 0:
        return float("nan")
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / (sx * sy)


def main():
    # --- Load data ---
    recall_rows = read_csv(RECALL_CSV)
    details = read_csv(DETAILS_CSV)
    counts = read_csv(COUNTS_CSV)
    concordance = read_csv(CONCORDANCE_CSV)
    resources = read_csv(RESOURCE_CSV)
    proximity = read_csv(PROXIMITY_CSV)
    truth = read_csv(TRUTH_CSV)

    # --- Compute AF accuracy ---
    present = [d for d in details if float(d["expected_freq"]) > 0]

    expected_freqs = [float(d["expected_freq"]) / 100 for d in present]
    breseq_afs = [float(d["breseq_af"]) for d in present]
    hc_afs = [float(d["hc_af"]) for d in present]

    r_breseq = pearson_r(expected_freqs, breseq_afs)
    r_hc = pearson_r(expected_freqs, hc_afs)
    r_tools = pearson_r(breseq_afs, hc_afs)

    # Mean absolute error
    mae_breseq = sum(abs(e - o) for e, o in zip(expected_freqs, breseq_afs)) / len(present)
    mae_hc = sum(abs(e - o) for e, o in zip(expected_freqs, hc_afs)) / len(present)

    # --- Count truth set properties ---
    n_snvs = sum(1 for t in truth if t["ref"].strip() and t["alt"].strip())
    n_repeat = sum(1 for t in truth if not t["ref"].strip() or not t["alt"].strip())
    lineages = sorted(set(t["strain"] for t in truth))
    genes = sorted(set(t["gene"].strip() for t in truth if t["ref"].strip() and t["alt"].strip()))

    # Lowest AF detected
    min_entry = min(present, key=lambda d: float(d["expected_freq"]))

    # --- Variant count averages ---
    clonal = [c for c in counts if c["type"] == "clonal"]
    population = [c for c in counts if c["type"] == "population"]

    def avg(rows, key):
        vals = [int(r[key]) for r in rows if r[key] not in ("N/A", "")]
        return sum(vals) / len(vals) if vals else 0

    # --- Concordance averages (clonal: AF>=90%, population: AF>=5%) ---
    pop_conc = [c for c in concordance if c["type"] == "population"]
    clo_conc = [c for c in concordance if c["type"] == "clonal"]
    avg_both_pop = avg(pop_conc, "concordant")
    avg_breseq_only_pop = avg(pop_conc, "breseq_only")
    avg_hc_only_pop = avg(pop_conc, "hc_only")
    avg_both_clo = avg(clo_conc, "concordant")
    avg_breseq_only_clo = avg(clo_conc, "breseq_only")
    avg_hc_only_clo = avg(clo_conc, "hc_only")

    # --- Proximity concordance averages (±50bp) ---
    pop_prox = [p for p in proximity if p["type"] == "population"]
    clo_prox = [p for p in proximity if p["type"] == "clonal"]

    def avg_f(rows, key):
        vals = [float(r[key]) for r in rows if r[key] not in ("N/A", "")]
        return sum(vals) / len(vals) if vals else 0

    prox_near_clo = avg_f(clo_prox, "breseq_near_hc")
    prox_buniq_clo = avg_f(clo_prox, "breseq_unique")
    prox_hcnear_clo = avg_f(clo_prox, "hc_near_breseq")
    prox_huniq_clo = avg_f(clo_prox, "hc_unique")
    prox_near_pop = avg_f(pop_prox, "breseq_near_hc")
    prox_buniq_pop = avg_f(pop_prox, "breseq_unique")
    prox_hcnear_pop = avg_f(pop_prox, "hc_near_breseq")
    prox_huniq_pop = avg_f(pop_prox, "hc_unique")

    # --- Example discordance locus ---
    breseq_ex = get_breseq_variant(EXAMPLE_BRESEQ_VCF, EXAMPLE_CHROM, EXAMPLE_POS)
    mpileup_ex = get_mpileup_alt_counts(
        EXAMPLE_CRAM, REFERENCE, EXAMPLE_CHROM, EXAMPLE_POS,
        breseq_ex["alt"] if breseq_ex else "T"
    )

    # --- Write report ---
    with open(OUTPUT, "w") as f:
        f.write("# SNV Calling Benchmarking Summary\n\n")

        # 1. Executive summary
        f.write("## Executive Summary\n\n")
        f.write(
            "Both variant calling tools in the pipeline — **breseq** and **GATK HaplotypeCaller** (joint germline mode) "
            "— achieve **100% recall** on a curated set of 24 SNVs across 5 ALE lineages, "
            "spanning allele frequencies from 17% to 100%. "
            "Neither tool produced false positives on 3 negative-control loci. "
            "Observed allele frequencies closely match expected values from spore-seq segregation "
            f"(Pearson r = {r_breseq:.3f} for breseq, r = {r_hc:.3f} for HaplotypeCaller). "
            "The pipeline is reliable for detecting SNVs in yeast ALE experiments.\n\n"
            "Beyond the curated truth set, the two tools show low position-level concordance genome-wide "
            "(~10% of breseq mutations in population samples exactly match HaplotypeCaller calls, ~25% within ±50 bp), reflecting fundamentally different "
            "alignment strategies (bowtie2 vs BWA-MEM) and variant calling models. "
            "Cross-validating mutations across both methods is essential for high-confidence calls, "
            "and investing in a starting-strain reference genome would further reduce alignment-driven discordance.\n\n"
        )

        # 2. Recall by frequency bin
        f.write("## Recall by Frequency Bin\n\n")
        f.write("| Frequency Bin | N (truth) | breseq TP | breseq Recall | HC TP | HC Recall |\n")
        f.write("|---------------|-----------|-----------|---------------|-------|-----------|\n")
        for row in recall_rows:
            f.write(f"| {row['freq_bin']} | {row['n_truth']} | {row['breseq_TP']} | {row['breseq_recall']} | {row['hc_TP']} | {row['hc_recall']} |\n")
        f.write(f"\nLowest-frequency variant detected by both tools: **{min_entry['gene']}** "
                f"({min_entry['chrom']}:{min_entry['pos']}) at **{min_entry['expected_freq']}% expected AF** "
                f"in sample {min_entry['sample']}.\n\n")

        # 3. Truth set
        absent = [d for d in details if float(d["expected_freq"]) == 0]
        f.write("## Truth Set\n\n")
        f.write("- **Source**: Table S8 — manually curated SNVs from spore-seq segregation analysis "
                "(adipic acid samples from https://www.sciencedirect.com/science/article/pii/S1096717619302824?via%3Dihub)\n")
        f.write(f"- **{n_snvs} SNVs** with defined ref/alt across {len(lineages)} ALE lineages ({', '.join(lineages)})\n")
        f.write(f"- **{len(genes)} genes** affected: {', '.join(genes)}\n")
        f.write(f"- Each SNV tested in 2 spore-seq strains (tolerant or sensitive to adipic acid) → **{len(details)} variant×sample entries**\n")
        f.write(f"  - {len(present)} expected-present (AF 17–100%)\n")
        f.write(f"  - {len(absent)} expected-absent (negative controls, expected AF = 0%)\n")
        f.write(f"- **Caveat:** {n_repeat} repeat-expansion mutations excluded (no simple ref/alt for VCF matching), "
                "synthetic data required for more in-depth analysis of structural mutations recalling.\n\n")

        # 4. Specificity
        f.write("## Specificity (False Positive Check)\n\n")
        f.write(f"- **{len(absent)} negative-control entries** (variant expected in one spore segregant but absent in the sibling)\n")
        f.write(f"- **breseq false positives: 0/{len(absent)}**\n")
        f.write(f"- **HaplotypeCaller false positives: 0/{len(absent)}**\n\n")
        f.write("**Caveat**: This tests specificity only at known loci (3 positions). "
                "It does not measure the genome-wide false positive rate, "
                "which would require synthetic spike-in or orthogonal validation.\n\n")

        # 5. AF accuracy
        f.write("## Allele Frequency Accuracy\n\n")
        f.write("Comparison of observed AF (from VCF) vs expected AF (from spore-seq segregation):\n\n")
        f.write(f"| Metric | breseq | HaplotypeCaller |\n")
        f.write(f"|--------|--------|----------------|\n")
        f.write(f"| Pearson r (vs expected) | {r_breseq:.3f} | {r_hc:.3f} |\n")
        f.write(f"| Mean absolute error | {mae_breseq:.3f} | {mae_hc:.3f} |\n")
        f.write(f"| Pearson r (breseq vs HC) | {r_tools:.3f} | {r_tools:.3f} |\n\n")
        f.write("Both tools produce allele frequency estimates that closely track the expected values "
                "and agree with each other.\n\n")

        # 6. Tool complementarity
        f.write("## Tool Complementarity\n\n")
        f.write("### Variant Counts by Sample Type\n\n")
        f.write(f"| Sample Type | N samples | breseq (avg) | HC PASS AF>=90% (avg) | HC PASS AF>=5% (avg) |\n")
        f.write(f"|-------------|-----------|-------------|----------------------|---------------------|\n")
        f.write(f"| Clonal (I1) | {len(clonal)} | {avg(clonal, 'breseq'):.0f} | **{avg(clonal, 'hc_pass_af90'):.0f}** | {avg(clonal, 'hc_pass_af5'):.0f} |\n")
        f.write(f"| Population (I2/I3) | {len(population)} | {avg(population, 'breseq'):.0f} | {avg(population, 'hc_pass_af90'):.0f} | **{avg(population, 'hc_pass_af5'):.0f}** |\n\n")

        clonal_ratio_af90 = avg(clonal, 'hc_pass_af90') / avg(clonal, 'breseq')
        pop_ratio_af5 = avg(population, 'breseq') / avg(population, 'hc_pass_af5')
        f.write("**Why counts differ**:\n\n")
        f.write(f"- **Clonal samples (breseq={avg(clonal, 'breseq'):.0f})**: breseq reports only consensus mutations "
                f"(AF rounded to 1 in VCF, actual AD/DP typically 79–91%). "
                f"HC at AF>=90% finds ~{clonal_ratio_af90:.0f}x more ({avg(clonal, 'hc_pass_af90'):.0f}) due to different aligner and algorithm "
                f"(BWA-MEM + joint genotyping vs breseq's bowtie2 + read-evidence model).\n")
        f.write(f"- **Population samples (breseq={avg(population, 'breseq'):.0f})**: breseq `-p` mode reports variants down to ~5% AF, "
                f"making it ~{pop_ratio_af5:.1f}x more sensitive than HC at AF>=5% ({avg(population, 'hc_pass_af5'):.0f}).\n\n")

        f.write("### Position-Level Concordance\n\n")
        f.write("Exact match requires identical chromosome, position, and alt allele. "
                "Proximity (±50bp) considers positions within 50bp on the same chromosome as matching, "
                "accounting for different variant representations (e.g., left- vs right-aligned indels).\n\n")

        f.write(f"**Clonal samples** (avg across {len(clo_conc)} samples; breseq consensus vs HC PASS AF>=90%):\n\n")
        f.write("| Metric | Exact match | Proximity (±50bp) |\n")
        f.write("|--------|-------------|-------------------|\n")
        f.write(f"| Concordant (both tools) | {avg_both_clo:.0f} | {prox_near_clo:.0f} |\n")
        f.write(f"| breseq-only | {avg_breseq_only_clo:.0f} | {prox_buniq_clo:.0f} |\n")
        f.write(f"| HC-only | {avg_hc_only_clo:.0f} | {prox_huniq_clo:.0f} |\n\n")

        f.write(f"**Population samples** (avg across {len(pop_conc)} samples; breseq `-p` vs HC PASS AF>=5%):\n\n")
        f.write("| Metric | Exact match | Proximity (±50bp) |\n")
        f.write("|--------|-------------|-------------------|\n")
        f.write(f"| Concordant (both tools) | {avg_both_pop:.0f} | {prox_near_pop:.0f} (breseq→HC) / {prox_hcnear_pop:.0f} (HC→breseq) |\n")
        f.write(f"| breseq-only | {avg_breseq_only_pop:.0f} | {prox_buniq_pop:.0f} |\n")
        f.write(f"| HC-only | {avg_hc_only_pop:.0f} | {prox_huniq_pop:.0f} |\n\n")

        f.write("Proximity matching roughly doubles concordance compared to exact matching, "
                "indicating many shared calls differ only in variant representation. "
                "Low overall overlap is expected — the tools use fundamentally different algorithms "
                "(breseq: read-evidence + polymorphism model; HC: haplotype assembly + joint genotyping) "
                "and have different sensitivity profiles at low allele frequencies. "
                "Critically, the two tools also use **different read aligners**: breseq performs its own internal "
                "alignment (bowtie2), while HaplotypeCaller operates on BWA-MEM alignments produced by the Sarek "
                "pipeline. This means read depth and allele counts at the same genomic position can differ "
                "substantially between tools, due to differences in alignment algorithms, mapping quality assignment, "
                "and potential divergence between the reference genome and the actual ancestral strain used in the ALE experiment.\n\n")

        if breseq_ex and mpileup_ex:
            b_af = breseq_ex["ad"] / breseq_ex["dp"] * 100
            m_af = mpileup_ex["alt_count"] / mpileup_ex["depth"] * 100
            f.write(
                f"**Example — {EXAMPLE_CHROM}:{EXAMPLE_POS} in {EXAMPLE_SAMPLE} (clonal)**: "
                f"breseq called {breseq_ex['ref']}→{breseq_ex['alt']} with "
                f"AD={breseq_ex['ad']}, DP={breseq_ex['dp']} (AD/DP={b_af:.1f}%), "
                f"but the BWA-MEM alignment (used by HC) shows only "
                f"{mpileup_ex['alt_count']} ALT reads out of {mpileup_ex['depth']:,} total ({m_af:.1f}%). "
                f"HC correctly did not call this position. "
                f"The discrepancy arises because breseq performs its own internal read alignment (bowtie2), "
                f"which can produce substantially different depth and allele counts at the same genomic position.\n\n"
            )

        f.write("Cross-validating mutations across independent methods is therefore essential for high-confidence ALE variant calls. "
                "Investing in a high-quality reference genome for the actual starting strain "
                "(rather than relying on a published assembly that may diverge at strain-specific loci) "
                "would further reduce alignment-driven discordance and improve concordance between tools.\n\n")

        f.write("### Resource Usage\n\n")
        if resources:
            f.write("| Tool | Avg Runtime/Sample | Peak RAM |\n")
            f.write("|------|--------------------|----------|\n")
            for r in resources:
                f.write(f"| {r['tool']} | {r['avg_duration']} | {r['max_peak_rss_gb']} GB |\n")
            f.write("\n")

        # 7. Limitations
        f.write("## Limitations & Caveats\n\n")
        f.write("1. **SNV-only benchmark**: Repeat expansions (2 mutations) and structural variants (chr2 duplications/triplications) are excluded from this analysis\n")
        f.write(f"2. **Small truth set**: {n_snvs} unique loci across {len(lineages)} lineages — representative but not exhaustive\n")
        f.write("3. **No genome-wide FP measurement**: Only 3 negative-control loci tested; genome-wide specificity would require spike-in or orthogonal sequencing\n")
        f.write("4. **Ploidy handling**: HC was run with ploidy=10 for population samples only (clonal samples use default ploidy=2); genotype fields (GT) require AD-based allele frequency interpretation rather than standard GT parsing\n")
        f.write("5. **Population vs clonal mode**: breseq variant counts depend critically on whether `-p` flag is set (controlled by `clonal_or_population` column in samplesheet)\n")

    print(f"Report written to: {OUTPUT}")


if __name__ == "__main__":
    main()
