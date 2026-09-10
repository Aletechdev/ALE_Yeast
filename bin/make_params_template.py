#!/usr/bin/env python
"""Generate docs/usage/params_template.yml — the launch-form parameters as a params file.

The template is GENERATED, never hand-edited: run this script after any change to the schema
overlay (conf/schema_overlay.yml → nextflow_schema.json) or to the ottilie calling recipe
(conf/test/ottilie_common.config), and commit the result together with the change. `--check`
verifies the committed template matches what the script would produce (CI/pre-commit).

What goes in, and where it comes from:
  * every parameter that is VISIBLE on the launch form (`hidden` not set in nextflow_schema.json),
    grouped and ordered exactly as the form shows them (the overlay's group_order/property_order),
    each at its schema default with the first sentence of its description as a trailing comment;
  * the Tier-1 calling recipe from conf/test/ottilie_common.config, applied on top of the schema
    defaults — the recipe file is parsed rather than copied, so it stays the single source
    (docs/dev-practices/testing_best_practices.md: four copies of one tool list is how runs
    silently diverged before that file existed);
  * a trailing block for the recipe parameters that are HIDDEN on the form but required for a
    Tier-1 run (skip_tools = baserecalibrator, and the iGenomes opt-out) — a visible-only params
    file would abort at the BaseRecalibrator join;
  * dataset-specific parameters left at null and marked `<-- SET`.

Usage:
    python bin/make_params_template.py            # rewrite docs/usage/params_template.yml
    python bin/make_params_template.py --check    # exit 1 if the committed template is stale
"""

import argparse
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCHEMA = REPO_ROOT / "nextflow_schema.json"
RECIPE = REPO_ROOT / "conf" / "test" / "ottilie_common.config"
TEMPLATE = REPO_ROOT / "docs" / "usage" / "params_template.yml"

# Parameters whose value is the dataset, not the recipe: emitted as null and flagged.
DATASET = {
    "input": "samplesheet CSV — absolute paths inside (docs/usage/input_samplesheet.md)",
    "outdir": "a NEW directory per run; publishDir overwrites but never deletes",
    "fasta": "reference FASTA (docs/usage/prepare_reference.md)",
    "snpeff_cache": "a DIRECTORY (local, az://, s3:// or gs://), not a .tar.gz",
    "snpeff_db": "the <db> directory name inside snpeff_cache",
    "report_gff3": "gene track for the mutation report; optional",
}

# Recipe parameters that the form hides but a Tier-1 run needs. Comments are the reason.
HIDDEN_RECIPE = {
    "skip_tools": "REQUIRED on a custom genome — BaseRecalibrator needs known-sites VCFs; omitting this aborts the run",
    "genome": "no iGenomes genome; the FASTA above is the reference",
    "igenomes_ignore": "do not load the iGenomes config",
    "split_haplotypecaller_joint_vcf": "per-sample VCFs from the joint HaplotypeCaller call (a Tier-1 deliverable)",
    "split_fastq": "no FASTQ sharding — keeps the task graph identical between runs",
}


def load_schema() -> dict:
    schema = json.loads(SCHEMA.read_text())
    return schema.get("$defs") or schema.get("definitions") or {}


def load_recipe() -> dict:
    """The `key = value` lines of ottilie_common.config's params block, as Python values."""
    text = RECIPE.read_text()
    block = re.search(r"^params \{(.*?)^\}", text, re.S | re.M)
    if not block:
        sys.exit(f"FATAL: no params block in {RECIPE}")
    recipe = {}
    for key, raw in re.findall(r"^\s*(\w+)\s*=\s*(.+?)\s*(?://.*)?$", block.group(1), re.M):
        raw = raw.strip()
        if raw == "null":
            recipe[key] = None
        elif raw in ("true", "false"):
            recipe[key] = raw == "true"
        elif re.fullmatch(r"-?\d+", raw):
            recipe[key] = int(raw)
        elif raw[0] == raw[-1] and raw[0] in "'\"":
            recipe[key] = raw[1:-1]
        else:
            sys.exit(f"FATAL: cannot parse recipe value {key} = {raw}")
    return recipe


def yaml_value(value) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    return json.dumps(value)


def first_sentence(text: str) -> str:
    text = (text or "").strip().split("\n")[0]
    match = re.match(r"(.+?\.)(\s|$)", text)
    return (match.group(1) if match else text).strip()


def render_block(rows: list[tuple[str, str, str]]) -> list[str]:
    """rows = (key, value, comment) → aligned `key: value  # comment` lines."""
    width = max(len(k) + 2 + len(v) for k, v, _ in rows)
    return [f"{k}: {v}".ljust(width) + (f"  # {c}" if c else "") for k, v, c in rows]


def build() -> str:
    groups = load_schema()
    recipe = load_recipe()
    out = [
        "# yAMP params file template — every launch-form field, in launch-form order, plus the",
        "# hidden parameters a Tier-1 run needs. Recipe values come from conf/test/ottilie_common.config",
        "# (the validated ALE recipe); everything else is at its pipeline default.",
        "#",
        "# GENERATED by bin/make_params_template.py — do not edit here. Copy it, fill the `<-- SET`",
        "# lines, delete what you leave at default, and launch with `-params-file <copy>.yml`",
        "# (or upload it in the Seqera launch form). How to use it, precedence and the traps:",
        "# docs/usage/launch_params_file.md",
        "#",
        "# `null` here is a real null (unset). On the command line `--x null` is the STRING 'null'.",
    ]
    seen = set()
    for group in groups.values():
        rows = []
        for name, prop in (group.get("properties") or {}).items():
            if prop.get("hidden"):
                continue
            seen.add(name)
            if name in DATASET:
                rows.append((name, "null", f"<-- SET  {DATASET[name]}"))
                continue
            value = recipe[name] if name in recipe else prop.get("default")
            comment = first_sentence(prop.get("description"))
            if name in recipe and recipe[name] != prop.get("default"):
                comment = f"(Tier-1 recipe) {comment}"
            rows.append((name, yaml_value(value), comment))
        if rows:
            out += ["", f"# ===== {group.get('title')} =====", *render_block(rows)]

    missing = [n for n in DATASET if n not in seen]
    if missing:
        sys.exit(f"FATAL: dataset parameter(s) no longer visible on the form: {missing}")
    rows = []
    for name, why in HIDDEN_RECIPE.items():
        if name not in recipe:
            sys.exit(f"FATAL: {name} is not set in {RECIPE.name}; update HIDDEN_RECIPE")
        rows.append((name, yaml_value(recipe[name]), why))
    out += ["", "# ===== Hidden on the launch form, but part of every Tier-1 run =====", *render_block(rows)]
    return "\n".join(out) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--check", action="store_true", help="verify the committed template is current")
    args = parser.parse_args()
    rendered = build()
    if args.check:
        current = TEMPLATE.read_text() if TEMPLATE.exists() else ""
        if current != rendered:
            print(f"STALE: {TEMPLATE.relative_to(REPO_ROOT)} — run bin/make_params_template.py", file=sys.stderr)
            return 1
        print(f"OK: {TEMPLATE.relative_to(REPO_ROOT)} is current")
        return 0
    TEMPLATE.write_text(rendered)
    print(f"wrote {TEMPLATE.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
