import json
import unittest

from collectors import lucas_chess as lucas


class LucasChessTests(unittest.TestCase):
    def test_definitions_do_not_execute_and_collapse_models_and_versions(self):
        text = '''
raise RuntimeError("must not execute")
mas("greko98", "", "9.8", "", "GreKo98a", 0)
mas("rodentii", "", "", "", "RodentII-0.9.64", 0)
mas("komodo", "", f"dragon-1{avx2}", "", f"dragon-linux{avx2}", 0)
mas(f"maia-{level}", "", str(level), "", "Lc0-0.27.0", 0, folder="maia")
mas("ceechess", "", "", "", "CeeChess-1.3.2", 0)
mas("k2", "", "", "", "K2-0.99", 0)
mas("arhanpassant", "", "", "", "arhanpassant-linux-x86_64-avx2", 0)
mas("octochess", "", "", "", "Octochess-r5190", 0)
mas("toga", "", "", "", "DeepToga1.9.6nps", 0)
'''
        rows = lucas.definitions(text)
        self.assertEqual(
            [rows[key]["family"] for key in rows],
            ["GreKo", "Rodent", "Dragon", "Maia", "CeeChess", "K2",
             "Arhanpassant", "Octochess", "Toga"],
        )

    def test_tree_provenance_and_explicit_code_links(self):
        paths = [
            ("tree", lucas.PREFIX + "amoeba"),
            ("blob", lucas.PREFIX + "amoeba/src.7z"),
            ("blob", lucas.PREFIX + "amoeba/source.url"),
            ("blob", lucas.PREFIX + "amoeba/Amoeba-2.6"),
            ("tree", lucas.PREFIX + "amoeba/personas"),
            ("blob", lucas.PREFIX + "amoeba/personas/src.zip"),
        ]
        replies = {
            lucas.TREE_URL: json.dumps({"tree": [{"type": t, "path": p} for t, p in paths]}),
            lucas.RAW_URL + lucas.CONFIG_PATH:
                'mas("amoeba", "Richard Delorme", "2.6", "https://github.com/abulmo/amoeba", "Amoeba-2.6", 0)',
            lucas.RAW_URL + lucas.PREFIX + "amoeba/source.url":
                "[InternetShortcut]\nURL=https://svn.example.org/chess/",
        }
        rows = lucas.collect(lambda url: replies[url])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["family"], "Amoeba")
        self.assertEqual(rows[0]["author"], "Richard Delorme")
        self.assertEqual(rows[0]["revision"], lucas.REVISION)
        self.assertEqual(len(rows[0]["code_urls"]), 3)
        self.assertIn("https://svn.example.org/chess", [
            code["url"] for code in rows[0]["code_urls"]
        ])
        self.assertIn(lucas.REVISION, rows[0]["url"])

    def test_missing_directory_definition_fails(self):
        tree = json.dumps({"tree": [{"type": "tree", "path": lucas.PREFIX + "unknown"}]})
        with self.assertRaisesRegex(ValueError, "directory/config mismatch"):
            lucas.collect(lambda url: tree if url == lucas.TREE_URL else
                          'mas("known", "", "", "", "Known-1", 0)')

    def test_truncated_tree_and_non_repository_links_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "truncated"):
            lucas.collect(lambda url: '{"truncated": true, "tree": []}')
        self.assertFalse(lucas.repository_url("https://github.com/LeelaChessZero"))
        self.assertFalse(lucas.repository_url("https://example.org/a/b"))
        self.assertFalse(lucas.repository_url("javascript:alert(1)"))


if __name__ == "__main__":
    unittest.main()
