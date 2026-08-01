"""plate_reader — license plate detection and recognition (ALPR/ANPR).

A small, self-contained toolkit that finds license plates in an image,
crops them, and reads their characters with OCR. Detection and OCR are
pluggable backends so you can start with zero model downloads (classical
OpenCV + Tesseract) and upgrade to YOLO / EasyOCR when you want more
accuracy.
"""

from .types import Detection, PlateResult
from .pipeline import PlateReader

__all__ = ["PlateReader", "Detection", "PlateResult"]
__version__ = "0.1.0"
