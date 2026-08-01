"""Parallel, memory-bounded batch processing over many images.

The core entry point is :func:`process`, which reads a list of images with a
pool of worker processes and hands each image's results to a callback as soon
as it is ready. Results are streamed (never accumulated in one big list), so
memory stays flat whether you run over ten images or ten million.

Workers are configured by a plain ``cfg`` dict (the keyword arguments for
:class:`~plate_reader.pipeline.PlateReader`) rather than a live reader object,
because OCR/detector backends are not picklable — each worker builds its own
reader once, in an initializer, and reuses it for every image it handles.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path
from typing import Callable, Optional, TextIO

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp", ".tif", ".tiff"}

# A per-image outcome: (image_path, list_of_plate_dicts, error_or_None).
Record = tuple[str, list, Optional[str]]
OnResult = Callable[[str, list, Optional[str]], None]


def collect_images(root: Path, recursive: bool = True) -> list[Path]:
    """List image files under ``root`` (a file returns just itself)."""
    if root.is_dir():
        it = root.rglob("*") if recursive else root.glob("*")
        return sorted(p for p in it if p.suffix.lower() in IMAGE_EXTS)
    return [root]


# --- worker-process state ---------------------------------------------------
# Each worker builds one reader in its initializer and stashes it here so every
# image it processes reuses the same (expensive to construct) backends.
_reader = None
_annotate_dir: Optional[str] = None


def _init_worker(cfg: dict, annotate_dir: Optional[str]) -> None:
    global _reader, _annotate_dir
    from .pipeline import PlateReader
    _reader = PlateReader(**cfg)
    _annotate_dir = annotate_dir


def _read_one(path_str: str) -> Record:
    """Read a single image. Never raises: failures come back as an error."""
    import cv2  # imported here so the module import stays light for workers

    img = cv2.imread(path_str)
    if img is None:
        return (path_str, [], "unreadable")
    try:
        results = _reader.read(img)  # type: ignore[union-attr]
    except Exception as exc:  # keep the batch going past a bad image
        return (path_str, [], f"error: {exc}")

    dicts = [r.to_dict() for r in results]
    if _annotate_dir:
        from .draw import annotate as draw_annotate
        src = Path(path_str)
        out = Path(_annotate_dir) / f"{src.stem}_annotated{src.suffix}"
        cv2.imwrite(str(out), draw_annotate(img, results))
    return (path_str, dicts, None)


def resolve_workers(workers: int) -> int:
    """``workers <= 0`` means auto (all CPUs); otherwise use the value given."""
    if workers and workers > 0:
        return workers
    return max(1, os.cpu_count() or 1)


def _emit_progress(done: int, total: int, plates: int, start: float,
                   log: TextIO, every: int = 20) -> None:
    if done % every != 0 and done != total:
        return
    elapsed = time.time() - start
    rate = done / elapsed if elapsed > 0 else 0.0
    eta = (total - done) / rate if rate > 0 else 0.0
    log.write(
        f"\r{done}/{total} images  {plates} plates  "
        f"{rate:5.1f} img/s  ETA {eta:5.0f}s "
    )
    log.flush()


def process(
    images: list[Path],
    cfg: dict,
    on_result: OnResult,
    *,
    workers: int = 0,
    annotate_dir: Optional[str] = None,
    progress: bool = False,
    log: TextIO = sys.stderr,
) -> dict:
    """Read ``images`` and invoke ``on_result(path, plates, error)`` per image.

    ``on_result`` runs in the main process, in completion order, so it is safe
    to write to a file or print from it without any locking.

    Returns a small stats dict: ``{"images", "plates", "seconds"}``.
    """
    total = len(images)
    n_workers = resolve_workers(workers)
    start = time.time()
    done = 0
    plates_found = 0

    def handle(rec: Record) -> None:
        nonlocal done, plates_found
        path_str, plates, error = rec
        on_result(path_str, plates, error)
        done += 1
        plates_found += len(plates)
        if progress:
            _emit_progress(done, total, plates_found, start, log)

    if n_workers <= 1 or total <= 1:
        # Serial: build one reader in-process and reuse it.
        _init_worker(cfg, annotate_dir)
        for p in images:
            handle(_read_one(str(p)))
    else:
        from concurrent.futures import ProcessPoolExecutor

        paths = [str(p) for p in images]
        # Chunk so workers are fed in batches (less IPC overhead) while results
        # still stream back in order and memory stays bounded.
        chunksize = max(1, min(64, total // (n_workers * 4) or 1))
        with ProcessPoolExecutor(
            max_workers=n_workers,
            initializer=_init_worker,
            initargs=(cfg, annotate_dir),
        ) as ex:
            for rec in ex.map(_read_one, paths, chunksize=chunksize):
                handle(rec)

    if progress and total:
        log.write("\n")
        log.flush()

    return {
        "images": done,
        "plates": plates_found,
        "seconds": round(time.time() - start, 3),
    }
