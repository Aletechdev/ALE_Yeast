"""One record per breakend junction: drop Manta BNDs whose MATEID was already emitted,
and TIDDIT SV_<n>_2 mates (TIDDIT pairs are SV_<n>_1 / SV_<n>_2)."""
import sys,re
seen=set()
for line in open(sys.argv[1]):
    if line.startswith('#'): sys.stdout.write(line); continue
    f=line.rstrip('\n').split('\t')
    info=dict(kv.split('=',1) if '=' in kv else (kv,True) for kv in f[7].split(';'))
    if info.get('SVTYPE')=='BND':
        if 'MATEID' in info:
            if info['MATEID'] in seen: continue
            seen.add(f[2])
        elif re.fullmatch(r'SV_\d+_2', f[2]): continue
    sys.stdout.write(line)
