#!/usr/bin/env python
"""Render read_preprocessing_steps.svg - what happens to one read pair, step by step, in run order.

    python docs/dev-practices/figures/fastq_trimming/make_read_journey.py [out.svg]

One synthetic read (insert + adapter read-through + poly-G tail), redrawn after each fastp step of
docs/usage/read_preprocessing.md. The ALE default path (steps 1, 3 = tail, 4) is drawn in colour;
optional branches (poly-G forcing, step 2 clips, 5' cut, `right`) in grey. No data involved.
"""
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Rectangle  # noqa: E402

OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).parent / "read_preprocessing_steps.svg"
INK, INK2, SURFACE = "#0b0b0b", "#52514e", "#fcfcfb"
INSERT, ADAPTER, POLYG, LOWQ, GONE = "#2a78d6", "#eb6834", "#eda100", "#1baf7a", "#d9d8d3"
OPT = "#8a8983"  # optional / not default

# read layout (bp along x): insert 0-78, adapter 78-92, poly-G 92-100; low-quality 3' stretch of the insert 66-78
L_INSERT, L_ADAPTER, L_END, LOWQ_FROM = 78, 92, 100, 66

rows = [  # (label, default?, kept insert interval, extra segments, caption)
    ("as sequenced", None, (0, L_INSERT), [("adapter", L_INSERT, L_ADAPTER), ("polyG", L_ADAPTER, L_END)],
     "insert + adapter read-through + poly-G tail (two-colour chemistry)"),
    ("step 1  adapter trimming", True, (0, L_INSERT), [],
     "trim_adapter (default on): adapter and all after it removed; poly-G by read-name rule or forced (trim_nextseq)"),
    ("step 2  fixed-count clipping", False, (0, L_INSERT), [],
     "clip_r*, three_prime_clip_r* (default 0): a set number of bases, for cycles known to be bad"),
    ("step 3  quality trimming", True, (0, LOWQ_FROM), [],
     "trim_quality_3prime = tail (default): low-quality 3' bases removed per read; right / 5' cut optional"),
    ("step 4  read filtering", True, (0, LOWQ_FROM), [],
     "filter_quality (on) + length_required 15: too-poor or too-short pairs are discarded, both mates"),
]

fig, ax = plt.subplots(figsize=(9.2, 4.3), facecolor=SURFACE)
ax.set_facecolor(SURFACE)
for side in ("top", "right", "left", "bottom"):
    ax.spines[side].set_visible(False)
ax.tick_params(left=False, labelleft=False, bottom=False, labelbottom=False)
ax.set_xlim(-34, 104)
ax.set_ylim(-1.1, len(rows) - 0.2)

H = 0.34
for i, (label, default, kept, extras, caption) in enumerate(rows):
    y = len(rows) - 1 - i
    colour = INK if default is None else (INK if default else OPT)
    ax.text(-33, y + 0.02, label, fontsize=8.5, color=colour, va="center", ha="left",
            fontweight="bold" if default in (None, True) else "normal")
    if default is False:
        ax.text(-33, y - 0.3, "optional, off by default", fontsize=6.5, color=OPT, va="center", ha="left")
    elif default:
        ax.text(-33, y - 0.3, "ALE default", fontsize=6.5, color=INSERT, va="center", ha="left")
    # full original extent in light grey, then what is kept on top
    ax.add_patch(Rectangle((0, y - H / 2), L_END, H, facecolor=GONE, edgecolor="none"))
    a, b = kept
    ax.add_patch(Rectangle((a, y - H / 2), b - a, H, facecolor=INSERT, edgecolor="none"))
    if b == L_INSERT and i < 3:  # low-quality stretch still present
        ax.add_patch(Rectangle((LOWQ_FROM, y - H / 2), L_INSERT - LOWQ_FROM, H, facecolor=LOWQ, edgecolor="none"))
    for name, s, e in extras:
        ax.add_patch(Rectangle((s, y - H / 2), e - s, H, facecolor=ADAPTER if name == "adapter" else POLYG, edgecolor="none"))
    ax.text(0, y - 0.5, caption, fontsize=6.8, color=INK2, va="center", ha="left")
    if i == 2:  # step 2 example: a 3' clip of 4 bp would land here - dashed marker, not applied by default
        ax.plot([L_INSERT - 4, L_INSERT - 4], [y - 0.28, y + 0.28], color=OPT, linewidth=1, linestyle=(0, (2, 2)))
    if i == 4:  # step 4: the discarded-pair example
        ax.text(102, y, "kept", fontsize=7, color=INK, va="center", ha="left")

# header + legend
ax.text(0, len(rows) - 0.45, "5'", fontsize=8, color=INK2, ha="left")
ax.text(L_END, len(rows) - 0.45, "3'", fontsize=8, color=INK2, ha="right")
ax.text(L_END / 2, len(rows) - 0.45, "one read of a pair (100 bp)", fontsize=8, color=INK2, ha="center")
lx, ly = 0, -0.95
for name, c in (("insert", INSERT), ("low-quality 3' bases", LOWQ), ("adapter", ADAPTER), ("poly-G", POLYG), ("removed", GONE)):
    ax.add_patch(Rectangle((lx, ly - 0.09), 3, 0.18, facecolor=c, edgecolor="none"))
    ax.text(lx + 4, ly, name, fontsize=7, color=INK2, va="center")
    lx += 6 + len(name) * 1.35
fig.savefig(OUT, bbox_inches="tight", facecolor=SURFACE, dpi=160,
            metadata={"Date": None} if OUT.suffix == ".svg" else None)
print(f"wrote {OUT}")
