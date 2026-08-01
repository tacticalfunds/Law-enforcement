"""Plate localization — find candidate plate regions in an image.

Two backends are provided:

* ``contour``  — classical OpenCV pipeline (morphology + contour filtering).
                 No model downloads; works everywhere OpenCV is installed.
                 This is the default.
* ``yolo``     — Ultralytics YOLO with a license-plate weights file. Much
                 more robust on real-world photos; requires ``ultralytics``
                 and a ``.pt`` model. Enabled only when a model path is given.

Every backend returns a list of :class:`~plate_reader.types.Detection`.
"""

from __future__ import annotations

from typing import Optional

import cv2
import numpy as np

from .types import BBox, Detection


# Plates are wide rectangles. These bounds are deliberately loose so we favour
# recall (the OCR stage rejects false positives that contain no readable text).
# The classical detector isolates the *character band* of the plate, which is
# tighter (and therefore wider in aspect) than the plate's outer rectangle.
# Long plates (e.g. 10 characters) can reach ~9:1, so the ceiling is generous;
# the OCR stage discards bands that contain no readable text.
MIN_ASPECT = 1.8
MAX_ASPECT = 10.0
MIN_AREA_FRAC = 0.0006   # region must be at least this fraction of the image
MAX_AREA_FRAC = 0.30     # ...and no larger than this (whole-image boxes are junk)


class ContourDetector:
    """Classical plate localizer using morphology + contour geometry.

    The idea: license plate characters form a dense horizontal band of edges.
    A black-hat morphological operation highlights that band; closing it
    joins the characters into a solid blob whose bounding box is the plate.
    """

    name = "contour"

    def __init__(self, min_aspect: float = MIN_ASPECT, max_aspect: float = MAX_ASPECT,
                 min_area_frac: float = MIN_AREA_FRAC, max_area_frac: float = MAX_AREA_FRAC):
        self.min_aspect = min_aspect
        self.max_aspect = max_aspect
        self.min_area_frac = min_area_frac
        self.max_area_frac = max_area_frac

    def detect(self, image: np.ndarray) -> list[Detection]:
        h, w = image.shape[:2]
        img_area = h * w
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        # Kernel widths scale with image size so the same code works on small
        # crops and large photos alike.
        kw = max(13, (w // 40) | 1)   # force odd
        rect_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (kw, 5))

        # Emphasise dark-on-light and light-on-dark text bands.
        blackhat = cv2.morphologyEx(gray, cv2.MORPH_BLACKHAT, rect_kernel)

        # Gradient in x picks up vertical character strokes.
        grad = cv2.Sobel(blackhat, ddepth=cv2.CV_32F, dx=1, dy=0, ksize=-1)
        grad = np.absolute(grad)
        gmin, gmax = grad.min(), grad.max()
        if gmax - gmin > 1e-6:
            grad = 255 * (grad - gmin) / (gmax - gmin)
        grad = grad.astype("uint8")

        # Close gaps between characters into a single horizontal region.
        grad = cv2.GaussianBlur(grad, (5, 5), 0)
        grad = cv2.morphologyEx(grad, cv2.MORPH_CLOSE, rect_kernel)
        thresh = cv2.threshold(grad, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)[1]

        # A wide horizontal close bridges the inter-character gaps so the whole
        # plate becomes one blob; a light erode trims the noise it introduces.
        wide_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (kw * 2 + 1, 7))
        thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, wide_kernel)
        thresh = cv2.erode(thresh, None, iterations=1)
        thresh = cv2.dilate(thresh, None, iterations=1)

        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL,
                                       cv2.CHAIN_APPROX_SIMPLE)

        detections: list[Detection] = []
        for c in contours:
            x, y, cw, ch = cv2.boundingRect(c)
            box = BBox(int(x), int(y), int(cw), int(ch))
            if not self._plausible(box, img_area):
                continue
            # Score by how plate-like the aspect ratio is (peak around 3.5:1),
            # scaled by fill ratio of the contour within its box.
            ar = box.aspect_ratio
            # Character bands cluster around ~5:1; score peaks there.
            ar_score = max(0.0, 1.0 - abs(ar - 5.0) / 5.0)
            fill = cv2.contourArea(c) / (box.area + 1e-6)
            score = float(np.clip(0.5 * ar_score + 0.5 * min(fill, 1.0), 0, 1))
            detections.append(Detection(bbox=box, score=score, source=self.name))

        detections.sort(key=lambda d: d.score, reverse=True)
        return detections

    def _plausible(self, box: BBox, img_area: int) -> bool:
        if box.h == 0 or box.w == 0:
            return False
        if not (self.min_aspect <= box.aspect_ratio <= self.max_aspect):
            return False
        frac = box.area / img_area
        return self.min_area_frac <= frac <= self.max_area_frac


class YoloDetector:
    """Ultralytics YOLO plate detector (optional, needs a weights file)."""

    name = "yolo"

    def __init__(self, model_path: str, conf: float = 0.25):
        try:
            from ultralytics import YOLO  # noqa: WPS433 (optional dependency)
        except ImportError as exc:  # pragma: no cover - depends on install
            raise ImportError(
                "The 'yolo' detector needs the 'ultralytics' package. "
                "Install it with:  pip install ultralytics"
            ) from exc
        self._model = YOLO(model_path)
        self.conf = conf

    def detect(self, image: np.ndarray) -> list[Detection]:
        results = self._model.predict(image, conf=self.conf, verbose=False)
        detections: list[Detection] = []
        for res in results:
            for box in res.boxes:
                x1, y1, x2, y2 = (int(v) for v in box.xyxy[0].tolist())
                detections.append(Detection(
                    bbox=BBox(x1, y1, x2 - x1, y2 - y1),
                    score=float(box.conf[0]),
                    source=self.name,
                ))
        detections.sort(key=lambda d: d.score, reverse=True)
        return detections


def build_detector(backend: str = "contour", *, model_path: Optional[str] = None,
                   conf: float = 0.25):
    """Factory for detectors. ``backend`` is 'contour' (default) or 'yolo'."""
    backend = backend.lower()
    if backend == "contour":
        return ContourDetector()
    if backend == "yolo":
        if not model_path:
            raise ValueError("backend='yolo' requires model_path=<path to .pt>")
        return YoloDetector(model_path, conf=conf)
    raise ValueError(f"Unknown detector backend: {backend!r}")
