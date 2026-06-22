"""Validate the quarry media build (DATA*.AKC -> media/article_media) under any interpreter.

Drives the real quarry build functions (`_ensure_map` + `ingest_data`) scoped to a
single DATA family, into a throwaway SQLite DB. Reports cold wall-clock, ok/failed
counts, and the resulting media / article_media table counts. Run under both CPython
and PyPy; counts MUST match.

Usage: python bench_media_build.py [N]   (N = records, default all)
"""
import sys
import tempfile
import time
from pathlib import Path

from quarry.corpus import _ensure_map
from quarry.ingest import ingest_data
from quarry.store import ContentStore

DATA = Path.home() / "Downloads/encarta/EE/ENCARTA/DATASTD.AKC"
MAP_DIR = Path(__file__).parent / "output/maps"


def main() -> int:
    n = int(sys.argv[1]) if len(sys.argv) > 1 else None
    impl = sys.implementation.name

    db = Path(tempfile.gettempdir()) / f"quarry_media_bench_{impl}.sqlite"
    if db.exists():
        db.unlink()
    store = ContentStore(str(db), assets_dir=None)

    map_path = _ensure_map(DATA, MAP_DIR)  # cached DATASTD.tsv -> instant

    t0 = time.perf_counter()
    stats = ingest_data(str(DATA), str(map_path), store, limit=n, source=DATA.name)
    store.commit()
    dt = time.perf_counter() - t0

    media = store.media_count()
    art_media = store.article_media_count()
    print(f"impl={impl}  records ok={stats['ok']} failed={stats['failed']}")
    print(f"decode+ingest_s={dt:.3f}  rec_per_s={stats['ok'] / dt:.1f}")
    print(f"media_count={media}  article_media_count={art_media}")
    print(f"db={db}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
