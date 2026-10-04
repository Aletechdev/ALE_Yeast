#!/usr/bin/env python
"""Coverage of the pipeline's Nextflow code (.nf and .config) from JaCoCo data taken on the head JVM.

Called by tests/nf_coverage.sh; docs/dev-practices/nextflow_code_coverage.md explains the measures,
how to read the output and what the numbers cannot show.

Measures, each reported for one or more named run sets (one JaCoCo XML report per set):
  lines       executable lines (lines that own bytecode) with at least one covered instruction
  closures    closures that run only when data arrives - operator bodies, a process's script / when /
              directive closures, lazy config values - whose body was entered at least once
  branches    JaCoCo's branch counter per line; "seen every way" = a line with branches, none missed
  fork ...    the same, restricted to lines that are not in pristine nf-core/sarek (--upstream)

Class -> source file
  .nf file                  `Script_<16 hex>: /abs/path.nf` lines of the runs' .nextflow.log files
  includeConfig'd file      the class is named Script<MD5 of the file text, upper case>
  nextflow.config, -c file  the class is named _nf_config_<hash>; matched by its line numbers to the
                            files in the log's "Parsing config file:" lines

Usage
  nf_coverage_report.py --dump CLASSDIR --logs 'GLOB' [--logs ...] [--upstream SAREK_DIR] \\
      --xml NAME=report.xml [--xml ...] [--no-tables] [--files] [--unique A,B,C] \\
      [--uncovered SET] [--annotate SET:path-suffix] [--tsv out.tsv] [--lcov SET:out.info]
"""
import argparse, collections, difflib, glob, hashlib, os, re, subprocess, sys
import xml.etree.ElementTree as ET

ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument('--root', default=os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'), help='repo root (default: the parent of tests/)')
ap.add_argument('--dump', required=True, help="the agent's classdumpdir")
ap.add_argument('--logs', action='append', default=[], help='glob of .nextflow.log files of the measured runs')
ap.add_argument('--upstream', help='pristine nf-core/sarek tree: lines not in it are fork lines')
ap.add_argument('--xml', action='append', default=[], help='NAME=jacoco-report.xml, one per run set')
ap.add_argument('--no-tables', action='store_true', help='skip the summary tables')
ap.add_argument('--files', action='store_true', help='per-file fork lines and closures')
ap.add_argument('--unique', help='A,B,C: what each of these run sets covers that none of the others does')
ap.add_argument('--uncovered', help='SET: fork lines, closures and one-sided conditions that set never executed')
ap.add_argument('--annotate', help='SET:path-suffix - one source file, line by line')
ap.add_argument('--tsv', help='per-file counts')
ap.add_argument('--lcov', help='SET:out.info - LCOV tracefile (editor gutters, genhtml, Codecov)')
a = ap.parse_args()
ROOT = os.path.realpath(a.root) + '/'

# ---------------------------------------------------------------- class -> file
cmap = {}; top_cfg = set()
for g in a.logs:
    for p in glob.glob(g, recursive=True):
        for line in open(p, errors='replace'):
            m = re.match(r'^\s+(Script_\w+): (/\S+\.nf)\s*$', line)
            if m:
                cmap[m.group(1)] = os.path.realpath(m.group(2))
            m = re.search(r'ConfigBuilder - Parsing config file: (/\S+)', line)
            if m and os.path.exists(m.group(1)):
                top_cfg.add(os.path.realpath(m.group(1)))
for d, dirs, fs in os.walk(ROOT):
    dirs[:] = [x for x in dirs if x not in ('.git', 'work', '.nextflow', '.nf-test', 'data') and not x.startswith(('output', 'work_'))]
    for f in fs:
        if f.endswith('.config'):
            p = os.path.join(d, f)
            cmap.setdefault('Script' + hashlib.md5(open(p, 'rb').read()).hexdigest().upper(), os.path.realpath(p))

# ---------------------------------------------------------------- static: which class owns which lines
jp = os.path.join(os.path.dirname(os.path.abspath(a.dump)), 'javap_l.txt')
if not os.path.exists(jp) or os.path.getmtime(jp) < os.path.getmtime(a.dump):
    names = sorted(f for f in os.listdir(a.dump) if f.startswith(('Script', '_nf_config_')))
    with open(jp, 'w') as out:
        for i in range(0, len(names), 400):
            subprocess.run(['javap', '-l', '-p'] + names[i:i + 400], cwd=a.dump, stdout=out, stderr=subprocess.DEVNULL)
cls_lines = collections.defaultdict(lambda: collections.defaultdict(set))   # class -> method -> lines
cur = meth = None
for line in open(jp):
    m = re.match(r'^(?:public |final |abstract )*class (\S+)', line)
    if m:
        cur = m.group(1); meth = None; continue
    m = re.match(r'^  \S.*?([\w$<>]+)\(.*\);\s*$', line)
    if m:
        meth = m.group(1); continue
    m = re.match(r'^\s+line (\d+): \d+', line)
    if m and cur and meth:
        cls_lines[cur][meth].add(int(m.group(1)))

def all_lines(cls):
    return set().union(*cls_lines[cls].values()) if cls_lines.get(cls) else set()

_text = {}
def text(f):
    if f not in _text:
        _text[f] = open(f, errors='replace').read().split('\n') if os.path.exists(f) else []
    return _text[f]

def code_lines(f):
    out = set(); block = False
    for i, l in enumerate(text(f), 1):
        t = l.strip()
        if block:
            block = '*/' not in t; continue
        if t.startswith('/*'):
            block = '*/' not in t; continue
        if t and not t.startswith('//'):
            out.add(i)
    return out

# nextflow.config and -c files: the hash in _nf_config_<hash> is not derivable here, so each class is
# matched to the one candidate file whose code lines contain all of the class's lines (closest fit)
for t in sorted({c.split('$', 1)[0] for c in cls_lines if c.startswith('_nf_config_')}):
    ls = set().union(*(all_lines(c) for c in cls_lines if c.split('$', 1)[0] == t))
    fits = sorted((len(code_lines(p) - ls), p) for p in top_cfg if ls and ls <= code_lines(p))
    if fits and (len(fits) == 1 or fits[0][0] < fits[1][0]):
        cmap[t] = fits[0][1]
    else:
        print(f"# unmapped config class {t} ({len(ls)} lines; {len(fits)} candidate files)", file=sys.stderr)

has_child = {c.rsplit('$', 1)[0] for c in cls_lines if '$' in c}
LAZY = re.compile(r'(=|:|,|\[|\()\s*\{')          # a closure used as a value: `ext.args = {`, `saveAs: {`, `path: {`
def kind(cls, f):
    """top      the script body: includes and definitions (runs when the file is loaded)
       body     a process definition or a workflow body (runs once, while the DAG is built); in a
                config file a scope block - process {}, withName: {} (runs when the config is parsed)
       closure  runs only when data arrives: an operator closure, a process script / when / directive
                closure, a lazy config value
       function a named function, or a closure inside one"""
    parts = cls.split('$')[1:]
    if not parts:
        return 'top'
    if not re.match(r'_run(Script)?_closure\d+$', parts[0]):
        return 'function'
    if len(parts) == 1:
        return 'body'
    ls = all_lines(cls)
    if f.endswith('.config'):
        src = text(f)
        if not ls or not src or cls in has_child:
            return 'body'            # a scope block: it contains other closures
        l0 = min(ls)
        if LAZY.search(src[l0 - 1] if l0 <= len(src) else ''):
            return 'closure'
        i = l0 - 2
        while i >= 0 and (not src[i].strip() or src[i].strip().startswith('//')):
            i -= 1
        return 'closure' if i >= 0 and re.search(r'(=|:)\s*\{\s*(\w+\s*->)?\s*(//.*)?$', src[i]) else 'body'
    if len(parts) == 2 and not cls_lines.get(cls.rsplit('$', 1)[0]):
        return 'body'                # a workflow body: its wrapper closure owns no lines
    return 'closure'

# ---------------------------------------------------------------- per run set: lines, closures, functions, branches
def hit(el):
    return any(x.get('type') == 'INSTRUCTION' and int(x.get('covered')) > 0 for x in el.findall('counter'))

runs = collections.OrderedDict()
closures = {}            # class -> (file, first line)
funcs = {}               # (class, method) -> (file, first line)
exe = collections.defaultdict(set)   # file -> executable lines
for spec in a.xml:
    name, path = spec.split('=', 1)
    cov = collections.defaultdict(set); ccov = set(); fcov = set(); br = collections.defaultdict(dict)
    root = ET.parse(path).getroot()
    for sf in root.iter('sourcefile'):
        f = cmap.get(sf.get('name'))
        if not f:
            continue
        for l in sf.findall('line'):
            nr = int(l.get('nr')); exe[f].add(nr)
            if int(l.get('ci')) > 0:
                cov[f].add(nr)
            if int(l.get('mb')) + int(l.get('cb')) > 0:
                br[f][nr] = (int(l.get('mb')), int(l.get('cb')))
    for c in root.iter('class'):
        cn = c.get('name'); f = cmap.get(cn.split('$', 1)[0])
        if not f:
            continue
        k = kind(cn, f)
        if k == 'closure' and all_lines(cn):
            closures[cn] = (f, min(all_lines(cn)))
            if any(hit(m) for m in c.findall('method') if m.get('name') == 'doCall'):
                ccov.add(cn)
        if k == 'top':
            for m in c.findall('method'):
                mn = m.get('name')
                if mn in ('<init>', '<clinit>', 'main', 'run', 'runScript') or mn.startswith('$') or not cls_lines[cn].get(mn):
                    continue
                funcs[(cn, mn)] = (f, min(cls_lines[cn][mn]))
                if hit(m):
                    fcov.add((cn, mn))
    runs[name] = (cov, ccov, fcov, br)

# ---------------------------------------------------------------- fork lines: not in pristine upstream
_fork = {}
def fork_lines(f):
    if f in _fork:
        return _fork[f]
    rel = f.replace(ROOT, '')
    up = os.path.join(a.upstream, rel) if a.upstream else None
    if up and not os.path.exists(up) and rel.startswith(('modules/nf-core/', 'subworkflows/nf-core/')):
        _fork[f] = (set(), 'nf-core')     # installed from nf-core/modules, not in sarek: upstream-authored, no baseline here to diff
    elif not up or not os.path.exists(up):
        _fork[f] = (set(range(1, len(text(f)) + 1)), 'added')
    else:
        theirs = open(up, errors='replace').read().split('\n')
        s = set()
        for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, theirs, text(f), autojunk=False).get_opcodes():
            if tag in ('replace', 'insert'):
                s |= set(range(j1 + 1, j2 + 1))
        _fork[f] = (s, 'modified' if s else 'pristine')
    return _fork[f]

