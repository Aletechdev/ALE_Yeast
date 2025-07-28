import os, re, csv
from collections import defaultdict

run_dir = "/Users/zhlia/Documents/GitRepo/NF_ALE/data"
data_dir = f"{run_dir}/data_a_paper"  # adjust to your folder
out_dir = f"{run_dir}/data_a_paper"  # adjust to your folder

out_file = "samplesheet_m3.csv"
# This script generates a samplesheet for Sarek from fastq files in a specified directory.
# It assumes the fastq files are named in a specific format and organizes them by sample and lane.
# pattern = re.compile(r'(?P<sample>[A-Z]\d+-\d+)_S\d+_L(?P<lane>\d{3})_R(?P<read>[12])_001\.fastq\.gz')
pattern = re.compile(r'(?P<sample>[A-Z0-9\-]+)_S\d+_L(?P<lane>\d{3})_R(?P<read>[12])_001\.fastq\.gz')
samples = defaultdict(lambda: {"R1": None, "R2": None})
status_map = {
    "CENPK113-7D-N": 0,
    "CENPK113-7D-O": 0,
}
# sub_set_samples = ["A1-3", "A1-5", "A1-6"]  # Example subset of samples, adjust as needed
# sub_set_lanes = ["L001"]  # Example subset of lanes, adjust as needed

for f in os.listdir(data_dir):
    m = pattern.match(f)
    if not m: continue
    s, lane, r = m.group("sample"), m.group("lane"), m.group("read")
    key = (s, lane)
    samples[key][f"R{r}"] = os.path.join(data_dir, f)

with open(f"{out_dir}/{out_file}", "w", newline="") as fh:
    w = csv.writer(fh)
    w.writerow(["patient","sample","lane","fastq_1","fastq_2","status","sex"])
    for (sample, lane), info in sorted(samples.items()):
        if not (info["R1"] and info["R2"]): continue
        patient = sample.split('-')[0]  # e.g., 'A1' or 'B1' #TODO, set patient as ALE sample name?
        status = status_map.get(sample, 1)  # Default to 1 if not found # Sarek treats 1 as cancer, 0 as normal
        w.writerow([patient, sample, f"L{lane}", info["R1"], info["R2"], status, "NA"])