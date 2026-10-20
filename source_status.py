"""Source-status research helpers.

    python source_status.py dossiers          # build .cache/research/dossiers.json
    python source_status.py record BATCH.json # validate and merge reviewed findings
    python source_status.py summary           # counts by tier and status
"""

import argparse
import json
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from html import unescape
from pathlib import Path

ROOT = Path(__file__).resolve().parent
STATUS_PATH = ROOT / "data" / "source-status.json"
RESEARCH_DIR = ROOT / ".cache" / "research"

LICENSING = {
    "open_source": "OSI/FSF-approved license or rights-holder public-domain dedication",
    "source_available": "rights holder published source under restrictive or missing license terms",
    "proprietary": "explicit closed-source statement, commercial product, or license limiting distribution to binaries",
    "unknown": "insufficient evidence, including leaked or third-party-preserved code without a license",
}
AVAILABILITY = {
    "available": "a copy of the source is reachable now",
    "archived_only": "source reachable only via an archive such as the Wayback Machine",
    "released_not_located": "credible report that source was released, but no copy found",
    "not_located": "no copy found; never by itself evidence of closed source",
    "not_checked": "not yet researched",
}
CONFIDENCE = {
    "high": "primary statement by the author/publisher or an inspected license",
    "medium": "consistent secondary evidence (wiki category, RWBC flag, unverified license file)",
    "low": "absence of evidence, unverified search summary, or unresolved identity",
}
RULES = [
    "Licensing and availability are independent.",
    "Freeware binaries without an explicit closed-source statement stay licensing=unknown.",
    "Source of a precursor, successor, or derivative is not attributed to another family.",
    "Third-party mirrors count as available but licensing comes only from the rights holder; originals are preferred.",
    "A wiki Commercial category is enough for proprietary, but such engines are still searched for published source.",
    "AI search summaries are leads, not evidence, unless the cited primary page confirms them.",
]
TIERS = {
    "A": "wiki open-source or license category",
    "B": "RWBC Src=yes",
    "C": "wiki Commercial or Dedicated category",
    "L": "only source link is a Lucas Chess bundle; search for the original",
    "E": "other wiki-linked families",
    "F": "list-only families",
    "D": "RWBC Src='-' only",
    "pilot": "51-family pilot sample",
    "review": "added or corrected during the review of ambiguous cases",
}
OPEN_CATEGORIES = re.compile(r"open source|gpl|mit|bsd|public domain|licen|apache|mpl|unlicense", re.I)
CLOSED_CATEGORIES = re.compile(r"^(commercial|dedicated)", re.I)
KEYWORDS = re.compile(
    r"open[- ]source|closed[- ]source|source code|sources? (?:is|are|was|were|has|have)|"
    r"\bGPL|\bMIT\b|BSD|licen[cs]e|commercial|proprietary|freeware|shareware|"
    r"public domain|github|gitlab|codeberg|sourcehut|sr\.ht|bitbucket|sourceforge|"
    r"\bsold\b|marketed|for sale|private",
    re.I,
)


def load_status():
    if STATUS_PATH.exists():
        return json.loads(STATUS_PATH.read_text(encoding="utf-8"))
    return {
        "definitions": {
            "licensing": LICENSING, "availability": AVAILABILITY,
            "confidence": CONFIDENCE, "rules": RULES, "tiers": TIERS,
        },
        "families": {},
    }


def save_status(status):
    status["families"] = dict(sorted(status["families"].items(), key=lambda kv: kv[0].casefold()))
    temporary = STATUS_PATH.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(status, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="")
    temporary.replace(STATUS_PATH)


