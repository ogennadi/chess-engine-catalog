import unittest

from collectors import amateurschach as frank


def engine_row(name, links):
    cell = name + ", ".join(f'<a href="{url}">{label}</a>' for label, url in links)
    return "<tr><td>" + cell + "</td>" + "<td>-</td>" * 7 + "</tr>"


class ArchivedEngineTests(unittest.TestCase):
    def test_archive_links_are_unwrapped_without_fetching_repositories(self):
        url = "https://web.archive.org/web/20260212005235/https://github.com/owner/engine/releases?q=1"
        self.assertEqual(frank.code_url(url), "https://github.com/owner/engine")
        self.assertEqual(frank.code_url("/web/20260212005235/https://github.com/owner/engine"),
                         "https://github.com/owner/engine")
        self.assertIsNone(frank.code_url("https://github.com/owner"))
        self.assertIsNone(frank.code_url("https://example.org/homepage"))
        self.assertIsNone(frank.code_url("https://github.com/owner/owner.github.io"))

    def test_derivatives_and_multiple_engines_remain_separate(self):
        self.assertEqual(frank.row_families({"text": "Stockfish, Sting, TC-85591 *7"}), ["Sting"])
        self.assertEqual(frank.row_families({"text": "Stockfish, Crystal *7"}), ["Crystal"])
        self.assertEqual(frank.row_families({"text": "Gull, Roc, Roc2 *23"}), ["Roc", "Roc2"])
        self.assertEqual(frank.row_families({"text": "Clarity, \u00b2 Anura"}), ["Clarity", "Anura"])
        self.assertEqual(frank.row_families({"text": "Hakkapelitta, Firefather"}),
                         ["Hakkapeliitta NNUE"])

    def test_only_engine_table_rows_and_first_column_links_are_used(self):
        html = '<tr><td><a href="https://github.com/gui/gui">GUI</a></td></tr>'
        html += (
            '<tr><td><a href="https://github.com/example/engine/releases">Engine</a>, GitHub: D/L</td>'
            '<td>-</td><td><a href="https://github.com/author/other">Author</a></td>'
            '<td>26/02</td><td>2.0</td><td>-</td><td>-</td><td>OSS</td></tr>'
        )
        fetched = []

        def fetch(url):
            fetched.append(url)
            return html

        rows = frank.collect(fetch)
        self.assertEqual(fetched, [frank.SOURCE_URL])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["family"], "Engine")
        self.assertEqual(rows[0]["code_urls"], [{
            "url": "https://github.com/example/engine", "evidence_url": frank.SOURCE_URL,
        }])
        self.assertEqual(rows[0]["snapshot"], frank.SNAPSHOT)

    def test_networks_and_evaluation_dependencies_are_not_engine_code(self):
        html = engine_row("", [
            ("Engine", "https://github.com/author/engine"),
            ("net", "https://github.com/author/EngineNets"),
            ("Cerebrum v2.0", "https://github.com/other/evaluation"),
        ])
        rows = frank.collect(lambda url: html)
        self.assertEqual(len(rows[0]["code_urls"]), 1)

    def test_multiple_engine_code_links_stay_scoped(self):
        html = engine_row("", [
            ("Gull, ", "https://example.org/gull"),
            ("Roc", "https://github.com/TomHyer/Roc"),
            ("Roc2 *23", "https://github.com/TomHyer/Roc2"),
        ])
        rows = frank.collect(lambda url: html)
        self.assertEqual([r["family"] for r in rows], ["Roc", "Roc2"])
        self.assertEqual([r["code_urls"][0]["url"] for r in rows], [
            "https://github.com/TomHyer/Roc", "https://github.com/TomHyer/Roc2",
        ])

    def test_versions_and_footnotes_are_not_names(self):
        for text, expected in [
            ("\u00b2 CuckooChess, Dropbox", "CuckooChess"),
            ("Deep iCE", "iCE"),
            ("Stockfish, dev - page 81", "Stockfish"),
            ("Schooner D/L *18 *19", "Schooner"),
            ("Rykba, CB, web", "Rybka"),
            ("Petrel - tags", "Petrel"),
            ("Carp + Carp", "Carp"),
        ]:
            self.assertEqual(frank.row_families({"text": text}), [expected])
        with self.assertRaisesRegex(ValueError, "no recognized engine rows"):
            frank.collect(lambda url: "<html>Wayback error</html>")


if __name__ == "__main__":
    unittest.main()
