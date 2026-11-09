"""Extract engine features from cached README files using features/taxonomy.json.

Usage: python features/extract_readme_features.py
Reads .cache/src/<Engine>/README*, writes features/readme-features.json (per engine)
and features/summary.json (per feature counts, strength-limited vs all, examples).
"""
import csv
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / ".cache" / "src"
HERE = ROOT / "features"
CPW = "https://www.chessprogramming.org/"

NEGATION = re.compile(
    r"\b(no|not|without|lacks?|missing|todo|planned|future|wip|instead of|rather than|"
    r"isn'?t|doesn'?t|don'?t|won'?t|never)\b|\[ \]", re.I)
NEG_HEADING = re.compile(
    r"todo|to-do|planned|roadmap|future|ideas|wish|not (yet )?implemented|omitted|left out|"
    r"missing|limitations|known issues|upcoming|next steps|not supported", re.I)
VENDORED = {"lib", "libs", "external", "extern", "3rdparty", "third_party", "thirdparty",
            "deps", "vendor", "node_modules", ".git", ".svn", "test", "tests", "docs"}


def norm(text):
    return re.sub(r"[^a-z0-9]", "", text.lower())


def dir_name(text):
    return re.sub(r"[^A-Za-z0-9._-]+", "_", text).strip("_") or "family"


def load_families():
    """Map cache dir -> (family name, first source URL) from engine-sources.txt."""
    fams, current = {}, None
    for line in (ROOT / "engine-sources.txt").read_text(encoding="utf8").splitlines():
        if not line.strip() or line.startswith("# "):
            continue
        if not line[0].isspace():
            current = line.strip()
            fams[dir_name(current)] = [current, None]
        elif current and line.strip().startswith("http") and fams[dir_name(current)][1] is None:
            fams[dir_name(current)][1] = line.strip()
    return fams


def load_cpw_urls():
    urls = {}
    with open(ROOT / "data" / "engines.csv", encoding="utf-8-sig") as fh:
        for row in csv.DictReader(fh):
            if row.get("chessprogramming_wiki_url"):
                urls[norm(row["name"])] = row["chessprogramming_wiki_url"]
    return urls


def strength_limited():
    with open(ROOT / "strength-limited" / "strength-limited-engines.csv", encoding="utf-8-sig") as fh:
        return {norm(r["Engine"]): r["Engine"] for r in csv.DictReader(fh)}


def options_text():
    """Reviewed UCI/XBoard option notes, keyed by normalised engine name (strength features only)."""
    texts = {}
    with open(ROOT / "strength-limited" / "strength-limited-engines.csv", encoding="utf-8-sig") as fh:
        for r in csv.DictReader(fh):
            texts[norm(r["Engine"])] = r["Options"]
    path = ROOT / "data" / "engine-options.csv"
    if path.exists():
        with open(path, encoding="utf-8-sig") as fh:
            for r in csv.DictReader(fh):
                if r.get("strength_limiting", "none").strip().lower() not in ("", "none"):
                    key = norm(r["family"])
                    texts[key] = (texts.get(key, "") + "\n" + r["strength_limiting"]).strip()
    return texts


def readmes(engine_dir):
    files = [p for p in engine_dir.iterdir() if p.is_file() and p.name.lower().startswith("readme")]
    if not files:
        for sub in engine_dir.iterdir():
            if sub.is_dir() and sub.name.lower() not in VENDORED:
                files += [p for p in sub.iterdir() if p.is_file() and p.name.lower().startswith("readme")]
    return sorted(files)


def clean(line):
    line = re.sub(r"\]\([^)]*\)", "]", line)
    return re.sub(r"https?://\S+", "", line)


def compile_taxonomy(tax):
    out = []
    for f in tax["features"]:
        pats = [re.compile(p, re.I) for p in f.get("match", [])]
        if pats:
            out.append((f, pats))
    return out


def scan(text, compiled):
    found = {}
    heading_neg = para_neg = False
    for raw in text.splitlines():
        line = clean(raw)
        stripped = line.strip()
        if not stripped:
            para_neg = False
            continue
        if re.match(r"#{1,6}\s|.+\n?[=-]{3,}$", stripped) or re.match(r"^\*\*[^*]+\*\*:?$", stripped):
            heading_neg = bool(NEG_HEADING.search(stripped))
            continue
        if re.match(r"(\*\*)?[^.]{0,40}(omitted|not implemented|left out|missing)", stripped, re.I):
            para_neg = True
        for f, pats in compiled:
            for pat in pats:
                m = pat.search(line)
                if not m:
                    continue
                before = line[max(0, m.start() - 40):m.start()]
                negated = heading_neg or para_neg or bool(NEGATION.search(before))
                status = "negated" if negated else "yes"
                prev = found.get(f["id"])
                if prev is None or (prev["status"] == "negated" and status == "yes"):
                    found[f["id"]] = {"status": status, "evidence": stripped[:160]}
                break
    for f, _ in compiled:
        for ex in f.get("excludeIf", []):
            if f["id"] in found and found.get(ex, {}).get("status") == "yes":
                del found[f["id"]]
    return found


