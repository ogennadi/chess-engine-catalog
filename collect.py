"""Build the engine-family catalog from the registered public lists."""

import argparse
import csv
import importlib
import io
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit

from collectors.http import Fetcher
from collectors import lichess


ROOT = Path(__file__).resolve().parent


def identity_key(name):
    return re.sub(r"\s+", " ", name.strip()).casefold()


def _source_alias(item, raw_name, rules):
    """Return the reviewed rule that reassigns a homonymous source entry, if any."""
    for rule in rules:
        if (
            item.get("source") in rule["sources"]
            and identity_key(raw_name) == identity_key(rule["family"])
            and re.search(rule.get("label_pattern", ""), item.get("label", ""))
        ):
            return rule
    return None


def unused_source_aliases(observations, rules):
    used = {
        id(rule) for item in observations
        for rule in [_source_alias(item, item["family"].strip(), rules)] if rule
    }
    return [rule for rule in rules if id(rule) not in used]


def url_key(url):
    return url.strip().rstrip("/").casefold()


def merge(observations, aliases, source_aliases=(), not_source=()):
    canonical = {identity_key(alias): target for alias, target in aliases.items()}
    rejected = {url_key(rule["url"]): rule for rule in not_source}
    engines = {}
    for item in observations:
        raw_name = item["family"].strip()
        # Same-named but different programs are split per source before the
        # name-only aliases, which would otherwise merge them.
        rule = _source_alias(item, raw_name, source_aliases)
        name = rule["target"] if rule else canonical.get(identity_key(raw_name), raw_name)
        if not name:
            raise ValueError("Engine-family names cannot be empty")
        key = identity_key(name)
        engine = engines.setdefault(
            key, {"name": name, "aliases": [], "provenance": [], "source_code": []}
        )
        if raw_name != engine["name"] and raw_name not in engine["aliases"]:
            engine["aliases"].append(raw_name)
        provenance = {k: v for k, v in item.items() if k not in ("family", "code_urls")}
        if rule:
            provenance.setdefault("identity_evidence_url", rule["evidence_url"])
        if provenance not in engine["provenance"]:
            engine["provenance"].append(provenance)
        for code in item.get("code_urls", []):
            code = {**code, "source": item["source"]}
            rule = rejected.get(url_key(code["url"]))
            if rule and identity_key(rule["family"]) == key:
                # Reviewed: the list links this URL as source, but it holds no source code.
                entry = {**code, "reason": rule["note"], "review_evidence_url": rule["evidence_url"]}
                if entry not in engine.setdefault("rejected_source_code", []):
                    engine["rejected_source_code"].append(entry)
                continue
            if code not in engine["source_code"]:
                engine["source_code"].append(code)
    result = sorted(engines.values(), key=lambda engine: identity_key(engine["name"]))
    for engine in result:
        engine["aliases"].sort(key=identity_key)
        engine["source_code"].sort(key=lambda code: (code["url"], code["evidence_url"]))
        if "rejected_source_code" in engine:
            engine["rejected_source_code"].sort(key=lambda code: (code["url"], code["source"]))
        engine["provenance"].sort(key=lambda p: (p["source"], p["label"], p["url"]))
    return result


def unused_not_source(engines, rules):
    used = {
        (identity_key(engine["name"]), url_key(code["url"]))
        for engine in engines for code in engine.get("rejected_source_code", [])
    }
    return [rule for rule in rules if (identity_key(rule["family"]), url_key(rule["url"])) not in used]


def mark_unreachable_links(engines, rules):
    """Flag reviewed unreachable source links and add their verified replacements; return unused rules."""
    by_family = {}
    for rule in rules:
        by_family.setdefault(identity_key(rule["family"]), []).append(rule)
    used = set()
    for engine in engines:
        for index, rule in enumerate(by_family.get(identity_key(engine["name"]), [])):
            hits = [c for c in engine["source_code"] if url_key(c["url"]) == url_key(rule["url"])]
            if not hits:
                continue
            used.add((identity_key(rule["family"]), index))
            for code in hits:
                code["unreachable"] = {"checked_at": rule["checked_at"], "status": rule["status"]}
            replacement = rule.get("replacement")
            if replacement and all(url_key(c["url"]) != url_key(replacement["url"]) for c in engine["source_code"]):
                engine["source_code"].append({
                    "url": replacement["url"], "evidence_url": replacement.get("evidence_url", replacement["url"]),
                    "source": "link-review", "kind": replacement["kind"],
                })
    return [
        rule for family, family_rules in by_family.items()
        for index, rule in enumerate(family_rules) if (family, index) not in used
    ]


