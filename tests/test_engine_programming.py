import unittest

from collect import merge
from collectors import engine_programming as community


DOCUMENT = """
### Chess Engines
| Engine Name | Author | Rating | Notes |
|---|---|---|---|
| [Engine42](https://github.com/a/engine42) 2.1 | [Author](https://github.com/a) | 3000 | |
| [Valiant](https://www.dropbox.com/sh/example?dl=0) Mk 8 | Author | 2000 | |
### Chess960 Engines
| Engine Name | Author | Rating | Notes |
|---|---|---|---|
| [Engine42](https://github.com/a/engine42) 2.1 | Author | 3000 | |
### Ataxx Engines
| [NotChess](https://github.com/a/ataxx) | Author | |
### GGPs & Other Game Engines
| Engine Name | Author | Game | Notes |
|---|---|---|---|
| [kZero](https://github.com/a/kzero) | Author | Chess, Go, Ataxx | |
| [FairyOnly](https://github.com/a/fairy) | Author | GGP (Fairy Chess) | |
| [TetrisOnly](https://github.com/a/tetris) | Author | Tetris | |
| [Unknown](https://github.com/a/unknown) | Author | |
"""


class CommunityListTests(unittest.TestCase):
    def test_chess_sections_and_explicit_chess_multigame_entries_only(self):
        calls = []

        def fetch(url):
            calls.append(url)
            return DOCUMENT

        fetch.checked_at = {community.RAW_URL: "2026-01-01T00:00:00+00:00"}

        rows = community.collect(fetch)
        self.assertEqual(calls, [community.RAW_URL])
        self.assertEqual([row["family"] for row in rows], ["Engine42", "Valiant", "Engine42", "kZero"])
        self.assertEqual(rows[0]["label"], "Engine42 2.1")
        self.assertEqual(rows[0]["revision"], community.REVISION)
        self.assertEqual(rows[0]["checked_at"], fetch.checked_at[community.RAW_URL])
        self.assertEqual(rows[0]["code_urls"][0]["evidence_url"], community.DOCUMENT_URL)
        self.assertEqual(rows[1]["code_urls"], [])
        self.assertEqual(rows[1]["project_url"], "https://www.dropbox.com/sh/example?dl=0")
        for row in rows:
            row["source"] = "engine-programming"
        engines = merge(rows, {})
        self.assertEqual(len(engines), 3)
        engine = next(engine for engine in engines if engine["name"] == "Engine42")
        self.assertEqual(len(engine["provenance"]), 2)
        self.assertEqual(len(engine["source_code"]), 1)

    def test_missing_sections_and_malformed_chess_rows_fail(self):
        for text in [
            "<html>Not a README</html>",
            DOCUMENT.replace("### Chess960 Engines", "### Unsupported"),
            DOCUMENT.replace("[Engine42](https://github.com/a/engine42)", "Engine42"),
        ]:
            with self.subTest(text=text[:40]), self.assertRaises(ValueError):
                community.collect(lambda url: text)


if __name__ == "__main__":
    unittest.main()
