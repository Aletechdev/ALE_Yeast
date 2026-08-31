#!/bin/bash
set -euo pipefail
B=$(cd $(dirname $0) && pwd)
SV=quay.io/biocontainers/mulled-v2-375a758a4ca8c128fb9d38047a68a9f4322d2acd:b3615e06ef17566f2988a215ce9e10808c1d08bf-0
JA=quay.io/biocontainers/jasminesv:1.1.5--hdfd78af_0
for D in test2 pilot4; do
  cd $B/$D; rm -rf svdb jasmine; mkdir -p svdb jasmine
  svdb() { docker run --rm -v $B/$D:/d -w /d $SV svdb "$@"; }
  jas()  { docker run --rm -v $B/$D:/d -w /d $JA jasmine "$@"; }
  bcft() { docker run --rm -v $B/$D:/d -w /d $SV bcftools "$@"; }
  T=$(ls in/*.tiddit.vcf | sort)
  echo "=== $D: SVDB ==="; SECONDS=0
  # L1 TIDDIT across samples (columns appended in given order)
  svdb --merge --no_intra --vcf $T > svdb/tiddit_cohort.vcf 2> svdb/l1.err
  # raredisease-style L1: PASS-only inputs, --notag --pass_only
  for f in $T; do bcft view --apply-filters .,PASS -Ov -o svdb/$(basename $f .vcf).passin.vcf $f; done
  svdb --merge --notag --pass_only --vcf $(ls svdb/*.passin.vcf | sort) > svdb/tiddit_cohort_rd.vcf 2> svdb/l1rd.err || echo "rd-style L1 failed (see l1rd.err)"
  # L2 cross-caller
  svdb --merge --no_intra --same_order --priority manta,tiddit --vcf in/joint_manta.vcf:manta svdb/tiddit_cohort.vcf:tiddit > svdb/cohort_union.vcf 2> svdb/l2.err
  svdb --merge --no_intra --same_order --pass_only --priority manta,tiddit --vcf in/joint_manta.vcf:manta svdb/tiddit_cohort.vcf:tiddit > svdb/cohort_pass.vcf 2>> svdb/l2.err
  # BND pre-collapse variant
  python $B/collapse_bnd.py in/joint_manta.vcf > svdb/joint_manta_bndcollapsed.vcf
  svdb --merge --no_intra --same_order --priority manta,tiddit --vcf svdb/joint_manta_bndcollapsed.vcf:manta svdb/tiddit_cohort.vcf:tiddit > svdb/cohort_union_bndcollapsed.vcf 2>> svdb/l2.err
  # --no_var variant (cross-type allowed) for reference
  svdb --merge --no_intra --same_order --no_var --priority manta,tiddit --vcf in/joint_manta.vcf:manta svdb/tiddit_cohort.vcf:tiddit > svdb/cohort_union_novar.vcf 2>> svdb/l2.err
  echo "svdb wall=${SECONDS}s"
  echo "=== $D: JASMINE ==="; SECONDS=0
  { echo in/joint_manta.vcf; for f in $T; do echo $f; done; } > jasmine/filelist.txt
  jas file_list=jasmine/filelist.txt out_file=jasmine/cohort_default.vcf out_dir=jasmine/tmp1 --output_genotypes > jasmine/j1.log 2>&1 || echo "jasmine default failed"
  jas file_list=jasmine/filelist.txt out_file=jasmine/cohort_1kb_normtype.vcf out_dir=jasmine/tmp2 max_dist=1000 --nonlinear_dist --normalize_type --output_genotypes > jasmine/j2.log 2>&1 || echo "jasmine normtype failed"
  jas file_list=jasmine/filelist.txt out_file=jasmine/cohort_1kb_ignoretype.vcf out_dir=jasmine/tmp3 max_dist=1000 --nonlinear_dist --ignore_type --output_genotypes > jasmine/j3.log 2>&1 || echo "jasmine ignoretype failed"
  echo "jasmine wall=${SECONDS}s"
done
