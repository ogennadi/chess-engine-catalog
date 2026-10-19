"""Collect engine families from the two CEGT all-version rating tables."""

from html.parser import HTMLParser
import re
from urllib.parse import urljoin


RATINGS_URLS = (
    "http://www.cegt.net/40_4_Ratinglist/40_4_AllVersion/rangliste.html",
    "http://www.cegt.net/40_40%20Rating%20List/40_40%20All%20Versions/rangliste.html",
)
_SECTIONS = ("CEGT 4/40", "CEGT 40/20")
_HEADERS = ("no", "program", "elo", "+", "-", "games", "score", "av.op.", "draws")
_VERSION = re.compile(
    r"^(?:v\.?)?\d+(?:[._-]\d+)*(?:[a-z]+\d*[a-z]?)?(?:[._-]\d+)*(?:/[a-z0-9]+)?$",
    re.I,
)
_BUILD = re.compile(
    r"^(?:x64|x86|amd64|nnue?|sse[\w.]*|avx\d*|bmi\d*|popcnt|popcount|"
    r"pext|hce|mcts|uci|single|default|w32|w64|[\d]+cpu|[\d]+threads?)$",
    re.I,
)
_ALIASES = {
    "bringer": "Der Bringer",
    "cheng3": "Cheng", "cheng4": "Cheng",
    "cstal": "Chess System Tal", "pro deo": "ProDeo",
    "nirvana chess": "NirvanaChess", "shallow blue": "Shallowblue",
    "tomitank chess": "tomitankChess", "thors hammer": "Thor's Hammer",
    "lczero": "Leela Chess",
    "kdragon": "Dragon",
    "goliath light": "Little Goliath", "goliath blitz": "Little Goliath",
    "lg evolution": "Little Goliath Evolution", "lge": "Little Goliath Evolution",
    "lgevolution": "Little Goliath Evolution",
    "list-mp": "List", "listmp": "List", "loop list": "Loop-List",
    "loop-mp": "Loop", "loopmp": "Loop", "loopp2": "Loop", "loopt2": "Loop",
    "slowchess": "Slow Chess", "slowchess blitz": "Slow Chess",
    "slowchess classic": "Slow Chess", "slowchessclassic": "Slow Chess",
    "slowchess blitz classic": "Slow Chess",
    "rodent ii": "Rodent", "rodent iii": "Rodent", "rodent iv": "Rodent",
    "toga ii": "Toga", "toga iii": "Toga",
    "phalanx xxii": "Phalanx", "phalanx xxiii": "Phalanx",
    "phalanx xxiv": "Phalanx", "phalanx xxv": "Phalanx",
    "stoofvlees ii": "Stoofvlees",
    "fatfritz": "Fat Fritz",
    "mr.bob": "MrBob", "ngplay": "NG-Play",
    "dan chess": "DanChess", "phalanx xxiii beta": "Phalanx",
    "sting sf": "Sting", "z5": "Starzix",
    "genius": "ChessGenius",
    "sfnnue": "Stockfish",
    "deep fritz": "Fritz",
    "deep shredder": "Shredder",
    "deep junior": "Junior",
    "deep rybka": "Rybka",
    "deep hiarcs": "Hiarcs",
    "deep sjeng": "Sjeng",
    "deep onno": "Onno",
    "deep gandalf": "Gandalf",
    "komodo dragon": "Dragon",
    "dragon komodo": "Dragon",
    "dragon by komodo": "Dragon",
    "clovis iii": "Clovis",
    "clovis iii ja": "Clovis",
    "chiron a": "Chiron",
    "chiron b": "Chiron",
    "chiron c": "Chiron",
    "hakkapeliitta tcec": "Hakkapeliitta",
    "dirty catpaw": "Dirty",
    "dirty duna": "Dirty",
    "zappa mexico": "Zappa",
    "dorpsgek eve's temptation": "Dorpsgek",
    "slow chess classic": "Slow Chess",
    "slow chess blitz": "Slow Chess",
    "zurichess nidwalden": "Zurichess",
    "zurichess neuchatel": "Zurichess",
    "zurichess appenzeller": "Zurichess",
    "turbulence": "Turbulence",
    "deep frenzee": "Frenzee",
    "deep ice": "iCE",
    "deep patzer": "Patzer",
    "deep pharaon": "Pharaon",
    "deep sjeng ct": "Sjeng",
    "deep sjeng wc": "Sjeng",
    "deep sjeng wc2008": "Sjeng",
    "deep shredder13": "Shredder",
    "deep smash": "Smash",
    "komodo cct": "Komodo",
    "komodo tcec": "Komodo",
    "zappa mexico ii": "Zappa",
    "zappa mexico ii wd": "Zappa",
    "slow chess blitz wv": "Slow Chess",
    "slow chess blitz wv2": "Slow Chess",
    "slow chess blitz wv2.1": "Slow Chess",
    "zurichess geneva": "Zurichess",
    "zurichess glarus": "Zurichess",
    "zurichess graubuenden": "Zurichess",
    "zurichess jura": "Zurichess",
    "zurichess luzern": "Zurichess",
}
_RELEASE_PREFIXES = {
    "Crafty": ("Cito",), "Comet": ("B68",), "Dan Chess": ("CCT7",),
    "DanChess": ("CCT7",), "Deep Junior": ("Yokohama",),
    "Dirty": ("Apr2013", "Apr2015", "Apr2017", "Cucumber", "Nov2015"),
    "ECE": ("X3", "X3.5"), "Frenzee": ("Dec07", "Feb08"),
    "Fritz": ("for Fun", "in Bahrain"), "X3D Fritz": ("",),
    "Ginkgo": ("Santiago", "Valencia"),
    "GinkgoSantiago": ("",), "GinkgoValencia": ("",),
    "Hiarcs": ("Paderborn", "X50", "X54"),
    "Marvin": ("TCEC s15",),
    "Robocide": ("Feb2013",), "RomiChess": ("OW2a LD", "OW2aLD", "P3d", "P3K", "P3n"),
    "RomiChessNG5": ("",), "RomiChessX64P3i": ("",),
    "Ruffian": ("Leiden",), "Shredder": ("Classic", "WM Edition Bonn"),
    "Stockfish": ("DD", "TCEC8"), "Stoofvlees": ("II",),
    "Yace": ("Paderborn",),
    "Zap!Chess": ("Paderborn", "Reykjavik", "Zanzibar"),
    "Glaurung": ("CCT8", "Lodz", "Mainz", "2-E/2", "2-E/2-5", "2-E/4-5"),
    "LCZero": ("0310rc2CUDA",), "Gull": ("II", "R375"),
    "LoopMP": ("11A/12.32",), "Loop": ("M1", "M1-P", "M1-T", "2010-x"),
    "Raptor": ("CCT002", "CCT16"), "Nimzo": ("'99",),
    "WbNimzo2000b": ("",), "Witz": ("Alpha21",),
    "Quanticade": ("E0.9",), "Rebel": ("EAS", "Extreme", "Century", "Decade", "15x2NN"),
    "Pirat": ("B.0.4.9",),
}


