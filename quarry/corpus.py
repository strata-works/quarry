"""Walk an extracted Encarta tree and ingest its article corpus.

Points at the disc root, finds the real article-content AKC families, builds (or
reuses) a key/refid map per family via the portable decoder, and ingests each
into one store. Editions overlap heavily (DLX ⊃ STD ⊃ STC); that's fine — articles
dedupe on ``refid`` (the PK), so a combined build just merges them.

Only the genuine content families are walked. Look-alikes such as ``CONTESK`` /
``CONTEDK`` / ``CONTECK`` are source-gate files that do NOT use the article codec
(per the decoder's README) and would fail to decode, so they are excluded by name.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path

from strata_akc_dump.portable_akc import write_refid_key_map

from .ingest import ingest_akc
from .store import ContentStore

logger = logging.getLogger(__name__)

# Article-content families by filename stem (uppercase): standard, deluxe/premium,
# student-compact, kids.
CONTENT_FAMILIES = {"CONTSTD", "CONTDLX", "CONTSTC", "CONTKDC"}


def discover_content_akc(src: str) -> list[Path]:
    found: list[Path] = []
    for dirpath, _dirs, files in os.walk(src):
        for fn in files:
            stem, ext = os.path.splitext(fn)
            if ext.lower() == ".akc" and stem.upper() in CONTENT_FAMILIES:
                found.append(Path(dirpath) / fn)
    return sorted(found)


def _ensure_map(akc: Path, map_dir: Path) -> Path:
    map_dir.mkdir(parents=True, exist_ok=True)
    map_path = map_dir / f"{akc.stem}.tsv"
    if map_path.exists():
        logger.info("reusing cached map %s", map_path)
    else:
        logger.warning("building map for %s (this can take a while)...", akc.name)
        write_refid_key_map(akc, map_path)
    return map_path


def build_corpus(
    src: str,
    store: ContentStore,
    map_dir: str,
    families: set[str] | None = None,
    limit: int | None = None,
) -> dict:
    akcs = discover_content_akc(src)
    if families:
        want = {f.upper() for f in families}
        akcs = [a for a in akcs if a.stem.upper() in want]
    totals = {"families": 0, "ok": 0, "failed": 0, "per_family": {}}
    for akc in akcs:
        map_path = _ensure_map(akc, Path(map_dir))
        stats = ingest_akc(str(akc), str(map_path), store, limit=limit, source=akc.name)
        store.commit()
        totals["families"] += 1
        totals["ok"] += stats["ok"]
        totals["failed"] += stats["failed"]
        totals["per_family"][akc.name] = stats
        logger.warning("ingested %s: %s", akc.name, stats)
    return totals
