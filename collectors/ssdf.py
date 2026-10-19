"""Collect SSDF's ranked software and named dedicated-computer products.

Named models such as Mephisto London remain distinct identities while CPU
configurations are removed. Bare manufacturer-only hardware is excluded;
wrappers are mapped to software only where the SSDF label names that engine.
"""

from html.parser import HTMLParser
import re
import warnings
from urllib.parse import urljoin


LIST_URL = "https://ssdf.bosjo.net/list.htm"
LONG_URL = "https://ssdf.bosjo.net/long.txt"
_SECTION = "SSDF rating list"
_RANKED_LINE = re.compile(
    r"^\s*(\d+)\s+(.+?)\s+(\d{4})\s{2,}\d{1,3}\s+-?\d{1,3}\s+\d+"
)
_VERSION = re.compile(
    r"^(?:v\.?)?\d+(?:[._-]\d+)*(?:[a-z]+\d*[a-z]?)?(?:/[a-z0-9.]+)?$",
    re.I,
)
_CPU = re.compile(
    r"^(?:x64|x86|amd64|arm\d*|pxa\d+|h8s?(?:/\d+)?|sh\d{3,4}|"
    r"2x68000|680\d{2}|6502|6301y|486(?:/.*)?|386/.*|pentium|"
    r"k6-2|q6600|1800x|athlon|p\d{3}|atari/amiga|iphone|ipad|"
    r"mcts|nnue?|uci|sse[\w.]*|avx\d*|bmi\d*|popcnt|"
    r"(?:[\d.]+)(?:mhz|ghz)|\d+(?:k|m)b?|"
    r"cuda(?:[-(].*)?|a\d+|m\d+)$",
    re.I,
)
_DEDICATED_PREFIXES = (
    "mephisto", "novag", "saitek", "fidelity", "cxg", "conchess",
    "millennium", "chessmachine", "chess machine", "kasparov",
    "tasc", "chess champion", "chessplayer", "the final chesscard",
)
_HARDWARE_ONLY = {
    "mephisto", "novag", "saitek", "fidelity", "cxg", "conchess",
    "millennium", "chessmachine", "chess machine", "kasparov", "tasc",
    "the final chesscard",
}
_EMBEDDED = (
    re.compile(r"^revelation(?:\s+\d+)?(?:\s+a\.e\.)?\s+", re.I),
    re.compile(r"^(?:p\.fritz|pocket fritz)\s+\S+\s+", re.I),
    re.compile(r"^(?:ceboard|resurrection)\s+", re.I),
)
_SOURCE_ALIASES = {
    "genius": "ChessGenius",
    "mchess pro": "MChess",
    "chessmaster king": "Chessmaster",
    "goliath light": "Little Goliath",
    "rebel century": "Rebel",
    "rebel decade": "Rebel",
    "wchess2000": "WChess",
    "zappa mexico ii": "Zappa",
    "comet32": "Comet", "cometa90": "Comet",
    "deep fritz": "Fritz",
    "deep shredder": "Shredder",
    "deep junior": "Junior",
    "deep rybka": "Rybka",
    "deep hiarcs": "Hiarcs",
    "deep sjeng": "Sjeng",
    "deep onno": "Onno",
    "deep gandalf": "Gandalf",
    "dragon komodo": "Dragon",
    "dragon by komodo": "Dragon",
    "komodo dragon": "Dragon",
    "palm hiarcs": "Hiarcs",
    "palm tiger": "Chess Tiger",
    "palm chess tiger": "Chess Tiger",
    "palm chess genius": "ChessGenius",
    "pocket shredder": "Shredder",
    "zap!chess zanzibar": "Zap!Chess",
    "yace paderborn": "Yace",
    "chess genius": "ChessGenius",
    "millennium chessgenius excl.": "ChessGenius",
    "millennium chessgenius pro": "ChessGenius",
    "millennium chessgenius arm": "ChessGenius",
    "millennium the king exclusive": "The King",
    "chessmachine the king": "The King",
    "chess machine the king": "The King",
    "chessmachine gideon": "Gideon",
    "chess machine gideon": "Gideon",
    "mephisto genius 2": "Mephisto Genius",
    "deep junior yokohama": "Junior",
    "junior yokohama": "Junior",
    "pro deo": "ProDeo",
}
_PREFIX_ALIASES = (
    ("millennium chessgenius", "ChessGenius"),
    ("millennium the king", "The King"),
    ("chessmachine the king", "The King"),
    ("chess machine the king", "The King"),
    ("chessmachine gideon", "Gideon"),
    ("chess machine gideon", "Gideon"),
)
_EMBEDDED_ENGINES = (
    "deep sjeng", "chess tiger", "glaurung", "chessgenius", "chess genius",
    "crafty", "shredder", "hiarcs", "komodo", "naum", "rybka", "ruffian",
    "fruit", "gideon", "the king", "rebel", "stockfish",
)


