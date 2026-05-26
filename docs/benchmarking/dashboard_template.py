#!/usr/bin/env python3
"""
Reusable benchmark dashboard template for ALE pipeline validation reports.

Design system extracted from the Marko SV benchmark dashboard. Generates
self-contained HTML files with:
  - Light/dark theme with OS auto-detection and manual toggle
  - Tabulator.js interactive tables (sort, filter, custom formatters)
  - Summary stat cards, badge components, finding/alert boxes
  - GitHub/VS Code-inspired color palette
  - System font stack (no external font dependencies)

Usage as a library:
    from dashboard_template import DashboardBuilder

    db = DashboardBuilder(
        title="My Benchmark — Tool A vs Tool B",
        subtitle="Sample: XYZ · Organism: E. coli · Generated 2026-05-21",
    )
    db.add_stat_card("42/42", "SNPs detected by both tools")
    db.add_stat_card("0/3", "Tool-A unique calls", style="warn")
    db.add_stat_card_organism("<em>E. coli</em> K-12", "MG1655 (haploid)")
    db.add_finding("warn", "<strong>3 calls missed.</strong> Details here...")
    db.add_finding("good", "<strong>100% recall.</strong> All variants matched.")
    db.add_section("SNP Concordance", subtitle="Click position to inspect.",
                   table_id="snp-table")
    db.add_table("snp-table", data=[...], columns=[...])
    db.add_details("Audit Log", "<pre>...</pre>")
    db.write("report/index.html")

Usage as a standalone script (generates a demo page):
    python dashboard_template.py -o demo_report.html
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path


# ---------------------------------------------------------------------------
# CSS Design System
# ---------------------------------------------------------------------------

CSS_THEME = """\
/* --- Light theme (default) --- */
:root {
    color-scheme: light;
    --bg: #ffffff;
    --fg: #333333;
    --fg-heading: #24292e;
    --fg-muted: #586069;
    --link: #0366d6;
    --border: #e1e4e8;
    --surface: #f6f8fa;
    --surface-alt: #fafbfc;
    --badge-pass-bg: #dcffe4; --badge-pass-fg: #22863a;
    --badge-warn-bg: #fff5b1; --badge-warn-fg: #735c0f;
    --badge-fail-bg: #ffeef0; --badge-fail-fg: #cb2431;
    --badge-na-bg: #f1f1f1;   --badge-na-fg: #888888;
    --finding-bg: #f6f8fa;
    --finding-warn-border: #e36209; --finding-warn-bg: #fff8f0;
    --finding-note-border: #6a737d; --finding-note-bg: #f6f8fa;
    --finding-good-border: #22863a;
    --finding-info-border: #0366d6;
    --organism-border: #6f42c1; --organism-bg: #f5f0ff; --organism-fg: #6f42c1;
    --warn-border: #e36209; --warn-bg: #fff8f0; --warn-fg: #e36209;
    --sor-high: #cb2431;
    --code-bg: #f6f8fa;
    --table-header-bg: #f6f8fa;
    --table-border: #e1e4e8;
    --hover: #f0f1f3;
}

