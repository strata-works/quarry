# strata-quarry

Encarta 2009 content ETL: turn the decoded disc into a searchable content store.

This is the **content pipeline** track (Linear project `strata-quarry`). It consumes
the [`strata-akc-portable`](../akc) decoder/extractor library and builds a SQLite
store: article bodies + FTS5 full-text search, the cross-reference graph, resolved
titles, a content-addressed asset store with article↔media links, and the MindMaze
question bank.

## Status

The full ETL runs end-to-end against a real Encarta 2009 disc. A single `quarry build`
over the disc tree produces (counts from a full build):

- **Articles + search** — 116,119 articles (raw XML) with 116,116 titles resolved, a
  contentless FTS5 index, and a 211,505-edge cross-reference graph (from
  `<xref RefID=...>`). Idempotent: re-running replaces rows, it never duplicates FTS
  entries (the prototype's bug).
- **Assets + media** — 409,937 content-addressed, deduped asset binaries extracted
  from the EIT containers, plus the media graph (307,183 media / 514,398 media files /
  158,354 article↔media links) resolved from `DATA*.AKC`.
- **MindMaze** — 8,020 trivia questions / 32,080 answers decoded from `MINDMAZE.DB`
  into `mm_question` + `mm_answer`, each answer joined to its `article` by refid and
  tagged with a castle-wing area from the `Area*.lst` pools. See
  `docs/superpowers/plans/2026-07-01-mindmaze-01-decode.md`.
- `quarry search` — full-text query over the built DB (bm25 ranked).

Still ahead: media transcode (WMV/WMA), the reader UI, and the MindMaze game UI
(separate repos). See Linear NEX-395/396/397.

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

## Build the full corpus

Walk an extracted disc tree and ingest every content family plus assets, media links,
titles, and MindMaze questions in one pass:

```bash
quarry build --src /path/to/EE --db build/encarta.sqlite
```

The MindMaze pass runs after the EIT/asset pass (so the `Area*.lst` topic pools it uses
for area tagging already exist in the store); skip it with `--no-mindmaze`, or skip the
whole asset pass with `--assets-only`/`--no-assets`/`--no-media` as needed.