def validate(name, record):
    problems = []
    for field, allowed in (("licensing", LICENSING), ("availability", AVAILABILITY), ("confidence", CONFIDENCE)):
        if record.get(field) not in allowed:
            problems.append(f"{field}={record.get(field)!r}")
    if not record.get("evidence"):
        problems.append("no evidence")
    for item in record.get("evidence", []):
        if "url" in item:
            if not str(item["url"]).startswith(("http://", "https://")):
                problems.append(f"evidence url {item.get('url')!r}")
        elif not any(key in item for key in ("search", "source", "user_input")):
            problems.append(f"evidence item without url/search/source: {item!r}")
    if record.get("availability") in {"available", "archived_only"} and not record.get("source_urls"):
        problems.append("available without source_urls")
    for item in record.get("source_urls", []):
        if not str(item.get("url", "")).startswith(("http://", "https://")):
            problems.append(f"source url {item.get('url')!r}")
    if not record.get("rationale"):
        problems.append("no rationale")
    return [f"{name}: {problem}" for problem in problems]


def wiki_details(fetch, url):
    html = fetch(url)
    categories = []
    match = re.search(r"Categories:(.*?)</div>", html, re.S)
    if match:
        categories = [unescape(c) for c in re.findall(r'href="/Category:[^"]+">([^<]+)<', match.group(1))]
    start = html.find("<article")
    article = html[start:html.find("</article>", start)] if start >= 0 else html
    links = []
    for href in re.findall(r'href="(https?://[^"]+)"', article):
        href = unescape(href)
        if "chessprogramming.org" not in href and href not in links:
            links.append(href)
    text = re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", " ", article)))
    snippets = []
    for found in KEYWORDS.finditer(text):
        snippet = text[max(0, found.start() - 140): found.end() + 140]
        if not any(snippet[100:180] in s for s in snippets):
            snippets.append(snippet)
    return categories, links[:15], snippets[:6], text[:600]


