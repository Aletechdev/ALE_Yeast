# ALE Yeast Test Run
# Uses azureD4as for resources, test_ALE_Yeast for test parameters, docker for containers
run_folder="/home/azureuser/Docs/ALE_nextflow"

nextflow run ./nf-core-sarek_3.5.1/3_5_1/main.nf \
    -c ${run_folder}/bin/nextflow.config \
    -profile azureD4as,test_ALE_Yeast,docker \
    -w ${run_folder}/work_test_run -resume