/* --- Dark theme --- */
[data-theme="dark"] {
    color-scheme: dark;
    --bg: #0d1117;
    --fg: #c9d1d9;
    --fg-heading: #e6edf3;
    --fg-muted: #8b949e;
    --link: #58a6ff;
    --border: #30363d;
    --surface: #161b22;
    --surface-alt: #1c2128;
    --hover: #2d333b;
    --badge-pass-bg: #1b3a2a; --badge-pass-fg: #56d364;
    --badge-warn-bg: #3b2e00; --badge-warn-fg: #e3b341;
    --badge-fail-bg: #3d1418; --badge-fail-fg: #f85149;
    --badge-na-bg: #21262d;   --badge-na-fg: #8b949e;
    --finding-bg: #161b22;
    --finding-warn-border: #d29922; --finding-warn-bg: #1c1500;
    --finding-note-border: #8b949e; --finding-note-bg: #161b22;
    --finding-good-border: #56d364;
    --finding-info-border: #58a6ff;
    --organism-border: #a371f7; --organism-bg: #1a0f2e; --organism-fg: #a371f7;
    --warn-border: #d29922; --warn-bg: #1c1500; --warn-fg: #d29922;
    --sor-high: #f85149;
    --code-bg: #161b22;
    --table-header-bg: #1c2128;
    --table-border: #30363d;
}"""

CSS_BASE = """\
body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
    max-width: 1200px;
    margin: 40px auto;
    padding: 0 20px;
    color: var(--fg);
    background: var(--bg);
}
h1 { border-bottom: 2px solid var(--link); padding-bottom: 8px; color: var(--fg-heading); }
h2 { margin-top: 32px; color: var(--fg-heading); }
h3 { color: var(--fg-heading); }
a { color: var(--link); text-decoration: none; }
a:hover { text-decoration: underline; }
code { background: var(--code-bg); padding: 1px 4px; border-radius: 3px; }
.meta { color: var(--fg-muted); font-size: 0.9em; }
.section { margin: 24px 0; }"""

CSS_COMPONENTS = """\
/* Stat cards */
.stat-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 16px;
    margin: 16px 0;
}
.stat-card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 16px;
    text-align: center;
}
.stat-card .value {
    font-size: 2em;
    font-weight: 700;
    color: var(--fg-heading);
}
.stat-card .label {
    font-size: 0.85em;
    color: var(--fg-muted);
    margin-top: 4px;
}
.stat-card.card-organism { border-left: 3px solid var(--organism-border); background: var(--organism-bg); }
.stat-card.card-organism .value { font-size: 1.1em; color: var(--organism-fg); }
.stat-card.card-warn { border-left: 3px solid var(--warn-border); background: var(--warn-bg); }
.stat-card.card-warn .value { color: var(--warn-fg); }

/* Badges */
.badge {
    display: inline-block;
    padding: 2px 8px;
    border-radius: 3px;
    font-size: 0.8em;
    font-weight: 600;
}
.badge-pass { background: var(--badge-pass-bg); color: var(--badge-pass-fg); }
.badge-warn { background: var(--badge-warn-bg); color: var(--badge-warn-fg); }
.badge-fail { background: var(--badge-fail-bg); color: var(--badge-fail-fg); }
.badge-na { background: var(--badge-na-bg); color: var(--badge-na-fg); }
.badge-yes { background: var(--badge-pass-bg); color: var(--badge-pass-fg); }
.badge-no { background: var(--badge-fail-bg); color: var(--badge-fail-fg); }

/* Findings / alerts */
.finding { margin: 8px 0; padding: 8px 12px; border-left: 3px solid var(--link); background: var(--finding-bg); }
.finding-good { border-left-color: var(--finding-good-border); }
.finding-warn { border-left-color: var(--finding-warn-border); background: var(--finding-warn-bg); }
.finding-note { border-left-color: var(--finding-note-border); background: var(--finding-note-bg); }
.finding-info { border-left-color: var(--finding-info-border); }

/* Details / collapsible sections */
details { margin: 8px 0; }
details summary { cursor: pointer; color: var(--link); font-weight: 600; }
pre.audit { background: var(--surface); padding: 12px; border-radius: 4px; font-size: 0.85em; overflow-x: auto; color: var(--fg); }

/* Inline tables */
.inline-table th, .inline-table td {
    padding: 6px 10px;
    border: 1px solid var(--border);
}
.inline-table tr:first-child { background: var(--surface); }

