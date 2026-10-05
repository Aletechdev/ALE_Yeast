#!/usr/bin/env python
"""Apply conf/schema_overlay.yml to nextflow_schema.json.

The schema is generated: upstream sarek schema + this overlay. On a sarek upgrade, take the
upstream schema wholesale and re-run this script; on any other day, edit the overlay, re-run,
commit both. `--check` verifies the committed schema matches the overlay (for CI/pre-commit).

Policy implemented here:
  * visible allowlist — every parameter NOT listed gets "hidden": true, listed ones have the
    key removed (upstream style for visible params). Parameters new in an upgrade are born hidden.
  * property_overrides — merged key-by-key into the named parameter's entry, wherever it lives.
  * property_removals — per parameter, keys DELETED from its entry (e.g. an upstream `default` the
    fork must not carry; applied after property_overrides).
  * group_overrides — title/description merged into the named group.
  * group_removals — per group, keys DELETED from its entry (e.g. an upstream section `help_text`
    that belongs on one parameter; applied after group_overrides).
  * property_order — per group, listed parameters first in that order; the rest keep their order.
  * strip_description_backticks — backticks removed from the description of every visible
    parameter (the launch form prints that line as plain text; applied after property_overrides).
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
    removals = overlay.get("property_removals") or {}
    strip_backticks = bool(overlay.get("strip_description_backticks"))

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
            for key in removals.get(name) or []:
                prop.pop(key, None)
            if strip_backticks and name in visible and isinstance(prop.get("description"), str):
                prop["description"] = prop["description"].replace("`", "")

    for name in sorted(visible - seen):
        warnings.append(f"visible-list parameter not in schema (renamed/removed upstream?): {name}")
    for name in sorted(set(overrides) - seen):
        warnings.append(f"property_overrides parameter not in schema: {name}")
    for name in sorted(set(removals) - seen):
        warnings.append(f"property_removals parameter not in schema: {name}")

    # group_overrides: title/description text for groups the fork owns outright.
    for gname, over in (overlay.get("group_overrides") or {}).items():
        if gname in groups:
            groups[gname].update(over)
        else:
            warnings.append(f"group_overrides group not in schema: {gname}")

    # group_removals: keys deleted from a group's entry (the group-level twin of property_removals).
    for gname, keys in (overlay.get("group_removals") or {}).items():
        if gname not in groups:
            warnings.append(f"group_removals group not in schema: {gname}")
            continue
        for key in keys or []:
            groups[gname].pop(key, None)

    # property_order: per group, listed parameters first in that order; unlisted ones keep their
    # original relative order after them (a parameter new in an upgrade lands at the end).
    for gname, order_list in (overlay.get("property_order") or {}).items():
        if gname not in groups:
            warnings.append(f"property_order group not in schema: {gname}")
            continue
        props = groups[gname].get("properties") or {}
        for name in sorted(set(order_list) - set(props)):
            warnings.append(f"property_order parameter not in group {gname}: {name}")
        placed = [n for n in order_list if n in props]
        groups[gname]["properties"] = {n: props[n] for n in placed + [n for n in props if n not in placed]}

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
