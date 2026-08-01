"""Draw detection boxes and plate text onto an image for visual output."""

from __future__ import annotations

import cv2
import numpy as np

from .types import PlateResult


def annotate(image: np.ndarray, results: list[PlateResult]) -> np.ndarray:
    """Return a copy of ``image`` with boxes + labels drawn for each result."""
    out = image.copy()
    for r in results:
        x, y, x2, y2 = r.bbox.as_xyxy()
        color = (0, 200, 0)
        cv2.rectangle(out, (x, y), (x2, y2), color, 2)

        label = f"{r.text} {r.confidence:.0%}"
        (tw, th), base = cv2.getTextSize(
            label, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2
        )
        top = max(0, y - th - base - 4)
        cv2.rectangle(out, (x, top), (x + tw + 6, y), color, -1)
        cv2.putText(
            out, label, (x + 3, y - base - 2),
            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 2, cv2.LINE_AA,
        )
    return out
