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
        try:
            sample = self.qs[:200]
            hits = 0
            for q in sample:
                rid = q.answers[0].article_refid
                if con.execute("SELECT 1 FROM article WHERE refid=?", (rid,)).fetchone():
                    hits += 1
            # Correct-answer topics are real articles; expect the vast majority to join.
            self.assertGreater(hits, int(len(sample) * 0.9))
        finally:
            con.close()


if __name__ == "__main__":
    unittest.main()
