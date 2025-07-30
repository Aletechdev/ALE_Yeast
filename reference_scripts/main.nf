nextflow.enable.dsl=2

params.vcf_dir = "vcfs"
params.bed_dir = "beds"
params.out_dir = "intersected_vcfs"
params.freebayes_vcf_filter = 'QUAL>=20 && INFO/DP>=10'
params.manta_vcf_filter = 'PASS'

// include { MULTIQC } from './modules/nf-core/multiqc/main' // something wrong with the docker image..
// based on the results, check if the mutations from the paper is reported, and estimated the filter score for filtering

Channel
    .fromPath("${params.vcf_dir}/**/*.vcf.gz")
    .map { file ->
        def fname = file.getBaseName()
        def sample_id = fname.replaceFirst(/\.(freebayes|manta\.tumor_sv|mutect2\.filtered|manta\.diploid_sv)_snpEff\.ann\.vcf(?:\.gz)?$/, '')
        def caller = (fname =~ /\.(freebayes|manta\.tumor_sv|manta\.diploid_sv|mutect2\.filtered)_snpEff\.ann\.vcf/)[0][1]
        caller = caller.replaceAll(/\.tumor_sv|\.filtered/, '') // simplify names like 'manta'
        tuple(sample_id, caller, file)
    }
    .set { vcf_ch }
// vcf_ch.view()
Channel
    .fromPath("${params.bed_dir}/*.bed")
    .map { file ->
        def sample_id = file.getBaseName().replaceFirst(/\.bed$/, '')
        sample_id = sample_id.replaceFirst(/_codon_mutations$/, '') // remove suffixes like '_gene_mutations' or '_codon_mutations'
        sample_id = sample_id.replaceFirst(/\./, '-') // replace first dot with underscore
        tuple(sample_id, file)
    }
    .set { bed_ch }
// bed_ch.view()

vcf_ch
    .combine(bed_ch, by: 0) // combine vcf and bed channels, then filter by sample ID
    .set { matched_samples }


process filterVcf_freebayes {
    // input: vcf and a vcf filter string
    container 'quay.io/biocontainers/bcftools:1.22--h3a4d415_1'

    input:
    tuple val(sample), val(caller), path(vcf)
    output:
    tuple val(sample), val(caller), path("${sample}.${caller}_filtered.vcf.gz"), path("${sample}.${caller}_filtered.vcf.gz.tbi"), emit: vcf_ch
    path "${sample}.${caller}_filtered.bcftools_stats.txt", emit: vcf_stats
    publishDir "output/${caller}/filtered", mode: 'copy'
    script:
    """
    bcftools filter -i '${params.freebayes_vcf_filter}' $vcf -o ${sample}.${caller}_filtered.vcf.gz
    # index the filtered VCF file
    bcftools index --tbi ${sample}.${caller}_filtered.vcf.gz
    # bcftools stats:
    # TODO: add fasta-ref for Indels context
    bcftools stats ${sample}.${caller}_filtered.vcf.gz > ${sample}.${caller}_filtered.bcftools_stats.txt
    """

}

process MERGE_WILDTYPE {
    tag "Merging wildtype VCF files"
    container 'quay.io/biocontainers/bcftools:1.22--h3a4d415_1'

    publishDir "${params.outdir}/${caller}/merged", mode: 'copy'

    input:
    path vcfs_and_indices
    val caller

    output:
    path "merged_wildtype.vcf.gz", emit: merged_vcf
    path "merged_wildtype.vcf.gz.tbi", emit: merged_vcf_index
    path "merged_wildtype.bcftools_stats.txt", emit: vcf_stats

    when:

    script:
    // Extract VCF files (every other file is an index)
    """
    # Create list of VCF files (excluding .tbi files)
    find . -name "*.vcf.gz" ! -name "*.tbi" > vcf_list.txt

    # Merge all wildtype VCFs into a single file
    bcftools merge --file-list vcf_list.txt -Oz -o merged_wildtype.vcf.gz

    # Index the merged VCF file
    bcftools index --tbi merged_wildtype.vcf.gz

    # stats for the merged VCF
    bcftools stats merged_wildtype.vcf.gz > merged_wildtype.bcftools_stats.txt
    """
}

