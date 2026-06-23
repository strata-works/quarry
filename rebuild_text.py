"""Corrected text rebuild: re-ingest content (UTF-8 FTS) + media (UTF-8 titles) +
backfill article.title, into the real DB. Assets are untouched (encoding-independent).
Run under PyPy. Idempotent.
"""
import time
from pathlib import Path

from quarry.corpus import build_corpus
from quarry.store import ContentStore

SRC = str(Path.home() / "Downloads/encarta")


def main() -> int:
    store = ContentStore("build/encarta.sqlite", assets_dir=None)
    print("before: articles", store.article_count(),
          "titles", store.title_count(), flush=True)
    t0 = time.perf_counter()
    totals = build_corpus(
        SRC, store, map_dir="output/maps",
        with_content=True, with_assets=False, with_media=True,
    )
    dt = time.perf_counter() - t0
    print(f"content ok={totals['ok']} media_ok={totals['media_ok']} "
          f"titles_backfilled={totals['titles']}  in {dt:.1f}s", flush=True)
    print("after: titles", store.title_count(), "of", store.article_count(), flush=True)
    for r in store.db.execute(
        "SELECT refid, title FROM article WHERE title!='' ORDER BY refid LIMIT 6"
    ):
        print("  ", r, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
