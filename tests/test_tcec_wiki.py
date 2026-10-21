import unittest

from collectors.tcec_wiki import PAGE_URL, STATUS_URL, collect, parse, parse_status


PAGE = """
<table class="wikitable"><tr><th>Contents</th></tr></table>
<table class="wikitable sortable">
<tr><th> Engine </th><th> Basic Type </th><th> Programming language </th><th> Author </th>
<th> Twitch chat </th><th> Discord</th></tr>
<tr><td> <a rel="nofollow" class="external text" href="https://github.com/Diazepawn/M4sseur">M4sseur</a>** </td>
<td> Classical on CPU </td><td> C++20 </td><td> Maik Guntermann </td><td> x </td><td></td></tr>
<tr><td> <a href="https://moonfish.neocities.org/">moonfish</a> </td>
<td> Classical on CPU </td><td> C </td><td> </td><td></td><td></td></tr>
<tr><td> <a href="https://www.chessprogramming.org/A0lite">A0lite</a> </td>
<td> NN on GPU </td><td> Python </td><td> Dietrich Kappe </td><td></td><td></td></tr>
<tr><td> Allie... (engine) </td><td> NN on GPU </td><td> C++ </td><td> Adam Treat </td><td></td><td></td></tr>
<tr><td> ...Stein (network) </td><td> NN on GPU </td><td> </td><td> Mark Jordan </td><td></td><td></td></tr>
<tr><td> Enrique S&#225;nchez </td><td> Classical on CPU </td><td> C++ </td><td> </td><td></td><td></td></tr>
</table>
<table><tr><th>Engine</th><th>S1</th></tr><tr><td>KomodoMCTS</td><td>99</td></tr></table>
"""

STATUS = """
<ul><li>not content</li></ul>
<div id="mw-content-text">
<h2><span class="mw-headline" id="Contents">Contents</span></h2><ul><li><b>Skip</b></li></ul>
<h3><span class="mw-headline" id="S30_Entrance_League">S30 Entrance League</span></h3>
<ul><li><b>Stoofvlees II d10</b> (S29 L2 12th) Updated for S28 Cup 15</li>
<li>2 engines from S30 DivP</li></ul>
<h3><span class="mw-headline" id="S31_4K_VIII">S31 4K VIII</span></h3>
<ul><li><b>molly e317a0c7b8</b> (S30 4K VII 6th)</li></ul>
<h2><span class="mw-headline" id="Not_playing.2C_invite_if_author_contacts">Not playing, invite if author contacts</span></h2>
<ul><li><b>Soul</b></li></ul>
<h2><span class="mw-headline" id="See_also">See also</span></h2>
<ul><li><b>Engines and authors</b></li></ul>
</div>
"""


class TcecWikiTests(unittest.TestCase):
    def test_engine_table_rows_become_families(self):
        rows = parse(PAGE)
        self.assertEqual(
            [row["family"] for row in rows],
            ["M4sseur", "moonfish", "A0lite", "Allie", "Stein", "Enrique Sánchez"],
        )
        self.assertEqual(rows[0]["label"], "M4sseur**")
        self.assertEqual(rows[0]["author"], "Maik Guntermann")
        self.assertEqual(
            rows[0]["comment"], "Classical on CPU; C++20; 4k event engine (fits in 4096 bytes)"
        )
        self.assertNotIn("author", rows[1])

    def test_repository_and_reviewed_homepage_links_are_source(self):
        rows = parse(PAGE)
        self.assertEqual(rows[0]["code_urls"], [
            {"url": "https://github.com/Diazepawn/M4sseur", "evidence_url": PAGE_URL},
        ])
        self.assertEqual(rows[1]["code_urls"], [{
            "url": "https://git.sr.ht/~zamfofex/moonfish",
            "evidence_url": "https://moonfish.neocities.org",
        }])
        self.assertEqual(rows[2]["code_urls"], [])
        self.assertEqual(rows[2]["project_url"], "https://www.chessprogramming.org/A0lite")

    def test_missing_engine_table_is_an_error(self):
        with self.assertRaises(ValueError):
            parse("<table><tr><th>Engine</th></tr></table>")

    def test_status_list_rows_include_not_playing_engines(self):
        rows = parse_status(STATUS)
        self.assertEqual(
            [(row["family"], row["section"]) for row in rows],
            [
                ("Stoofvlees", "S30 Entrance League"),
                ("molly", "S31 4K VIII"),
                ("Soul", "Not playing, invite if author contacts"),
            ],
        )
        self.assertEqual(rows[0]["label"], "Stoofvlees II d10")
        self.assertEqual(rows[0]["comment"], "(S29 L2 12th) Updated for S28 Cup 15")
        self.assertEqual(rows[0]["url"], STATUS_URL + "#S30_Entrance_League")
        self.assertEqual(rows[0]["code_urls"], [])
        self.assertNotIn("comment", rows[2])
        self.assertEqual(rows[2]["code_urls"], [{
            "url": "https://github.com/Aethdv/Soul",
            "evidence_url": "https://wiki.chessdom.org/Soul_questionnaire_20260620",
        }])

    def test_collect_reads_both_pages(self):
        pages = {PAGE_URL: PAGE, STATUS_URL: STATUS}
        rows = collect(pages.get)
        self.assertEqual({row["url"].split("#")[0] for row in rows}, {PAGE_URL, STATUS_URL})


if __name__ == "__main__":
    unittest.main()
