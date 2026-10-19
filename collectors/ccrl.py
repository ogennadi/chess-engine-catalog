"""CCRL 40/15 engine families and explicitly linked source code.

The complete rating list contains thousands of *versions*.  Instead, use the
index's ``select name=family`` (CCRL's own taxonomy), and enrich it from the
index's best-version details, in small bulk requests.  Detail pages explicitly
identify their family, including single-version families.  No name/version
heuristic is used, and forks remain separate when CCRL lists them separately.

Only CCRL pages are fetched; external homepages are not crawled.  Direct
repository links in the engine's Links field count even when CCRL calls them
"Homepage".  Ordinary homepages, binary downloads and references in historical
commentary do not.  CCRL folds ShashChess into Stockfish; that family's details
are also inspected for explicitly named fork source links, without stripping
version suffixes.  Such forks get separate observations, not Stockfish's code.
Empty code_urls does not mean closed source: older versions
and families absent from the best-version list are not exhaustively researched.
Fetch failures during enrichment issue warnings but preserve the family list.
"""

from html.parser import HTMLParser
import re
from urllib.parse import parse_qs, urlencode, urljoin, urlsplit
import warnings


INDEX_URL = "https://computerchess.org.uk/4040/index.html"
DETAILS_URL = "https://computerchess.org.uk/4040/cgi/engine_details.cgi"
COMPARE_URL = "https://computerchess.org.uk/4040/cgi/compare_engines.cgi"
_BATCH_SIZE = 20


def _text(parts):
    return " ".join("".join(parts).split())


