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
            store.db.close()

    def test_area_is_none_without_area_pools(self):
        with TemporaryDirectory() as d:
            db_file = Path(d) / "MINDMAZE.DB"
            db_file.write_bytes(FIXTURE)
            store = ContentStore(":memory:")  # no assets_dir -> no pools
            stats = ingest_mindmaze(db_file, store)
            self.assertEqual(stats["with_area"], 0)
            store.db.close()


if __name__ == "__main__":
    unittest.main()
