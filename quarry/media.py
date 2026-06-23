"""Parse a decoded Encarta DATA*.AKC media record into the article<->asset link.

This is the resolution that NEX-392 was missing (and that `catalog.parse_baggage_map`
stubbed out): the decoded ``<data>`` records carry the media->asset mapping and the
article->media reverse links directly, so no baggage.ecs / gid reversing is needed.

    <data refid="<media-id>" group="media" ticon="image" ...>
      <title/> <credit/> <caption/>
      <files>
        <image x="" y="">msencdata::baggage/<stem>.<ext></image>   # role = tag name
        ...
      </files>
      <reverse>
        <assoc refid="<article-id>" group="article" .../>           # which articles use it
      </reverse>
    </data>

The ``<files>`` baggage ``<stem>`` equals the ``asset.baggage_id`` produced by the
EIT asset ingest, so media rows join straight to the stored asset files.
"""
from __future__ import annotations

from dataclasses import dataclass
import re

_REFID_RE = re.compile(rb'<data\s+[^>]*\brefid="(\d+)"')
_GROUP_RE = re.compile(rb'<data\s+[^>]*\bgroup="([^"]*)"')
_TITLE_RE = re.compile(rb"<title>(.*?)</title>", re.S)
_CREDIT_RE = re.compile(rb"<credit>(.*?)</credit>", re.S)
_CAPTION_RE = re.compile(rb"<caption>(.*?)</caption>", re.S)
_FILES_RE = re.compile(rb"<files>(.*?)</files>", re.S)
_FILE_RE = re.compile(rb"<([a-zA-Z][a-zA-Z0-9]*)\b[^>]*>msencdata::baggage/([^.<]+)\.([^<]+)</\1>")
_REVERSE_RE = re.compile(rb"<reverse>(.*?)</reverse>", re.S)
_ASSOC_ARTICLE_RE = re.compile(rb'<assoc\b[^>]*\brefid="(\d+)"[^>]*\bgroup="article"')


def _text(pattern, data: bytes) -> str | None:
    m = pattern.search(data)
    return m.group(1).decode("utf-8", "replace").strip() if m else None


@dataclass(frozen=True)
class MediaFile:
    role: str          # ticon | picon | thumb | image | ...
    baggage_id: str    # joins to asset.baggage_id
    ext: str


@dataclass(frozen=True)
class DataRecord:
    refid: int
    group: str | None
    title: str | None
    credit: str | None
    caption: str | None
    files: list[MediaFile]
    article_refids: list[int]


def parse_data_record(xml: bytes) -> DataRecord:
    if isinstance(xml, str):
        xml = xml.encode("utf-8", "replace")
    m = _REFID_RE.search(xml)
    if not m:
        raise ValueError("no <data refid=...> root in record")
    refid = int(m.group(1))
    gm = _GROUP_RE.search(xml)
    group = gm.group(1).decode("utf-8", "replace") if gm else None

    files: list[MediaFile] = []
    fm = _FILES_RE.search(xml)
    if fm:
        for role, stem, ext in _FILE_RE.findall(fm.group(1)):
            files.append(MediaFile(role.decode(), stem.decode(), ext.decode().lower()))

    article_refids: list[int] = []
    seen: set[int] = set()
    rm = _REVERSE_RE.search(xml)
    if rm:
        for a in _ASSOC_ARTICLE_RE.findall(rm.group(1)):
            ref = int(a)
            if ref not in seen:
                seen.add(ref)
                article_refids.append(ref)

    return DataRecord(
        refid=refid,
        group=group,
        title=_text(_TITLE_RE, xml),
        credit=_text(_CREDIT_RE, xml),
        caption=_text(_CAPTION_RE, xml),
        files=files,
        article_refids=article_refids,
    )
