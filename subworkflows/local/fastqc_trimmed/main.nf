//
// FASTQC_TRIMMED: FastQC on the fastp output — the reads that are actually aligned. The upstream
// FASTQC call sees only the input FASTQs, so trimming results were visible nowhere but fastp's own
// report (docs/dev-practices/fastq_preprocessing_audit.md, finding F).
//
// One FastQC report per mate per lane in both fastp modes, named <id>_trimmed_{1,2}:
//   - unsplit (split_fastq = 0): FASTP emits the pair, FastQC runs on it directly;
//   - split   (split_fastq > 0): FASTP emits every shard of the lane (0001.<id>_1.fastp.fastq.gz,
//     0001.<id>_2..., 0002...) and FastQC reports per FILE, so the shards are concatenated per mate
//     first (CAT_FASTQ) — a per-shard report would neither describe the lane nor merge in MultiQC.
// MultiQC shows the reports as a second FastQC section beside the raw one and strips `_trimmed` from
// the sample name, so raw and trimmed columns share a General Stats row (assets/multiqc_config.yml).
// Nothing downstream consumes these outputs: adding or skipping them changes no other task's hash.
//

include { CAT_FASTQ as CAT_FASTQ_TRIMMED } from '../../../modules/nf-core/cat/fastq/main'
include { FASTQC    as FASTQC_TRIMMED    } from '../../../modules/nf-core/fastqc/main'

workflow FASTQC_TRIMMED_QC {
    take:
    reads    // channel: [ meta, fastq(s) ] — FASTP.out.reads: the lane's pair, or all of its shards
    split    // boolean: params.split_fastq > 0 — the files are shards to concatenate per mate

    main:
    versions = Channel.empty()

    if (split) {
        // Sorted by name the shards alternate mates (0001.x_1, 0001.x_2, 0002.x_1, ...), which is the
        // even/odd convention CAT_FASTQ pairs on. A lone file (single-end, one shard) is wrapped.
        CAT_FASTQ_TRIMMED(reads.map { meta, files -> [ meta, (files instanceof List ? files : [ files ]).sort(false) { it.name } ] })
        reads_per_lane = CAT_FASTQ_TRIMMED.out.reads
        versions = versions.mix(CAT_FASTQ_TRIMMED.out.versions.first())
    } else {
        reads_per_lane = reads
    }

    FASTQC_TRIMMED(reads_per_lane)
    versions = versions.mix(FASTQC_TRIMMED.out.versions.first())

    emit:
    zip  = FASTQC_TRIMMED.out.zip   // channel: [ meta, [ zip(s) ] ] — for MultiQC
    html = FASTQC_TRIMMED.out.html  // channel: [ meta, [ html(s) ] ]
    versions                        // channel: [ versions.yml ]
}
