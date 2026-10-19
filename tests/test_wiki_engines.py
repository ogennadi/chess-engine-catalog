import unittest
from unittest.mock import patch

from collect import merge
from collectors import wiki_engines as wiki
from collectors.http import Fetcher


def document(items, heading="A"):
    return f"""
    <h2 id="introduction">Engines</h2>
    <ul><li><a href="/Not_An_Engine">Introduction link</a></li></ul>
    <h2 id="alphabetical-list">Alphabetical List</h2>
    <p>maintained manually</p><h3>{heading}</h3><ul>{items}</ul>
    <h2 id="forum-posts">Forum Posts</h2>
    <ul><li><a href="/Footer">Footer</a></li></ul>
    """


def collect(text):
    def fetch(url):
        if url != wiki.SOURCE_URL:
            raise AssertionError(f"Unexpected fetch: {url}")
        return text

    fetch.checked_at = {wiki.SOURCE_URL: "2026-10-18T19:00:00+00:00"}
    return wiki.collect(fetch)


class WikiEngineTests(unittest.TestCase):
    def test_only_primary_engine_anchors_in_alphabetical_lists(self):
        rows = collect(document("""
        <li><b><a href="/Almond"><em>Almond</em></a></b>, a
            <a href="/Category:Clone">clone</a> of <a href="/Now">Now</a></li>
        <li><a href="/Ares">Ares</a> by <a href="/Frans_van_Gool">Frans van Gool</a></li>
        <li><a href="/Hydra">Hydra</a> (<a href="/FPGA">FPGA</a> program)</li>
        <li>Unlinked Engine by <a href="/An_Author">An Author</a></li>
        <li>Unlinked Engine</li>
        <li><a href="/Category:Engines">Engines</a></li>
        <li><a href="/List_of_Engines">List of engines</a></li>
        <li><a href="/Universal_Chess_Interface">UCI</a></li>
        <li><a href="/Chess_GUI">GUI</a></li>
        <li><a href="/Computers">Computers</a></li>
        <li><a href="/DroidFish">DroidFish</a></li>
        <li><a href="/PicoChess">PicoChess</a></li>
        <li><a href="/Raspberry_Turk">Raspberry Turk</a></li>
        <li><a href="#related">Related</a></li>
        <li><a href="https://elsewhere.invalid/Engine">External</a></li>
        """))
        self.assertEqual([row["family"] for row in rows], ["Almond", "Ares", "Hydra"])
        self.assertEqual(rows[0]["label"], "Almond, a clone of Now")
        self.assertIn("Frans van Gool", rows[1]["label"])
        self.assertTrue(all(row["code_urls"] == [] for row in rows))

    def test_page_provenance_and_actual_fetch_timestamp(self):
        row = collect(document(
            '<li><a href="/Pr%C3%A9dateur" title="Prédateur">Prédateur</a></li>'
        ))[0]
        self.assertEqual(row["family"], "Predateur")
        self.assertEqual(row["listed_name"], "Prédateur")
        self.assertEqual(row["page_title"], "Prédateur")
        self.assertEqual(row["page_path"], "/Pr%C3%A9dateur")
        self.assertEqual(row["project_url"], "https://chessprogramming.org/Pr%C3%A9dateur")
        self.assertEqual(row["listing_url"], wiki.SOURCE_URL)
        self.assertEqual(row["url"], wiki.SECTION_URL)
        self.assertEqual(row["checked_at"], "2026-10-18T19:00:00+00:00")
        self.assertEqual(row["section"], "A")
        self.assertEqual(row["code_urls"], [])
        doctor = collect(document('<li><a href="/Doctor%253F">Doctor?</a></li>'))[0]
        self.assertEqual(doctor["page_title"], "Doctor?")
        self.assertEqual(doctor["page_path"], "/Doctor%253F")

    def test_reviewed_catalog_aliases_and_qualified_homonyms(self):
        rows = collect(document("""
        <li><a href="/Bringer">Bringer</a></li>
        <li><a href="/Leela_Chess_Zero">Leela Chess Zero</a></li>
        <li><a href="/BugChess_NL">BugChess</a> by Erik van het Hof</li>
        <li><a href="/BugChess_FR">BugChess2</a> by François Karr</li>
        <li><a href="/Ares">Ares</a></li>
        <li><a href="/Ares_US">Ares</a></li>
        <li><a href="/BBchess">BBchess</a></li>
        <li><a href="/BBChess_%28SI%29">BBChess</a></li>
        <li><a href="/Chessmaster">Chessmaster</a></li>
        <li><a href="/Chess_Champion_Super_System_III">ChessMaster</a></li>
        """))
        self.assertEqual([row["family"] for row in rows], [
            "Der Bringer", "Leela Chess", "BugChess NL", "BugChess",
            "Ares", "Ares US", "BBchess", "BBChess (SI)",
            "Chessmaster", "Chess Champion Super System III",
        ])
        self.assertTrue(all("identity_note" in rows[index] for index in (0, 1, 2, 3, 5, 7, 9)))

    def test_shared_articles_do_not_merge_distinct_programs(self):
        rows = collect(document("""
        <li><a href="/Goliath">Goliath</a></li>
        <li><a href="/Goliath">Little Goliath</a> (Goliath)</li>
        <li><a href="/Goliath">Little Goliath Evolution</a></li>
        <li><a href="/Loop_%28Program%29">Loop</a></li>
        <li><a href="/Loop_%28Program%29">Loop-List</a></li>
        <li><a href="/Capivara">Capivara</a></li>
        <li><a href="/Capivara">Capivara LK</a></li>
        <li><a href="/Tech">Tech</a></li>
        <li><a href="/Tech">Tech 2</a></li>
        <li><a href="/Tech">Tech 3</a></li>
        """))
        for row in rows:
            row["source"] = "wiki-engines"
        engines = merge(rows, {})
        self.assertEqual(len(engines), 9)
        self.assertEqual([row["family"] for row in rows[:7]], [
            "Little Goliath", "Little Goliath", "Little Goliath Evolution",
            "Loop", "Loop-List", "Capivara", "Capivara LK",
        ])
        self.assertTrue(all("Shared article" in row["identity_note"] for row in rows[:7]))
        self.assertTrue(all(not engine["source_code"] for engine in engines))

    def test_reviewed_predecessors_and_variants_share_family(self):
        rows = collect(document("""
        <li><a href="/Awit">Awit</a></li>
        <li><a href="/Wita">Wita</a></li>
        <li><a href="/Mac_Hack">Mac Hack</a></li>
        <li><a href="/Greenblatt_Chess_Program">Greenblatt Chess Program</a></li>
        <li><a href="/Stockfish">Stockfish</a></li>
        <li><a href="/Stockfish_NNUE">Stockfish NNUE</a></li>
        <li><a href="/Maia_Chess">Maia Chess</a></li>
        """))
        self.assertEqual([row["family"] for row in rows], [
            "Awit", "Awit", "Mac Hack", "Mac Hack", "Stockfish", "Stockfish", "Maia",
        ])
        self.assertEqual(rows[1]["page_title"], "Wita")

    def test_historical_engines_are_not_rejected_modern_lookalikes(self):
        rows = collect(document("""
        <li><a href="/Atlas">Atlas</a> by Alex Bell</li>
        <li><a href="/Atlas_%28ESP%29">Atlas</a> by Andrés Manzanares Campillo</li>
        <li><a href="/Achilles">Achilles</a></li>
        <li><a href="/Albatross">Albatross</a></li>
        <li><a href="/Nuchess">Nuchess</a></li>
        """))
        self.assertEqual([row["family"] for row in rows], [
            "Atlas (1967)", "Atlas", "Achilles", "Albatross", "Nuchess",
        ])
        self.assertIn("1967", rows[0]["identity_note"])
        modern = [{"family": name, "label": name, "url": "example", "source": "existing"}
                  for name in ("Atlas", "Achillees", "Albatros", "Nu-chess")]
        for row in rows:
            row["source"] = "wiki-engines"
        self.assertEqual(len(merge(modern + rows, {})), 8)

    def test_explicit_non_chess_games_excluded_but_chess_programs_preserved(self):
        rows = collect(document("""
        <li><a href="/Apery">Apery</a> (<a href="/Shogi">Shogi</a>)</li>
        <li><a href="/Abyss">Abyss</a> (<a href="/Chinese_Chess">Chinese Chess</a>)</li>
        <li><a href="/OnlyGo">OnlyGo</a> (Go)</li>
        <li><a href="/OnlyShogi">OnlyShogi</a> (Shogi)</li>
        <li><a href="/Multigame">Multigame</a>
            (<a href="/Chess">Chess</a>, <a href="/Go">Go</a>)</li>
        <li><a href="/Fairy-Max">Fairy-Max</a></li>
        <li><a href="/Mac_Hack">Mac Hack</a></li>
        """))
        self.assertEqual([row["family"] for row in rows], ["Multigame", "Fairy-Max", "Mac Hack"])

    def test_missing_boundaries_and_unexpected_structure_fail(self):
        valid = document('<li><a href="/An_Engine">An Engine</a></li>')
        for text in (
            "<html>not an index</html>",
            valid.replace('id="alphabetical-list"', 'id="other"'),
            valid.replace('id="forum-posts"', 'id="related-links"'),
            valid[:valid.index('<h2 id="forum-posts"')],
            valid.replace("<h3>A</h3>", "<h3>Related engines</h3>"),
            valid.replace("<ul><li><a href=\"/An_Engine\">", "<ul><ul><li><a href=\"/An_Engine\">"),
            valid.replace("An Engine</a></li>", "An Engine</a>"),
            valid.replace("<h3>A</h3>", "<table></table><h3>A</h3>"),
            valid.replace('id="forum-posts"', 'id="alphabetical-list"'),
            document("<li>Unlinked only</li>"),
            document('<li><a href="/Empty"></a></li>'),
            document('<li><a href="/Junk">(clone)</a></li>'),
            document('<li><a href="/Junk">--</a></li>'),
            document('<li><a href="/Unknown_A">Unknown</a></li>'
                     '<li><a href="/Unknown_B">Unknown</a></li>'),
        ):
            with self.subTest(text=text[:100]), self.assertRaises(ValueError):
                collect(text)

    def test_cached_index_offline(self):
        fetch = Fetcher(offline=True)
        # The fixture is optional in clean checkouts. Never attempt HTTP even
        # when the local cache is absent or a future parser requests more pages.
        with patch.object(fetch.opener, "open", side_effect=AssertionError("Network forbidden")):
            try:
                rows = wiki.collect(fetch)
            except FileNotFoundError:
                self.skipTest("Engine index is not cached locally")
        self.assertGreater(len(rows), 1000)
        self.assertGreater(len({row["family"].casefold() for row in rows}), 1000)
        self.assertFalse({"DroidFish", "PicoChess", "Raspberry Turk"} & {row["family"] for row in rows})
        self.assertTrue(all(row["checked_at"] == fetch.checked_at[wiki.SOURCE_URL] for row in rows))
        self.assertTrue(all(row["listing_url"] == wiki.SOURCE_URL for row in rows))
        self.assertTrue(all(not row["code_urls"] for row in rows))
        self.assertEqual(len(fetch.checked_at), 1)


if __name__ == "__main__":
    unittest.main()
