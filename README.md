# strata-quarry

Encarta 2009 content ETL: turn the decoded disc into a searchable content store.

This is the **content pipeline** track (Linear project `strata-quarry`). It consumes
the [`strata-akc-portable`](../akc) decoder/extractor library and builds a SQLite
store with FTS5 full-text search, the article cross-reference graph, and (later) a
deduped asset store + media transcode.

## Status

Early. The first vertical slice is working and validated against the real
`CONTSTD.AKC`:

- `quarry build-content` — decode a `CONT*.AKC` via the portable decoder and load
  `article` (raw XML) + `article_fts` (FTS5) + `xref` (related-article graph from
  `<xref RefID=...>`) into SQLite. Idempotent: re-running replaces rows, it does not
  duplicate FTS entries (the prototype's bug).
- `quarry search` — full-text query over the built DB (bm25 ranked).

Not yet done: media/asset ingest from EIT baggage, `gid -> baggage-hexid` resolution
from `DATA*/DATAF*.AKC`, `REL*.AKC` related-articles, title resolution from the index,
media transcode. See Linear NEX-394/392/396/395.

## Provenance vs. the prototype

Supersedes the `encarta_pipeline.py` prototype (`encarta-flutter-pipeline.zip`), which
predated the AKC crack: it ignored `.AKC`, mistook `<bib>` bibliographies for article
bodies, and double-inserted FTS rows on re-run. Quarry sources article bodies from
decoded `CONT*.AKC` instead, and is built test-first against real data.

## Develop

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ../akc        # the strata-akc-portable decoder
pip install -e .

# unit tests (fast, no data needed)
python -m unittest discover -s tests

# integration tests (real data) — point at a disc + a key map
export STRATA_AKC_CONTSTD=/path/to/EE/ENCARTA/CONTSTD.AKC
export STRATA_AKC_CONTSTD_MAP=/path/to/key_refid_map.tsv
python -m unittest tests.test_ingest
```

## Build a content DB

```bash
# 1. build the key/refid map with the decoder (one-time, per AKC family)
strata-akc map-akc --akc CONTSTD.AKC --out output/contstd_map.tsv

# 2. ingest into SQLite + FTS5
quarry build-content --akc CONTSTD.AKC --map output/contstd_map.tsv \
  --db build/encarta.sqlite

# 3. search
quarry search "ottoman empire" --db build/encarta.sqlite
```
