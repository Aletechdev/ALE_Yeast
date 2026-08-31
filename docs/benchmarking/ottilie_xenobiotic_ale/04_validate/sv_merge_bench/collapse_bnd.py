"""Keep one record per Manta breakend pair: drop a BND whose MATEID was already emitted."""
import sys
seen=set()
for line in open(sys.argv[1]):
    if line.startswith('#'): sys.stdout.write(line); continue
    f=line.rstrip('\n').split('\t')
    info=dict(kv.split('=',1) if '=' in kv else (kv,True) for kv in f[7].split(';'))
    if info.get('SVTYPE')=='BND':
        mate=info.get('MATEID')
        if mate in seen: continue
        seen.add(f[2])
    sys.stdout.write(line)
