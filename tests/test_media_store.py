import os
import tempfile
import unittest

from quarry.media import parse_data_record
from quarry.store import ContentStore
from tests.test_media import SAMPLE


class MediaStoreTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.mkdtemp()
        self.store = ContentStore(
            os.path.join(tmp, "db.sqlite"), assets_dir=os.path.join(tmp, "assets")
        )
        self.rec = parse_data_record(SAMPLE)

    def test_add_media_record_populates_three_tables(self):
        self.store.add_media_record(self.rec, source="DATASTD.AKC")
        self.store.commit()
        self.assertEqual(self.store.media_count(), 1)
        self.assertEqual(self.store.media_file_count(), 4)        # ticon/picon/thumb/image
        self.assertEqual(self.store.article_media_count(), 2)     # two distinct articles

    def test_reingest_is_idempotent(self):
        for _ in range(3):
            self.store.add_media_record(self.rec, source="DATASTD.AKC")
        self.store.commit()
        self.assertEqual(self.store.media_count(), 1)
        self.assertEqual(self.store.media_file_count(), 4)
        self.assertEqual(self.store.article_media_count(), 2)

    def test_backfill_article_titles_from_media(self):
        # An article's own DATA*-sourced media record (same refid) carries its title.
        from quarry.content import parse_article
        art = parse_article(b'<content refid="102613117"><text>body</text></content>')
        self.store.add_article(art, source="CONTSTD.AKC")
        self.store.add_media_record(self.rec, source="DATASTD.AKC")  # title "Traffic in Quito, Ecuador"
        self.store.commit()
        updated = self.store.backfill_article_titles()
        self.store.commit()
        title = self.store.db.execute(
            "SELECT title FROM article WHERE refid=102613117"
        ).fetchone()[0]
        self.assertEqual(title, "Traffic in Quito, Ecuador")
        self.assertEqual(updated, 1)

    def test_assets_for_article_joins_media_file_to_asset(self):
        # asset present for the image stem -> resolving an article's media yields it
        self.store.add_asset("t062836a", b"\xff\xd8jpg", "image", ".jpg", source="MDSTD01.EIT")
        self.store.add_media_record(self.rec, source="DATASTD.AKC")
        self.store.commit()
        rows = self.store.assets_for_article(761563377)
        # the 'image' role for media 102613117 resolves to the stored asset path
        self.assertTrue(any(r["baggage_id"] == "t062836a" and r["role"] == "image"
                            and r["path"] for r in rows))


if __name__ == "__main__":
    unittest.main()
