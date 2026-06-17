"""quarry — Encarta content ETL CLI.

  build-content   CONT*.AKC + key map  -> SQLite (article + FTS5 + xref graph)
  search          query the built DB
"""
from __future__ import annotations

import argparse
import logging
import sys

from .ingest import ingest_akc
from .store import ContentStore


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

    b = sub.add_parser("build-content", help="CONT*.AKC -> SQLite content store")
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
