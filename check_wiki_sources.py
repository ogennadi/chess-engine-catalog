"""Check wiki pages for reviewed engine source links missing from other lists."""

import argparse
import json

from collect import ROOT, publish
from collectors.http import Fetcher
from collectors.wiki_sources import check, orphan_reviews


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    flags = parser.add_mutually_exclusive_group()
    flags.add_argument("--refresh", action="store_true", help="Download wiki pages again")
    flags.add_argument("--offline", action="store_true", help="Use cached pages only")
    args = parser.parse_args()
    catalog = json.loads((ROOT / "data" / "engines.json").read_text(encoding="utf-8"))
    reviews = json.loads((ROOT / "wiki-source-overrides.json").read_text(encoding="utf-8"))
    fetch = Fetcher(ROOT / ".cache" / "http", refresh=args.refresh, offline=args.offline)
    results = check(catalog["engines"], fetch, reviews)
    for name in orphan_reviews(catalog["engines"], reviews):
        print(f"WARNING: wiki-source-overrides.json reviews {name!r}, which is not a catalog family "
              "(renamed or merged?); review it", flush=True)
    path = ROOT / "data" / "chessprogramming-source-code.json"
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)
    unresolved = json.loads((ROOT / "data" / "unresolved-lichess.json").read_text(encoding="utf-8"))
    publish(catalog, unresolved)
    counts = catalog["chessprogramming_source_code"]
    print(
        f"Checked {len(results['engines'])} wiki-linked families: "
        f"{counts['found']} with source links, {counts['no_source_link_found']} without, "
        f"{counts['needs_review']} need review."
    )


if __name__ == "__main__":
    main()