process SUBTRACT_VARIANTS {
    tag "Subtracting wildtype variants from ${sample_id}"
    container 'quay.io/biocontainers/bcftools:1.22--h3a4d415_1'

    publishDir "${params.outdir}/${caller}/subtracted", mode: 'copy'

    input:
    tuple val(sample_id), val(caller), path(exp_vcf), path(exp_vcf_index)
    path wildtype_vcf
    path wildtype_vcf_index

    output:
    tuple val(sample_id), val(caller), path("${sample_id}.${caller}.subtracted.vcf.gz"), path("${sample_id}.${caller}.subtracted.vcf.gz.tbi"), emit: subtracted_vcf
    path("${sample_id}.${caller}.subtracted.bcftools_stats.txt"), emit: vcf_stats

    script:
    """
    # Use bcftools isec to find variants unique to experimental sample (set difference)
    # -C means complement: output positions present only in the first file but not in the second
    bcftools isec -C -c none -p temp_dir ${exp_vcf} ${wildtype_vcf}

    # Compress and rename the output
    bcftools view -Oz -o ${sample_id}.${caller}.subtracted.vcf.gz temp_dir/0000.vcf

    # Index the output VCF
    bcftools index --tbi ${sample_id}.${caller}.subtracted.vcf.gz

    # stats for the subtracted VCF
    bcftools stats ${sample_id}.${caller}.subtracted.vcf.gz > ${sample_id}.${caller}.subtracted.bcftools_stats.txt
    """
}

process bedtoolsIntersect {
    tag "$sample ($caller)"
    container 'quay.io/biocontainers/bedtools:2.31.1--h13024bc_3'

    input:
    tuple val(sample), val(caller), path(vcf), path(vcf_index), path(bed)

    output:
    tuple val(sample), val(caller), path("${sample}.intersected.vcf"), path(vcf), emit: intersected_vcf

    // publishDir "${params.outdir}/${caller}", mode: 'copy'

    script:
    """
    bedtools intersect -a $vcf -b $bed -wa > ${sample}.intersected.vcf
    # sort by chromosome and position
    sort -k1,1 -k2,2n ${sample}.intersected.vcf -o ${sample}.intersected.vcf
    """
}

process VCF_addHeader_index {
    tag "$sample ($caller)"
    container 'quay.io/biocontainers/bcftools:1.22--h3a4d415_1'

    input:
    tuple val(sample), val(caller), path(intersected_vcf), path(vcf)

    output:
    tuple val(sample), val(caller), path("${sample}.${caller}_intersecte_knowSNP.vcf.gz"), path("${sample}.${caller}_intersecte_knowSNP.vcf.gz.tbi"), emit: vcf_intersecte_knowSNP
    path("${sample}.${caller}_intersecte_knowSNP.bcftools_stats.txt"), emit: vcf_stats

    publishDir "${params.outdir}/${caller}/intersected", mode: 'copy'

    script:
    """
    bcftools view --header-only $vcf > ${sample}.${caller}_header.txt
    # Reheader the intersected VCF with the original VCF header
    cat ${sample}.${caller}_header.txt $intersected_vcf > ${sample}.${caller}_intersecte_knowSNP.vcf
    # Compress the VCF file
    bgzip ${sample}.${caller}_intersecte_knowSNP.vcf
    # Index the VCF file
    bcftools index --tbi ${sample}.${caller}_intersecte_knowSNP.vcf.gz

    # stats for the VCF with header
    bcftools stats ${sample}.${caller}_intersecte_knowSNP.vcf.gz > ${sample}.${caller}_intersecte_knowSNP.bcftools_stats.txt
    """
}



process multiqc_report {
    container 'multiqc/multiqc:v1.30'

    input:
    path(stats)
    val(caller)

    output:
    path("multiqc_report.html")
    
    publishDir "${params.outdir}/${caller}/multiqc", mode: 'copy'

    script:
    """
    multiqc $stats -o . --force
    """
}

// process extract_vcf_gene_mutations {
//     tag "$sample ($caller)"
//     container 'quay.io/biocontainers/snpsift:4.2--py27_1'

//     input:
//     tuple val(sample), val(caller), path(vcf), path(vcf_index)

//     output:
//     path("${sample}.${caller}_gene_mutations.txt")

//     script:
//     """
//     SnpSift extractFields -s "," -e "." $vcf CHROM POS REF ALT AO RO DPB 'ANN[*].GENE' 'ANN[*].HGVS_P' > ${sample}.${caller}_gene_mutations.txt
//     # The above command extracts the fields: CHROM, POS, REF, ALT, AO (Alternate Observations), RO (Reference Observations), DPB (Depth of Base), and the gene annotations (GENE and HGVS_P) from the VCF file.
//     """
// }