def grp(f):
    r = f.replace(ROOT, '')
    if r.endswith('.config'):
        return 'conf/modules' if r.startswith('conf/modules') else 'config (other)'
    for p in ('modules/local', 'subworkflows/local', 'modules/nf-core', 'subworkflows/nf-core', 'workflows'):
        if r.startswith(p):
            return p
    return 'main.nf' if r == 'main.nf' else 'other'

def pct(c, n):
    return f"{c:5}/{n:<5} {100 * c / n:5.1f}%" if n else f"{'-':>17}"

files = sorted(f for f in exe if f.startswith(ROOT) and os.path.exists(f))   # nf-test's temporary wrapper scripts are gone by now
names = list(runs)

# ---------------------------------------------------------------- one file, line by line
if a.annotate:
    setn, suf = a.annotate.split(':', 1)
    f = [x for x in files if x.endswith(suf)][0]
    cov, ccov, _, br = runs[setn]; fl = fork_lines(f)[0]
    inside = {ln for c, (cf, _) in closures.items() if cf == f for ln in all_lines(c)}
    dead = {ln for c, (cf, _) in closures.items() if cf == f and c not in ccov for ln in all_lines(c)}
    print(f"# {f.replace(ROOT, '')} [{setn}]   + ran   - never ran   ~ the line ran, but a closure on it was never entered   (blank: no bytecode)")
    print("#   F = not in upstream sarek   c = inside a closure that needs data   m/n = m of n branches never taken")
    for i, t in enumerate(text(f), 1):
        mark = ' ' if i not in exe[f] else ('-' if i not in cov[f] else ('~' if i in dead else '+'))
        b = br[f].get(i); bs = f"{b[0]}/{b[0] + b[1]}" if b and b[0] else ''
        print(f"{mark}{'F' if i in fl else ' '}{'c' if i in inside else ' '} {bs:5} {i:4} {t[:120]}")
    sys.exit()

