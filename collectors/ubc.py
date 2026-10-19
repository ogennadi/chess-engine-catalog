"""Collect UBC engine names without conflating forks with their ancestors.

UBC's POST type3 ("By Family") is an ancestry view, not a list of distinct
engines: its Glaurung group includes Stockfish, asmFish, Houdini, ChessBrainVB
and Viper; its IPPOLIT group includes Fire, Gull and others.  Consequently we
use the engine labels, not those headings, as identities, removing recognizable
version/build suffixes conservatively. A bounded alias table collapses known
named releases, Deep editions and Slow Chess Classic/Blitz. Dragon by Komodo
keeps its qualified name (and remains distinct from Komodo); Luna and LunaChess
remain distinct. Unknown named releases are not inferred from ancestry.

Only explicit repository/source-archive links in an engine's row are retained.
The live list inspected in October 2026 had no such links (its eng@ anchors
are JavaScript POST controls, not hyperlinks). No repository URLs are guessed,
and opponent-result POST pages are not crawled.
"""

from html.parser import HTMLParser
import re
from urllib.parse import unquote, urljoin, urlsplit


RATINGS_URL = "https://e4e6.com/ubc_ratings.php"

_VERSION = re.compile(
    r"^(?:\d|v\d|r\d|rev(?:ision)?(?:[-_]|\d|$)|dev(?:[-_]|\d|$)"
    r"|[0-9a-f]{7,}$|[IVXLCDM]+$)",
    re.IGNORECASE,
)
_BUILD = re.compile(
    r"^(?:avx\d*|bmi\d*|popcnt|popcount|pext|sse[\d.]*|hce|nnue"
    r"|beta|alpha|x64|x86|amd64|32bit|64bit)$",
    re.IGNORECASE,
)

# Exact names from the listing, not ancestry-based or fuzzy prefix matches.
_ALIASES = {
    "zurichess nidwalden": "Zurichess",
    "zurichess neuchatel": "Zurichess",
    "zurichess appenzeller": "Zurichess",
    "turbulence_v4": "Turbulence",
    "hakkapeliitta tcec": "Hakkapeliitta",
    "deep rybka": "Rybka",
    "deep shredder": "Shredder",
    "deep onno": "Onno",
    "deep gandalf": "Gandalf",
    "dirty catpaw": "Dirty",
    "dirty duna": "Dirty",
    "zappa mexico": "Zappa",
    "dorpsgek eve's temptation": "Dorpsgek",
    "slow chess classic": "Slow Chess",
    "slow chess blitz": "Slow Chess",
}


def _clean(text):
    return " ".join(text.split())


def _family(label):
    # This UBC build attaches the version/hash to the name with an underscore.
    label = re.sub(
        r"^Byte-Knight_\d+-[0-9a-f]{7}(?:GS)?(?=\s|$)",
        "Byte-Knight", label, flags=re.IGNORECASE,
    )
    words = label.split()
    # The first word can itself be numeric, e.g. "100 Elo" or "4ku".
    for index, word in enumerate(words[1:], 1):
        if _VERSION.match(word) or _BUILD.fullmatch(word):
            name = " ".join(words[:index])
            break
    else:
        name = label
    return _ALIASES.get(name.casefold(), name)


def _code_url(href, text):
    """Accept repositories or explicitly identified source downloads, not sites."""
    url = urljoin(RATINGS_URL, href)
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        return None
    host = parts.hostname.lower()
    path = [part for part in parts.path.strip("/").split("/") if part]
    if host in ("github.com", "www.github.com", "bitbucket.org", "codeberg.org"):
        if len(path) >= 2 and path[0].lower() not in (
            "topics", "orgs", "users", "search", "features", "collections",
        ):
            if len(path) == 2 or path[2].lower() in (
                "tree", "blob", "src", "archive", "raw",
            ):
                return url
    if host == "gitlab.com" and len(path) >= 2:
        if "-" not in path or path[path.index("-") + 1 :][:1] in (
            ["tree"], ["blob"], ["archive"], ["raw"],
        ):
            return url
    if host in ("git.sr.ht", "hg.sr.ht") and len(path) >= 2:
        return url
    if host == "sourceforge.net" and len(path) >= 3:
        if path[0] == "projects" and path[2] in ("code", "source"):
            return url
    decoded_path = unquote(parts.path).lower()
    if re.search(r"\.(?:zip|7z|tar|tgz|tar\.gz|tar\.bz2|tar\.xz)$", decoded_path):
        if re.search(r"\b(?:source|sources|src)\b", text, re.IGNORECASE) or re.search(
            r"(?:^|[/_.-])(?:source|sources|src)(?:[/_.-]|$)", decoded_path
        ):
            return url
    return None


class _RatingsParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.rows = []
        self.row = []
        self.anchor = None
        self.ignored = 0

    def _finish_row(self):
        if self.row:
            self.rows.append(self.row)
        self.row = []
        self.anchor = None

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self.ignored += 1
        if self.ignored:
            return
        if tag == "tr":
            # UBC sometimes omits closing tr/td tags in its family headings.
            self._finish_row()
        elif tag == "a":
            self.anchor = [dict(attrs), []]

    def handle_data(self, data):
        if self.anchor is not None and not self.ignored:
            self.anchor[1].append(data)

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self.ignored = max(0, self.ignored - 1)
        elif tag == "a" and self.anchor is not None:
            attrs, text = self.anchor
            self.row.append((attrs, _clean("".join(text))))
            self.anchor = None
        elif tag == "tr":
            self._finish_row()

    def finish(self):
        self.close()
        self._finish_row()
        return self.rows


def collect(fetch):
    """Return distinct engine families; ``fetch(url, data=dict)`` performs POST.

    Network errors propagate. An unrecognized/empty rating response raises
    ValueError rather than silently reporting a successful empty collection.
    Provenance includes the actual POST endpoint and request body; GET alone
    does not reproduce the listing.
    """
    parser = _RatingsParser()
    parser.feed(fetch(RATINGS_URL, data={"type": "type3"}))
    families = {}
    for row in parser.finish():
        engines = [
            (attrs, label) for attrs, label in row
            if re.fullmatch(r"eng@\d+", attrs.get("id") or "") and label
        ]
        if len(engines) != 1:
            continue
        _, label = engines[0]
        family = _family(label)
        record = families.setdefault(family.casefold(), {
            "family": family,
            "label": label,
            "url": RATINGS_URL,
            "request_data": {"type": "type3"},
            "code_urls": [],
        })
        for attrs, text in row:
            href = attrs.get("href")
            if not href:
                continue
            code_url = _code_url(href, text)
            if code_url:
                evidence = {"url": code_url, "evidence_url": RATINGS_URL}
                if evidence not in record["code_urls"]:
                    record["code_urls"].append(evidence)
    if not families:
        raise ValueError("UBC type3 response contains no recognizable engine rows")
    return list(families.values())
