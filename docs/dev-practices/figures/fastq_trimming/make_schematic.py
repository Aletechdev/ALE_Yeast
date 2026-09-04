#!/usr/bin/env python
"""Render trim_quality_modes.svg - the schematic behind the ASCII sketch in the `trim_quality` help text.

    python docs/dev-practices/figures/fastq_trimming/make_schematic.py [out.svg]

One synthetic read with a quality profile (high, a mid-read dip, a low 3' tail) and, below it, what
each `trim_quality` mode keeps. No data involved; edit the profile constants to change the story.
"""
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).parent / "trim_quality_modes.svg"
INK, INK2, GRID, SURFACE, TRIM = "#0b0b0b", "#52514e", "#e6e5e1", "#fcfcfb", "#d9d8d3"
MODES = [  # name, colour, kept interval(s) in read coordinates (0..100), caption
    ("3' tail", "#1baf7a", [(0, 91)], "trim_quality_3prime = tail: walk in from the 3' end, stop at the first window that passes"),
    ("3' right", "#eb6834", [(0, 44)], "trim_quality_3prime = right: scan 5'→3', cut at the first window that fails and everything after it"),
    ("5'", "#2a78d6", [(6, 100)], "trim_quality_5prime: same as tail, from the 5' end"),
]
DIP, TAIL, LOW5 = (44, 50), 91, 6      # the three quality features of the synthetic read
THRESHOLD = 20

# synthetic per-base quality: low first 6 bp, plateau ~37, dip to ~14 at 44-50, decay from 80 to ~10 at 100
x = np.arange(0, 101)
q = np.full(x.shape, 37.0)
q[x < LOW5] = 16
q[(x >= DIP[0]) & (x < DIP[1])] = 14
q[x >= 78] = 37 - (x[x >= 78] - 78) * (27 / 22)

fig, (ax_q, ax_m) = plt.subplots(2, 1, figsize=(8.4, 3.6), facecolor=SURFACE,
                                 gridspec_kw=dict(height_ratios=[1.15, 1], hspace=0.08), sharex=True)
for ax in (ax_q, ax_m):
    ax.set_facecolor(SURFACE)
    for side in ("top", "right", "left", "bottom"):
        ax.spines[side].set_visible(False)
    ax.tick_params(left=False, labelleft=False, bottom=False, labelbottom=False)
    ax.set_xlim(-14, 101)

# quality profile
ax_q.plot(x, q, color=INK, linewidth=1.8, solid_joinstyle="round")
ax_q.axhline(THRESHOLD, color=INK2, linewidth=0.8, linestyle=(0, (4, 3)))
ax_q.text(100.5, THRESHOLD, f"Q{THRESHOLD} window\nthreshold", fontsize=7, color=INK2, va="center", ha="left")
ax_q.text(-13, 37, "base\nquality", fontsize=8, color=INK2, va="center")
ax_q.set_ylim(4, 44)
ax_q.annotate("mid-read dip", (47, 14), xytext=(47, 5), textcoords="data", fontsize=7, color=INK2, ha="center",
              arrowprops=dict(arrowstyle="-", color=INK2, linewidth=0.6))
ax_q.annotate("3' quality decay", (95, q[95]), xytext=(80, 8), fontsize=7, color=INK2, ha="center",
              arrowprops=dict(arrowstyle="-", color=INK2, linewidth=0.6))
ax_q.annotate("low 5' start", (3, 16), xytext=(12, 8), fontsize=7, color=INK2, ha="center",
              arrowprops=dict(arrowstyle="-", color=INK2, linewidth=0.6))
ax_q.text(0, 42.5, "5'", fontsize=8, color=INK2, ha="left")
ax_q.text(100, 42.5, "3'", fontsize=8, color=INK2, ha="right")
ax_q.text(50, 42.5, "one read, 100 bp", fontsize=8, color=INK2, ha="center")

# what each mode keeps
rows = list(range(len(MODES)))[::-1]
for (name, colour, kept, caption), y in zip(MODES, rows):
    ax_m.add_patch(plt.Rectangle((0, y - 0.18), 100, 0.36, facecolor=TRIM, edgecolor="none"))
    for a, b in kept:
        ax_m.add_patch(plt.Rectangle((a, y - 0.18), b - a, 0.36, facecolor=colour, edgecolor="none"))
        cut = b if b < 100 else a
        ax_m.plot([cut, cut], [y - 0.32, y + 0.32], color=INK, linewidth=1.2)
    ax_m.text(-1.5, y, name, fontsize=8.5, color=INK, ha="right", va="center", fontweight="bold")
    ax_m.text(0, y - 0.5, caption, fontsize=7, color=INK2, ha="left", va="center")
ax_m.set_ylim(-0.9, len(MODES) - 0.4)
ax_m.text(100, len(MODES) - 0.45, "coloured = kept,  grey = trimmed,  | = cut point", fontsize=7, color=INK2,
          ha="right", va="bottom")

fig.savefig(OUT, bbox_inches="tight", facecolor=SURFACE, dpi=160,
            metadata={"Date": None} if OUT.suffix == ".svg" else None)
print(f"wrote {OUT}")
