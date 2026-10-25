#!/usr/bin/env python3
"""A4 table, in type large enough to read from about 9 ft, of engine families that can limit their strength.

Two steps, so the table can be reviewed and hand-edited before printing:

    python strength-limited/table_pdf.py csv
        Reads data/engine-options.csv (a local, untracked working file) and
        writes strength-limited/strength-limited-engines.csv with columns for
        protocol, evaluation, Chess960 support and language, plus the
        strength options and their source permalink (used by publish.py's
        family pages, not printed).

    python strength-limited/table_pdf.py pdf
        Turns that reviewed CSV into strength-limited/strength-limited-engines.pdf.

Stockfish ports, Carballo (near-duplicate of Karballo) and engines whose
strength option is declared but never applied are skipped. Engines in
CONSOLE_ONLY have no protocol strength option but a level set by a console
command or startup switch; their protocol is marked with "*". The
language comes from LANGUAGE_OVERRIDES, or else from the notes column.

No third-party packages.
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
import zlib
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
from names_pdf import _HELVETICA, _HELVETICA_BOLD, Base14Font, pdf_string  # noqa: E402

CSV_PATH = ROOT / "data" / "engine-options.csv"
TABLE_CSV = HERE / "strength-limited-engines.csv"
OUT = HERE / "strength-limited-engines.pdf"

# Stockfish ports and forks (per their review notes); Fairy-Stockfish and Stockfish itself stay.
# Carballo is left out because Karballo is its Kotlin port. Morphy (danem) and OliveChess declare
# UCI_LimitStrength/UCI_Elo but never apply them; PolarChess's setoption bug means UCI_Elo never takes effect.
EXCLUDE = {
    "Alexander", "asmFish", "Brainfish", "Brainlearn", "CFish", "CorChess", "DON", "Fat Fritz", "Fat Titz",
    "Nextfish", "Portfish", "Revolution", "Stockfish BAE", "Stockfish-js", "Strato III",
    "Carballo", "Morphy (danem)", "OliveChess", "PolarChess",
}
# No UCI/xboard strength option, but a weaker level via a console command or startup switch
# (see section 5 of strength-limiting-methods.md).
CONSOLE_ONLY = {"Beowulf", "ChessbotX", "Crafty", "Cupcake", "KnightCap", "Phalanx", "Puca", "SilChess"}
CONSOLE_MARK = "*"

A4_PORTRAIT, A4_LANDSCAPE = (595, 842), (842, 595)
MARGIN = 20
MAX_SIZE = 32  # body text; ~0.3 in cap height, readable from about 9 ft
MAX_PAGES = 2
ROW_FACTOR = 1.25  # row height in ems
PAD = 0.45  # gap between columns, in ems
FONTS = {"F1": Base14Font("Helvetica", _HELVETICA), "F2": Base14Font("Helvetica-Bold", _HELVETICA_BOLD)}
HEADERS = ("Engine", "Protocol", "Eval", "Variant", "Language")
# Extra CSV-only columns for the website's family pages; the PDF doesn't print them.
DETAIL_HEADERS = ("Options", "Options source")
# The PDF uses short labels so the large type fits; the legend on page 1 explains them. The CSV keeps full text.
PDF_HEADERS = ("#", "Engine", "Proto", "Eval", "Var", "Lang")
PDF_ABBREVIATIONS = (
    {"Sjaak (Glebbeek)": "Sjaak II"},
    {"UCI, xboard": "UCI/XB", "xboard, UCI": "UCI/XB", "xboard": "XB", "UCI, xboard*": "UCI/XB*", "xboard*": "XB*"},
    {"HCE + NN": "HCE+NN"},
    {"Chess960 et al.": "960+", "Chess960": "960", "Others": "Oth"},
    {"Python, JavaScript": "Py/JS"},
)
LEGEND = (
    "XB = xboard \u00b7 * = level set only by console command or startup switch",
    "960 = Chess960 \u00b7 960+ = Chess960 and other variants \u00b7 Oth = other variants only",
)
DASH = "\u2014"
# Engines that play nonstandard variants besides Chess960 (from options/notes in engine-options.csv).
OTHER_VARIANTS = {"ChessV", "Fairy-Stockfish", "Minic", "Peras", "PychessEngine", "Reglisse", "Sjaak (Glebbeek)"}

NEGATIVE = re.compile(r"(none|no\b|unknown|probably)", re.I)

# Earliest mention in the notes wins.
LANGUAGES = (
    (r"C\+\+", "C++"),
    (r"C#|\.NET", "C#"),
    (r"\bC (?:engine|port|program)\b", "C"),
    (r"\bJava\b", "Java"),
    (r"\bKotlin\b", "Kotlin"),
    (r"\bRust\b", "Rust"),
    (r"\bZig\b", "Zig"),
    (r"\bNim\b", "Nim"),
    (r"\bGo (?:engine|port)\b", "Go"),
    (r"\bPython\b", "Python"),
    (r"\bJavaScript\b", "JavaScript"),
    (r"\bEmscripten\b|asm\.js", "JavaScript (asm.js)"),
    (r"\bAssembly\b", "Assembly"),
)
# Families whose notes don't name a language (or name it ambiguously): the GitHub repository's
# primary language, or for archives the source file cited in options_source_url (checked against
# the archive's file types). These take precedence over the notes.
LANGUAGE_OVERRIDES = {
    "Annie": "Nim",
    "Arasan": "C++",
    "Beowulf": "C",
    "ChessbotX": "Java",
    "Crafty": "C",
    "CT800": "C",
    "Cupcake": "Java",
    "KnightCap": "C",
    "Phalanx": "C",
    "Puca": "C",
    "SilChess": "C++",
    "CuckooChess": "Java",
    "Demolito": "C",
    "DiscoCheck": "C++",
    "Eguzki": "C++",
    "EXchess": "C++",
    "Fairy-Stockfish": "C++",
    "Galjoen": "C++",
    "MadChess": "C#",
    "Mayhem": "C++",
    "MeikeChess": "C++",
    "Minic": "C++",
    "Morphy (danem)": "C++",
    "OliveChess": "C++",
    "Patricia": "C++",
    "PolarChess": "C++",
    "PychessEngine": "Python",
    "PyTuroChamp": "Python",
    # The repo has a Python and a JavaScript version of the engine.
    "Reglisse": "Python, JavaScript",
    "Sjaak (Glebbeek)": "C++",
    "Stockfish": "C++",
    "Texel": "C++",
}

PROTOCOLS = {"uci": "UCI", "xboard": "xboard", "gui": "GUI", "nonstandard-cli": "CLI", "library": "library"}
EVALUATIONS = {"hce": "HCE", "nn": "NN", "both": "HCE + NN", "other": "Other", "unknown": "Unknown"}


def has(value):
    value = value.strip()
    return bool(value) and not NEGATIVE.match(value)


def language(notes, family):
    if family in LANGUAGE_OVERRIDES:
        return LANGUAGE_OVERRIDES[family]
    found = [(m.start(), name) for pattern, name in LANGUAGES for m in [re.search(pattern, notes)] if m]
    return min(found)[1] if found else DASH


def protocol(value, family=""):
    tokens = [re.split(r"[\s(,]", t.strip(), maxsplit=1)[0].lower() for t in value.split(";")]
    names = [PROTOCOLS.get(t, t) for t in tokens if t]
    # A built-in GUI isn't a protocol; keep it only when it's the sole way to play the engine.
    if len(names) > 1:
        names = [n for n in names if n != "GUI"]
    if family in CONSOLE_ONLY:
        # The mark stands in for the console/command line, which is how these engines are weakened.
        names = [n for n in names if n in ("UCI", "xboard")]
        return ", ".join(names) + CONSOLE_MARK
    return ", ".join(names) or DASH


def evaluation(value):
    word = re.split(r"[\s(:,]", value.strip(), maxsplit=1)[0].lower()
    return EVALUATIONS.get(word, word or DASH)


def variant(r):
    chess960, others = has(r["chess960"]), r["family"] in OTHER_VARIANTS
    if chess960:
        return "Chess960 et al." if others else "Chess960"
    return "Others" if others else ""


def rows():
    with CSV_PATH.open(encoding="utf-8") as f:
        families = [
            r for r in csv.DictReader(f)
            if (has(r["strength_limiting"]) or r["family"] in CONSOLE_ONLY) and r["family"] not in EXCLUDE
        ]
    families.sort(key=lambda r: r["family"].casefold())
    return [
        (r["family"], protocol(r["protocols"], r["family"]), evaluation(r["evaluation"]),
         variant(r), language(r["notes"], r["family"]), r["strength_limiting"].strip(),
         r["options_source_url"].strip())
        for r in families
    ]


def text(font, x, y, value, size):
    return b"/%s %.2f Tf 1 0 0 1 %.2f %.2f Tm " % (font.encode(), size, x, y) + pdf_string(value) + b" Tj"


def em_width(value, font):
    widths = FONTS[font].widths
    return sum(widths.get(c, widths["?"]) for c in value) / 1000


def layout(numbered, page, size=None):
    """Font size, column widths and row split for one page orientation."""
    width, height = page
    ems = [max(em_width(h, "F2"), *(em_width(r[i], "F1") for r in numbered)) + PAD for i, h in enumerate(PDF_HEADERS)]
    size = min(size or MAX_SIZE, MAX_SIZE, (width - 2 * MARGIN) / sum(ems))
    row = size * ROW_FACTOR
    title_size, note_size = size * 1.1, size * 0.5
    title_height = title_size + (len(LEGEND) + 1) * note_size * 1.5 + size * 0.6
    first = int((height - 2 * MARGIN - title_height) // row) - 1
    rest = int((height - 2 * MARGIN) // row) - 1
    pages_needed = 1 + max(0, -(-(len(numbered) - first) // rest))
    # Spread rows evenly instead of leaving a short last page; page 1 also holds the title.
    first_take = min(first, -(-len(numbered) // pages_needed))
    later = pages_needed - 1
    pages = [numbered[:first_take]]
    remaining = numbered[first_take:]
    for p in range(later):
        take = -(-len(remaining) // (later - p))
        pages.append(remaining[:take])
        remaining = remaining[take:]
    return dict(page=page, size=size, widths=[e * size for e in ems], row=row, title_size=title_size,
                note_size=note_size, title_height=title_height, pages=pages)


def fitted(numbered, page):
    """The largest layout for this orientation that needs at most MAX_PAGES pages."""
    size = MAX_SIZE
    while (result := layout(numbered, page, size))["size"] > 6 and len(result["pages"]) > MAX_PAGES:
        size = result["size"] - 0.1
    return result


def render(table):
    title = f"Chess engines that can limit their strength: {len(table)} families"
    subtitle = f"Stockfish ports, Carballo and non-functional limits omitted \u00b7 generated {date.today().isoformat()}"
    numbered = [
        (str(n), *(subs.get(c, c) for c, subs in zip(cells, PDF_ABBREVIATIONS)))
        for n, cells in enumerate(table, 1)
    ]
    # Whichever orientation allows the larger type (to the nearest point); portrait wins a tie.
    best = max((fitted(numbered, p) for p in (A4_PORTRAIT, A4_LANDSCAPE)),
               key=lambda l: (round(l["size"]), -len(l["pages"])))
    width, height = best["page"]
    size, widths, row, pages = best["size"], best["widths"], best["row"], best["pages"]
    usable = width - 2 * MARGIN
    title_size = min(best["title_size"], usable / em_width(title, "F2"))
    note_size = min(best["note_size"], usable / max(em_width(n, "F1") for n in (*LEGEND, subtitle)))
    table_width = sum(widths)
    streams = []
    for number, chunk in enumerate(pages, 1):
        parts = []
        top = height - MARGIN
        if number == 1:
            parts.append(b"BT 0 g " + text("F2", MARGIN, top - title_size, title, title_size) + b" ET")
            for k, note in enumerate((*LEGEND, subtitle), 1):
                y = top - title_size - note_size * 1.5 * k
                parts.append(b"BT 0.3 g " + text("F1", MARGIN, y, note, note_size) + b" ET")
            top -= best["title_height"]
        # Header row background, then zebra-striped body rows.
        parts.append(b"0.82 g %.2f %.2f %.2f %.2f re f" % (MARGIN, top - row, table_width, row))
        for i in range(1, len(chunk), 2):
            parts.append(b"0.93 g %.2f %.2f %.2f %.2f re f" % (MARGIN, top - row * (i + 2), table_width, row))
        parts.append(b"BT 0 g")
        for i, cells in enumerate([PDF_HEADERS, *chunk]):
            y = top - row * (i + 1) + (row - size * 0.72) / 2
            x = MARGIN + size * PAD / 2
            for cell, w in zip(cells, widths):
                parts.append(text("F2" if i == 0 else "F1", x, y, cell, size))
                x += w
        parts.append(b"ET")
        streams.append(zlib.compress(b"\n".join(parts)))

    objects = [b"<< /Type /Catalog /Pages 2 0 R >>", None]
    font_refs = []
    for key, font in FONTS.items():
        font_refs.append(b"/%s %d 0 R" % (key.encode(), len(objects) + 1))
        objects += font.pdf_objects(len(objects) + 1)
    kids = []
    for stream in streams:
        objects.append(b"<< /Length %d /Filter /FlateDecode >>\nstream\n" % len(stream) + stream + b"\nendstream")
        content = len(objects)
        kids.append(content + 1)
        objects.append(
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 %d %d] " % best["page"]
            + b"/Resources << /Font << " + b" ".join(font_refs) + b" >> >> /Contents %d 0 R >>" % content
        )
    objects[1] = b"<< /Type /Pages /Kids [%s] /Count %d >>" % (b" ".join(b"%d 0 R" % k for k in kids), len(kids))
    body, offsets = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n"), []
    for n, obj in enumerate(objects, 1):
        offsets.append(len(body))
        body += b"%d 0 obj\n" % n + obj + b"\nendobj\n"
    xref = len(body)
    body += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1)
    body += b"".join(b"%010d 00000 n \n" % o for o in offsets)
    body += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objects) + 1, xref)
    OUT.write_bytes(bytes(body))
    return len(pages)


def write_csv(table):
    with TABLE_CSV.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(HEADERS + DETAIL_HEADERS)
        writer.writerows(table)


def read_csv():
    with TABLE_CSV.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f)
        next(reader)
        return [tuple(row[:len(HEADERS)]) for row in reader if row]


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("step", choices=("csv", "pdf"), help="csv: build the table for review; pdf: print it")
    args = parser.parse_args()
    if args.step == "csv":
        table = rows()
        write_csv(table)
        print(f"Wrote {TABLE_CSV.relative_to(ROOT)}: {len(table)} families")
    else:
        table = read_csv()
        pages = render(table)
        print(f"Wrote {OUT.relative_to(ROOT)}: {len(table)} families on {pages} page(s)")


if __name__ == "__main__":
    main()
