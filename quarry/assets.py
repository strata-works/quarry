"""Ingest media/baggage assets from Encarta EIT (ITOLITLS) containers.

Walks an opened ``EitFile``'s entries, classifies each by extension, and loads it
into the store's content-addressed asset store (deduped by hash). The baggage id
(entry stem) is the key articles reference via the gid->hexid map (NEX-392).
"""
from __future__ import annotations

import logging
import os

from strata_akc_dump.lit import EitFile

from .store import ContentStore

logger = logging.getLogger(__name__)

_KIND_BY_EXT = {
    ".jpg": "image", ".jpeg": "image", ".gif": "image", ".png": "image", ".bmp": "image",
    ".wma": "audio", ".wav": "audio", ".mp3": "audio",
    ".wmv": "video", ".avi": "video", ".mpg": "video", ".mpeg": "video",
    ".smi": "caption", ".smil": "caption",
    ".mid": "midi", ".midi": "midi",
    ".xml": "xml",
}


def classify(name: str) -> str:
    return _KIND_BY_EXT.get(os.path.splitext(name)[1].lower(), "other")


def ingest_eit(eit_path: str, store: ContentStore, source: str | None = None) -> dict:
    source = source or os.path.basename(eit_path)
    eit = EitFile(eit_path)
    stats = {"ok": 0, "failed": 0, "skipped": 0}
    try:
        for name in eit.entries:
            base = os.path.basename(name)
            # Skip ITOLITLS internal streams (::DataSpace/...) and directory markers.
            if name.startswith("::") or name.endswith("/") or not base:
                stats["skipped"] += 1
                continue
            try:
                data = eit.get_file(name)
            except Exception as exc:  # noqa: BLE001 — record and continue
                stats["failed"] += 1
                logger.warning("extract failed for %s in %s: %s", name, source, exc)
                continue
            baggage_id = os.path.splitext(base)[0]
            ext = os.path.splitext(base)[1].lower()
            store.add_asset(baggage_id, data, classify(base), ext, source=source)
            stats["ok"] += 1
    finally:
        stream = getattr(eit, "stream", None)
        if stream is not None:
            stream.close()
    return stats
