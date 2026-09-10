#!/usr/bin/env python3
"""Render data/contributions.json as an animated 53-week contribution calendar SVG.

Cells reveal diagonally (fade + slide down, CSS keyframes inside the SVG),
play once and freeze. Month labels on top, Mon/Wed/Fri on the left, legend
and streak stats in the footer. Regenerated daily by the workflow.

Usage: python scripts/render_heatmap_svg.py [--src data/contributions.json] [--out contrib-heatmap.svg]
"""
import argparse
import datetime as dt
import json

PALETTE = ["#161b22", "#0e4429", "#006d32", "#26a641", "#39d353"]
BG, BORDER, TEXT, DIM = "#0d1117", "#30363d", "#c9d1d9", "#8b949e"
FONT = "-apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif"
CELL, GAP, R = 12, 3, 2
STEP = CELL + GAP


def plural(n: int, word: str) -> str:
    return f"{n} {word}{'' if n == 1 else 's'}"


def build(data: dict, width: int) -> str:
    days = data["days"]
    first = dt.date.fromisoformat(days[0]["date"])
    weeks = (len(days) + first.weekday() + 1) // 7 + 1  # weeks start on Sunday
    left, top, foot, pad = 30, 22, 34, 14
    grid_w = weeks * STEP - GAP
    height = top + 7 * STEP - GAP + foot + 2 * pad
    ox, oy = pad + left, pad + top
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        "<style>",
        f"  text {{ font-family: {FONT}; font-size: 11px; fill: {DIM}; }}",
        "  .c { opacity: 0; animation: drop .5s cubic-bezier(.2,.7,.2,1) forwards; }",
        "  @keyframes drop { from { opacity: 0; transform: translateY(-6px); } to { opacity: 1; transform: none; } }",
        "</style>",
        f'<rect x="0.5" y="0.5" width="{width-1}" height="{height-1}" rx="8" fill="{BG}" stroke="{BORDER}"/>',
    ]
    # day labels
    for row, label in ((1, "Mon"), (3, "Wed"), (5, "Fri")):
        out.append(f'<text x="{ox - 8}" y="{oy + row*STEP + CELL - 2}" text-anchor="end">{label}</text>')
    # cells + month labels
    seen_month = None
    for d in days:
        date = dt.date.fromisoformat(d["date"])
        col = (date - first).days + (first.weekday() + 1) % 7
        week, dow = divmod(col, 7)
        x, y = ox + week * STEP, oy + dow * STEP
        if date.month != seen_month and (date.day <= 7) and week < weeks - 1:
            if seen_month is not None or date.day <= 7:
                out.append(f'<text x="{x}" y="{oy - 8}">{date.strftime("%b")}</text>')
            seen_month = date.month
        delay = week * 0.02 + dow * 0.035
        out.append(
            f'<rect class="c" style="animation-delay:{delay:.2f}s" x="{x}" y="{y}" width="{CELL}" height="{CELL}" '
            f'rx="{R}" fill="{PALETTE[d["level"]]}"><title>{plural(d["count"], "contribution")} on {d["date"]}</title></rect>'
        )
    # footer: stats left, legend right
    fy = oy + 7 * STEP - GAP + 24
    stats = (f'<tspan fill="{TEXT}" font-weight="600">{data["total"]:,}</tspan> contributions in the last year'
             f'  ·  longest streak <tspan fill="{TEXT}" font-weight="600">{plural(data["longest_streak"], "day")}</tspan>'
             f'  ·  current <tspan fill="{TEXT}" font-weight="600">{plural(data["current_streak"], "day")}</tspan>'
             f'  ·  refreshed {data["fetched_at"][:10]}')
    out.append(f'<text x="{ox}" y="{fy}">{stats}</text>')
    lx = ox + grid_w - 5 * STEP - 62
    out.append(f'<text x="{lx - 6}" y="{fy}" text-anchor="end">Less</text>')
    for i, c in enumerate(PALETTE):
        out.append(f'<rect x="{lx + i*STEP}" y="{fy - CELL + 2}" width="{CELL}" height="{CELL}" rx="{R}" fill="{c}"/>')
    out.append(f'<text x="{lx + 5*STEP + 2}" y="{fy}">More</text>')
    out.append("</svg>")
    return "\n".join(out)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default="data/contributions.json")
    ap.add_argument("--out", default="contrib-heatmap.svg")
    ap.add_argument("--width", type=int, default=860)
    a = ap.parse_args()
    with open(a.src) as f:
        data = json.load(f)
    svg = build(data, a.width)
    with open(a.out, "w") as f:
        f.write(svg)
    print(f"wrote {a.out} ({len(svg)//1024}KB)")


if __name__ == "__main__":
    main()