def build_dossiers():
    sys.path.insert(0, str(ROOT))
    from collectors.http import Fetcher

    fetch = Fetcher(ROOT / ".cache" / "http", offline=True)
    engines = json.loads((ROOT / "data" / "engines.json").read_text(encoding="utf-8"))["engines"]
    status = load_status()
    authors_path = ROOT / ".cache" / "ccrl-authors.json"
    ccrl_authors = json.loads(authors_path.read_text(encoding="utf-8")) if authors_path.exists() else {}
    dossiers = []
    for engine in engines:
        lucas_only = engine["source_code"] and all(c["source"] == "lucas-chess" for c in engine["source_code"])
        if engine["source_code"] and not lucas_only:
            continue
        if engine["name"] in status["families"]:
            continue
        rwbc = [
            {"name": p["row"][1], "author": p["row"][2], "src": p["row"][11], "dist": p["row"][18],
             "alias": p["row"][16], "previous": p["row"][17], "info": p["row"][24][:300], "web": p["row"][25]}
            for p in engine["provenance"] if p["source"] == "rwbc" and p.get("row")
        ]
        cco = [
            {"name": p["label"], "author": p.get("author", ""), "section": p.get("section", ""),
             "comment": p.get("comment", ""), "links": p.get("links", [])}
            for p in engine["provenance"] if p["source"] == "computer-chess-org"
        ]
        labels = sorted({p["label"] for p in engine["provenance"]})
        ccrl = sorted({
            author for p in engine["provenance"] if p["source"] == "ccrl"
            for key, author in ccrl_authors.items() if key == p["label"] or key.startswith(p["label"] + " ")
        })
        wiki_url = (engine.get("chessprogramming_wiki") or {}).get("url")
        categories, links, snippets, intro = [], [], [], ""
        if wiki_url:
            try:
                categories, links, snippets, intro = wiki_details(fetch, wiki_url)
            except FileNotFoundError:
                pass
        flags = {r["src"].strip() for r in rwbc}
        if lucas_only:
            tier = "L"
        elif any(OPEN_CATEGORIES.search(c) for c in categories):
            tier = "A"
        elif "yes" in {f.casefold() for f in flags} or any(
            p["section"] == "Source Code Only List" or re.search(r"(?<!no )\bsource\b", p["comment"], re.I)
            for p in cco
        ):
            tier = "B"
        elif any(CLOSED_CATEGORIES.search(c) for c in categories):
            tier = "C"
        elif flags and flags <= {"-"}:
            tier = "D"
        elif wiki_url:
            tier = "E"
        else:
            tier = "F"
        dossiers.append({
            "name": engine["name"], "tier": tier, "aliases": engine["aliases"],
            "sources": sorted({p["source"] for p in engine["provenance"]}),
            "labels": labels[:8], "ccrl_authors": ccrl, "rwbc": rwbc, "computer_chess_org": cco,
            "project_urls": sorted({p["project_url"] for p in engine["provenance"] if p.get("project_url")}),
            "lucas_source_urls": [c["url"] for c in engine["source_code"]] if lucas_only else [],
            "wiki_url": wiki_url, "wiki_categories": categories, "wiki_intro": intro,
            "wiki_external_links": links, "wiki_snippets": snippets,
        })
    RESEARCH_DIR.mkdir(parents=True, exist_ok=True)
    path = RESEARCH_DIR / "dossiers.json"
    path.write_text(json.dumps(dossiers, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(dossiers)} dossiers:", dict(sorted(Counter(d["tier"] for d in dossiers).items())))


def attach(catalog, status):
    """Add compact research status and researched source links to catalog engines."""
    families = status.get("families", {})
    for engine in catalog["engines"]:
        record = families.get(engine["name"])
        if not record:
            continue
        engine["source_status"] = {
            key: record[key] for key in (
                "tier", "availability", "licensing", "confidence", "needs_review", "checked_at",
            ) if key in record
        }
        known = {code["url"].rstrip("/").casefold() for code in engine["source_code"]}
        evidence_url = next((e["url"] for e in record.get("evidence", []) if "url" in e), None)
        for item in record.get("source_urls", []):
            if record["availability"] not in {"available", "archived_only"}:
                break
            key = item["url"].rstrip("/").casefold()
            if key in known:
                continue
            known.add(key)
            engine["source_code"].append({
                "url": item["url"], "evidence_url": evidence_url or item["url"],
                "source": "source-status-research", "kind": item.get("kind", ""),
            })


def availability_label(engine):
    status = engine.get("source_status")
    if status:
        return status["availability"]
    return "linked" if engine["source_code"] else "not_checked"


def _slug(name):
    import unicodedata
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", ascii_name.casefold()).strip("-") or "family"


def family_slugs(engines):
    slugs, used = {}, set()
    for engine in sorted(engines, key=lambda e: e["name"].casefold()):
        base = slug = _slug(engine["name"])
        number = 2
        while slug in used:
            slug = f"{base}-{number}"
            number += 1
        used.add(slug)
        slugs[engine["name"]] = slug
    return slugs


def _md(text):
    return str(text).replace("|", "\\|").replace("\n", " ")


def render_family_pages(engines, status, directory):
    """Write one generated markdown page per family plus an index."""
    families = status.get("families", {})
    directory.mkdir(parents=True, exist_ok=True)
    slugs = family_slugs(engines)
    written = {"README.md"}
    index = [
        "# Engine families", "",
        "Generated by `collect.py` from `data/engines.json` and `data/source-status.json`; do not edit.",
        "", "| Family | Source availability | Licensing |", "|---|---|---|",
    ]
    for engine in sorted(engines, key=lambda e: e["name"].casefold()):
        record = families.get(engine["name"], {})
        slug = slugs[engine["name"]]
        lines = [f"# {engine['name']}", ""]
        if engine["aliases"]:
            lines += [f"- **Aliases:** {', '.join(engine['aliases'])}"]
        wiki = engine.get("chessprogramming_wiki", {})
        if wiki.get("url"):
            lines += [f"- **Chess Programming Wiki:** <{wiki['url']}>"]
        lines += [
            f"- **Source availability:** {availability_label(engine)}",
            f"- **Licensing:** {record.get('licensing', 'not researched')}",
        ]
        if record:
            lines += [f"- **Confidence:** {record['confidence']}"]
            if record.get("tier"):
                lines += [f"- **Research tier:** {record['tier']}"]
            if record.get("checked_at"):
                lines += [f"- **Researched:** {record['checked_at']}"]
        lines += ["", "## Source code", ""]
        if engine["source_code"]:
            for code in sorted(engine["source_code"], key=lambda c: c["url"]):
                kind = f" ({code['kind']})" if code.get("kind") else ""
                lines.append(f"- <{code['url']}>{kind} â€” evidence: <{code['evidence_url']}> [{code.get('source', '')}]")
        else:
            lines.append("None found.")
        if record:
            lines += ["", "## Research notes", "", record.get("rationale", "")]
            for key, label in (("release_scope", "Release scope"), ("identity_issue", "Identity issue"), ("notes", "Notes")):
                if record.get(key):
                    lines += ["", f"**{label}:** {record[key]}"]
            if record.get("needs_review"):
                lines += ["", "**Needs review.**"]
            licensed = [s for s in record.get("source_urls", []) if s.get("license")]
            if licensed:
                lines += ["", "### Licenses", ""]
                lines += [f"- <{s['url']}>: {s['license']}" for s in licensed]
            lines += ["", "### Evidence", ""]
            for item in record.get("evidence", []):
                where = item.get("url") and f"<{item['url']}>" or item.get("search") and f"search `{item['search']}`" \
                    or item.get("source") or "repository owner"
                lines.append(f"- {where}: {_md(item.get('quote', item.get('user_input', '')))}")
        lines += ["", "## Listed by", ""]
        for source in sorted({p["source"] for p in engine["provenance"]}):
            observed = [p for p in engine["provenance"] if p["source"] == source]
            labels = sorted({p["label"] for p in observed})
            urls = sorted({p["url"] for p in observed})
            more = f" (+{len(labels) - 5} more)" if len(labels) > 5 else ""
            lines.append(f"- **{source}**: {', '.join(_md(l) for l in labels[:5])}{more} â€” <{urls[0]}>")
        (directory / f"{slug}.md").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="")
        written.add(f"{slug}.md")
        index.append(
            f"| [{_md(engine['name'])}]({slug}.md) | {availability_label(engine)} | {record.get('licensing', '')} |"
        )
    (directory / "README.md").write_text("\n".join(index) + "\n", encoding="utf-8", newline="")
    for stale in directory.glob("*.md"):
        if stale.name not in written:
            stale.unlink()


