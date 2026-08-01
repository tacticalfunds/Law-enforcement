"""End-to-end pipeline: image in, structured plate readings out."""

from __future__ import annotations

from pathlib import Path
from typing import Optional, Union

import cv2
import numpy as np

from .detect import build_detector
from .ocr import build_ocr, normalize_plate_text
from .types import BBox, Detection, PlateResult

ImageLike = Union[str, Path, np.ndarray]


class PlateReader:
    """Locate plates in an image and read their characters.

    Example
    -------
    >>> reader = PlateReader()                      # contour + tesseract
    >>> results = reader.read("car.jpg")
    >>> for r in results:
    ...     print(r.text, round(r.confidence, 2), r.bbox.as_xyxy())
    """

    def __init__(
        self,
        detector: str = "contour",
        ocr: str = "tesseract",
        *,
        detector_model: Optional[str] = None,
        detector_conf: float = 0.25,
        max_candidates: int = 8,
        min_plate_len: int = 4,
        max_plate_len: int = 10,
        min_confidence: float = 0.10,
        fix_confusions: bool = False,
        ocr_kwargs: Optional[dict] = None,
    ):
        self.detector = build_detector(
            detector, model_path=detector_model, conf=detector_conf
        )
        self.ocr = build_ocr(ocr, **(ocr_kwargs or {}))
        self.max_candidates = max_candidates
        self.min_plate_len = min_plate_len
        self.max_plate_len = max_plate_len
        self.min_confidence = min_confidence
        self.fix_confusions = fix_confusions

    # -- public API ---------------------------------------------------------

    def read(self, image: ImageLike) -> list[PlateResult]:
        """Return plate readings for ``image``, best-confidence first."""
        img = self._load(image)
        candidates = self.detector.detect(img)[: self.max_candidates]

        results: list[PlateResult] = []
        for det in candidates:
            crop = self._crop(img, det.bbox)
            if crop.size == 0:
                continue
            raw, ocr_conf = self.ocr.read(crop)
            text = normalize_plate_text(raw, fix_confusions=self.fix_confusions)
            if not self._acceptable(text, ocr_conf, det):
                continue
            results.append(PlateResult(
                bbox=det.bbox,
                text=text,
                raw_text=raw,
                ocr_confidence=ocr_conf,
                detect_score=det.score,
                detector=self.detector.name,
                ocr_engine=self.ocr.name,
            ))

        results = self._dedupe(results)
        results.sort(key=lambda r: r.confidence, reverse=True)
        return results

    def read_to_dict(self, image: ImageLike) -> list[dict]:
        return [r.to_dict() for r in self.read(image)]

    # -- helpers ------------------------------------------------------------

    @staticmethod
    def _load(image: ImageLike) -> np.ndarray:
        if isinstance(image, np.ndarray):
            return image
        path = str(image)
        img = cv2.imread(path)
        if img is None:
            raise FileNotFoundError(f"Could not read image: {path}")
        return img

    @staticmethod
    def _crop(img: np.ndarray, box: BBox, pad: int = 4) -> np.ndarray:
        h, w = img.shape[:2]
        x1 = max(0, box.x - pad)
        y1 = max(0, box.y - pad)
        x2 = min(w, box.x2 + pad)
        y2 = min(h, box.y2 + pad)
        return img[y1:y2, x1:x2]

    def _acceptable(self, text: str, ocr_conf: float, det: Detection) -> bool:
        if not (self.min_plate_len <= len(text) <= self.max_plate_len):
            return False
        # A plate needs at least one digit or letter run; reject all-same junk.
        if len(set(text)) <= 1:
            return False
        combined = self._combine_conf(ocr_conf, det.score)
        return combined >= self.min_confidence

    @staticmethod
    def _combine_conf(ocr_conf: float, det_score: float) -> float:
        signals = [s for s in (ocr_conf, det_score) if s > 0]
        return sum(signals) / len(signals) if signals else 0.0

    @staticmethod
    def _dedupe(results: list[PlateResult]) -> list[PlateResult]:
        """Drop duplicate readings of the same plate text, keep the best."""
        best: dict[str, PlateResult] = {}
        for r in results:
            cur = best.get(r.text)
            if cur is None or r.confidence > cur.confidence:
                best[r.text] = r
        return list(best.values())
