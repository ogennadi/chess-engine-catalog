import unittest

import fetch_sources as fs


class ClassifyTests(unittest.TestCase):
    def test_github_repository_links_clone_the_repository(self):
        for url in ("https://github.com/Nonlinear2/Bread-Engine", "https://github.com/a/b.git/",
                    "https://github.com/a/b/tree/main/src", "https://github.com/a/b/blob/master/x.c"):
            target = fs.classify(url)
            self.assertEqual(target["kind"], "git")
        self.assertEqual(fs.classify("https://github.com/a/b/tree/x")["clone"], "https://github.com/a/b.git")

    def test_github_archive_blob_is_downloaded_raw(self):
        target = fs.classify("https://github.com/lukasmonk/lucaschessR6/blob/4bd6/bin/Engines/beef/src.7z")
        self.assertEqual(target["kind"], "file")
        self.assertEqual(target["fetch"], "https://raw.githubusercontent.com/lukasmonk/lucaschessR6/4bd6/bin/Engines/beef/src.7z")

    def test_user_pages_and_web_pages_are_skipped(self):
        self.assertEqual(fs.classify("https://github.com/someone")["kind"], "skip")
        self.assertEqual(fs.classify("https://nanochess.org/chess1.html")["kind"], "skip")
        self.assertEqual(fs.classify("https://mega.nz/file/abc")["kind"], "skip")

    def test_gitlab_subgroups_and_other_git_hosts(self):
        self.assertEqual(fs.classify("https://gitlab.com/g/sub/repo/-/tree/main")["clone"], "https://gitlab.com/g/sub/repo.git")
        self.assertEqual(fs.classify("https://repo.or.cz/w/rattatechess.git")["clone"], "https://repo.or.cz/rattatechess.git")
        self.assertEqual(fs.classify("http://hgm.nubati.net/git/simple.git")["kind"], "git")

    def test_sourceforge_project_and_mount(self):
        target = fs.classify("https://sourceforge.net/p/animatschess/code/")
        self.assertEqual((target["kind"], target["project"], target["mount"]), ("sf", "animatschess", "code"))
        self.assertIsNone(fs.classify("https://sourceforge.net/projects/belofte/")["mount"])

    def test_software_heritage_uses_origin(self):
        target = fs.classify("https://archive.softwareheritage.org/browse/origin/directory/?origin_url=https://github.com/flok99/Embla")
        self.assertEqual((target["kind"], target["origin"]), ("swh", "https://github.com/flok99/Embla"))

    def test_internet_archive_is_never_fetched_but_gives_a_manual_url(self):
        target = fs.classify("https://web.archive.org/web/20070607093301/http://example.org/eng/src.zip")
        self.assertEqual(target["kind"], "skip")
        self.assertEqual(target["manual"], "https://web.archive.org/web/20070607093301id_/http://example.org/eng/src.zip")
        for url in ("https://web.archive.org/web/2007/http://example.org/page.htm",
                    "https://archive.org/details/KAISSA", "https://ia800300.us.archive.org/1/items/x/x.zip"):
            self.assertEqual(fs.classify(url)["kind"], "skip")
            self.assertTrue(fs.classify(url)["manual"])
        with self.assertRaises(fs.RefusedInternetArchive):
            fs.http("https://archive.org/download/x/x.zip")

    def test_source_list_round_trip(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "list.txt"
            path.write_text("# comment\n\nBread\n  = Bread Engine\n  https://github.com/a/b\n\n#Chess\n  https://x/y.zip\n",
                            encoding="utf-8")
            engines = fs.read_source_list(path)
        self.assertEqual([(e["name"], e["aliases"], [c["url"] for c in e["source_code"]]) for e in engines],
                         [("Bread", ["Bread Engine"], ["https://github.com/a/b"]), ("#Chess", [], ["https://x/y.zip"])])

    def test_plan_puts_most_cited_repository_first_and_drops_unreachable(self):
        engine = {"name": "X", "source_code": [
            {"url": "https://example.org/x.zip"},
            {"url": "https://github.com/fork/x"},
            {"url": "https://github.com/orig/x"}, {"url": "https://github.com/orig/x/"},
            {"url": "https://github.com/dead/x", "unreachable": True},
        ]}
        self.assertEqual([t["url"] for t in fs.plan(engine)],
                         ["https://github.com/orig/x", "https://github.com/fork/x", "https://example.org/x.zip"])


if __name__ == "__main__":
    unittest.main()
