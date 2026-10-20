"""Collect engine rows from the Computer-Chess Wiki chess engine list."""

import re
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit

from collectors.rwbc import _repository, _source_archive


SOURCE_URL = "http://computer-chess.org/doku.php?id=computer_chess:wiki:lists:chess_engine_list"
# Tables per section heading: release years, then the four special lists.
COLUMNS = {
    7: ("date_added", "engine", "version", "author", "downloads", "protocol", "comment"),
    5: ("engine", "version", "author", "protocol", "comment"),
    4: ("engine", "author", "protocol", "comment"),
}
SPECIAL_SECTIONS = {
    "Dead Engine List": 7, "Source Code Only List": 4, "Withdrawn Engine List": 5,
}
# Announced but unreleased projects (often empty repositories) are not engines.
SKIPPED_SECTIONS = {"Someday Announcement Engine List"}
# The list labels reconciled with the catalog's existing family names.
FAMILY_ALIASES = {
    "(Deep) Gandalf": "Gandalf", "ACE(2)": "ACE2", "Ajedrez Táctico": "Ajedrez Tactico",
    "Animats Chess": "AnimatsChess", "Apep Chess Engine": "Apep",
    "BagaturChess": "Bagatur", "BDI Chess": "BDIChess", "Betsabé II": "Betsabe II",
    "Celes [aka: 31337, Eleet]": "Celes", "Chad's Chess": "Chads Chess",
    "Chess Rikus": "Chess-Rikus", "ChessProj (Chess AI Engine)": "ChessProj",
    "DarkFusc# (DarkFusch)": "DarkFusc", "Deep Hiarcs": "Hiarcs", "Deep Smash": "Smash",
    "Dirty-Bit": "DirtyBit", "Doumi [aka Naguene]": "Doumi", "Easy Peasy": "EasyPeasy",
    "Evolution Chess": "EvolutionChess", "EvilKnight III": "EvilKnightIII",
    "Fischer": "Fischer-Chess", "Fusc# (Fusch, Dark Fusch)": "FUSc#", "Gaïa": "Gaia",
    "GambitFruit": "Gambit Fruit", "GnuCheese [GnuChess5]": "GnuCheese",
    "GNUchess3": "GNU Chess", "GNUchess4": "GNU Chess", "GNUchess6": "GNU Chess",
    "Gray Matter": "GrayMatter", "JSSchach": "JS Schach", "Joker(2)": "Joker2",
    "Junior (Deep Junior)": "Junior", "Kasparov": "KasparovChess",
    "KingOfKings": "King of Kings", "KMT Chess": "KMTChess", "LCZero": "Leela Chess",
    "Le DJO": "LeDjo", "Lightning (The Lightning)": "Lightning (The)", "MagiC": "MagiC-engine",
    "Bringer": "Der Bringer", "Chesley the Chess Engine": "Chesley",
    "DeepSaros_eXp": "Deep Saros", "LTChess2": "LTChess",
    "P4wn Javascript Chess": "P4wn", "SSEChess": "SSEChessII", "Sugar NN": "SugaR",
    "micro-Max (µMax)": "Micro-Max", "Mister Queen": "MisterQueen",
    "Polar Chess": "PolarChess", "Poor Little Pinkus": "PoorLittlePinkus",
    "Prédateur": "Predateur", "Pulse Chess": "Pulse", "Shallow Blue": "Shallowblue",
    "simple UCI chess engine": "ChessEngine", "Sting SF": "Sting",
    "T-Rex": "T.rex", "Tarrasch Toy Engine": "TarraschToyEngine",
    "The King (ChessMaster 11)": "The King", "Tikov Chess": "Tikov", "Toga II": "Toga",
    "tomitank Chess": "tomitankChess", "Violet": "Violet (Deep)",
    "Virutor": "Virutor Chess", "Wowl Chess": "Wowl",
}
# Same-named programs by different authors: (list label, author substring) -> family.
HOMONYMS = {
    ("Chess", "Stanback"): "Chess (Stanback)",
    ("Chess(2)", "Lattanzi"): "Chess (Lattanzi)",
    ("Chess(3)", "Sonkoly"): "Chess-3",
    ("Chess(4)", "Cimbalista"): "Chess",
    ("Chess(5)", "Waugh"): "Chess (Waugh)",
    ("ChessEngine", "Clarity"): "ChessEngine (Clarity)",
    ("ChessEngine", "Socha"): "ChessEngine (Socha)",
    ("ChessEngine(3)", "Alain Lou"): "ChessEngine (Lou)",
    ("Armageddon(2)", "Kasabasic"): "Armageddon (Kasabasic)",
    ("Crab", "Kleng"): "Crab (Kleng)",
    ("Morphy", "danem"): "Morphy (danem)",
    ("Neptune", "Leszczynski"): "Neptune (Leszczynski)",
    ("Phoenix", "Rahul"): "Phoenix (Rahul)",
    ("Savant", "Dalton He"): "Savant (He)",
    ("Turochamp", "Baroja"): "Turochamp (Baroja)",
    ("Zugzwang", "Despa"): "Zugzwang (Despa)",
}
_SOURCE_LABEL = re.compile(r"\b(?:source|src|code)\b", re.I)
_NAME_KEY = re.compile(r"[^a-z0-9]")
_FORGES = {"github.com", "gitlab.com", "codeberg.org", "bitbucket.org", "sourceforge.net"}


