"""Read the engine directory from an OpenBench instance's sidebar."""

import html
import re
from urllib.parse import urlsplit


# collect.py passes the registered instance URL to collectors that set this.
COLLECT_FROM_SOURCE_URL = True

FORGES = ("github.com", "gitlab.com", "codeberg.org", "bitbucket.org", "git.sr.ht")
# Stock OpenBench uses an "Engines" sidebar list; some instances restyle it.
ENGINE_SECTIONS = (
    re.compile(r'<li class="header">\s*(?:Our\s+)?Engines\s*</li>(.*?)</ul>', re.S | re.I),
    re.compile(r"<summary>\s*Engines\b.*?</summary>(.*?)</div>", re.S | re.I),
)
LINK = re.compile(r'<a\b[^>]*\bhref="([^"]+)"[^>]*>(.*?)</a>', re.S)

# Reviewed sidebar links that are not public source; such rows keep no code link.
NOT_SOURCE = {
    "https://github.com/chesscom/torchdev":
        "Private repository (HTTP 404); Torch is closed source",
}
# Reviewed testing forks; the engine is credited to the repository GitHub
# reports it was forked from, with the fork page as evidence.
FORKS = {
    "https://github.com/andygrant/stockfish": "https://github.com/official-stockfish/Stockfish",
    "https://github.com/silverrzz/fairy-stockfish":
        "https://github.com/fairy-stockfish/Fairy-Stockfish",
}
# Reviewed repositories that GitHub reports under a new owner or name.
MOVED = {
    "https://github.com/thetilted096/wilted-chess-engine":
        "https://github.com/THETILTED1/Wilted-Chess-Engine",
    "https://github.com/aronpetko/vine": "https://github.com/vine-chess/vine",
    "https://github.com/crippa1337/pytteliten": "https://github.com/1337crisis/Pytteliten",
    "https://github.com/crippa1337/svart": "https://github.com/feliskio/svart",
    "https://github.com/dsekercioglu/blackmarlin": "https://github.com/jnlt3/blackmarlin",
    "https://github.com/jeffreyan11/uci-chess-engine":
        "https://github.com/jeffreyan11/laser-chess-engine",
}


def parse(text, page_url):
    for pattern in ENGINE_SECTIONS:
        match = pattern.search(text)
        if match:
            break
    else:
        raise ValueError(f"No engine directory found on OpenBench page {page_url}")
    rows, seen = [], set()
    for href, label in LINK.findall(match.group(1)):
        name = html.unescape(re.sub(r"<[^>]+>", "", label)).replace("\u2197", "").strip()
        project_url = html.unescape(href).strip().rstrip("/")
        if not name or name.casefold() in seen:
            continue
        seen.add(name.casefold())
        parts = urlsplit(project_url)
        row = {
            "family": name, "label": name, "url": page_url,
            "project_url": project_url, "code_urls": [],
        }
        key = project_url.casefold()
        if key in NOT_SOURCE:
            row["project_url_note"] = NOT_SOURCE[key]
        elif key in FORKS:
            row["code_urls"].append({"url": FORKS[key], "evidence_url": project_url})
        elif parts.hostname in FORGES and len(parts.path.strip("/").split("/")) >= 2:
            row["code_urls"].append({
                "url": MOVED.get(key, project_url), "evidence_url": page_url,
            })
        rows.append(row)
    if not rows:
        raise ValueError(f"OpenBench engine directory on {page_url} is empty")
    return rows


def collect(fetch, page_url):
    return parse(fetch(page_url), page_url)
