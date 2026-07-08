#!/usr/bin/env python3
"""Post-process CNVKit igv-reports HTML to customize track display.

Sets custom height, colors, and labels for BedGraph coverage tracks.
"""

import json
import gzip
import base64
import re
import sys


def main():
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <report_html>", file=sys.stderr)
        sys.exit(1)

    report_path = sys.argv[1]

    html = open(report_path).read()
    m = re.search(r'const sessionDictionary = (\{.*?\});', html)
    if not m:
        sys.exit(0)

    sd = json.loads(m.group(1))

    modified = False
    for key in sd:
        uri = sd[key]
        b64 = uri.split(',', 1)[1]
        raw = gzip.decompress(base64.b64decode(b64))
        session = json.loads(raw)

        for track in session.get('tracks', []):
            if track.get('type') == 'wig':
                track['height'] = 150
                name = track.get('name', '').lower()
                if 'depth' in name:
                    track['color'] = 'rgb(0,114,178)'
                    track['name'] = 'Read Depth (~5kb bins)'
                elif 'log2' in name:
                    track['color'] = 'rgb(230,159,0)'
                    track['name'] = 'Log2 Ratio (0=normal)'
                modified = True

        if modified:
            new_raw = json.dumps(session).encode()
            new_gz = gzip.compress(new_raw)
            new_uri = 'data:application/gzip;base64,' + base64.b64encode(new_gz).decode()
            sd[key] = new_uri

    if modified:
        new_sd = json.dumps(sd)
        html = html.replace(m.group(0), 'const sessionDictionary = ' + new_sd + ';')
        open(report_path, 'w').write(html)


if __name__ == '__main__':
    main()
