"""Collect families from Stefan Pohl's full UHO and EAS rating tables."""

import base64
import json
import re
from html.parser import HTMLParser
from urllib.parse import urljoin


SOURCE_URL = "https://www.sp-cc.de/files/uho_full_list.txt"
BAE_README_URL = "https://api.github.com/repos/tsoj/Stockfish-BAE/readme"
GAIA_README_URL = "https://api.github.com/repos/jromang/gaiachess/readme"
REBEL_README_URL = "https://api.github.com/repos/egh-s/Rebel-14.1.02-Chess-System-TAL-1/readme"
SLOW_CHESS_URL = "https://www.3dkingdoms.com/chess/slow.htm"
_UHO_ROW = re.compile(
    r"^\s*(\d+)\s+(.+?)\s+:\s+\d+\s+\d+\s+\d+\s+\d+\s+"
    r"[\d.]+%\s+[\d.]+\s+[\d.]+%(?:\s+\((?:NEW|OLD)\))?\s*$"
)
_EAS_ROW = re.compile(
    r"^\s*(\d+)\s+\d+\s+(?:[\d.]+%\s+){4}\d+\s+(.+?)\s*$"
)
_NAMED_VARIANTS = (
    ("Stockfish BAE", "Stockfish BAE"),
    ("Stockfish final HCE", "Stockfish"),
    ("Stockfish", "Stockfish"),
    ("CS Tal", "Chess System Tal"),
    ("CSTal", "Chess System Tal"),
    ("KomodoDragon", "Dragon"),
    ("Rebel", "Rebel"),
    ("Rodent", "Rodent"),
)


class _Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.urls = set()

    def handle_starttag(self, tag, attrs):
        href = dict(attrs).get("href")
        if tag == "a" and href:
            self.urls.add(urljoin(SLOW_CHESS_URL, href))


def enrich_source_links(rows, fetch):
    """Attach reviewed external evidence without treating dependencies as engine code."""
    families = {row["family"] for row in rows}
    links = {}
    for family, api_url, repository, marker, release, note in [
        (
            "Gaia", GAIA_README_URL, "https://github.com/jromang/gaiachess",
            "Gaia 4", "4.x",
            "Gaia 4 rewrite by Julien Romang; unrelated to gaetanserre/GAiA.",
        ),
        (
            "Rebel", REBEL_README_URL,
            "https://github.com/egh-s/Rebel-14.1.02-Chess-System-TAL-1",
            "Rebel-14.1.02", "14.1.02",
            "Historical Rebel 14.1.02/Tal source; not verified source for "
            "the listed Rebel 16.3 or Extreme/EAS releases.",
        ),
    ]:
        if family not in families:
            continue
        readme = json.loads(fetch(api_url))
        content = base64.b64decode(readme["content"], validate=False).decode("utf-8")
        if marker not in content or not readme["html_url"].startswith(repository + "/blob/"):
            raise ValueError(f"{family} README no longer confirms the reviewed source identity")
        links[family] = {
            "url": repository, "evidence_url": readme["html_url"],
            "source_release": release, "note": note,
        }
    if "Slow Chess" in families:
        page = fetch(SLOW_CHESS_URL)
        parser = _Links()
        parser.feed(page)
        source_url = urljoin(SLOW_CHESS_URL, "Slow296src.zip")
        if source_url not in parser.urls or "Very Old (and messy) Source Code" not in page:
            raise ValueError("Slow Chess page no longer confirms the reviewed historical source archive")
        links["Slow Chess"] = {
            "url": source_url, "evidence_url": SLOW_CHESS_URL,
            "source_release": "2.96 (historical numbering)",
            "note": "Historical source based on old Slow Chess 2.94, not "
                    "source for the modern Slow Chess Blitz 2.9 in the rating list.",
        }
    for row in rows:
        if row["family"] in links:
            row["code_urls"].append(dict(links[row["family"]]))


def family_name(label):
    for prefix, family in _NAMED_VARIANTS:
        if label == prefix or label.startswith(prefix + " "):
            return family
    words = label.split()
    for index, word in enumerate(words[1:], 1):
        if re.match(r"(?:v?\d|avx|a512|bmi|popavx|nnue)", word, re.I):
            return " ".join(words[:index])
    raise ValueError(f"Unrecognized Stefan Pohl engine/version label: {label!r}")


def collect(fetch):
    text = fetch(SOURCE_URL)
    update = re.search(r"Full UHO-Ratinglist updated:\s*(\d{4}/\d{2}/\d{2})", text)
    if not update:
        raise ValueError("Stefan Pohl list has no recognized UHO update header")
    rows = []
    ranks = {"uho": [], "eas": []}
    section = None
    dates = {"uho": update.group(1)}
    for line in text.splitlines():
        eas_update = re.search(r"Full EAS-Ratinglist updated:\s*(\d{4}/\d{2}/\d{2})", line)
        if eas_update:
            dates["eas"] = eas_update.group(1)
        if re.search(r"\bProgram\s+Celo\s+\+\s+-\s+Games\b", line):
            section = "uho"
            continue
        if re.search(r"^Rank\s+EAS-Score\s+sacs\s+sacs\s+shorts\s+draws\s+moves\s+Engine/player", line):
            section = "eas"
            continue
        if line.startswith("***"):
            section = None
            continue
        pattern = _UHO_ROW if section == "uho" else _EAS_ROW if section == "eas" else None
        if pattern is None:
            continue
        match = pattern.fullmatch(line)
        if not match:
            if re.match(r"^\s*\d+\s", line):
                raise ValueError(f"Unrecognized {section} rating row: {line!r}")
            continue
        rank, label = match.groups()
        if section not in dates:
            raise ValueError(f"Stefan Pohl list has no {section} update date")
        ranks[section].append(int(rank))
        family = family_name(label)
        row = {
            "family": family, "label": label, "url": SOURCE_URL,
            "section": section, "rank": int(rank),
            "list_updated": dates[section].replace("/", "-"),
            "code_urls": [],
        }
        if family == "Stockfish BAE":
            row["identity_note"] = (
                "Stockfish fork replacing the classical evaluation with "
                "BAE (big array eval); kept separate from standard Stockfish."
            )
        elif family == "Cerberus":
            row["identity_note"] = (
                "Composite engine switching between Patricia and Velvet; "
                "not an alias of either component."
            )
            row["identity_evidence_url"] = "https://www.sp-cc.de/cerberus-project.htm"
        rows.append(row)
    for section, values in ranks.items():
        if not values or values != list(range(1, len(values) + 1)):
            raise ValueError(f"Missing, duplicated, or nonsequential {section} table ranks")
    bae_rows = [row for row in rows if row["family"] == "Stockfish BAE"]
    if bae_rows:
        readme = json.loads(fetch(BAE_README_URL))
        content = base64.b64decode(readme["content"], validate=False).decode("utf-8")
        if "Stockfish BAE is a fork" not in content or not readme["html_url"].startswith(
            "https://github.com/tsoj/Stockfish-BAE/"
        ):
            raise ValueError("Stockfish BAE README no longer confirms the reviewed fork identity")
        for row in bae_rows:
            row["identity_evidence_url"] = readme["html_url"]
            row["code_urls"] = [{
                "url": "https://github.com/tsoj/Stockfish-BAE",
                "evidence_url": readme["html_url"],
            }]
    enrich_source_links(rows, fetch)
    return rows
