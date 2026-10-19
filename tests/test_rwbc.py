import csv
import io
import unittest

from collectors.http import Fetcher
from collectors.rwbc import (
    CSV_URL, HEADERS, SOURCE_URL, collect, identity_report,
)


def engine(name, author="Example Author", source="yes", alias="", previous="", links=""):
    row = [""] * len(HEADERS)
    for column, value in {
        1: name, 2: author, 11: source, 16: alias, 17: previous,
        18: "free", 25: links,
    }.items():
        row[column] = value
    return row


def fixture(rows, count=None, padding=0):
    stream = io.StringIO(newline="")
    writer = csv.writer(stream)
    metadata = [""] * len(HEADERS)
    metadata[0] = "10/18/2026"
    metadata[3] = f"Alpha List (current count :: {len(rows) if count is None else count})"
    writer.writerow(metadata)
    writer.writerow(HEADERS)
    for rank, row in enumerate(rows + [[""] * len(HEADERS) for _ in range(padding)], 1):
        writer.writerow([str(rank), *row[1:]])
    return stream.getvalue()


class RWBCTests(unittest.TestCase):
    def test_extraction_preserves_full_evidence_and_fetch_time(self):
        original = engine(
            "My Engine 2", author="Surname First\nSecond Author", alias="MyEngine\n(Fruit)",
            previous="Older Engine 1.2", links=(
                "https://github.com/author/project/tree/main\n"
                "https://example.org/download.html"
            ),
        )
        text = fixture([original], padding=2)

        def fetch(url):
            self.assertEqual(url, CSV_URL)
            return text

        fetch.checked_at = {CSV_URL: "2026-10-19T01:17:00+00:00"}
        row, = collect(fetch)
        self.assertEqual(row["family"], "My Engine 2")
        self.assertEqual(row["authors"], original[2])
        self.assertEqual(row["alternate_names"], original[16])
        self.assertEqual(row["previous_names"], original[17])
        self.assertEqual(row["row"], ["1", *original[1:]])
        self.assertEqual(row["checked_at"], fetch.checked_at[CSV_URL])
        self.assertEqual(row["listing_url"], SOURCE_URL)
        self.assertEqual(row["declared_count"], 1)
        self.assertEqual(row["code_urls"], [{
            "url": "https://github.com/author/project", "evidence_url": CSV_URL,
        }])

    def test_sources_require_explicit_flag_and_project_or_source_archive(self):
        rows = [
            engine("Repo", links="https://github.com/owner/repo/releases/tag/v1"),
            engine("Closed", source="-", links="https://github.com/owner/closed"),
            engine("Partial", source="%", links="https://github.com/owner/partial"),
            engine("Homepage", links="https://example.org/\nhttps://example.org/engine.zip"),
            engine("Binary", links="https://example.org/engine-binaries.zip"),
            engine("Source", links="https://example.org/engine-src.tar.gz"),
            engine("Archive", links=(
                "https://web.archive.org/web/20260101000000/"
                "http://example.org/source/engine.zip"
            )),
            engine("Profile", links="https://github.com/owner\nhttps://gitlab.com/author"),
            engine("Attachment", links=(
                "https://github.com/user-attachments/files/123/engine_binaries.tar.gz"
            )),
            engine("NoSource", source="-", links="https://example.org/engine-source.zip"),
            engine("Gitlab", links="https://gitlab.com/group/subgroup/gitlab/-/tree/main"),
            engine("Forge", links="https://sourceforge.net/p/forge/code/HEAD/tree/"),
            engine("Maverick", links=(
                "https://example.org/Maverick%20Source%20%282015-10-28%29.zip"
            )),
            engine("Zchess2", links="https://example.org/QChessSource.zip"),
        ]
        result = collect(lambda url: fixture(rows))
        self.assertEqual([bool(row["code_urls"]) for row in result], [
            True, False, False, False, False, True, True, False, False, False, True, True,
            True, True,
        ])
        self.assertEqual(result[5]["code_urls"][0]["url"], "https://example.org/engine-src.tar.gz")
        self.assertEqual(result[6]["code_urls"][0]["url"], result[6]["links"][0])
        self.assertEqual(result[10]["code_urls"][0]["url"], "https://gitlab.com/group/subgroup/gitlab")
        self.assertEqual(result[11]["code_urls"][0]["url"], "https://sourceforge.net/projects/forge/")

    def test_unrelated_engines_dependencies_and_weights_are_not_source(self):
        rows = [
            engine("Stockfish#", alias="(Glaurung 2.1)", links=(
                "https://github.com/official-stockfish/Stockfish\n"
                "https://github.com/glinscott/fishtest/wiki/Regression-Tests\n"
                "https://github.com/owner/NNUE-Nets\n"
                "https://github.com/owner/chess-library\n"
                "https://github.com/owner/Cfish\n"
                "https://github.com/owner/asmFish"
            )),
            engine("Cfish", alias="(Stockfish)", links="https://github.com/owner/Cfish"),
            engine("asmFish", alias="(Stockfish)", links="https://github.com/owner/asmFish"),
            engine("CaffeinatedPawn", links=(
                "https://github.com/owner/CaffeinatedPawn\n"
                "https://github.com/bhlangonijr/chesslib"
            )),
        ]
        result = collect(lambda url: fixture(rows))
        self.assertEqual(result[0]["family"], "Stockfish")
        self.assertEqual(result[0]["original_name"], "Stockfish#")
        self.assertEqual(result[0]["code_urls"], [{
            "url": "https://github.com/official-stockfish/Stockfish", "evidence_url": CSV_URL,
        }])
        self.assertEqual(len(result[3]["code_urls"]), 1)
        self.assertEqual(len({row["family"] for row in result}), 4)

    def test_only_reviewed_release_families_merge_and_forks_remain_distinct(self):
        rows = [
            engine("Rodent#", alias="(Sungorus)"),
            engine("Rodent# II-IV", alias="(Sungorus)"),
            engine("Rodent# V", alias="(Sungorus)"),
            engine("Sungorus"),
            engine("Named Fork", alias="(Rodent)\n(Pesto PST)"),
            engine("Chess3"),
            engine("4ku"),
            engine("Betsabe II#"),
        ]
        result = collect(lambda url: fixture(rows))
        self.assertEqual([row["family"] for row in result], [
            "Rodent", "Rodent", "Rodent", "Sungorus", "Named Fork", "Chess3", "4ku", "Betsabe II",
        ])

    def test_exact_port_repository_preferred_to_ancestor_substring(self):
        row, = collect(lambda url: fixture([
            engine("WukongJS", previous="Wukong", links=(
                "https://github.com/author/wukong\n"
                "https://github.com/author/wukongJS"
            )),
        ]))
        self.assertEqual(row["code_urls"], [{
            "url": "https://github.com/author/wukongJS", "evidence_url": CSV_URL,
        }])

    def test_reports_alias_collisions_without_applying_them(self):
        rows = collect(lambda url: fixture([
            engine("Chess Cpp", alias="ChessDotCpp"),
            engine("Fork", alias="(Stockfish)"),
            engine("New", previous="Old"),
            engine("Old"),
            engine("Known Alias"),
        ]))
        report = identity_report(rows, ["chess.cpp", "Stockfish", "Canonical"], {
            "ChessDotCpp": "chess.cpp", "Known Alias": "Canonical",
        })
        self.assertEqual(rows[0]["family"], "Chess Cpp")
        self.assertEqual(report["rows"], 5)
        self.assertEqual(report["new_canonical_names"], ["Chess Cpp", "Fork", "New", "Old"])
        self.assertEqual(
            [(item["family"], item["suggested_canonical"]) for item in report["identity_conflicts"]],
            [("Chess Cpp", "chess.cpp"), ("New", "Old")],
        )
        self.assertFalse(any(item["family"] == "Fork" for item in report["mapping_suggestions"]))

    def test_malformed_headers_count_rank_and_empty_names_raise(self):
        good = fixture([engine("Example")])
        cases = {
            "header": good.replace("Web/Download", "Download"),
            "missing metadata": good.split("\n", 1)[1],
            "count mismatch": fixture([engine("Example")], count=2),
            "invalid count": good.replace("current count :: 1", "current count :: unknown"),
            "zero count": fixture([engine("Example")], count=0),
            "duplicate rank": fixture([engine("One"), engine("Two")]).replace("\n2,", "\n1,"),
            "invalid rank": good.replace("\n1,", "\nx,"),
            "empty name": fixture([engine("")]),
            "blank slot within declared count": fixture([engine("Example")], count=2, padding=1),
            "short row": good.rsplit(",", 1)[0],
        }
        for label, text in cases.items():
            with self.subTest(label=label), self.assertRaises(ValueError):
                collect(lambda url: text)

    def test_optional_cached_chronology_is_complete_and_offline(self):
        fetch = Fetcher(offline=True)
        try:
            fetch(CSV_URL)
        except FileNotFoundError:
            self.skipTest("RWBC chronology is not cached")
        rows = collect(fetch)
        self.assertEqual(len(rows), rows[0]["declared_count"])
        self.assertEqual([row["rank"] for row in rows], list(range(1, len(rows) + 1)))
        self.assertTrue(all(row["checked_at"] == fetch.checked_at[CSV_URL] for row in rows))
        self.assertTrue(all(row["original_name"] == row["row"][1] for row in rows))
        stockfish, = [row for row in rows if row["original_name"] == "Stockfish#"]
        self.assertTrue(stockfish["code_urls"])
        self.assertTrue(all(
            url["url"].rstrip("/").split("/")[-1].lower() == "stockfish"
            for url in stockfish["code_urls"]
        ))
        self.assertEqual(
            {row["family"] for row in rows if row["original_name"].startswith("Rodent#")},
            {"Rodent"},
        )
        self.assertTrue(any(row["family"] == "Sungorus" for row in rows))
        maverick, = [row for row in rows if row["family"] == "Maverick"]
        self.assertTrue(any("Source%20" in code["url"] for code in maverick["code_urls"]))


if __name__ == "__main__":
    unittest.main()
