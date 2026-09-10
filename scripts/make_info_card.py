#!/usr/bin/env python3
"""Hand-authored neofetch-style info card as an animated SVG.

Lines fade and slide in one after another (CSS keyframes inside the SVG —
GitHub honours them because the SVG is loaded via <img>). STATIC=1 in the
environment renders the final frame with no animation (handy for previews).

Usage: python scripts/make_info_card.py [--out info-card.svg] [--width 480] [--height 379]
Edit CONTENT below when the details change, then re-run.
"""
import argparse
import os
from xml.sax.saxutils import escape

CONTENT: list[tuple[str, str]] = [
    ("Name", "Diogo Silva Sena"),
    ("Handle", "AltDoug"),
    ("Where", "Florida, USA"),
    ("Now", "AI-agent tooling for Claude Code"),
    ("Stack", "Shell · Python · TypeScript"),
    ("Ships", "found-issues · claude-plugins"),
    ("Motto", "I build tools that solve my own"),
    ("", "problems, then share the good ones."),
    ("Contact", "silvasenadiogo2025@gmail.com"),
]
PROMPT = "altdoug@github"
PALETTE = ["#ff7b72", "#ffa657", "#d2a8ff", "#79c0ff", "#7ee787", "#a5d6ff", "#c9d1d9", "#8b949e"]
BG, BORDER, KEY, VAL, DIM, TITLE = "#0d1117", "#30363d", "#79c0ff", "#c9d1d9", "#8b949e", "#7ee787"
FONT = "SFMono-Regular, Menlo, Consolas, 'Liberation Mono', 'DejaVu Sans Mono', monospace"


def build(width: int, height: int, static: bool) -> str:
    fs, lh, pad, bar = 13, 24, 26, 38
    lines: list[str] = []
    n = 0

    def line(markup: str, y: float, raw: bool = False) -> None:
        nonlocal n
        delay = "" if static else f' style="animation-delay:{0.25 + n*0.14:.2f}s"'
        inner = markup if raw else f'<text x="{pad}" y="{y:.1f}">{markup}</text>'
        lines.append(f'<g class="ln"{delay}>{inner}</g>')
        n += 1

    y = bar + pad + 4
    line(f'<tspan fill="{TITLE}" font-weight="bold">{PROMPT}</tspan>', y)
    y += lh * 0.9
    line(f'<tspan fill="{DIM}">{"─" * len(PROMPT)}</tspan>', y)
    y += lh
    for key, val in CONTENT:
        k = f'<tspan fill="{KEY}" font-weight="bold">{escape(key)}</tspan>' if key else ""
        line(f'{k}<tspan x="{pad + 96}" fill="{VAL}">{escape(val)}</tspan>', y)
        y += lh

    # neofetch palette strip
    y += 6
    sw = 24
    swatches = "".join(
        f'<rect x="{pad + i*sw}" y="{y - 12:.1f}" width="{sw}" height="14" fill="{c}"/>' for i, c in enumerate(PALETTE)
    )
    line(swatches, y, raw=True)
    y += lh
    cursor = "" if static else '<animate attributeName="opacity" values="1;1;0;0" dur="1.1s" repeatCount="indefinite"/>'
    line(f'<tspan fill="{TITLE}">$</tspan> <tspan fill="{VAL}">_<title>cursor</title>{cursor}</tspan>', y)

    anim = "" if static else """
    .ln { opacity: 0; animation: rise .45s cubic-bezier(.2,.7,.2,1) forwards; }
    @keyframes rise { from { opacity: 0; transform: translateX(-10px); } to { opacity: 1; transform: none; } }"""
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
<style>
  text {{ font-family: {FONT}; font-size: {fs}px; }}{anim}
</style>
<rect x="0.5" y="0.5" width="{width-1}" height="{height-1}" rx="8" fill="{BG}" stroke="{BORDER}"/>
<path d="M0.5 {bar}.5 H{width-0.5}" stroke="{BORDER}"/>
<circle cx="22" cy="{bar/2}" r="6" fill="#ff5f56"/><circle cx="42" cy="{bar/2}" r="6" fill="#ffbd2e"/><circle cx="62" cy="{bar/2}" r="6" fill="#27c93f"/>
<text x="{width/2}" y="{bar/2 + 4.5}" text-anchor="middle" fill="{DIM}">{PROMPT}: ~</text>
{chr(10).join(lines)}
</svg>
"""


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="info-card.svg")
    ap.add_argument("--width", type=int, default=480)
    ap.add_argument("--height", type=int, default=379)
    a = ap.parse_args()
    svg = build(a.width, a.height, os.environ.get("STATIC") == "1")
    with open(a.out, "w") as f:
        f.write(svg)
    print(f"wrote {a.out}: {a.width}x{a.height}px")


if __name__ == "__main__":
    main()
