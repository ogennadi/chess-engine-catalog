import unittest

from collectors.ubc import RATINGS_URL, _family, collect


class UBCTests(unittest.TestCase):
    def collect_html(self, html):
        requests = []

        def fetch(url, data=None):
            requests.append((url, data))
            return html

        result = collect(fetch)
        self.assertEqual(requests, [(RATINGS_URL, {"type": "type3"})])
        return result

    def test_ancestry_headings_do_not_merge_derivatives(self):
        records = self.collect_html("""
            <table><tr><td>Engines in <span>Glaurung</span> family<br>
            <tr><td><a id="eng@2">Stockfish&nbsp;16 <b>avx2</b> HCE</a></td></tr>
            <tr><td><a id="eng@3">Stockfish 15.1 bmi2</a></td></tr>
            <tr><td><a id="eng@5">asmFish 2019-10-16 popcnt</a></td></tr>
            <tr><td><a id="eng@6">Houdini 4 Pro A</a></td></tr>
            <tr><td><a id="eng@7">Glaurung 2.2</a></td></tr>
            </table>
        """)
        self.assertEqual(
            [r["family"] for r in records],
            ["Stockfish", "asmFish", "Houdini", "Glaurung"],
        )
        self.assertEqual(records[0]["label"], "Stockfish 16 avx2 HCE")
        for record in records:
            self.assertEqual(record["url"], RATINGS_URL)
            self.assertEqual(record["request_data"], {"type": "type3"})
            self.assertEqual(record["code_urls"], [])

    def test_names_versions_and_case_deduplication(self):
        names = [
            "100 Elo v1 v3", "4ku 5.1", "Dragon by Komodo avx2 HCE",
            "Slow Chess Classic 2.4", "Clockwork dev-20251226-bfeadec8 v3",
            "The Flying Dutchman 0.1.0", "Fruit Reloaded 15th anniversary",
            "Teki Random Mover", "pawnocchio 1.4.9", "Pawnocchio 1.9",
            "Rodent IV 0.30", "Clovis III JA", "QBBEngine",
        ]
        records = self.collect_html("<table>" + "".join(
            f'<tr><td><a id="eng@{i}">{name}</a></td></tr>'
            for i, name in enumerate(names)
        ) + "</table>")
        self.assertEqual([r["family"] for r in records], [
            "100 Elo", "4ku", "Dragon by Komodo", "Slow Chess",
            "Clockwork", "The Flying Dutchman", "Fruit Reloaded",
            "Teki Random Mover", "pawnocchio", "Rodent", "Clovis", "QBBEngine",
        ])

    def test_known_named_releases_and_builds(self):
        examples = {
            "Zurichess Nidwalden dev": "Zurichess",
            "Zurichess Neuchatel amd64": "Zurichess",
            "Zurichess Appenzeller amd64": "Zurichess",
            "Turbulence_v4 0.0.5 v3": "Turbulence",
            "Byte-Knight_010-665af7eGS": "Byte-Knight",
            "Byte-Knight 2.0.0": "Byte-Knight",
            "Hakkapeliitta TCEC v2": "Hakkapeliitta",
            "Deep Rybka 4.1 SSE42 x64": "Rybka",
            "Rybka 2.3.2a": "Rybka",
            "Deep Shredder 12": "Shredder",
            "Deep Onno 1-2-70": "Onno",
            "Deep Gandalf 7.0": "Gandalf",
            "Dirty Catpaw": "Dirty",
            "Dirty DUNA": "Dirty",
            "Zappa Mexico II": "Zappa",
            "Dorpsgek Eve's Temptation SSE4.2 01.04.2018": "Dorpsgek",
            "Slow Chess Classic 2.4 HCE": "Slow Chess",
            "Slow Chess Blitz 2.1": "Slow Chess",
        }
        for label, expected in examples.items():
            with self.subTest(label=label):
                self.assertEqual(_family(label), expected)
        records = self.collect_html("<table>" + "".join(
            f'<tr><td><a id="eng@{i}">{label}</a></td></tr>'
            for i, label in enumerate(examples)
        ) + "</table>")
        self.assertEqual(len(records), len(set(examples.values())))
        self.assertEqual(records[0]["label"], "Zurichess Nidwalden dev")

    def test_aliases_do_not_collapse_forks_or_numeric_names(self):
        examples = {
            "Luna 2.0.0 avx2": "Luna",
            "LunaChess 0.4.0 AB": "LunaChess",
            "Dragon by Komodo 3.3 avx2 HCE": "Dragon by Komodo",
            "Komodo 1.3 JA": "Komodo",
            "Stockfish 16": "Stockfish",
            "asmFish 2019-10-16": "asmFish",
            "Fruit Reloaded 15th anniversary": "Fruit Reloaded",
            "Fruit 05-11-03": "Fruit",
            "4ku 5.1": "4ku",
            "100 Elo v1": "100 Elo",
            "ice4 6": "ice4",
            "STRO4K 4.0": "STRO4K",
            "chess22k 1.10": "chess22k",
            "Nemo SP64o 1.0.1": "Nemo SP64o",
            "Turbulence_v5": "Turbulence_v5",
            "Deep Blue": "Deep Blue",
            "Dirty NewEngine": "Dirty NewEngine",
            "Byte-Knight_Chess": "Byte-Knight_Chess",
        }
        for label, expected in examples.items():
            with self.subTest(label=label):
                self.assertEqual(_family(label), expected)

    def test_only_explicit_code_links_and_correct_row_evidence(self):
        records = self.collect_html("""
            <a href="https://github.com/unrelated/repo">Unrelated</a>
            <table><tr><td><a id="eng@1">Example 1.0</a>
            <a href="https://example.org/">Home</a>
            <a href="https://github.com/author">Author</a>
            <a href="https://github.com/author/engine">Repository</a>
            <a href="https://github.com/author/engine/releases">Binaries</a>
            <a href="https://github.com/author/engine/issues/1">Issue</a>
            <a href="data/example.zip">Download</a>
            <a href="data/example-src.tar.gz">Download</a>
            <a href="/data/source.zip?rev=1&amp;x=2">Source code</a>
            <a href="javascript:alert(1)">Source</a></td></tr>
            <tr><td><a id="eng@2">Example 2.0</a>
            <a href="https://github.com/author/engine">Repository</a>
            <a href="https://codeberg.org/author/engine">Code</a></td></tr>
            <tr><td><a id="eng@3">Other 1</a></td></tr></table>
        """)
        self.assertEqual([c["url"] for c in records[0]["code_urls"]], [
            "https://github.com/author/engine",
            "https://e4e6.com/data/example-src.tar.gz",
            "https://e4e6.com/data/source.zip?rev=1&x=2",
            "https://codeberg.org/author/engine",
        ])
        self.assertTrue(all(
            c["evidence_url"] == RATINGS_URL for c in records[0]["code_urls"]
        ))
        self.assertEqual(records[1]["code_urls"], [])

    def test_empty_or_non_rating_html_fails_loudly(self):
        for html in ("", "<html>Service unavailable</html>",
                     '<script><a id="eng@1">Fake 1</a></script>'):
            with self.subTest(html=html), self.assertRaises(ValueError):
                collect(lambda url, data=None: html)

    def test_fetch_failure_propagates(self):
        def fetch(url, data=None):
            raise OSError("offline")

        with self.assertRaisesRegex(OSError, "offline"):
            collect(fetch)


if __name__ == "__main__":
    unittest.main()
