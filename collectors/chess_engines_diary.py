"""Collect both current CEDR rating tables, excluding books, GUIs and packs."""

import re

from collectors.cegt import _RatingTables, _clean, _family


SOURCE_URL = "https://chessengines.blogspot.com/p/rating-jcer.html"
HEADERS = ("ran", "player", "rating", "games", "w-d-l", "draw %", "points")
DERIVATIVE_HEADERS = ("pl", "engines", "rating", "games", "w-d-l", "score %", "points")


def family_name(label):
    label = re.sub(r"\s+(?:dev[- ]|r\d|rev\d).*$", "", label, flags=re.I)
    for prefix, family in {
        "Dragon free": "Dragon", "Bagatur.cpp": "BagaturCPP",
        "Colossus Chess": "Colossus", "Quanticade Phoenix": "Quanticade",
        "Rodent V": "Rodent", "Rusty Rival": "Rusty-Rival",
        "Spaghet BologNNese": "Spaghet", "Nalwald ab11891": "Nalwald",
        "Potential-unlocked": "Potential", "Stallion GB Edition": "Stallion",
        "Tuna2": "Tuna",
    }.items():
        if label == prefix or label.startswith(prefix + " "):
            return family
    return _family(label)


def collect(fetch):
    parser = _RatingTables()
    parser.feed(fetch(SOURCE_URL))
    tables = [
        table for table in parser.finish()
        if table and tuple(_clean("".join(c["text"])).casefold() for c in table[0])
        in (HEADERS, DERIVATIVE_HEADERS)
    ]
    if not tables:
        raise ValueError("Chess Engines Diary has no recognized CEDR rating tables")
    rows = []
    for number, table in enumerate(tables, 1):
        rank = 0
        for cells in table[1:]:
            values = [_clean("".join(c["text"])) for c in cells]
            if not any(values):
                continue
            rank += 1
            if len(values) != 7 or values[0] != str(rank) or not values[1]:
                raise ValueError("Malformed or nonsequential CEDR rating row")
            if not re.fullmatch(r"\d+(?:\.\d+)?", values[2]):
                raise ValueError("Malformed CEDR rating")
            rows.append({
                "family": family_name(values[1]), "label": values[1],
                "url": SOURCE_URL, "section": f"CEDR rating table {number}",
                "rank": rank, "code_urls": [],
            })
    if not rows:
        raise ValueError("Chess Engines Diary rating tables have no engines")
    return rows
