import os
import tempfile
import unittest

from quarry.assets import ingest_eit
from quarry.corpus import discover_eit
from quarry.store import ContentStore


class DiscoverEitTests(unittest.TestCase):
    def _touch(self, root, rel):
        p = os.path.join(root, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        open(p, "wb").close()
        return p

    def test_finds_eit_itr_ste_recursively(self):
        with tempfile.TemporaryDirectory() as root:
            self._touch(root, "CONTENT/MDSTD.EIT")
            self._touch(root, "EE/ENCARTA/CATALOG.STE")
            self._touch(root, "CONTENT/x.ITR")
            self._touch(root, "EE/ENCARTA/CONTSTD.AKC")   # not a container
            self._touch(root, "readme.txt")
            found = {os.path.basename(p).upper() for p in discover_eit(root)}
            self.assertEqual(found, {"MDSTD.EIT", "CATALOG.STE", "X.ITR"})


EIT = os.environ.get("STRATA_EIT_MDSTD")


@unittest.skipUnless(EIT, "set STRATA_EIT_MDSTD to a real MDSTD.EIT (needs STRATA_USE_PY_LZX=1)")
class IngestEitRealTests(unittest.TestCase):
    def test_ingests_baggage_assets_from_real_container(self):
        tmp = tempfile.mkdtemp()
        store = ContentStore(
            os.path.join(tmp, "db.sqlite"), assets_dir=os.path.join(tmp, "assets")
        )
        stats = ingest_eit(EIT, store, source="MDSTD.EIT")
        store.commit()
        self.assertGreater(stats["ok"], 0)
        self.assertGreater(store.asset_count(), 0)


if __name__ == "__main__":
    unittest.main()
