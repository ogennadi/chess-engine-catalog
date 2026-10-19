"""Match catalog families against the wiki's public, complete title index."""

import json
from urllib.parse import quote


BASE_URL = "https://chessprogramming.org/"
INDEX_URL = BASE_URL + "search-index.json"
TITLE_ALIASES = {
    "Atlas": "Atlas (ESP)",
    "Atlas (1967)": "Atlas",
    "BugChess": "BugChess FR",
    "Capivara LK": "Capivara",
    "Colossus": "Colossus Chess",
    "Der Bringer": "Bringer",
    "Dragon": "Dragon by Komodo Chess",
    "E.T. Chess": "E.T.Chess",
    "Fortress": "Fortress (Engine)",
    "Karballo": "Carballo",
    "Leela Chess": "Leela Chess Zero",
    "List": "List (Program)",
    "Little Goliath": "Goliath",
    "Little Goliath Evolution": "Goliath",
    "Loop": "Loop (Program)",
    "Loop-List": "Loop (Program)",
    "Predateur": "Pr\u00e9dateur",
    "Queen": "Queen (engine)",
    "rofChade": "RofChade",
    "Shallowblue": "Shallow Blue",
    "Vajolet": "Vajolet",
    "VanillaChess": "Vanilla Chess",
}
REVIEW_CANDIDATES = {}
REJECTED_CANDIDATES = {
    "Space": [{
        "title": "Space",
        "url": BASE_URL + "Space",
        "reason": "The Space article describes an evaluation term, not rustam-cpp's Space engine.",
        "identity_evidence_url": "https://github.com/rustam-cpp/Space-Engine",
    }],
    "Chaos (Quinniboi10)": [{
        "title": "CHAOS",
        "url": BASE_URL + "CHAOS",
        "reason": "The wiki's CHAOS is the 1970s mainframe program, not Quinniboi10's modern engine.",
        "identity_evidence_url": "https://github.com/Quinniboi10/Chaos",
    }],
    "Chess": [{
        "title": "Chess",
        "url": BASE_URL + "Chess",
        "reason": "The Chess article describes the game, not David Cimbalista's engine named Chess.",
        "identity_evidence_url": "https://github.com/stockfishdeveloper/C---Bitboard-Chess-Engine",
    }],
    "Nu-chess": [{
        "title": "Nuchess",
        "url": BASE_URL + "Nuchess",
        "reason": (
            "Frank's archived engine list identifies Nu-chess 1.0 "
            "(October 2021) as Filippo Marfe's engine. The wiki's Nuchess "
            "is David Slate and William Blanchard's Northwestern University "
            "Fortran program, which competed in the 1980 and 1983 world championships."
        ),
        "identity_evidence_url": (
            "https://web.archive.org/web/20260212005235/"
            "https://www.amateurschach.de/main/_engines.htm"
        ),
    }],
    "LazySMP": [{
        "title": "Lazy SMP",
        "url": BASE_URL + "Lazy_SMP",
        "reason": (
            "UBC lists an engine named LazySMP 5.0 avx2. The wiki's Lazy SMP "
            "article describes a parallel-search technique, not this engine."
        ),
        "identity_evidence_url": "https://e4e6.com/ubc_ratings.php",
    }],
    "Atlas": [{
        "title": "Atlas",
        "url": BASE_URL + "Atlas",
        "reason": (
            "Frank's archived engine list identifies modern Atlas 4.35 "
            "(December 2024) as Andres Manzanares's engine. The wiki's Atlas "
            "is Alex Bell's 1967 Algol program for the ICL Atlas computer."
        ),
        "identity_evidence_url": (
            "https://web.archive.org/web/20260212005235/"
            "https://www.amateurschach.de/main/_engines.htm"
        ),
    }],
    "Albatros": [{
        "title": "Albatross",
        "url": BASE_URL + "Albatross",
        "reason": (
            "No evidence connects the catalog's Albatros to Michael Parker's "
            "historical Albatross, written in Z80 assembly for the Nascom 1 "
            "and competing in 1980-1983. The name-matched Lichess account "
            "describes a C# engine running on a Raspberry Pi; its association "
            "with the UBC engine is not independently verified."
        ),
        "identity_evidence_url": "https://lichess.org/@/Albatros_Engine",
    }],
    "Achillees": [{
        "title": "Achilles",
        "url": BASE_URL + "Achilles",
        "reason": (
            "CCRL identifies Achillees as Daniel Diaz's engine (Spain). "
            "The wiki's Achilles is Vladan Vuckovic's parallel system based on Axon 3."
        ),
        "identity_evidence_url": (
            "https://computerchess.org.uk/4040/cgi/engine_details.cgi"
            "?print=Details&each_game=0&eng=Achillees+1.0+64-bit"
        ),
    }],
    "Pawn (Coelho)": [{
        "title": "Pawn",
        "url": BASE_URL + "Pawn",
        "reason": (
            "The Pawn article describes the chess piece. Rui Coelho's engine has "
            "no wiki article; Pawn (Program) is Thomas Starke's freeware program."
        ),
        "identity_evidence_url": (
            "https://computerchess.org.uk/4040/cgi/engine_details.cgi"
            "?print=Details&each_game=0&eng=pawn+4.0+64-bit+4CPU"
        ),
    }],
    "Robin (Dachtera)": [{
        "title": "Robin",
        "url": BASE_URL + "Robin",
        "reason": (
            "CCRL identifies Robin as Piotr Dachtera's engine (Poland). "
            "The wiki's Robin is P\u00e9ter Horv\u00e1th's MS-DOS program."
        ),
        "identity_evidence_url": (
            "https://computerchess.org.uk/4040/cgi/engine_details.cgi"
            "?print=Details&each_game=0&eng=Robin+0.983"
        ),
    }],
}


