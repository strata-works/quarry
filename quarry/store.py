"""SQLite + FTS5 content store for decoded Encarta articles.

Idempotent by design: re-ingesting an article replaces its rows in every table
(article, article_fts, xref) instead of appending — fixing the prototype's bug
where ``article_fts`` accumulated duplicate rows on each run.

``article_fts`` is a regular FTS5 table with ``rowid = refid``, so a re-ingest is
a plain ``DELETE ... WHERE rowid=?`` followed by an insert (contentless FTS5
forbids that delete, which is why the prototype couldn't dedupe).
"""
from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path

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
CREATE TABLE IF NOT EXISTS asset(
    baggage_id  TEXT PRIMARY KEY,   -- entry stem; joined to by media_file.baggage_id
    hash        TEXT,               -- content hash (dedupe key)
    kind        TEXT,
    ext         TEXT,
    path        TEXT,               -- relative path under assets_dir
    source      TEXT
);
-- Media records + the article<->asset link, resolved from DATA*.AKC (NEX-392).
CREATE TABLE IF NOT EXISTS media(
    refid    INTEGER PRIMARY KEY,   -- the media content-id
    "group"  TEXT,
    title    TEXT,
    credit   TEXT,
    caption  TEXT,
    source   TEXT
);
CREATE TABLE IF NOT EXISTS media_file(
    media_refid  INTEGER,
    role         TEXT,              -- ticon | picon | thumb | image | ...
    baggage_id   TEXT,              -- joins to asset.baggage_id
    ext          TEXT,
    PRIMARY KEY (media_refid, role)
);
CREATE TABLE IF NOT EXISTS article_media(
    article_refid  INTEGER,
    media_refid    INTEGER,
    PRIMARY KEY (article_refid, media_refid)
);
"""


class ContentStore:
    def __init__(self, path: str = ":memory:", assets_dir: str | None = None):
        self.db = sqlite3.connect(path)
        self.db.executescript(_SCHEMA)
        self.assets_dir = Path(assets_dir) if assets_dir else None
        # hash -> relative path, seeded from existing rows so re-runs stay deduped.
        self._seen_hash: dict[str, str] = {
            h: p for h, p in self.db.execute("SELECT hash, path FROM asset")
        }

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

    def add_asset(self, baggage_id: str, data: bytes, kind: str, ext: str, source: str) -> None:
        if self.assets_dir is None:
            raise ValueError("ContentStore has no assets_dir; cannot store assets")
        digest = hashlib.sha1(data).hexdigest()[:16]
        relpath = self._seen_hash.get(digest)
        if relpath is None:
            dest = self.assets_dir / kind / f"{digest}{ext}"
            dest.parent.mkdir(parents=True, exist_ok=True)
            if not dest.exists():
                dest.write_bytes(data)
            relpath = str(dest.relative_to(self.assets_dir))
            self._seen_hash[digest] = relpath
        self.db.execute(
            "INSERT OR REPLACE INTO asset(baggage_id, hash, kind, ext, path, source) "
            "VALUES (?,?,?,?,?,?)",
            (baggage_id, digest, kind, ext, relpath, source),
        )

    def add_asset_row(self, baggage_id: str, digest: str, kind: str, ext: str,
                      path: str, source: str) -> None:
        """DB-only insert of an asset whose file a worker already wrote (parallel path)."""
        self._seen_hash.setdefault(digest, path)
        self.db.execute(
            "INSERT OR REPLACE INTO asset(baggage_id, hash, kind, ext, path, source) "
            "VALUES (?,?,?,?,?,?)",
            (baggage_id, digest, kind, ext, path, source),
        )

    def asset_count(self) -> int:
        return self.db.execute("SELECT count(*) FROM asset").fetchone()[0]

    def add_media_record(self, rec, source: str) -> None:
        db = self.db
        db.execute(
            'INSERT OR REPLACE INTO media(refid, "group", title, credit, caption, source) '
            "VALUES (?,?,?,?,?,?)",
            (rec.refid, rec.group, rec.title, rec.credit, rec.caption, source),
        )
        db.execute("DELETE FROM media_file WHERE media_refid=?", (rec.refid,))
        db.executemany(
            "INSERT OR REPLACE INTO media_file(media_refid, role, baggage_id, ext) VALUES (?,?,?,?)",
            [(rec.refid, f.role, f.baggage_id, f.ext) for f in rec.files],
        )
        db.executemany(
            "INSERT OR IGNORE INTO article_media(article_refid, media_refid) VALUES (?,?)",
            [(a, rec.refid) for a in rec.article_refids],
        )

    def media_count(self) -> int:
        return self.db.execute("SELECT count(*) FROM media").fetchone()[0]

    def media_file_count(self) -> int:
        return self.db.execute("SELECT count(*) FROM media_file").fetchone()[0]

    def article_media_count(self) -> int:
        return self.db.execute("SELECT count(*) FROM article_media").fetchone()[0]

    def backfill_article_titles(self) -> int:
        """Set article.title from the same-refid DATA* media record.

        Encarta article titles aren't in the body XML; each article's own
        DATA*.AKC record (media.refid == article.refid) carries the display
        title. Returns the number of article rows updated.
        """
        cur = self.db.execute(
            "UPDATE article SET title = ("
            "  SELECT m.title FROM media m WHERE m.refid = article.refid"
            ") WHERE refid IN ("
            "  SELECT refid FROM media WHERE title IS NOT NULL AND title != ''"
            ")"
        )
        return cur.rowcount

    def title_count(self) -> int:
        return self.db.execute(
            "SELECT count(*) FROM article WHERE title IS NOT NULL AND title != ''"
        ).fetchone()[0]

    def assets_for_article(self, article_refid: int) -> list[dict]:
        """Resolve an article's media to stored asset files (the NEX-392 join)."""
        rows = self.db.execute(
            "SELECT mf.media_refid, mf.role, mf.baggage_id, a.path, a.kind "
            "FROM article_media am "
            "JOIN media_file mf ON mf.media_refid = am.media_refid "
            "LEFT JOIN asset a ON a.baggage_id = mf.baggage_id "
            "WHERE am.article_refid = ?",
            (article_refid,),
        ).fetchall()
        cols = ("media_refid", "role", "baggage_id", "path", "kind")
        return [dict(zip(cols, r)) for r in rows]

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
