"""Full media fill: DATA*.AKC -> media/media_file/article_media in the real DB.

Media-only pass (skips content + EIT/assets) via the real build_corpus path.
Discovery is whitelisted to DATA_FAMILIES {DATASTD,DATADLX,DATASTC,DATAKDC}, so
the broken DATAF* variants are never touched. add_media_record is idempotent, so
this safely completes the partially-populated tables. Run under PyPy.
"""
import time
from pathlib import Path

from quarry.corpus import build_corpus
from quarry.store import ContentStore

SRC = str(Path.home() / "Downloads/encarta")
DB = "build/encarta.sqlite"
MAP_DIR = "output/maps"


def main() -> int:
    store = ContentStore(DB, assets_dir=None)
    print("before:", "media", store.media_count(),
          "media_file", store.media_file_count(),
          "article_media", store.article_media_count(), flush=True)
    t0 = time.perf_counter()
    totals = build_corpus(
        SRC, store, map_dir=MAP_DIR,
        with_content=False, with_assets=False, with_media=True,
    )
    dt = time.perf_counter() - t0
    print(f"media families={totals['media_families']} "
          f"ok={totals['media_ok']} failed={totals['media_failed']}  in {dt:.1f}s", flush=True)
    print("after:", "media", store.media_count(),
          "media_file", store.media_file_count(),
          "article_media", store.article_media_count(), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
