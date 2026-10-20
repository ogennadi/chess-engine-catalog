"""Collect linked chess programs from the wiki's manual alphabetical index."""

import re
from html.parser import HTMLParser
from urllib.parse import unquote, urljoin, urlsplit


SOURCE_URL = "https://chessprogramming.org/Engines"
SECTION_URL = SOURCE_URL + "#alphabetical-list"

# These are reviewed name/link pairs, not an inversion of wiki.TITLE_ALIASES:
# Capivara, Loop and Goliath pages each cover more than one catalog identity.
_ALIASES = {
    ("Bringer", "Bringer"): "Der Bringer",
    ("BugChess2", "BugChess FR"): "BugChess",
    ("Carballo", "Carballo"): "Karballo",
    ("Colossus Chess", "Colossus Chess"): "Colossus",
    ("Dragon by Komodo Chess", "Dragon by Komodo Chess"): "Dragon",
    ("E.T.Chess", "E.T.Chess"): "E.T. Chess",
    ("Goliath", "Goliath"): "Little Goliath",
    ("Leela Chess Zero", "Leela Chess Zero"): "Leela Chess",
    ("Prédateur", "Prédateur"): "Predateur",
    ("RofChade", "RofChade"): "rofChade",
    ("Shallow Blue", "Shallow Blue"): "Shallowblue",
    ("Vanilla Chess", "Vanilla Chess"): "VanillaChess",
    ("Garbochess", "Garbochess"): "GarboChess",
    ("nanoSzachy", "NanoSzachy"): "NanoSzachy",
    ("Nirvanachess", "Nirvanachess"): "NirvanaChess",
    ("WildCat", "WildCat"): "Wildcat",
    ("Complete Chess System II - TAL", "Chess System Tal"): "Chess System Tal",
    ("Maia Chess", "Maia Chess"): "Maia",
    ("Greenblatt Chess Program", "Greenblatt Chess Program"): "Mac Hack",
    ("Greenblatt Chess Program", "Mac Hack"): "Mac Hack",
    ("Stockfish NNUE", "Stockfish NNUE"): "Stockfish",
    ("Wita", "Wita"): "Awit",
    ("Wita", "Awit"): "Awit",
    ("ChessBin.com", "ChessCore"): "ChessCore",
}

# Homonymous programs are distinguished by the linked article, never merged
# merely because their displayed names coincide (including case-only matches).
_HOMONYMS = {
    "Ares US", "BBChess (SI)", "BugChess NL", "Caligula PC", "CCCP (US)",
    "Chaturanga IT", "Delta (GB)", "Genesis AR", "Genesis IL", "Genesis NL",
    "Hydra 97", "Jester US", "Joker IT", "Joker NL", "Killer (NL)",
    "MAX (Gillogly)", "Merlin (GB)", "Merlin (HU)", "Nightmare NL",
    "Nightmare GER", "ProChess IT", "Raptor LU", "Schach (US)",
    "Sjaak (Glebbeek)", "Storm US", "The Turk (TR)", "Tigran ES",
    "Toledo 2000", "Turbo Chess (GB)", "Zeus RU", "Ziggy IS",
    "Chess Champion Super System III",
}
_NON_CHESS = {"shogi", "go", "chinese chess", "xiangqi"}
_NON_ENGINE = {
    "engines", "protocols", "uci", "uci protocol", "chess engine communication protocol",
    "graphical user interface", "chess graphical user interfaces", "gui",
    "universal chess interface", "chess engines", "engine list", "chess gui",
    "fpga", "hardware", "platforms", "computers", "related links",
    "droidfish", "picochess", "raspberry turk",
    # Chess problem solvers (wiki Category:Problem) that do not play games.
    # LL Chess and Wilhelm share that category but are game-playing programs.
    "alybadix", "chest", "gustav", "popeye",
}

_SHARED_FAMILY_ARTICLES = {
    "awit": {"Awit", "Wita"},
    "mac hack": {"Mac Hack", "Greenblatt Chess Program"},
    "stockfish": {"Stockfish", "Stockfish NNUE"},
}


def _text(parts):
    return " ".join("".join(parts).split())


