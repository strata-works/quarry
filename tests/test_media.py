import unittest

from quarry.media import parse_data_record

# A real decoded DATASTD.AKC media record (refid 102613117, "Traffic in Quito"), trimmed.
SAMPLE = (
    b'<data refid="102613117" group="media" ticon="image" origin="EE" InVB="1" revision="105">'
    b'<title>Traffic in Quito, Ecuador</title>'
    b'<credit>K. Rodgers/Hutchison Library</credit>'
    b'<caption>Many of Ecuador\x92s cities ...</caption>'
    b'<files>'
    b'<ticon x="16" y="16">msencdata::baggage/transparent.gif</ticon>'
    b'<picon x="216" y="192">msencdata::baggage/t062836a.jsm</picon>'
    b'<thumb x="64" y="64">msencdata::baggage/t062836a.jtn</thumb>'
    b'<image x="324" y="476">msencdata::baggage/t062836a.jpg</image>'
    b'</files>'
    b'<reverse>'
    b'<assoc refid="761563377" group="article" sec="1" sequence="15"/>'
    b'<assoc refid="761563377" group="article" appears="102613117" sequence="15"/>'
    b'<assoc refid="761565312" group="article" sec="36" sequence="1"/>'
    b'</reverse>'
    b'</data>'
)


class ParseDataRecordTests(unittest.TestCase):
    def test_extracts_media_refid_and_metadata(self):
        rec = parse_data_record(SAMPLE)
        self.assertEqual(rec.refid, 102613117)
        self.assertEqual(rec.group, "media")
        self.assertEqual(rec.title, "Traffic in Quito, Ecuador")
        self.assertEqual(rec.credit, "K. Rodgers/Hutchison Library")

    def test_files_give_role_baggage_stem_and_ext(self):
        files = {f.role: (f.baggage_id, f.ext) for f in parse_data_record(SAMPLE).files}
        self.assertEqual(files["image"], ("t062836a", "jpg"))
        self.assertEqual(files["picon"], ("t062836a", "jsm"))
        self.assertEqual(files["thumb"], ("t062836a", "jtn"))
        self.assertEqual(files["ticon"], ("transparent", "gif"))

    def test_reverse_assoc_gives_deduped_article_refids(self):
        # the article -> media link; 761563377 appears twice, must dedupe
        self.assertEqual(parse_data_record(SAMPLE).article_refids, [761563377, 761565312])


if __name__ == "__main__":
    unittest.main()
