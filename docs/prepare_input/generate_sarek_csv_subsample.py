import os, re, csv, argparse
from collections import defaultdict

# Generate samplesheet for sub_sample test data (SubSample-prefixed FASTQ files)
# Based on generate_sarek_csv.py but adapted for sub_sample directory structure
#
# Usage:
#   python generate_sarek_csv_subsample.py                          # default: assets/reads
#   python generate_sarek_csv_subsample.py --data-dir /path/to/dir  # custom directory

PROJECT_ROOT = "/home/azureuser/Docs/ALE_nextflow"

parser = argparse.ArgumentParser(description="Generate Sarek samplesheet from SubSample FASTQ files")
parser.add_argument("--data-dir", default=os.path.join(PROJECT_ROOT, "assets/reads"),
                    help="Directory containing SubSample*.fastq.gz files (default: assets/reads)")
parser.add_argument("--out-file", default="samplesheet.csv",
                    help="Output filename (default: samplesheet.csv)")
args = parser.parse_args()

data_dir = args.data_dir
out_dir = data_dir
out_file = args.out_file

# Compute relative FASTQ path prefix from project root
fastq_prefix = os.path.relpath(data_dir, PROJECT_ROOT)
patient_field = "ALE_Exp1"
sex = "XX"

# Map raw sample names (after stripping "SubSample" prefix) to standardized ALE format
sample_name_map = {
    # Bulk sequencing samples
    "CENPK113-7D-N": "A0-F0-I1-R1",
    "CENPK113-7D-O": "A0-F0-I2-R1",
    "A1-6": "A1-F6-I1-R1",
    "A3-3": "A3-F3-I1-R1",
    "A4-5": "A4-F5-I1-R1",
    "A5-4": "A5-F4-I1-R1",
    "A6-6": "A6-F6-I1-R1",
    # Spore seq samples (POS = I2, NEG = I3)
    "Sp-A1-6-POS": "A1-F6-I2-R1",
    "Sp-A1-6-NEG": "A1-F6-I3-R1",
    "Sp-A3-3-POS": "A3-F3-I2-R1",
    "Sp-A3-3-NEG": "A3-F3-I3-R1",
    "Sp-A4-5-POS": "A4-F5-I2-R1",
    "Sp-A4-5-NEG": "A4-F5-I3-R1",
    "Sp-A5-4-POS": "A5-F4-I2-R1",
    "Sp-A5-4-NEG": "A5-F4-I3-R1",
    "Sp-A6-6-POS": "A6-F6-I2-R1",
    "Sp-A6-6-NEG": "A6-F6-I3-R1",
}

# Status: all samples treated as normal (status=0) for --joint_germline mode
# See CLAUDE.md: "treat all samples as normal, to run haplotypecaller --joint_germline"
status_map = {
    "A0-F0-I1-R1": 0,
    "A0-F0-I2-R1": 0,
    "A1-F6-I1-R1": 0,
    "A3-F3-I1-R1": 0,
    "A4-F5-I1-R1": 0,
    "A5-F4-I1-R1": 0,
    "A6-F6-I1-R1": 0,
    # Spore seq samples
    "A1-F6-I2-R1": 0,
    "A1-F6-I3-R1": 0,
    "A3-F3-I2-R1": 0,
    "A3-F3-I3-R1": 0,
    "A4-F5-I2-R1": 0,
    "A4-F5-I3-R1": 0,
    "A5-F4-I2-R1": 0,
    "A5-F4-I3-R1": 0,
    "A6-F6-I2-R1": 0,
    "A6-F6-I3-R1": 0,
}

# Clonal or population: default is "clonal" unless specified here
clonal_or_population_map = {
    # Spore seq samples are population-based
    "A1-F6-I2-R1": "population",
    "A1-F6-I3-R1": "population",
    "A3-F3-I2-R1": "population",
    "A3-F3-I3-R1": "population",
    "A4-F5-I2-R1": "population",
    "A4-F5-I3-R1": "population",
    "A5-F4-I2-R1": "population",
    "A5-F4-I3-R1": "population",
    "A6-F6-I2-R1": "population",
    "A6-F6-I3-R1": "population",
}
clonal_or_population_default = "clonal"

# Ploidy: default is 1 unless specified here
ploidy_map = {
    # "A1-F6-I2-R1": 2,  # example override
    "A1-F6-I2-R1": 2,
    "A1-F6-I3-R1": 2,
}
ploidy_default = 1

# Match SubSample-prefixed files:
#   Bulk: SubSampleA1-6_S2_L001_R1_001.fastq.gz
#   Spore: SubSampleSp-A1-6-POS_S61_L001_R1_001.fastq.gz
pattern = re.compile(r'SubSample(?P<sample>[A-Za-z0-9\-]+)_S\d+_L(?P<lane>\d{3})_R(?P<read>[12])_001\.fastq\.gz')

samples = defaultdict(lambda: {"R1": None, "R2": None})

print(f"Scanning directory: {data_dir}")
for f in sorted(os.listdir(data_dir)):
    m = pattern.match(f)
    if not m:
        continue
    s, lane, r = m.group("sample"), m.group("lane"), m.group("read")
    key = (s, lane)
    samples[key][f"R{r}"] = os.path.join(fastq_prefix, f)
    print(f"  Found: {f} -> sample={s}, lane=L{lane}, read=R{r}")

# Write CSV
out_path = os.path.join(out_dir, out_file)
print(f"\nWriting samplesheet to: {out_path}")

with open(out_path, "w", newline="") as fh:
    w = csv.writer(fh)
    w.writerow(["experiment", "sample", "status", "clonal_or_population", "ploidy", "sex", "lane", "fastq_1", "fastq_2"])

    count = 0
    for (sample_raw, lane), info in sorted(samples.items()):
        if not (info["R1"] and info["R2"]):
            print(f"  Warning: Skipping {sample_raw} (lane {lane}) - missing R1 or R2")
            continue

        sample_mapped = sample_name_map.get(sample_raw, sample_raw)
        status = status_map.get(sample_mapped, 0)

        if sample_raw not in sample_name_map:
            print(f"  Warning: Sample '{sample_raw}' not in sample_name_map, using as-is")

        sample_type = clonal_or_population_map.get(sample_mapped, clonal_or_population_default)
        sample_ploidy = ploidy_map.get(sample_mapped, ploidy_default)

        w.writerow([patient_field, sample_mapped, status, sample_type, sample_ploidy, sex, f"L{lane}", info["R1"], info["R2"]])
        count += 1

print(f"\nSummary: {count} rows written to {out_file}")
