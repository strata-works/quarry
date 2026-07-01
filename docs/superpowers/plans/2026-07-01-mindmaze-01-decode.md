# MindMaze Phase 1 — Decode Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Parse `MINDMAZE.DB` into `mm_question` / `mm_answer` tables inside the existing `encarta.sqlite`, with each answer joinable to the `article` table and each question tagged with its castle-wing area.

**Architecture:** Add a pure `parse_mindmaze_db(bytes) -> list[MindMazeQuestion]` decoder plus an area-assignment step to the `quarry` package, extend `ContentStore` with the two tables, and wire a `MINDMAZE.DB` pass into `build_corpus` (after the EIT/asset pass, so the `Area*.lst` pools exist). No new dependencies; mirrors the existing `content.py` → `store.py` → `corpus.py` flow.

**Tech Stack:** Python ≥3.10, stdlib `struct` + `sqlite3`, `unittest`. Part of the `strata-quarry` package (repo: `/Users/nexus/projects/experiments/strata/quarry`).

## Global Constraints

- Python ≥3.10; standard library only (no new deps in `pyproject.toml`).
- Tests use `unittest` with an in-memory `ContentStore(":memory:")` and inline byte fixtures — match `tests/test_store.py`.
- All writes are idempotent: re-ingesting replaces a question's rows (`INSERT OR REPLACE` on `mm_question`, `DELETE ... WHERE question_id=?` then insert on `mm_answer`) — match the `article`/`xref` pattern in `store.py`.
- Text fields decode as **cp1252** (raw Microsoft file; not AKC/UTF-8). Never use UTF-8 for `MINDMAZE.DB` bytes.
- Source binaries are read-only at `~/Downloads/encarta/EE/ENCARTA/MINDMAZE.DB`; never modify them.
- Record format (validated: 8,020 records, entire 1,468,275-byte file consumed, 4 answers each):
  ```
  u32  zero marker (0x00000000)
  u32  clue_len (little-endian)
  bytes[clue_len]           clue
  answer × 4:
     u8   answer_len
     bytes[answer_len]      answer text
     u32  article_refid     (little-endian; joins article.refid)
     u16  flag              (mostly 1; semantics unknown — preserved raw)
  ```
  Answer ordinal 0 is the authored **correct** answer; ordinals 1–3 are decoys. A record ends where the next 4 bytes are `0x00000000` followed by a plausible `clue_len` (`0 < n < 1000`), or at EOF.
- Run tests from the repo root with the dev env: `source ../akc/.venv/bin/activate && python -m unittest -v`.

---

### Task 1: `parse_mindmaze_db` decoder

**Files:**
- Create: `quarry/mindmaze.py`
- Test: `tests/test_mindmaze.py`

**Interfaces:**
- Produces:
  - `@dataclass MindMazeAnswer(text: str, article_refid: int, is_correct: bool, flag: int)`
  - `@dataclass MindMazeQuestion(clue: str, answers: list[MindMazeAnswer], area: int | None = None)`
  - `parse_mindmaze_db(data: bytes) -> list[MindMazeQuestion]`
  - Test helpers `mk_answer(text: str, refid: int, flag: int = 1) -> bytes` and `mk_record(clue: str, answers: list[tuple[str, int]]) -> bytes` (defined in the test file).

- [ ] **Step 1: Write the failing test**

Create `tests/test_mindmaze.py`:

```python
import struct
import unittest

from quarry.mindmaze import MindMazeAnswer, MindMazeQuestion, parse_mindmaze_db


def mk_answer(text, refid, flag=1):
    b = text.encode("cp1252")
    return bytes([len(b)]) + b + struct.pack("<I", refid) + struct.pack("<H", flag)


def mk_record(clue, answers):
    b = clue.encode("cp1252")
    out = struct.pack("<I", 0) + struct.pack("<I", len(b)) + b
    for text, refid in answers:
        out += mk_answer(text, refid)
    return out


# Two records mirroring the real file's first entries.
FIXTURE = mk_record(
    "Apparatus on aircraft for aiming and releasing bombs.",
    [("Bombsight", 761574727), ("Depth Charge", 761571708),
     ("Guided Missile", 761560558), ("Bazooka", 761551777)],
) + mk_record(
    "Self-powered work vehicle designed for transporting machinery or heavy loads.",
    [("Tractor", 761568751), ("Cultivator", 761558556),
     ("Plow", 761555730), ("Prairie Schooner", 761566610)],
)


class ParseMindMazeDbTests(unittest.TestCase):
    def test_parses_all_records_with_four_answers(self):
        qs = parse_mindmaze_db(FIXTURE)
        self.assertEqual(len(qs), 2)
        self.assertTrue(all(len(q.answers) == 4 for q in qs))

    def test_first_record_fields(self):
        q = parse_mindmaze_db(FIXTURE)[0]
        self.assertEqual(q.clue, "Apparatus on aircraft for aiming and releasing bombs.")
        self.assertEqual(q.answers[0], MindMazeAnswer("Bombsight", 761574727, True, 1))
        self.assertEqual(q.answers[1].text, "Depth Charge")
        self.assertEqual(q.answers[1].article_refid, 761571708)

    def test_only_first_answer_is_correct(self):
        q = parse_mindmaze_db(FIXTURE)[0]
        self.assertEqual([a.is_correct for a in q.answers], [True, False, False, False])

    def test_area_defaults_to_none(self):
        self.assertIsNone(parse_mindmaze_db(FIXTURE)[0].area)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `source ../akc/.venv/bin/activate && python -m unittest tests.test_mindmaze -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'quarry.mindmaze'`.

- [ ] **Step 3: Write minimal implementation**

Create `quarry/mindmaze.py`:

```python
"""Decode MINDMAZE.DB (the Encarta MindMaze question bank).

MINDMAZE.DB is a raw Microsoft data file — NOT an AKC/EIT container, so it needs
no LZX/Huffman codec, just a length-prefixed record walk. Each record is a clue
plus four answers; answer 0 is the authored correct answer, answers 1-3 decoys.
Every answer carries an ``article.refid`` so answers link straight into the
encyclopedia. Text is cp1252 (raw MS file), not the UTF-8 the AKC decoder emits.
"""
from __future__ import annotations

import struct
from dataclasses import dataclass, field

_ENC = "cp1252"
_MAX_LEN = 1000  # clue/answer sanity bound; real clues are < 300 bytes


@dataclass
class MindMazeAnswer:
    text: str
    article_refid: int
    is_correct: bool
    flag: int


@dataclass
class MindMazeQuestion:
    clue: str
    answers: list[MindMazeAnswer] = field(default_factory=list)
    area: int | None = None


def _at_record_marker(data: bytes, j: int) -> bool:
    """True if a new record header (u32 zero + plausible clue_len) starts at j."""
    if j + 8 > len(data):
        return False
    zero, clue_len = struct.unpack_from("<II", data, j)
    return zero == 0 and 0 < clue_len < _MAX_LEN


def parse_mindmaze_db(data: bytes) -> list[MindMazeQuestion]:
    n = len(data)
    i = 0
    out: list[MindMazeQuestion] = []
    while i + 8 <= n:
        zero, clue_len = struct.unpack_from("<II", data, i)
        if zero != 0 or not (0 < clue_len < _MAX_LEN) or i + 8 + clue_len > n:
            break
        j = i + 8 + clue_len
        clue = data[i + 8:j].decode(_ENC)
        answers: list[MindMazeAnswer] = []
        while j < n and not _at_record_marker(data, j):
            alen = data[j]
            if alen == 0 or j + 1 + alen + 6 > n:
                break
            text = data[j + 1:j + 1 + alen].decode(_ENC)
            k = j + 1 + alen
            refid, flag = struct.unpack_from("<IH", data, k)
            answers.append(MindMazeAnswer(text, refid, not answers, flag))
            j = k + 6
        out.append(MindMazeQuestion(clue, answers))
        i = j
    return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `source ../akc/.venv/bin/activate && python -m unittest tests.test_mindmaze -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add quarry/mindmaze.py tests/test_mindmaze.py
git commit -m "feat(mindmaze): decode MINDMAZE.DB question records"
```

---

### Task 2: Area assignment from `Area*.lst` pools

**Files:**
- Modify: `quarry/mindmaze.py`
- Test: `tests/test_mindmaze.py`

**Interfaces:**
- Consumes: `MindMazeQuestion` (Task 1).
- Produces:
  - `assign_areas(questions: list[MindMazeQuestion], pools: dict[int, set[int]]) -> None` — mutates each question's `.area` to the lowest-index area whose pool contains the question's correct-answer refid, or `None` if unmatched.
  - `build_area_pools(store) -> dict[int, set[int]]` — reads `Area0..Area8` `.lst` assets from a `ContentStore` (returns `{}` if the assets/`assets_dir` are absent).

- [ ] **Step 1: Write the failing test**

Add to `tests/test_mindmaze.py`:

```python
from quarry.mindmaze import assign_areas


class AssignAreasTests(unittest.TestCase):
    def _questions(self):
        return parse_mindmaze_db(FIXTURE)

    def test_assigns_lowest_matching_area(self):
        qs = self._questions()
        pools = {0: {761574727}, 1: {761574727, 761568751}, 2: {761568751}}
        assign_areas(qs, pools)
        self.assertEqual(qs[0].area, 0)  # Bombsight refid in areas 0 and 1 -> 0
        self.assertEqual(qs[1].area, 1)  # Tractor refid in areas 1 and 2 -> 1

    def test_unmatched_refid_area_is_none(self):
        qs = self._questions()
        assign_areas(qs, {5: {999}})
        self.assertIsNone(qs[0].area)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `source ../akc/.venv/bin/activate && python -m unittest tests.test_mindmaze.AssignAreasTests -v`
Expected: FAIL — `ImportError: cannot import name 'assign_areas'`.

- [ ] **Step 3: Write minimal implementation**

Append to `quarry/mindmaze.py`:

```python
def assign_areas(questions: list[MindMazeQuestion],
                 pools: dict[int, set[int]]) -> None:
    for q in questions:
        if not q.answers:
            q.area = None
            continue
        rid = q.answers[0].article_refid
        q.area = next((idx for idx in sorted(pools) if rid in pools[idx]), None)


def build_area_pools(store) -> dict[int, set[int]]:
    """Read the 9 Area*.lst refid pools out of the extracted MINDMAZE.EIT assets.

    Returns {} when the asset rows or the on-disk .lst files are not present, so
    a caller can still ingest questions with area=None.
    """
    if store.assets_dir is None:
        return {}
    pools: dict[int, set[int]] = {}
    for idx in range(9):
        row = store.db.execute(
            "SELECT path FROM asset WHERE source='MINDMAZE.EIT' AND baggage_id=?",
            (f"Area{idx}",),
        ).fetchone()
        if not row:
            continue
        path = store.assets_dir / row[0]
        if not path.exists():
            continue
        ids = {int(tok) for tok in path.read_bytes().split() if tok.strip().isdigit()}
        if ids:
            pools[idx] = ids
    return pools
```

- [ ] **Step 4: Run test to verify it passes**

Run: `source ../akc/.venv/bin/activate && python -m unittest tests.test_mindmaze -v`
Expected: PASS (6 tests total).

- [ ] **Step 5: Commit**

```bash
git add quarry/mindmaze.py tests/test_mindmaze.py
git commit -m "feat(mindmaze): assign questions to castle-wing areas from Area*.lst"
```

---

### Task 3: `ContentStore` tables + insert

**Files:**
- Modify: `quarry/store.py` (add to `_SCHEMA`; add methods to `ContentStore`)
- Test: `tests/test_mindmaze_store.py`

**Interfaces:**
- Consumes: `MindMazeQuestion` / `MindMazeAnswer` (Task 1).
- Produces on `ContentStore`:
  - `add_mindmaze_question(self, qid: int, rec: MindMazeQuestion) -> None`
  - `mm_question_count(self) -> int`
  - `mm_answer_count(self) -> int`
- New tables: `mm_question(id, area, clue)`, `mm_answer(id, question_id, ordinal, text, article_refid, is_correct, flag)`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_mindmaze_store.py`:

```python
import unittest

from quarry.mindmaze import MindMazeAnswer, MindMazeQuestion
from quarry.store import ContentStore


def _q():
    return MindMazeQuestion(
        clue="Apparatus on aircraft for aiming and releasing bombs.",
        answers=[
            MindMazeAnswer("Bombsight", 761574727, True, 1),
            MindMazeAnswer("Depth Charge", 761571708, False, 1),
            MindMazeAnswer("Guided Missile", 761560558, False, 1),
            MindMazeAnswer("Bazooka", 761551777, False, 1),
        ],
        area=3,
    )


class MindMazeStoreTests(unittest.TestCase):
    def setUp(self):
        self.store = ContentStore(":memory:")

    def test_add_question_populates_both_tables(self):
        self.store.add_mindmaze_question(0, _q())
        self.store.commit()
        self.assertEqual(self.store.mm_question_count(), 1)
        self.assertEqual(self.store.mm_answer_count(), 4)

    def test_correct_answer_and_area_stored(self):
        self.store.add_mindmaze_question(0, _q())
        self.store.commit()
        row = self.store.db.execute(
            "SELECT text, article_refid FROM mm_answer "
            "WHERE question_id=0 AND is_correct=1"
        ).fetchone()
        self.assertEqual(row, ("Bombsight", 761574727))
        area = self.store.db.execute(
            "SELECT area FROM mm_question WHERE id=0"
        ).fetchone()[0]
        self.assertEqual(area, 3)

    def test_reingest_is_idempotent(self):
        for _ in range(3):
            self.store.add_mindmaze_question(0, _q())
        self.store.commit()
        self.assertEqual(self.store.mm_question_count(), 1)
        self.assertEqual(self.store.mm_answer_count(), 4)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `source ../akc/.venv/bin/activate && python -m unittest tests.test_mindmaze_store -v`
Expected: FAIL — `AttributeError: 'ContentStore' object has no attribute 'add_mindmaze_question'`.

- [ ] **Step 3: Write minimal implementation**

In `quarry/store.py`, append these tables to the `_SCHEMA` string (before its closing `"""`):

```python
CREATE TABLE IF NOT EXISTS mm_question(
    id    INTEGER PRIMARY KEY,   -- 0-based record index in MINDMAZE.DB
    area  INTEGER,               -- castle wing 0-8 (nullable; from Area*.lst)
    clue  TEXT
);
CREATE TABLE IF NOT EXISTS mm_answer(
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    question_id   INTEGER,
    ordinal       INTEGER,       -- 0 = authored correct answer, 1-3 = decoys
    text          TEXT,
    article_refid INTEGER,       -- joins article.refid
    is_correct    INTEGER,       -- 1 for ordinal 0, else 0
    flag          INTEGER        -- raw per-answer u16 (semantics TBD; preserved)
);
```

Add these methods to the `ContentStore` class (next to `add_media_record`):

```python
    def add_mindmaze_question(self, qid: int, rec) -> None:
        db = self.db
        db.execute(
            "INSERT OR REPLACE INTO mm_question(id, area, clue) VALUES (?,?,?)",
            (qid, rec.area, rec.clue),
        )
        db.execute("DELETE FROM mm_answer WHERE question_id=?", (qid,))
        db.executemany(
            "INSERT INTO mm_answer"
            "(question_id, ordinal, text, article_refid, is_correct, flag) "
            "VALUES (?,?,?,?,?,?)",
            [
                (qid, ordinal, a.text, a.article_refid,
                 1 if a.is_correct else 0, a.flag)
                for ordinal, a in enumerate(rec.answers)
            ],
        )

    def mm_question_count(self) -> int:
        return self.db.execute("SELECT count(*) FROM mm_question").fetchone()[0]

    def mm_answer_count(self) -> int:
        return self.db.execute("SELECT count(*) FROM mm_answer").fetchone()[0]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `source ../akc/.venv/bin/activate && python -m unittest tests.test_mindmaze_store -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add quarry/store.py tests/test_mindmaze_store.py
git commit -m "feat(store): mm_question/mm_answer tables + idempotent insert"
```

---

### Task 4: `ingest_mindmaze` + build/CLI wiring

**Files:**
- Modify: `quarry/mindmaze.py` (add `discover_mindmaze_db`, `ingest_mindmaze`)
- Modify: `quarry/corpus.py` (call the pass from `build_corpus`)
- Modify: `quarry/cli.py` (add `--no-mindmaze` flag; print counts)
- Test: `tests/test_mindmaze_ingest.py`

**Interfaces:**
- Consumes: `parse_mindmaze_db`, `assign_areas`, `build_area_pools` (Tasks 1–2); `add_mindmaze_question` (Task 3).
- Produces:
  - `discover_mindmaze_db(src: str) -> list[Path]` — every `MINDMAZE.DB` under `src`.
  - `ingest_mindmaze(db_path: Path, store) -> dict` — parses, assigns areas (best-effort), stores; returns `{"questions": int, "answers": int, "with_area": int}`.
  - `build_corpus(..., with_mindmaze: bool = True)` runs the pass after the media pass and adds `mindmaze` stats into its `totals` dict.

- [ ] **Step 1: Write the failing test**

Create `tests/test_mindmaze_ingest.py`:

```python
import struct
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from quarry.mindmaze import ingest_mindmaze
from quarry.store import ContentStore
from tests.test_mindmaze import FIXTURE  # reuse the 2-record byte fixture


class IngestMindMazeTests(unittest.TestCase):
    def test_ingest_stores_questions_and_answers(self):
        with TemporaryDirectory() as d:
            db_file = Path(d) / "MINDMAZE.DB"
            db_file.write_bytes(FIXTURE)
            store = ContentStore(":memory:")
            stats = ingest_mindmaze(db_file, store)
            self.assertEqual(stats["questions"], 2)
            self.assertEqual(stats["answers"], 8)
            self.assertEqual(store.mm_question_count(), 2)
            self.assertEqual(store.mm_answer_count(), 8)

    def test_area_is_none_without_area_pools(self):
        with TemporaryDirectory() as d:
            db_file = Path(d) / "MINDMAZE.DB"
            db_file.write_bytes(FIXTURE)
            store = ContentStore(":memory:")  # no assets_dir -> no pools
            stats = ingest_mindmaze(db_file, store)
            self.assertEqual(stats["with_area"], 0)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `source ../akc/.venv/bin/activate && python -m unittest tests.test_mindmaze_ingest -v`
Expected: FAIL — `ImportError: cannot import name 'ingest_mindmaze'`.

- [ ] **Step 3: Write minimal implementation**

Append to `quarry/mindmaze.py`:

```python
import os
from pathlib import Path


def discover_mindmaze_db(src: str) -> list[Path]:
    found: list[Path] = []
    for dirpath, _dirs, files in os.walk(src):
        for fn in files:
            if fn.upper() == "MINDMAZE.DB":
                found.append(Path(dirpath) / fn)
    return sorted(found)


def ingest_mindmaze(db_path: Path, store) -> dict:
    data = Path(db_path).read_bytes()
    questions = parse_mindmaze_db(data)
    pools = build_area_pools(store)
    if pools:
        assign_areas(questions, pools)
    for qid, q in enumerate(questions):
        store.add_mindmaze_question(qid, q)
    store.commit()
    return {
        "questions": len(questions),
        "answers": sum(len(q.answers) for q in questions),
        "with_area": sum(1 for q in questions if q.area is not None),
    }
```

In `quarry/corpus.py`, add the import near the other package imports:

```python
from .mindmaze import discover_mindmaze_db, ingest_mindmaze
```

Add a `with_mindmaze: bool = True` parameter to `build_corpus`'s signature (alongside `with_media`), initialise `totals["mindmaze"] = {"questions": 0, "answers": 0, "with_area": 0}`, and after the media pass add:

```python
    if with_mindmaze:
        for db_path in discover_mindmaze_db(src):
            stats = ingest_mindmaze(db_path, store)
            totals["mindmaze"]["questions"] += stats["questions"]
            totals["mindmaze"]["answers"] += stats["answers"]
            totals["mindmaze"]["with_area"] += stats["with_area"]
            logger.warning("ingested %s: %s", db_path.name, stats)
```

In `quarry/cli.py`, in `cmd_build` pass `with_mindmaze=not args.no_mindmaze` into `build_corpus`, register the flag in the `build` subparser:

```python
    w.add_argument("--no-mindmaze", action="store_true", help="skip the MINDMAZE.DB question pass")
```

and add to the totals print in `cmd_build`:

```python
    print(
        f"  mindmaze: questions={totals['mindmaze']['questions']} "
        f"answers={totals['mindmaze']['answers']} "
        f"with_area={totals['mindmaze']['with_area']}"
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `source ../akc/.venv/bin/activate && python -m unittest tests.test_mindmaze_ingest tests.test_corpus -v`
Expected: PASS (new ingest tests pass; existing `test_corpus` still passes — the new `build_corpus` kwarg defaults preserve behaviour).

- [ ] **Step 5: Commit**

```bash
git add quarry/mindmaze.py quarry/corpus.py quarry/cli.py tests/test_mindmaze_ingest.py
git commit -m "feat(mindmaze): ingest pass + build_corpus/CLI wiring"
```

---

### Task 5: End-to-end validation against the real file

**Files:**
- Create: `tests/test_mindmaze_real.py` (skips cleanly when the source disc is absent)

**Interfaces:**
- Consumes: `parse_mindmaze_db` (Task 1); the real `MINDMAZE.DB` and the built `encarta.sqlite`.

This task proves the decoder against the actual data: exactly 8,020 four-answer records, the whole file consumed, and correct-answer refids that join the real `article` table.

- [ ] **Step 1: Write the test**

Create `tests/test_mindmaze_real.py`:

```python
import os
import sqlite3
import struct
import unittest
from pathlib import Path

from quarry.mindmaze import parse_mindmaze_db

DB = Path(os.path.expanduser("~/Downloads/encarta/EE/ENCARTA/MINDMAZE.DB"))
CORPUS = Path("build/encarta.sqlite")


@unittest.skipUnless(DB.exists(), "MINDMAZE.DB source disc not present")
class RealMindMazeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = DB.read_bytes()
        cls.qs = parse_mindmaze_db(cls.data)

    def test_exact_record_count_and_shape(self):
        self.assertEqual(len(self.qs), 8020)
        self.assertTrue(all(len(q.answers) == 4 for q in self.qs))

    def test_consumes_entire_file(self):
        # Re-walk to the final offset and assert nothing is left over.
        n = len(self.data)
        i = 0
        for q in self.qs:
            zero, clue_len = struct.unpack_from("<II", self.data, i)
            self.assertEqual(zero, 0)
            i += 8 + clue_len
            for a in q.answers:
                i += 1 + len(a.text.encode("cp1252")) + 6
        self.assertEqual(i, n)

    @unittest.skipUnless(CORPUS.exists(), "built encarta.sqlite not present")
    def test_correct_answers_join_articles(self):
        con = sqlite3.connect(CORPUS)
        sample = self.qs[:200]
        hits = 0
        for q in sample:
            rid = q.answers[0].article_refid
            if con.execute("SELECT 1 FROM article WHERE refid=?", (rid,)).fetchone():
                hits += 1
        # Correct-answer topics are real articles; expect the vast majority to join.
        self.assertGreater(hits, int(len(sample) * 0.9))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the validation**

Run: `source ../akc/.venv/bin/activate && python -m unittest tests.test_mindmaze_real -v`
Expected: PASS (or SKIP if the source disc / built DB is absent on this machine).

- [ ] **Step 3: Materialize into the real DB (manual verification, not committed)**

Run the real ingest against the existing corpus DB and eyeball the counts:

```bash
source ../akc/.venv/bin/activate
python -c "
from pathlib import Path
from quarry.store import ContentStore
from quarry.mindmaze import ingest_mindmaze
store = ContentStore('build/encarta.sqlite', assets_dir='build/assets')
print(ingest_mindmaze(Path('$HOME/Downloads/encarta/EE/ENCARTA/MINDMAZE.DB'), store))
print('questions', store.mm_question_count(), 'answers', store.mm_answer_count())
"
```
Expected: `{'questions': 8020, 'answers': 32080, 'with_area': ~6600}` and matching counts. (`with_area` ≈ 6,600 because ~95% of the 6,923 distinct correct-answer refids fall in an `Area*.lst` pool.)

- [ ] **Step 4: Commit**

```bash
git add tests/test_mindmaze_real.py
git commit -m "test(mindmaze): validate decode against the real MINDMAZE.DB (8020 questions)"
```

---

## Self-Review

**Spec coverage (against `reader/docs/superpowers/specs/2026-07-01-mindmaze-design.md` §2, §3):**
- `MINDMAZE.DB` walkable record parse → Task 1. ✓
- Answer→article refids join `article` → Task 1 fields + Task 5 join test. ✓
- `mm_question(id, area, clue, correct_answer_id)` / `mm_answer(...)` → Task 3. Deviation: dropped the redundant `mm_question.correct_answer_id` in favour of `mm_answer.is_correct` (ordinal 0), and added `mm_answer.ordinal` + `mm_answer.flag` for lossless decode. Documented here so a reader of the spec isn't surprised.
- `area` derived from `Area0-8.lst` pools → Task 2, wired in Task 4. Nullable + lowest-index primary match, reflecting the real 95%/multi-area coverage. ✓
- Runs as an added corpus build step → Task 4. ✓
- `MINDMAZE.IDX` treated as optional/not a hard dependency → not used here (the DB walks cleanly without it); left for a later phase if needed. ✓ (spec §2.2)

**Placeholder scan:** No TBD/TODO; every code step shows full content. ✓

**Type consistency:** `MindMazeQuestion` / `MindMazeAnswer` fields (`clue`, `answers`, `area`, `text`, `article_refid`, `is_correct`, `flag`) are used identically in Tasks 1→5; `add_mindmaze_question(qid, rec)` signature matches its callers in Task 4; `ingest_mindmaze` return keys (`questions`, `answers`, `with_area`) match both the tests and the corpus/CLI print code. ✓

**Out of scope (later phases):** `encarta_data` Dart query methods (Phase 2), `encarta_mindmaze` game core (Phase 3), the castle UI + sprite cyan→alpha keying (Phases 4–6). Each gets its own plan in `reader/docs/superpowers/plans/`.
