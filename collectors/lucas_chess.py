"""Read bundled Linux engines without executing Lucas Chess's Python code."""

import ast
import json
import re
from urllib.parse import quote, urlsplit


REVISION = "4bd66bb9cb1d55bd66156f8de8e128e52f66ba79"
REPOSITORY = "lukasmonk/lucaschessR6"
PREFIX = "bin/OS/linux/Engines/"
BASE_URL = f"https://github.com/{REPOSITORY}"
SOURCE_URL = f"{BASE_URL}/tree/{REVISION}/{PREFIX.rstrip('/')}"
TREE_URL = f"https://api.github.com/repos/{REPOSITORY}/git/trees/{REVISION}?recursive=1"
CONFIG_PATH = "bin/OS/linux/OSEngines.py"
RAW_URL = f"https://raw.githubusercontent.com/{REPOSITORY}/{REVISION}/"
CONFIG_URL = f"{BASE_URL}/blob/{REVISION}/{CONFIG_PATH}"

# These directory names denote versions, model collections, or legacy keys,
# rather than independently named engines.
FAMILY_NAMES = {
    "greko98": "GreKo",
    "rodentii": "Rodent",
    "komodo": "Dragon",
    "lc0": "Lc0",
    "maia": "Maia",
    "gambitfruit": "Gambit Fruit",
    "ct800": "CT800",
    "texel": "Texel",
    "alouette": "Alouette",
    "eguzki": "Eguzki",
    "eguzkilore": "Eguzkilore",
    "irina": "Irina",
    "stockfish": "Stockfish",
    "patricia": "Patricia",
    "arhanpassant": "Arhanpassant",
    "octochess": "Octochess",
    "toga": "Toga",
}


def constant(node):
    return node.value if isinstance(node, ast.Constant) else None


def repository_url(url):
    parsed = urlsplit(url)
    parts = parsed.path.strip("/").split("/")
    if parsed.scheme not in ("http", "https"):
        return False
    return (
        parsed.netloc in ("github.com", "gitlab.com", "codeberg.org", "bitbucket.org")
        and len(parts) == 2 and all(parts)
    )


def definitions(text):
    result = {}
    for node in ast.walk(ast.parse(text)):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
            continue
        if node.func.id != "mas":
            continue
        if len(node.args) < 5:
            raise ValueError("Lucas Chess engine definition has too few arguments")
        key = constant(node.args[0])
        folder = next((constant(k.value) for k in node.keywords if k.arg == "folder"), key)
        if not isinstance(folder, str) or not folder:
            raise ValueError("Lucas Chess engine definition has no static directory")
        executable = constant(node.args[4])
        family = FAMILY_NAMES.get(folder)
        if family is None:
            if not isinstance(executable, str):
                raise ValueError(f"No static engine name for {folder}")
            family = re.split(r"[-_]v?\d", executable, maxsplit=1, flags=re.I)[0]
        result[folder] = {
            "family": family, "label": key if isinstance(key, str) else folder,
            "homepage": constant(node.args[3]),
        }
    if not result:
        raise ValueError("Lucas Chess configuration contained no engine definitions")
    return result


def collect(fetch):
    tree = json.loads(fetch(TREE_URL))
    if tree.get("truncated") or not isinstance(tree.get("tree"), list):
        raise ValueError("Lucas Chess repository tree is missing or truncated")
    directories = {
        entry["path"][len(PREFIX):]
        for entry in tree["tree"]
        if entry["type"] == "tree" and entry["path"].startswith(PREFIX)
        and "/" not in entry["path"][len(PREFIX):]
    }
    if not directories:
        raise ValueError("Lucas Chess repository contains no engine directories")
    configured = definitions(fetch(RAW_URL + CONFIG_PATH))
    if directories != set(configured):
        raise ValueError(
            f"Lucas Chess directory/config mismatch: "
            f"unconfigured={sorted(directories - set(configured))}, "
            f"missing={sorted(set(configured) - directories)}"
        )
    rows = []
    for folder in sorted(directories):
        engine = configured[folder]
        path = PREFIX + folder
        url = f"{BASE_URL}/tree/{REVISION}/{quote(path)}"
        code = []
        if engine["homepage"] and repository_url(engine["homepage"]):
            code.append({"url": engine["homepage"].rstrip("/"), "evidence_url": CONFIG_URL})
        files = [
            entry["path"] for entry in tree["tree"]
            if entry["type"] == "blob" and entry["path"].startswith(path + "/")
            and "/" not in entry["path"][len(path) + 1:]
        ]
        for filename in sorted(files):
            basename = filename.rsplit("/", 1)[1].strip()
            if re.fullmatch(
                r"(?:(?:src|source)\.(?:7z|zip|tar\.gz)|LeelaChessZero-lc0-.+\.tar\.gz)",
                basename, re.I,
            ):
                code.append({
                    "url": f"{BASE_URL}/blob/{REVISION}/{quote(filename)}",
                    "evidence_url": url,
                })
            elif basename.casefold() in ("source.url", "src.url"):
                for link in re.findall(r"https?://[^\s<>\"']+", fetch(RAW_URL + quote(filename))):
                    code.append({
                        "url": link.rstrip("/"),
                        "evidence_url": f"{BASE_URL}/blob/{REVISION}/{quote(filename)}",
                    })
        rows.append({
            "family": engine["family"], "label": engine["label"], "url": url,
            "listing_url": SOURCE_URL, "configuration_url": CONFIG_URL,
            "revision": REVISION, "directory": folder, "code_urls": code,
        })
    timestamps = [
        getattr(fetch, "checked_at", {}).get(url)
        for url in (TREE_URL, RAW_URL + CONFIG_PATH)
    ]
    checked_at = max((timestamp for timestamp in timestamps if timestamp), default=None)
    if checked_at:
        for row in rows:
            row["checked_at"] = checked_at
    return rows
