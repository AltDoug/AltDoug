#!/usr/bin/env python3
"""Turn source-prepped.png (RGBA) into an animated portrait SVG.

Two styles. `pixels` (default): square pixel art from a quantized palette,
drawn as run-merged <rect>s so it renders identically regardless of the
viewer's fonts. `ascii`: glyph density from brightness, glyph colour from the
palette, transparent pixels as spaces. In both, each row sits under a clipPath
whose width animates 0 -> full (SMIL), staggered top-to-bottom, so the image
"types" itself in and then freezes. No JavaScript: GitHub renders SVGs via
<img> and honours SMIL.

Usage: python scripts/make_ascii_svg.py [--src source-prepped.png] [--out altdoug-portrait.svg]
       [--cols 48] [--width 340] [--colors 10] [--style pixels|ascii]
Prints the SVG height so the info card can be sized to match.
"""
import argparse
from xml.sax.saxutils import escape

import numpy as np
from PIL import Image

RAMP = " .:-=+*#%@"  # sparse -> dense
BG, BORDER, INK = "#0d1117", "#30363d", "#c9d1d9"
FONT = "SFMono-Regular, Menlo, Consolas, 'Liberation Mono', 'DejaVu Sans Mono', monospace"
FLOOR = 2  # an opaque pixel never drops below this glyph, so the silhouette always reads


def to_grid(src: str, cols: int, cell_w: float, cell_h: float, gamma: float, ncolors: int, mono: bool):
    img = Image.open(src).convert("RGBA")
    rows = max(1, round(img.height / img.width * cols * (cell_w / cell_h)))
    small = img.resize((cols, rows), Image.Resampling.LANCZOS)
    arr = np.asarray(small, dtype=np.float32)
    alpha = arr[:, :, 3] > 96
    lum = 0.299 * arr[:, :, 0] + 0.587 * arr[:, :, 1] + 0.114 * arr[:, :, 2]
    vis = lum[alpha] if alpha.any() else lum
    lo, hi = np.percentile(vis, 2), np.percentile(vis, 98)
    norm = np.clip((lum - lo) / max(hi - lo, 1e-6), 0, 1) ** gamma
    idx = (FLOOR + norm * (len(RAMP) - 1 - FLOOR)).round().astype(int)
    idx[~alpha] = 0
    glyphs = [[RAMP[i] for i in row] for row in idx]

    if mono:
        return glyphs, [[INK] * cols for _ in range(rows)]
    # Quantize colours of the visible pixels, then lift them so they sit well on a dark panel.
    rgb = small.convert("RGB")
    q = rgb.quantize(colors=ncolors, method=Image.Quantize.MEDIANCUT).convert("RGB")
    hsv = np.asarray(q.convert("HSV"), dtype=np.float32)
    hsv[:, :, 1] = np.clip(hsv[:, :, 1] * 1.25, 0, 255)      # richer hue
    hsv[:, :, 2] = np.clip(np.maximum(hsv[:, :, 2] * 1.15, 120), 0, 255)  # never muddy on dark
    lifted = np.asarray(Image.fromarray(hsv.astype(np.uint8), "HSV").convert("RGB"))
    colors = [["#%02x%02x%02x" % tuple(lifted[r, c]) for c in range(cols)] for r in range(rows)]
    return glyphs, colors


def to_pixels(src: str, cols: int, ncolors: int):
    """Square pixel grid with a quantized, slightly lifted palette; None = transparent."""
    img = Image.open(src).convert("RGBA")
    prow = max(2, round(img.height / img.width * cols))
    small = img.resize((cols, prow), Image.Resampling.LANCZOS)
    alpha = np.asarray(small)[:, :, 3] > 96
    q = small.convert("RGB").quantize(colors=ncolors, method=Image.Quantize.MEDIANCUT).convert("RGB")
    hsv = np.asarray(q.convert("HSV"), dtype=np.float32)
    hsv[:, :, 1] = np.clip(hsv[:, :, 1] * 1.15, 0, 255)
    hsv[:, :, 2] = np.clip(np.maximum(hsv[:, :, 2] * 1.1, 70), 0, 255)
    rgb = np.asarray(Image.fromarray(hsv.astype(np.uint8), "HSV").convert("RGB"))
    return [["#%02x%02x%02x" % tuple(rgb[r, c]) if alpha[r, c] else None for c in range(cols)] for r in range(prow)]


