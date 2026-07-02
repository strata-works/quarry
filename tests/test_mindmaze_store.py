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

    def tearDown(self):
        self.store.db.close()

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

    def test_mm_answer_has_indexes_on_join_keys(self):
        names = {
            row[0] for row in self.store.db.execute(
                "SELECT name FROM sqlite_master WHERE type='index'"
            )
        }
        self.assertIn("idx_mm_answer_question", names)
        self.assertIn("idx_mm_answer_article", names)


if __name__ == "__main__":
    unittest.main()
