#!/usr/bin/env python
"""Compare a resumed QC-first run's outputs with a one-shot run's (tests/qc_gate.sh part b).

Two tiers of docs/dev-practices/output_comparison.md §3:
  * names   — the same set of files on both sides. pipeline_info/ is ignored (per-execution names);
              the resumed side may additionally hold the QC-only run's own MultiQC report and this
              test's marker files.
  * content — md5-identical for every file the e2e contract test snapshots by content (everything
              NOT matched by tests/.nftignore, the same glob rules), and record-identical (header
              lines `##…` stripped: they carry timestamps and command lines) for every .vcf / .vcf.gz.
              Everything else (gzip framing, renders, CRAMs) is out of scope here — the CRAMs are
              covered indirectly by the VCFs and cohort tables derived from them.

Usage: python tests/qc_gate_compare.py <reference_outdir> <resumed_outdir>   (exit 1 on any difference)
"""

import gzip
import hashlib
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
NFTIGNORE = REPO / "tests" / ".nftignore"

IGNORE_NAMES = ["pipeline_info/**"]
RESUMED_EXTRA_OK = [".qc_gate", ".qc_gate_session", ".qc_gate_trace_run1.txt", "qc_gate_run1.log", "qc_gate_run2.log",
                    "multiqc/*_multiqc_report.html", "multiqc/*_multiqc_report_data/**", "multiqc/*_multiqc_report_plots/**"]


def glob_to_regex(pattern: str) -> re.Pattern:
    """Java PathMatcher 'glob:' semantics as nf-test applies them: ** crosses '/', * and ? do not, {a,b} alternates."""
    out, i = "", 0
    while i < len(pattern):
        c = pattern[i]
        if pattern.startswith("**", i):
            out += ".*"; i += 2; continue
        if c == "*":
            out += "[^/]*"
        elif c == "?":
            out += "[^/]"
        elif c == "{":
            j = pattern.index("}", i)
            out += "(" + "|".join(re.escape(x) for x in pattern[i + 1:j].split(",")) + ")"
            i = j
        else:
            out += re.escape(c)
        i += 1
    return re.compile("^" + out + "$")


def load_patterns(path: Path) -> list[re.Pattern]:
    return [glob_to_regex(l.strip()) for l in path.read_text().splitlines() if l.strip() and not l.startswith("#")]


def matches(rel: str, patterns: list[re.Pattern]) -> bool:
    return any(p.match(rel) for p in patterns)


def files(root: Path) -> set[str]:
    return {p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()}


def md5(path: Path) -> str:
    h = hashlib.md5()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def vcf_records_md5(path: Path) -> str:
    opener = gzip.open if path.name.endswith(".gz") else open
    h = hashlib.md5()
    with opener(path, "rb") as f:
        for line in f:
            if not line.startswith(b"##"):
                h.update(line)
    return h.hexdigest()


def main() -> int:
    ref, res = Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve()
    ignore = [glob_to_regex(p) for p in IGNORE_NAMES]
    extra_ok = [glob_to_regex(p) for p in RESUMED_EXTRA_OK]
    nftignore = load_patterns(NFTIGNORE)

    ref_files = {f for f in files(ref) if not matches(f, ignore)}
    res_files = {f for f in files(res) if not matches(f, ignore) and not matches(f, extra_ok)}
    ok = True
    only_ref, only_res = sorted(ref_files - res_files), sorted(res_files - ref_files)
    if only_ref or only_res:
        ok = False
        for f in only_ref: print(f"NAME  only in reference: {f}")
        for f in only_res: print(f"NAME  only in resumed:   {f}")
    print(f"names: {len(ref_files & res_files)} common, {len(only_ref)} only-reference, {len(only_res)} only-resumed")

    n_md5 = n_vcf = n_skip = 0
    for f in sorted(ref_files & res_files):
        if f.endswith((".vcf", ".vcf.gz")):
            a, b = vcf_records_md5(ref / f), vcf_records_md5(res / f); n_vcf += 1; kind = "VCF records"
        elif not matches(f, nftignore):
            a, b = md5(ref / f), md5(res / f); n_md5 += 1; kind = "md5"
        else:
            n_skip += 1; continue
        if a != b:
            ok = False
            print(f"DIFF  {kind}: {f}")
    print(f"content: {n_md5} files md5-identical checked, {n_vcf} VCFs record-checked, {n_skip} skipped (tests/.nftignore classes)")
    print("qc_gate_compare: " + ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
