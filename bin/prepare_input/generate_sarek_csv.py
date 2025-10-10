import os, re, csv
from collections import defaultdict
from pathlib import Path

# for formatting data from paper: https://www.sciencedirect.com/science/article/pii/S1096717619302824?via%3Dihub 
## focus on adipic acid samples
# data_dir = "/home/azureuser/Docs/ALE_nextflow/data/data_a_paper/sub_sample"  # adjust to your folder
data_dir = "/home/azureuser/Docs/ALE_nextflow/data/data_a_paper"  # adjust to your folder
spore_seq_dir = "/home/azureuser/Docs/ALE_nextflow/data/data_a_paper/spore_seq"  # spore seq data
out_dir = data_dir # adjust to your folder
out_file = "samplesheet_gen2.csv"
patient_field = "ALE_Exp1" # Patient field required by Sarek, for ALE it can be the experiment name "ALE_Exp1"
ploidty = 1  # Example ploidy, adjust as needed
clonal_or_population = "clonal"  # Example clonal or population, adjust as needed


# sample_name_map = {
#     "SubSampleCENPK113-7D-N": "A0-F0-I1-R1",
#     "SubSampleCENPK113-7D-O": "A0-F0-I2-R1",
#     "SubSampleA1-6" : "A1-F6-I1-R1",
#     "SubSampleA3-3" : "A3-F3-I1-R1",
#     "SubSampleA4-5" : "A4-F5-I1-R1",
#     "SubSampleA5-4" : "A5-F4-I1-R1",
#     "SubSampleA6-6" : "A6-F6-I1-R1",
#     # Add more mappings as needed
# }
sample_name_map = {
    # Main data files (bulk sequencing)
    "CENPK113-7D-N": "A0-F0-I1-R1",
    "CENPK113-7D-O": "A0-F0-I2-R1",
    "A1-6" : "A1-F6-I1-R1",
    "A3-3" : "A3-F3-I1-R1",
    "A4-5" : "A4-F5-I1-R1",
    "A5-4" : "A5-F4-I1-R1",
    "A6-6" : "A6-F6-I1-R1",
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
status_map = {
    "A0-F0-I1-R1": 0,  # Ancestral strain (normal)
    "A0-F0-I2-R1": 1,  # Ancestral strain replicate (normal), nf-sarek only takes on normal sample for each experiment(patient)
    # All evolved strains and spore seq samples default to status=1 (evolved)
}
sex = "XX" # Yeast has no sex chromosomes, but Sarek requires this field for controlfreec

# Regex patterns to match the filenames
# Pattern 1: Main data files (e.g., A1-6_S11_L001_R1_001.fastq.gz)
pattern_main = re.compile(r'(?P<sample>[A-Z0-9\-]+)_S\d+_L(?P<lane>\d{3})_R(?P<read>[12])_001\.fastq\.gz')
# Pattern 2: Spore seq files (e.g., Sp-A1-6-POS_S61_L001_R1_001.fastq.gz)
pattern_spore = re.compile(r'(?P<sample>Sp-[A-Z0-9\-]+-(?:POS|NEG))_S\d+_L(?P<lane>\d{3})_R(?P<read>[12])_001\.fastq\.gz')

samples = defaultdict(lambda: {"R1": None, "R2": None})

# Process main data directory (bulk sequencing)
print(f"Scanning main data directory: {data_dir}")
for f in os.listdir(data_dir):
    m = pattern_main.match(f)
    if not m: continue
    s, lane, r = m.group("sample"), m.group("lane"), m.group("read")
    key = (s, lane)
    samples[key][f"R{r}"] = os.path.join("../data/data_a_paper", f)
    print(f"  Found main data file: {f} -> sample={s}, lane={lane}, read=R{r}")

# Process spore_seq directory (recursive search)
print(f"\nScanning spore_seq directory: {spore_seq_dir}")
if os.path.exists(spore_seq_dir):
    for root, dirs, files in os.walk(spore_seq_dir):
        for f in files:
            if not f.endswith('.fastq.gz'): continue
            m = pattern_spore.match(f)
            if not m: continue
            s, lane, r = m.group("sample"), m.group("lane"), m.group("read")
            key = (s, lane)
            # Calculate relative path from data_dir to maintain consistent format with main data
            full_path = os.path.join(root, f)
            rel_path_from_data = os.path.relpath(full_path, data_dir)
            # Add the same prefix as main data files
            samples[key][f"R{r}"] = os.path.join("../data/data_a_paper", rel_path_from_data)
            print(f"  Found spore_seq file: {f} -> sample={s}, lane={lane}, read=R{r}")
else:
    print(f"  Warning: spore_seq directory not found: {spore_seq_dir}")

# Write CSV output
print(f"\n{'='*60}")
print(f"Writing samplesheet to: {out_dir}/{out_file}")
print(f"{'='*60}")

with open(f"{out_dir}/{out_file}", "w", newline="") as fh:
    w = csv.writer(fh)
    w.writerow(["experiment","sample","status","clonal_or_population","ploidy", "sex", "lane","fastq_1","fastq_2"])

    sample_count = 0
    for (sample_raw, lane), info in sorted(samples.items()):
        if not (info["R1"] and info["R2"]):
            print(f"  Warning: Skipping {sample_raw} (lane {lane}) - missing R1 or R2")
            continue

        # Map raw sample name to standardized format
        sample_mapped = sample_name_map.get(sample_raw, sample_raw)

        # Determine status (0=normal/ancestral, 1=evolved/treated)
        status = status_map.get(sample_mapped, 1)

        # Determine clonal_or_population: spore seq samples are "population", bulk samples are "clonal"
        if sample_raw.startswith("Sp-"):
            sample_type = "population"  # Spore seq samples are population-based
        else:
            sample_type = clonal_or_population  # Bulk samples use default (clonal)

        # Log unmapped samples
        if sample_raw not in sample_name_map:
            print(f"  Warning: Sample '{sample_raw}' not found in sample_name_map, using as-is")
        if sample_mapped not in status_map and sample_mapped not in ["A0-F0-I1-R1", "A0-F0-I2-R1"]:
            print(f"  Info: Sample '{sample_mapped}' not in status_map, defaulting to status=1 (evolved)")

        w.writerow([patient_field, sample_mapped, status, sample_type, ploidty, sex, f"L{lane}", info["R1"], info["R2"]])
        sample_count += 1

print(f"\n{'='*60}")
print(f"Summary:")
print(f"  Total samples processed: {sample_count}")
print(f"  Output file: {out_dir}/{out_file}")
print(f"{'='*60}")