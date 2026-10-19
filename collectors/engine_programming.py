"""Read chess-capable entries from the Engine Programming community list."""

import re
from urllib.parse import urlsplit


REVISION = "e48b281cb78d757d974e1eeb5e84024d4b1aef9e"
SOURCE_URL = "https://github.com/EngineProgramming/engine-list"
DOCUMENT_URL = f"{SOURCE_URL}/blob/{REVISION}/README.md"
RAW_URL = (
    "https://raw.githubusercontent.com/EngineProgramming/engine-list/"
    f"{REVISION}/README.md"
)
SECTIONS = {
    "Chess Engines": "chess-engines",
    "Chess960 Engines": "chess960-engines",
    "GGPs & Other Game Engines": "ggps--other-game-engines",
}


def collect(fetch):
    text = fetch(RAW_URL)
    section = None
    seen_sections = set()
    rows = []
    for line in text.splitlines():
        if line.startswith("#"):
            section = line.lstrip("#").strip()
            if section in SECTIONS:
                seen_sections.add(section)
            continue
        if section not in SECTIONS or not line.startswith("|"):
            continue
        cells = re.split(r"(?<!\\)\|", line)[1:-1]
        if not cells:
            continue
        name_cell = cells[0].strip()
        if name_cell == "Engine Name" or re.fullmatch(r"[-:\s]+", name_cell):
            continue
        if len(cells) < 3:
            raise ValueError(f"Incomplete community-list engine row: {line!r}")
        if section == "GGPs & Other Game Engines":
            games = {game.strip().casefold() for game in cells[2].split(",")}
            if "chess" not in games and "chess960" not in games:
                continue
        match = re.fullmatch(r"\[([^\]]+)\]\((https?://[^\s)]+)\)(.*)", name_cell)
        if not match:
            raise ValueError(f"Unrecognized community-list engine link: {name_cell!r}")
        family, project_url, suffix = match.groups()
        family = family.strip()
        if not family:
            raise ValueError("Empty community-list engine-family name")
        parsed = urlsplit(project_url)
        parts = parsed.path.strip("/").split("/")
        code = []
        if (
            parsed.netloc in ("github.com", "gitlab.com", "codeberg.org", "bitbucket.org")
            and len(parts) == 2 and all(parts)
        ):
            code.append({"url": project_url.rstrip("/"), "evidence_url": DOCUMENT_URL})
        rows.append({
            "family": family, "label": family + suffix,
            "url": DOCUMENT_URL + "#" + SECTIONS[section],
            "listing_url": SOURCE_URL, "project_url": project_url,
            "section": section, "revision": REVISION, "code_urls": code,
        })
    if seen_sections != set(SECTIONS) or not rows:
        raise ValueError("Community list is missing recognized chess-capable sections or entries")
    checked_at = getattr(fetch, "checked_at", {}).get(RAW_URL)
    if checked_at:
        for row in rows:
            row["checked_at"] = checked_at
    return rows
