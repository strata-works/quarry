import os
import unittest

from quarry.ingest import ingest_akc
from quarry.store import ContentStore

AKC = os.environ.get("STRATA_AKC_CONTSTD")
MAP = os.environ.get("STRATA_AKC_CONTSTD_MAP")


@unittest.skipUnless(
    AKC and MAP,
    "set STRATA_AKC_CONTSTD and STRATA_AKC_CONTSTD_MAP to real CONTSTD.AKC + key map",
)
class IngestRealDataTests(unittest.TestCase):
    def test_ingest_loads_real_article_bodies(self):
        store = ContentStore(":memory:")
        stats = ingest_akc(AKC, MAP, store, limit=50, source="CONTSTD.AKC")
        store.commit()
        self.assertEqual(stats["ok"], 50)
        self.assertEqual(store.article_count(), 50)
        self.assertEqual(store.fts_count(), 50)
        self.assertGreater(store.xref_count(), 0)        # real bodies cross-link
        self.assertTrue(store.search("empire"))           # real prose is searchable

    def test_reingest_does_not_duplicate(self):
        store = ContentStore(":memory:")
        ingest_akc(AKC, MAP, store, limit=30, source="CONTSTD.AKC")
        ingest_akc(AKC, MAP, store, limit=30, source="CONTSTD.AKC")
        store.commit()
        self.assertEqual(store.article_count(), 30)
        self.assertEqual(store.fts_count(), 30)


if __name__ == "__main__":
    unittest.main()
