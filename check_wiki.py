"""Check every catalog family against Chess Programming Wiki's title index."""

import argparse
import json

from collect import ROOT, publish
from collectors.http import Fetcher
from collectors.wiki import check


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    flags = parser.add_mutually_exclusive_group()
    flags.add_argument("--refresh", action="store_true", help="Download the title index again")
    flags.add_argument("--offline", action="store_true", help="Use cached title index only")
    args = parser.parse_args()
    catalog_path = ROOT / "data" / "engines.json"
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    fetch = Fetcher(ROOT / ".cache" / "http", refresh=args.refresh, offline=args.offline)
    results = check(catalog["engines"], fetch)
    path = ROOT / "data" / "chessprogramming-wiki.json"
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)
    unresolved = json.loads((ROOT / "data" / "unresolved-lichess.json").read_text(encoding="utf-8"))
    publish(catalog, unresolved)
    counts = catalog["chessprogramming_wiki"]
    print(
        f"Checked {len(catalog['engines'])} families: {counts['found']} found, "
        f"{counts['not_found']} no matching indexed title, {counts['needs_review']} need review."
    )


if __name__ == "__main__":
    main()
