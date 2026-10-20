import csv
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError

from collect import merge, publish, unused_not_source, unused_source_aliases
from collectors.http import Fetcher
from collectors.lichess import collect, repository_links


class MergeTests(unittest.TestCase):
    def observation(self, family, source):
        return {
            "family": family, "source": source, "label": family,
            "url": "https://example.org/" + source, "code_urls": [],
        }

    def test_merges_case_and_reviewed_aliases_preserving_provenance(self):
        engines = merge([
            self.observation("Stockfish", "one"),
            self.observation("STOCKFISH", "two"),
            self.observation("SF", "three"),
        ], {"SF": "Stockfish"})
        self.assertEqual(len(engines), 1)
        self.assertEqual(len(engines[0]["provenance"]), 3)
        self.assertIn("SF", engines[0]["aliases"])

    def test_does_not_merge_forks_or_numeric_names(self):
        names = ["Stockfish", "asmFish", "Chess22k", "Chess", "C++", "C"]
        self.assertEqual(len(merge([self.observation(n, "x") for n in names], {})), 6)

    def test_code_links_keep_evidence(self):
        row = self.observation("A", "one")
        row["code_urls"] = [{"url": "https://github.com/a/a", "evidence_url": row["url"]}]
        self.assertEqual(merge([row, row], {})[0]["source_code"], [
            {**row["code_urls"][0], "source": "one"}
        ])

    def test_source_aliases_split_homonyms_before_name_aliases(self):
        rules = [
            {"sources": ["ccrl"], "family": "Joker", "target": "Joker NL",
             "evidence_url": "https://example.org/joker"},
            {"sources": ["cegt"], "family": "Dragon", "label_pattern": r"^Dragon 4\.6\b",
             "target": "Dragon FR", "evidence_url": "https://example.org/dragon"},
        ]
        komodo = {**self.observation("Dragon", "cegt"), "label": "Komodo Dragon 3.3"}
        lucas = {**self.observation("Dragon", "cegt"), "label": "Dragon 4.6"}
        engines = {e["name"]: e for e in merge([
            self.observation("joker", "ccrl"), self.observation("Joker", "wiki-engines"),
            komodo, lucas,
        ], {"Joker": "Joker"}, rules)}
        self.assertEqual(sorted(engines), ["Dragon", "Dragon FR", "Joker", "Joker NL"])
        self.assertEqual(engines["Joker NL"]["aliases"], ["joker"])
        self.assertEqual(engines["Dragon FR"]["provenance"][0]["identity_evidence_url"],
                         "https://example.org/dragon")
        self.assertNotIn("identity_evidence_url", engines["Dragon"]["provenance"][0])
        self.assertEqual(unused_source_aliases([komodo], rules), rules)

    def test_not_source_urls_are_recorded_but_not_linked(self):
        row = self.observation("Isa", "one")
        row["code_urls"] = [
            {"url": "https://github.com/d/Isa-NNUE-releases/", "evidence_url": row["url"]},
            {"url": "https://github.com/d/Isa", "evidence_url": row["url"]},
        ]
        other = {**self.observation("Other", "one"),
                 "code_urls": [{"url": "https://github.com/d/isa-nnue-releases", "evidence_url": row["url"]}]}
        rules = [
            {"family": "Isa", "url": "https://github.com/d/isa-nnue-releases",
             "evidence_url": "https://example.org/isa", "note": "Binaries only."},
            {"family": "Gone", "url": "https://example.org/gone", "evidence_url": "https://example.org", "note": "x"},
        ]
        engines = {e["name"]: e for e in merge([row, other], {}, (), rules)}
        self.assertEqual([c["url"] for c in engines["Isa"]["source_code"]], ["https://github.com/d/Isa"])
        self.assertEqual(engines["Isa"]["rejected_source_code"], [{
            "url": "https://github.com/d/Isa-NNUE-releases/", "evidence_url": row["url"], "source": "one",
            "reason": "Binaries only.", "review_evidence_url": "https://example.org/isa",
        }])
        # Rules are family-specific, so another family's identical link is kept.
        self.assertEqual(len(engines["Other"]["source_code"]), 1)
        self.assertEqual(unused_not_source(list(engines.values()), rules), rules[1:])

    def test_reviewed_source_aliases_are_well_formed(self):
        overrides = json.loads((Path(__file__).parents[1] / "overrides.json").read_text(encoding="utf-8"))
        for rule in overrides["source_aliases"]:
            self.assertTrue(rule["sources"] and rule["evidence_url"].startswith("https://"), rule)
            self.assertNotEqual(rule["family"].casefold(), rule["target"].casefold(), rule)
        for rule in overrides["not_source_urls"]:
            self.assertTrue(rule["family"] and rule["note"], rule)
            self.assertTrue(rule["url"].startswith("https://") and rule["evidence_url"].startswith("https://"), rule)
        from publish import RELATIONS
        for rule in overrides["related_families"]:
            self.assertIn(rule["relation"], RELATIONS, rule)
            self.assertNotEqual(rule["family"], rule["related"], rule)
            self.assertTrue(rule["note"] and rule["evidence_url"].startswith("https://"), rule)