def publish(catalog, unresolved, unreachable_links=()):
    directory = ROOT / "data"
    directory.mkdir(exist_ok=True)
    wiki_path = directory / "chessprogramming-wiki.json"
    if wiki_path.exists():
        from collectors.wiki import attach
        attach(catalog, json.loads(wiki_path.read_text(encoding="utf-8")))
    wiki_sources_path = directory / "chessprogramming-source-code.json"
    if wiki_sources_path.exists():
        from collectors.wiki_sources import attach as attach_sources
        attach_sources(catalog, json.loads(wiki_sources_path.read_text(encoding="utf-8")))
    import source_status
    status_path = directory / "source-status.json"
    status = json.loads(status_path.read_text(encoding="utf-8")) if status_path.exists() else {}
    source_status.attach(catalog, status)
    engines = catalog["engines"]
    for rule in mark_unreachable_links(engines, unreachable_links):
        print(f"WARNING: unreachable-link rule {rule['url']} matched no {rule['family']} link; review overrides.json", flush=True)
    outputs = {
        "engines.json": json.dumps(catalog, ensure_ascii=False, indent=2) + "\n",
        "engines.csv": catalog_csv(engines),
        "engine-names.txt": "".join(engine["name"] + "\n" for engine in engines),
        "unresolved-lichess.json": json.dumps(unresolved, ensure_ascii=False, indent=2) + "\n",
    }
    for filename, text in outputs.items():
        path = directory / filename
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(text, encoding="utf-8", newline="")
        temporary.replace(path)
    source_status.render_family_pages(engines, status, ROOT / "docs" / "families")


