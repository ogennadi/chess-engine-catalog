"""Write a compact, printable PDF listing every family whose source code is available.

    python names_pdf.py [--out PATH] [--paper letter|a4|poster] [--orientation portrait|landscape] [--min-size PT]

Reads data/engines.json (run collect.py first). Families whose availability is linked,
available, or archived_only are numbered and listed alphabetically under letter headings,
in as many columns as fit (portrait pages by default). The default 16 pt minimum is about the
smallest text that 20/20 vision can read from 9 feet; the largest size up to 4 pt above
it that still gives the fewest pages is chosen. Uses only the standard library. Names are set in Atkinson Hyperlegible
and index numbers in Atkinson Hyperlegible Mono (embedded from fonts/, SIL OFL 1.1), so l, I and 1 stay distinct, and the
title in the PDF base-14 Helvetica; text is horizontally condensed. The output is generated, so it is gitignored.
For a single 48 x 36 inch landscape poster, use --paper poster --orientation landscape --max-pages 1.
"""

import argparse
import json
import struct
import zlib
from datetime import date
from pathlib import Path
from urllib.parse import quote, urlsplit

import source_status

ROOT = Path(__file__).resolve().parent
AVAILABLE = {"linked", "available", "archived_only"}
PAPER = {"letter": (612, 792), "a4": (595, 842), "poster": (36 * 72, 48 * 72)}
MARGIN = 18
GUTTER = 6
LEADING = 1.13
CONDENSE = 85
SIZE_RANGE = 4.0
# Upper bound so short lists do not grow until a single row no longer fits a page.
MAX_SIZE = 48.0
DAGGER = "\u2020"

FONT_DIR = ROOT / "fonts"
FIRST_CHAR, LAST_CHAR = 32, 255


# Helvetica and Helvetica-Bold advance widths (1/1000 em) for ASCII 32-126, from the Adobe AFM files.
_HELVETICA = (
    "278 278 355 556 556 889 667 191 333 333 389 584 278 333 278 278 556 556 556 556 556 556 556 556 "
    "556 556 278 278 584 584 584 556 1015 667 667 722 722 667 611 778 722 278 500 667 556 833 722 778 "
    "667 778 722 667 611 722 667 944 667 667 611 278 278 278 469 556 333 556 556 500 556 556 278 556 "
    "556 222 222 500 222 833 556 556 556 556 333 500 278 556 500 722 500 500 500 334 260 334 584"
)
_HELVETICA_BOLD = (
    "278 333 474 556 556 889 722 238 333 333 389 584 278 333 278 278 556 556 556 556 556 556 556 556 "
    "556 556 333 333 584 584 584 611 975 722 722 722 722 667 611 778 722 278 556 722 611 833 722 778 "
    "667 778 722 667 611 722 667 944 667 667 611 333 278 333 584 556 333 556 611 556 611 556 333 611 "
    "611 278 278 556 278 889 611 611 611 611 389 556 333 611 556 778 556 556 500 389 280 389 584"
)


class Base14Font:
    """A standard PDF font that readers supply, so nothing is embedded."""

    def __init__(self, name, table):
        self.name = name
        self.widths = {chr(32 + i): int(w) for i, w in enumerate(table.split())}
        # The title's em dash and the subtitle's dagger, from the same AFM files.
        self.widths.update({"\u2014": 1000, DAGGER: 556})

    def pdf_objects(self, first):
        return [b"<< /Type /Font /Subtype /Type1 /BaseFont /%s /Encoding /WinAnsiEncoding >>" % self.name.encode()]


