import struct
import tempfile
import unittest
from pathlib import Path

from quarry.mindmaze import MindMazeAnswer, MindMazeQuestion, assign_areas, build_area_pools, parse_mindmaze_db
from quarry.store import ContentStore


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


def mk_raw_record(clue_bytes, answers=()):
    """Like mk_record, but takes raw clue bytes (no .encode) so tests can embed
    bytes that are undefined in cp1252 (e.g. 0x81) without failing at
    construction time."""
    out = struct.pack("<I", 0) + struct.pack("<I", len(clue_bytes)) + clue_bytes
    for text, refid in answers:
        out += mk_answer(text, refid)
    return out


class ParseMindMazeDbUndefinedByteTests(unittest.TestCase):
    def test_undefined_cp1252_byte_in_clue_is_replaced_not_raised(self):
        # 0x81 is one of the 5 bytes cp1252 leaves undefined; strict decode
        # raises UnicodeDecodeError on it. Text is display-only, so a lossy
        # replacement is safe and must not abort the whole ingest pass.
        raw = mk_raw_record(b"Bad byte: \x81 here.")
        qs = parse_mindmaze_db(raw)
        self.assertEqual(len(qs), 1)
        self.assertEqual(qs[0].clue, "Bad byte: � here.")


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

    def test_empty_answers_area_is_none(self):
        q = MindMazeQuestion("clue", [])
        assign_areas([q], {0: {1}})
        self.assertIsNone(q.area)


class BuildAreaPoolsTests(unittest.TestCase):
    def test_assets_dir_none_returns_empty_dict(self):
        store = ContentStore(":memory:", assets_dir=None)
        self.addCleanup(store.db.close)
        pools = build_area_pools(store)
        self.assertEqual(pools, {})

    def test_missing_asset_rows_returns_empty_dict(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ContentStore(":memory:", assets_dir=tmpdir)
            self.addCleanup(store.db.close)
            pools = build_area_pools(store)
            self.assertEqual(pools, {})

    def test_missing_on_disk_file_skipped(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ContentStore(":memory:", assets_dir=tmpdir)
            self.addCleanup(store.db.close)
            # Insert an asset row but don't create the file
            store.db.execute(
                "INSERT INTO asset(baggage_id, hash, kind, ext, path, source) VALUES(?,?,?,?,?,?)",
                ("Area0", "abc123", "list", ".lst", "Area0.lst", "MINDMAZE.EIT"),
            )
            pools = build_area_pools(store)
            self.assertEqual(pools, {})

    def test_happy_path_reads_area_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ContentStore(":memory:", assets_dir=tmpdir)
            self.addCleanup(store.db.close)
            # Insert asset row and create the file
            store.db.execute(
                "INSERT INTO asset(baggage_id, hash, kind, ext, path, source) VALUES(?,?,?,?,?,?)",
                ("Area0", "abc123", "list", ".lst", "Area0.lst", "MINDMAZE.EIT"),
            )
            path = Path(tmpdir) / "Area0.lst"
            path.write_bytes(b"761574727\n761568751\n")
            pools = build_area_pools(store)
            self.assertEqual(pools, {0: {761574727, 761568751}})


if __name__ == "__main__":
    unittest.main()
