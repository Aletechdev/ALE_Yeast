
# /data/ #/Users/zhlia/Documents/GitRepo/NF_ALE/data/BakerYeast_reference/
# ├─ snpeff_cache/
# │  ├─ draft_ref.52/
# │  │  ├─ snpEff.config
# │  │  ├─ genome.fa
# │  │  ├─ genes.gff
# ├─ vep_cache/
# │  ├─ Saccharomyces_cerevisiae/
# │  │  ├─ 52_draft/

data_folder="/Users/zhlia/Documents/GitRepo/NF_ALE/data/BakerYeast_reference"
species="Saccharomyces_cerevisiae"
genome_name="draft_ref"
version="52"


# build for SnpEff:
# source: https://pcingola.github.io/SnpEff/snpeff/build_db/#step-1-configure-a-new-genome 

snpEff_cache_folder="${data_folder}/snpeff_cache"
mkdir -p "${snpEff_cache_folder}"
# for snpEff build
snpeff_data_folder="${snpEff_cache_folder}/data/${genome_name}.${version}"
mkdir -p "${snpeff_data_folder}"
# empty folder for sarek input check
snpEff_genome_folder="${snpEff_cache_folder}/${genome_name}.${version}"
mkdir -p "${snpEff_genome_folder}"

#step 1: configure a new genome
echo "# ${species} genome ${genome_name}, version ${version}" > "${snpEff_cache_folder}/snpEff.config"
# echo "${genome_name}.${version} : ${species}" >> "${snpEff_cache_folder}/snpEff.config"
echo "${genome_name}.${version}.genome : ${genome_name}.${version}" >> "${snpEff_cache_folder}/snpEff.config"
cp "${data_folder}/draft_ref52.gff3" "${snpeff_data_folder}/draft_ref52.gff3"
# for genes.gff file, if the third column=="source", remove it
#quick clean up gff file:
awk -F'\t' '$3 != "source"' "${snpeff_data_folder}/draft_ref52.gff3" > "${snpeff_data_folder}/genes.gff"

docker run --rm -v ${snpEff_cache_folder}:/data -w /data quay.io/biocontainers/snpeff:5.1--hdfd78af_2 snpEff build -gff3 -v draft_ref.52 -noCheckCds -noCheckProtein
# need to make another 2 folder to pass Sarek input check null.${genome_name}.${version} (empty folder) and format for SnpEff ${genome_name}.${version}.${genome_name}.${version} (with snpEffect.config: draft_ref.52.draft_ref.52.genome)
mkdir -p "${snpEff_cache_folder}/null.${genome_name}.${version}"
cp -r  "${snpeff_data_folder}" "${snpEff_cache_folder}/${genome_name}.${version}.${genome_name}.${version}"
# echo "${genome_name}.${version}.${genome_name}.${version}.genome : ${genome_name}.${version}" >> "${snpEff_cache_folder}/${genome_name}.${version}.${genome_name}.${version}/snpEff.config"
echo "${genome_name}.${version}.genome : ${genome_name}.${version}" >> "${snpEff_cache_folder}/${genome_name}.${version}.${genome_name}.${version}/snpEff.config"

####
# # build for VEP:
# vep_cache_folder="${data_folder}/vep_cache/${species}/${version}_${genome_name}/"
# mkdir -p "${vep_cache_folder}"

# use the snpEff cache folder as the input for nf-core Sarek pipeline:
# nextflow run nf-core/sarek -r 3.4.0 -profile docker --input /Users/zhlia/Documents/GitRepo/tmp_NF_AMP/data/dicarboxylic_acids/data_a_test/sub_sample/samplesheet.csv --outdir /Users/zhlia/Documents/GitRepo/tmp_NF_AMP/output  --genome draft_ref.52 --igenomes_ignore --fasta /Users/zhlia/Documents/GitRepo/tmp_NF_AMP/data/BakerYeast_reference/draft_ref52.fasta --skip_tools baserecalibrator -c /Users/zhlia/Documents/GitRepo/tmp_NF_AMP/bin/nextflow.config --tools freebayes,mutect2,cnvkit,snpeff --split_fastq 0  --snpeff_cache /Users/zhlia/Documents/GitRepo/tmp_NF_AMP/data/BakerYeast_reference/snpeff_cache --snpeff_db draft_ref.52