# ---------------------------------------------------------------- summary tables
def table(title, sel):
    print(f"\n## {title}")
    print(f"{'group':22} {'files':>5}  " + '  '.join(f"{n:>17}" for n in names))
    tot = collections.defaultdict(lambda: collections.defaultdict(lambda: [0, 0])); nf = collections.Counter()
    for f in files:
        cnt = sel(f)
        if cnt is None:
            continue
        for g in (grp(f), 'TOTAL'):
            nf[g] += 1
            for n in names:
                c, t = cnt(n); tot[g][n][0] += c; tot[g][n][1] += t
    for g in sorted(tot, key=lambda g: (g == 'TOTAL', g)):
        print(f"{g:22} {nf[g]:5}  " + '  '.join(pct(*tot[g][n]) for n in names))

def line_sel(only_fork):
    def sel(f):
        ls = exe[f] & fork_lines(f)[0] if only_fork else exe[f]
        return (lambda n: (len(ls & runs[n][0][f]), len(ls))) if ls else None
    return sel
def clo_sel(only_fork):
    def sel(f):
        cs = [c for c, (cf, ln) in closures.items() if cf == f and (not only_fork or ln in fork_lines(f)[0])]
        return (lambda n: (sum(1 for c in cs if c in runs[n][1]), len(cs))) if cs else None
    return sel