process SnpSift_tsv{
    tag "$sample ($caller)"
    container 'quay.io/biocontainers/snpsift:4.2--py27_1'
    publishDir "${params.outdir}/${caller}/SnpSift", mode: 'copy'

    input:
    tuple val(sample), val(caller), path(vcf), path(vcf_index)

    output:
    tuple val(sample), val(caller), path("${sample}.${caller}_geneID_mutation.tsv")

    script:
    """
    SnpSift extractFields -s "," -e "." $vcf CHROM POS REF ALT AO RO DPB 'ANN[*].GENE' 'ANN[*].HGVS_P' > ${sample}.${caller}_geneID_mutation.tsv
    """
}

process addGene_name {
    input:
    tuple val(sample), val(caller), path(mutation_table)
    path(gene_info)
    output:
    tuple val(sample), val(caller), path("${sample}.${caller}_geneID_mutation_addName.tsv")
    publishDir "${params.outdir}/${caller}/SnpSift", mode: 'copy'

    script:
    """
    awk -F'\\t' '
        NR==FNR { map[\$1]=\$2; next }               # read gene_info into array map[key]=value
        {
            n = split(\$8, a, / *, */)                # split column 8 by comma (with optional spaces)
            for (i=1; i<=n; i++) {
                if (a[i] in map) a[i] = map[a[i]]     # if token exists in map, replace it
            }
            \$8 = a[1]
            for (i=2; i<=n; i++) \$8 = \$8 "," a[i]   # rebuild column 8
            print \$1, \$2, \$3, \$4, \$5, \$6, \$7, \$8, \$9                       # reference \$1, \$2, and \$8 explicitly
        }
    ' OFS='\\t' $gene_info $mutation_table > ${sample}.${caller}_geneID_mutation_addName.tsv
    """
}

workflow {
    // working with  freebayes VCFs:

    filtered_freebayes_ch = filterVcf_freebayes(vcf_ch.filter { it[1] == 'freebayes' })
    // filtered_freebayes_ch.vcf_ch.view()

    // if filtered_freebayes_ch.vcf_ch[0] equal to CENPK113-7D-N or CENPK113-7D-O, split the channel into two separate channels
    def control_samples = filtered_freebayes_ch.vcf_ch.filter { it[0] == 'CENPK113-7D-N' || it[0] == 'CENPK113-7D-O' }
    def treated_samples = filtered_freebayes_ch.vcf_ch.filter { it[0] != 'CENPK113-7D-N' && it[0] != 'CENPK113-7D-O' }

    // control_samples.view()
    // treated_samples.view()
    control_samples_vcf_with_index = control_samples.map{ tuple(it[2], it[3])} // create a channel with VCF files and their indices

    MERGE_WILDTYPE(control_samples_vcf_with_index.collect(), 'freebayes')

    SUBTRACT_VARIANTS(
        treated_samples,
        MERGE_WILDTYPE.out.merged_vcf,
        MERGE_WILDTYPE.out.merged_vcf_index
    )

    // SUBTRACT_VARIANTS.out.subtracted_vcf.view()
    SUBTRACT_VARIANTS.out.subtracted_vcf.combine(bed_ch, by: 0)
    .set { substracted_vcf_bed_ch }

    intersected_ch = bedtoolsIntersect(substracted_vcf_bed_ch)
    intersected_ch.intersected_vcf.view()

    VCF_addHeader_index(
        intersected_ch.intersected_vcf
    )

    VCF_addHeader_index.out.vcf_stats.concat(SUBTRACT_VARIANTS.out.vcf_stats, MERGE_WILDTYPE.out.vcf_stats, filtered_freebayes_ch.vcf_stats).set { vcf_stats }
    multiqc_report(vcf_stats.collect(), 'freebayes')
    //, SUBTRACT_VARIANTS.vcf_stats

    SnpSift_tsv(
        VCF_addHeader_index.out.vcf_intersecte_knowSNP
    )

    addGene_name(SnpSift_tsv.out, params.gene_info)


    // stats_ch = filtered_freebayes_ch.map { it[4] }

    // Collect all stats file paths into one list
    // collected_stats = stats_ch.collect()


    // Run the MULTIQC module, could not get it to work,
    // there is a bug with no docker container for multiqc:1.30
    // MULTIQC(collected_stats, [], [], [], [], [])

    // Continue with the rest of your workflow TODO: use the filtered VCFs
    // bedtoolsIntersect(matched_samples)
}