class TrueTypeFont:
    """Just enough of a TrueType file to embed it as a WinAnsi-encoded simple PDF font."""

    def __init__(self, path):
        self.data = data = path.read_bytes()
        tables = {
            data[12 + 16 * i:16 + 16 * i].decode("latin-1"): struct.unpack(">II", data[20 + 16 * i:28 + 16 * i])
            for i in range(struct.unpack(">H", data[4:6])[0])
        }

        def table(tag):
            offset, length = tables[tag]
            return data[offset:offset + length]

        head, hhea, os2 = table("head"), table("hhea"), table("OS/2")
        self.units = struct.unpack(">H", head[18:20])[0]
        self.bbox = [self.scale(v) for v in struct.unpack(">hhhh", head[36:44])]
        self.ascent, self.descent = (self.scale(v) for v in struct.unpack(">hh", hhea[4:8]))
        self.cap_height = self.scale(struct.unpack(">h", os2[88:90])[0])
        self.italic_angle = struct.unpack(">i", table("post")[4:8])[0] / 65536
        name = table("name")
        count, strings = struct.unpack(">HH", name[2:6])
        self.name = next(
            name[strings + offset:strings + offset + length].decode("utf-16-be")
            for platform, _, _, name_id, length, offset in
            (struct.unpack(">HHHHHH", name[6 + 12 * i:18 + 12 * i]) for i in range(count))
            if platform == 3 and name_id == 6
        )
        metrics = struct.unpack(">H", hhea[34:36])[0]
        hmtx = table("hmtx")
        advances = [struct.unpack(">H", hmtx[4 * i:4 * i + 2])[0] for i in range(metrics)]
        glyphs = self.cmap(table("cmap"))
        self.widths = {}
        for code in range(FIRST_CHAR, LAST_CHAR + 1):
            char = bytes([code]).decode("cp1252", "replace")
            glyph = glyphs.get(ord(char), 0)
            self.widths[char] = self.scale(advances[min(glyph, metrics - 1)])

    def scale(self, value):
        return round(value * 1000 / self.units)

    @staticmethod
    def cmap(data):
        """Map code points to glyph ids from the Windows Unicode BMP (format 4) subtable."""
        for i in range(struct.unpack(">H", data[2:4])[0]):
            platform, encoding, offset = struct.unpack(">HHI", data[4 + 8 * i:12 + 8 * i])
            if (platform, encoding) == (3, 1) and struct.unpack(">H", data[offset:offset + 2])[0] == 4:
                break
        else:
            raise ValueError("TrueType font has no Windows Unicode cmap")
        segments = struct.unpack(">H", data[offset + 6:offset + 8])[0] // 2
        arrays = offset + 14
        ends = struct.unpack(">%dH" % segments, data[arrays:arrays + 2 * segments])
        starts_at = arrays + 2 * segments + 2
        starts = struct.unpack(">%dH" % segments, data[starts_at:starts_at + 2 * segments])
        deltas = struct.unpack(">%dh" % segments, data[starts_at + 2 * segments:starts_at + 4 * segments])
        ranges_at = starts_at + 4 * segments
        ranges = struct.unpack(">%dH" % segments, data[ranges_at:ranges_at + 2 * segments])
        glyphs = {}
        for i, (start, end, delta, range_offset) in enumerate(zip(starts, ends, deltas, ranges)):
            for code in range(start, min(end, 0xFFFE) + 1):
                if range_offset:
                    at = ranges_at + 2 * i + range_offset + 2 * (code - start)
                    glyph = struct.unpack(">H", data[at:at + 2])[0]
                    glyph = (glyph + delta) % 65536 if glyph else 0
                else:
                    glyph = (code + delta) % 65536
                glyphs[code] = glyph
        return glyphs

    def pdf_objects(self, first):
        """Font, descriptor and font-file objects, numbered from `first`."""
        packed = zlib.compress(self.data)
        widths = b" ".join(b"%d" % self.widths[bytes([c]).decode("cp1252", "replace")]
                           for c in range(FIRST_CHAR, LAST_CHAR + 1))
        name = self.name.encode("ascii")
        return [
            b"<< /Type /Font /Subtype /TrueType /BaseFont /%s /FirstChar %d /LastChar %d /Widths [%s] "
            b"/Encoding /WinAnsiEncoding /FontDescriptor %d 0 R >>"
            % (name, FIRST_CHAR, LAST_CHAR, widths, first + 1),
            b"<< /Type /FontDescriptor /FontName /%s /Flags 32 /FontBBox [%d %d %d %d] /ItalicAngle %g "
            b"/Ascent %d /Descent %d /CapHeight %d /StemV 80 /FontFile2 %d 0 R >>"
            % (name, *self.bbox, self.italic_angle, self.ascent, self.descent, self.cap_height, first + 2),
            b"<< /Length %d /Length1 %d /Filter /FlateDecode >>\nstream\n" % (len(packed), len(self.data))
            + packed + b"\nendstream",
        ]