def catalog_csv(engines):
    """Spreadsheet export of catalog engines (with source status already attached)."""
    import source_status
    table = io.StringIO(newline="")
    writer = csv.writer(table)
    writer.writerow([
        "name", "aliases", "sources", "provenance_urls", "source_code_urls",
        "source_availability",
        "chessprogramming_wiki_url", "chessprogramming_wiki_status",
        "chessprogramming_wiki_checked_at",
    ])
    for engine in sorted(engines, key=lambda engine: identity_key(engine["name"]), reverse=True):
        wiki = engine.get("chessprogramming_wiki", {})
        writer.writerow([
            engine["name"], "; ".join(engine["aliases"]),
            "; ".join(sorted({p["source"] for p in engine["provenance"]})),
            "; ".join(sorted({p["url"] for p in engine["provenance"]})),
            "; ".join(sorted({c["url"] for c in engine["source_code"]})),
            source_status.availability_label(engine),
            wiki.get("url") or "", wiki.get("status", "not_checked"),
            wiki.get("checked_at") or "",
        ])
    return table.getvalue()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh", action="store_true", help="Re-fetch cached pages (at most one request/second)")
    parser.add_argument("--offline", action="store_true", help="Use cached responses only; fail if any are missing")
    args = parser.parse_args()
    if args.refresh and args.offline:
        parser.error("--refresh and --offline cannot be combined")
    fetch = Fetcher(ROOT / ".cache" / "http", refresh=args.refresh, offline=args.offline)
    sources = json.loads((ROOT / "sources.json").read_text(encoding="utf-8"))
    overrides = json.loads((ROOT / "overrides.json").read_text(encoding="utf-8"))
    observations, statuses, unresolved = [], [], []
    previous_path = ROOT / "data" / "engines.json"
    previous = json.loads(previous_path.read_text(encoding="utf-8")) if previous_path.exists() else {"engines": []}

    for source in sources:
        print(f"Collecting {source['id']}...", flush=True)
        status = {k: v for k, v in source.items() if k != "collector"}
        try:
            if source["collector"] is None:
                fetch(source["url"])
                raise ValueError(f"{source['url']} is reachable but needs a collector")
            if source["collector"] == "lichess":
                known_names = [
                    engine["name"] for engine in merge(
                        observations, overrides["aliases"], overrides["source_aliases"]
                    )
                ]
                rows, unresolved, counts = lichess.collect(
                    fetch, known_names, overrides["lichess_accounts"]
                )
                status.update(counts)
            else:
                module = importlib.import_module("collectors." + source["collector"])
                if getattr(module, "COLLECT_FROM_SOURCE_URL", False):
                    rows = module.collect(fetch, source["url"])
                else:
                    rows = module.collect(fetch)
                warnings = getattr(module.collect, "last_warnings", [])
                if warnings:
                    status["warnings"] = warnings
                    for row in rows:
                        row.pop("warnings", None)
            if not rows:
                raise ValueError(f"{source['id']} returned no engine families")
            status["status"] = "collected"
        except (HTTPError, URLError, TimeoutError) as error:
            status["status"] = "unavailable"
            status["error"] = str(error)
            print(f"WARNING: {source['id']}: {error}", flush=True)
            if source["id"] == "lichess":
                pending_path = ROOT / "data" / "unresolved-lichess.json"
                if pending_path.exists():
                    unresolved = json.loads(pending_path.read_text(encoding="utf-8"))
            # Do not erase previously observed engines when a source is down.
            rows = []
            for engine in previous["engines"]:
                for provenance in engine["provenance"]:
                    if provenance["source"] == source["id"]:
                        rows.append({
                            **provenance, "family": engine["name"],
                            "code_urls": [
                                {k: code[k] for k in ("url", "evidence_url")} if "reason" in code else code
                                for code in engine["source_code"] + engine.get("rejected_source_code", [])
                                if code.get("source") == source["id"]
                                or code["evidence_url"] == provenance["url"]
                            ],
                        })
            status["retained_stale_observations"] = len(rows)
        source_times = [
            timestamp for url, timestamp in fetch.checked_at.items()
            if urlsplit(url).hostname == urlsplit(source["url"]).hostname
        ]
        source_times.extend(row["checked_at"] for row in rows if row.get("checked_at"))
        status["checked_at"] = max(source_times) if source_times else None
        for row in rows:
            row["source"] = source["id"]
            row.setdefault("checked_at", fetch.checked_at.get(
                row["url"], status["checked_at"]
            ))
        if source["id"] == "lichess" and status["status"] == "collected":
            for candidate in unresolved:
                candidate["source"] = source["id"]
                candidate["checked_at"] = status["checked_at"]
        observations.extend(rows)
        status["observations"] = len(rows)
        statuses.append(status)

    catalog = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "coverage_complete": not unresolved and all(
            source["status"] == "collected" and not source.get("warnings")
            for source in statuses
        ),
        "sources": statuses,
        "engines": merge(
            observations, overrides["aliases"], overrides["source_aliases"], overrides.get("not_source_urls", [])
        ),
    }
    for rule in unused_source_aliases(observations, overrides["source_aliases"]):
        print(
            f"WARNING: source alias {rule['family']} -> {rule['target']} "
            f"matched no {'/'.join(rule['sources'])} entry; review overrides.json",
            flush=True,
        )
    for rule in unused_not_source(catalog["engines"], overrides.get("not_source_urls", [])):
        print(
            f"WARNING: not-source URL {rule['url']} matched no {rule['family']} link; review overrides.json",
            flush=True,
        )
    publish(catalog, unresolved, overrides.get("unreachable_source_urls", []))
    print(
        f"Wrote {len(catalog['engines'])} families; "
        f"{sum(bool(e['source_code']) for e in catalog['engines'])} with linked source code; "
        f"{len(unresolved)} Lichess accounts need identity review.",
        flush=True,
    )


if __name__ == "__main__":
    main()
