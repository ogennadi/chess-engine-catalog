"""Collect engine rows from the archived Frank's Chess Page table."""

import re
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit, urlunsplit


SOURCE_URL = (
    "https://web.archive.org/web/20260212005235/"
    "https://www.amateurschach.de/main/_engines.htm"
)
ORIGINAL_URL = "https://www.amateurschach.de/main/_engines.htm"
SNAPSHOT = "20260212005235"
MULTIPLE_FAMILIES = {
    "Clarity": ("Clarity", "Anura"),
    "Calvin": ("Calvin", "Hobbes"),
    "Starzix": ("Starzix", "Starlynn"),
    "Stash": ("Stash", "Vault"),
    "rofChade": ("rofChade", "PeSTO"),
}
FAMILY_ALIASES = {
    "Rykba": "Rybka",
    "Deep iCE": "iCE",
    "Gödel": "Godel",
    "Leela Chess Zero": "Leela Chess",
    "Slow Chess Blitz": "Slow Chess",
    "Carp + Carp": "Carp",
}


def original_url(url):
    url = urljoin(SOURCE_URL, url)
    while True:
        match = re.match(r"https?://web\.archive\.org/web/\d+[a-z_]*/(https?://.+)", url)
        if not match:
            return url
        url = match.group(1)


def code_url(url):
    parsed = urlsplit(original_url(url))
    parts = parsed.path.strip("/").split("/")
    if parsed.netloc.lower() in ("github.com", "gitlab.com", "codeberg.org", "bitbucket.org"):
        if len(parts) >= 2 and all(parts[:2]) and not parts[1].endswith(".github.io"):
            return urlunsplit((
                parsed.scheme, parsed.netloc, "/" + "/".join(parts[:2]), "", "",
            ))
    if parsed.netloc.lower() == "sourceforge.net" and len(parts) >= 2:
        if parts[0] == "projects":
            return f"https://sourceforge.net/projects/{parts[1]}/"
        if parts[0] == "p":
            return original_url(url)
    return None


class EngineTable(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.rows = []
        self.cells = []
        self.cell = None
        self.link = None

    def handle_starttag(self, tag, attrs):
        if tag == "tr":
            self.cells = []
        elif tag in ("td", "th"):
            self.cell = {"text": "", "links": []}
        elif tag == "a" and self.cell is not None:
            self.link = {"url": dict(attrs).get("href", ""), "text": ""}
        elif tag == "br" and self.cell is not None:
            self.cell["text"] += " "

    def handle_data(self, data):
        if self.cell is not None:
            self.cell["text"] += data
        if self.link is not None:
            self.link["text"] += data

    def handle_endtag(self, tag):
        if tag == "a" and self.link is not None:
            self.link["text"] = " ".join(self.link["text"].split())
            if self.cell is not None:
                self.cell["links"].append(self.link)
            self.link = None
        elif tag in ("td", "th") and self.cell is not None:
            self.cell["text"] = " ".join(self.cell["text"].split())
            self.cells.append(self.cell)
            self.cell = None
        elif tag == "tr":
            if len(self.cells) == 8 and self.cells[0]["links"]:
                self.rows.append(self.cells)
            self.cells = []


def clean_name(text):
    text = re.sub(r"\*\s*\d+", "", text)
    text = text.replace("\u00b2", "").strip()
    text = re.sub(r"\s*\((?:Wayback|own site)\)", "", text, flags=re.I)
    text = re.sub(r"\s+(?:D/L|aka LTChess)\s*$", "", text)
    text = re.sub(r"\s+-\s+(?:Pre|dev|HCE|archived).*$", "", text, flags=re.I)
    text = re.sub(r"\s+-\s+tags$", "", text, flags=re.I)
    return " ".join(text.split())


def row_families(cell):
    text = cell["text"]
    primary = clean_name(text.split(",", 1)[0])
    if primary == "Stockfish":
        for derivative in ("Sting", "Crystal", "Modjo", "ShashChess", "Alexander"):
            if re.search(r"\b" + derivative + r"\b", text):
                return [derivative]
    if primary == "Gull" and re.search(r"\bRoc2?\b", text):
        return ["Roc", "Roc2"]
    if primary == "Hakkapelitta" and "Firefather" in text:
        return ["Hakkapeliitta NNUE"]
    return list(MULTIPLE_FAMILIES.get(primary, (FAMILY_ALIASES.get(primary, primary),)))


def collect(fetch):
    parser = EngineTable()
    parser.feed(fetch(SOURCE_URL))
    if not parser.rows:
        raise ValueError("Archived Frank's Chess Page contained no recognized engine rows")
    observations = []
    for row in parser.rows:
        cell = row[0]
        families = row_families(cell)
        for family in families:
            if not family:
                raise ValueError(f"Empty engine-family name in {cell['text']!r}")
            code = []
            for link in cell["links"]:
                if re.match(
                    r"^(?:net\b|Iv\b|CB\b|WIKI\b|REPO\b|TC-\d+|IPman\b|EAS\b|Cerebrum\b)",
                    link["text"], re.I,
                ):
                    continue
                # For multi-engine rows, never attribute one engine's code to
                # its sibling. Generic links belong only to single-engine rows.
                if len(families) > 1 and clean_name(link["text"]) != family:
                    continue
                repository = code_url(link["url"])
                if repository:
                    item = {"url": repository, "evidence_url": SOURCE_URL}
                    if item not in code:
                        code.append(item)
            observations.append({
                "family": family, "label": cell["text"], "url": SOURCE_URL,
                "original_url": ORIGINAL_URL, "snapshot": SNAPSHOT,
                "code_urls": code,
            })
    return observations