class EngineTables(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.section = None
        self.heading = None
        self.rows = []
        self.cells = None
        self.cell = None
        self.link = None

    def handle_starttag(self, tag, attrs):
        if tag == "h2":
            self.heading = ""
        elif tag == "tr":
            self.cells = []
        elif tag in ("td", "th") and self.cells is not None:
            self.cell = {"text": "", "links": [], "header": tag == "th"}
        elif tag == "a" and self.cell is not None:
            self.link = {"url": urljoin(SOURCE_URL, dict(attrs).get("href") or ""), "text": ""}
        elif tag == "br" and self.cell is not None:
            self.cell["text"] += " "

    def handle_data(self, data):
        if self.heading is not None:
            self.heading += data
        if self.cell is not None:
            self.cell["text"] += data
        if self.link is not None:
            self.link["text"] += data

    def handle_endtag(self, tag):
        if tag == "h2" and self.heading is not None:
            self.section = " ".join(self.heading.split())
            self.heading = None
        elif tag == "a" and self.link is not None:
            self.link["text"] = " ".join(self.link["text"].split())
            if self.cell is not None:
                self.cell["links"].append(self.link)
            self.link = None
        elif tag in ("td", "th") and self.cell is not None:
            self.cell["text"] = " ".join(self.cell["text"].split())
            self.cells.append(self.cell)
            self.cell = None
        elif tag == "tr" and self.cells is not None:
            if self.cells and not any(cell["header"] for cell in self.cells):
                self.rows.append((self.section, self.cells))
            self.cells = None


def _key(name):
    return _NAME_KEY.sub("", name.casefold())


def family_name(label, author):
    for (name, author_part), family in HOMONYMS.items():
        if label == name and author_part.casefold() in author.casefold():
            return family
    return FAMILY_ALIASES.get(label, label)


def repository(url):
    found = _repository(url)
    if found and urlsplit(found).hostname == "gitlab.com":
        # Older GitLab pages omit the "/-/" separator before tags and trees.
        found = re.sub(r"/(?:tags|releases|tree|blob)(?:/.*)?$", "", found)
    return found


def code_urls(family, label, site_links, download_links):
    """Repository links from the engine column, and explicitly labelled source downloads."""
    identities = {_key(family), _key(label)} - {""}
    result = []

    def add(url):
        item = {"url": url, "evidence_url": SOURCE_URL}
        if item not in result:
            result.append(item)

    for link in site_links:
        found = repository(link["url"])
        if found:
            add(found)
        elif _source_archive(link["url"]):
            add(link["url"])
    for link in download_links:
        found = repository(link["url"])
        if _SOURCE_LABEL.search(link["text"]):
            # A forge URL that is not a repository is an author profile.
            if found or (urlsplit(link["url"]).hostname or "").lower() not in _FORGES:
                add(found or link["url"])
        elif found:
            # Unlabelled download repositories are often third-party build
            # collections; keep only those named after this engine.
            project = _key(urlsplit(found).path.rstrip("/").split("/")[-1])
            if any(len(key) >= 3 and (key in project or project in key) for key in identities):
                add(found)
    return result


def collect(fetch):
    parser = EngineTables()
    parser.feed(fetch(SOURCE_URL))
    observations, warnings, sections = [], [], set()
    for section, cells in parser.rows:
        if section in SKIPPED_SECTIONS:
            continue
        expected = SPECIAL_SECTIONS.get(section, 7 if re.fullmatch(r"\d{4} Releases", section or "") else None)
        if expected is None:
            raise ValueError(f"Unrecognized computer-chess.org section {section!r}")
        if len(cells) != expected:
            raise ValueError(f"Malformed computer-chess.org row in {section}: {len(cells)} cells")
        sections.add(section)
        row = {name: cell for name, cell in zip(COLUMNS[expected], cells)}
        label = row["engine"]["text"]
        author = row["author"]["text"]
        if not label:
            raise ValueError(f"Empty computer-chess.org engine name in {section}")
        family = family_name(label, author)
        if re.search(r"\(\d+\)$", family):
            warnings.append(f"Unreviewed numbered homonym {label!r} by {author!r}")
        site = row["engine"]["links"]
        downloads = row.get("downloads", {"links": []})["links"]
        observation = {
            "family": family, "label": label, "url": SOURCE_URL, "section": section,
            "author": author, "version": row.get("version", {}).get("text", ""),
            "protocol": row["protocol"]["text"], "comment": row["comment"]["text"],
            "links": [link["url"] for cell in cells for link in cell["links"]],
            "code_urls": code_urls(family, label, site, downloads),
        }
        if "date_added" in row:
            observation["date_added"] = row["date_added"]["text"]
        if site:
            observation["project_url"] = site[0]["url"]
        observations.append(observation)
    if not observations or not set(SPECIAL_SECTIONS) <= sections:
        raise ValueError("computer-chess.org list is missing recognized engine sections")
    collect.last_warnings = warnings
    checked_at = getattr(fetch, "checked_at", {}).get(SOURCE_URL)
    if checked_at:
        for observation in observations:
            observation["checked_at"] = checked_at
    return observations


collect.last_warnings = []