class _Index(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.started = False
        self.finished = False
        self.heading = None
        self.heading_text = []
        self.section = None
        self.in_list = False
        self.item = None
        self.anchor = None
        self.entries = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "h2":
            boundary = attrs.get("id")
            if boundary == "alphabetical-list":
                if self.started or self.finished:
                    raise ValueError("Duplicate wiki alphabetical-list boundary")
                self.started = True
            elif self.started and not self.finished:
                if boundary != "forum-posts" or self.in_list or self.item is not None:
                    raise ValueError("Unexpected wiki alphabetical-list end boundary")
                self.finished = True
            return
        if not self.started or self.finished:
            return
        if tag == "h3":
            if self.in_list or self.heading is not None:
                raise ValueError("Unexpected wiki alphabetical heading")
            self.heading = tag
            self.heading_text = []
        elif tag in ("ul", "ol"):
            if tag != "ul" or self.in_list or self.section is None:
                raise ValueError("Unexpected wiki alphabetical list structure")
            self.in_list = True
        elif tag == "li":
            if not self.in_list or self.item is not None:
                raise ValueError("Unexpected wiki engine list item")
            self.item = {"text": [], "links": [], "section": self.section}
        elif tag == "a" and self.item is not None:
            if self.anchor is not None:
                raise ValueError("Nested wiki anchor elements")
            self.anchor = {
                "href": attrs.get("href", ""), "text": [],
                "prefix": _text(self.item["text"]),
            }
        elif tag in {"table", "dl", "h4", "h5", "h6"}:
            raise ValueError("Unexpected wiki alphabetical index structure")

    def handle_data(self, data):
        if self.heading is not None:
            self.heading_text.append(data)
        if self.item is not None:
            self.item["text"].append(data)
        if self.anchor is not None:
            self.anchor["text"].append(data)

    def handle_endtag(self, tag):
        if not self.started or self.finished:
            return
        if tag == "h3":
            heading = _text(self.heading_text)
            if self.heading is None or not re.fullmatch(r"[#0-9A-Za-z]", heading):
                raise ValueError("Unrecognized wiki alphabetical heading")
            self.section = heading
            self.heading = None
        elif tag == "a" and self.anchor is not None:
            self.item["links"].append(self.anchor)
            self.anchor = None
        elif tag == "li":
            if self.item is None or self.anchor is not None:
                raise ValueError("Unclosed wiki engine link or missing item")
            self.entries.append(self.item)
            self.item = None
        elif tag == "ul":
            if not self.in_list or self.item is not None:
                raise ValueError("Unclosed wiki engine list item")
            self.in_list = False


def _page(href):
    parsed = urlsplit(urljoin(SOURCE_URL, href))
    if (
        parsed.scheme != "https" or parsed.netloc != "chessprogramming.org"
        or parsed.query or parsed.fragment or not parsed.path.startswith("/")
    ):
        return None
    title = unquote(parsed.path[1:]).replace("_", " ")
    # The recovered static site double-encodes this article's question mark.
    if title == "Doctor%3F":
        title = "Doctor?"
    if (
        not title or ":" in title or "/" in title
        or title.casefold() in _NON_ENGINE
        or title.casefold().startswith(("list of ", "category", "related "))
    ):
        return None
    return title, parsed.path, parsed.geturl()


def collect(fetch):
    parser = _Index()
    parser.feed(fetch(SOURCE_URL))
    parser.close()
    if (
        not parser.started or not parser.finished or parser.heading is not None
        or parser.in_list or parser.item is not None or not parser.entries
    ):
        raise ValueError("Wiki engine index is missing complete alphabetical-list/forum-posts boundaries")
    rows = []
    for item in parser.entries:
        if not item["links"]:
            continue
        primary = item["links"][0]
        # A name without a link followed by its linked author/game is not a
        # linked engine entry. Secondary links describe authors, hardware, etc.
        if primary["prefix"]:
            continue
        page = _page(primary["href"])
        if page is None:
            continue
        title, path, project_url = page
        games = {
            _text(link["text"]).casefold() for link in item["links"][1:]
        }
        label = _text(item["text"])
        annotations = {text.casefold() for text in re.findall(r"\(([^()]*)\)", label)}
        if (games | annotations) & _NON_CHESS and not games & {"chess", "chess960"}:
            continue
        name = _text(primary["text"])
        if (
            not name or not any(character.isalnum() for character in name)
            or re.fullmatch(r"\([^)]*\)|aka|by|clone|and|or", name, re.I)
        ):
            raise ValueError("Empty or annotation-only wiki engine name")
        family = _ALIASES.get((name, title), name)
        note = None
        if title in _HOMONYMS:
            family = title
            note = "Distinct program identified by the qualified wiki article; not the unqualified namesake."
        if title == "Atlas":
            family = "Atlas (1967)"
            note = (
                "Alex Bell's 1967 Algol chess program for ICL Atlas; "
                "not Andres Manzanares's modern Atlas engine."
            )
        elif title == "Atlas (ESP)":
            family = "Atlas"
            note = "Modern Atlas by Andres Manzanares Campillo; distinct from Alex Bell's 1967 program."
        elif family != name:
            note = note or "Reviewed index name/article pair reuses the catalog family identity."
        if title in {"Goliath", "Loop (Program)", "Capivara"}:
            note = (
                "Shared article: use only the explicitly listed engine identity; "
                "do not infer Little Goliath Evolution, Loop-List or Capivara LK from the page URL."
            )
        row = {
            "family": family, "label": label,
            "listed_name": name, "url": SECTION_URL, "listing_url": SOURCE_URL,
            "project_url": project_url, "page_title": title, "page_path": path,
            "section": item["section"], "code_urls": [],
        }
        if note:
            row["identity_note"] = note
        checked_at = getattr(fetch, "checked_at", {}).get(SOURCE_URL)
        if checked_at:
            row["checked_at"] = checked_at
        rows.append(row)
    if not rows:
        raise ValueError("Wiki alphabetical index contains no linked chess programs")
    identities = {}
    titles = {}
    for row in rows:
        key = row["family"].casefold()
        paths = identities.setdefault(key, set())
        paths.add(row["page_path"])
        titles.setdefault(key, set()).add(row["page_title"])
        if len(paths) > 1 and not titles[key] <= _SHARED_FAMILY_ARTICLES.get(key, set()):
            raise ValueError(f"Unreviewed wiki engine-name collision: {row['family']}")
    return rows
