#!/usr/bin/env python
"""
Phase 2a Prototype: Mutation Overview Report Generator

Reads pilot CSVs from data/ and generates a self-contained HTML dashboard
with CN heatmaps, CN region tables, and SV event matrices using Tabulator.js.

Usage:
    python generate_prototype.py
    python generate_prototype.py --data-dir data/ --output mutation_overview.html
"""

import argparse
import csv
import json
from pathlib import Path


def load_csv(path: Path) -> list[dict]:
    """Load a CSV file into a list of dicts."""
    with open(path) as f:
        return list(csv.DictReader(f))


def get_sample_columns(headers: list[str], suffix: str) -> list[str]:
    """Extract sample names from column headers ending with a given suffix."""
    samples = []
    for h in headers:
        if h.endswith(suffix):
            name = h[: -len(suffix)]
            if name not in samples:
                samples.append(name)
    return samples


def load_cn_chr(path: Path) -> dict:
    """Load chromosome-level CN summary. Returns {rows, samples, row_count}."""
    rows = load_csv(path)
    if not rows:
        return {"rows": [], "samples": [], "row_count": 0}
    samples = get_sample_columns(list(rows[0].keys()), "_diploid_cn")
    out = []
    for r in rows:
        entry = {
            "chromosome": r["chromosome"],
            "length": int(r.get("length", 0)),
        }
        for s in samples:
            cn_raw = r.get(f"{s}_diploid_cn", "2")
            # Handle asterisk annotation (e.g. "2*" means CI overlap)
            cn_clean = cn_raw.rstrip("*")
            entry[f"{s}_cn"] = int(cn_clean) if cn_clean else 2
            entry[f"{s}_log2"] = float(r.get(f"{s}_log2", 0))
            entry[f"{s}_abs"] = float(r.get(f"{s}_absolute_cn", 0))
            entry[f"{s}_note"] = "*" if cn_raw.endswith("*") else ""
        out.append(entry)
    return {"rows": out, "samples": samples, "row_count": len(out)}


def load_cn_regions(path: Path) -> dict:
    """Load collapsed CN region matrix. Returns {rows, samples, row_count}."""
    rows = load_csv(path)
    if not rows:
        return {"rows": [], "samples": [], "row_count": 0}
    samples = get_sample_columns(list(rows[0].keys()), "_diploid_cn")
    out = []
    for r in rows:
        span = 0
        try:
            span = int(r.get("end", 0)) - int(r.get("start", 0))
        except (ValueError, TypeError):
            pass
        entry = {
            "chromosome": r["chromosome"],
            "start": int(r.get("start", 0)),
            "end": int(r.get("end", 0)),
            "span_kb": round(span / 1000, 1),
        }
        for s in samples:
            entry[f"{s}_cn"] = int(r.get(f"{s}_diploid_cn", 2))
            entry[f"{s}_log2"] = float(r.get(f"{s}_log2", 0))
        out.append(entry)
    return {"rows": out, "samples": samples, "row_count": len(out)}


def load_sv_matrix(path: Path) -> dict:
    """Load SV cohort matrix. Returns {rows, samples, row_count}."""
    rows = load_csv(path)
    if not rows:
        return {"rows": [], "samples": [], "row_count": 0}
    fixed_cols = {"chrom", "pos", "chrom2", "end", "svtype", "svlen"}
    samples = [h for h in rows[0].keys() if h not in fixed_cols]
    out = []
    for r in rows:
        entry = {
            "chrom": r["chrom"],
            "pos": int(r.get("pos", 0)),
            "chrom2": r.get("chrom2", ""),
            "end": int(r.get("end", 0)),
            "svtype": r.get("svtype", ""),
            "svlen": int(r.get("svlen", 0)),
        }
        for s in samples:
            entry[s] = r.get(s, "-")
        out.append(entry)
    return {"rows": out, "samples": samples, "row_count": len(out)}