def _clean(text):
    return " ".join(text.split())


class _DetailLinks(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.rows = []
        self.row = None
        self.cell = None
        self.links = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "tr":
            self.row = []
        elif tag == "td" and self.row is not None:
            self.cell = {"text": [], "links": []}
            self.row.append(self.cell)
        elif tag == "a" and self.cell is not None:
            self.links.append({"href": attrs.get("href"), "text": []})

    def handle_data(self, data):
        if self.cell is not None:
            self.cell["text"].append(data)
        if self.links:
            self.links[-1]["text"].append(data)

    def handle_endtag(self, tag):
        if tag == "a" and self.links:
            link = self.links.pop()
            link["text"] = _clean("".join(link["text"]))
            if self.cell is not None:
                self.cell["links"].append(link)
        elif tag == "td":
            self.cell = None
        elif tag == "tr" and self.row is not None:
            self.rows.append(self.row)
            self.row = None


def _detail_urls(html):
    parser = _DetailLinks()
    parser.feed(html)
    parser.close()
    links = {}
    for row in parser.rows:
        cells = row or []
        candidates = [
            link
            for cell in cells
            for link in cell["links"]
            if link["href"] and re.fullmatch(r"nr\d+\.htm", link["href"], re.I)
        ]
        if not candidates:
            continue
        rank_text = _clean("".join(cells[0]["text"])) if cells else ""
        if not rank_text.isdigit() or len(candidates) != 1:
            raise ValueError("Malformed SSDF ranked detail link row")
        rank = int(rank_text)
        match = re.fullmatch(r"nr(\d+)\.htm", candidates[0]["href"], re.I)
        if int(match[1]) != rank or rank in links:
            raise ValueError("SSDF detail link rank does not match its rating row")
        if not candidates[0]["text"]:
            raise ValueError("SSDF detail link row has no engine label")
        links[rank] = {
            "label": candidates[0]["text"],
            "url": urljoin(LIST_URL, candidates[0]["href"]),
        }
    if not links:
        raise ValueError("SSDF list page contains no ranked detail links")
    return links


def _ranked_entries(text):
    header = re.search(r"THE SSDF RATING LIST[^\n]*?\b(\d+)\s+computers\b", text)
    if not header or int(header[1]) < 1:
        raise ValueError("SSDF long.txt has no declared computer count")
    expected = int(header[1])
    entries = []
    started = False
    for line in text.splitlines():
        match = _RANKED_LINE.match(line)
        if not match:
            if started:
                break
            continue
        rank = int(match[1])
        if rank == 1:
            started = True
        if not started:
            continue
        if rank != len(entries) + 1:
            raise ValueError("Nonsequential SSDF rank %s in long.txt" % rank)
        label = _clean(match[2])
        if not label:
            raise ValueError("Empty SSDF label at rank %s" % rank)
        entries.append((rank, label))
        if rank == expected:
            break
    if len(entries) != expected:
        raise ValueError("SSDF long.txt contains %d ranked entries; expected %d" % (len(entries), expected))
    return entries


def _embedded_engine(label):
    for pattern in _EMBEDDED:
        match = pattern.match(label)
        if not match:
            continue
        rest = label[match.end():]
        for name in _EMBEDDED_ENGINES:
            if rest.casefold() == name or rest.casefold().startswith(name + " "):
                return rest
    return None


def _strip_hardware(label):
    words = label.split()
    for index, word in enumerate(words):
        if (
            word.isdigit()
            and index + 1 < len(words)
            and words[index + 1].casefold() in ("kb", "mb")
        ):
            return _clean(" ".join(words[:index]))
        if (
            re.fullmatch(r"\d+(?:\.\d+)?", word)
            and index + 1 < len(words)
            and words[index + 1].casefold() in ("mhz", "ghz")
        ):
            return _clean(" ".join(words[:index]))
        if _CPU.fullmatch(word.strip(" ,;")):
            return _clean(" ".join(words[:index]))
    return label


def _family(label):
    """Normalize listed releases/platforms without treating hardware as an engine name."""
    label = _clean(label)
    embedded = _embedded_engine(label)
    if embedded:
        label = embedded
    label = _strip_hardware(label)
    label = re.sub(r"\s+(?:Brute F[.]|Turbo Kit)$", "", label)
    lowered = label.casefold()
    if lowered in _SOURCE_ALIASES:
        return _SOURCE_ALIASES[lowered]
    for prefix, family in _PREFIX_ALIASES:
        if lowered == prefix or lowered.startswith(prefix + " "):
            return family

    words = label.split()
    dedicated = any(
        lowered.startswith(prefix + " ") or lowered == prefix
        for prefix in _DEDICATED_PREFIXES
    )
    if not dedicated:
        end = len(words)
        for index, word in enumerate(words[1:], 1):
            if _VERSION.fullmatch(word) or re.fullmatch(r"v\.", word, re.I):
                end = index
                break
        label = _clean(" ".join(words[:end]))
    else:
        for index, word in enumerate(words[1:], 1):
            if re.fullmatch(r"v\.?(?:\d|$)", word, re.I):
                label = _clean(" ".join(words[:index]))
                break

    lowered = label.casefold()
    if lowered in _SOURCE_ALIASES:
        return _SOURCE_ALIASES[lowered]
    for prefix, family in _PREFIX_ALIASES:
        if lowered == prefix or lowered.startswith(prefix + " "):
            return family
    if lowered in _HARDWARE_ONLY:
        return ""
    if lowered.startswith("deep "):
        label = label[5:]
        lowered = label.casefold()
        return _SOURCE_ALIASES.get(lowered, label)
    if lowered.startswith("chess genius"):
        return "ChessGenius"
    return label


def _collect(fetch):
    detail_urls = _detail_urls(fetch(LIST_URL))
    entries = _ranked_entries(fetch(LONG_URL))
    checked_at = getattr(fetch, "checked_at", {})
    timestamp = checked_at.get(LONG_URL)
    rows = []
    excluded = []
    mismatched_details = 0
    for rank, label in entries:
        family = _family(label)
        if not family:
            excluded.append((rank, label))
            continue
        row = {
            "family": family,
            "label": label,
            "url": LIST_URL,
            "listing_url": LIST_URL,
            "data_url": LONG_URL,
            "rank": rank,
            "section": _SECTION,
            "code_urls": [],
        }
        if rank in detail_urls:
            detail = detail_urls[rank]
            if detail["label"].casefold() == label.casefold():
                row["detail_url"] = detail["url"]
            else:
                mismatched_details += 1
        if timestamp:
            row["checked_at"] = timestamp
        rows.append(row)
    if not rows:
        raise ValueError("SSDF rating list contains no recognizable engine identities")
    if excluded:
        warnings.warn(
            "SSDF excluded %d hardware-only entries without a named engine: %s"
            % (len(excluded), ", ".join("%d %s" % item for item in excluded)),
            RuntimeWarning,
        )
    if mismatched_details:
        warnings.warn(
            "SSDF list.htm has %d detail-link labels that do not match the same "
            "long.txt rank; those detail URLs were omitted"
            % mismatched_details,
            RuntimeWarning,
        )
    return rows


def collect(fetch):
    """Collect declared SSDF ranks, excluding unresolved bare hardware labels."""
    collect.last_warnings = []
    with warnings.catch_warnings(record=True) as issues:
        warnings.simplefilter("always", RuntimeWarning)
        rows = _collect(fetch)
    collect.last_warnings = list(dict.fromkeys(str(issue.message) for issue in issues))
    if collect.last_warnings:
        for row in rows:
            row["warnings"] = list(collect.last_warnings)
    for issue in issues:
        warnings.warn(str(issue.message), issue.category, stacklevel=2)
    return rows


collect.last_warnings = []
