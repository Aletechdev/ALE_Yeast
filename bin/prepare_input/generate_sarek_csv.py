import os, re, csv
from collections import defaultdict


# data_dir = "/home/azureuser/Docs/ALE_nextflow/data/data_a_paper/sub_sample"  # adjust to your folder
data_dir = "/home/azureuser/Docs/ALE_nextflow/data/data_a_paper"  # adjust to your folder
out_dir = data_dir # adjust to your folder
out_file = "samplesheet.csv"
patient_field = "ALE_Exp1" # Patient field required by Sarek, for ALE it can be the experiment name "ALE_Exp1"
ploidty = 2  # Example ploidy, adjust as needed
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
    "CENPK113-7D-N": "A0-F0-I1-R1",
    "CENPK113-7D-O": "A0-F0-I2-R1",
    "A1-6" : "A1-F6-I1-R1",
    "A3-3" : "A3-F3-I1-R1",
    "A4-5" : "A4-F5-I1-R1",
    "A5-4" : "A5-F4-I1-R1",
    "A6-6" : "A6-F6-I1-R1",
    # Add more mappings as needed
}
status_map = {
    "A0-F0-I1-R1": 0,  # one 'normal' sample per patient/experiment
    # "SubSampleCENPK113-7D-O": 0,  # Example status mapping, adjust as needed
}
sex = "XX" # Yeast has not sex chromosomes, but Sarek requires this field for controlfreec

# Regex pattern to match the filenames
# pattern = re.compile(r'(?P<sample>SubSample[A-Z0-9\-]+)_S\d+_L(?P<lane>\d{3})_R(?P<read>[12])_001\.fastq\.gz')
pattern = re.compile(r'(?P<sample>[A-Z0-9\-]+)_S\d+_L(?P<lane>\d{3})_R(?P<read>[12])_001\.fastq\.gz')
samples = defaultdict(lambda: {"R1": None, "R2": None})



for f in os.listdir(data_dir):
    m = pattern.match(f)
    if not m: continue
    s, lane, r = m.group("sample"), m.group("lane"), m.group("read")
    key = (s, lane)
    # samples[key][f"R{r}"] = os.path.join("../data/data_a_paper/sub_sample", f)
    samples[key][f"R{r}"] = os.path.join("../data/data_a_paper", f)

with open(f"{out_dir}/{out_file}", "w", newline="") as fh:
    w = csv.writer(fh)
    w.writerow(["experiment","sample","status","clonal_or_population","ploidy", "sex", "lane","fastq_1","fastq_2"])
    for (sample, lane), info in sorted(samples.items()):
        if not (info["R1"] and info["R2"]): continue
        # patient = sample.split('-')[0]  # e.g., 'A1' or 'B1'
        # patient = sample
        sample = sample_name_map.get(sample, sample)
        if sample not in status_map:
            print(f"Sample {sample} not found in status_map, defaulting to 1 (cancer/treated)")
        patient = "ALE_Exp1"
        status = status_map.get(sample, 1)  # Default to 1 if not found # Sarek treats 1 as cancer, 0 as normal
        w.writerow([patient, sample, status, clonal_or_population, ploidty, sex, f"L{lane}", info["R1"], info["R2"], ])