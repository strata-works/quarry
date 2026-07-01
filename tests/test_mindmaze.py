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
