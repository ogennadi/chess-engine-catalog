"""Read RWBC's alphabetic chronology, retaining its original CSV evidence."""

import csv
import io
import re
from urllib.parse import unquote, urlsplit, urlunsplit

from collectors.amateurschach import code_url, original_url


SOURCE_URL = "https://rwbc-chess.de/"
SHEET_URL = (
    "https://docs.google.com/spreadsheets/d/"
    "1Qm_YC4Do6Edj-bTCO5IGc6e4SeDSqRijJjSkHiiSQO0/"
)
CSV_URL = SHEET_URL + "gviz/tq?tqx=out:csv&sheet=Chronology%20-%20Alpha%20List"
HEADERS = [
    "", "Name\n(color description\ns. TOC)", "Author L.N. F.N.", "CC3",
    "F1", "F2", "LR/LV (dev)", "", "", "RC\n(s. TOC)", "Prot", "Src",
    "PL", "NN\nNNUE", "MP", "EGT", "N-Alias\n(base/add.)", "N-Pre\nLV",
    "Dist.", "Vers. FR", "", "", "", "CMD (arg) Config\nExamples",
    "Peculiarities + Bugs + Info", "Web/Download",
]
# These are explicitly numbered releases, not ancestry-based identity mappings.
RELEASE_FAMILIES = {"Rodent II-IV": "Rodent", "Rodent V": "Rodent"}
_URL = re.compile(r"https?://[^\s<>\"']+", re.I)
_NON_CODE = re.compile(
    r"(?:^|[-_/.\s])(?:nnue[-_]?nets?|nets?|networks?|weights?|"
    r"training[-_]?data|fishtest|chesslib|chess[-_]library|pesto|"
    r"binaries|binary|user-attachments)(?:$|[-_/.\s])", re.I,
)


def _name(value):
    """Remove sheet classification marks, never infer releases from digits."""
    return " ".join(value.replace("#", "").replace("*", "").split())


def _key(value):
    return re.sub(r"[^a-z0-9]", "", value.casefold())


def _alternates(value):
    # Parentheses in N-Alias identify ancestors, PSTs and libraries, not aliases.
    value = re.sub(r"\([^)]*\)", "", value, flags=re.S)
    return [line.strip() for line in value.splitlines() if line.strip()]


def extract_urls(value):
    return list(dict.fromkeys(match.rstrip(".,;)") for match in _URL.findall(value)))


def _repository(url):
    parsed = urlsplit(original_url(url))
    if not parsed.hostname:
        return None
    parts = parsed.path.strip("/").split("/")
    host = parsed.hostname.lower()
    if host == "github.com" and parts[0].casefold() in {
        "user-attachments", "orgs", "users", "topics", "collections", "sponsors",
    }:
        return None
    repository = code_url(url)
    if not repository:
        return None
    if host == "gitlab.com":
        # Unlike GitHub, GitLab permits arbitrarily nested project groups.
        path = parsed.path.split("/-/")[0].rstrip("/")
        repository = urlunsplit((parsed.scheme, parsed.netloc, path, "", ""))
    elif host == "sourceforge.net" and parts[0] == "p":
        repository = f"https://sourceforge.net/projects/{parts[1]}/"
    return repository


def _source_archive(url):
    original_path = unquote(urlsplit(original_url(url)).path)
    path = original_path.lower()
    if not re.search(r"\.(?:zip|7z|rar|tar(?:\.(?:gz|bz2|xz))?|tgz)$", path):
        return False
    if _NON_CODE.search(path) or re.search(r"(?:^|[-_/])(?:win32|win64|linux|exe)", path):
        return False
    return bool(
        re.search(r"(?:^|[-_/.\s])(?:src|sources?|source[-_]?code)(?:$|[-_/.\s(])", path)
        or re.search(r"(?:Src|Source)(?:[-_.\s(]|$)", original_path.rsplit("/", 1)[-1])
    )


def _code_urls(row, known_names):
    if row[11].strip().casefold() != "yes":
        return []
    names = [_name(row[1]), *_alternates(row[16])]
    identities = {_key(name) for name in names if _key(name)}
    candidates = []
    for url in extract_urls(row[25]):
        repository = _repository(url)
        if repository and not _NON_CODE.search(unquote(urlsplit(repository).path)):
            project = urlsplit(repository).path.rstrip("/").split("/")[-1]
            project_key = _key(project)
            matches = 2 if project_key in identities else int(any(
                len(key) >= 3 and (key in project_key or project_key in key)
                for key in identities
            ))
            # Links to another listed engine are not this engine's source.
            other_engine = project_key in known_names and project_key not in identities
            if not other_engine:
                candidates.append((repository, matches))
        elif not repository and _source_archive(url):
            candidates.append((url, 2))
    matched = max((matches for _, matches in candidates), default=0)
    result = []
    for url, matches in candidates:
        # Prefer exact port names over ancestor substrings. Without a name match,
        # retain only the first repository (often named just "chess").
        if matches < matched or (not matches and result):
            continue
        item = {"url": url, "evidence_url": CSV_URL}
        if item not in result:
            result.append(item)
    return result


