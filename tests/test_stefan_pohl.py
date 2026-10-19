import base64
import json
import unittest

from collectors.stefan_pohl import (
    BAE_README_URL, GAIA_README_URL, REBEL_README_URL, SLOW_CHESS_URL,
    SOURCE_URL, collect, enrich_source_links, family_name,
)


LIST = """*** Full UHO-Ratinglist updated: 2026/10/14 ***
     Program                     Celo    +    - Games    Score   Av.Op. Draws
   1 Stockfish 19 260905       : 3954    4    4 21000    69.1%   3811   48.7% (NEW)
   2 CS Tal 3.00 avx2          : 3500    5    5 14000    50.0%   3500   40.0%
*** Full EAS-Ratinglist updated: 2026/10/04 ***
Rank  EAS-Score  sacs    sacs   shorts  draws  moves  Engine/player
   1    750655  57.26%  45.49%  44.36%  05.00%   66   Cerberus 2722145081r9b
*** EAS single-statistics (6 categories, each with Top5 engines):
   2    750655  57.26%  45.49%  44.36%  05.00%   66   Fake 1.0
"""


class StefanPohlTests(unittest.TestCase):
    def test_family_names_preserve_forks_and_remove_versions_settings(self):
        for label, family in [
            ("Slow Chess 2.9 avx2", "Slow Chess"),
            ("CS Tal Extreme", "Chess System Tal"),
            ("CSTal 2.1 EAS", "Chess System Tal"),
            ("KomodoDragon 3.3 avx2", "Dragon"),
            ("Stockfish BAE 1.0", "Stockfish BAE"),
            ("Stockfish final HCE", "Stockfish"),
            ("Cerberus 2722145081r9b", "Cerberus"),
            ("Rebel Extreme 1.1", "Rebel"),
            ("Rebel EAS avx2", "Rebel"),
            ("Rodent V Tal", "Rodent"),
            ("Velvet 8.1.0 risky", "Velvet"),
            ("Coda 0.9.4 AI", "Coda"),
            ("4ku 5.0", "4ku"),
        ]:
            with self.subTest(label=label):
                self.assertEqual(family_name(label), family)

    def test_both_tables_keep_observed_labels_and_provenance(self):
        calls = []

        def fetch(url):
            calls.append(url)
            return LIST

        rows = collect(fetch)
        self.assertEqual(calls, [SOURCE_URL])
        self.assertEqual([row["family"] for row in rows], ["Stockfish", "Chess System Tal", "Cerberus"])
        self.assertEqual([row["section"] for row in rows], ["uho", "uho", "eas"])
        self.assertEqual([row["list_updated"] for row in rows],
                         ["2026-10-14", "2026-10-14", "2026-10-04"])
        self.assertTrue(all(row["code_urls"] == [] for row in rows))

    def test_invalid_or_incomplete_tables_fail_loudly(self):
        for text in [
            "Access denied", LIST.replace("   2 CS Tal", "   3 CS Tal"),
            LIST.replace("3954    4", "invalid    4"),
            LIST.split("*** Full EAS")[0],
        ]:
            with self.subTest(text=text[:50]), self.assertRaises(ValueError):
                collect(lambda url: text)
        with self.assertRaises(ValueError):
            family_name("Unrecognized named edition")

    def test_bae_is_a_verified_distinct_fork_with_source_evidence(self):
        text = LIST.replace("Stockfish 19 260905", "Stockfish BAE 1.0")

        def fetch(url):
            if url == SOURCE_URL:
                return text
            self.assertEqual(url, BAE_README_URL)
            return json.dumps({
                "content": base64.b64encode(b"Stockfish BAE is a fork with big array eval").decode(),
                "html_url": "https://github.com/tsoj/Stockfish-BAE/blob/master/Readme.md",
            })

        row = collect(fetch)[0]
        self.assertEqual(row["family"], "Stockfish BAE")
        self.assertEqual(row["code_urls"][0]["url"], "https://github.com/tsoj/Stockfish-BAE")

    def test_reviewed_sources_preserve_release_scope_and_evidence(self):
        rows = [
            {"family": name, "code_urls": []}
            for name in ["Gaia", "Rebel", "Slow Chess", "Cerberus", "Gaia"]
        ]
        calls = []

        def fetch(url):
            calls.append(url)
            if url == SLOW_CHESS_URL:
                return 'Very Old (and messy) Source Code: <a href="Slow296src.zip">2.96</a>'
            repository, content = {
                GAIA_README_URL: ("jromang/gaiachess", "Gaia 4 is a rewrite"),
                REBEL_README_URL: ("egh-s/Rebel-14.1.02-Chess-System-TAL-1", "Rebel-14.1.02"),
            }[url]
            return json.dumps({
                "content": base64.b64encode(content.encode()).decode(),
                "html_url": f"https://github.com/{repository}/blob/main/README.md",
            })

        enrich_source_links(rows, fetch)
        self.assertEqual(calls, [GAIA_README_URL, REBEL_README_URL, SLOW_CHESS_URL])
        self.assertEqual(rows[0]["code_urls"][0]["url"], "https://github.com/jromang/gaiachess")
        self.assertEqual(rows[1]["code_urls"][0]["source_release"], "14.1.02")
        self.assertIn("not verified source", rows[1]["code_urls"][0]["note"])
        self.assertEqual(rows[2]["code_urls"][0]["url"],
                         "https://www.3dkingdoms.com/chess/Slow296src.zip")
        self.assertIn("not source", rows[2]["code_urls"][0]["note"])
        self.assertEqual(rows[3]["code_urls"], [])
        self.assertEqual(rows[0]["code_urls"], rows[4]["code_urls"])

    def test_reviewed_source_identity_changes_fail_explicitly(self):
        for family, response in [
            ("Gaia", json.dumps({
                "content": base64.b64encode(b"Unrelated GAiA").decode(),
                "html_url": "https://github.com/jromang/gaiachess/blob/main/README.md",
            })),
            ("Rebel", json.dumps({
                "content": base64.b64encode(b"Rebel-14.1.02").decode(),
                "html_url": "https://github.com/unrelated/rebel/blob/main/README.md",
            })),
            ("Slow Chess", '<a href="SlowChess-2.9.zip">binary</a>'),
        ]:
            with self.subTest(family=family), self.assertRaises(ValueError):
                enrich_source_links([{"family": family, "code_urls": []}], lambda url: response)


if __name__ == "__main__":
    unittest.main()