class PublishTests(unittest.TestCase):
    def test_csv_sorted_by_name_descending_without_reordering_catalog(self):
        engines = [
            {"name": name, "aliases": [], "provenance": [], "source_code": []}
            for name in ["Alpha", "zeta", "Beta"]
        ]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch("collect.ROOT", root):
                publish({"engines": engines}, [])
            with (root / "data" / "engines.csv").open(encoding="utf-8", newline="") as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual([row["name"] for row in rows], ["zeta", "Beta", "Alpha"])
            catalog = json.loads((root / "data" / "engines.json").read_text(encoding="utf-8"))
            self.assertEqual([engine["name"] for engine in catalog["engines"]], ["Alpha", "zeta", "Beta"])


class FetchTests(unittest.TestCase):
    def response(self, body=b"hello"):
        response = MagicMock()
        response.__enter__.return_value = response
        response.headers.get_content_charset.return_value = "utf-8"
        response.read.return_value = body
        return response

    def test_cache_and_post_data_are_distinct(self):
        with tempfile.TemporaryDirectory() as directory:
            fetch = Fetcher(Path(directory))
            with patch.object(fetch.opener, "open", return_value=self.response()) as network:
                self.assertEqual(fetch("https://example.org", {"type": "one"}), "hello")
                self.assertEqual(fetch("https://example.org", {"type": "one"}), "hello")
                fetch("https://example.org", {"type": "two"})
                self.assertEqual(network.call_count, 2)

    def test_rate_limit_at_least_one_second(self):
        with tempfile.TemporaryDirectory() as directory:
            fetch = Fetcher(Path(directory))
            with patch("collectors.http.time.monotonic", side_effect=[10, 10, 10.2, 11.1]):
                with patch("collectors.http.time.sleep") as sleep:
                    fetch._wait_for_slot()
                    fetch._wait_for_slot()
                    self.assertAlmostEqual(sleep.call_args_list[1].args[0], 0.9)
                    self.assertGreaterEqual(fetch._last_request - 10, 1.0)

    def test_404_is_explicit_and_cached(self):
        with tempfile.TemporaryDirectory() as directory:
            fetch = Fetcher(Path(directory))
            with patch.object(fetch.opener, "open", side_effect=HTTPError(
                "https://example.org", 404, "Not Found", {}, None
            )) as network:
                for _ in range(2):
                    with self.assertRaises(HTTPError):
                        fetch("https://example.org")
                self.assertEqual(network.call_count, 1)

    def test_offline_cache_miss_does_not_access_network(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(FileNotFoundError):
                Fetcher(Path(directory), offline=True)("https://example.org")

    def test_redirect_requests_also_take_a_rate_limit_slot(self):
        from collectors.http import ThrottledRedirects
        from urllib.request import Request

        wait = MagicMock()
        redirect = ThrottledRedirects(wait)
        redirect.redirect_request(
            Request("https://example.org/old"), None, 302, "Found", {},
            "https://example.org/new",
        )
        wait.assert_called_once()

    def test_429_waits_before_retrying(self):
        with tempfile.TemporaryDirectory() as directory:
            fetch = Fetcher(Path(directory))
            error = HTTPError("https://example.org", 429, "Rate limit", {"Retry-After": "120"}, None)
            with patch.object(fetch.opener, "open", side_effect=[error, self.response()]):
                with patch("collectors.http.time.sleep") as sleep:
                    self.assertEqual(fetch("https://example.org"), "hello")
                    self.assertIn(unittest.mock.call(120.0), sleep.call_args_list)


class LichessTests(unittest.TestCase):
    def test_profile_links_cover_alternative_forges_without_duplicates(self):
        self.assertEqual(repository_links(
            "Source: github.com/Owner/Engine/tree/main (see also git.sr.ht/~me)",
            "https://git.sr.ht/~prokop/uzenatch\r\nhttps://github.com/owner/engine\r\n"
            "https://gitlab.com/group/sub/repo https://bitbucket.org/a/b.git "
            "https://lichess.org/@/x mail@github.com/a/b",
        ), [
            "https://bitbucket.org/a/b",
            "https://git.sr.ht/~prokop/uzenatch",
            "https://github.com/Owner/Engine",
        ])

    def test_account_handle_is_not_a_family_and_wrappers_are_not_engines(self):
        self.assertEqual(repository_links(
            "https://github.com/a/lichess-bot https://github.com/user "
            "https://github.com/a/Engine."
        ), ["https://github.com/a/Engine"])
        members = [{"id": "somebot"}, {"id": "human"}]
        profiles = [
            {"id": "somebot", "username": "SomeBot", "title": "BOT"},
            {"id": "human", "username": "Human"},
        ]

        def fetch(url, data=None):
            if data is not None:
                return json.dumps(profiles)
            return "\n".join(json.dumps(member) for member in members)

        rows, unresolved, counts = collect(fetch, [], {})
        self.assertEqual(rows, [])
        self.assertEqual(len(unresolved), 1)
        self.assertEqual(counts["non_bot_accounts_excluded"], 1)
        rows, unresolved, _ = collect(fetch, [], {"somebot": {"family": "Actual engine"}})
        self.assertEqual(rows[0]["family"], "Actual engine")
        self.assertEqual(unresolved, [])
        rows, unresolved, _ = collect(fetch, ["Some"], {})
        self.assertEqual(rows[0]["family"], "Some")
        rows, unresolved, _ = collect(fetch, ["Some"], {"somebot": {"unresolved": True}})
        self.assertEqual((rows, len(unresolved)), ([], 1))


if __name__ == "__main__":
    unittest.main()
