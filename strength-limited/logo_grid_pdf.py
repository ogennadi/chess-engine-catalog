#!/usr/bin/env python3
"""A4 poster (at most four pages) of the strength-limited engines as a grid of logo tiles.

Each tile shows the engine's logo, its name below, and protocol, evaluation, variant
and language below that. Engines without a logo get a grey rook placeholder.

    python strength-limited/logo_grid_pdf.py logos [--refresh]
        Fetches each logo listed in strength-limited/logos.json (from a URL or the
        engine source cache in .cache/src) and normalizes it to a JPEG in .cache/logos.
        Needs Pillow; SVGs are rasterized with headless Edge or Chrome.

    python strength-limited/logo_grid_pdf.py pdf
        Reads strength-limited/strength-limited-engines.csv and the normalized logos and
        writes strength-limited/strength-limited-logos.pdf (standard library only).

The table poster (table_pdf.py) is separate and unchanged.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import urllib.request
import zlib
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT))
from names_pdf import LOGO_ROOK_PATH, pdf_string  # noqa: E402
from table_pdf import FONTS, PDF_ABBREVIATIONS, em_width, read_csv  # noqa: E402

MANIFEST = HERE / "logos.json"
SOURCE_CACHE = ROOT / ".cache" / "src"
LOGO_DIR = ROOT / ".cache" / "logos"
RAW_DIR = LOGO_DIR / "raw"
OUT = HERE / "strength-limited-logos.pdf"

A4_PORTRAIT, A4_LANDSCAPE = (595, 842), (842, 595)
MARGIN = 20
MAX_PAGES = 4
COL_GAP = 12
ROW_GAP = 14
ASPECT = 2  # logo box width / height, the 100x50 convention of engine logos
LOGO_INSET = 0.06  # padding inside the logo box, as a fraction of its height
SEPARATOR = "  \u00b7  "
META_SEPARATOR = " \u00b7 "
PLACEHOLDER_NOTE = "grey rook = no logo found"
BROWSER_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130 Safari/537.36"
BROWSERS = (
    Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
    Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
)
MIN_HEIGHT, MAX_WIDTH = 400, 1200  # normalized logo pixels


def slug(name):
    return re.sub(r"[^A-Za-z0-9]+", "-", name).strip("-")


def logo_path(name):
    return LOGO_DIR / f"{slug(name)}.jpg"


# --- logos step -------------------------------------------------------------------------------

def fetch(name, entry, refresh):
    """The raw logo file for one engine, downloaded or copied from the source cache once."""
    if "cache" in entry:
        source = SOURCE_CACHE / entry["cache"]
        suffix = source.suffix.lower()
    else:
        source = None
        suffix = Path(entry["url"].split("?")[0]).suffix.lower() or ".img"
    source_key = entry.get("url") or entry["cache"]
    raw = RAW_DIR / f"{slug(name)}-{hashlib.sha1(source_key.encode()).hexdigest()[:8]}{suffix}"
    if raw.exists() and not refresh:
        return raw
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    if source:
        shutil.copyfile(source, raw)
    else:
        request = urllib.request.Request(entry["url"], headers={"User-Agent": BROWSER_UA})
        with urllib.request.urlopen(request, timeout=60) as response:
            raw.write_bytes(response.read())
    return raw


def rasterize_svg(svg):
    """PNG bytes of an SVG, rendered by a headless Chromium browser on white."""
    browser = next((b for b in BROWSERS if b.exists()), None)
    if not browser:
        raise RuntimeError("SVG logos need Edge or Chrome")
    with tempfile.TemporaryDirectory() as tmp:
        page, shot = Path(tmp) / "logo.html", Path(tmp) / "logo.png"
        page.write_text(
            "<html><body style='margin:0;background:#fff'>"
            f"<img src='{svg.as_uri()}' style='width:100vw;height:100vh;object-fit:contain'></body></html>",
            encoding="utf-8",
        )
        subprocess.run(
            [str(browser), "--headless=new", "--disable-gpu", "--hide-scrollbars", f"--screenshot={shot}",
             "--window-size=1200,600", page.as_uri()],
            check=True, capture_output=True, timeout=60,
        )
        return shot.read_bytes()


def normalize(raw, out, crop=None):
    """Crop if asked, flatten onto white, trim white margins, scale to a printable size and save as baseline JPEG."""
    from PIL import Image, ImageChops

    data = rasterize_svg(raw) if raw.suffix == ".svg" else raw.read_bytes()
    image = Image.open(io.BytesIO(data))
    image.seek(0)
    image = image.convert("RGBA")
    if crop:
        image = image.crop(tuple(crop))
    flat = Image.new("RGB", image.size, "white")
    flat.paste(image, mask=image.getchannel("A"))
    diff = ImageChops.difference(flat, Image.new("RGB", flat.size, "white")).convert("L").point(lambda v: 255 if v > 12 else 0)
    if box := diff.getbbox():
        pad = max(2, round(min(flat.size) * 0.02))
        flat = flat.crop((max(0, box[0] - pad), max(0, box[1] - pad),
                          min(flat.width, box[2] + pad), min(flat.height, box[3] + pad)))
    scale = max(MIN_HEIGHT / flat.height, 1)
    scale = min(scale, MAX_WIDTH / flat.width) if flat.width * scale > MAX_WIDTH else scale
    if scale != 1:
        flat = flat.resize((max(1, round(flat.width * scale)), max(1, round(flat.height * scale))), Image.LANCZOS)
    out.parent.mkdir(parents=True, exist_ok=True)
    flat.save(out, "JPEG", quality=92, progressive=False)
    return flat.size


def build_logos(refresh=False):
    manifest = {k: v for k, v in json.loads(MANIFEST.read_text(encoding="utf-8")).items() if not k.startswith("_")}
    engines = {row[0] for row in read_csv()}
    for name in sorted(set(manifest) - engines):
        print(f"warning: {name} is in logos.json but not in the engine CSV")
    failures = 0
    for name in sorted(set(manifest) & engines, key=str.casefold):
        try:
            size = normalize(fetch(name, manifest[name], refresh), logo_path(name), manifest[name].get("crop"))
            print(f"{name}: {size[0]}x{size[1]}")
        except Exception as error:  # report every bad source, not just the first
            failures += 1
            print(f"{name}: FAILED ({error})")
    missing = sorted(engines - set(manifest), key=str.casefold)
    print(f"{len(manifest) - failures} logos, {failures} failed; placeholders: {', '.join(missing) or 'none'}")
    return failures


# --- pdf step ---------------------------------------------------------------------------------

def jpeg_info(data):
    """(width, height, components) from a baseline or progressive JPEG's SOF marker."""
    i = 2
    while i < len(data):
        marker, length = data[i + 1], struct.unpack(">H", data[i + 2:i + 4])[0]
        if marker in (0xC0, 0xC1, 0xC2):
            height, width = struct.unpack(">HH", data[i + 5:i + 9])
            return width, height, data[i + 9]
        i += 2 + length
    raise ValueError("no SOF marker")


