import os
import tempfile
import unittest

from quarry.assets import classify
from quarry.store import ContentStore


class ClassifyTests(unittest.TestCase):
    def test_classifies_by_extension(self):
        self.assertEqual(classify("2d648e25.jpg"), "image")
        self.assertEqual(classify("clip.wma"), "audio")
        self.assertEqual(classify("movie.wmv"), "video")
        self.assertEqual(classify("cap.smil"), "caption")
        self.assertEqual(classify("tune.mid"), "midi")
        self.assertEqual(classify("bib.xml"), "xml")
        self.assertEqual(classify("blob.bin"), "other")


class AssetStoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.store = ContentStore(
            os.path.join(self.tmp, "db.sqlite"),
            assets_dir=os.path.join(self.tmp, "assets"),
        )

    def _image_files(self):
        d = os.path.join(self.tmp, "assets", "image")
        return os.listdir(d) if os.path.isdir(d) else []

    def test_add_asset_writes_file_and_row(self):
        self.store.add_asset("2d648e25", b"\xff\xd8jpegdata", "image", ".jpg", source="MDSTD01.EIT")
        self.store.commit()
        self.assertEqual(self.store.asset_count(), 1)
        self.assertEqual(len(self._image_files()), 1)

    def test_identical_bytes_dedupe_to_one_physical_file(self):
        self.store.add_asset("a", b"SAME", "image", ".jpg", source="X")
        self.store.add_asset("b", b"SAME", "image", ".jpg", source="X")
        self.store.commit()
        self.assertEqual(self.store.asset_count(), 2)   # two logical assets
        self.assertEqual(len(self._image_files()), 1)   # one physical file

    def test_reingest_same_baggage_id_is_idempotent(self):
        for _ in range(3):
            self.store.add_asset("a", b"DATA", "image", ".jpg", source="X")
        self.store.commit()
        self.assertEqual(self.store.asset_count(), 1)
        self.assertEqual(len(self._image_files()), 1)


if __name__ == "__main__":
    unittest.main()
