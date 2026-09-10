#!/usr/bin/env python3
"""Prepare a source image for the ASCII portrait.

Pipeline: background removal (rembg CLI, birefnet-general) -> CLAHE local
contrast boost -> crop to content -> save as RGBA (transparent background).
make_ascii_svg.py turns transparent cells into spaces, so the subject floats
on the panel colour.

Usage: python scripts/prep_photo.py <image> [--out source-prepped.png] [--skip-rembg]
An RGBA input with a real alpha channel skips rembg automatically.
"""
import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import cv2
import numpy as np
from PIL import Image


def remove_background(src: Path) -> Image.Image:
    img = Image.open(src)
    if img.mode == "RGBA" and img.getextrema()[3][0] < 255:
        return img  # already has transparency
    if shutil.which("rembg") is None:
        sys.exit("rembg not on PATH: uv tool install --python 3.11 'rembg[cpu,cli]'")
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "cutout.png"
        subprocess.run(["rembg", "i", str(src), str(out), "-m", "birefnet-general"], check=True)
        return Image.open(out).convert("RGBA").copy()


def boost_contrast(rgba: Image.Image) -> Image.Image:
    arr = np.array(rgba)
    bgr = cv2.cvtColor(arr[:, :, :3], cv2.COLOR_RGB2BGR)
    lab = cv2.cvtColor(bgr, cv2.COLOR_BGR2LAB)
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
    lab[:, :, 0] = clahe.apply(lab[:, :, 0])
    rgb = cv2.cvtColor(cv2.cvtColor(lab, cv2.COLOR_LAB2BGR), cv2.COLOR_BGR2RGB)
    arr[:, :, :3] = rgb
    return Image.fromarray(arr, "RGBA")


def crop_and_pad(rgba: Image.Image, pad_frac: float = 0.12) -> Image.Image:
    """Crop to the opaque bounding box, keep transparency (the SVG picks the panel colour)."""
    bbox = rgba.getchannel("A").point(lambda a: 255 if a > 8 else 0).getbbox()
    if bbox:
        rgba = rgba.crop(bbox)
    pad = round(rgba.width * pad_frac)
    padded = Image.new("RGBA", (rgba.width + 2 * pad, rgba.height + 2 * pad), (0, 0, 0, 0))
    padded.paste(rgba, (pad, pad))
    return padded


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("image")
    ap.add_argument("--out", default="source-prepped.png")
    args = ap.parse_args()
    cut = remove_background(Path(args.image))
    boosted = boost_contrast(cut)
    crop_and_pad(boosted).save(args.out)
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
