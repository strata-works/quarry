"""Ingest a decoded CONT*.AKC corpus into the content store.

Uses the ``strata_akc_dump`` portable decoder (no msitss / Windows) to turn each
mapped record into article XML, then parses it into a store row. Failures are
logged per-refid and counted, never silently swallowed.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path

from strata_akc_dump.portable_akc import ArticleWindow, PortableAkcDecoder

from .content import parse_article
from .store import ContentStore

logger = logging.getLogger(__name__)


def _read_map(map_path: str, limit: int | None = None):
    rows: list[tuple[int, ArticleWindow]] = []
    with open(map_path, encoding="utf-8") as f:
        idx = {name: i for i, name in enumerate(f.readline().rstrip("\n").split("\t"))}
        for line in f:
            parts = line.rstrip("\n").split("\t")
            if not parts[idx["refid"]]:
                continue
            rows.append(
                (
                    int(parts[idx["refid"]]),
                    ArticleWindow(
                        key=int(parts[idx["key"]]),
                        body_off=int(parts[idx["body_off"]]),
                        body_size=int(parts[idx["body_size"]]),
                        xml_size=int(parts[idx["xml_bytes"]]),
                        token_offset=int(parts[idx["token_offset"]]),
                        token_count=int(parts[idx["token_count"]]),
                    ),
                )
            )
            if limit and len(rows) >= limit:
                break
    return rows


def ingest_akc(
    akc_path: str,
    map_path: str,
    store: ContentStore,
    limit: int | None = None,
    source: str | None = None,
) -> dict:
    source = source or os.path.basename(akc_path)
    dec = PortableAkcDecoder(Path(akc_path), map_path=Path(map_path))
    stats = {"ok": 0, "failed": 0}
    for refid, win in _read_map(map_path, limit=limit):
        try:
            article = dec.decode_window(win) if win.body_off >= 0 else dec.decode_key(win.key)
            rec = parse_article(article.xml)
        except Exception as exc:  # noqa: BLE001 — record and continue, don't abort the run
            stats["failed"] += 1
            logger.warning("ingest failed for refid %s: %s", refid, exc)
            continue
        store.add_article(rec, source=source)
        stats["ok"] += 1
    return stats
