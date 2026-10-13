"""Step 3 sizing: which constructs the fork-wide branch denominator comes from.
usage: classify.py branch_lines_all.tsv fork_lines_438a9dc.tsv"""
import csv, re, sys, collections
br = [r for r in csv.DictReader(open(sys.argv[1]), delimiter='\t') if r['fork'] == '1']
fk = list(csv.DictReader(open(sys.argv[2]), delimiter='\t'))
def strip(t):
    t = re.sub(r'//.*$', '', t)                       # line comments
    t = re.sub(r"'[^']*'|\"[^\"]*\"", "''", t)        # string literals (a '||' inside a shell string is not an operator)
    return t
def feats(t):
    t = strip(t)
    return dict(ops=len(re.findall(r'&&|\|\|', t)), elv=len(re.findall(r'\?:', t)), safe=len(re.findall(r'\?\.', t)),
                tern=len(re.findall(r'\?(?![:.])', t)), decision=bool(re.match(r'^(\}\s*)?(else\s+)?(if|while)\b', t)) or bool(re.search(r'\?(?![:.])', t)))
def cat(f):
    if f['ops']: return 'compound (&& / ||)'
    if f['elv'] >= 2: return 'chained ?: (2+)'
    if f['elv'] == 1: return 'single ?:'
    if f['tern']: return 'ternary ? :'
    if f['safe']: return '?. only'
    return 'plain (if / switch / other)'
T = sum(int(r['mb']) + int(r['cb']) for r in br); C = sum(int(r['cb']) for r in br)
rows = collections.defaultdict(lambda: [0, 0, 0])
for r in br:
    c = cat(feats(r['text'])); rows[c][0] += 1; rows[c][1] += int(r['cb']); rows[c][2] += int(r['mb']) + int(r['cb'])
print(f"fork lines with branches: {len(br)}; fork branches: {C}/{T}\n")
print(f"{'construct on the line':32} {'lines':>5} {'branches':>9} {'covered':>8} {'share of 920':>12}")
for c, (n, cb, t) in sorted(rows.items(), key=lambda x: -x[1][2]):
    print(f"{c:32} {n:5} {t:9} {cb:8} {100*t/T:11.1f}%")
# measured artefact count on clean compound lines: one operator, nothing else -> total is 6 (feeds a decision) or 4 (value)
comp = [(r, feats(r['text'])) for r in br if feats(r['text'])['ops']]
clean = [(r, f) for r, f in comp if f['ops'] == 1 and f['elv'] == 0 and f['tern'] == 0]
dist = collections.Counter(int(r['mb']) + int(r['cb']) for r, f in clean)
print(f"\ncompound lines: {len(comp)}; operators (&&/||) on them: {sum(f['ops'] for _, f in comp)}; branches: {sum(int(r['mb'])+int(r['cb']) for r,_ in comp)}")
print(f"clean one-operator lines (no ?: or ternary on the line): {len(clean)}; their branch totals: {dict(sorted(dist.items()))}")
print("   6 = the && / || feeds an if or ternary (2 artefact branches); 4 = the boolean is returned or assigned (none); other = more on the line")
art_meas = 2 * sum(1 for r, f in clean if int(r['mb']) + int(r['cb']) == 6)
rest = [(r, f) for r, f in comp if (r, f) not in clean]
art_lo = art_meas; art_hi = art_meas + 2 * sum(f['ops'] for _, f in rest)
art_mid = art_meas + 2 * sum(f['ops'] for _, f in rest if f['decision'])
print(f"artefact branches: measured on clean lines {art_meas}; plus the {len(rest)} other compound lines by the text rule -> {art_mid} (likely) .. {art_hi} (upper bound)")
print(f"   = {100*art_mid/T:.1f}% .. {100*art_hi/T:.1f}% of the 920; without them the denominator would be about {T-art_mid}, the headline {C}/{T} = {100*C/T:.1f}% becomes ~{100*(C - sum(int(r['cb']) for r,f in clean if int(r['mb'])+int(r['cb'])==6)//3)/(T-art_mid):.1f}% (artefact covered when the operands are)")
# multi-operator lines: measured vs rule 4n-2
multi = [(r, f) for r, f in comp if f['ops'] >= 2 and f['elv'] == 0 and f['tern'] == 0]
print(f"\nmulti-operator clean lines: {len(multi)} ->", ', '.join(f"ops={f['ops']} total={int(r['mb'])+int(r['cb'])}" for r, f in multi))
# the when guard
wg = [r for r in br if 'task.ext.when == null' in r['text']]
print(f"\n`task.ext.when == null || task.ext.when` lines: {len(wg)}, branch totals {collections.Counter(int(r['mb'])+int(r['cb']) for r in wg)}, covered {sum(int(r['cb']) for r in wg)}")
# safe navigation across all fork executable lines
exe = [r for r in fk if r['exe'] == '1']
safe_lines = [r for r in exe if re.search(r'\?\.', strip(r['text']))]
brk = {(r['file'], r['line']) for r in br}
print(f"\nfork executable lines: {len(exe)}; containing `?.`: {len(safe_lines)}; of those with any branches: {sum(1 for r in safe_lines if (r['file'], r['line']) in brk)} (branches come from other constructs on the line)")
chain = [r for r in exe if len(re.findall(r'\?:', strip(r['text']))) >= 2]
print(f"fork executable lines with chained ?: : {len(chain)}; with && / ||: {sum(1 for r in exe if re.search(r'&&|\|\|', strip(r['text'])))}")
print("\nexamples (file:line total text):")
for c in ['chained ?: (2+)', 'compound (&& / ||)']:
    for r in [r for r in br if cat(feats(r['text'])) == c][:4]:
        print(f"  {r['file']}:{r['line']}  {int(r['mb'])+int(r['cb'])}  {r['text'][:95]}")