class _Index(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.families = []
        self.engines = []
        self._family_select = False
        self._option = None
        self._value = None
        self._name_cell = False

    def _finish_option(self):
        if self._option is not None:
            name = self._value if self._value is not None else _text(self._option)
            if name.strip() and name.strip() not in self.families:
                self.families.append(name.strip())
        self._option = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "select":
            self._family_select = attrs.get("name") == "family"
        elif tag == "option" and self._family_select:
            self._finish_option()
            self._option = []
            self._value = attrs.get("value")
        elif tag == "td":
            self._name_cell = "name" in attrs.get("class", "").split()
        elif tag == "a" and self._name_cell:
            href = urlsplit(urljoin(INDEX_URL, attrs.get("href", "")))
            if href.path.endswith("/engine_details.cgi"):
                for engine in parse_qs(href.query).get("eng", []):
                    if engine not in self.engines:
                        self.engines.append(engine)

    def handle_data(self, data):
        if self._option is not None:
            self._option.append(data)

    def handle_endtag(self, tag):
        if tag == "option":
            self._finish_option()
        elif tag == "select":
            self._finish_option()
            self._family_select = False
        elif tag == "td":
            self._name_cell = False


class _Details(HTMLParser):
    """Keep only each details header, never its opponent table."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.records = []
        self.record = None
        self._header_depth = 0
        self._cell = None
        self._anchor = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        classes = attrs.get("class", "").split()
        if tag == "div" and "details_container" in classes:
            self.record = {"family": None, "engine": None, "cells": []}
            self.records.append(self.record)
        if self.record is None:
            return
        if tag == "table":
            if "det_header" in classes:
                self._header_depth = 1
            elif self._header_depth:
                self._header_depth += 1
        if not self._header_depth:
            return
        if tag == "td":
            self._finish_cell()
            self._cell = {"text": [], "links": [], "class": classes}
        elif tag == "a":
            href = attrs.get("href", "")
            query = parse_qs(urlsplit(href).query)
            if urlsplit(href).path.endswith("compare_engines.cgi"):
                family = query.get("family", [])
                if len(family) == 1:
                    self.record["family"] = family[0]
            if self._cell is not None:
                if "hname" in self._cell["class"]:
                    self.record["engine"] = next(iter(query.get("eng", [])), None)
                self._anchor = {"url": href, "text": []}

    def handle_data(self, data):
        if self._header_depth and self._cell is not None:
            self._cell["text"].append(data)
            if self._anchor is not None:
                self._anchor["text"].append(data)

    def _finish_cell(self):
        if self._cell is not None:
            self.record["cells"].append(self._cell)
        self._cell = None
        self._anchor = None

    def handle_endtag(self, tag):
        if tag == "a" and self._anchor is not None:
            if self._cell is not None:
                self._cell["links"].append(self._anchor)
            self._anchor = None
        elif tag == "td" and self._header_depth:
            self._finish_cell()
        elif tag == "table" and self._header_depth:
            self._finish_cell()
            self._header_depth -= 1


def _is_code_url(url, label):
    parsed = urlsplit(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return False
    if re.search(r"\bsource(?:s|\s+code)?\b", label, re.I):
        return True
    host = (parsed.hostname or "").lower()
    path = parsed.path.rstrip("/")
    pieces = path.strip("/").split("/")
    if host in ("github.com", "bitbucket.org", "codeberg.org"):
        if len(pieces) == 2:
            return True
        if len(pieces) > 2 and pieces[2] in ("tree", "blob", "src", "archive"):
            return True
    if host == "gitlab.com" and len(pieces) >= 2:
        return "-/" not in path or any(
            "/-/" + kind + "/" in path for kind in ("tree", "blob", "archive")
        )
    if host in ("sourceforge.net", "www.sourceforge.net"):
        return bool(re.match(r"^/p/[^/]+/(?:code|git|svn)(?:/|$)", path))
    return bool(
        re.search(r"(?:^|[/_.-])(?:src|source|sources)(?:[/_.-]|$)", path, re.I)
        and re.search(r"\.(?:zip|7z|tar(?:\.(?:gz|bz2|xz))?|tgz)$", path, re.I)
    )


def _source_links(record, evidence):
    for cell in record["cells"]:
        if re.match(r"Links?\s*:", _text(cell["text"]), re.I):
            for link in cell["links"]:
                code = urljoin(evidence, link["url"])
                label = _text(link["text"])
                if _is_code_url(code, label):
                    yield code, label


def _named_fork(record, evidence):
    engine = record["engine"] or ""
    for code, label in _source_links(record, evidence):
        match = re.fullmatch(r"(.+?)\s+(?:homepage|sources?|source code)", label, re.I)
        if not match:
            continue
        name = match[1]
        if engine.casefold().startswith(name.casefold() + " "):
            name = engine[:len(name)]
            if name.casefold() != (record["family"] or "").casefold():
                return name
    return None


def _merge_record(record, observations, forks_only=False):
    family = record["family"]
    if family is None:
        for cell in record["cells"]:
            match = re.fullmatch(
                r"This is the only (.+) version we tested\.",
                _text(cell["text"]),
            )
            if match:
                family = match[1]
                break
    if family not in observations:
        warnings.warn(
            "CCRL detail has no recognized authoritative family: %r"
            % record["engine"],
            RuntimeWarning,
        )
        return
    evidence = DETAILS_URL + "?" + urlencode(
        {"print": "Details", "each_game": "0", "eng": record["engine"]}
    )
    fork = _named_fork(record, evidence)
    if forks_only and not fork:
        return
    if fork:
        family = fork
        observations.setdefault(family, {
            "family": family, "label": family, "url": evidence, "code_urls": [],
        })
    links = observations[family]["code_urls"]
    for code, label in _source_links(record, evidence):
        # A fork header can also link its parent's repository.
        if fork and not label.casefold().startswith(fork.casefold() + " "):
            continue
        if not any(item["url"] == code for item in links):
            links.append({"url": code, "evidence_url": evidence})


def _collect(fetch) -> list[dict]:
    """Return one observation per authoritative CCRL 40/15 family.

    ``fetch(url, data=None)`` supplies decoded HTML and owns caching/timeouts.
    At most one best-version details record per listed engine is requested,
    sequentially in batches of 20; no individual-version crawl is performed.
    One extra Stockfish family request recovers CCRL's explicitly linked forks.
    Enrichment errors warn rather than silently presenting missing links.
    """
    index = _Index()
    index.feed(fetch(INDEX_URL))
    index.close()
    if not index.families:
        raise ValueError("CCRL index contains no family selector; layout/access changed")
    observations = {
        family: {
            "family": family,
            "label": family,
            "url": COMPARE_URL + "?" + urlencode(
                {"family": family, "print": "Rating list"}
            ),
            "code_urls": [],
        }
        for family in index.families
    }
    if not index.engines:
        warnings.warn("CCRL index has no best-version detail links", RuntimeWarning)
    for start in range(0, len(index.engines), _BATCH_SIZE):
        engines = index.engines[start:start + _BATCH_SIZE]
        query = [("print", "Details"), ("each_game", "0")]
        query.extend(("eng", engine) for engine in engines)
        url = DETAILS_URL + "?" + urlencode(query)
        try:
            details = _Details()
            details.feed(fetch(url))
            details.close()
            if not details.records:
                raise ValueError("no engine details headers found")
        except Exception as exc:
            warnings.warn(
                "CCRL details batch %d failed: %s" % (start // _BATCH_SIZE + 1, exc),
                RuntimeWarning,
            )
            continue
        returned = {record["engine"] for record in details.records}
        missing = set(engines) - returned
        if missing:
            warnings.warn(
                "CCRL details batch omitted %d requested engines" % len(missing),
                RuntimeWarning,
            )
        for record in details.records:
            engine = record["engine"]
            if engine not in engines:
                warnings.warn("CCRL detail has an unexpected engine", RuntimeWarning)
                continue
            _merge_record(record, observations)
    if "Stockfish" in observations:
        url = DETAILS_URL + "?" + urlencode(
            {"print": "Details", "each_game": "0", "family": "Stockfish"}
        )
        try:
            details = _Details()
            details.feed(fetch(url))
            details.close()
            if not details.records:
                raise ValueError("no Stockfish family detail headers found")
            for record in details.records:
                if record["family"] == "Stockfish" and record["engine"]:
                    _merge_record(record, observations, forks_only=True)
        except Exception as exc:
            warnings.warn("CCRL fork enrichment failed: %s" % exc, RuntimeWarning)
    return list(observations.values())


def collect(fetch) -> list[dict]:
    """Collect families, exposing enrichment issues in rows and last_warnings.

    Warnings are attached to every row because a failed bulk request cannot
    always be attributed to a particular family.  This conservatively preserves
    incomplete-enrichment evidence in persisted catalog provenance.
    """
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
