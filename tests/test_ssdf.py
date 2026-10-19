import unittest
import warnings

from collectors.ssdf import LIST_URL, LONG_URL, _family, collect


def ranked_text(labels):
    lines = [
        "THE SSDF RATING LIST 2023-12-31 164540 games played by 440 computers",
        "Rating   +   - Games",
    ]
    for rank, label in enumerate(labels, 1):
        lines.append("%4d %-55s %4d  20 -19 600  50%% 3000" % (
            rank, label, 3000 - rank,
        ))
    return "\n".join(lines)


def index_page(ranks):
    rows = []
    for rank, label in ranks:
        rows.append(
            "<tr><td>%d</td><td><a href='nr%03d.htm'>%s</a></td></tr>"
            % (rank, rank, label)
        )
    return "<table>" + "".join(rows) + "</table>"


class SSDFTests(unittest.TestCase):
    def make_rows(self, labels):
        rank_links = [(rank, label) for rank, label in enumerate(labels, 1) if rank <= 2]
        pages = {LIST_URL: index_page(rank_links), LONG_URL: ranked_text(labels)}
        calls = []

        def fetch(url):
            calls.append(url)
            return pages[url]

        fetch.checked_at = {LONG_URL: "2026-10-18T00:00:00+00:00"}
        return collect(fetch), calls, fetch

    def test_full_ranked_list_provenance_without_detail_crawling(self):
        labels = [
            "Fritz 13 x64 Q6600 2.4 GHz",
            "Deep Fritz 13 Athlon 1.2 GHz",
            "Komodo 14 x64 1800X 3.6 GHz",
            "Dragon Komodo 3 x64 1800X 3.6 GHz",
            "Stockfish 16 x64 1800X 3.6 GHz",
            "Mephisto London 68030 33 MHz",
            "Mephisto London 68020 12 MHz",
            "Mephisto",
            "Revelation 2 A.E. Komodo 12.1 A7 1 GHz",
            "Millennium ChessGenius Excl. M7 300 MHz",
        ] + ["Arasan 23.4 x64 Q6600 2.4 GHz"] * 430
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            rows, calls, fetch = self.make_rows(labels)
        self.assertEqual(calls, [LIST_URL, LONG_URL])
        self.assertEqual(len(rows), 439)
        self.assertEqual([rows[index]["family"] for index in range(6)], [
            "Fritz", "Fritz", "Komodo", "Dragon", "Stockfish", "Mephisto London",
        ])
        self.assertEqual(rows[6]["family"], "Mephisto London")
        self.assertEqual(rows[7]["family"], "Komodo")
        self.assertEqual(rows[8]["family"], "ChessGenius")
        self.assertEqual(rows[0]["label"], labels[0])
        self.assertEqual(rows[0]["url"], LIST_URL)
        self.assertEqual(rows[0]["data_url"], LONG_URL)
        self.assertEqual(rows[0]["rank"], 1)
        self.assertEqual(rows[0]["section"], "SSDF rating list")
        self.assertEqual(rows[0]["detail_url"], "https://ssdf.bosjo.net/nr001.htm")
        self.assertNotIn("detail_url", next(row for row in rows if row["rank"] == 3))
        self.assertEqual(rows[0]["checked_at"], fetch.checked_at[LONG_URL])
        self.assertEqual(len(caught), 1)
        self.assertIn("excluded 1 hardware-only", str(caught[0].message))
        self.assertEqual(collect.last_warnings, [str(caught[0].message)])
        self.assertTrue(all(row["warnings"] == collect.last_warnings for row in rows))

    def test_normalization_retains_named_models_and_distinguishes_forks(self):
        cases = {
            "Stockfish 16 x64 1800X": "Stockfish",
            "Dragon Komodo 3 x64": "Dragon",
            "Komodo 14 x64": "Komodo",
            "Mephisto London 68030 33 MHz": "Mephisto London",
            "Mephisto Genius 2 486/50-66 MHz": "Mephisto Genius",
            "Millennium ChessGenius Excl. M7 300 MHz": "ChessGenius",
            "Revelation 2 Hiarcs 14.1 PXA320 800 MHz": "Hiarcs",
            "Fritz Athlon 1.2 GHz": "Fritz",
            "Kasparov SPARC 20 MHz": "Kasparov SPARC",
            "Palm Chess Genius 1.5 m515 16MB 42MHz": "ChessGenius",
            "Palm Hiarcs 9.5a/9.6 TungstenE 126 MHz": "Hiarcs",
            "TASC R30 v. 2.5 ARM6 30 MHz": "TASC R30",
            "Yace Paderborn Athlon 1.2 GHz": "Yace",
            "Zap!Chess Zanzibar Athlon 1.2 GHz": "Zap!Chess",
            "Pro Deo 2.1 YAT Athlon 1.2 GHz": "ProDeo",
            "MChess Pro 3.12 486/33 MHz": "MChess",
            "Rebel Century 4 Athlon 1.2 GHz": "Rebel",
            "Chessmaster King 3.5 x64 Q6600 2.4 GHz": "Chessmaster",
            "Mephisto Atlanta Brute F. 6502 4 MHz": "Mephisto Atlanta",
            "Mephisto MM 4 Turbo Kit 6502 5 MHz": "Mephisto MM 4",
        }
        for label, expected in cases.items():
            with self.subTest(label=label):
                self.assertEqual(_family(label), expected)

    def test_malformed_rankings_and_detail_links_fail_loudly(self):
        valid = index_page([(1, "Fritz 13"), (2, "Fritz 12")])
        with self.assertRaisesRegex(ValueError, "expected 440"):
            collect(lambda url: valid if url == LIST_URL else ranked_text(["Fritz 13"]))
        bad_links = index_page([(1, "Fritz 13")]).replace("nr001.htm", "nr002.htm")
        with self.assertRaisesRegex(ValueError, "does not match"):
            collect(lambda url: bad_links if url == LIST_URL else ranked_text(["Fritz 13"] * 440))

    def test_declared_count_can_change_without_changing_collector(self):
        text = ranked_text(["Fritz 13", "Stockfish 16"]).replace("440 computers", "2 computers")
        page = index_page([(1, "Fritz 13"), (2, "Stockfish 16")])
        rows = collect(lambda url: page if url == LIST_URL else text)
        self.assertEqual([row["family"] for row in rows], ["Fritz", "Stockfish"])

    def test_mismatched_cached_detail_label_is_warned_and_omitted(self):
        labels = ["Fritz 13"] * 440
        pages = {
            LIST_URL: index_page([(1, "Different engine")]),
            LONG_URL: ranked_text(labels),
        }

        def fetch(url):
            return pages[url]

        with self.assertWarnsRegex(RuntimeWarning, "detail-link labels"):
            rows = collect(fetch)
        self.assertNotIn("detail_url", rows[0])
        self.assertTrue(any("detail-link labels" in warning for warning in collect.last_warnings))

    def test_fetch_failure_propagates(self):
        def fetch(url):
            raise OSError("cached page unavailable")

        with self.assertRaisesRegex(OSError, "cached page unavailable"):
            collect(fetch)


if __name__ == "__main__":
    unittest.main()