/* Footer */
.footer {
    color: var(--fg-muted);
    font-size: 0.85em;
    margin-top: 40px;
    border-top: 1px solid var(--border);
    padding-top: 12px;
}"""

CSS_THEME_TOGGLE = """\
.theme-toggle {
    position: fixed;
    top: 12px;
    right: 16px;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 20px;
    padding: 6px 12px;
    cursor: pointer;
    font-size: 1.1em;
    line-height: 1;
    z-index: 1000;
    color: var(--fg);
}
.theme-toggle:hover { background: var(--surface-alt); }"""

CSS_TABULATOR = """\
/* Tabulator theme integration */
.tabulator { font-size: 0.9em; border: 1px solid var(--table-border); }
.tabulator .tabulator-header { background: var(--table-header-bg); color: var(--fg); }
.tabulator .tabulator-header .tabulator-col { background: var(--table-header-bg); border-color: var(--table-border); color: var(--fg); }
.tabulator .tabulator-header .tabulator-col .tabulator-col-content { color: var(--fg); }
.tabulator-row { background: var(--bg); color: var(--fg); }
.tabulator-row.tabulator-row-even { background: var(--surface-alt); }
.tabulator-row .tabulator-cell { border-color: var(--table-border); }
.tabulator .tabulator-header .tabulator-col { border-right: 1px solid var(--table-border); }
.tabulator .tabulator-tableholder { background: var(--bg); }
.tabulator-row.tabulator-row-odd { background: var(--bg); }
.tabulator-row .tabulator-cell a { color: var(--link); }
.tabulator .tabulator-header .tabulator-header-filter input {
    background: var(--surface); color: var(--fg); border: 1px solid var(--border);
}
/*
 * Tabulator hover overrides — hardcoded per theme.
 * Using html[data-theme] prefix to beat Tabulator's selector specificity.
 * Hardcoded colors because some browsers (Safari) have issues resolving
 * CSS custom properties inside :hover pseudo-states on third-party elements.
 */
