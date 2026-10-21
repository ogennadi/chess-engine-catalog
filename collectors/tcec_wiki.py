"""Read the TCEC wiki's Engines and authors table and Current Engine Status list."""

import html
import re
from urllib.parse import urlsplit


PAGE_URL = "https://wiki.chessdom.org/Engines_and_authors"
STATUS_URL = "https://wiki.chessdom.org/Current_Engine_Status"
WIKI = "https://wiki.chessdom.org/"
FORGES = ("github.com", "gitlab.com", "codeberg.org", "bitbucket.org", "git.sr.ht")
# Reviewed homepages whose own pages link the engine's source repository.
HOMEPAGE_SOURCE = {
    "https://moonfish.neocities.org": "https://git.sr.ht/~zamfofex/moonfish",
}
# Reviewed repositories named in TCEC questionnaires for engines that appear
# only on Current Engine Status, which itself has no repository links.
QUESTIONNAIRE_SOURCE = {
    "CatGPT": ("https://github.com/butter76/CatGPT", "CatGPT_questionnaire_20260525"),
    "molly": ("https://codeberg.org/latuernich/molly", "Molly_questionnaire_20251015"),
    "Soul": ("https://github.com/Aethdv/Soul", "Soul_questionnaire_20260620"),
    "SSSimpler": ("https://github.com/Kirill020708/SSSimpler", "SSSimpler_questionnaire_20260617"),
}
SKIPPED_STATUS_SECTIONS = {"Contents", "Suggested engines", "See also"}
HEADING_OR_ITEM = re.compile(r"<h[23]\b[^>]*>(.*?)</h[23]>|<li>(.*?)</li>", re.S)
TABLE = re.compile(r"<table\b.*?</table>", re.S)
ROW = re.compile(r"<tr\b.*?</tr>", re.S)
CELL = re.compile(r"<t[dh]\b[^>]*>(.*?)</t[dh]>", re.S)
LINK = re.compile(r'<a\b[^>]*\bhref="([^"]+)"')


def _text(cell):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", cell))).strip()


def _family(label):
    """Drop footnote stars and the page's "Allie... (engine)"/"...Stein (network)" styling."""
    name = re.sub(r"\((?:engine|network)\)", "", label.rstrip("*"))
    return name.replace("...", "").strip()


def parse(text):
    tables = [t for t in TABLE.findall(text) if "Programming language" in t]
    if not tables:
        raise ValueError(f"No Engine Information table on {PAGE_URL}")
    rows = []
    for row in ROW.findall(tables[0]):
        cells = CELL.findall(row)
        if len(cells) < 4 or _text(cells[0]) == "Engine":
            continue
        label = _text(cells[0])
        family = _family(label)
        if not family:
            raise ValueError(f"Empty engine name in TCEC wiki row: {label!r}")
        details = [_text(cells[1]), _text(cells[2])]
        if label.endswith("**"):
            details.append("4k event engine (fits in 4096 bytes)")
        item = {
            "family": family, "label": label, "url": PAGE_URL,
            "comment": "; ".join(d for d in details if d), "code_urls": [],
        }
        if _text(cells[3]):
            item["author"] = _text(cells[3])
        links = LINK.findall(cells[0])
        if links:
            project_url = html.unescape(links[0]).strip().rstrip("/")
            item["project_url"] = project_url
            parts = urlsplit(project_url)
            if project_url.casefold() in HOMEPAGE_SOURCE:
                item["code_urls"].append({
                    "url": HOMEPAGE_SOURCE[project_url.casefold()], "evidence_url": project_url,
                })
            elif parts.hostname in FORGES and len(parts.path.strip("/").split("/")) >= 2:
                item["code_urls"].append({"url": project_url, "evidence_url": PAGE_URL})
        rows.append(item)
    if not rows:
        raise ValueError(f"TCEC wiki Engine Information table on {PAGE_URL} is empty")
    return rows


def parse_status(text):
    """Rows for every bolded engine on Current Engine Status, including not-playing sections."""
    start = text.find('id="mw-content-text"')
    if start < 0:
        raise ValueError(f"No page content on {STATUS_URL}")
    rows, section, anchor = [], None, ""
    for match in HEADING_OR_ITEM.finditer(text, start):
        heading, item = match.groups()
        if heading is not None:
            section = re.sub(r"\[\s*edit\s*\]", "", _text(heading)).strip()
            ids = re.findall(r'\bid="([^"]+)"', heading)
            anchor = ids[0] if ids else ""
            continue
        if section is None or section in SKIPPED_STATUS_SECTIONS:
            continue
        bold = re.match(r"\s*<b>(.*?)</b>", item, re.S)
        if not bold:
            continue
        label = _text(bold.group(1))
        family = label.split(" ")[0]
        if not family:
            continue
        row = {
            "family": family, "label": label,
            "url": STATUS_URL + ("#" + anchor if anchor else ""),
            "section": section, "comment": _text(item)[len(label):].strip(), "code_urls": [],
        }
        if not row["comment"]:
            del row["comment"]
        if family in QUESTIONNAIRE_SOURCE:
            repository, page = QUESTIONNAIRE_SOURCE[family]
            row["code_urls"].append({"url": repository, "evidence_url": WIKI + page})
        rows.append(row)
    if not rows:
        raise ValueError(f"No engines found on {STATUS_URL}")
    return rows


def collect(fetch):
    return parse(fetch(PAGE_URL)) + parse_status(fetch(STATUS_URL))
