"""SQLite + FTS5 content store for decoded Encarta articles.

Idempotent by design: re-ingesting an article replaces its rows in every table
(article, article_fts, xref) instead of appending — fixing the prototype's bug
where ``article_fts`` accumulated duplicate rows on each run.

``article_fts`` is a regular FTS5 table with ``rowid = refid``, so a re-ingest is
a plain ``DELETE ... WHERE rowid=?`` followed by an insert (contentless FTS5
forbids that delete, which is why the prototype couldn't dedupe).
"""
from __future__ import annotations

import sqlite3

from .content import ArticleRecord

_SCHEMA = """
CREATE TABLE IF NOT EXISTS article(
    refid   INTEGER PRIMARY KEY,
    source  TEXT,
    title   TEXT,            -- resolved later from the DATA*/CATALOG index
    xml     BLOB
);
CREATE VIRTUAL TABLE IF NOT EXISTS article_fts USING fts5(
    body,
    tokenize='unicode61'
);
CREATE TABLE IF NOT EXISTS xref(
    refid         INTEGER,
    target_refid  INTEGER,
    PRIMARY KEY (refid, target_refid)
);
"""


class ContentStore:
    def __init__(self, path: str = ":memory:"):
        self.db = sqlite3.connect(path)
        self.db.executescript(_SCHEMA)

    def add_article(self, rec: ArticleRecord, source: str) -> None:
        db = self.db
        db.execute(
            "INSERT OR REPLACE INTO article(refid, source, xml) VALUES (?,?,?)",
            (rec.refid, source, rec.xml),
        )
        # rowid == refid keeps the FTS row addressable for idempotent re-ingest.
        db.execute("DELETE FROM article_fts WHERE rowid=?", (rec.refid,))
        db.execute(
            "INSERT INTO article_fts(rowid, body) VALUES (?,?)",
            (rec.refid, rec.text),
        )
        db.execute("DELETE FROM xref WHERE refid=?", (rec.refid,))
        db.executemany(
            "INSERT OR IGNORE INTO xref(refid, target_refid) VALUES (?,?)",
            [(rec.refid, t) for t in rec.xrefs],
        )

    def commit(self) -> None:
        self.db.commit()

    def article_count(self) -> int:
        return self.db.execute("SELECT count(*) FROM article").fetchone()[0]

    def fts_count(self) -> int:
        return self.db.execute("SELECT count(*) FROM article_fts").fetchone()[0]

    def xref_count(self) -> int:
        return self.db.execute("SELECT count(*) FROM xref").fetchone()[0]

    def search(self, query: str) -> list[int]:
        rows = self.db.execute(
            "SELECT rowid FROM article_fts WHERE article_fts MATCH ? "
            "ORDER BY bm25(article_fts)",
            (query,),
        ).fetchall()
        return [r[0] for r in rows]
