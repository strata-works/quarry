import os
import tempfile
import unittest

from quarry.corpus import discover_content_akc, discover_data_akc


class DiscoverContentAkcTests(unittest.TestCase):
    def _touch(self, root, relpath):
        path = os.path.join(root, relpath)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        open(path, "wb").close()
        return path

    def test_finds_content_families_recursively_and_skips_the_rest(self):
        with tempfile.TemporaryDirectory() as root:
            self._touch(root, "EE/ENCARTA/CONTSTD.AKC")
            self._touch(root, "EE/ENCARTA/CONTDLX.AKC")
            self._touch(root, "EE/KIDS/CONTKDC.AKC")     # nested edition
            self._touch(root, "EE/ENCARTA/CONTESK.AKC")  # source-gate, not content
            self._touch(root, "EE/ENCARTA/DATASTD.AKC")  # data, not article bodies
            self._touch(root, "EE/ENCARTA/MDSTD.EIT")    # EIT container, not AKC

            found = {os.path.basename(p).upper() for p in discover_content_akc(root)}
            self.assertEqual(found, {"CONTSTD.AKC", "CONTDLX.AKC", "CONTKDC.AKC"})

    def test_returns_empty_for_tree_without_content(self):
        with tempfile.TemporaryDirectory() as root:
            self._touch(root, "EE/ENCARTA/DATASTD.AKC")
            self.assertEqual(discover_content_akc(root), [])


class DiscoverDataAkcTests(unittest.TestCase):
    def _touch(self, root, relpath):
        path = os.path.join(root, relpath)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        open(path, "wb").close()

    def test_finds_data_families_and_skips_index_and_gate_files(self):
        with tempfile.TemporaryDirectory() as root:
            self._touch(root, "EE/ENCARTA/DATASTD.AKC")
            self._touch(root, "EE/ENCARTA/DATADLX.AKC")
            self._touch(root, "EE/KIDS/DATAKDC.AKC")
            self._touch(root, "EE/ENCARTA/DATAFSTD.AKC")  # DATAF* index family, not media
            self._touch(root, "EE/ENCARTA/DATAESK.AKC")   # source-gate, not media
            self._touch(root, "EE/ENCARTA/CONTSTD.AKC")   # content, not data
            found = {os.path.basename(p).upper() for p in discover_data_akc(root)}
            self.assertEqual(found, {"DATASTD.AKC", "DATADLX.AKC", "DATAKDC.AKC"})


if __name__ == "__main__":
    unittest.main()