def fn_sel(only_fork):
    def sel(f):
        fs = [k for k, (cf, ln) in funcs.items() if cf == f and (not only_fork or ln in fork_lines(f)[0])]
        return (lambda n: (sum(1 for k in fs if k in runs[n][2]), len(fs))) if fs else None
    return sel
def br_sel(only_fork, what):
    def sel(f):
        def cnt(n):
            vs = [v for nr, v in runs[n][3][f].items() if not only_fork or nr in fork_lines(f)[0]]
            if what == 'branches':
                return (sum(v[1] for v in vs), sum(v[0] + v[1] for v in vs))
            return (sum(1 for v in vs if v[0] == 0), len(vs))
        return cnt if any(cnt(n)[1] for n in names) else None
    return sel

if not a.no_tables:
    print(f"class->file map: {len(cmap)} entries; source files with coverage data: {len(files)}; data-driven closures: {len(closures)}; named functions: {len(funcs)}")
    table('Executable lines covered - all code', line_sel(False))
    table('Data-driven closures entered - all code', clo_sel(False))
    if a.upstream:
        table('Executable lines covered - fork lines only', line_sel(True))
        table('Data-driven closures entered - fork closures only', clo_sel(True))
        table('Named functions entered - fork functions only', fn_sel(True))
        table('Branches taken - fork lines only', br_sel(True, 'branches'))
        table('Conditions seen every way - fork lines only (lines with branches, none missed)', br_sel(True, 'lines'))

if a.unique:
    us = a.unique.split(',')
    print("\n## What each run set covers that none of the others listed does (fork = not in upstream sarek)")
    print(f"{'run set':30} {'lines':>6} {'fork lines':>10} {'closures':>8} {'fork closures':>13}   fork files gaining")
    for u in us:
        nl = nfl = 0; gain = collections.Counter()
        for f in files:
            only = (runs[u][0][f] & exe[f]) - set().union(*(runs[o][0][f] for o in us if o != u))
            nl += len(only); k = len(only & fork_lines(f)[0]); nfl += k
            if k:
                gain[f.replace(ROOT, '')] += k
        onlyc = [c for c in runs[u][1] - set().union(*(runs[o][1] for o in us if o != u)) if c in closures and closures[c][0] in files]
        fc = [c for c in onlyc if closures[c][1] in fork_lines(closures[c][0])[0]]
        for c in fc:
            gain[closures[c][0].replace(ROOT, '')] += 0
        print(f"{u:30} {nl:6} {nfl:10} {len(onlyc):8} {len(fc):13}   " + ', '.join(os.path.dirname(k) if k.endswith('main.nf') else k for k, _ in gain.most_common(4)))

