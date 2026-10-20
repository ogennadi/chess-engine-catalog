"""Write a compact, printable PDF listing every family whose source code is available.

    python names_pdf.py [--out PATH] [--paper letter|a4] [--orientation portrait|landscape] [--min-size PT]

Reads data/engines.json (run collect.py first). Families whose availability is linked,
available, or archived_only are numbered and listed alphabetically under letter headings,
in as many columns as fit (portrait pages by default). The default 16 pt minimum is about the
smallest text that 20/20 vision can read from 9 feet; the largest size up to 4 pt above
it that still gives the fewest pages is chosen. Uses only the standard library and the PDF base-14 Helvetica fonts,
horizontally condensed. The output is generated, so it is gitignored.
"""

import argparse
import json
import zlib
from datetime import date
from pathlib import Path

import source_status

ROOT = Path(__file__).resolve().parent
AVAILABLE = {"linked", "available", "archived_only"}
PAPER = {"letter": (612, 792), "a4": (595, 842)}
MARGIN = 18
GUTTER = 6
LEADING = 1.13
CONDENSE = 85
SIZE_RANGE = 4.0
# Upper bound so short lists do not grow until a single row no longer fits a page.
MAX_SIZE = 48.0
DAGGER = "\u2020"

# Helvetica and Helvetica-Bold advance widths (1/1000 em) for ASCII 32-126, from the Adobe AFM files.
_REGULAR = (
    "278 278 355 556 556 889 667 191 333 333 389 584 278 333 278 278 556 556 556 556 556 556 556 556 "
    "556 556 278 278 584 584 584 556 1015 667 667 722 722 667 611 778 722 278 500 667 556 833 722 778 "
    "667 778 722 667 611 722 667 944 667 667 611 278 278 278 469 556 333 556 556 500 556 556 278 556 "
    "556 222 222 500 222 833 556 556 556 556 333 500 278 556 500 722 500 500 500 334 260 334 584"
)
_BOLD = (
    "278 333 474 556 556 889 722 238 333 333 389 584 278 333 278 278 556 556 556 556 556 556 556 556 "
    "556 556 333 333 584 584 584 611 975 722 722 722 722 667 611 778 722 278 556 722 611 833 722 778 "
    "667 778 722 667 611 722 667 944 667 667 611 333 278 333 584 556 333 556 611 556 611 556 333 611 "
    "611 278 278 556 278 889 611 611 611 611 389 556 333 611 556 778 556 556 500 389 280 389 584"
)
WIDTHS = {
    font: {chr(32 + i): int(w) for i, w in enumerate(table.split())}
    for font, table in (("F1", _REGULAR), ("F2", _BOLD))
}


def text_width(text, font, size):
    widths = WIDTHS[font]
    return sum(widths.get(c, 556) for c in text) * size / 1000 * CONDENSE / 100


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


def number_width(rows, size):
    return text_width(str(max(r[2] or 0 for r in rows)), "F1", size) + size * 0.4


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


def render(rows, count, size, page_size, out):
    width, height = page_size
    line = size * LEADING
    pages = layout(rows, size, page_size, 2)
    numbers = number_width(rows, size)
    digits = text_width("0", "F1", size)
    streams = []
    for number, columns in enumerate(pages, 1):
        parts = []
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
            title_size = min(big, usable / (text_width(title, "F2", 1) * 100 / CONDENSE))
            sub_size = min(size, usable / text_width(subtitle, "F1", 1))
            parts.append(b"BT 100 Tz /F2 %.2f Tf %.2f %.2f Td " % (title_size, MARGIN, top - big) + pdf_string(title) + b" Tj ET")
            parts.append(
                b"BT %d Tz /F1 %.2f Tf %.2f %.2f Td " % (CONDENSE, sub_size, MARGIN, top - big * LEADING - size)
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
                # Right-align the index (all digits share one width) in a gray number field.
                label = str(index)
                left = MARGIN + x + numbers - size * 0.4 - digits * len(label)
                parts.append(b"0.45 g /F1 %.2f Tf 1 0 0 1 %.2f %.2f Tm " % (size, left, y) + pdf_string(label) + b" Tj")
                parts.append(b"0 g 1 0 0 1 %.2f %.2f Tm " % (MARGIN + x + numbers, y) + pdf_string(text) + b" Tj")
            parts.append(b"ET")
        footer = f"{number} / {len(pages)}"
        parts.append(
            b"BT %d Tz 0.45 g /F1 6 Tf %.2f %.2f Td " % (CONDENSE, width / 2 - text_width(footer, "F1", 6) / 2, MARGIN / 2 - 2)
            + pdf_string(footer) + b" Tj ET"
        )
        streams.append(zlib.compress(b"\n".join(parts)))

    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        None,
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>",
    ]
    kids = []
    for stream in streams:
        content = len(objects) + 1
        objects.append(b"<< /Length %d /Filter /FlateDecode >>\nstream\n" % len(stream) + stream + b"\nendstream")
        kids.append(len(objects) + 1)
        objects.append(
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 %d %d] " % page_size
            + b"/Resources << /Font << /F1 3 0 R /F2 4 0 R >> >> /Contents %d 0 R >>" % content
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
    rows, count = entries()
    portrait = PAPER[args.paper]
    page_size = portrait if args.orientation == "portrait" else (portrait[1], portrait[0])
    size, _ = choose(rows, page_size, args.min_size, args.max_pages)
    pages = render(rows, count, size, page_size, args.out)
    print(f"Wrote {args.out} ({count} families, {pages} pages, {size:g} pt)")


if __name__ == "__main__":
    main()
