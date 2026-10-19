import json
import csv
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from collectors.wiki import INDEX_URL, attach, check


class WikiTests(unittest.TestCase):
    def fetcher(self, entries):
        def fetch(url):
            self.assertEqual(url, INDEX_URL)
            return json.dumps(entries)
        fetch.checked_at = {INDEX_URL: "2026-10-18T20:00:00+00:00"}
        return fetch

    def engines(self, *names):
        return [{"name": name, "aliases": []} for name in names]

    def test_one_bulk_request_checks_every_engine_and_excludes_namespaces(self):
        fetch = self.fetcher([
            ["Stockfish", "Stockfish"], ["Missing", "Category:Missing"],
            ["Stockfish", "File:Stockfish.png"],
        ])
        results = check(self.engines("Stockfish", "Missing"), fetch)
        self.assertEqual(results["engines"]["Stockfish"]["status"], "found")
        self.assertEqual(results["engines"]["Missing"]["status"], "not_found")
        self.assertEqual(results["main_namespace_pages"], 1)

    def test_engine_disambiguation_precedes_exact_nonengine_title(self):
        results = check(self.engines("Queen", "Fortress"), self.fetcher([
            ["Queen", "Queen"], ["Queen (engine)", "Queen_(engine)"],
            ["Fortress", "Fortress"], ["Fortress (Engine)", "Fortress_(Engine)"],
        ]))["engines"]
        self.assertEqual(results["Queen"]["title"], "Queen (engine)")
        self.assertEqual(results["Fortress"]["title"], "Fortress (Engine)")

    def test_distinct_historical_atlas_and_modern_spanish_atlas(self):
        results = check(self.engines("Atlas", "Atlas (1967)"), self.fetcher([
            ["Atlas", "Atlas"], ["Atlas (ESP)", "Atlas_(ESP)"],
        ]))["engines"]
        self.assertEqual(results["Atlas"]["title"], "Atlas (ESP)")
        self.assertEqual(results["Atlas (1967)"]["title"], "Atlas")

    def test_explicit_index_provenance_supplies_qualified_article_title(self):
        engines = self.engines("Example")
        engines[0]["provenance"] = [{
            "source": "wiki-engines", "page_title": "Example (engine)",
        }]
        result = check(engines, self.fetcher([
            ["Example", "Example"], ["Example (engine)", "Example_(engine)"],
        ]))["engines"]["Example"]
        self.assertEqual(result["title"], "Example (engine)")

    def test_similar_or_unrelated_names_are_not_false_positive_links(self):
        results = check(self.engines("Atlas", "Nu-chess", "LazySMP", "Caissa", "Ray"),
                        self.fetcher([
                            ["Atlas", "Atlas"], ["Nuchess", "Nuchess"],
                            ["Lazy SMP", "Lazy_SMP"], ["Kaissa", "Kaissa"], ["Rays", "Rays"],
                        ]))["engines"]
        self.assertEqual(results["Nu-chess"]["status"], "not_found")
        self.assertIsNone(results["Nu-chess"]["url"])
        self.assertIn("Filippo Marfe", results["Nu-chess"]["rejected_candidates"][0]["reason"])
        self.assertEqual(results["LazySMP"]["status"], "not_found")
        self.assertIsNone(results["LazySMP"]["url"])
        self.assertIn("parallel-search technique",
                      results["LazySMP"]["rejected_candidates"][0]["reason"])
        self.assertEqual(results["Atlas"]["status"], "not_found")
        self.assertIsNone(results["Atlas"]["url"])
        self.assertIn("1967", results["Atlas"]["rejected_candidates"][0]["reason"])
        self.assertEqual(results["Caissa"]["status"], "not_found")
        self.assertEqual(results["Ray"]["status"], "not_found")

    def test_achillees_rejection_persists_without_blocking_future_exact_page(self):
        engines = self.engines("Achillees")
        engines[0]["aliases"] = ["Achilles"]
        result = check(engines, self.fetcher([["Achilles", "Achilles"]]))["engines"]["Achillees"]
        self.assertEqual(result["status"], "not_found")
        self.assertIsNone(result["url"])
        rejection = result["rejected_candidates"][0]
        self.assertIn("Daniel Diaz", rejection["reason"])
        self.assertIn("Vladan Vuckovic", rejection["reason"])
        self.assertTrue(rejection["identity_evidence_url"])
        future = check(engines, self.fetcher([
            ["Achilles", "Achilles"], ["Achillees", "Achillees"],
        ]))["engines"]["Achillees"]
        self.assertEqual(future["status"], "found")
        self.assertEqual(future["title"], "Achillees")

    def test_albatros_is_not_the_historical_albatross(self):
        result = check(self.engines("Albatros"), self.fetcher([
            ["Albatross", "Albatross"],
        ]))["engines"]["Albatros"]
        self.assertEqual(result["status"], "not_found")
        self.assertIsNone(result["url"])
        rejection = result["rejected_candidates"][0]
        self.assertEqual(rejection["title"], "Albatross")
        self.assertIn("not independently verified", rejection["reason"])

    def test_aliases_case_unicode_and_ambiguous_catalog_aliases(self):
        engines = self.engines("E.T. Chess", "Plain", "Ambiguous", "Lower")
        engines[1]["aliases"] = ["Pr\u00e9dateur"]
        engines[2]["aliases"] = ["One", "Two"]
        results = check(engines, self.fetcher([
            ["E.T.Chess", "E.T.Chess"], ["Pr\u00e9dateur", "Pr\u00e9dateur"],
            ["One", "One"], ["Two", "Two"], ["LOWER", "LOWER"],
        ]))["engines"]
        self.assertEqual(results["E.T. Chess"]["status"], "found")
        self.assertIn("%C3%A9", results["Plain"]["url"])
        self.assertEqual(results["Ambiguous"]["status"], "needs_review")
        self.assertEqual(results["Lower"]["status"], "found")

    def test_preserves_results_and_flags_new_engines_unchecked(self):
        engines = self.engines("Stockfish")
        results = check(engines, self.fetcher([["Stockfish", "Stockfish"]]))
        catalog = {"engines": engines + self.engines("New engine")}
        attach(catalog, results)
        self.assertEqual(catalog["chessprogramming_wiki"]["found"], 1)
        self.assertEqual(catalog["chessprogramming_wiki"]["not_checked"], 1)

    def test_invalid_index_fails_explicitly(self):
        for entries in ([], [["Bad"]], [["Unsafe", "https://evil.example"]]):
            with self.subTest(entries=entries), self.assertRaises(ValueError):
                check(self.engines("Stockfish"), self.fetcher(entries))

    def test_case_collisions_use_exact_title_or_require_review(self):
        results = check(self.engines("Duplicate", "duplicate"), self.fetcher([
            ["Duplicate", "one"], ["DUPLICATE", "two"],
        ]))["engines"]
        self.assertEqual(results["Duplicate"]["url"], "https://chessprogramming.org/one")
        self.assertEqual(results["duplicate"]["status"], "needs_review")

    def test_already_escaped_index_paths_are_not_escaped_again(self):
        result = check(self.engines("Doctor?"), self.fetcher([
            ["Doctor?", "Doctor%253F"],
        ]))["engines"]["Doctor?"]
        self.assertEqual(result["url"], "https://chessprogramming.org/Doctor%253F")

    def test_engine_named_chess_does_not_match_the_game_article(self):
        result = check(self.engines("Chess"), self.fetcher([["Chess", "Chess"]]))["engines"]["Chess"]
        self.assertEqual(result["status"], "not_found")
        self.assertIsNone(result["url"])

    def test_publish_preserves_wiki_results_in_json_and_csv(self):
        from collect import publish

        engines = [{
            "name": "Stockfish", "aliases": [], "provenance": [], "source_code": [],
        }]
        results = check(engines, self.fetcher([["Stockfish", "Stockfish"]]))
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "data").mkdir()
            (root / "data" / "chessprogramming-wiki.json").write_text(
                json.dumps(results), encoding="utf-8",
            )
            with patch("collect.ROOT", root):
                publish({"engines": engines}, [])
            catalog = json.loads((root / "data" / "engines.json").read_text(encoding="utf-8"))
            self.assertEqual(catalog["engines"][0]["chessprogramming_wiki"]["status"], "found")
            with (root / "data" / "engines.csv").open(encoding="utf-8", newline="") as stream:
                row = next(csv.DictReader(stream))
            self.assertEqual(row["chessprogramming_wiki_url"], "https://chessprogramming.org/Stockfish")
            self.assertEqual(row["chessprogramming_wiki_status"], "found")


if __name__ == "__main__":
    unittest.main()
