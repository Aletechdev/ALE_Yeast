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