def _parse(text):
    try:
        rows = list(csv.reader(io.StringIO(text.lstrip("\ufeff"), newline=""), strict=True))
    except csv.Error as error:
        raise ValueError(f"Malformed RWBC CSV: {error}") from error
    if len(rows) < 3 or rows[1] != HEADERS or len(rows[0]) != len(HEADERS):
        raise ValueError("Malformed RWBC chronology headers")
    counts = re.findall(r"current count\s*::\s*(\d+)", " ".join(rows[0]), re.I)
    if len(counts) != 1 or int(counts[0]) <= 0:
        raise ValueError("Invalid RWBC declared count")
    count = int(counts[0])
    populated = []
    padding = False
    for rank, row in enumerate(rows[2:], 1):
        if len(row) != len(HEADERS):
            raise ValueError(f"Malformed RWBC row {rank}: expected {len(HEADERS)} columns")
        if not re.fullmatch(r"[1-9]\d*", row[0]) or int(row[0]) != rank:
            raise ValueError(f"Invalid RWBC rank at row {rank}: {row[0]!r}")
        # The sheet preallocates numbered, otherwise entirely empty slots.
        if not any(row[1:]) and rank > count:
            padding = True
            continue
        if not row[1].strip() or not _name(row[1]):
            raise ValueError(f"Empty RWBC engine name at rank {rank}")
        if padding:
            raise ValueError(f"RWBC engine after empty padding at rank {rank}")
        populated.append(row)
    if len(populated) != count:
        raise ValueError(f"RWBC declared count {count} does not match {len(populated)} engine rows")
    return rows[0], populated, count


def collect(fetch):
    metadata, rows, count = _parse(fetch(CSV_URL))
    known_names = {_key(_name(row[1])) for row in rows}
    checked_at = getattr(fetch, "checked_at", {}).get(CSV_URL)
    observations = []
    for row in rows:
        name = _name(row[1])
        observation = {
            "family": RELEASE_FAMILIES.get(name, name),
            "label": row[1], "original_name": row[1],
            "url": CSV_URL, "listing_url": SOURCE_URL, "sheet_url": SHEET_URL,
            "rank": int(row[0]), "authors": row[2],
            "alternate_names": row[16], "previous_names": row[17],
            "distribution": row[18], "source_flag": row[11],
            "links": extract_urls(row[25]), "row": list(row),
            "headers": list(HEADERS), "sheet_metadata": list(metadata),
            "declared_count": count, "code_urls": _code_urls(row, known_names),
        }
        if checked_at:
            observation["checked_at"] = checked_at
        observations.append(observation)
    return observations


def identity_report(rows, canonical_names, aliases):
    """Suggest review mappings without applying ambiguous alternate identities."""
    known = {name.strip().casefold(): name for name in canonical_names}
    overrides = {alias.strip().casefold(): target for alias, target in aliases.items()}
    families = {row["family"].casefold(): row["family"] for row in rows}
    suggestions = []
    conflicts = []
    new = set()
    for row in rows:
        family = row["family"]
        target = overrides.get(family.casefold(), known.get(family.casefold(), family))
        if target.casefold() not in known:
            new.add(target)
        candidates = []
        for field in ("alternate_names", "previous_names"):
            for alternate in _alternates(row[field]):
                alternate = _name(alternate)
                key = alternate.casefold()
                destination = overrides.get(key, known.get(key, families.get(key)))
                if destination and destination.casefold() != target.casefold():
                    candidate = {
                        "family": family, "alternate": alternate,
                        "suggested_canonical": destination, "field": field,
                        "rank": row["rank"],
                    }
                    if candidate not in candidates:
                        candidates.append(candidate)
                    conflicts.append(candidate)
        suggestions.extend(candidates)
    return {
        "rows": len(rows),
        "source_link_families": len({row["family"] for row in rows if row["code_urls"]}),
        "new_canonical_names": sorted(new, key=str.casefold),
        "mapping_suggestions": suggestions, "identity_conflicts": conflicts,
    }
