#!/usr/bin/env python
"""Documentation consistency checks — run before cutting a release.

Two independent passes over every git-tracked (and untracked-but-not-ignored) .md file:

  links   markdown links `[text](target)` + reference definitions, resolved relative to the
          containing file. Reports targets that do not exist on disk. Should always be 0.

  paths   backticked repo paths (`conf/foo.config`, `modules/local/bar/main.nf`, …) that no
          longer exist. NOT expected to be 0 — historical notes, proposed designs, and
          deliberately-removed files all show up. Read the diff against the previous run
          rather than the absolute count.

Usage:
    python docs/dev-practices/check_docs.py              # both passes, repo root
    python docs/dev-practices/check_docs.py --mode links
    python docs/dev-practices/check_docs.py --root /path/to/repo

Exit status is non-zero only when the `links` pass finds a broken link, so this is safe to
wire into CI as a gate.  See docs/dev-practices/release_process.md.
"""
import argparse
import os
import re
import subprocess
import sys
from urllib.parse import unquote

INLINE_LINK = re.compile(r"\[[^\]\n]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
REF_DEF = re.compile(r"^\s{0,3}\[[^\]]+\]:\s*(\S+)", re.M)
FENCE = re.compile(r"```.*?```", re.S)
CODE_SPAN = re.compile(r"`([^`\n]+)`")
LINE_ANCHOR = re.compile(r":\d+(?:-\d+)?$")

EXTERNAL = ("http://", "https://", "mailto:", "ftp://", "#", "az://", "s3://", "tel:")

# top-level directories that are actually part of this repo
REPO_DIRS = (
    "bin/", "conf/", "docs/", "modules/", "subworkflows/", "workflows/", "assets/",
    "tests/", "containers/", "infra/", "data/", ".github/",
)
ROOT_FILES = (
    "main.nf", "nextflow.config", "nextflow_schema.json", "nf-test.config", "modules.json",
    "CHANGELOG.md", "CITATIONS.md", "CLAUDE.md", "README.md", "tower.yml",
    "generate_mutation_report.nf",
)
# archive/ documents history on purpose; stale paths there are expected
PATH_PASS_SKIP = ("docs/archive/",)


def markdown_files(root):
    out = subprocess.run(
        ["git", "-C", root, "ls-files", "--cached", "--others", "--exclude-standard", "*.md"],
        capture_output=True, text=True, check=True,
    ).stdout.split()
    return sorted(out)


def read(root, rel):
    with open(os.path.join(root, rel), encoding="utf-8", errors="replace") as fh:
        return fh.read()


def check_links(root, rel):
    text = FENCE.sub("", read(root, rel))
    bad = []
    for raw in INLINE_LINK.findall(text) + REF_DEF.findall(text):
        target = raw.strip()
        if not target or target.lower().startswith(EXTERNAL):
            continue
        target = unquote(target.split("#", 1)[0])
        if not target:
            continue
        if target.startswith("<") and target.endswith(">"):
            target = target[1:-1]
        base = root if target.startswith("/") else os.path.dirname(os.path.join(root, rel))
        resolved = os.path.normpath(os.path.join(base, target.lstrip("/")))
        if not os.path.exists(resolved):
            bad.append((None, raw))
    return bad


def repo_path_candidate(token):
    t = token.strip().strip(",;:").rstrip(".")
    if " " in t or "\t" in t:
        return None
    t = LINE_ANCHOR.sub("", t.split("#", 1)[0])   # drop #anchor and :123 / :12-34
    if "<" in t or ">" in t:
        return None                               # <placeholder> templates
    if t.startswith(("http", "az://", "s3://", "$", "-", "--")):
        return None
    if not (t.startswith(REPO_DIRS) or t in ROOT_FILES):
        return None
    return t


def path_exists(root, t):
    if any(ch in t for ch in "*?{}"):             # glob — check the literal prefix only
        base = t.split("*")[0].split("{")[0]
        base = base.rsplit("/", 1)[0] + "/" if "/" in base else base
        return os.path.exists(os.path.join(root, base))
    return os.path.exists(os.path.join(root, t))


def check_paths(root, rel):
    bad = []
    for lineno, line in enumerate(read(root, rel).splitlines(), 1):
        for token in CODE_SPAN.findall(line):
            candidate = repo_path_candidate(token)
            if candidate and not path_exists(root, candidate):
                bad.append((lineno, candidate))
    return bad


def run_pass(root, files, checker, title, skip=()):
    total = 0
    for rel in files:
        if rel.startswith(skip):
            continue
        findings = checker(root, rel)
        if findings:
            print(f"\n{rel}")
            for lineno, item in findings:
                where = f":{lineno}" if lineno else ""
                print(f"  {where:<7} {item}")
            total += len(findings)
    print(f"\n=== {title}: {total} finding(s) across {len(files)} markdown files ===")
    return total


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default=".", help="repo root (default: cwd)")
    ap.add_argument("--mode", choices=["links", "paths", "both"], default="both")
    args = ap.parse_args()

    root = os.path.abspath(args.root)
    files = markdown_files(root)
    broken_links = 0

    if args.mode in ("links", "both"):
        print("########## markdown links (must be 0) ##########")
        broken_links = run_pass(root, files, check_links, "broken links")

    if args.mode in ("paths", "both"):
        print("\n########## backticked repo paths (triage, not a gate) ##########")
        run_pass(root, files, check_paths, "missing paths", skip=PATH_PASS_SKIP)

    return 1 if broken_links else 0


if __name__ == "__main__":
    sys.exit(main())
