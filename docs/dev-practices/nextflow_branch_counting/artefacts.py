"""Apply the measured materialise-then-retest rule to every fork line with branches.
usage: artefacts.py [branch_lines_all.tsv]   (default: the TSV next to this script)
artefact pairs on a line = (operators - 1, if 2+ && / ||) [left-nesting] + (number of ! negations)
                           + 1 if a compound or negated boolean feeds an if / while / ternary test.
Validated first on the 'clean' lines (one && / ||, nothing else), where measured totals are known to be 4, 6, 8 or 10."""
import csv, re, collections, os, sys
tsv = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), 'branch_lines_all.tsv')
br = [r for r in csv.DictReader(open(tsv), delimiter='\t') if r['fork'] == '1']
def strip(t):
    t = re.sub(r'//.*$', '', t); t = re.sub(r"'[^']*'|\"[^\"]*\"", "''", t); return re.sub(r'/\S*?/', '//', t)   # strings, regex literals
def feats(t):
    s = strip(t)
    ops = len(re.findall(r'&&|\|\|', s)); nots = len(re.findall(r'(?<![=!<>])!(?!=)', s))
    tern = len(re.findall(r'\?(?![:.])', s)); elv = len(re.findall(r'\?:', s))
    dec = bool(re.match(r'^(\}\s*)?(else\s+)?(if|while)\b', s)) or tern > 0 or bool(re.match(r'^[a-z_]+:\s', s))  # branch-operator criterion lines count as a test
    return ops, nots, tern, elv, dec
def artefact_pairs(ops, nots, dec):
    return (ops - 1 if ops >= 2 else 0) + nots + (1 if dec and (ops or nots) else 0)
T = sum(int(r['mb']) + int(r['cb']) for r in br)
# validation on clean one-operator lines: predicted total = 2*(2 operands) + 2*artefacts
ok = bad = 0; bad_rows = []
for r in br:
    ops, nots, tern, elv, dec = feats(r['text']); tot = int(r['mb']) + int(r['cb'])
    if ops == 1 and tern == 0 and elv == 0:
        pred = 4 + 2 * artefact_pairs(ops, nots, dec)
        if pred == tot: ok += 1
        else: bad += 1; bad_rows.append((pred, tot, r['file'], r['line'], r['text'][:80]))
print(f"validation on one-operator lines: rule reproduces the measured total on {ok}, misses {bad}")
for b in bad_rows: print("   predicted", b[0], "measured", b[1], f"{b[2]}:{b[3]}", b[4])
# multi-operator clean lines too
ok2 = bad2 = 0
for r in br:
    ops, nots, tern, elv, dec = feats(r['text']); tot = int(r['mb']) + int(r['cb'])
    if ops >= 2 and tern == 0 and elv == 0:
        pred = 2 * (ops + 1) + 2 * artefact_pairs(ops, nots, dec)
        if pred == tot: ok2 += 1
        else: bad2 += 1; print(f"   multi: predicted {pred} measured {tot}  {r['file']}:{r['line']}  {r['text'][:80]}")
print(f"validation on multi-operator lines: {ok2} reproduced, {bad2} not (lines carrying more than the chain, e.g. a closure or a second statement)")
art = sum(2 * artefact_pairs(*[feats(r['text'])[i] for i in (0, 1, 4)]) for r in br)
lines_with = sum(1 for r in br if artefact_pairs(*[feats(r['text'])[i] for i in (0, 1, 4)]))
print(f"\ninferred artefact branches over all {len(br)} fork branch lines: {art} of {T} ({100*art/T:.1f}%), on {lines_with} lines")
C = sum(int(r['cb']) for r in br)
print(f"headline 514/920 = {100*C/T:.1f}%; the same lines without artefact branches have a denominator of about {T-art}")
# per-construct contribution of artefacts
by = collections.Counter()
for r in br:
    ops, nots, tern, elv, dec = feats(r['text'])
    if ops >= 2: by['nesting (2+ operators)'] += 2 * (ops - 1)
    by['negation !'] += 2 * nots
    if dec and (ops or nots): by['re-test of the result in if / ternary'] += 2
print("artefact branches by cause:", dict(by))
