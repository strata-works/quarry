import unittest

from quarry.content import parse_article


# A real decoded CONTSTD.AKC record (refid 1741500128, "Abdul-Aziz"), trimmed.
SAMPLE = (
    b'<content refid="1741500128" revision="100">'
    b'<text refid="1741500128" xml:space="preserve">'
    b'<section id="1" type="4"><sectiontitle>INTRODUCTION</sectiontitle>'
    b'<pkey id="1"><inlinetitle></inlinetitle> (1830-1876), 32nd sultan of the '
    b'<xref type="8" RefID="761553949">Ottoman Empire</xref> and 2nd sultan of the '
    b'<xref type="8" RefID="761588419">Tanzimat</xref> period.</pkey><sec>I</sec>'
    b'</section></text></content>'
)


class ParseArticleTests(unittest.TestCase):
    def test_extracts_refid(self):
        self.assertEqual(parse_article(SAMPLE).refid, 1741500128)

    def test_fts_text_has_prose_without_markup(self):
        rec = parse_article(SAMPLE)
        self.assertIn("Ottoman Empire", rec.text)
        self.assertIn("32nd sultan", rec.text)
        self.assertNotIn("<", rec.text)
        self.assertNotIn("sectiontitle", rec.text)

    def test_collects_xref_target_refids(self):
        rec = parse_article(SAMPLE)
        self.assertEqual(rec.xrefs, [761553949, 761588419])

    def test_preserves_raw_xml(self):
        rec = parse_article(SAMPLE)
        self.assertIn(b"<sectiontitle>INTRODUCTION", rec.xml)

    def test_fts_text_decodes_utf8(self):
        # Article bodies are UTF-8: U+2019 (') is bytes E2 80 99. The FTS text must
        # carry the real character, not windows-1252 mojibake.
        rec = parse_article(
            b'<content refid="1"><text>Bug\xe2\x80\x99s Life</text></content>'
        )
        self.assertIn("Bug’s Life", rec.text)


if __name__ == "__main__":
    unittest.main()
