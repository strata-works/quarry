# Encarta article XML — tag vocabulary (NEX-393)

Renderer spec input. Built empirically from the **full decoded corpus** —
116,119 article bodies in `build/encarta.sqlite` (all four CONT* tiers), not the
bibliography sample. Survey script: a regex pass over `article.xml` (UTF-8);
counts are *articles using the tag* / *total occurrences*.

**32 distinct elements.** Bodies are UTF-8 (see NEX-394 — the "windows-1252"
note was wrong), `xml:space="preserve"`. No DTD; the structure below is observed,
not declared.

## Document shape

```
content                       (root; refid, revision)
└─ text                       (body wrapper; refid, xml:space="preserve")
   ├─ section                 (nestable; type = depth/kind)
   │  ├─ sectiontitle
   │  ├─ seca | secb | secc   (outline enumerators: "A", "B", …)
   │  └─ pkey | list | …      (block content)
   ├─ pkey                    (the dominant prose block)
   ├─ intro | headline | author | quote | example | list | rule
   └─ (inline runs inside blocks)
```

Article titles are **not** in the body — `inlinetitle` is an empty placeholder.
The renderer substitutes the resolved `article.title` (sourced from the
same-refid DATA* record; see NEX-394). 41,282 articles carry the placeholder.

## Elements

Class: **R**oot · **B**lock · **I**nline · **X**ref · **M**edia · **Meta**

| element | class | articles | occurs | attrs | notes / example |
|---|---|--:|--:|---|---|
| `content` | R | 116,119 | 116,119 | `refid`, `revision` | document root |
| `text` | R | 100,074 | 100,074 | `refid`, `xml:space` | body wrapper (`preserve`) |
| `pkey` | B | 100,071 | 703,294 | `id` | **the paragraph unit** — main prose block |
| `section` | B | 23,054 | 211,296 | `type`, `id` | nestable; `type` 6 (147k) / 4 (27k) / 7 (27k) / 5 (10k) = depth/kind |
| `sectiontitle` | B | 23,054 | 211,296 | — | heading for its `section` |
| `intro` | B | 2,695 | 2,706 | `id` | article lead/intro block |
| `headline` | B | 2,699 | 9,177 | `type`, `id` | feature/sidebar headlines; `type` 33/32/36/35/34 |
| `author` | B | 1,574 | 2,129 | `id` | byline (guest essays / features) |
| `list` | B | 3,296 | 8,567 | `type` | `type` 1 (bulleted, 7k) / 19 / 20 |
| `listitem` | B | 3,296 | 60,755 | — | child of `list` |
| `quote` | B | 739 | 2,600 | `type` | block quotation; `type` 30 / 27 |
| `example` | B | 221 | 1,103 | `id` | worked example (style/grammar entries) |
| `sec` | B | 5,661 | 58,346 | — | outline enumerator (e.g. `I`) |
| `seca` | B | 1,386 | 25,080 | — | outline enumerator level A (`A`) |
| `secb` | B | 437 | 5,541 | — | outline enumerator level B |
| `secc` | B | 53 | 659 | — | outline enumerator level C |
| `rule` | B | 2,688 | 3,402 | — | horizontal divider |
| `br` | B/I | 6,318 | 43,745 | — | line break (`<br></br>`) |
| `xref` | X | 33,843 | 225,168 | `type`, `RefID`, `paraID`, `URL`, `lang` | cross-reference / link — see below |
| `inlinebmp` | M | 310 | 2,887 | `type`, `id` | inline bitmap; `id` = `<NAME>.DIB`; `type` 28/27/30 |
| `inlinetitle` | Meta | 41,282 | 41,285 | — | **empty** placeholder → fill with `article.title` |
| `i` | I | 31,844 | 244,547 | — | italic |
| `b` | I | 5,824 | 18,798 | — | bold |
| `u` | I | 1 | 36 | — | underline (rare) |
| `smallcaps` | I | 4,724 | 14,641 | — | small caps |
| `sub` | I | 612 | 3,708 | — | subscript |
| `sup` | I | 689 | 2,819 | — | superscript |
| `fs` | I | 1,072 | 3,650 | `type` | special inline (fractions etc.); `type` 2 (numerator/denominator) |
| `fl` | I | 23 | 71 | — | rare inline format |
| `cq` | I | 3 | 16 | `para` | rare |
| `item` | I | 1 | 2 | `pos` | rare |
| `notation` | I | 1 | 1 | `type` | rare |

### `xref` link types (`type` attribute)

| type | count | meaning |
|--:|--:|---|
| 8 | 194,779 | **internal article link** — `RefID` → another article's refid |
| 17 | 15,238 | internal (subtype) |
| 15 | 6,786 | internal (subtype) |
| 10 | 2,766 | internal (subtype) |
| 11 | 1,983 | internal (subtype) |
| 9 | 1,857 | **external** — carries `URL` |
| 14 | 1,684 | internal (subtype) |
| 16 | 45 | internal (subtype) |

`RefID` resolves directly against `article.refid` (already captured in the
`xref` graph table). `paraID` (5,490) = deep-link to a paragraph within the
target. `URL` (1,857) = external web link. The exact semantic of subtypes
10/11/14/15/16/17 (e.g. media vs sidebar vs dictionary target) is the one open
refinement — they're all `RefID`-bearing, so they render as links regardless.

## Media in bodies

- **No `msencdata:` URLs** appear in any body (0/116,119). Article-level media
  (images/audio/video) is resolved out-of-band via the `article_media` →
  `media_file` → `asset` join (NEX-392), **not** inline in the XML.
- Inline bitmaps are the exception: `inlinebmp id="<NAME>.DIB"` embeds a `.DIB`
  image by filename. These resolve against the asset store by stem (note: `.DIB`
  assets are currently classified `kind=other`, not `image` — minor ETL fixup).

## Rendering: XSLT is embedded, not loose

Encarta renders via `msencxml.dll` applying an **XSLT** to this XML (the extracted
XML is *semantic source*, not final presentation). Confirmed:

- **0 `.xsl`/`.xslt` files** anywhere in the install tree.
- `MSENCXML.DLL` is present at `AREF/COMPNTS/MSENCXML.DLL` — the stylesheets are
  **embedded as PE resources** in that DLL, as NEX-393 suspected.

**Renderer recommendation: option (b) — treat the XML as semantic source and
design our own presentation.** The vocabulary is small (32 tags), clean, and
maps naturally to widgets (blocks → paragraphs/sections/lists, inline → spans,
`xref` → links, `inlinebmp`/`article_media` → images). Extracting and porting
the embedded XSL from a Windows DLL is high-effort and would only reproduce
2009-era desktop styling. Porting XSL (option a) is not worth it; we have enough
here to build a faithful renderer directly. (If exact fidelity is ever needed,
the XSL can be pulled from `MSENCXML.DLL`'s resources later.)

## Acceptance (NEX-393)

- [x] Every element: frequency, attributes, example, nesting, classification —
      over the decoded `CONT*.AKC` corpus (not just the bibliography sample).
- [x] XSL stylesheets located: none loose; embedded in `MSENCXML.DLL`
      (`AREF/COMPNTS/`) + transform note above, with a renderer-mapping decision.
