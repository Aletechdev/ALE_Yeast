#!/usr/bin/env python
"""Apply conf/schema_overlay.yml to nextflow_schema.json.

The schema is generated: upstream sarek schema + this overlay. On a sarek upgrade, take the
upstream schema wholesale and re-run this script; on any other day, edit the overlay, re-run,
commit both. `--check` verifies the committed schema matches the overlay (for CI/pre-commit).

Policy implemented here:
  * visible allowlist — every parameter NOT listed gets "hidden": true, listed ones have the
    key removed (upstream style for visible params). Parameters new in an upgrade are born hidden.
  * property_overrides — merged key-by-key into the named parameter's entry, wherever it lives.
  * a listed name missing from the schema warns (renamed/removed upstream) but does not fail.
"""

import argparse
import json
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
SCHEMA = REPO_ROOT / "nextflow_schema.json"
OVERLAY = REPO_ROOT / "conf" / "schema_overlay.yml"


def apply_overlay(schema: dict, overlay: dict) -> tuple[dict, list[str]]:
    warnings = []
    groups = schema.get("$defs") or schema.get("definitions") or {}
    visible = set(overlay.get("visible") or [])
    overrides = overlay.get("property_overrides") or {}

    seen = set()
    for group in groups.values():
        for name, prop in (group.get("properties") or {}).items():
            seen.add(name)
            if name in visible:
                prop.pop("hidden", None)
            else:
                prop["hidden"] = True
            if name in overrides:
                prop.update(overrides[name])

    for name in sorted(visible - seen):
        warnings.append(f"visible-list parameter not in schema (renamed/removed upstream?): {name}")
    for name in sorted(set(overrides) - seen):
        warnings.append(f"property_overrides parameter not in schema: {name}")

    # group_order: listed groups first, in that order; unlisted groups keep their original
    # relative order after them (a group new in an upgrade therefore lands at the end).
    order = overlay.get("group_order") or []
    if order and groups:
        defs_key = "$defs" if "$defs" in schema else "definitions"
        for name in sorted(set(order) - set(groups)):
            warnings.append(f"group_order group not in schema (renamed/removed upstream?): {name}")
        placed = [g for g in order if g in groups]
        rest = [g for g in groups if g not in placed]
        schema[defs_key] = {g: groups[g] for g in placed + rest}
        if isinstance(schema.get("allOf"), list):
            by_ref = {a.get("$ref", "").split("/")[-1]: a for a in schema["allOf"]}
            extras = [a for a in schema["allOf"] if a.get("$ref", "").split("/")[-1] not in schema[defs_key]]
            schema["allOf"] = [by_ref[g] for g in schema[defs_key] if g in by_ref] + extras
    return schema, warnings


def render(schema: dict) -> str:
    return json.dumps(schema, indent=4, ensure_ascii=False) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true",
                        help="verify nextflow_schema.json matches the overlay; exit 1 on drift")
    args = parser.parse_args()

    schema = json.loads(SCHEMA.read_text())
    overlay = yaml.safe_load(OVERLAY.read_text())
    schema, warnings = apply_overlay(schema, overlay)
    for w in warnings:
        print(f"WARNING: {w}", file=sys.stderr)

    expected = render(schema)
    if args.check:
        if SCHEMA.read_text() != expected:
            print(f"DRIFT: {SCHEMA.name} does not match {OVERLAY.name} — "
                  f"run `python bin/apply_schema_overlay.py` and commit the result.", file=sys.stderr)
            return 1
        print(f"OK: {SCHEMA.name} matches the overlay ({len(overlay.get('visible') or [])} visible parameters).")
        return 0

    SCHEMA.write_text(expected)
    n_hidden = sum(1 for g in (schema.get("$defs") or {}).values()
                   for p in (g.get("properties") or {}).values() if p.get("hidden"))
    n_total = sum(len(g.get("properties") or {}) for g in (schema.get("$defs") or {}).values())
    print(f"Wrote {SCHEMA.name}: {n_total - n_hidden} visible / {n_hidden} hidden parameters.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
