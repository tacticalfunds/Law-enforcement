"""Generate a synthetic scene with a license plate for smoke-testing.

This creates a fake "car rear" image (gray body) with a white rectangular
plate bearing black characters, so the pipeline can be exercised without any
real vehicle photos. Real-world accuracy depends on the chosen backends.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import cv2
import numpy as np


def make_sample(text: str = "ABC1234", size: tuple[int, int] = (600, 900)) -> np.ndarray:
    h, w = size
    img = np.full((h, w, 3), 60, dtype=np.uint8)  # dark background / "car body"

    # Plate rectangle, centred, ~3.3:1 aspect ratio.
    pw, ph = 360, 110
    x = (w - pw) // 2
    y = (h - ph) // 2
    cv2.rectangle(img, (x, y), (x + pw, y + ph), (245, 245, 245), -1)
    cv2.rectangle(img, (x, y), (x + pw, y + ph), (30, 30, 30), 3)

    font = cv2.FONT_HERSHEY_SIMPLEX
    scale = 2.2
    thick = 6
    (tw, th), _ = cv2.getTextSize(text, font, scale, thick)
    tx = x + (pw - tw) // 2
    ty = y + (ph + th) // 2
    cv2.putText(img, text, (tx, ty), font, scale, (20, 20, 20), thick, cv2.LINE_AA)
    return img


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--text", default="ABC1234")
    ap.add_argument("--out", default=str(Path(__file__).parent / "sample_plate.jpg"))
    args = ap.parse_args()
    cv2.imwrite(args.out, make_sample(args.text))
    print(f"wrote {args.out}")
