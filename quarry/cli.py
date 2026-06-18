"""quarry — Encarta content ETL CLI.

  build           walk an Encarta dir tree -> SQLite (all content families)
  build-content   one CONT*.AKC + key map -> SQLite (article + FTS5 + xref graph)
  search          query the built DB
"""
from __future__ import annotations

import argparse
import logging
import sys

from .corpus import build_corpus
from .ingest import ingest_akc
from .store import ContentStore


def cmd_build(args) -> int:
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(message)s")
    store = ContentStore(args.db, assets_dir=None if args.no_assets else args.assets_dir)
    totals = build_corpus(
        args.src, store, map_dir=args.map_dir, families=set(args.family or []),
        limit=args.limit, with_assets=not args.no_assets, with_content=not args.assets_only,
        with_media=not args.no_media and not args.assets_only, workers=args.workers,
    )
    if totals["families"] == 0 and totals["media_families"] == 0 and totals["containers"] == 0:
        print(f"no content/data AKC families or EIT containers found under {args.src}")
        return 1
    print(
        f"built {totals['families']} content + {totals['media_families']} data families, "
        f"{totals['containers']} containers -> {args.db}"
    )
    print(
        f"  totals: articles={store.article_count()} fts={store.fts_count()} "
        f"xref={store.xref_count()} assets={store.asset_count()} "
        f"media={store.media_count()} article_media={store.article_media_count()}"
    )
    for name, stats in totals["per_family"].items():
        print(f"  {name}: {stats['ok']} ok, {stats['failed']} failed")
    return 0


def cmd_build_content(args) -> int:
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(message)s")
    store = ContentStore(args.db)
    stats = ingest_akc(args.akc, args.map, store, limit=args.limit, source=args.source)
    store.commit()
    print(
        f"ingested {stats['ok']} articles ({stats['failed']} failed) -> {args.db}; "
        f"fts={store.fts_count()} xref={store.xref_count()}"
    )
    return 1 if stats["ok"] == 0 else 0


def cmd_search(args) -> int:
    store = ContentStore(args.db)
    hits = store.search(args.query)[: args.limit]
    print(f"{len(hits)} hit(s) for {args.query!r}:")
    for refid in hits:
        print(f"  {refid}")
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="quarry", description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)

    w = sub.add_parser("build", help="walk an Encarta dir tree and ingest all content families")
    w.add_argument("--src", required=True, help="extracted Encarta root (walked recursively)")
    w.add_argument("--db", default="./build/encarta.sqlite")
    w.add_argument("--map-dir", default="./output/maps", help="where per-family key maps are cached/built")
    w.add_argument("--assets-dir", default="./build/assets", help="content-addressed asset store dir")
    w.add_argument("--no-assets", action="store_true", help="skip the EIT/asset pass")
    w.add_argument("--no-media", action="store_true", help="skip the DATA*.AKC media/link pass")
    w.add_argument("--assets-only", action="store_true", help="only walk EIT for assets (skip AKC content + media)")
    w.add_argument("--family", action="append",
                   help="restrict to a content family stem, e.g. CONTSTD; may repeat")
    w.add_argument("--limit", type=int, help="ingest only the first N records per family (smoke test)")
    w.add_argument("--workers", type=int, help="parallel worker processes for the EIT/asset pass (default: pool default; 1 = sequential)")
    w.set_defaults(func=cmd_build)

    b = sub.add_parser("build-content", help="one CONT*.AKC -> SQLite content store")
    b.add_argument("--akc", required=True, help="path to a CONT*.AKC file")
    b.add_argument("--map", required=True, help="key/refid map TSV (from strata-akc map-akc)")
    b.add_argument("--db", default="./build/encarta.sqlite")
    b.add_argument("--limit", type=int, help="ingest only the first N records (smoke test)")
    b.add_argument("--source", help="source label stored per article (defaults to filename)")
    b.set_defaults(func=cmd_build_content)

    s = sub.add_parser("search", help="full-text search the built DB")
    s.add_argument("query")
    s.add_argument("--db", default="./build/encarta.sqlite")
    s.add_argument("--limit", type=int, default=20)
    s.set_defaults(func=cmd_search)

    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
