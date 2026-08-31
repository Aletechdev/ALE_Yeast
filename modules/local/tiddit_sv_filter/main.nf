// Manta-inspired soft filters for TIDDIT's PASS view (item 4, decided 2026-08-31).
//
// TIDDIT's own PASS is a single link-count check; Manta's is six orthogonal soft vetoes.
// This step adds three named tags to the FILTER column of the per-sample SV-merge input
// (--mode +, nothing removed): the pass VIEW then excludes them via the existing
// `-f PASS,.` pre-filter, while the union view keeps every record with its reason in
// tiddit_FILTERS. The published caller VCF (variant_calling/tiddit/) is untouched.
//
//   LowSupport  (~ Manta NoPairSupport / raredisease -p 6): DV+RV < 6
//   LowQual     (~ Manta MinQUAL, TIDDIT's 0-80 scale):     QUAL < 40
//   HighMQ0     (~ Manta MaxMQ0Frac):                       any-breakend LQ > 0.4
//
// Calibration on the 2026-08-31 pilot (truth set: no real SVs): removes 56/86 TIDDIT-only
// PASS rows, 0/6 Manta-corroborated rows affected. Thresholds live in
// conf/modules/mutation_report.config (ext.*) — tuning is a config change.
process TIDDIT_SV_FILTER {
    tag "$meta.id"
    label 'process_single'

    conda "${moduleDir}/../../nf-core/svdb/merge/environment.yml"
    container "${ workflow.containerEngine in ['singularity', 'apptainer'] && !task.ext.singularity_pull_docker_container ?
        'https://community-cr-prod.seqera.io/docker/registry/v2/blobs/sha256/f5/f59712ead354411dd8bea4918d777737ca4ef2ad1360289507fe35acb688e74f/data':
        'community.wave.seqera.io/library/bcftools_svdb:12db401acbacc624' }"

    input:
    tuple val(meta), path(vcf)

    output:
    tuple val(meta), path("${prefix}.vcf"), emit: vcf
    path "versions.yml"                   , emit: versions

    when:
    task.ext.when == null || task.ext.when

    script:
    prefix = task.ext.prefix ?: "${meta.id}.tiddit"
    def lowqual    = task.ext.lowqual    ?: 'QUAL<40'
    def lowsupport = task.ext.lowsupport ?: 'MAX(FMT/DV+FMT/RV)<6'
    def highmq0    = task.ext.highmq0    ?: 'MAX(FMT/LQ)>0.4'
    // Output name is load-bearing: svdb derives its provenance tags from the input
    // filename, so this must stay <sample>.tiddit.vcf (the collapse step's output is
    // therefore named .tiddit.collapsed.vcf to avoid a staging collision).
    """
    bcftools filter --soft-filter LowQual    --mode + --exclude '${lowqual}'    ${vcf} \\
        | bcftools filter --soft-filter LowSupport --mode + --exclude '${lowsupport}' - \\
        | bcftools filter --soft-filter HighMQ0    --mode + --exclude '${highmq0}'    - \\
        > ${prefix}.vcf

    cat <<-END_VERSIONS > versions.yml
    "${task.process}":
        bcftools: \$(bcftools --version 2>&1 | head -n1 | sed 's/^.*bcftools //; s/ .*\$//')
    END_VERSIONS
    """
}