# Atkinson Hyperlegible (SIL OFL 1.1) keeps l, I and 1 distinct for reading at a distance: F1 names,
# F2 letter headings, F3 index numbers (monospaced so they line up). Helvetica sets the title (F4) and
# subtitle and footer (F5).
FONTS = {
    "F1": TrueTypeFont(FONT_DIR / "AtkinsonHyperlegible-Regular.ttf"),
    "F2": TrueTypeFont(FONT_DIR / "AtkinsonHyperlegible-Bold.ttf"),
    "F3": TrueTypeFont(FONT_DIR / "AtkinsonHyperlegibleMono-Regular.ttf"),
    "F4": Base14Font("Helvetica-Bold", _HELVETICA_BOLD),
    "F5": Base14Font("Helvetica", _HELVETICA),
}


def text_width(text, font, size):
    widths = FONTS[font].widths
    return sum(widths.get(c, widths["?"]) for c in text) * size / 1000 * CONDENSE / 100


def entries(catalog=None):
    """Return (text, is_heading, index) rows and the family count; headings have no index."""
    if catalog is None:
        catalog = json.loads((ROOT / "data" / "engines.json").read_text(encoding="utf-8"))
    names = sorted(
        (e["name"] + (DAGGER if source_status.availability_label(e) == "archived_only" else ""))
        for e in catalog["engines"] if source_status.availability_label(e) in AVAILABLE
    )
    names.sort(key=source_status.name_sort_key)
    rows, current = [], None
    for index, name in enumerate(names, 1):
        initial = source_status.name_sort_key(name[0])[0].upper()
        letter = initial if initial.isalpha() else "#"
        if letter != current:
            rows.append((letter, True, None))
            current = letter
        rows.append((name, False, index))
    return rows, len(names)