def tiles():
    """(name, metadata line, logo path or None) for each engine in CSV order."""
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    result = []
    for cells in read_csv():
        name, *meta = (subs.get(c, c) for c, subs in zip(cells, PDF_ABBREVIATIONS))
        path = logo_path(cells[0])
        usable = cells[0] in manifest and path.exists()
        result.append((name, META_SEPARATOR.join(m for m in meta if m), path if usable else None))
    return result


def layout(items, page, cols):
    """Tile geometry for a page size and column count, or None if it needs more than MAX_PAGES.

    Every page uses the same row grid, justified to the page height; on page 1 the title
    and note take the top row slot(s) instead of tiles."""
    width, height = page
    usable_w, usable_h = width - 2 * MARGIN, height - 2 * MARGIN
    cell_w = (usable_w - (cols - 1) * COL_GAP) / cols
    box_h = cell_w / ASPECT
    name_size = min(cell_w * 0.13, cell_w / max(em_width(n, "F2") for n, _, _ in items))
    meta_size = min(name_size * 0.72, cell_w / max(em_width(m, "F1") for _, m, _ in items))
    cell_h = box_h + name_size * 1.45 + meta_size * 1.35
    rows = int((usable_h + ROW_GAP) // (cell_h + ROW_GAP))
    if rows < 2:
        return None
    pitch = cell_h + (usable_h - rows * cell_h) / (rows - 1)
    notes = (PLACEHOLDER_NOTE + SEPARATOR + subtitle(),)
    title_size = min(name_size * 1.6, usable_w / em_width(title(items), "F2"))
    note_size = min(max(meta_size, 7), usable_w / max(em_width(n, "F1") for n in notes))
    header_h = title_size * 1.2 + len(notes) * note_size * 1.45
    header_rows = -(-(header_h + ROW_GAP) // pitch)
    if header_rows >= rows:
        return None
    pages, remaining = [int(rows - header_rows) * cols], len(items) - int(rows - header_rows) * cols
    while remaining > 0:
        pages.append(rows * cols)
        remaining -= rows * cols
    if len(pages) > MAX_PAGES:
        return None
    return dict(page=page, cols=cols, cell_w=cell_w, box_h=box_h, cell_h=cell_h, pitch=pitch,
                name_size=name_size, meta_size=meta_size, title_size=title_size, note_size=note_size,
                notes=notes, header_h=header_h, header_rows=int(header_rows), capacity=pages)


def best_layout(items):
    """Largest tiles (then fewest pages) over both orientations and every column count that fits."""
    options = [l for page in (A4_PORTRAIT, A4_LANDSCAPE) for cols in range(1, 10)
               if (l := layout(items, page, cols))]
    return max(options, key=lambda l: (round(l["cell_w"]), -len(l["capacity"]), l["page"] == A4_PORTRAIT))


def title(items):
    return f"Chess engines that can limit their strength: {len(items)} families"


def subtitle():
    return f"generated {date.today().isoformat()}"


def text(font, x, y, value, size):
    return b"BT /%s %.2f Tf 1 0 0 1 %.2f %.2f Tm " % (font.encode(), size, x, y) + pdf_string(value) + b" Tj ET"


def centered(font, cx, y, value, size):
    return text(font, cx - em_width(value, font) * size / 2, y, value, size)


def rect(x, y, w, h):
    return b"%.2f %.2f %.2f %.2f re" % (x, y, w, h)


def placeholder(x, y, w, h):
    """Light grey box with the site logo's rook in mid grey."""
    xs, ys = [p[0] for p in LOGO_ROOK_PATH], [p[1] for p in LOGO_ROOK_PATH]
    scale = h * 0.62 / (max(ys) - min(ys))
    left = x + w / 2 - (max(xs) + min(xs)) / 2 * scale
    top = y + h / 2 + (max(ys) + min(ys)) / 2 * scale
    path = b" ".join(b"%.2f %.2f %s" % (left + px * scale, top - py * scale, b"m" if i == 0 else b"l")
                     for i, (px, py) in enumerate(LOGO_ROOK_PATH))
    return b"q 0.93 g " + rect(x, y, w, h) + b" f 0.72 g " + path + b" h f Q"


def render(items):
    geo = best_layout(items)
    width, height = geo["page"]
    cols, cell_w, box_h, cell_h = geo["cols"], geo["cell_w"], geo["box_h"], geo["cell_h"]
    name_size, meta_size = geo["name_size"], geo["meta_size"]
    inset = box_h * LOGO_INSET

    images, image_refs = [], {}
    for _, _, path in items:
        if path and path not in image_refs:
            data = path.read_bytes()
            image_refs[path] = len(images)
            images.append((data, *jpeg_info(data)))

    streams, start = [], 0
    for number, capacity in enumerate(geo["capacity"], 1):
        chunk = items[start:start + capacity]
        start += capacity
        parts, top, first_row = [], height - MARGIN, 0
        if number == 1:
            # Title and note, vertically centred in the row slot(s) they replace.
            first_row = geo["header_rows"]
            area = first_row * geo["pitch"] - (geo["pitch"] - cell_h)
            y = top - (area - geo["header_h"]) / 2 - geo["title_size"]
            parts.append(b"0 g " + text("F2", MARGIN, y, title(items), geo["title_size"]))
            y -= geo["title_size"] * 0.2
            for note in geo["notes"]:
                y -= geo["note_size"] * 1.45
                parts.append(b"0.3 g " + text("F1", MARGIN, y, note, geo["note_size"]))
        for i, (name, meta, path) in enumerate(chunk):
            row, col = divmod(i, cols)
            x = MARGIN + col * (cell_w + COL_GAP)
            box_y = top - (first_row + row) * geo["pitch"] - box_h
            if path:
                _, w, h, _ = images[image_refs[path]]
                scale = min((cell_w - 2 * inset) / w, (box_h - 2 * inset) / h)
                iw, ih = w * scale, h * scale
                parts.append(b"q %.3f 0 0 %.3f %.2f %.2f cm /Im%d Do Q" % (
                    iw, ih, x + (cell_w - iw) / 2, box_y + (box_h - ih) / 2, image_refs[path]))
            else:
                parts.append(placeholder(x, box_y, cell_w, box_h))
            cx = x + cell_w / 2
            name_y = box_y - name_size * 1.1
            parts.append(b"0 g " + centered("F2", cx, name_y, name, name_size))
            parts.append(b"0.3 g " + centered("F1", cx, name_y - meta_size * 1.35, meta, meta_size))
        streams.append(zlib.compress(b"\n".join(parts)))

    objects = [b"<< /Type /Catalog /Pages 2 0 R >>", None]
    font_refs = []
    for key, font in FONTS.items():
        font_refs.append(b"/%s %d 0 R" % (key.encode(), len(objects) + 1))
        objects += font.pdf_objects(len(objects) + 1)
    image_names = []
    for n, (data, w, h, components) in enumerate(images):
        space = b"/DeviceGray" if components == 1 else b"/DeviceRGB"
        objects.append(b"<< /Type /XObject /Subtype /Image /Width %d /Height %d /ColorSpace %s "
                       b"/BitsPerComponent 8 /Filter /DCTDecode /Interpolate true /Length %d >>\nstream\n"
                       % (w, h, space, len(data)) + data + b"\nendstream")
        image_names.append(b"/Im%d %d 0 R" % (n, len(objects)))
    resources = (b"/Resources << /Font << " + b" ".join(font_refs) + b" >> /XObject << "
                 + b" ".join(image_names) + b" >> >>")
    kids = []
    for stream in streams:
        objects.append(b"<< /Length %d /Filter /FlateDecode >>\nstream\n" % len(stream) + stream + b"\nendstream")
        content = len(objects)
        kids.append(content + 1)
        objects.append(b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 %d %d] " % geo["page"]
                       + resources + b" /Contents %d 0 R >>" % content)
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
    orientation = "portrait" if geo["page"] == A4_PORTRAIT else "landscape"
    return len(streams), cols, orientation, sum(1 for *_, p in items if p)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("step", choices=("logos", "pdf"), help="logos: fetch and normalize; pdf: draw the poster")
    parser.add_argument("--refresh", action="store_true", help="re-download logos already fetched")
    args = parser.parse_args()
    if args.step == "logos":
        sys.exit(1 if build_logos(args.refresh) else 0)
    items = tiles()
    pages, cols, orientation, logos = render(items)
    print(f"Wrote {OUT.relative_to(ROOT)}: {len(items)} families ({logos} logos), "
          f"{cols} columns, {orientation}, {pages} page(s)")


if __name__ == "__main__":
    main()
