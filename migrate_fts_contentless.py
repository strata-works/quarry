"""One-shot migration: rebuild article_fts as a contentless FTS5 table.

The body text already lives in article.xml, so the FTS index needn't keep a
second copy. Drops the old (content-storing) article_fts, recreates it
contentless, re-indexes from the stored article.xml (no AKC re-decode), then
VACUUMs to shrink the file. Idempotent-safe; FTS is fully derived.
"""
import sqlite3
import time
from pathlib import Path

from quarry.content import parse_article

DB = "build/encarta.sqlite"
DDL = ("CREATE VIRTUAL TABLE article_fts USING fts5("
       "body, content='', contentless_delete=1, tokenize='unicode61')")


def main() -> int:
    before = Path(DB).stat().st_size
    con = sqlite3.connect(DB)
    con.execute("DROP TABLE IF EXISTS article_fts")
    con.execute(DDL)

    read, write = con.cursor(), con.cursor()
    read.execute("SELECT refid, xml FROM article")
    t0 = time.time()
    n, batch = 0, []
    for refid, xml in read:
        batch.append((refid, parse_article(xml).text))
        n += 1
        if len(batch) >= 2000:
            write.executemany("INSERT INTO article_fts(rowid, body) VALUES (?,?)", batch)
            batch = []
    if batch:
        write.executemany("INSERT INTO article_fts(rowid, body) VALUES (?,?)", batch)
    con.commit()
    fts = con.execute("SELECT count(*) FROM article_fts").fetchone()[0]
    print(f"reindexed {n} articles (fts_count={fts}) in {time.time()-t0:.1f}s", flush=True)

    # sanity: search still works on the contentless index
    hit = con.execute(
        "SELECT rowid FROM article_fts WHERE article_fts MATCH 'aardvark' "
        "ORDER BY bm25(article_fts) LIMIT 1"
    ).fetchone()
    print("sample search 'aardvark' ->", hit, flush=True)

    print("VACUUM...", flush=True)
    con.execute("VACUUM")
    con.commit()
    con.close()
    after = Path(DB).stat().st_size
    print(f"size: {before/1e6:.1f} MB -> {after/1e6:.1f} MB "
          f"(saved {(before-after)/1e6:.1f} MB)", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