if a.files:
    print("\n## Per file, fork lines only: lines | closures per run set   (file status vs upstream sarek)")
    for f in files:
        ls = exe[f] & fork_lines(f)[0]
        cs = [c for c, (cf, ln) in closures.items() if cf == f and ln in fork_lines(f)[0]]
        if not ls and not cs:
            continue
        row = '  '.join(f"{len(ls & runs[n][0][f]):3}/{len(ls):<3} {sum(1 for c in cs if c in runs[n][1]):3}/{len(cs):<3}" for n in names)
        print(f"  {row}  {fork_lines(f)[1]:8} {f.replace(ROOT, '')}")

if a.uncovered:
    cov, ccov, _, br = runs[a.uncovered]
    print(f"\n## Fork code that run set '{a.uncovered}' never executed")
    print("##   (blank) the line never ran   c = inside a closure that was never entered   b m/n = the line ran, but m of its n branches were never taken")
    for f in files:
        fl = fork_lines(f)[0]; miss = (exe[f] & fl) - cov[f]
        dead = {ln for c, (cf, _) in closures.items() if cf == f and c not in ccov for ln in all_lines(c)} & fl
        part = {nr: v for nr, v in br[f].items() if nr in fl and v[0] > 0 and v[1] > 0 and nr not in dead}
        rows = sorted(miss | dead | set(part))
        if not rows:
            continue
        print(f"\n{f.replace(ROOT, '')}  ({len(miss)} lines never ran, {len(dead - miss)} more inside unentered closures, {len(set(part) - miss)} one-sided conditions)")
        for ln in rows:
            tag = 'c' if ln in dead else (f"b {part[ln][0]}/{sum(part[ln])}" if ln in part and ln not in miss else ' ')
            print(f"   {tag:7} {ln:4}  {text(f)[ln - 1].strip()[:110]}")

if a.lcov:
    setn, out = a.lcov.split(':', 1); cov, ccov, _, br = runs[setn]
    with open(out, 'w') as o:
        for f in files:
            o.write(f"TN:\nSF:{f}\n")
            cs = sorted((ln, c.split('$', 1)[1], c in ccov) for c, (cf, ln) in closures.items() if cf == f)
            for ln, c, _ in cs:
                o.write(f"FN:{ln},{c}\n")
            for _, c, h in cs:
                o.write(f"FNDA:{int(h)},{c}\n")
            o.write(f"FNF:{len(cs)}\nFNH:{sum(h for _, _, h in cs)}\n")
            for ln in sorted(br[f]):
                mb, cb = br[f][ln]
                for i in range(mb + cb):
                    o.write(f"BRDA:{ln},0,{i},{1 if i < cb else 0}\n")
            o.write(f"BRF:{sum(sum(v) for v in br[f].values())}\nBRH:{sum(v[1] for v in br[f].values())}\n")
            for ln in sorted(exe[f]):
                o.write(f"DA:{ln},{1 if ln in cov[f] else 0}\n")
            o.write(f"LF:{len(exe[f])}\nLH:{len(exe[f] & cov[f])}\nend_of_record\n")

if a.tsv:
    with open(a.tsv, 'w') as o:
        o.write('file\tgroup\tstatus\texe_lines\tfork_exe_lines\tclosures\t' + '\t'.join(f"{n}_lines\t{n}_fork_lines\t{n}_closures" for n in names) + '\n')
        for f in files:
            fl = fork_lines(f); ls = exe[f]; cs = [c for c, (cf, _) in closures.items() if cf == f]
            o.write(f"{f.replace(ROOT, '')}\t{grp(f)}\t{fl[1]}\t{len(ls)}\t{len(ls & fl[0])}\t{len(cs)}\t" +
                    '\t'.join(f"{len(ls & runs[n][0][f])}\t{len(ls & fl[0] & runs[n][0][f])}\t{sum(1 for c in cs if c in runs[n][1])}" for n in names) + '\n')
