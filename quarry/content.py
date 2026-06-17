"""Parse a decoded Encarta CONT*.AKC article record into a DB-ready row.

The decoder (``strata_akc_dump``) emits one XML record per article:

    <content refid="..." revision="..."><text refid="..." xml:space="preserve">
      <section>...<xref type="8" RefID="...">linked article</xref>...</section>
    </text></content>

Article titles are NOT in the body (``<inlinetitle>`` is empty) — they live in
the DATA*/CATALOG index, joined in a later stage. Here we capture the raw XML,
a tag-stripped full-text body for FTS5, and the ``<xref>`` related-article graph.
"""
from __future__ import annotations

from dataclasses import dataclass
import re

_REFID_RE = re.compile(rb'<content\s+refid="(\d+)"')
_XREF_RE = re.compile(rb'<xref\b[^>]*\bRefID="(\d+)"', re.I)
_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


@dataclass(frozen=True)
class ArticleRecord:
    refid: int
    xml: bytes
    text: str
    xrefs: list[int]


def parse_article(xml: bytes) -> ArticleRecord:
    if isinstance(xml, str):
        xml = xml.encode("windows-1252", "replace")
    m = _REFID_RE.search(xml)
    if not m:
        raise ValueError("no <content refid=...> root in record")
    refid = int(m.group(1))
    xrefs = [int(x) for x in _XREF_RE.findall(xml)]
    txt = xml.decode("windows-1252", "replace")
    txt = _WS_RE.sub(" ", _TAG_RE.sub(" ", txt)).strip()
    return ArticleRecord(refid=refid, xml=xml, text=txt, xrefs=xrefs)