def render_pixels(px, width, pad):
    """Pixel art as run-merged <rect>s (font-independent), one clip-wipe per pixel row."""
    cols, prow = len(px[0]), len(px)
    size = (width - 2 * pad) / cols
    height = round(prow * size + 2 * pad)
    stagger, wipe = 0.03, 0.45
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        f'<rect x="0.5" y="0.5" width="{width-1}" height="{height-1}" rx="8" fill="{BG}" stroke="{BORDER}"/>',
        '<g shape-rendering="crispEdges">',
    ]
    for r, row in enumerate(px):
        y = pad + r * size
        out.append(
            f'<clipPath id="r{r}"><rect x="{pad}" y="{y:.2f}" width="0" height="{size+0.5:.2f}">'
            f'<animate attributeName="width" from="0" to="{cols*size:.2f}" dur="{wipe}s" '
            f'begin="{r*stagger:.3f}s" fill="freeze"/></rect></clipPath>'
        )
        out.append(f'<g clip-path="url(#r{r})">')
        c = 0
        while c < cols:
            color = row[c]
            run = 1
            while c + run < cols and row[c + run] == color:
                run += 1
            if color:
                out.append(f'<rect x="{pad + c*size:.2f}" y="{y:.2f}" width="{run*size + 0.3:.2f}" '
                           f'height="{size + 0.3:.2f}" fill="{color}"/>')
            c += run
        out.append("</g>")
    out.append("</g></svg>")
    return "\n".join(out), height


def row_markup(glyphs: list[str], colors: list[str]) -> str:
    """Merge same-colour runs into tspans; spaces join whichever run they touch."""
    runs: list[tuple[str, list[str]]] = []
    for g, c in zip(glyphs, colors):
        if g == " " and runs:
            runs[-1][1].append(g)
        elif runs and (runs[-1][0] == c or all(x == " " for x in runs[-1][1])):
            runs[-1] = (c, runs[-1][1] + [g])
        else:
            runs.append((c, [g]))
    return "".join(f'<tspan fill="{c}">{escape("".join(chars))}</tspan>' for c, chars in runs)


def render(rows_markup: list[list[str]], cols, width, cell_w, cell_h, pad):
    """rows_markup: per text row, the inner markup of one or more overlapping <text> elements."""
    text_w = cols * cell_w
    height = round(len(rows_markup) * cell_h + 2 * pad)
    font_size = cell_w / 0.6  # monospace advance ~0.6em
    stagger, wipe = 0.045, 0.5
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        f'<rect x="0.5" y="0.5" width="{width-1}" height="{height-1}" rx="8" fill="{BG}" stroke="{BORDER}"/>',
        f'<g font-family="{FONT}" font-size="{font_size:.2f}" xml:space="preserve">',
    ]
    for i, layers in enumerate(rows_markup):
        y = pad + i * cell_h
        out.append(
            f'<clipPath id="r{i}"><rect x="{pad}" y="{y:.2f}" width="0" height="{cell_h+1:.2f}">'
            f'<animate attributeName="width" from="0" to="{text_w:.2f}" dur="{wipe}s" '
            f'begin="{i*stagger:.3f}s" fill="freeze"/></rect></clipPath>'
        )
        for inner in layers:
            out.append(
                f'<text x="{pad}" y="{y + cell_h*0.8:.2f}" clip-path="url(#r{i})" '
                f'textLength="{text_w:.2f}" lengthAdjust="spacingAndGlyphs">{inner}</text>'
            )
    out.append("</g></svg>")
    return "\n".join(out), height


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default="source-prepped.png")
    ap.add_argument("--out", default="altdoug-portrait.svg")
    ap.add_argument("--cols", type=int, default=48)
    ap.add_argument("--width", type=int, default=340)
    ap.add_argument("--pad", type=int, default=14)
    ap.add_argument("--gamma", type=float, default=1.0, help=">1 thins mid-tones, <1 thickens them")
    ap.add_argument("--colors", type=int, default=10, help="palette size")
    ap.add_argument("--mono", action="store_true", help="single light-grey ink instead of colour")
    ap.add_argument("--style", choices=["ascii", "pixels"], default="pixels",
                    help="pixels: run-merged rect pixel art (font-independent); ascii: density glyphs")
    a = ap.parse_args()
    cell_w = (a.width - 2 * a.pad) / a.cols
    cell_h = cell_w * 1.9
    if a.style == "pixels":
        px = to_pixels(a.src, a.cols, a.colors)
        svg, height = render_pixels(px, a.width, a.pad)
        rows = px
    else:
        glyphs, colors = to_grid(a.src, a.cols, cell_w, cell_h, a.gamma, a.colors, a.mono)
        rows = [[row_markup(g, c)] for g, c in zip(glyphs, colors)]
        svg, height = render(rows, a.cols, a.width, cell_w, cell_h, a.pad)
    with open(a.out, "w") as f:
        f.write(svg)
    print(f"wrote {a.out}: {a.cols}x{len(rows)} rows, {a.width}x{height}px, {len(svg)//1024}KB")


if __name__ == "__main__":
    main()
