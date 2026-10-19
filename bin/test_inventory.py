#!/usr/bin/env python
"""Test inventory per scope: of the files the fork ADDED or MODIFIED relative to pristine
nf-core/sarek 3.5.1, how many does any test reach.

Replaces the folder-based "6 of 89 files have a test" figure (GitHub issue #14, item 4) with one
derived from (a) a byte comparison of the working tree against the pristine 3.5.1 tree and (b) the
per-file coverage table of a finished `tests/nf_coverage.sh run` (coverage.tsv plus the per-run
JaCoCo XML reports, docs/dev-practices/nextflow_code_coverage.md).

Scope: main.nf, nextflow.config and every file under workflows/, subworkflows/, modules/, conf/,
bin/, lib/ (if present). Not: tests/, docs/, deploy/, data/.

Per file:
  scope      ADDED (not in 3.5.1) | MODIFIED (in 3.5.1, bytes differ) | PRISTINE (byte-identical)
  reached    yes      the coverage table shows >= 1 covered line in some run; the runs are listed
             no       the file is head-JVM Nextflow code (.nf / .config) and no measured run covered a line
             n/a      the coverage method cannot see the file (bin/ runs in the task's shell or container,
                      module metadata and test fixtures are not executed, a -c / profile config no run
                      loaded is not compiled) - the reason is printed, not a "no"
  unit test  the commit gate's TESTMAP (bin/check_snapshot_staged.sh) names a test for the path

The ADDED and MODIFIED sets are cross-checked against the inventories in
docs/dev-practices/SAREK_MODIFICATIONS.md; every disagreement is printed, neither side is trusted.

Usage
  python bin/test_inventory.py --upstream /path/to/sarek-3.5.1 --coverage output_coverage_99aef57 \\
      --out docs/dev-practices/test_inventory_YYYY-MM-DD.md [--tsv per_file.tsv]

  --upstream   pristine 3.5.1 tree root (the directory holding main.nf), e.g. the `3_5_1/` directory
               of `nf-core pipelines download sarek --revision 3.5.1 --outdir DIR --compress none
               --container-system none`, kept OUTSIDE the working tree
  --coverage   a finished run directory of tests/nf_coverage.sh (needs coverage.tsv, RUN_INFO.txt,
               xml/<run>.xml, logs/*.nextflow.log). Read only.
Requires: python 3, git (to read the coverage commit's config texts for the class -> file map).
"""
import argparse, collections, datetime, glob, hashlib, os, re, subprocess, sys
import xml.etree.ElementTree as ET

ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument('--root', default=os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
ap.add_argument('--upstream', required=True)
ap.add_argument('--coverage', required=True)
ap.add_argument('--out', required=True, help='markdown report to write')
ap.add_argument('--tsv', help='per-file table as TSV')
a = ap.parse_args()
ROOT = os.path.realpath(a.root)
UP = os.path.realpath(a.upstream)
COV = os.path.realpath(a.coverage)
os.chdir(ROOT)

def git(*args):
    return subprocess.run(['git'] + list(args), capture_output=True, text=True).stdout

SCOPE_DIRS = ['workflows', 'subworkflows', 'modules', 'conf', 'bin', 'lib']
# tracked files plus untracked-but-not-ignored ones: a `.nextflow/` cache left inside bin/ is not the fork
listed = set(git('ls-files', '--cached', '--others', '--exclude-standard', '--', 'main.nf', 'nextflow.config', *SCOPE_DIRS).split('\n'))
files = sorted(f for f in listed if f and os.path.isfile(f) and (f in ('main.nf', 'nextflow.config') or f.split('/')[0] in SCOPE_DIRS))

# ---------------------------------------------------------------- 1. scope: ADDED / MODIFIED / PRISTINE
def classify(rel):
    up = os.path.join(UP, rel)
    if not os.path.exists(up):
        return 'ADDED'
    return 'PRISTINE' if open(rel, 'rb').read() == open(up, 'rb').read() else 'MODIFIED'
scope = {f: classify(f) for f in files}

# ---------------------------------------------------------------- file kinds (what the coverage method can see)
task_scripts = set()        # bin/ files some modules/**/main.nf names (the commit gate's rule)
for mf in glob.glob('modules/**/main.nf', recursive=True):
    for tok in re.findall(r'\b[\w.-]+\.(?:py|sh|R|pl)\b', open(mf, errors='replace').read()):
        if os.path.isfile(os.path.join('bin', tok)):
            task_scripts.add(os.path.join('bin', tok))
nfconf = open('nextflow.config', errors='replace').read()
included_conf = set(re.findall(r"includeConfig\s+'([^']+)'", nfconf))

def kind(f):
    if '/tests/' in f and f.startswith(('modules/', 'subworkflows/')):
        return 'module test fixture'
    if f.endswith('.nf') or f.endswith('.config'):
        return 'nextflow code'
    if f.startswith('bin/'):
        return 'task script (bin)' if f in task_scripts else 'tooling script (bin)'
    if '/tests/' in f:
        return 'module test fixture'
    if os.path.basename(f) in ('meta.yml', 'environment.yml'):
        return 'module metadata'
    if f.endswith('.diff'):
        return 'nf-core patch'
    if f.endswith(('.yml', '.yaml', '.json')):
        return 'params / overlay file'
    return 'other'

# ---------------------------------------------------------------- 2. reached by a test (coverage run, read only)
run_info = dict(l.rstrip('\n').split('\t', 1) for l in open(os.path.join(COV, 'RUN_INFO.txt')) if '\t' in l and not l.startswith('run\t') and l.split('\t')[0] in ('date', 'commit', 'versions'))
cov_commit = run_info['commit'].split()[0]
runs_recorded = [l.split('\t')[0] for l in open(os.path.join(COV, 'RUN_INFO.txt')) if re.match(r'^(preview|qc_only|t_\w+)\t', l)]

covtsv = {}
with open(os.path.join(COV, 'coverage.tsv')) as fh:
    hdr = fh.readline().rstrip('\n').split('\t')
    for l in fh:
        r = dict(zip(hdr, l.rstrip('\n').split('\t')))
        covtsv[r['file']] = r

# class -> file: Script_<hash> from the runs' logs; Script<MD5> from the config text AT THE COVERAGE COMMIT
# (the class is named by the MD5 of the text that ran, not of today's text)
cmap = {}
for lg in glob.glob(os.path.join(COV, 'logs', '*.nextflow.log')):
    for line in open(lg, errors='replace'):
        m = re.match(r'^\s+(Script_\w+): (/\S+\.nf)\s*$', line)
        if m:
            p = os.path.realpath(m.group(2))
            if p.startswith(ROOT + '/'):
                cmap[m.group(1)] = p[len(ROOT) + 1:]
md5_note = []
for f in files:
    if f.endswith('.config'):
        txt = subprocess.run(['git', 'show', f'{cov_commit}:{f}'], capture_output=True).stdout
        if not txt:
            txt = open(f, 'rb').read(); md5_note.append(f)
        cmap.setdefault('Script' + hashlib.md5(txt).hexdigest().upper(), f)

def run_label(n):
    return {'preview': 'plan-only', 'qc_only': 'qc_only', 't_ottilie_e2e': 'e2e'}.get(n, n[2:] + '.nf.test' if n.startswith('t_') else n)

per_run = collections.defaultdict(dict)       # file -> run -> covered lines
run_names = []
for x in sorted(glob.glob(os.path.join(COV, 'xml', '*.xml'))):
    n = os.path.basename(x)[:-4]
    if n == 'all':
        continue
    run_names.append(n)
    for sf in ET.parse(x).getroot().iter('sourcefile'):
        f = cmap.get(sf.get('name'))
        if f:
            per_run[f][n] = per_run[f].get(n, 0) + sum(1 for l in sf.findall('line') if int(l.get('ci')) > 0)
# nextflow.config compiles to _nf_config_* classes whose hash is not derivable; the report script mapped
# them by line numbers. Every launch parses it, so its per-run presence is the run list itself and the
# covered counts are coverage.tsv's columns.
if 'nextflow.config' in covtsv and int(covtsv['nextflow.config']['all_lines']) > 0:
    for n in run_names:
        per_run['nextflow.config'][n] = int(covtsv['nextflow.config'].get({'preview': 'preview_lines', 'qc_only': 'qc_only_lines', 't_ottilie_e2e': 'e2e_lines'}.get(n, 'all_lines'), 0))

def reached(f):
    """-> (status, runs, reason)   status: yes | no | n/a"""
    k = kind(f)
    if k != 'nextflow code':
        why = {'task script (bin)': 'runs inside the task container; JaCoCo sees the head JVM only (needs coverage.py / bash tracing, a separate track)',
               'tooling script (bin)': 'developer tooling, never run by the pipeline',
               'module test fixture': 'nf-core module test files; not executed by the owned suite and not head-JVM code',
               'module metadata': 'not executed',
               'nf-core patch': 'applied at install time, not executed',
               'params / overlay file': 'data read by a script or the launch form, not compiled code'}.get(k, 'not head-JVM code')
        return 'n/a', [], why
    row = covtsv.get(f)
    hits = [n for n in run_names if per_run.get(f, {}).get(n, 0) > 0]
    if row is None:
        if f.endswith('.config'):
            if f in included_conf:
                return 'n/a', [], 'profile / include that no measured run selected; would be seen if a run used it'
            return 'n/a', [], 'config passed with -c only (deployment); no measured run loads it'
        return 'no', [], 'never included by any measured run (no class compiled)'
    if int(row['all_lines']) > 0:
        if not hits:
            hits_note = 'covered in coverage.tsv but no per-run XML maps to it'
            return 'yes', [], hits_note
        return 'yes', hits, ''
    return 'no', [], 'compiled (included) by a run, no line executed'

# ---------------------------------------------------------------- unit test declared (commit gate TESTMAP)
testmap = {}
for m in re.finditer(r"\['([^']+)'\]=('([^']+)'|(\w+))", open('bin/check_snapshot_staged.sh').read()):
    testmap[m.group(1)] = (m.group(3) or m.group(4)).split()
def unit_tests(f):
    out = []
    for p, ts in testmap.items():
        if f == p or f.startswith(p):
            out += ts
    return sorted(set(out))

# ---------------------------------------------------------------- 3. cross-check with SAREK_MODIFICATIONS.md
MODS = 'docs/dev-practices/SAREK_MODIFICATIONS.md'
mods = open(MODS, errors='replace').read().split('\n')
def section(heading_re):
    out = []; on = False
    for l in mods:
        if re.search(heading_re, l):
            on = True; continue
        if on and l.startswith('## '):
            break
        if on:
            out.append(l)
    return out
def table_names(heading_re):
    return [re.sub(r'`.*', '', re.sub(r'^\| `', '', l)) for l in section(heading_re) if re.match(r'^\| `', l)]
def bt(lines):
    return re.findall(r'`([^`]+)`', '\n'.join(lines))

doc = {
    'subworkflows/local ADDED': set(table_names(r'^## `subworkflows/local/` — ADDED')),
    'subworkflows/local MODIFIED': set(table_names(r'^## `subworkflows/local/` — MODIFIED')),
    'modules/local ADDED': set(table_names(r'^## `modules/local/` — ADDED')),
    'modules/nf-core PATCHED': set(),
    'modules/nf-core ADDED': set(),
    'conf ADDED': set(table_names(r'^## `conf/` — ADDED')),
    'conf MODIFIED': set(),
    'root MODIFIED': set(),
}
for l in section(r'^## `modules/nf-core/` — PATCHED'):
    if re.match(r'^\| `', l):
        cell = l.split('|')[1]
        mod = re.findall(r'`([^`]+)`', cell)
        base = os.path.dirname(mod[0])
        for t in mod:
            doc['modules/nf-core PATCHED'].add(t if '/' in t else f'{base}/{t}')
for l in section(r'^## `modules/nf-core/` — ADDED'):
    doc['modules/nf-core ADDED'] |= {t for t in re.findall(r'`([^`]+)`', l) if re.match(r'^[\w-]+(/[\w-]+)?$', t) and os.path.isdir(f'modules/nf-core/{t}')}
    if l.startswith('Upstream-managed'):
        break
para = []
for l in section(r'^## `conf/` — MODIFIED'):
    if not l.strip() and para:
        break
    if l.strip():
        para.append(l)
doc['conf MODIFIED'] = {t for t in bt(para) if t.endswith('.config') and os.path.isfile(f'conf/{t}')}
for l in mods:
    if re.match(r'^\| (Root files|Core workflow) \|', l):
        doc['root MODIFIED'] |= {t for t in bt([l]) if os.path.isfile(t) and t in files}

main_dirs = {os.path.dirname(f) for f in files if os.path.basename(f) == 'main.nf'}
def unit_of(f):
    """the module / subworkflow a file belongs to: its nearest ancestor directory holding a main.nf"""
    d = os.path.dirname(f)
    while d and d not in main_dirs:
        d = os.path.dirname(d)
    return d
def dir_scope(prefix):
    """unit-level roll-up: ADDED if the unit's directory is not upstream, else MODIFIED if any file differs"""
    out = {}
    for f in files:
        if not f.startswith(prefix) or '/tests/' in f:
            continue
        u = unit_of(f)
        if not u.startswith(prefix) or u == prefix.rstrip('/'):
            continue
        d = u[len(prefix):]
        if not os.path.isdir(os.path.join(UP, u)):
            out[d] = 'ADDED'
        elif out.get(d) != 'ADDED' and (scope[f] == 'MODIFIED' or out.get(d) is None):
            out[d] = 'MODIFIED' if scope[f] == 'MODIFIED' or out.get(d) == 'MODIFIED' else 'PRISTINE'
    return out
tree = {
    # the doc (and bin/check_doc_drift.sh) name local units by their FIRST-level directory: breseq, not breseq/summary_mqc
    'subworkflows/local ADDED': {d.split('/')[0] for d, s in dir_scope('subworkflows/local/').items() if s == 'ADDED'},
    'subworkflows/local MODIFIED': {d.split('/')[0] for d, s in dir_scope('subworkflows/local/').items() if s == 'MODIFIED'},
    'modules/local ADDED': {d.split('/')[0] for d, s in dir_scope('modules/local/').items() if s == 'ADDED'},
    'modules/nf-core ADDED': {d for d, s in dir_scope('modules/nf-core/').items() if s == 'ADDED'},
    'modules/nf-core PATCHED': {f[len('modules/nf-core/'):] for f in files if f.startswith('modules/nf-core/') and scope[f] == 'MODIFIED' and '/tests/' not in f},
    'conf ADDED': {f[5:] for f in files if f.startswith('conf/') and scope[f] == 'ADDED'},
    'conf MODIFIED': {f[5:] for f in files if f.startswith('conf/') and scope[f] == 'MODIFIED'},
    'root MODIFIED': {f for f in ('main.nf', 'nextflow.config', 'workflows/sarek/main.nf') if scope[f] == 'MODIFIED'},
}
# fork code the doc has no inventory for at all
undocumented_areas = {
    'subworkflows/nf-core MODIFIED (no section in the doc)': {f for f in files if f.startswith('subworkflows/nf-core/') and scope[f] != 'PRISTINE'},
    'bin/ task scripts the doc never names': {f for f in sorted(task_scripts) if os.path.basename(f) not in '\n'.join(mods)},
    'modules/local MODIFIED (doc says 0)': {f for f in files if f.startswith('modules/local/') and scope[f] == 'MODIFIED'},
}
disagreements = []
for key in doc:
    only_tree = sorted(tree[key] - doc[key]); only_doc = sorted(doc[key] - tree[key])
    for x in only_tree:
        disagreements.append((key, x, 'in the tree, not in the doc\'s list'))
    for x in only_doc:
        if key == 'modules/nf-core PATCHED' and not os.path.exists(os.path.join(UP, 'modules/nf-core', x)):
            disagreements.append((key, x, 'the doc calls it patched; the module is not in sarek 3.5.1, so it is ADDED here (the patch is relative to nf-core/modules, which this inventory cannot check)'))
        else:
            disagreements.append((key, x, 'in the doc\'s list, not so in the tree'))
for key, s in undocumented_areas.items():
    for x in sorted(s):
        disagreements.append((key, x, 'fork change with no inventory row'))

# the coverage report classifies too (line diff: insert / replace); compare on the files both see
cov_vs_mine = []
for f, r in covtsv.items():
    if f in scope and r['status'] in ('added', 'modified', 'pristine') and r['status'] != scope[f].lower():
        cov_vs_mine.append((f, r['status'], scope[f]))

# ---------------------------------------------------------------- the per-file table
rows = []
for f in files:
    st, hits, why = reached(f)
    cr = covtsv.get(f, {})
    rows.append(dict(scope=scope[f], file=f, kind=kind(f), reached=st, runs=[run_label(h) for h in hits], why=why, tests=unit_tests(f),
                     cov_status=cr.get('status', ''), closures=int(cr.get('closures', 0) or 0), entered=int(cr.get('all_closures', 0) or 0)))
order = {'ADDED': 0, 'MODIFIED': 1, 'PRISTINE': 2}
rows.sort(key=lambda r: (order[r['scope']], r['file']))

def summary(sel):
    c = collections.defaultdict(collections.Counter)
    for r in rows:
        if sel(r):
            c[r['scope']][r['reached']] += 1
    return c

sum_all = summary(lambda r: True)
sum_code = summary(lambda r: r['kind'] == 'nextflow code')
sum_cfgnf = summary(lambda r: r['kind'] == 'nextflow code' and not ('/tests/' in r['file']))

head = git('rev-parse', '--short', 'HEAD').strip()
dirty = git('status', '--porcelain', '--untracked-files=no').strip()
today = datetime.date.today().isoformat()
up_how = ('`nf-core pipelines download sarek --revision 3.5.1` (the `3_5_1/` directory of its output)' if UP.endswith('3_5_1')
          else 'the GitHub tag archive of 3.5.1' if 'sarek-3.5.1' in UP else 'see the path')

def line(r):
    runs = ', '.join(r['runs']) if r['runs'] else ('' if r['reached'] != 'yes' else '(see note)')
    tests = ', '.join(r['tests'])
    note = r['why']
    clo = f"{r['entered']}/{r['closures']}" if r['closures'] else ''
    return f"| {r['scope']} | `{r['file']}` | {r['kind']} | {r['reached']} | {runs} | {clo} | {tests} | {note} |"

out = []
out.append(f"# Test inventory per scope ({today})\n")
out.append("Of the files the fork **added** or **modified** relative to pristine nf-core/sarek 3.5.1, how many does any "
           "test reach. Generated by `bin/test_inventory.py` (GitHub issue #14, item 4); replaces the folder-based "
           "\"6 of 89 files have a test\" figure, which counted the `.nf` files with a `TESTMAP` entry among the 89 "
           "`.nf` files of `main.nf` + `workflows/` + `subworkflows/local/` + `modules/local/` that the coverage run compiled.\n")
out.append("**Scope** (per file, byte comparison with the pristine tree): ADDED = not in 3.5.1; MODIFIED = in 3.5.1, "
           "content differs; PRISTINE = byte-identical. **Reached** = the coverage run's per-file table shows at least one "
           "covered line in some run (`yes`), none although the file was compiled or includable (`no`), or the method "
           "cannot see the file (`n/a`, reason given: `bin/` runs in the task shell or container, module metadata and "
           "nf-core test fixtures are never executed, a `-c`-only config is not loaded by any test). **Unit test** = the "
           "commit gate's `TESTMAP` names a test for the path (declared, as opposed to measured).\n")

out.append("## Summary\n")
def sum_table(title, c, what):
    out.append(f"### {title}\n")
    out.append("| Scope | files | reached | not reached | not measurable |")
    out.append("|---|---:|---:|---:|---:|")
    tot = collections.Counter()
    for s in ('ADDED', 'MODIFIED', 'PRISTINE'):
        n = sum(c[s].values()); tot.update(c[s]); tot['n'] += n
        out.append(f"| {s} | {n} | {c[s]['yes']} | {c[s]['no']} | {c[s]['n/a']} |")
    out.append(f"| **all** | {tot['n']} | {tot['yes']} | {tot['no']} | {tot['n/a']} |\n")
    for s in ('ADDED', 'MODIFIED'):
        n = sum(c[s].values()); m = c[s]['yes'] + c[s]['no']
        if m:
            out.append(f"- **{s}, {what}:** {c[s]['yes']} of the {m} measurable files are reached by at least one run "
                       f"({100 * c[s]['yes'] / m:.0f} %); {c[s]['no']} are not; {c[s]['n/a']} cannot be measured this way.")
        else:
            out.append(f"- **{s}, {what}:** {n} files, none measurable by the head-JVM method.")
    s = 'PRISTINE'; m = c[s]['yes'] + c[s]['no']
    if m:
        out.append(f"- **PRISTINE, {what}:** {c[s]['yes']} of {m} measurable upstream files are reached; this is context, not a target.")
    out.append("")
sum_table("All files in scope", sum_all, "all files")
sum_table("Nextflow code only (`.nf` and `.config`, the files the head-JVM method can see)", sum_code, "Nextflow code")

# the sentence
A = sum_code['ADDED']; M = sum_code['MODIFIED']
fork_yes = A['yes'] + M['yes']; fork_meas = fork_yes + A['no'] + M['no']; fork_na = A['n/a'] + M['n/a']
fork_all = sum(A.values()) + sum(M.values())
mod_no = [r for r in rows if r['scope'] == 'MODIFIED' and r['reached'] == 'no']
add_no = [r for r in rows if r['scope'] == 'ADDED' and r['reached'] == 'no' and r['kind'] == 'nextflow code']
decl = sum(1 for r in rows if r['kind'] == 'nextflow code' and r['scope'] != 'PRISTINE' and r['tests'])
loaded_idle = [r for r in rows if r['scope'] != 'PRISTINE' and r['reached'] == 'yes' and r['closures'] and not r['entered']]
out.append("### The one sentence\n")
out.append(f"> Of the {fork_all} Nextflow files the fork added or changed, the test suite executes {fork_yes} of the "
           f"{fork_meas} that can be measured ({100 * fork_yes / fork_meas:.0f} %); {len(mod_no)} modified and {len(add_no)} added files are never "
           f"run by any test, and {fork_na} are configs no test loads. Only {decl} of the {fork_all} have a unit test declared in the commit gate.\n")
exercised = fork_yes - len(loaded_idle)
out.append(f"> Stricter: {exercised} of the {fork_meas} measurable fork files did data-driven work in some run (a closure that needs a "
           f"channel item or a task was entered, or the file has none); {len(loaded_idle)} more were loaded but never did any.\n")
out.append("**Reached is a low bar.** A process definition's lines execute while the DAG is built, whether or not a task is "
           "ever created for it, so a module can read `yes` from the plan-only run alone. The closure column tells the two apart: "
           f"{len(loaded_idle)} fork file(s) read as reached without a single data-driven closure entered in any run"
           + (': ' + ', '.join('`' + r['file'] + '`' for r in loaded_idle) if loaded_idle else '') + ".\n")
out.append("Counting every file kind (scripts in `bin/`, module metadata, nf-core test fixtures), the fork's footprint is "
           f"{sum(sum_all['ADDED'].values())} added and {sum(sum_all['MODIFIED'].values())} modified files, of which "
           f"{sum_all['ADDED']['n/a'] + sum_all['MODIFIED']['n/a']} are outside what JaCoCo on the head JVM can see.\n")

out.append("## Disagreements with `SAREK_MODIFICATIONS.md`\n")
if disagreements:
    out.append("| Inventory | Item | Finding |")
    out.append("|---|---|---|")
    for k, x, why in disagreements:
        out.append(f"| {k} | `{x}` | {why} |")
else:
    out.append("None: every ADDED / MODIFIED set equals the doc's list.")
out.append("")
out.append("Against the coverage run's own `status` column (a line diff, on the files both classify): "
           + (f"{len(cov_vs_mine)} differences: " + ', '.join(f'`{f}` {c} vs {m}' for f, c, m in cov_vs_mine) if cov_vs_mine
              else f"agrees on all {sum(1 for f, r in covtsv.items() if f in scope and r['status'] != 'nf-core')} files.") + "\n")
out.append("Directory-level comparison for `modules/` and `subworkflows/` (the doc lists directories), file-level for "
           "`conf/` and the root files. The doc's `conf/ — MODIFIED` list is prose; the backticked `*.config` names of "
           "that paragraph that exist under `conf/` are taken as its list. `MODIFIED` here is a byte comparison; the "
           "coverage report's `status` column is a line-diff (insert/replace), so a deletion-only change reads "
           "`pristine` there and `MODIFIED` here. `nextflow_schema.json` and `assets/` are outside this inventory's scope.\n")

out.append("## Fork files no test reaches\n")
out.append("The finding this inventory exists for: MODIFIED first, then ADDED. `nextflow code` only; `n/a` rows are in the full list.\n")
out.append("| Scope | File | Why not reached | Coverage-run status |")
out.append("|---|---|---|---|")
for r in mod_no + add_no:
    out.append(f"| {r['scope']} | `{r['file']}` | {r['why']} | {r['cov_status'] or 'no row'} |")
out.append("")

out.append("## Full per-file list\n")
out.append(f"Sorted by scope, then path. Runs: `plan-only` = `nextflow run -preview`, `qc_only` = the `--qc_only` run, "
           f"`e2e` = `ottilie_e2e.nf.test`, the others are the named test files; {len(run_names)} run sets recorded.\n")
out.append("Closures = data-driven closures entered / present (operator bodies, `script:` / `when:` / directive closures, lazy "
           "config values), merged over every run: a file whose closures were all skipped was loaded but never did work.\n")
out.append("| Scope | File | Kind | Reached | Runs that reach it | Closures entered | Unit test (TESTMAP) | Note |")
out.append("|---|---|---|---|---|---|---|---|")
for r in rows:
    out.append(line(r))
out.append("")

out.append("## Provenance\n")
out.append(f"- **Working tree:** `{head}`" + (" with uncommitted changes:\n```\n" + dirty + "\n```" if dirty else ", clean (tracked files)."))
out.append(f"- **Pristine 3.5.1:** `{UP}`, fetched with {up_how}; {sum(len(f) for _, _, f in os.walk(UP))} files.")
out.append(f"- **Coverage run:** `{COV}` — commit `{run_info['commit']}`, started {run_info['date']}; "
           f"{run_info['versions']}. Runs recorded: {', '.join(runs_recorded)}.")
if md5_note:
    out.append(f"- Config files not present at the coverage commit (class map used today's text): {', '.join('`' + f + '`' for f in md5_note)}.")
if head != cov_commit:
    changed = [l for l in git('diff', '--name-only', cov_commit, 'HEAD', '--', 'main.nf', 'nextflow.config', *SCOPE_DIRS).split('\n') if l]
    out.append(f"- **The tree is {head}, the coverage data {cov_commit}.** In-scope files changed between them: "
               + (', '.join('`' + c + '`' for c in changed) if changed else 'none')
               + ". Their `reached` row is from the older text; scope is from today's text.")
out.append(f"- **Script:** `bin/test_inventory.py`, run {today}; arguments `--upstream {a.upstream} --coverage {a.coverage}`.")
out.append("")
out.append("## Re-point\n")
out.append("Once a newer `tests/nf_coverage.sh run` has finished in `output_coverage/` (its `RUN_INFO.txt` lists every run with an exit code):\n")
out.append("```bash")
out.append(f"python bin/test_inventory.py --upstream {a.upstream} --coverage output_coverage --out docs/dev-practices/test_inventory_$(date +%F).md")
out.append("```")
out.append("")

os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
open(a.out, 'w').write('\n'.join(out))
if a.tsv:
    with open(a.tsv, 'w') as o:
        o.write('scope\tfile\tkind\treached\truns\tunit_tests\tnote\tcoverage_status\n')
        for r in rows:
            o.write('\t'.join([r['scope'], r['file'], r['kind'], r['reached'], ','.join(r['runs']), ','.join(r['tests']), r['why'], r['cov_status']]) + '\n')

# ---------------------------------------------------------------- console
print(f"tree {head}{' (dirty)' if dirty else ''}  upstream {UP}  coverage {COV} ({cov_commit})  files in scope: {len(files)}")
for title, c in (('all files', sum_all), ('nextflow code', sum_code)):
    print(f"\n{title:14} {'files':>5} {'reached':>8} {'no':>5} {'n/a':>5}")
    for s in ('ADDED', 'MODIFIED', 'PRISTINE'):
        print(f"  {s:12} {sum(c[s].values()):5} {c[s]['yes']:8} {c[s]['no']:5} {c[s]['n/a']:5}")
print(f"\nnot reached, MODIFIED ({len(mod_no)}):"); [print('  ', r['file'], '-', r['why']) for r in mod_no]
print(f"not reached, ADDED nextflow code ({len(add_no)}):"); [print('  ', r['file'], '-', r['why']) for r in add_no]
print(f"\ndisagreements with {MODS} ({len(disagreements)}):")
for k, x, why in disagreements:
    print(f"  [{k}] {x}: {why}")
print(f"\nwrote {a.out}" + (f" and {a.tsv}" if a.tsv else ''))