def main():
    tax = json.loads((HERE / "taxonomy.json").read_text(encoding="utf8"))
    compiled = compile_taxonomy(tax)
    area_of = {f["id"]: f.get("area") or next(g["area"] for g in tax["groups"] if g["id"] == f["group"])
               for f in tax["features"]}
    strength_compiled = [(f, p) for f, p in compiled if area_of[f["id"]] == "strength"]
    fams, cpw_urls, sl, opts = load_families(), load_cpw_urls(), strength_limited(), options_text()

    engines = {}
    for d in sorted(SRC.iterdir(), key=lambda p: p.name.lower()):
        if not d.is_dir():
            continue
        files = readmes(d)
        name, src_url = fams.get(d.name, [d.name.replace("_", " ").strip(), None])
        sl_name = sl.get(norm(name)) or sl.get(norm(d.name))
        is_sl = sl_name is not None
        name = sl_name or name
        opt = opts.get(norm(name)) or opts.get(norm(d.name))
        if not files and not opt:
            continue
        text = "\n".join(p.read_text(encoding="utf8", errors="replace") for p in files)
        found = scan(text, compiled)
        for v in found.values():
            v["source"] = "readme"
        if opt:
            for fid, v in scan(opt, strength_compiled).items():
                if found.get(fid, {}).get("status") != "yes" and v["status"] == "yes":
                    found[fid] = {**v, "source": "options"}
        engines[name] = {
            "dir": d.name,
            "strength_limited": is_sl,
            "readme_chars": len(text),
            "readmes": [str(p.relative_to(SRC)).replace("\\", "/") for p in files],
            "url": cpw_urls.get(norm(name)) or src_url,
            "features": found,
        }

    (HERE / "readme-features.json").write_text(
        json.dumps(engines, indent=1, ensure_ascii=False), encoding="utf8")

    n_all = len(engines)
    n_sl = sum(e["strength_limited"] for e in engines.values())
    summary = {"engines_scanned": n_all, "strength_limited_scanned": n_sl,
               "missing_strength_limited": sorted(set(sl.values()) - {
                   n for n, e in engines.items() if e["strength_limited"]}),
               "features": {}}
    for f in tax["features"]:
        yes = [n for n, e in engines.items() if e["features"].get(f["id"], {}).get("status") == "yes"]
        neg = [n for n, e in engines.items() if e["features"].get(f["id"], {}).get("status") == "negated"]
        sl_yes = [n for n in yes if engines[n]["strength_limited"]]
        others = sorted((n for n in yes if not engines[n]["strength_limited"]),
                        key=lambda n: (engines[n]["url"] is None or "chessprogramming" not in engines[n]["url"],
                                       -engines[n]["readme_chars"]))
        examples = (sorted(sl_yes) + others)[:4]
        summary["features"][f["id"]] = {
            "label": f["label"],
            "area": f.get("area") or next(g["area"] for g in tax["groups"] if g["id"] == f["group"]),
            "cpw": CPW + f["cpw"].replace(" ", "_") if f.get("cpw") else None,
            "ref": f.get("ref"),
            "engines": len(yes),
            "engines_pct": round(100 * len(yes) / n_all, 1),
            "strength_limited": len(sl_yes),
            "strength_limited_pct": round(100 * len(sl_yes) / n_sl, 1) if n_sl else 0,
            "negated_or_planned": len(neg),
            "examples": [{"engine": n, "strength_limited": engines[n]["strength_limited"],
                          "url": engines[n]["url"], "source": engines[n]["features"][f["id"]]["source"],
                          "evidence": engines[n]["features"][f["id"]]["evidence"]}
                         for n in examples],
        }
    summary["note"] = ("Counts = engines whose README states the feature (strength-area features also use "
                       "reviewed option notes; source='options'). Absence means 'not stated', not 'absent'.")
    (HERE / "summary.json").write_text(json.dumps(summary, indent=1, ensure_ascii=False), encoding="utf8")
    print(f"{n_all} engines with READMEs or option notes ({n_sl} strength-limited); "
          f"missing SL: {summary['missing_strength_limited']}")


if __name__ == "__main__":
    main()
