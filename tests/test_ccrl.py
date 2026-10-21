import unittest
import warnings
from urllib.parse import parse_qs, urlsplit

from collectors.ccrl import INDEX_URL, _is_code_url, collect


INDEX = """
<select name=family multiple>
<option>Stockfish</option><option>Bace</option>
<option>Stockfish Fork</option><option>4kc</option>
</select>
<table><tr><td class=name><a href="cgi/engine_details.cgi?eng=SF+19">SF 19</a>
</td></tr><tr><td class=name>
<a href="cgi/engine_details.cgi?eng=BACE+4.6">BACE 4.6</a></td></tr></table>
"""

DETAILS = """
<div class=details_container>
<table class=det_header><tr><td class=hname>
<a href="engine_details.cgi?eng=SF+19">SF 19</a></td></tr>
<tr><td class=engine_comment><table><tr><td>Authors: Team</td>
<td>Links: <a href="https://stockfishchess.org/">Homepage</a>,
<a href="https://github.com/official-stockfish/Stockfish">Homepage</a>,
<a href="https://example.org/sf-src.zip">Download</a></td></tr></table>
Based on <a href="https://github.com/someone/other">Other engine</a>.
</td></tr><tr><td class=engine_comment>
This is one of the 151 Stockfish versions we tested:
<a href="compare_engines.cgi?family=Stockfish">Compare them!</a>
</td></tr></table>
<table class=det_rows><tr><td>Opponent:
<a href="https://github.com/unrelated/engine">Source code</a>
</td></tr></table></div>
<div class=details_container><table class=det_header>
<tr><td class=hname><a href="engine_details.cgi?eng=BACE+4.6">BACE 4.6</a></td></tr>
<tr><td class=engine_comment><table><tr><td>Author: Someone</td>
<td>Link: <a href="../files/bace.zip">Source code</a></td></tr></table></td></tr>
<tr><td class=engine_comment>This is the only Bace version we tested.</td></tr>
</table></div>
"""


class CCRLTests(unittest.TestCase):
    def test_authoritative_families_and_scoped_source_links(self):
        calls = []

        def fetch(url, data=None):
            calls.append((url, data))
            if parse_qs(urlsplit(url).query).get("family") == ["Stockfish"]:
                return DETAILS
            return INDEX if url == INDEX_URL else DETAILS

        rows = collect(fetch)
        self.assertEqual([r["family"] for r in rows],
                         ["Stockfish", "Bace", "Stockfish Fork", "4kc"])
        self.assertEqual(len([c for c in calls if "/4040/" in c[0]]), 3)
        query = parse_qs(urlsplit(calls[1][0]).query)
        self.assertEqual(query["eng"], ["SF 19", "BACE 4.6"])
        self.assertEqual([x["url"] for x in rows[0]["code_urls"]], [
            "https://github.com/official-stockfish/Stockfish",
            "https://example.org/sf-src.zip",
        ])
        self.assertEqual(rows[1]["code_urls"][0]["url"],
                         "https://computerchess.org.uk/4040/files/bace.zip")
        self.assertEqual(rows[2]["code_urls"], [])
        self.assertEqual(rows[3]["code_urls"], [])
        for row in rows:
            self.assertEqual(row["label"], row["family"])
            self.assertEqual(parse_qs(urlsplit(row["url"]).query)["family"],
                             [row["family"]])
            for link in row["code_urls"]:
                self.assertTrue(link["evidence_url"].startswith(
                    "https://computerchess.org.uk/4040/cgi/engine_details.cgi?"))

    def test_enrichment_failure_keeps_families_and_warns(self):
        def fetch(url, data=None):
            if url == INDEX_URL:
                return INDEX
            raise OSError("unavailable")

        with self.assertWarnsRegex(RuntimeWarning, "unavailable"):
            rows = collect(fetch)
        self.assertEqual(len(rows), 4)
        self.assertTrue(all(not row["code_urls"] for row in rows))
        self.assertTrue(any("unavailable" in issue for issue in collect.last_warnings))
        self.assertTrue(all(row["warnings"] == collect.last_warnings for row in rows))

    def test_challenge_page_is_not_empty_success(self):
        with self.assertRaisesRegex(ValueError, "no family selector"):
            collect(lambda url: "<html>Access denied</html>")

    def test_implicit_option_endings_and_entity_decoding(self):
        html = '<select name=family><option>A &amp; B<option>Fork 2</select>'
        with warnings.catch_warnings(record=True):
            rows = collect(lambda url: html)
        self.assertEqual([r["family"] for r in rows], ["A & B", "Fork 2"])
        self.assertTrue(rows[0]["warnings"])

    def test_other_lists_add_families_and_merge_links(self):
        blitz = INDEX.replace("<option>4kc</option>", "<option>Blitzer</option>")

        def fetch(url, data=None):
            if url == INDEX_URL:
                return INDEX
            if url == "https://computerchess.org.uk/404/index.html":
                return blitz
            if url.endswith("/index.html"):
                raise OSError("list offline")
            return DETAILS

        with warnings.catch_warnings(record=True):
            rows = {r["family"]: r for r in collect(fetch)}
        self.assertEqual(rows["4kc"]["section"], "CCRL 40/15")
        self.assertEqual(rows["Bace"]["section"], "CCRL 40/15, CCRL Blitz")
        self.assertEqual(rows["Blitzer"]["section"], "CCRL Blitz")
        self.assertIn("/404/cgi/compare_engines.cgi", rows["Blitzer"]["url"])
        self.assertEqual(len(rows["Bace"]["code_urls"]), 2)
        self.assertTrue(any("list offline" in w for w in collect.last_warnings))

    def test_source_url_recognition(self):
        for url in [
            "https://github.com/user",
            "https://github.com/user/repo/releases",
            "https://example.com/engine",
            "https://sourceforge.net/projects/engine/",
            "javascript:alert(1)",
        ]:
            self.assertFalse(_is_code_url(url, "Homepage"), url)
        self.assertTrue(_is_code_url("https://gitlab.com/team/engine", "Homepage"))
        self.assertTrue(_is_code_url("https://example.com/code.zip", "Sources"))

    def test_explicit_fork_stays_separate_from_parent(self):
        fork = DETAILS.split('<div class=details_container>')[1]
        fork = '<div class=details_container>' + fork
        fork = fork.replace("SF+19", "ShashChess+Santiago")
        fork = fork.replace(
            '<a href="https://stockfishchess.org/">Homepage</a>',
            '<a href="https://github.com/amchess/ShashChess">'
            'Shashchess Homepage</a>',
        )

        def fetch(url, data=None):
            if url == INDEX_URL:
                return INDEX
            if parse_qs(urlsplit(url).query).get("family"):
                return fork
            return DETAILS

        rows = {r["family"]: r for r in collect(fetch)}
        self.assertEqual(rows["ShashChess"]["code_urls"], [{
            "url": "https://github.com/amchess/ShashChess",
            "evidence_url": "https://computerchess.org.uk/4040/cgi/"
                            "engine_details.cgi?print=Details&each_game=0&"
                            "eng=ShashChess+Santiago",
        }])
        self.assertNotIn("ShashChess", str(rows["Stockfish"]["code_urls"]))


if __name__ == "__main__":
    unittest.main()