def check(engines, fetch):
    entries = json.loads(fetch(INDEX_URL))
    if not isinstance(entries, list) or not entries:
        raise ValueError("Wiki title index must be a nonempty array")
    titles = {}
    for entry in entries:
        if (
            not isinstance(entry, list) or len(entry) != 2
            or not all(isinstance(value, str) and value for value in entry)
        ):
            raise ValueError("Malformed wiki title-index entry")
        title, path = entry
        if path.startswith(("/", "http:", "https:")) or ".." in path.split("/"):
            raise ValueError(f"Unsafe wiki page path: {path}")
        if ":" in path:
            continue
        key = title.casefold()
        titles.setdefault(key, {})[path] = (title, path)
    if not titles:
        raise ValueError("Wiki index contains no main-namespace pages")
    checked_at = fetch.checked_at[INDEX_URL]
    results = {}
    for engine in engines:
        name = engine["name"]
        indexed_titles = {
            row["page_title"] for row in engine.get("provenance", [])
            if row.get("source") == "wiki-engines" and row.get("page_title")
        }
        reviewed_title = TITLE_ALIASES.get(name)
        if reviewed_title is None and len(indexed_titles) == 1:
            reviewed_title = next(iter(indexed_titles))
        queries = [reviewed_title] if reviewed_title else [name, *engine["aliases"]]
        matches = {}
        for query in queries:
            candidates = titles.get(query.casefold(), {})
            exact = {path: pair for path, pair in candidates.items() if pair[0] == query}
            matches.update(exact or candidates)
        rejected = REJECTED_CANDIDATES.get(name, [])
        rejected_titles = {candidate["title"].casefold() for candidate in rejected}
        matches = {
            path: pair for path, pair in matches.items()
            if pair[0].casefold() not in rejected_titles
        }
        result = {
            "status": "not_found", "url": None, "title": None,
            "checked_at": checked_at, "evidence_url": INDEX_URL,
            "method": "main-namespace-title-index",
            "titles_checked": list(dict.fromkeys(queries)),
        }
        if rejected:
            result["rejected_candidates"] = rejected
            if not matches:
                result["reason"] = "No matching indexed engine page found; reviewed lookalikes were rejected."
        if name in REVIEW_CANDIDATES:
            matches = {}
            for title in REVIEW_CANDIDATES[name]:
                matches.update(titles.get(title.casefold(), {}))
            result["status"] = "needs_review"
            result["reason"] = "Similar title refers to a different or unconfirmed engine, or a non-engine subject."
        elif len(matches) == 1:
            title, path = next(iter(matches.values()))
            result.update(
                status="found", title=title, url=BASE_URL + quote(path, safe="/_()%"),
                method="reviewed-title-alias" if reviewed_title else "exact-title-or-catalog-alias",
            )
        elif len(matches) > 1:
            result["status"] = "needs_review"
            result["reason"] = "Catalog names match more than one wiki page."
        if result["status"] == "needs_review":
            result["candidates"] = [
                {"title": title, "url": BASE_URL + quote(path, safe="/_()%")}
                for title, path in sorted(matches.values())
            ]
        results[name] = result
    return {
        "index_url": INDEX_URL, "checked_at": checked_at,
        "main_namespace_pages": sum(len(pages) for pages in titles.values()), "engines": results,
    }


def attach(catalog, results):
    counts = {"found": 0, "not_found": 0, "needs_review": 0, "not_checked": 0}
    for engine in catalog["engines"]:
        result = results["engines"].get(engine["name"])
        if result is None:
            result = {"status": "not_checked", "url": None, "title": None, "checked_at": None}
        engine["chessprogramming_wiki"] = result
        counts[result["status"]] += 1
    catalog["chessprogramming_wiki"] = {
        "index_url": results["index_url"], "checked_at": results["checked_at"],
        "main_namespace_pages": results["main_namespace_pages"], **counts,
    }
