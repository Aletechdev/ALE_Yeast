"""Build branch_dump.py: a copy of tests/nf_coverage_report.py with three additions and nothing removed.
  --at-commit REV   read every source file (text, config MD5) from `git show REV:path` so the recorded
                    classes/line numbers are matched against the code they were compiled from
  --branch-dump SET print one row per line carrying JaCoCo branches: file, line, mb, cb, fork, group, text
  --fork-dump       print every fork line of every measured file, with an executable flag
The pipeline script is untouched; this copy lives next to this file (regenerate it after changing the report script)."""
import os, sys
here = os.path.dirname(os.path.abspath(__file__))
root = os.path.abspath(os.path.join(here, '..', '..', '..'))  # docs/dev-practices/<this dir>/ -> repo root
src = open(os.path.join(root, 'tests', 'nf_coverage_report.py')).read()

def sub(old, new):
    global src
    assert src.count(old) == 1, f"anchor not unique/found: {old[:60]!r}"
    src = src.replace(old, new)

# the copy lives under docs/dev-practices/<dir>/, not tests/, so the inherited --root default (the parent of the
# script's directory) would point at docs/dev-practices/; make it the repo root
sub("ap.add_argument('--root', default=os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'), help='repo root (default: the parent of tests/)')\n",
    "ap.add_argument('--root', default=os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..'), help='repo root (default: three levels above this copy)')\n")

sub("a = ap.parse_args()\n",
    "ap.add_argument('--at-commit', help='read sources from this git revision instead of the working tree')\n"
    "ap.add_argument('--fork-dump', action='store_true', help='every fork line of every measured file, with an executable flag')\n"
    "ap.add_argument('--branch-dump', help='SET: one row per line with branches (file, line, mb, cb, fork, group, text)')\n"
    "a = ap.parse_args()\n")

sub("ROOT = os.path.realpath(a.root) + '/'\n",
    "ROOT = os.path.realpath(a.root) + '/'\n"
    "def at_commit_bytes(p):\n"
    "    \"\"\"bytes of file p at --at-commit, or None when not given / not tracked there\"\"\"\n"
    "    if not a.at_commit or not p.startswith(ROOT):\n"
    "        return None\n"
    "    r = subprocess.run(['git', '-C', ROOT, 'show', f\"{a.at_commit}:{p[len(ROOT):]}\"], capture_output=True)\n"
    "    return r.stdout if r.returncode == 0 else None\n")

sub("            cmap.setdefault('Script' + hashlib.md5(open(p, 'rb').read()).hexdigest().upper(), os.path.realpath(p))\n",
    "            _b = at_commit_bytes(os.path.realpath(p))\n"
    "            cmap.setdefault('Script' + hashlib.md5(_b if _b is not None else open(p, 'rb').read()).hexdigest().upper(), os.path.realpath(p))\n")

sub("        _text[f] = open(f, errors='replace').read().split('\\n') if os.path.exists(f) else []\n",
    "        _b = at_commit_bytes(f)\n"
    "        _text[f] = _b.decode(errors='replace').split('\\n') if _b is not None else (open(f, errors='replace').read().split('\\n') if os.path.exists(f) else [])\n")

sub("names = list(runs)\n",
    "names = list(runs)\n"
    "\n"
    "if a.fork_dump:\n"
    "    print('file\\tline\\texe\\ttext')\n"
    "    for f in files:\n"
    "        fl = fork_lines(f)[0]; src = text(f)\n"
    "        for nr in sorted(fl):\n"
    "            if nr <= len(src) and src[nr - 1].strip():\n"
    "                print(f\"{f.replace(ROOT, '')}\\t{nr}\\t{int(nr in exe[f])}\\t{src[nr - 1].strip()}\")\n"
    "    sys.exit()\n"
    "if a.branch_dump:\n"
    "    br = runs[a.branch_dump][3]\n"
    "    print('file\\tline\\tmb\\tcb\\tfork\\tgroup\\ttext')\n"
    "    for f in files:\n"
    "        fl = fork_lines(f)[0]; src = text(f)\n"
    "        for nr in sorted(br[f]):\n"
    "            mb, cb = br[f][nr]\n"
    "            t = src[nr - 1].strip() if nr <= len(src) else ''\n"
    "            print(f\"{f.replace(ROOT, '')}\\t{nr}\\t{mb}\\t{cb}\\t{int(nr in fl)}\\t{grp(f)}\\t{t}\")\n"
    "    sys.exit()\n")

out = os.path.join(here, 'branch_dump.py')
open(out, 'w').write(src)
print('wrote', out)
