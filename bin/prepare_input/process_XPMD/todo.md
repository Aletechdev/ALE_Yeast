[DONE]the XPMD seems to be using an older version of template, e.g., no ploidty, maybe fix it by myself??

the fastq file name is not correct for Yeast_Methanoal, the is no -R, be careful, maybe fix them before and communicate the changes?
    should be ok fix, by comparing the _S[][] ==> compare /home/azureuser/Docs/ALE_nextflow/data/Yeast_methanol_RWTH/sequencing_data/Yeast_methanol_RWTH/Yeast Methanotrophic-NCYC495-9-46-1-1.csv, all -A and -B file are used???


also, for the freebayes filter, the diplody filter remove all mutations: `view -i 'GT[0] != '.' && GT[0] != '0/0' && GT[1] = '0/0' &&..`
TODO: change the GT filter to address for ploidy
