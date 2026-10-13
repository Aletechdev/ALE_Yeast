"""Per-line JaCoCo counters from an XML report: nr, mi, ci, mb, cb, and the source text.
usage: xml_lines.py REPORT.xml SOURCE_FILE [--all]   (--all: every executable line, not only branch lines)"""
import sys, xml.etree.ElementTree as ET
xml, src = sys.argv[1], sys.argv[2]; show_all = '--all' in sys.argv
text = open(src, errors='replace').read().split('\n')
root = ET.parse(xml).getroot()
for sf in root.iter('sourcefile'):
    print(f"# sourcefile {sf.get('name')}")
    tot_mb = tot_cb = 0
    for l in sf.findall('line'):
        nr, mi, ci, mb, cb = (int(l.get(k)) for k in ('nr', 'mi', 'ci', 'mb', 'cb'))
        tot_mb += mb; tot_cb += cb
        if show_all or mb + cb:
            t = text[nr - 1].strip() if nr <= len(text) else '?'
            print(f"{nr:4}  instr {ci:3}/{mi + ci:<3}  branches cb={cb} mb={mb} total={mb + cb}   {t[:90]}")
    print(f"# totals: branches covered {tot_cb}, missed {tot_mb}, total {tot_mb + tot_cb}")
for c in root.iter('class'):
    for m in c.findall('method'):
        br = [x for x in m.findall('counter') if x.get('type') == 'BRANCH']
        if br:
            print(f"# method {c.get('name')}.{m.get('name')} line {m.get('line')}: branches covered {br[0].get('covered')} missed {br[0].get('missed')}")
