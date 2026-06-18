"""Parallel EIT/asset extraction across CPU cores.

The 119 EIT containers are independent, so we fan them out to a process pool.
Each worker decodes one container and writes its asset files directly (deduped by
content hash via atomic temp+rename, which is safe across workers — identical bytes
hash to the same path), then returns the asset rows. The parent stays the single
SQLite writer, so there's no DB-write contention.

The worker must be a module-level function: macOS uses spawn, so it has to pickle.
"""
from __future__ import annotations

import hashlib
import logging
import os
from concurrent.futures import ProcessPoolExecutor

from strata_akc_dump.lit import EitFile

from .assets import classify
from .store import ContentStore

logger = logging.getLogger(__name__)


def _extract_container(args: tuple[str, str]) -> tuple[list[tuple], dict]:
    eit_path, assets_dir = args
    source = os.path.basename(eit_path)
    rows: list[tuple] = []
    stats = {"source": source, "ok": 0, "failed": 0, "skipped": 0, "error": None}
    try:
        eit = EitFile(eit_path)
    except Exception as exc:  # noqa: BLE001 — non-ITOLITLS / unreadable container
        stats["error"] = str(exc)
        return rows, stats
    try:
        for name in eit.entries:
            base = os.path.basename(name)
            if name.startswith("::") or name.endswith("/") or not base:
                stats["skipped"] += 1
                continue
            try:
                data = eit.get_file(name)
            except Exception:  # noqa: BLE001
                stats["failed"] += 1
                continue
            kind = classify(base)
            ext = os.path.splitext(base)[1].lower()
            digest = hashlib.sha1(data).hexdigest()[:16]
            relpath = os.path.join(kind, f"{digest}{ext}")
            dest = os.path.join(assets_dir, relpath)
            if not os.path.exists(dest):
                os.makedirs(os.path.dirname(dest), exist_ok=True)
                tmp = f"{dest}.tmp{os.getpid()}"
                with open(tmp, "wb") as f:
                    f.write(data)
                os.replace(tmp, dest)  # atomic; concurrent identical writes are safe
            rows.append((os.path.splitext(base)[0], digest, kind, ext, relpath, source))
            stats["ok"] += 1
    finally:
        stream = getattr(eit, "stream", None)
        if stream is not None:
            stream.close()
    return rows, stats


def ingest_eit_parallel(eit_paths, store: ContentStore, workers: int | None = None) -> dict:
    if store.assets_dir is None:
        raise ValueError("ContentStore has no assets_dir; cannot store assets")
    assets_dir = str(store.assets_dir)
    os.makedirs(assets_dir, exist_ok=True)
    args = [(str(p), assets_dir) for p in eit_paths]
    totals = {"containers": 0, "assets_ok": 0, "assets_failed": 0, "skipped_containers": 0}
    with ProcessPoolExecutor(max_workers=workers) as ex:
        for rows, stats in ex.map(_extract_container, args):
            if stats["error"]:
                totals["skipped_containers"] += 1
                logger.warning("skipping container %s: %s", stats["source"], stats["error"])
                continue
            for r in rows:
                store.add_asset_row(*r)
            store.commit()
            totals["containers"] += 1
            totals["assets_ok"] += stats["ok"]
            totals["assets_failed"] += stats["failed"]
            logger.warning("ingested %s: ok=%d failed=%d", stats["source"], stats["ok"], stats["failed"])
    return totals
