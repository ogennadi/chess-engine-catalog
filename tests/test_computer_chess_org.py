import unittest

from collectors import computer_chess_org as cco


def row(*cells):
    html = "<tr>"
    for cell in cells:
        if isinstance(cell, tuple):
            text, links = cell
            html += "<td>" + text + "".join(f' <a href="{url}">{label}</a>' for label, url in links) + "</td>"
        else:
            html += f"<td>{cell}</td>"
    return html + "</tr>"


def page(*sections):
    html = ""
    for heading, rows in sections:
        html += f"<h2>{heading}</h2><table><tr><th>Engine</th></tr>{''.join(rows)}</table>"
    return html


SPECIAL = [
    ("Dead Engine List", [row("2010", "Old", "1", "A. Author", "-", "WB", "-")]),
    ("Source Code Only List", [row("Code", "B. Author", "UCI", "C source")]),
    ("Withdrawn Engine List", [row("Gone", "2", "C. Author", "UCI", "-")]),
]


class ComputerChessOrgTests(unittest.TestCase):
    def collect(self, *sections):
        html = page(*sections, *SPECIAL)
        return cco.collect(lambda url: html)

    def test_sections_columns_and_unreleased_projects(self):
        observations = self.collect(
            ("2020 Releases", [row("2020-01-02", ("", [("Toga II", "https://example.org/toga")]),
                                   "4.0", "Thomas Gaksch", "-", "UCI", "C++ source")]),
            ("Someday Announcement Engine List", [row("Future", "D. Author")]),
        )
        by_family = {item["family"]: item for item in observations}
        self.assertEqual(sorted(by_family), ["Code", "Gone", "Old", "Toga"])
        toga = by_family["Toga"]
        self.assertEqual((toga["label"], toga["version"], toga["comment"], toga["date_added"]),
                         ("Toga II", "4.0", "C++ source", "2020-01-02"))
        self.assertEqual(toga["project_url"], "https://example.org/toga")
        self.assertEqual(by_family["Code"]["section"], "Source Code Only List")
        self.assertEqual(by_family["Gone"]["version"], "2")

    def test_homonyms_split_by_author(self):
        self.assertEqual(cco.family_name("Chess(2)", "Pier Lattanzi"), "Chess (Lattanzi)")
        self.assertEqual(cco.family_name("Crab", "Thomas Kleng"), "Crab (Kleng)")
        self.assertEqual(cco.family_name("Crab", "Someone Else"), "Crab")
        self.assertEqual(cco.family_name("LCZero", "LC0 Team"), "Leela Chess")

    def test_unreviewed_numbered_homonyms_warn(self):
        self.collect(("2019 Releases", [row("-", "Engine(7)", "1", "X", "-", "UCI", "-")]))
        self.assertEqual(cco.collect.last_warnings, ["Unreviewed numbered homonym 'Engine(7)' by 'X'"])

    def test_code_links(self):
        site = [{"url": "https://github.com/owner/anything", "text": "Site"},
                {"url": "https://example.org/home", "text": "Home"}]
        downloads = [
            {"url": "https://www.mediafire.com/file/abc/engine_src.zip", "text": "Source"},
            {"url": "https://github.com/author/", "text": "source"},
            {"url": "https://github.com/builder/engine-builds", "text": "Windows"},
            {"url": "https://github.com/builder/compiles", "text": "Windows"},
            {"url": "https://gitlab.com/owner/engine/tags", "text": "Releases"},
        ]
        self.assertEqual([item["url"] for item in cco.code_urls("Engine", "Engine", site, downloads)], [
            "https://github.com/owner/anything",
            "https://www.mediafire.com/file/abc/engine_src.zip",
            "https://github.com/builder/engine-builds",
            "https://gitlab.com/owner/engine",
        ])

    def test_malformed_rows_and_missing_sections_fail(self):
        with self.assertRaises(ValueError):
            self.collect(("2020 Releases", [row("only", "three", "cells")]))
        with self.assertRaises(ValueError):
            cco.collect(lambda url: page(("2020 Releases", [row("-", "E", "1", "X", "-", "UCI", "-")])))
        with self.assertRaises(ValueError):
            self.collect(("Mystery List", [row("E", "X", "UCI", "-")]))


if __name__ == "__main__":
    unittest.main()
