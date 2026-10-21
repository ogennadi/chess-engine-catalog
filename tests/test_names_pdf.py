import tempfile
import json
import unittest
from pathlib import Path

import names_pdf


class PosterTests(unittest.TestCase):
    def setUp(self):
        self.rows, self.count = names_pdf.entries()
        portrait = names_pdf.PAPER["poster"]
        self.page_size = (portrait[1], portrait[0])

    def test_poster_dimensions(self):
        self.assertEqual(self.page_size, (48 * 72, 36 * 72))

    def test_all_families_fit_with_sequential_indices_and_no_clipping(self):
        size, page_count = names_pdf.choose(self.rows, self.page_size, 16, 1)
        self.assertEqual(page_count, 1)
        self.assertGreaterEqual(size, 16)
        pages = names_pdf.layout(self.rows, size, self.page_size, 2)
        self.assertEqual(len(pages), 1)
        indices = []
        numbers = names_pdf.number_width(self.rows, size)
        right = 0
        for x, column in pages[0]:
            self.assertGreaterEqual(x, right)
            right = x + max(names_pdf.row_width(row, size, numbers) for row in column)
            self.assertLessEqual(right, self.page_size[0] - 2 * names_pdf.MARGIN)
            bottom = (self.page_size[1] - names_pdf.MARGIN - names_pdf.title_height(size)
                      - size - (len(column) - 1) * size * names_pdf.LEADING)
            self.assertGreaterEqual(bottom, names_pdf.MARGIN)
            self.assertFalse(column[-1][1], "A heading must not be stranded at a column end")
            indices.extend(index for _, heading, index in column if not heading)
        self.assertEqual(indices, list(range(1, self.count + 1)))
        self.assertGreater(len(names_pdf.layout(self.rows, size + 0.25, self.page_size, 2)), 1)

    def test_render_single_poster_page(self):
        size, _ = names_pdf.choose(self.rows, self.page_size, 16, 1)
        catalog = json.loads((names_pdf.ROOT / "data" / "engines.json").read_text(encoding="utf-8"))
        links = names_pdf.source_links(catalog)
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / "poster.pdf"
            pages = names_pdf.render(self.rows, self.count, size, self.page_size, out, links)
            pdf = out.read_bytes()
        self.assertEqual(pages, 1)
        self.assertIn(b"/MediaBox [0 0 3456 2592]", pdf)
        self.assertIn(b"/Count 1", pdf)
        self.assertEqual(pdf.count(b"/Subtype /Link"), self.count)
        self.assertTrue(pdf.endswith(b"%%EOF\n"))


class SourceLinkTests(unittest.TestCase):
    def choose(self, *codes):
        return names_pdf.preferred_source({"name": "Example", "source_code": list(codes)})

    def test_corroborated_repository_beats_fork_and_bundle(self):
        official = "https://github.com/author/engine"
        self.assertEqual(self.choose(
            {"url": "https://github.com/fork/engine", "source": "rwbc"},
            {"url": "https://github.com/bundle/engines/blob/hash/src.zip", "source": "lucas-chess"},
            {"url": official, "source": "ccrl"},
            {"url": official, "source": "rwbc"},
        ), official)

    def test_researched_archive_beats_stale_download(self):
        archive = "https://web.archive.org/web/20040101/http://old.example/src.zip"
        self.assertEqual(self.choose(
            {"url": "http://old.example/src.zip", "source": "rwbc"},
            {"url": archive, "source": "source-status-research"},
        ), archive)

    def test_caution_lowers_priority_and_ties_preserve_order(self):
        first = "https://example.org/source.zip"
        self.assertEqual(self.choose(
            {"url": "https://old.example/src.zip", "source": "source-status-research",
             "kind": "site offline; liveness not checked"},
            {"url": first, "source": "source-status-research"},
            {"url": "https://mirror.example/source.zip", "source": "source-status-research"},
        ), first)

    def test_unsafe_or_missing_links_fail_explicitly(self):
        with self.assertRaisesRegex(ValueError, "Example"):
            self.choose({"url": "javascript:alert(1)", "source": "rwbc"})


if __name__ == "__main__":
    unittest.main()
