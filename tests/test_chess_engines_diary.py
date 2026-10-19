import unittest

from collectors.chess_engines_diary import collect, family_name


class DiaryTests(unittest.TestCase):
    def table(self, rank="1"):
        return (
            "<table><tr><th>Ran</th><th>Player</th><th>Rating</th><th>Games</th>"
            "<th>W-D-L</th><th>Draw %</th><th>Points</th></tr>"
            f"<tr><td>{rank}</td><td>Stockfish dev-20260922</td><td>3912.4</td>"
            "<td>142</td><td>56-86-0</td><td>60.6</td><td>99.0</td></tr></table>"
        )

    def test_only_ranked_tables_and_both_sections(self):
        table = self.table().replace("</tr><tr>", "</tr><tr><td></td></tr><tr>")
        rows = collect(lambda url: "<table><tr><td>Arena GUI</td></tr></table>" + table * 2)
        self.assertEqual(len(rows), 2)
        self.assertEqual([r["family"] for r in rows], ["Stockfish"] * 2)
        self.assertNotEqual(rows[0]["section"], rows[1]["section"])
        self.assertEqual(rows[0]["code_urls"], [])

    def test_versions_preserve_forks(self):
        for label, name in [
            ("Reckless 0.10.0 dev-7300f044", "Reckless"),
            ("Wreckless 2.0.0", "Wreckless"), ("Stockfish dev-20260922", "Stockfish"),
        ]:
            self.assertEqual(family_name(label), name)

    def test_derivative_table_header_is_recognized(self):
        table = self.table().replace("Ran</th>", "Pl</th>").replace(
            "Player</th>", "Engines</th>"
        ).replace("Draw %</th>", "Score %</th>")
        self.assertEqual(len(collect(lambda url: table)), 1)

    def test_missing_and_malformed_tables_fail(self):
        for text in ["Access denied", self.table("2"), self.table().replace("3912.4", "bad")]:
            with self.assertRaises(ValueError):
                collect(lambda url: text)
