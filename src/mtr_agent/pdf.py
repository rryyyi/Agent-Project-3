"""Vector PDF evidence extraction; geometric candidates always require review."""

import hashlib
import math
from pathlib import Path

import pymupdf

from .knowledge import Knowledge


def extract_pdf(path: str | Path, snap_distance: float = 60, max_pages: int = 100) -> dict:
    path = Path(path)
    if not path.is_file() or path.stat().st_size > 30 * 1024 * 1024:
        raise ValueError("PDF must exist and be <= 30 MiB")
    if snap_distance <= 0 or max_pages < 1:
        raise ValueError("Invalid PDF extraction limits")
    try:
        doc = pymupdf.open(path)
    except (pymupdf.FileDataError, RuntimeError) as exc:
        raise ValueError("Invalid PDF") from exc
    with doc:
        if not doc.is_pdf or doc.needs_pass or len(doc) > max_pages:
            raise ValueError("PDF must be unencrypted and within page limit")
        kb = Knowledge.load()
        pages = []
        for index, page in enumerate(doc):
            labels = []
            station_labels = []
            for block in page.get_text("dict")["blocks"]:
                for line in block.get("lines", []):
                    # A PDF span is a font run, not a station; merge spans within a text line.
                    text = "".join(span["text"] for span in line["spans"]).strip()
                    bbox = list(line["bbox"])
                    ids = kb.resolve(text)
                    label = {"text": text, "bbox": bbox, "station_ids": ids}
                    labels.append(label)
                    if len(ids) == 1:
                        station_labels.append(
                            (ids[0], ((bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2))
                        )
            segments = []
            for drawing in page.get_drawings():
                for item in drawing["items"]:
                    if item[0] == "l":
                        segments.append(
                            {
                                "start": list(item[1]),
                                "end": list(item[2]),
                                "color": list(drawing.get("color") or []),
                                "width": drawing.get("width"),
                                "path_id": drawing["seqno"],
                            }
                        )
            candidates = []
            for i, segment in enumerate(segments):
                nearest = []
                for point in (segment["start"], segment["end"]):
                    options = sorted(
                        (math.dist(point, center), sid) for sid, center in station_labels
                    )
                    nearest.append(
                        options[0] if options and options[0][0] <= snap_distance else None
                    )
                if all(nearest) and nearest[0][1] != nearest[1][1]:
                    candidates.append(
                        {
                            "a": nearest[0][1],
                            "b": nearest[1][1],
                            "segment_index": i,
                            "page": index + 1,
                            "endpoint_distances": [round(x[0], 2) for x in nearest],
                            "status": "unreviewed",
                            "method": "nearest-label-endpoints",
                        }
                    )
            pages.append(
                {
                    "page": index + 1,
                    "width": page.rect.width,
                    "height": page.rect.height,
                    "labels": labels,
                    "segments": segments,
                    "candidate_edges": candidates,
                    "needs_ocr": not bool(labels),
                }
            )
        return {
            "schema_version": "1",
            "filename": path.name,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "requires_review": True,
            "pages": pages,
            "limitations": [
                "No timetable or travel-time inference",
                "No OCR in baseline",
                "Crossings, curved paths and label offsets require human review",
                "Only stations in the packaged alias vocabulary are matched",
            ],
        }
