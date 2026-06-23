import unittest

from quarry.content import parse_article
from quarry.store import ContentStore

SAMPLE = (
    b'<content refid="1741500128" revision="100">'
    b'<text refid="1741500128" xml:space="preserve">'
    b'<section><sectiontitle>INTRODUCTION</sectiontitle>'
    b'<pkey>sultan of the <xref type="8" RefID="761553949">Ottoman Empire</xref> '
    b'and the <xref type="8" RefID="761588419">Tanzimat</xref> period.</pkey>'
    b'</section></text></content>'
)


class ContentStoreTests(unittest.TestCase):
    def setUp(self):
        self.store = ContentStore(":memory:")
        self.rec = parse_article(SAMPLE)

    def test_add_article_populates_article_and_fts_and_xref(self):
        self.store.add_article(self.rec, source="CONTSTD.AKC")
        self.store.commit()
        self.assertEqual(self.store.article_count(), 1)
        self.assertEqual(self.store.fts_count(), 1)
        self.assertEqual(self.store.xref_count(), 2)

    def test_reingest_is_idempotent(self):
        # The prototype's bug: re-running duplicated every FTS row.
        for _ in range(3):
            self.store.add_article(self.rec, source="CONTSTD.AKC")
        self.store.commit()
        self.assertEqual(self.store.article_count(), 1)
        self.assertEqual(self.store.fts_count(), 1)
        self.assertEqual(self.store.xref_count(), 2)

    def test_full_text_search_finds_article(self):
        self.store.add_article(self.rec, source="CONTSTD.AKC")
        self.store.commit()
        self.assertEqual(self.store.search("Ottoman"), [1741500128])
        self.assertEqual(self.store.search("nonexistentword"), [])

    def test_fts_is_contentless_keeps_no_body_copy(self):
        # The body already lives in article.xml; the FTS must not store a second
        # copy (contentless fts5). Search still works; the column reads back NULL.
        self.store.add_article(self.rec, source="CONTSTD.AKC")
        self.store.commit()
        self.assertEqual(self.store.search("Ottoman"), [1741500128])
        body = self.store.db.execute(
            "SELECT body FROM article_fts WHERE rowid=1741500128"
        ).fetchone()[0]
        self.assertIsNone(body)


if __name__ == "__main__":
    unittest.main()
