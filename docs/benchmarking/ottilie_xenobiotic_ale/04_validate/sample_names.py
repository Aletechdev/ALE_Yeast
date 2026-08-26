"""Sample-name resolution shared by the ottilie validation scripts.

The same clone is spelled differently across sources — Sup Data 4/5 (``Carmaphycin--R9-2``,
``Doxorubicin-16--R2b``, ``CBR110-15R3a``), the SRA library name, and the pipeline samplesheet
(``Carmaphycin-R9-2``, ``Doxorubicin16-R2b``, ``CBR110-15-R3a``). Exact matching silently drops
any clone whose punctuation differs, which is how the pilot validation scored one evolved sample
instead of three. Match exactly first, then on a key that ignores case and punctuation.
"""

import re


def name_key(name):
    """Case- and punctuation-insensitive key: 'Doxorubicin-16--R2b' -> 'doxorubicin16r2b'."""
    return re.sub(r"[^a-z0-9]", "", name.lower())


def resolve_sample(candidates, available):
    """Return the entry of ``available`` that a clone's name variants refer to, or None.

    ``candidates`` are the name spellings known for one clone, in priority order; ``available``
    the sample names present in the pipeline output. Exact matches win; otherwise the first
    candidate whose key matches exactly one available sample. Verified collision-free across the
    356-clone dictionary and the Tier 2 samplesheet (2026-08-26).
    """
    candidates = [c for c in candidates if c]
    for c in candidates:
        if c in available:
            return c
    by_key = {}
    for a in available:
        by_key.setdefault(name_key(a), []).append(a)
    for c in candidates:
        hits = by_key.get(name_key(c), [])
        if len(hits) == 1:
            return hits[0]
    return None