def _clean(text):
    return " ".join(text.split())


def _family(label):
    """Remove a CEGT release/build suffix, retaining the source label separately."""
    label = _clean(label)
    if re.match(r"^CM(?:10th|8000|9000|C\b|X\b| Challenge\b)", label, re.I):
        return "Chessmaster"
    for prefix, releases in _RELEASE_PREFIXES.items():
        for release in releases:
            marker = (prefix + " " + release).strip()
            if label.casefold() == marker.casefold() or label.casefold().startswith(marker.casefold() + " "):
                base = {
                    "X3D Fritz": "Fritz", "GinkgoSantiago": "Ginkgo", "GinkgoValencia": "Ginkgo",
                    "RomiChessNG5": "RomiChess", "RomiChessX64P3i": "RomiChess",
                    "WbNimzo2000b": "Nimzo", "LCZero": "Leela Chess", "LoopMP": "Loop",
                }.get(prefix, prefix)
                return _ALIASES.get(base.casefold(), base)
    label = re.sub(r"\s+(?:rev\d|r\d|[A-Z]{1,2}-\d|a\d+(?:\s|$)|b\d+(?:\s|$)).*$", "", label)
    label = re.sub(r"\s+\d+[.]\w+[./-]\w+.*$", "", label)
    label = re.sub(r"\s+\d+[.]xx\b.*$", "", label)
    label = re.sub(r"([_-])v(?=\d)", " ", label, flags=re.I)
    words = label.split()
    first_version = re.fullmatch(
        r"(.+?)[_-](?:v\.?)?\d+(?:[._-]\d+)*(?:[a-z]+\d*[a-z]?)?(?:[._-]\d+)*(?:/[a-z0-9]+)?",
        words[0],
        re.I,
    ) if words else None
    if first_version:
        words[0] = first_version[1]
    end = len(words)
    for index, word in enumerate(words[1:], 1):
        if (
            _VERSION.fullmatch(word)
            or re.fullmatch(r"\d{1,4}/\d{1,2}/\d{1,4}", word)
            or _BUILD.fullmatch(word)
        ):
            end = index
            break
    name = _clean(" ".join(words[:end]))
    return _ALIASES.get(name.casefold(), name)


