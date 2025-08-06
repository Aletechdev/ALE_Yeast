import os, re, csv
from collections import defaultdict


data_dir = "/home/azureuser/Docs/NF_ALE/data/data_a_paper/sub_sample"  # adjust to your folder
out_dir = data_dir # adjust to your folder
out_file = "samplesheet.csv"
patient_field = "ALE_Exp1" # Patient field required by Sarek, for ALE it can be the experiment name "ALE_Exp1"
ploidty = 2  # Example ploidy, adjust as needed
# Regex pattern to match the filenames
pattern = re.compile(r'(?P<sample>SubSample[A-Z0-9\-]+)_S\d+_L(?P<lane>\d{3})_R(?P<read>[12])_001\.fastq\.gz')
samples = defaultdict(lambda: {"R1": None, "R2": None})
status_map = {
    "SubSampleCENPK113-7D-N": 0,  # Example status mapping, adjust as needed
    # "SubSampleCENPK113-7D-O": 0,  # Example status mapping, adjust as needed
}

for f in os.listdir(data_dir):
    m = pattern.match(f)
    if not m: continue
    s, lane, r = m.group("sample"), m.group("lane"), m.group("read")
    key = (s, lane)
    samples[key][f"R{r}"] = os.path.join(data_dir, f)

with open(f"{out_dir}/{out_file}", "w", newline="") as fh:
    w = csv.writer(fh)
    w.writerow(["patient","sample","lane","fastq_1","fastq_2","status","sex","ploidy"])
    for (sample, lane), info in sorted(samples.items()):
        if not (info["R1"] and info["R2"]): continue
        # patient = sample.split('-')[0]  # e.g., 'A1' or 'B1'
        # patient = sample
        patient = "ALE_Exp1"
        status = status_map.get(sample, 1)  # Default to 1 if not found # Sarek treats 1 as cancer, 0 as normal
        w.writerow([patient, sample, f"L{lane}", info["R1"], info["R2"], status, "NA", ploidty])