def check(paths):
    names = {e["name"] for e in json.loads((ROOT / "data" / "engines.json").read_text(encoding="utf-8"))["engines"]}
    problems = []
    for path in paths:
        for name, item in json.loads(Path(path).read_text(encoding="utf-8")).items():
            if name not in names:
                problems.append(f"{name}: not a catalog family")
            problems.extend(validate(name, item))
    print("\n".join(problems) if problems else "OK")
    if problems:
        raise SystemExit(1)


def record(paths):
    status = load_status()
    names = {e["name"] for e in json.loads((ROOT / "data" / "engines.json").read_text(encoding="utf-8"))["engines"]}
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    batch, problems = {}, []
    for path in paths:
        for name, item in json.loads(Path(path).read_text(encoding="utf-8")).items():
            if name not in names:
                problems.append(f"{name}: not a catalog family")
            problems.extend(validate(name, item))
            item.setdefault("checked_at", now)
            batch[name] = item
    if problems:
        print("\n".join(problems))
        raise SystemExit(1)
    status["families"].update(batch)
    save_status(status)
    print(f"recorded {len(batch)}; total {len(status['families'])}")


def summary():
    families = load_status()["families"]
    print("records:", len(families))
    for field in ("tier", "availability", "licensing", "confidence"):
        print(field, dict(Counter(r.get(field) for r in families.values()).most_common()))
    print("needs_review:", sum(bool(r.get("needs_review")) for r in families.values()))


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("dossiers")
    rec = sub.add_parser("record")
    rec.add_argument("paths", nargs="+")
    chk = sub.add_parser("check")
    chk.add_argument("paths", nargs="+")
    sub.add_parser("summary")
    args = parser.parse_args()
    if args.command == "dossiers":
        build_dossiers()
    elif args.command == "record":
        record(args.paths)
    elif args.command == "check":
        check(args.paths)
    else:
        summary()


if __name__ == "__main__":
    main()