class _RatingTables(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tables = []
        self._stack = []
        self._row = None
        self._cell = None
        self._anchor = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "table":
            self._stack.append({"rows": [], "row": None})
        elif tag == "tr" and self._stack:
            self._row = []
            self._stack[-1]["row"] = self._row
        elif tag in ("td", "th") and self._stack and self._stack[-1]["row"] is not None:
            self._cell = {"text": [], "links": []}
            self._stack[-1]["row"].append(self._cell)
        elif tag == "a" and self._cell is not None:
            self._anchor = {"href": attrs.get("href"), "text": []}

    def handle_data(self, data):
        if self._cell is not None:
            self._cell["text"].append(data)
        if self._anchor is not None:
            self._anchor["text"].append(data)

    def handle_endtag(self, tag):
        if tag == "a" and self._anchor is not None:
            self._anchor["text"] = _clean("".join(self._anchor["text"]))
            if self._cell is not None:
                self._cell["links"].append(self._anchor)
            self._anchor = None
        elif tag in ("td", "th"):
            self._cell = None
        elif tag == "tr" and self._stack:
            if self._row is not None:
                self._stack[-1]["rows"].append(self._row)
            self._stack[-1]["row"] = None
            self._row = None
        elif tag == "table" and self._stack:
            table = self._stack.pop()
            self.tables.append(table["rows"])

    def finish(self):
        self.close()
        return self.tables


def _table_rows(html, url):
    parser = _RatingTables()
    parser.feed(html)
    tables = parser.finish()
    matching = []
    for table in tables:
        if not table:
            continue
        headers = tuple(_clean("".join(cell["text"])).casefold() for cell in table[0])
        if headers == _HEADERS:
            matching.append(table)
    if len(matching) != 1:
        raise ValueError(
            "CEGT page %s has %d recognizable nine-column rating tables"
            % (url, len(matching))
        )
    records = []
    for row in matching[0][1:]:
        if not any(_clean("".join(cell["text"])) for cell in row):
            continue
        if len(row) != 9:
            raise ValueError("Malformed CEGT rating row on %s" % url)
        rank_text = _clean("".join(row[0]["text"]))
        if not rank_text.isdigit():
            raise ValueError("Unrecognized CEGT rank %r on %s" % (rank_text, url))
        name_cell = row[1]
        label = _clean("".join(name_cell["text"]))
        links = [link for link in name_cell["links"] if link["href"] and link["text"]]
        if not label or len(links) != 1 or links[0]["text"] != label:
            raise ValueError("CEGT rank %s has no unique linked program name" % rank_text)
        rank = int(rank_text)
        if rank != len(records) + 1:
            raise ValueError("Nonsequential CEGT rating rank %s on %s" % (rank, url))
        records.append((rank, label, urljoin(url, links[0]["href"])))
    if not records:
        raise ValueError("CEGT page %s contains no ranked program rows" % url)
    return records


def collect(fetch):
    """Return one CEGT observation per ranked program with page-specific evidence."""
    rows = []
    checked_at = getattr(fetch, "checked_at", {})
    for url, section in zip(RATINGS_URLS, _SECTIONS):
        records = _table_rows(fetch(url), url)
        timestamp = checked_at.get(url)
        for rank, label, detail_url in records:
            row = {
                "family": _family(label),
                "label": label,
                "url": url,
                "listing_url": url,
                "rank": rank,
                "section": section,
                "detail_url": detail_url,
                "code_urls": [],
            }
            if timestamp:
                row["checked_at"] = timestamp
            rows.append(row)
    return rows