def compute_summary(cn_sens, cn_str, sv_pass, sv_all) -> dict:
    """Compute summary card values."""
    samples = cn_sens["samples"]

    # CN agreement: count chr where sensitive == stringent for all samples
    agree = 0
    total = 0
    for rs, rt in zip(cn_sens["rows"], cn_str["rows"]):
        total += 1
        if all(rs.get(f"{s}_cn") == rt.get(f"{s}_cn") for s in samples):
            agree += 1
    agreement_pct = round(100 * agree / total, 1) if total else 0

    # CN changes: count cells where cn != 2
    cn_changes = 0
    for r in cn_sens["rows"]:
        for s in samples:
            if r.get(f"{s}_cn", 2) != 2:
                cn_changes += 1

    return {
        "n_samples": len(samples),
        "sv_all": sv_all["row_count"],
        "sv_pass": sv_pass["row_count"],
        "cn_changes": cn_changes,
        "cn_agreement_pct": agreement_pct,
    }


def generate_html(
    cn_chr_sens, cn_chr_str, cn_reg_sens, cn_reg_str, sv_pass, sv_all, summary
) -> str:
    """Generate the self-contained HTML dashboard."""
    samples = cn_chr_sens["samples"]
    sv_samples = sv_pass["samples"]

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="color-scheme" content="light">
    <title>Mutation Overview — Ottilie 4-Sample Pilot</title>
    <link href="https://unpkg.com/tabulator-tables@6.3.0/dist/css/tabulator.min.css" rel="stylesheet">
    <style>
        :root {{
            color-scheme: light;
            --bg: #ffffff; --fg: #333333; --fg-heading: #24292e; --fg-muted: #586069;
            --link: #0366d6; --border: #e1e4e8; --surface: #f6f8fa; --surface-alt: #fafbfc;
            --hover: #f0f1f3;
            --badge-pass-bg: #dcffe4; --badge-pass-fg: #22863a;
            --badge-warn-bg: #fff5b1; --badge-warn-fg: #735c0f;
            --badge-fail-bg: #ffeef0; --badge-fail-fg: #cb2431;
            --badge-na-bg: #f1f1f1; --badge-na-fg: #888888;
            --table-header-bg: #f6f8fa; --table-border: #e1e4e8;
            /* Caller badge colors */
            --caller-manta: #22863a; --caller-manta-bg: #dcffe4;
            --caller-tiddit: #0366d6; --caller-tiddit-bg: #dbedff;
            --caller-both: #6f42c1; --caller-both-bg: #f5f0ff;
        }}
        [data-theme="dark"] {{
            color-scheme: dark;
            --bg: #0d1117; --fg: #c9d1d9; --fg-heading: #e6edf3; --fg-muted: #8b949e;
            --link: #58a6ff; --border: #30363d; --surface: #161b22; --surface-alt: #1c2128;
            --hover: #2d333b;
            --badge-pass-bg: #1b3a2a; --badge-pass-fg: #56d364;
            --badge-warn-bg: #3b2e00; --badge-warn-fg: #e3b341;
            --badge-fail-bg: #3d1418; --badge-fail-fg: #f85149;
            --badge-na-bg: #21262d; --badge-na-fg: #8b949e;
            --table-header-bg: #1c2128; --table-border: #30363d;
            --caller-manta: #56d364; --caller-manta-bg: #1b3a2a;
            --caller-tiddit: #58a6ff; --caller-tiddit-bg: #0d2240;
            --caller-both: #a371f7; --caller-both-bg: #1a0f2e;
        }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
            max-width: 1400px; margin: 30px auto; padding: 0 20px;
            background: var(--bg); color: var(--fg);
        }}
        h1 {{ border-bottom: 2px solid var(--link); padding-bottom: 8px; color: var(--fg-heading); }}
        h2 {{ margin-top: 32px; color: var(--fg-heading); }}
        .note {{ color: var(--fg-muted); font-size: 0.9em; margin-top: 4px; }}
        a {{ color: var(--link); text-decoration: none; }}

        /* Summary cards */
        .cards {{ display: flex; gap: 16px; flex-wrap: wrap; margin: 20px 0; }}
        .card {{
            flex: 1; min-width: 150px; padding: 14px 18px;
            background: var(--surface); border: 1px solid var(--border); border-radius: 6px;
            border-left: 3px solid var(--link);
        }}
        .card .value {{ font-size: 1.8em; font-weight: 700; color: var(--fg-heading); }}
        .card .label {{ font-size: 0.85em; color: var(--fg-muted); margin-top: 2px; }}

        /* Tab bar */
        .tab-bar {{ display: flex; gap: 0; margin-top: 24px; border-bottom: 2px solid var(--border); }}
        .tab-btn {{
            padding: 8px 16px; cursor: pointer; border: none;
            background: transparent; color: var(--fg-muted); font-size: 0.9em; font-weight: 600;
            border-bottom: 2px solid transparent; margin-bottom: -2px;
        }}
        .tab-btn:hover {{ color: var(--fg); }}
        .tab-btn.active {{ color: var(--link); border-bottom-color: var(--link); }}
        .tab-panel {{ display: none; padding-top: 12px; }}
        .tab-panel.active {{ display: block; }}

        /* CN heatmap grid */
        .cn-grid {{ overflow-x: auto; }}
        .cn-grid table {{ border-collapse: collapse; font-size: 0.85em; width: 100%; }}
        .cn-grid th, .cn-grid td {{
            padding: 6px 10px; border: 1px solid var(--table-border); text-align: center;
        }}
        .cn-grid th {{ background: var(--table-header-bg); color: var(--fg); font-weight: 600; position: sticky; top: 0; }}
        .cn-grid td.chr {{ text-align: left; font-weight: 600; background: var(--surface); white-space: nowrap; }}
        .cn-grid td.len {{ text-align: right; color: var(--fg-muted); font-size: 0.9em; }}

        /* CN colors */
        .cn-loss {{ background: var(--badge-fail-bg); color: var(--badge-fail-fg); font-weight: 600; }}
        .cn-neutral {{ background: var(--bg); color: var(--fg-muted); }}
        .cn-gain {{ background: #dbedff; color: #0366d6; font-weight: 600; }}
        .cn-amp {{ background: #0366d6; color: #ffffff; font-weight: 700; }}
        [data-theme="dark"] .cn-gain {{ background: #0d2240; color: #58a6ff; }}
        [data-theme="dark"] .cn-amp {{ background: #1158c7; color: #ffffff; }}

        /* Caller badges */
        .badge {{
            display: inline-block; padding: 2px 6px; border-radius: 3px;
            font-size: 0.8em; font-weight: 600;
        }}
        .badge-manta {{ background: var(--caller-manta-bg); color: var(--caller-manta); }}
        .badge-tiddit {{ background: var(--caller-tiddit-bg); color: var(--caller-tiddit); }}
        .badge-both {{ background: var(--caller-both-bg); color: var(--caller-both); }}
        .badge-none {{ color: var(--fg-muted); }}
        .badge-svtype {{
            display: inline-block; padding: 1px 5px; border-radius: 3px;
            font-size: 0.75em; font-weight: 700;
        }}
        .svtype-DEL {{ background: var(--badge-fail-bg); color: var(--badge-fail-fg); }}
        .svtype-DUP {{ background: #dbedff; color: #0366d6; }}
        .svtype-INV {{ background: var(--badge-warn-bg); color: var(--badge-warn-fg); }}
        .svtype-TRA {{ background: var(--caller-both-bg); color: var(--caller-both); }}
        .svtype-INS {{ background: var(--badge-pass-bg); color: var(--badge-pass-fg); }}
        [data-theme="dark"] .svtype-DUP {{ background: #0d2240; color: #58a6ff; }}

        /* Tabulator overrides */
        .tabulator {{ font-size: 0.85em; border: 1px solid var(--table-border); }}
        .tabulator .tabulator-header {{ background: var(--table-header-bg); color: var(--fg); }}
        .tabulator .tabulator-header .tabulator-col {{ background: var(--table-header-bg); border-color: var(--table-border); color: var(--fg); }}
        .tabulator .tabulator-header .tabulator-col .tabulator-col-content {{ color: var(--fg); }}
        .tabulator .tabulator-tableholder {{ background: var(--bg); }}
        .tabulator-row {{ background: var(--bg); color: var(--fg); }}
        .tabulator-row.tabulator-row-even {{ background: var(--surface-alt); }}
        .tabulator-row.tabulator-row-odd {{ background: var(--bg); }}
        .tabulator-row .tabulator-cell {{ border-color: var(--table-border); }}
        .tabulator .tabulator-header .tabulator-col {{ border-right: 1px solid var(--table-border); }}
        .tabulator .tabulator-header .tabulator-header-filter input {{
            background: var(--surface); color: var(--fg); border: 1px solid var(--border);
        }}
        html[data-theme="light"] .tabulator-row.tabulator-selectable:hover,
        html:not([data-theme]) .tabulator-row.tabulator-selectable:hover {{ background-color: #f0f1f3 !important; }}
        html[data-theme="dark"] .tabulator-row.tabulator-selectable:hover {{ background-color: #2d333b !important; }}

        /* Theme toggle */
        .theme-toggle {{
            position: fixed; top: 12px; right: 16px;
            background: var(--surface); border: 1px solid var(--border);
            border-radius: 20px; padding: 6px 12px; cursor: pointer;
            font-size: 1.1em; line-height: 1; z-index: 1000; color: var(--fg);
        }}
        .theme-toggle:hover {{ background: var(--surface-alt); }}

        .footer {{
            color: var(--fg-muted); font-size: 0.85em; margin-top: 40px;
            border-top: 1px solid var(--border); padding-top: 12px;
        }}

        /* SV filter bar */
        .filter-bar {{ display: flex; gap: 8px; flex-wrap: wrap; margin: 8px 0; }}
        .filter-btn {{
            padding: 4px 10px; border: 1px solid var(--border); border-radius: 4px;
            background: var(--surface); color: var(--fg); cursor: pointer; font-size: 0.85em;
        }}
        .filter-btn:hover {{ background: var(--hover); }}
        .filter-btn.active {{ background: var(--link); color: #fff; border-color: var(--link); }}
    </style>
    <script>
        (function() {{
            var saved = localStorage.getItem('dashboard-theme');
            var theme = saved || (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
            document.documentElement.setAttribute('data-theme', theme);
            var csm = document.querySelector('meta[name="color-scheme"]');
            if (csm) csm.setAttribute('content', theme);
        }})();
    </script>
</head>
<body>

<button class="theme-toggle" id="themeToggle" title="Toggle dark / light mode">&#9790;</button>

<h1>Mutation Overview — Ottilie 4-Sample Pilot</h1>
<p class="note">
    CNVKit copy number and Manta/TIDDIT structural variant calls.
    CNVKit uses diploid-scale CN: cn=2 is baseline regardless of organism ploidy.
    For haploid yeast, cn=2 = normal, cn=1 = loss, cn=3 = gain.
</p>

<!-- Summary cards -->
<div class="cards">
    <div class="card">
        <div class="value">{summary["n_samples"]}</div>
        <div class="label">Samples</div>
    </div>
    <div class="card">
        <div class="value">{summary["cn_changes"]}</div>
        <div class="label">CN Changes (sensitive)</div>
    </div>
    <div class="card">
        <div class="value">{summary["cn_agreement_pct"]}%</div>
        <div class="label">Sensitive / Stringent Agreement</div>
    </div>
    <div class="card">
        <div class="value">{summary["sv_all"]} &rarr; {summary["sv_pass"]}</div>
        <div class="label">SV Events (all &rarr; PASS)</div>
    </div>
</div>

<!-- ============================================================ -->
<!-- CN Chromosome Heatmap                                         -->
<!-- ============================================================ -->
<div class="tab-bar" id="cn-chr-tabs">
    <button class="tab-btn active" data-tab="cn-chr-sens">CN Chromosome Sensitive #{cn_chr_sens["row_count"]}</button>
    <button class="tab-btn" data-tab="cn-chr-str">CN Chromosome Stringent #{cn_chr_str["row_count"]}</button>
</div>
<div class="tab-panel active" id="cn-chr-sens">
    <div class="cn-grid">{_render_cn_chr_table(cn_chr_sens, samples)}</div>
</div>
<div class="tab-panel" id="cn-chr-str">
    <div class="cn-grid">{_render_cn_chr_table(cn_chr_str, samples)}</div>
</div>

<!-- ============================================================ -->
<!-- CN Region Detail                                              -->
<!-- ============================================================ -->
<div class="tab-bar" id="cn-reg-tabs">
    <button class="tab-btn active" data-tab="cn-reg-sens">CN Regions Sensitive #{cn_reg_sens["row_count"]}</button>
    <button class="tab-btn" data-tab="cn-reg-str">CN Regions Stringent #{cn_reg_str["row_count"]}</button>
</div>
<div class="tab-panel active" id="cn-reg-sens">
    <div id="cn-reg-sens-table"></div>
</div>
<div class="tab-panel" id="cn-reg-str">
    <div id="cn-reg-str-table"></div>
</div>

<!-- ============================================================ -->
<!-- SV Event Matrix                                               -->
<!-- ============================================================ -->
<div class="tab-bar" id="sv-tabs">
    <button class="tab-btn active" data-tab="sv-pass">SV High-Quality #{sv_pass["row_count"]}</button>
    <button class="tab-btn" data-tab="sv-all">SV Cohort #{sv_all["row_count"]}</button>
</div>
<div class="tab-panel active" id="sv-pass">
    <div class="filter-bar" id="sv-pass-filters"></div>
    <div id="sv-pass-table"></div>
</div>
<div class="tab-panel" id="sv-all">
    <div class="filter-bar" id="sv-all-filters"></div>
    <div id="sv-all-table"></div>
</div>

<div class="footer">
    Phase 2a prototype — Ottilie xenobiotic ALE pilot (4 samples).<br>
    Data: CNVKit .call.cns (sensitive) and .germline.call.cns (stringent); Manta + TIDDIT SVs.<br>
    CN scale: diploid baseline (cn=2 = normal). See cnvkit_ploidy_cn_scale.md for details.
</div>

<script src="https://unpkg.com/tabulator-tables@6.3.0/dist/js/tabulator.min.js"></script>
<script>
// --- Theme toggle ---
var __darkMql = window.matchMedia('(prefers-color-scheme: dark)');
(function() {{
    var btn = document.getElementById('themeToggle');
    var root = document.documentElement;
    function cur() {{ return root.getAttribute('data-theme') || (__darkMql.matches ? 'dark' : 'light'); }}
    function apply(t) {{
        root.setAttribute('data-theme', t);
        var csm = document.querySelector('meta[name="color-scheme"]');
        if (csm) csm.setAttribute('content', t);
        btn.textContent = t === 'dark' ? '\\u2600' : '\\u263E';
    }}
    apply(cur());
    btn.addEventListener('click', function() {{
        var next = cur() === 'dark' ? 'light' : 'dark';
        localStorage.setItem('dashboard-theme', next);
        apply(next);
    }});
}})();

// --- Tab switching ---
document.querySelectorAll('.tab-bar').forEach(function(bar) {{
    bar.querySelectorAll('.tab-btn').forEach(function(btn) {{
        btn.addEventListener('click', function() {{
            bar.querySelectorAll('.tab-btn').forEach(function(b) {{ b.classList.remove('active'); }});
            btn.classList.add('active');
            var tabId = btn.getAttribute('data-tab');
            // Hide all panels that are siblings after this tab-bar
            var next = bar.nextElementSibling;
            while (next && next.classList.contains('tab-panel')) {{
                next.classList.remove('active');
                next = next.nextElementSibling;
            }}
            document.getElementById(tabId).classList.add('active');
        }});
    }});
}});

// --- CN color helper ---
function cnClass(cn) {{
    if (cn < 2) return 'cn-loss';
    if (cn === 2) return 'cn-neutral';
    if (cn >= 10) return 'cn-amp';
    return 'cn-gain';
}}

// --- CN Region tables ---
var cnRegSensData = {json.dumps(cn_reg_sens["rows"])};
var cnRegStrData = {json.dumps(cn_reg_str["rows"])};
var cnRegSamples = {json.dumps(cn_reg_sens["samples"])};

function cnCellFormatter(cell) {{
    var v = cell.getValue();
    var cls = cnClass(v);
    return '<span class="' + cls + '" style="display:inline-block;padding:1px 6px;border-radius:3px">' + v + '</span>';
}}

function buildCnRegColumns(samples) {{
    var cols = [
        {{ title: "Chr", field: "chromosome", headerFilter: "input", frozen: true, width: 60 }},
        {{ title: "Start", field: "start", sorter: "number", hozAlign: "right", formatter: function(c) {{ return c.getValue().toLocaleString(); }} }},
        {{ title: "End", field: "end", sorter: "number", hozAlign: "right", formatter: function(c) {{ return c.getValue().toLocaleString(); }} }},
        {{ title: "Span (kb)", field: "span_kb", sorter: "number", hozAlign: "right" }},
    ];
    samples.forEach(function(s) {{
        cols.push({{
            title: s.replace(/-/g, '\\u2011'), field: s + "_cn", hozAlign: "center",
            sorter: "number", formatter: cnCellFormatter
        }});
    }});
    return cols;
}}

new Tabulator("#cn-reg-sens-table", {{
    data: cnRegSensData, layout: "fitDataFill", height: 500,
    headerSortTristate: true, columns: buildCnRegColumns(cnRegSamples),
}});
new Tabulator("#cn-reg-str-table", {{
    data: cnRegStrData, layout: "fitDataFill", height: 500,
    headerSortTristate: true, columns: buildCnRegColumns(cnRegSamples),
}});

// --- SV tables ---
var svPassData = {json.dumps(sv_pass["rows"])};
var svAllData = {json.dumps(sv_all["rows"])};
var svSamples = {json.dumps(sv_samples)};

function callerBadge(val) {{
    if (!val || val === '-') return '<span class="badge-none">-</span>';
    if (val.indexOf('+') > -1) return '<span class="badge badge-both">' + val + '</span>';
    if (val === 'Manta') return '<span class="badge badge-manta">Manta</span>';
    if (val === 'TIDDIT') return '<span class="badge badge-tiddit">TIDDIT</span>';
    return '<span class="badge">' + val + '</span>';
}}

function svtypeBadge(cell) {{
    var v = cell.getValue();
    var cls = 'svtype-' + v;
    return '<span class="badge-svtype ' + cls + '">' + v + '</span>';
}}

function buildSvColumns(samples) {{
    var cols = [
        {{ title: "Chr", field: "chrom", headerFilter: "input", frozen: true, width: 60 }},
        {{ title: "Pos", field: "pos", sorter: "number", hozAlign: "right", formatter: function(c) {{ return c.getValue().toLocaleString(); }} }},
        {{ title: "Chr2", field: "chrom2", width: 60 }},
        {{ title: "End", field: "end", sorter: "number", hozAlign: "right", formatter: function(c) {{ return c.getValue().toLocaleString(); }} }},
        {{ title: "Type", field: "svtype", headerFilter: "list", headerFilterParams: {{ valuesLookup: true }}, formatter: svtypeBadge, width: 70 }},
        {{ title: "Length", field: "svlen", sorter: "number", hozAlign: "right", formatter: function(c) {{ var v = c.getValue(); return v ? v.toLocaleString() : '0'; }} }},
    ];
    samples.forEach(function(s) {{
        cols.push({{
            title: s.replace(/-/g, '\\u2011'),
            field: s, hozAlign: "center",
            formatter: function(cell) {{ return callerBadge(cell.getValue()); }},
            headerFilter: "list", headerFilterParams: {{ valuesLookup: true }},
        }});
    }});
    return cols;
}}

new Tabulator("#sv-pass-table", {{
    data: svPassData, layout: "fitDataFill", height: 600,
    headerSortTristate: true, columns: buildSvColumns(svSamples),
    initialSort: [{{ column: "chrom", dir: "asc" }}, {{ column: "pos", dir: "asc" }}],
}});
new Tabulator("#sv-all-table", {{
    data: svAllData, layout: "fitDataFill", height: 600,
    headerSortTristate: true, columns: buildSvColumns(svSamples),
    initialSort: [{{ column: "chrom", dir: "asc" }}, {{ column: "pos", dir: "asc" }}],
}});
</script>
</body>
</html>"""


def _cn_cell_class(cn: int) -> str:
    if cn < 2:
        return "cn-loss"
    if cn == 2:
        return "cn-neutral"
    if cn >= 10:
        return "cn-amp"
    return "cn-gain"


def _render_cn_chr_table(data: dict, samples: list[str]) -> str:
    """Render an HTML table for chromosome-level CN heatmap."""
    rows_html = []
    for r in data["rows"]:
        cells = [
            f'<td class="chr">{r["chromosome"]}</td>',
            f'<td class="len">{r["length"]:,}</td>',
        ]
        for s in samples:
            cn = r.get(f"{s}_cn", 2)
            log2 = r.get(f"{s}_log2", 0)
            abs_cn = r.get(f"{s}_abs", 0)
            note = r.get(f"{s}_note", "")
            cls = _cn_cell_class(cn)
            tooltip = f"log2={log2:.4f}, abs_cn={abs_cn:.3f}"
            display = f"{cn}{note}"
            cells.append(f'<td class="{cls}" title="{tooltip}">{display}</td>')
        rows_html.append("<tr>" + "".join(cells) + "</tr>")

    sample_headers = "".join(
        f'<th>{s.replace("-", "&#8209;")}</th>' for s in samples
    )
    return f"""<table>
<thead><tr><th>Chr</th><th>Length</th>{sample_headers}</tr></thead>
<tbody>{"".join(rows_html)}</tbody>
</table>"""


def main():
    parser = argparse.ArgumentParser(description="Generate mutation overview prototype")
    parser.add_argument(
        "--data-dir", type=Path, default=Path(__file__).parent / "data",
        help="Directory containing pilot CSV files",
    )
    parser.add_argument(
        "--output", type=Path, default=Path(__file__).parent / "mutation_overview.html",
        help="Output HTML file",
    )
    args = parser.parse_args()
    d = args.data_dir

    cn_chr_sens = load_cn_chr(d / "cn_chr_summary_sensitive.csv")
    cn_chr_str = load_cn_chr(d / "cn_chr_summary_stringent.csv")
    cn_reg_sens = load_cn_regions(d / "cn_cohort_collapsed_sensitive.csv")
    cn_reg_str = load_cn_regions(d / "cn_cohort_collapsed_stringent.csv")
    sv_pass = load_sv_matrix(d / "sv_cohort_matrix_union_pass.csv")
    sv_all = load_sv_matrix(d / "sv_cohort_matrix_union.csv")

    summary = compute_summary(cn_chr_sens, cn_chr_str, sv_pass, sv_all)

    html = generate_html(
        cn_chr_sens, cn_chr_str, cn_reg_sens, cn_reg_str, sv_pass, sv_all, summary
    )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(html)
    print(f"Generated: {args.output} ({len(html):,} bytes)")


if __name__ == "__main__":
    main()