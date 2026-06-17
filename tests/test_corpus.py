import os
import tempfile
import unittest

from quarry.corpus import discover_content_akc


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


if __name__ == "__main__":
    unittest.main()
