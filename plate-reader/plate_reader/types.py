"""Shared data structures for detection and recognition results."""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Optional


@dataclass
class BBox:
    """Axis-aligned bounding box in pixel coordinates (top-left origin)."""

    x: int
    y: int
    w: int
    h: int

    @property
    def x2(self) -> int:
        return self.x + self.w

    @property
    def y2(self) -> int:
        return self.y + self.h

    @property
    def area(self) -> int:
        return self.w * self.h

    @property
    def aspect_ratio(self) -> float:
        return self.w / self.h if self.h else 0.0

    def as_xyxy(self) -> tuple[int, int, int, int]:
        return (self.x, self.y, self.x2, self.y2)

    def to_dict(self) -> dict:
        return {"x": self.x, "y": self.y, "w": self.w, "h": self.h}


@dataclass
class Detection:
    """A candidate plate region located within an image."""

    bbox: BBox
    score: float = 0.0  # detector confidence, 0..1 (0 when a backend gives none)
    source: str = ""    # which detector produced it

    def to_dict(self) -> dict:
        return {"bbox": self.bbox.to_dict(), "score": round(self.score, 4),
                "source": self.source}


@dataclass
class PlateResult:
    """A detected plate together with its OCR reading."""

    bbox: BBox
    text: str
    ocr_confidence: float          # 0..1
    detect_score: float = 0.0      # 0..1
    detector: str = ""
    ocr_engine: str = ""
    raw_text: str = ""             # OCR output before normalization

    @property
    def confidence(self) -> float:
        """Combined confidence used for ranking (mean of the two signals)."""
        signals = [s for s in (self.detect_score, self.ocr_confidence) if s > 0]
        return sum(signals) / len(signals) if signals else 0.0

    def to_dict(self) -> dict:
        d = {
            "text": self.text,
            "raw_text": self.raw_text,
            "confidence": round(self.confidence, 4),
            "ocr_confidence": round(self.ocr_confidence, 4),
            "detect_score": round(self.detect_score, 4),
            "detector": self.detector,
            "ocr_engine": self.ocr_engine,
            "bbox": self.bbox.to_dict(),
        }
        return d
