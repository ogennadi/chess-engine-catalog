import unittest

from collectors.cegt import RATINGS_URLS, _family, collect


def rating_page(labels):
    rows = []
    for rank, label in enumerate(labels, 1):
        rows.append(
            "<tr><td>%d</td><td class=left><a class=t href='%d.html'>%s</a></td>"
            "<td>3000</td><td>10</td><td>10</td><td>100</td>"
            "<td>50%%</td><td>3000</td><td>50%%</td></tr>" % (rank, rank, label)
        )
    return (
        "<table><tr><th>no</th><th>Program</th><th>Elo</th><th>+</th><th>-</th>"
        "<th>Games</th><th>Score</th><th>Av.Op.</th><th>Draws</th></tr>"
        + "".join(rows)
        + "</table>"
    )


class CEGTTests(unittest.TestCase):
    def test_ranked_tables_keep_provenance_and_normalize_conservatively(self):
        pages = {
            RATINGS_URLS[0]: rating_page([
                "Stockfish 16 x64 8CPU",
                "Deep Fritz 13 x64 1CPU",
                "Komodo Dragon 3.0 x64 1CPU",
            ]),
            RATINGS_URLS[1]: rating_page([
                "Komodo 14 x64 1CPU",
                "Turbulence_v4 0.0.5",
                "4ku-3.0",
            ]),
        }

        def fetch(url):
            return pages[url]

        fetch.checked_at = {url: "2026-10-18T00:00:00+00:00" for url in pages}
        rows = collect(fetch)
        self.assertEqual([row["family"] for row in rows], [
            "Stockfish", "Fritz", "Dragon", "Komodo", "Turbulence", "4ku",
        ])
        self.assertEqual([row["url"] for row in rows[:3]], [RATINGS_URLS[0]] * 3)
        self.assertEqual([row["section"] for row in rows[3:]], ["CEGT 40/20"] * 3)
        self.assertEqual([row["rank"] for row in rows], [1, 2, 3, 1, 2, 3])
        self.assertEqual(rows[0]["label"], "Stockfish 16 x64 8CPU")
        self.assertEqual(rows[0]["detail_url"], RATINGS_URLS[0].rsplit("/", 1)[0] + "/1.html")
        self.assertEqual(rows[0]["checked_at"], fetch.checked_at[RATINGS_URLS[0]])
        self.assertTrue(all(row["code_urls"] == [] for row in rows))
        self.assertNotEqual(rows[2]["family"], rows[3]["family"])

    def test_reviewed_aliases_and_versions(self):
        examples = {
            "Deep Shredder 13 x64": "Shredder",
            "Clovis III 4CPU": "Clovis",
            "Capivara LK 0.08a11": "Capivara LK",
            "Capivara LK 0.09b02d x64": "Capivara LK",
            "BugChess2 v.1.6.2": "BugChess2",
            "4ku-5.1": "4ku",
            "4ku-3.0 x64 1CPU": "4ku",
            "Chiron B 03/03/06": "Chiron",
            "Chiron v0.8.1b10.61": "Chiron",
            "Dragon by Komodo 3": "Dragon",
            "Deep Sjeng WC2008 w32": "Sjeng",
            "Komodo TCEC w32": "Komodo",
            "Zappa Mexico II WD x64": "Zappa",
            "Slow Chess Blitz WV2.1": "Slow Chess",
            "Zurichess Geneva x64": "Zurichess",
            "CM10th Behemoth II 1CPU": "Chessmaster",
            "CM9000 Metallicus 1CPU": "Chessmaster",
            "Stockfish DD x64": "Stockfish",
            "Rebel Extreme 1.1 avx2": "Rebel",
            "Quanticade E0.9 x64": "Quanticade",
            "Glaurung 2-E/2-5 x64": "Glaurung",
            "LCZero 0310rc2CUDA t3d2767500": "Leela Chess",
            "RomiChess OW2a LD x64": "RomiChess",
            "Phalanx XXV UCI": "Phalanx",
            "Sting SF 28": "Sting",
            "z5 1.0": "Starzix",
            "FatFritz 1.0": "Fat Fritz",
        }
        for label, expected in examples.items():
            with self.subTest(label=label):
                self.assertEqual(_family(label), expected)

    def test_access_or_layout_errors_do_not_return_empty_success(self):
        with self.assertRaisesRegex(ValueError, "rating tables"):
            collect(lambda url: "<html>Access denied</html>")
        malformed = (
            "<table><tr><th>no</th><th>Program</th><th>Elo</th><th>+</th><th>-</th>"
            "<th>Games</th><th>Score</th><th>Av.Op.</th><th>Draws</th></tr>"
            "<tr><td>1</td><td>Stockfish 16</td></tr></table>"
        )
        with self.assertRaisesRegex(ValueError, "Malformed CEGT rating row"):
            collect(lambda url: malformed)

    def test_fetch_failure_propagates(self):
        def fetch(url):
            raise OSError("cached page unavailable")

        with self.assertRaisesRegex(OSError, "cached page unavailable"):
            collect(fetch)


if __name__ == "__main__":
    unittest.main()
