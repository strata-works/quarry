import os
import tempfile
import unittest

from quarry.store import ContentStore


class AddAssetRowTests(unittest.TestCase):
    """The parent (single SQLite writer) inserts rows produced by worker processes;
    workers already wrote the files, so this is DB-only (no file I/O)."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.store = ContentStore(
            os.path.join(self.tmp, "db.sqlite"), assets_dir=os.path.join(self.tmp, "assets")
        )

    def test_add_asset_row_inserts_without_touching_files(self):
        self.store.add_asset_row("t01", "deadbeef", "image", ".jpg", "image/deadbeef.jpg", "MDSTD01.EIT")
        self.store.commit()
        self.assertEqual(self.store.asset_count(), 1)
        # no file written by the DB-only path
        self.assertFalse(os.path.exists(os.path.join(self.tmp, "assets", "image", "deadbeef.jpg")))

    def test_add_asset_row_is_idempotent_on_baggage_id(self):
        for _ in range(3):
            self.store.add_asset_row("t01", "deadbeef", "image", ".jpg", "image/deadbeef.jpg", "X")
        self.store.commit()
        self.assertEqual(self.store.asset_count(), 1)


if __name__ == "__main__":
    unittest.main()
