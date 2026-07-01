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
