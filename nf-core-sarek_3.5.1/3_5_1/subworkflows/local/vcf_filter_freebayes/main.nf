//
// FreeBayes-specific VCF filtering subworkflow
//

include { BCFTOOLS_FILTER                    } from '../../../modules/nf-core/bcftools/filter/main'
include { BCFTOOLS_FILTER as BCFTOOLS_FILTER_HIGH_IMPACT } from '../../../modules/nf-core/bcftools/filter/main'
include { BCFTOOLS_QUERY                     } from '../../../modules/nf-core/bcftools/query/main'
include { TABIX_TABIX                        } from '../../../modules/nf-core/tabix/tabix/main'
include { TABIX_TABIX as TABIX_HIGH_IMPACT   } from '../../../modules/nf-core/tabix/tabix/main'

workflow VCF_FILTER_FREEBAYES {
    take:
    ch_vcf_tbi    // channel: [ val(meta), path(vcf), path(tbi) ]
    
    main:
    ch_versions = Channel.empty()
    
    // Filter FreeBayes VCFs only
    ch_freebayes_vcfs = ch_vcf_tbi.filter{ meta, vcf, tbi -> 
        meta.variantcaller == 'freebayes' || vcf.name.contains('freebayes')
    }
    
    // Apply basic quality filters for FreeBayes
    // FreeBayes-specific filters: QUAL>=20, DP>=10, AF>=0.05
    // Also filter out reference calls and low-confidence variants
    ch_freebayes_vcfs.map{ meta, vcf, tbi ->
        [meta + [id: "${meta.id}.${meta.variantcaller}.quality_filtered"], vcf, tbi]
    }.set{ ch_for_basic_filter }
    
    BCFTOOLS_FILTER(
        ch_for_basic_filter,
        []  // no regions file
    )
    
    ch_versions = ch_versions.mix(BCFTOOLS_FILTER.out.versions.first())
    
    // Index filtered VCFs
    TABIX_TABIX(BCFTOOLS_FILTER.out.vcf)
    ch_versions = ch_versions.mix(TABIX_TABIX.out.versions.first())
    
    // Create channel with filtered VCFs and their indices
    ch_filtered_vcfs = BCFTOOLS_FILTER.out.vcf.join(
        TABIX_TABIX.out.tbi, 
        failOnDuplicate: true, 
        failOnMismatch: true
    )
    
    // Extract high-impact variants for separate analysis
    ch_filtered_vcfs.map{ meta, vcf, tbi ->
        [meta + [id: "${meta.id}.high_impact"], vcf, tbi]
    }.set{ ch_for_high_impact_filter }
    
    BCFTOOLS_FILTER_HIGH_IMPACT(
        ch_for_high_impact_filter,
        []  // no regions file
    )
    
    TABIX_HIGH_IMPACT(BCFTOOLS_FILTER_HIGH_IMPACT.out.vcf)
    
    ch_high_impact_vcfs = BCFTOOLS_FILTER_HIGH_IMPACT.out.vcf.join(
        TABIX_HIGH_IMPACT.out.tbi,
        failOnDuplicate: true,
        failOnMismatch: true
    )
    
    // Extract variant summaries using bcftools query
    ch_filtered_vcfs.map{ meta, vcf, tbi ->
        [meta + [id: "${meta.id}.summary"], vcf]
    }.set{ ch_for_query }
    
    BCFTOOLS_QUERY(
        ch_for_query,
        [],  // no regions file
        [],  // no targets file  
        []   // no samples file
    )
    
    emit:
    vcf_filtered     = ch_filtered_vcfs           // channel: [ val(meta), path(vcf), path(tbi) ]
    vcf_high_impact  = ch_high_impact_vcfs        // channel: [ val(meta), path(vcf), path(tbi) ]
    summary          = BCFTOOLS_QUERY.out.output  // channel: [ val(meta), path(txt) ]
    versions         = ch_versions                // channel: [ path(versions.yml) ]
}