def preferred_source(engine):
    """Choose an evidenced URL, favoring research and stable, corroborated repositories."""
    candidates = {}
    for code in engine["source_code"]:
        url = code["url"]
        parsed = urlsplit(url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            continue
        candidates.setdefault(url, []).append(code)
    if not candidates:
        raise ValueError(f"No HTTP(S) source URL for {engine['name']}")

    def rank(url):
        codes = candidates[url]
        parsed = urlsplit(url)
        reviewed = [c for c in codes if c["source"] in {"source-status-research", "link-review"}]
        caution = any(
            phrase in c.get("kind", "").casefold()
            for c in reviewed
            for phrase in ("site offline", "liveness not checked", "http 521",
                           "unverified", "not captured", "not all archived", "partial",
                           "not a full listing", "incomplete")
        )
        repository = parsed.hostname in {
            "github.com", "gitlab.com", "codeberg.org", "bitbucket.org",
            "git.sr.ht", "sourceforge.net",
        }
        bundled = all(c["source"] == "lucas-chess" for c in codes)
        return (
            not any(c.get("unreachable") for c in codes),
            not caution,
            bool(reviewed),
            repository and not bundled,
            len({c["source"] for c in codes}),
            parsed.scheme == "https",
        )

    # max preserves the evidence order when equally ranked.
    return max(candidates, key=rank)


def source_links(catalog):
    return {
        e["name"] + (DAGGER if source_status.availability_label(e) == "archived_only" else ""):
        preferred_source(e)
        for e in catalog["engines"] if source_status.availability_label(e) in AVAILABLE
    }


def number_width(rows, size):
    return text_width(str(max(r[2] or 0 for r in rows)), "F3", size) + size * 0.4


def row_width(row, size, numbers):
    text, heading, _ = row
    return text_width(text, "F2", size) if heading else numbers + text_width(text, "F1", size)


def layout(rows, size, page_size, title_lines):
    """Fill columns top to bottom, each as wide as its widest entry. Return pages of columns."""
    width, height = page_size
    line = size * LEADING
    usable_width = width - 2 * MARGIN
    pages, columns, column, x = [], [], [], 0.0
    first_page = True
    numbers = number_width(rows, size)

    def capacity():
        top = height - MARGIN - (title_height(size) if first_page else 0)
        return int((top - MARGIN) // line)

    def close_column():
        nonlocal column, columns, x, first_page
        col_width = max(row_width(row, size, numbers) for row in column)
        if columns and x + col_width > usable_width:
            pages.append(columns)
            columns, x, first_page = [], 0.0, False
        columns.append((x, column))
        x += col_width + GUTTER
        column = []

    for row in rows:
        limit = capacity()
        # Keep a heading with the first name below it.
        if row[1] and len(column) >= limit - 1 or len(column) >= limit:
            close_column()
        column.append(row)
    if column:
        close_column()
    if columns:
        pages.append(columns)
    return pages


def choose(rows, page_size, min_size, max_pages=None):
    if max_pages:
        # Largest size (in 0.25 pt steps) that still fits within the page limit.
        size, best = min_size, None
        while size <= MAX_SIZE and (pages := len(layout(rows, size, page_size, 2))) <= max_pages:
            best = (size, pages)
            size += 0.25
        if best is None:
            raise SystemExit(f"{min_size:g} pt needs more than {max_pages} pages; lower --min-size")
        return best
    candidates = []
    size = min_size + SIZE_RANGE
    while size >= min_size - 1e-9:
        candidates.append((len(layout(rows, size, page_size, 2)), -size))
        size -= 0.25
    pages, negative = min(candidates)
    return -negative, pages


def title_height(size):
    return size * (1.3 + 1.0) * LEADING + size * 0.4


def pdf_string(text):
    raw = text.encode("cp1252", "replace")
    return b"(" + raw.replace(b"\\", b"\\\\").replace(b"(", b"\\(").replace(b")", b"\\)") + b")"


def render(rows, count, size, page_size, out, links=None):
    width, height = page_size
    line = size * LEADING
    pages = layout(rows, size, page_size, 2)
    numbers = number_width(rows, size)
    streams, annotations = [], []
    for number, columns in enumerate(pages, 1):
        parts, page_links = [], []
        top = height - MARGIN
        if number == 1:
            title = f"Chess engines with available source code \u2014 {count:,} families"
            subtitle = (
                f"Generated {date.today().isoformat()} from data/engines.json. "
                f"{DAGGER} = archived copy only (e.g. Wayback Machine)."
            )
            # Shrink the title lines if needed so they fit the page width.
            usable = width - 2 * MARGIN
            big = size * 1.3
            title_size = min(big, usable / (text_width(title, "F4", 1) * 100 / CONDENSE))
            sub_size = min(size, usable / text_width(subtitle, "F5", 1))
            parts.append(b"BT 100 Tz /F4 %.2f Tf %.2f %.2f Td " % (title_size, MARGIN, top - big) + pdf_string(title) + b" Tj ET")
            parts.append(
                b"BT %d Tz /F5 %.2f Tf %.2f %.2f Td " % (CONDENSE, sub_size, MARGIN, top - big * LEADING - size)
                + pdf_string(subtitle) + b" Tj ET"
            )
            top -= title_height(size)
        for x, column in columns:
            parts.append(b"BT %d Tz" % CONDENSE)
            for i, (text, heading, index) in enumerate(column):
                y = top - size - i * line
                if heading:
                    parts.append(b"0 g /F2 %.2f Tf 1 0 0 1 %.2f %.2f Tm " % (size, MARGIN + x, y) + pdf_string(text) + b" Tj")
                    continue
                # Right-align the monospaced index in a gray number field.
                label = str(index)
                left = MARGIN + x + numbers - size * 0.4 - text_width(label, "F3", size)
                parts.append(b"0.45 g /F3 %.2f Tf 1 0 0 1 %.2f %.2f Tm " % (size, left, y) + pdf_string(label) + b" Tj")
                parts.append(b"0 g /F1 %.2f Tf 1 0 0 1 %.2f %.2f Tm " % (size, MARGIN + x + numbers, y)
                             + pdf_string(text) + b" Tj")
                if links is not None:
                    url = quote(links[text], safe=":/?#[]@!$&'()*+,;=%")
                    name_left = MARGIN + x + numbers
                    page_links.append(
                        b"<< /Type /Annot /Subtype /Link /Rect [%.2f %.2f %.2f %.2f] "
                        % (name_left, y - size * 0.22,
                           name_left + text_width(text, "F1", size), y + size * 0.8)
                        + b"/Border [0 0 0] /A << /S /URI /URI " + pdf_string(url) + b" >> >>"
                    )
            parts.append(b"ET")
        footer = f"{number} / {len(pages)}"
        parts.append(
            b"BT %d Tz 0.45 g /F5 6 Tf %.2f %.2f Td " % (CONDENSE, width / 2 - text_width(footer, "F5", 6) / 2, MARGIN / 2 - 2)
            + pdf_string(footer) + b" Tj ET"
        )
        streams.append(zlib.compress(b"\n".join(parts)))
        annotations.append(page_links)

    objects = [b"<< /Type /Catalog /Pages 2 0 R >>", None]
    font_refs = []
    for key, font in FONTS.items():
        font_refs.append(b"/%s %d 0 R" % (key.encode(), len(objects) + 1))
        objects += font.pdf_objects(len(objects) + 1)
    kids = []
    for stream, page_links in zip(streams, annotations):
        content = len(objects) + 1
        objects.append(b"<< /Length %d /Filter /FlateDecode >>\nstream\n" % len(stream) + stream + b"\nendstream")
        refs = []
        for annotation in page_links:
            refs.append(len(objects) + 1)
            objects.append(annotation)
        kids.append(len(objects) + 1)
        objects.append(
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 %d %d] " % page_size
            + b"/Resources << /Font << " + b" ".join(font_refs) + b" >> >> /Contents %d 0 R " % content
            + b"/Annots [" + b" ".join(b"%d 0 R" % ref for ref in refs) + b"] >>"
        )
    objects[1] = b"<< /Type /Pages /Kids [%s] /Count %d >>" % (
        b" ".join(b"%d 0 R" % k for k in kids), len(kids)
    )
    body, offsets = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n"), []
    for number, obj in enumerate(objects, 1):
        offsets.append(len(body))
        body += b"%d 0 obj\n" % number + obj + b"\nendobj\n"
    xref = len(body)
    body += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1)
    body += b"".join(b"%010d 00000 n \n" % o for o in offsets)
    body += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objects) + 1, xref)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(bytes(body))
    return len(pages)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", type=Path, default=ROOT / "data" / "source-available-engines.pdf")
    parser.add_argument("--paper", choices=sorted(PAPER), default="letter")
    parser.add_argument("--orientation", choices=["landscape", "portrait"], default="portrait")
    parser.add_argument("--min-size", type=float, default=16.0, help="Smallest font size in points (default 16)")
    parser.add_argument(
        "--max-pages", type=int, default=15,
        help="Use the largest font that fits in this many pages (default 15; 0 = fewest pages instead)",
    )
    args = parser.parse_args()
    catalog = json.loads((ROOT / "data" / "engines.json").read_text(encoding="utf-8"))
    rows, count = entries(catalog)
    portrait = PAPER[args.paper]
    page_size = portrait if args.orientation == "portrait" else (portrait[1], portrait[0])
    size, _ = choose(rows, page_size, args.min_size, args.max_pages)
    pages = render(rows, count, size, page_size, args.out, source_links(catalog))
    print(f"Wrote {args.out} ({count} families, {pages} pages, {size:g} pt)")


if __name__ == "__main__":
    main()
