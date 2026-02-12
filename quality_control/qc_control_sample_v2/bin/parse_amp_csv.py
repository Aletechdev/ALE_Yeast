#!/usr/bin/env python3
"""
Parse AMP CSV file to VCF-like format for comparison with ALE-Yeast pipeline output.

This script reads mutations from ALEdb-AMP pipeline CSV format and converts them
to a VCF-like format for easier comparison with VCF outputs.
"""

import csv
import re
import sys
from pathlib import Path
from typing import Dict, List, Tuple, Optional


def normalize_sample_name(sample_name: str) -> str:
    """
    Convert sample name from 'A0 F0 I1 R1' format to 'A0-F0-I1-R1' format.

    Args:
        sample_name: Sample name with spaces (e.g., "A0 F0 I1 R1")

    Returns:
        Sample name with hyphens (e.g., "A0-F0-I1-R1")
    """
    return sample_name.replace(" ", "-")


def parse_position(position_str: str) -> int:
    """
    Parse position string, removing commas.

    Args:
        position_str: Position with potential commas (e.g., "291,476")

    Returns:
        Position as integer (e.g., 291476)
    """
    return int(position_str.replace(",", ""))


def parse_sequence_change(seq_change: str, mut_type: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Parse sequence change to extract REF and ALT alleles.

    Args:
        seq_change: Sequence change description (various formats)
        mut_type: Mutation type (SNP, INS, DEL)

    Returns:
        Tuple of (REF, ALT) or (None, None) if cannot parse
    """
    # Handle SNP with → separator
    if "→" in seq_change:
        parts = seq_change.split("→")
        if len(parts) == 2:
            ref = parts[0].strip()
            alt = parts[1].strip()

            # Handle simple SNP: G→T
            if len(ref) == 1 and len(alt) == 1:
                return (ref, alt)

            # Handle repeat changes: (AT)16→15, (A)17→16
            repeat_match = re.match(r'\(([A-Z]+)\)(\d+)', ref)
            if repeat_match:
                unit = repeat_match.group(1)
                from_count = int(repeat_match.group(2))
                to_count = int(alt)

                if from_count > to_count:
                    # Deletion: return longer sequence as REF
                    return (unit * from_count, unit * to_count)
                else:
                    # Insertion: return shorter sequence as REF
                    return (unit * from_count, unit * to_count)

    # Handle insertions: +A, +GTGGGA
    if seq_change.startswith("+"):
        alt_seq = seq_change[1:]
        # For insertions, we need reference context (not available in CSV)
        # Return as is for now
        return (".", alt_seq)

    # If cannot parse, return None
    return (None, None)


def parse_sample_frequency(freq_str: str) -> Tuple[Optional[float], Optional[float]]:
    """
    Parse sample frequency string in format "breseq/GATK_CNVnator".

    Args:
        freq_str: Frequency string like "1.00/0.96" or empty ""

    Returns:
        Tuple of (breseq_freq, gatk_freq) or (None, None) if empty
    """
    if not freq_str or freq_str.strip() == "":
        return (None, None)

    parts = freq_str.split("/")
    if len(parts) == 2:
        try:
            breseq_freq = float(parts[0]) if parts[0] else None
            gatk_freq = float(parts[1]) if parts[1] else None
            return (breseq_freq, gatk_freq)
        except ValueError:
            return (None, None)

    return (None, None)


def is_detected_by_amp(breseq_freq: Optional[float], gatk_freq: Optional[float]) -> bool:
    """
    Check if mutation is detected by AMP pipeline.

    Args:
        breseq_freq: Frequency from breseq
        gatk_freq: Frequency from GATK_CNVnator

    Returns:
        True if EITHER breseq OR gatk frequency is > 0, False otherwise
        (changed from requiring BOTH to requiring EITHER)
    """
    # Detected if either tool detected it (OR logic, not AND)
    breseq_detected = breseq_freq is not None and breseq_freq > 0
    gatk_detected = gatk_freq is not None and gatk_freq > 0
    return breseq_detected or gatk_detected


def parse_amp_csv(csv_path: Path, output_dir: Path):
    """
    Parse AMP CSV file and generate VCF-like output files.

    Args:
        csv_path: Path to input CSV file
        output_dir: Path to output directory
    """
    print(f"Reading AMP CSV file: {csv_path}")

    # Read CSV file
    with open(csv_path, 'r') as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    print(f"Total rows in CSV: {len(rows)}")

    # Get sample names from header (skip first 6 columns: metadata)
    fieldnames = reader.fieldnames
    sample_cols = [normalize_sample_name(col) for col in fieldnames[6:]]
    print(f"Samples found: {len(sample_cols)}")
    print(f"Sample names: {', '.join(sample_cols)}")

    # Parse mutations into VCF-like format
    mutations = []
    parse_errors = 0

    for row in rows:
        chrom = row["Reference Seq"]
        pos = parse_position(row["Position"])
        mut_type = row["Mutation Type"]
        seq_change = row["Sequence Change"]
        gene = row["Gene (Scrollable)"]
        details = row["Details"]

        ref, alt = parse_sequence_change(seq_change, mut_type)

        if ref is None or alt is None:
            parse_errors += 1
            # Still record the mutation with original sequence change
            ref = "."
            alt = seq_change

        # Parse sample frequencies
        sample_data = {}
        for sample_col in sample_cols:
            original_col = sample_col.replace("-", " ")
            freq_str = row[original_col]
            breseq_freq, gatk_freq = parse_sample_frequency(freq_str)
            detected = is_detected_by_amp(breseq_freq, gatk_freq)

            sample_data[sample_col] = {
                "breseq_freq": breseq_freq,
                "gatk_freq": gatk_freq,
                "detected": detected,
                "raw": freq_str
            }

        mutations.append({
            "CHROM": chrom,
            "POS": pos,
            "REF": ref,
            "ALT": alt,
            "MUT_TYPE": mut_type,
            "SEQ_CHANGE": seq_change,
            "GENE": gene,
            "DETAILS": details,
            "samples": sample_data
        })

    print(f"Mutations parsed: {len(mutations)}")
    print(f"Parse errors (sequences not converted): {parse_errors}")

    # Write VCF-like format for each sample
    output_dir.mkdir(parents=True, exist_ok=True)

    for sample in sample_cols:
        sample_output = output_dir / f"{sample}_AMP_mutations.tsv"

        with open(sample_output, 'w') as f:
            # Write header
            f.write("CHROM\tPOS\tREF\tALT\tMUT_TYPE\tSEQ_CHANGE\tGENE\tDETAILS\tBRESEQ_FREQ\tGATK_FREQ\tDETECTED\n")

            sample_mutations = 0
            detected_mutations = 0

            for mut in mutations:
                sample_data = mut["samples"][sample]

                # Only include mutations where sample has data
                if sample_data["breseq_freq"] is not None or sample_data["gatk_freq"] is not None:
                    breseq = f"{sample_data['breseq_freq']:.2f}" if sample_data["breseq_freq"] is not None else "."
                    gatk = f"{sample_data['gatk_freq']:.2f}" if sample_data["gatk_freq"] is not None else "."
                    detected = "YES" if sample_data["detected"] else "NO"

                    f.write(f"{mut['CHROM']}\t{mut['POS']}\t{mut['REF']}\t{mut['ALT']}\t"
                           f"{mut['MUT_TYPE']}\t{mut['SEQ_CHANGE']}\t{mut['GENE']}\t{mut['DETAILS']}\t"
                           f"{breseq}\t{gatk}\t{detected}\n")

                    sample_mutations += 1
                    if sample_data["detected"]:
                        detected_mutations += 1

        print(f"  {sample}: {detected_mutations} detected mutations (out of {sample_mutations} total)")

    # Write summary statistics
    summary_output = output_dir / "AMP_mutation_summary.tsv"
    with open(summary_output, 'w') as f:
        f.write("SAMPLE\tTOTAL_MUTATIONS\tDETECTED_MUTATIONS\tDETECTION_RATE\n")

        for sample in sample_cols:
            total_muts = 0
            detected_muts = 0

            for mut in mutations:
                sample_data = mut["samples"][sample]
                if sample_data["breseq_freq"] is not None or sample_data["gatk_freq"] is not None:
                    total_muts += 1
                    if sample_data["detected"]:
                        detected_muts += 1

            detection_rate = (detected_muts / total_muts * 100) if total_muts > 0 else 0
            f.write(f"{sample}\t{total_muts}\t{detected_muts}\t{detection_rate:.1f}%\n")

    print(f"\nSummary written to: {summary_output}")
    print(f"Per-sample files written to: {output_dir}")


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: python parse_amp_csv.py <amp_csv_file> [output_dir]")
        sys.exit(1)

    csv_path = Path(sys.argv[1])
    output_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("output")

    if not csv_path.exists():
        print(f"Error: CSV file not found: {csv_path}")
        sys.exit(1)

    parse_amp_csv(csv_path, output_dir)


if __name__ == "__main__":
    main()
