import sys,re,collections
LOCI={'XV:722kb DEL':('XV',721000,723500),'ADH1 star (XV:159.6kb)':('XV',159400,159900)}
def parse(p):
    cols=None;recs=[]
    for line in open(p):
        if line.startswith('##'): continue
        if line.startswith('#'): cols=line.rstrip('\n').split('\t')[9:]; continue
        f=line.rstrip('\n').split('\t')
        info={}
        for kv in f[7].split(';'):
            if '=' in kv: k,v=kv.split('=',1); info[k]=v
            else: info[kv]=True
        recs.append((f,info))
    return cols,recs
def touches(f,info,chrom,lo,hi):
    if f[0]==chrom and lo<=int(f[1])<=hi: return True
    if info.get('CHR2',f[0])==chrom and 'END' in info and lo<=int(info['END'])<=hi: return True
    m=re.search(r'([IVX]+|Mito):(\d+)',f[4])
    if m and m.group(1)==chrom and lo<=int(m.group(2))<=hi: return True
    return False
for p in sys.argv[1:]:
    cols,recs=parse(p)
    st=collections.Counter(i.get('SVTYPE','?').replace('DUP:TANDEM','DUP') for f,i in recs)
    filt=collections.Counter(f[6] for f,i in recs)
    mate=sum(1 for f,i in recs if 'MATEID' in i)
    multi=sum(1 for f,i in recs if (i.get('FOUNDBY','1')!='1') or (i.get('SUPP_VEC','1').count('1')>1 and i.get('SUPP_VEC','')[0]=='1'))
    print(f"\n### {p}\n  samples: {cols}\n  records={len(recs)} types={dict(st)} MATEID={mate} FILTER={dict(filt)}")
    for k in ('set','SUPP_VEC'):
        c=collections.Counter(i.get(k) for f,i in recs if k in i)
        if c: print(f"  {k}: {dict(c)}")
    for name,(chrom,lo,hi) in LOCI.items():
        hits=[(f,i) for f,i in recs if touches(f,i,chrom,lo,hi)]
        print(f"  -- {name}: {len(hits)} rows")
        for f,i in hits:
            gts=' '.join(x.split(':')[0] for x in f[9:])
            prov=i.get('set') or i.get('SUPP_VEC') or ''
            print(f"     {f[0]}:{f[1]} {i.get('SVTYPE')} end={i.get('END','.')} alt={f[4][:28]:28} q={f[5]} {f[6]:<20} {prov:<22} mate={'y' if 'MATEID' in i else '-'} GT[{gts}] id={f[2][:34]}")