html[data-theme="light"] .tabulator .tabulator-header .tabulator-col.tabulator-sortable.tabulator-col-sorter-element:hover,
html:not([data-theme]) .tabulator .tabulator-header .tabulator-col.tabulator-sortable.tabulator-col-sorter-element:hover {
    background-color: #e8e9eb !important;
}
html[data-theme="light"] .tabulator-row.tabulator-selectable:hover,
html:not([data-theme]) .tabulator-row.tabulator-selectable:hover {
    background-color: #f0f1f3 !important;
}
html[data-theme="light"] .tabulator-row:hover .tabulator-cell,
html:not([data-theme]) .tabulator-row:hover .tabulator-cell {
    background-color: #f0f1f3 !important;
}
html[data-theme="dark"] .tabulator .tabulator-header .tabulator-col.tabulator-sortable.tabulator-col-sorter-element:hover {
    background-color: #3a414b !important;
}
html[data-theme="dark"] .tabulator-row.tabulator-selectable:hover {
    background-color: #2d333b !important;
}
html[data-theme="dark"] .tabulator-row:hover .tabulator-cell {
    background-color: #2d333b !important;
}"""

# ---------------------------------------------------------------------------
# JavaScript
# ---------------------------------------------------------------------------

JS_THEME_INIT = """\
// Apply theme immediately (before paint) to prevent flash.
(function() {
    var saved = localStorage.getItem('dashboard-theme');
    var theme = saved || (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
    document.documentElement.setAttribute('data-theme', theme);
    var csm = document.querySelector('meta[name="color-scheme"]');
    if (csm) csm.setAttribute('content', theme);
})();"""

JS_THEME_TOGGLE = """\
// --- Theme toggle ---
var __darkMql = window.matchMedia('(prefers-color-scheme: dark)');
(function() {
    var btn = document.getElementById('themeToggle');
    var root = document.documentElement;
    function currentTheme() {
        return root.getAttribute('data-theme') ||
            (__darkMql.matches ? 'dark' : 'light');
    }
    function applyTheme(theme) {
        root.setAttribute('data-theme', theme);
        var csm = document.querySelector('meta[name="color-scheme"]');
        if (csm) csm.setAttribute('content', theme);
        btn.textContent = theme === 'dark' ? '\\u2600' : '\\u263E';
    }
    applyTheme(currentTheme());
    btn.addEventListener('click', function() {
        var next = currentTheme() === 'dark' ? 'light' : 'dark';
        localStorage.setItem('dashboard-theme', next);
        applyTheme(next);
    });
    function onSystemChange(e) {
        if (!localStorage.getItem('dashboard-theme')) {
            applyTheme(e.matches ? 'dark' : 'light');
        }
    }
    if (__darkMql.addEventListener) {
        __darkMql.addEventListener('change', onSystemChange);
    } else if (__darkMql.addListener) {
        __darkMql.addListener(onSystemChange);
    }
})();"""

JS_BADGE_FORMATTERS = """\
// --- Common badge formatters for Tabulator columns ---
function yesNoBadge(cell) {
    var v = cell.getValue();
    if (v === "Yes") return '<span class="badge badge-yes">Yes</span>';
    if (v === "No") return '<span class="badge badge-no">No</span>';
    if (v === "N/A") return '<span class="badge badge-na">N/A</span>';
    return v;
}
function filterBadge(cell) {
    var v = cell.getValue();
    if (v === "PASS") return '<span class="badge badge-pass">PASS</span>';
    if (v === "NOT_FOUND") return '<span class="badge badge-fail">NOT FOUND</span>';
    return '<span class="badge badge-warn">' + v + '</span>';
}
function effectBadge(cell) {
    var v = cell.getValue();
    if (!v) return '';
    if (v.includes('nonsense') || v.includes('stop_gained') || v.includes('frameshift'))
        return '<span class="badge badge-fail">' + v + '</span>';
    if (v.includes('missense') || v.includes('nonsynonymous'))
        return '<span class="badge badge-warn">' + v + '</span>';
    if (v.includes('synonymous') && !v.includes('non'))
        return '<span class="badge badge-pass">' + v + '</span>';
    return '<span class="badge badge-na">' + v + '</span>';
}
function numberFmt(decimals) {
    return function(cell) {
        var v = cell.getValue();
        return v != null ? v.toFixed(decimals) : "";
    };
}
function highlightAbove(threshold, decimals) {
    return function(cell) {
        var v = cell.getValue();
        if (v == null) return "";
        var s = v.toFixed(decimals || 2);
        return v > threshold
            ? '<span style="color:var(--sor-high);font-weight:600">' + s + '</span>'
            : s;
    };
}"""

# Tabulator CDN URLs
TABULATOR_CSS = "https://unpkg.com/tabulator-tables@6.3.0/dist/css/tabulator.min.css"
TABULATOR_JS = "https://unpkg.com/tabulator-tables@6.3.0/dist/js/tabulator.min.js"


# ---------------------------------------------------------------------------
# Builder class
# ---------------------------------------------------------------------------

class DashboardBuilder:
    """Programmatic builder for self-contained benchmark HTML dashboards."""

    def __init__(self, title, subtitle="", footer=""):
        self.title = title
        self.subtitle = subtitle
        self.footer = footer
        self._stat_cards = []
        self._findings = []
        self._sections = []  # list of (heading, subtitle, content_html)
        self._tables = {}    # table_id -> {data, columns_js}
        self._extra_js = []
        self._extra_css = []

    # -- Stat cards --

    def add_stat_card(self, value, label, style=""):
        """Add a summary stat card. style: '' (default), 'warn', 'organism'."""
        cls = f" card-{style}" if style else ""
        self._stat_cards.append(
            f'<div class="stat-card{cls}">'
            f'<div class="value">{value}</div>'
            f'<div class="label">{label}</div></div>'
        )

    def add_stat_card_organism(self, value, label):
        self.add_stat_card(value, label, style="organism")

    # -- Findings --

    def add_finding(self, style, html_content):
        """Add a finding box. style: 'good', 'warn', 'note', 'info'."""
        self._findings.append(f'<div class="finding finding-{style}">{html_content}</div>')

    # -- Sections --

    def add_section(self, heading, subtitle="", table_id="", html_content=""):
        """Add a content section. If table_id is given, a <div id=...> is appended."""
        content = ""
        if subtitle:
            content += f'<p class="meta">{subtitle}</p>\n'
        if html_content:
            content += html_content + "\n"
        if table_id:
            content += f'<div id="{table_id}"></div>\n'
        self._sections.append((heading, content))

    def add_details(self, summary_text, inner_html):
        """Add a collapsible <details> section."""
        self._sections.append(("", f'<details><summary>{summary_text}</summary>\n{inner_html}\n</details>'))

    def add_raw_section(self, html):
        """Add raw HTML as a section (no heading wrapper)."""
        self._sections.append(("", html))

    # -- Tables --

    def add_table(self, table_id, data, columns_js):
        """Register a Tabulator table.

        Args:
            table_id: Matches the table_id in add_section().
            data: List of dicts (will be JSON-serialized).
            columns_js: Raw JavaScript string for the columns array.
                Example: '[{title:"Pos", field:"pos", sorter:"number"}]'
        """
        self._tables[table_id] = {"data": data, "columns_js": columns_js}

    # -- Customization --

    def add_custom_js(self, js_code):
        """Append custom JavaScript (runs after tables are created)."""
        self._extra_js.append(js_code)

    def add_custom_css(self, css_code):
        """Append custom CSS rules."""
        self._extra_css.append(css_code)

    # -- Render --

    def render(self):
        """Render the complete self-contained HTML string."""
        generated = datetime.now().strftime("%Y-%m-%d %H:%M")

        # --- CSS ---
        css_blocks = [
            CSS_THEME, CSS_BASE, CSS_COMPONENTS, CSS_THEME_TOGGLE,
            CSS_TABULATOR,
        ]
        if self._extra_css:
            css_blocks.extend(self._extra_css)
        all_css = "\n".join(css_blocks)

        # --- Summary section ---
        summary_html = ""
        if self._stat_cards:
            cards = "\n        ".join(self._stat_cards)
            summary_html = f"""
<div class="section">
    <h2>Summary</h2>
    <div class="stat-grid">
        {cards}
    </div>
</div>"""

        # --- Findings section ---
        findings_html = ""
        if self._findings:
            items = "\n    ".join(self._findings)
            findings_html = f"""
<div class="section">
    <h2>Key Findings</h2>
    {items}
</div>"""

        # --- Content sections ---
        sections_html = ""
        for heading, content in self._sections:
            if heading:
                sections_html += f'\n<div class="section">\n    <h2>{heading}</h2>\n    {content}\n</div>'
            else:
                sections_html += f'\n<div class="section">\n    {content}\n</div>'

        # --- Table initialization JS ---
        table_js_parts = []
        for tid, tconf in self._tables.items():
            data_json = json.dumps(tconf["data"], ensure_ascii=False)
            table_js_parts.append(f"""
new Tabulator("#{tid}", {{
    data: {data_json},
    layout: "fitDataFill",
    headerSortTristate: true,
    columns: {tconf["columns_js"]},
}});""")

        extra_js = "\n".join(self._extra_js)
        table_js = "\n".join(table_js_parts)

        # --- Footer ---
        footer_text = self.footer or f"Generated by <code>dashboard_template.py</code> on {generated}"

        return f"""\
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="color-scheme" content="light dark">
    <title>{self.title}</title>
    <link href="{TABULATOR_CSS}" rel="stylesheet">
    <style>
{all_css}
    </style>
    <script>
{JS_THEME_INIT}
    </script>
</head>
<body>

<button class="theme-toggle" id="themeToggle" title="Toggle dark / light mode" aria-label="Toggle dark mode">&#9790;</button>

<h1>{self.title}</h1>
<p class="meta">{self.subtitle} &middot; Generated {generated}</p>
{summary_html}
{findings_html}
{sections_html}

<div class="footer">{footer_text}</div>

<script src="{TABULATOR_JS}"></script>
<script>
{JS_BADGE_FORMATTERS}

{table_js}

{extra_js}

{JS_THEME_TOGGLE}
</script>
</body>
</html>
"""

    def write(self, path):
        """Render and write to file."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        html = self.render()
        path.write_text(html)
        print(f"Dashboard written to {path} ({len(html):,} bytes)")
        return path


# ---------------------------------------------------------------------------
# Demo / standalone
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Generate a demo benchmark dashboard using the ALE design system")
    parser.add_argument("-o", "--output", type=Path, default=Path("demo_dashboard.html"),
                        help="Output HTML file path")
    args = parser.parse_args()

    db = DashboardBuilder(
        title="Demo Benchmark Dashboard",
        subtitle="Sample: DEMO_001 &middot; Organism: <em>S. cerevisiae</em> CEN.PK &middot; Ploidy: 2",
    )

    # Summary cards
    db.add_stat_card_organism("<em>S. cerevisiae</em>", "CEN.PK113-7D (eukaryote, diploid)")
    db.add_stat_card("85/85", "SNPs matched<br>across both callers")
    db.add_stat_card("3/5", "CNV events confirmed", style="warn")
    db.add_stat_card("98.8%", "Overall concordance")

    # Findings
    db.add_finding("good", "<strong>High SNP concordance.</strong> 85/85 variants matched between Tool A and Tool B.")
    db.add_finding("warn", "<strong>2 CNV calls unconfirmed.</strong> Require manual IGV inspection.")
    db.add_finding("note", "<strong>Filter thresholds.</strong> QD &lt; 2.0 flagged 12% of variants.")

    # Table section
    demo_data = [
        {"pos": 12345, "type": "SNP", "ref_alt": "A>G", "tool_a": "Yes", "tool_b": "Yes", "gene": "YDR150W", "effect": "missense_variant", "filter": "PASS"},
        {"pos": 67890, "type": "INS", "ref_alt": "->T", "tool_a": "Yes", "tool_b": "No", "gene": "YBR101C", "effect": "frameshift_variant", "filter": "QD_filter"},
        {"pos": 234567, "type": "DEL", "ref_alt": "G>.", "tool_a": "No", "tool_b": "Yes", "gene": "YGL121C", "effect": "synonymous_variant", "filter": "PASS"},
    ]
    columns_js = """[
        {title: "Position", field: "pos", sorter: "number", hozAlign: "right",
         formatter: function(cell) { return cell.getValue().toLocaleString(); }},
        {title: "Type", field: "type", headerFilter: "list", headerFilterParams: {valuesLookup: true}, width: 70},
        {title: "Ref>Alt", field: "ref_alt", width: 90},
        {title: "Tool A", field: "tool_a", hozAlign: "center", formatter: yesNoBadge, width: 80},
        {title: "Tool B", field: "tool_b", hozAlign: "center", formatter: yesNoBadge, width: 80},
        {title: "Gene", field: "gene", headerFilter: "input", minWidth: 100},
        {title: "Effect", field: "effect", formatter: effectBadge, minWidth: 140},
        {title: "Filter", field: "filter", hozAlign: "center", formatter: filterBadge, width: 110}
    ]"""

    db.add_section(
        "Variant Concordance",
        subtitle="Demo data &mdash; 3 example variants shown.",
        table_id="variant-table",
    )
    db.add_table("variant-table", demo_data, columns_js)

    # Audit section
    db.add_details("Show processing audit", '<pre class="audit">Tool A: 85 variants called\nTool B: 88 variants called\nMatched: 85 (100% of Tool A)\nTool B only: 3 variants</pre>')

    db.write(args.output)


if __name__ == "__main__":
    main()
