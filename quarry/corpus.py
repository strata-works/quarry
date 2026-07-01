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

from .assets import ingest_eit
from .ingest import ingest_akc, ingest_data
from .mindmaze import discover_mindmaze_db, ingest_mindmaze
from .store import ContentStore

logger = logging.getLogger(__name__)

# Article-content families by filename stem (uppercase): standard, deluxe/premium,
# student-compact, kids.
CONTENT_FAMILIES = {"CONTSTD", "CONTDLX", "CONTSTC", "CONTKDC"}

# Media/data-metadata families (the article<->asset link, NEX-392). Excludes the
# DATAF* index family (unsupported decoder path) and the DATA*SK source-gate files.
DATA_FAMILIES = {"DATASTD", "DATADLX", "DATASTC", "DATAKDC"}

# ITOLITLS container extensions holding media/baggage + the catalog.
CONTAINER_EXTS = {".eit", ".itr", ".ste"}


def _discover_akc(src: str, families: set[str]) -> list[Path]:
    found: list[Path] = []
    for dirpath, _dirs, files in os.walk(src):
        for fn in files:
            stem, ext = os.path.splitext(fn)
            if ext.lower() == ".akc" and stem.upper() in families:
                found.append(Path(dirpath) / fn)
    return sorted(found)


def discover_content_akc(src: str) -> list[Path]:
    return _discover_akc(src, CONTENT_FAMILIES)


def discover_data_akc(src: str) -> list[Path]:
    return _discover_akc(src, DATA_FAMILIES)


def discover_eit(src: str) -> list[Path]:
    found: list[Path] = []
    for dirpath, _dirs, files in os.walk(src):
        for fn in files:
            if os.path.splitext(fn)[1].lower() in CONTAINER_EXTS:
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
    with_assets: bool = True,
    with_content: bool = True,
    with_media: bool = True,
    with_mindmaze: bool = True,
    workers: int | None = None,
) -> dict:
    akcs = discover_content_akc(src) if with_content else []
    if families:
        want = {f.upper() for f in families}
        akcs = [a for a in akcs if a.stem.upper() in want]
    totals = {
        "families": 0, "ok": 0, "failed": 0, "per_family": {},
        "media_families": 0, "media_ok": 0, "media_failed": 0,
        "containers": 0, "assets_ok": 0, "assets_failed": 0,
        "mindmaze": {"questions": 0, "answers": 0, "with_area": 0},
    }
    # Article content (AKC).
    for akc in akcs:
        map_path = _ensure_map(akc, Path(map_dir))
        stats = ingest_akc(str(akc), str(map_path), store, limit=limit, source=akc.name)
        store.commit()
        totals["families"] += 1
        totals["ok"] += stats["ok"]
        totals["failed"] += stats["failed"]
        totals["per_family"][akc.name] = stats
        logger.warning("ingested %s: %s", akc.name, stats)

    # Media metadata + article<->asset links (DATA*.AKC, NEX-392).
    if with_media:
        data_akcs = discover_data_akc(src)
        if families:
            # match on edition suffix so e.g. --family CONTSTD also selects DATASTD
            want_suffix = {f.upper()[-3:] for f in families}
            data_akcs = [a for a in data_akcs if a.stem.upper()[-3:] in want_suffix]
        for akc in data_akcs:
            map_path = _ensure_map(akc, Path(map_dir))
            stats = ingest_data(str(akc), str(map_path), store, limit=limit, source=akc.name)
            store.commit()
            totals["media_families"] += 1
            totals["media_ok"] += stats["ok"]
            totals["media_failed"] += stats["failed"]
            logger.warning("ingested %s: %s", akc.name, stats)

    # MindMaze question bank (MINDMAZE.DB) — best-effort area assignment.
    if with_mindmaze:
        for db_path in discover_mindmaze_db(src):
            stats = ingest_mindmaze(db_path, store)
            totals["mindmaze"]["questions"] += stats["questions"]
            totals["mindmaze"]["answers"] += stats["answers"]
            totals["mindmaze"]["with_area"] += stats["with_area"]
            logger.warning("ingested %s: %s", db_path.name, stats)

    # Media/baggage assets (EIT containers) — parallel across cores when workers != 1.
    if with_assets and store.assets_dir is not None:
        eits = discover_eit(src)
        if workers is None or workers > 1:
            from .parallel import ingest_eit_parallel
            ptotals = ingest_eit_parallel(eits, store, workers=workers)
            totals["containers"] += ptotals["containers"]
            totals["assets_ok"] += ptotals["assets_ok"]
            totals["assets_failed"] += ptotals["assets_failed"]
        else:
            for eit in eits:
                try:
                    stats = ingest_eit(str(eit), store, source=eit.name)
                except Exception as exc:  # noqa: BLE001 — non-ITOLITLS / unreadable, skip
                    logger.warning("skipping container %s: %s", eit.name, exc)
                    continue
                store.commit()
                totals["containers"] += 1
                totals["assets_ok"] += stats["ok"]
                totals["assets_failed"] += stats["failed"]
                logger.warning("ingested %s: %s", eit.name, stats)

    # Article titles live in the same-refid DATA* record, not the body XML; fill them
    # once content + media are in place (idempotent, no-ops if either side is absent).
    totals["titles"] = store.backfill_article_titles()
    store.commit()
    logger.warning("backfilled %d article titles", totals["titles"])
    return totals
