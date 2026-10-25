"""Download chess engine source code, with full git history where available.

Standalone: needs only Python 3.10+, git, and engine-sources.txt beside this script
(optionally 7z for .7z/.rar archives).

    python fetch_sources.py --list                # names that can be requested
    python fetch_sources.py Bread "Fairy-Max"     # one or more families (name or alias)
    python fetch_sources.py --all                 # every family in the list
    python fetch_sources.py --all --update        # also fetch new commits for existing clones
    python fetch_sources.py --export              # regenerate engine-sources.txt (catalog repo only)

Git repositories (GitHub, GitLab, Codeberg, Bitbucket, sourcehut, SourceForge git, other *.git)
are fully cloned into <dest>/src; existing shallow clones are unshallowed. Software Heritage
links are fetched as git bundles through the SWH vault. Direct archive or source-file links are
downloaded into <dest>/src-archives and unpacked into <dest>/src. Internet Archive links are never
fetched: the script prints the URL so you can download it yourself. Everything else is reported.
"""
import argparse
import difflib
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import threading
import time
import urllib.parse
import urllib.request
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE_LIST = HERE / "engine-sources.txt"
SRC = ARCHIVES = LOG = None  # set by set_dest()
USER_AGENT = "chess-engine-catalog source fetcher (+https://github.com/ogennadi/chess-engine-catalog)"
SWH_API = "https://archive.softwareheritage.org/api/1"

GIT_HOSTS = {"github.com", "gitlab.com", "codeberg.org", "bitbucket.org", "git.sr.ht", "notabug.org", "gitea.com"}
MANUAL_HOSTS = {"drive.google.com", "mega.nz", "www.mediafire.com", "mediafire.com", "code.google.com"}
ARCHIVE_EXT = re.compile(r"\.(zip|7z|rar|tar|tgz|tar\.gz|tar\.bz2|tbz2?|tar\.xz|txz|lzh|arj)$", re.I)
CODE_EXT = re.compile(r"\.(c|cc|cpp|cxx|h|hpp|java|py|pas|bas|asm|s|js|rs|go|cs|f|for|lisp|scm|pl|txt|pdf)$", re.I)
# Seconds between requests to the same host.
HOST_DELAY = {"archive.softwareheritage.org": 7.0}
DEFAULT_DELAY = 2.0
GIT_TIMEOUT = 3600

GIT_ENV = {**os.environ, "GIT_TERMINAL_PROMPT": "0", "GCM_INTERACTIVE": "never"}
GIT = ["git", "-c", "credential.helper=", "-c", "core.longpaths=true"]


def set_dest(dest):
    global SRC, ARCHIVES, LOG
    dest = Path(dest).resolve()
    SRC, ARCHIVES, LOG = dest / "src", dest / "src-archives", dest / "research" / "fetch-sources" / "last-run.json"


set_dest(HERE / ".cache")


def dir_name(text):
    return re.sub(r"[^A-Za-z0-9._-]+", "_", text).strip("_") or "family"


def is_internet_archive(host):
    return host == "archive.org" or host.endswith(".archive.org")


def classify(url):
    """Return a target dict for a source URL: kind is git, sf, swh, file or skip."""
    parts = urllib.parse.urlsplit(url.strip())
    host = (parts.hostname or "").lower()
    path = [p for p in parts.path.split("/") if p]

    if host in {"web.archive.org", "wayback.archive.org"}:
        match = re.match(r"^/web/(\d+)[a-z_]*/(.+)$", parts.path)
        original = (match.group(2) + (f"?{parts.query}" if parts.query else "")) if match else ""
        if match and (ARCHIVE_EXT.search(original.split("?")[0]) or CODE_EXT.search(original.split("?")[0])):
            manual = f"https://web.archive.org/web/{match.group(1)}id_/{original}"
            return {"kind": "skip", "url": url, "manual": manual,
                    "reason": f"Internet Archive is not fetched automatically; download manually: {manual}"}
        return {"kind": "skip", "url": url, "manual": url, "reason": "Internet Archive web page; browse manually"}

    if is_internet_archive(host):
        return {"kind": "skip", "url": url, "manual": url,
                "reason": f"Internet Archive is not fetched automatically; download manually: {url}"}

    if host == "archive.softwareheritage.org":
        origin = urllib.parse.parse_qs(parts.query).get("origin_url", [None])[0]
        if origin:
            return {"kind": "swh", "url": url, "origin": origin, "key": "swh:" + origin.rstrip("/").casefold()}
        return {"kind": "skip", "url": url, "reason": "Software Heritage link without origin_url"}

    if host in {"github.com", "www.github.com"}:
        if len(path) < 2:
            return {"kind": "skip", "url": url, "reason": "GitHub user page, not a repository"}
        owner, repo = path[0], re.sub(r"\.git$", "", path[1])
        rest = path[2:]
        if len(rest) >= 3 and rest[0] in {"blob", "raw"} and ARCHIVE_EXT.search(rest[-1]):
            return {"kind": "file", "url": url, "filename": rest[-1],
                    "fetch": f"https://raw.githubusercontent.com/{owner}/{repo}/{'/'.join(rest[1:])}"}
        if len(rest) >= 4 and rest[0] == "releases" and rest[1] == "download":
            return {"kind": "file", "url": url, "filename": rest[-1], "fetch": url}
        return _git(url, f"https://github.com/{owner}/{repo}.git", f"{owner}-{repo}")

    if host in {"gitlab.com", "salsa.debian.org", "framagit.org"}:
        project = parts.path.split("/-/")[0].strip("/")
        project = re.sub(r"\.git$", "", project)
        if project.count("/") < 1:
            return {"kind": "skip", "url": url, "reason": "GitLab user page, not a repository"}
        return _git(url, f"https://{host}/{project}.git", project.replace("/", "-"))

    if host == "repo.or.cz" and path and path[-1].endswith(".git"):
        return _git(url, f"https://repo.or.cz/{path[-1]}", path[-1][:-4])

    if host in GIT_HOSTS:
        if len(path) < 2:
            return {"kind": "skip", "url": url, "reason": "user page, not a repository"}
        owner, repo = path[0], re.sub(r"\.git$", "", path[1])
        return _git(url, f"https://{host}/{owner}/{repo}", f"{owner.lstrip('~')}-{repo}")

    if host.endswith("sourceforge.net"):
        project = None
        if host in {"sourceforge.net", "www.sourceforge.net"} and len(path) >= 2 and path[0] in {"projects", "p"}:
            project = path[1]
        elif host.endswith(".sourceforge.net") and host not in {"downloads.sourceforge.net", "git.code.sf.net"}:
            project = host.split(".")[0]
        if project:
            mount = path[2] if len(path) >= 3 and path[0] == "p" else None
            return {"kind": "sf", "url": url, "project": project, "mount": mount, "key": "sf:" + project.casefold()}

    if host in MANUAL_HOSTS:
        return {"kind": "skip", "url": url, "reason": f"{host} needs a manual download or is defunct"}
    if host.startswith("svn.") or "/svn/" in parts.path:
        return {"kind": "skip", "url": url, "reason": "Subversion repository; needs svn or git-svn"}
    if parts.path.endswith(".git"):
        return _git(url, url, path[-1][:-4])
    filename = parts.path.rstrip("/").rsplit("/", 1)[-1]
    if ARCHIVE_EXT.search(filename) or CODE_EXT.search(filename):
        return {"kind": "file", "url": url, "fetch": url, "filename": filename}
    return {"kind": "skip", "url": url, "reason": "web page, not a repository or file"}


def _git(url, clone, label):
    return {"kind": "git", "url": url, "clone": clone, "label": label,
            "key": "git:" + re.sub(r"(\.git)?/?$", "", clone).casefold()}


def plan(engine):
    """Distinct fetch targets for a family, repositories first, most-cited first."""
    targets, counts = {}, {}
    for code in engine["source_code"]:
        if code.get("unreachable"):
            continue
        target = classify(code["url"])
        key = _key(target)
        counts[key] = counts.get(key, 0) + 1
        targets.setdefault(key, target)
    order = {"git": 0, "sf": 1, "swh": 2, "file": 3, "skip": 4}
    return sorted(targets.values(), key=lambda t: (order[t["kind"]], -counts[_key(t)]))


def _key(target):
    if target["kind"] == "file":
        return "file:" + target["fetch"]
    if target["kind"] == "skip":
        return "skip:" + target["url"]
    return target["key"]


class Throttle:
    def __init__(self):
        self.lock = threading.Lock()
        self.last = {}
        self.host_locks = {}

    def wait(self, url):
        host = urllib.parse.urlsplit(url).hostname or ""
        with self.lock:
            host_lock = self.host_locks.setdefault(host, threading.Lock())
        with host_lock:
            delay = HOST_DELAY.get(host, DEFAULT_DELAY) - (time.monotonic() - self.last.get(host, 0))
            if delay > 0:
                time.sleep(delay)
            self.last[host] = time.monotonic()


THROTTLE = Throttle()


class _NoInternetArchiveRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if is_internet_archive((urllib.parse.urlsplit(newurl).hostname or "").lower()):
            raise RefusedInternetArchive(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class RefusedInternetArchive(Exception):
    def __init__(self, url):
        self.url = url
        super().__init__(f"Internet Archive is not fetched automatically; download manually: {url}")


OPENER = urllib.request.build_opener(_NoInternetArchiveRedirects)


def http(url, method="GET", timeout=120):
    if is_internet_archive((urllib.parse.urlsplit(url).hostname or "").lower()):
        raise RefusedInternetArchive(url)
    THROTTLE.wait(url)
    request = urllib.request.Request(url, method=method, headers={"User-Agent": USER_AGENT})
    return OPENER.open(request, timeout=timeout)


def http_json(url, method="GET"):
    with http(url, method) as response:
        return json.load(response)


def run_git(*args, cwd=None):
    result = subprocess.run([*GIT, *args], cwd=cwd, env=GIT_ENV, capture_output=True, text=True,
                            encoding="utf-8", errors="replace", timeout=GIT_TIMEOUT)
    return result.returncode, (result.stderr or result.stdout).strip().splitlines()[-1:] or [""]


def existing_remotes():
    """Map normalised origin URL -> directory for clones already in .cache/src."""
    remotes = {}
    if not SRC.exists():
        return remotes
    for directory in SRC.iterdir():
        config = directory / ".git" / "config"
        if not config.is_file():
            continue
        match = re.search(r'\[remote "origin"\][^\[]*?url\s*=\s*(\S+)', config.read_text(encoding="utf-8", errors="replace"))
        if match:
            remotes["git:" + re.sub(r"(\.git)?/?$", "", match.group(1)).casefold()] = directory
    return remotes


def free_dir(base, suffix):
    directory = SRC / base
    if not directory.exists():
        return directory
    directory = SRC / f"{base}~{dir_name(suffix)}"
    number = 2
    while directory.exists():
        directory = SRC / f"{base}~{dir_name(suffix)}-{number}"
        number += 1
    return directory


def fetch_git(clone, directory, update):
    if (directory / ".git").exists():
        if (directory / ".git" / "shallow").exists():
            code, msg = run_git("fetch", "--quiet", "--unshallow", "--tags", cwd=directory)
            return ("unshallowed" if code == 0 else "error"), msg[0]
        if update:
            code, msg = run_git("fetch", "--quiet", "--tags", "--prune", cwd=directory)
            return ("updated" if code == 0 else "error"), msg[0]
        return "present", ""
    code, msg = run_git("clone", "--quiet", clone, str(directory))
    if code == 0:
        return "cloned", ""
    if (directory / ".git").exists():
        return "cloned", "checkout incomplete: " + msg[0]
    shutil.rmtree(directory, ignore_errors=True)
    return "error", msg[0]


def sourceforge_repos(target):
    """SourceForge git mount points; other SCMs are returned as notes."""
    try:
        tools = http_json(f"https://sourceforge.net/rest/p/{target['project']}")["tools"]
    except Exception as error:  # noqa: BLE001 - report any network/API failure
        return [], [f"SourceForge API: {error}"]
    repos, notes = [], []
    for tool in tools:
        if target["mount"] and tool["mount_point"] != target["mount"] and tool["name"] in {"git", "svn", "hg", "cvs"}:
            continue
        if tool["name"] == "git":
            repos.append(f"https://git.code.sf.net/p/{target['project']}/{tool['mount_point']}")
        elif tool["name"] in {"svn", "hg", "cvs"}:
            notes.append(f"{tool['name']} repository at /p/{target['project']}/{tool['mount_point']} not fetched")
    return repos, notes


def fetch_swh(target, directory):
    """Clone a Software Heritage origin's HEAD history via the vault's git-bare cooker."""
    origin = urllib.parse.quote(target["origin"], safe="")
    visit = http_json(f"{SWH_API}/origin/{origin}/visit/latest/?require_snapshot=true")
    branches = http_json(f"{SWH_API}/snapshot/{visit['snapshot']}/")["branches"]
    head = branches.get("HEAD") or next(iter(branches.values()))
    while head and head["target_type"] == "alias":
        head = branches.get(head["target"])
    if not head or head["target_type"] != "revision":
        return "error", "no revision in latest snapshot"
    swhid = f"swh:1:rev:{head['target']}"
    cook = f"{SWH_API}/vault/git-bare/{swhid}/"
    job = http_json(cook, "POST")
    deadline = time.monotonic() + 3600
    while job["status"] in {"new", "pending"} and time.monotonic() < deadline:
        time.sleep(30)
        job = http_json(cook)
    if job["status"] != "done":
        return "error", f"vault status {job['status']}: {job.get('progress_message') or ''}"
    with tempfile.TemporaryDirectory() as temp:
        bundle = Path(temp) / "bare.tar.gz"
        with http(job["fetch_url"], timeout=600) as response, open(bundle, "wb") as out:
            shutil.copyfileobj(response, out)
        with tarfile.open(bundle) as tar:
            members = tar.getmembers()
            for member in members:  # SWHIDs contain ':', which Windows paths cannot
                member.name = member.name.replace(":", "_")
            tar.extractall(temp, members=members, filter="data")
        bare = next(Path(temp).glob("*.git"))
        code, msg = run_git("clone", "--quiet", str(bare), str(directory))
        if code != 0:
            return "error", msg[0]
        run_git("remote", "set-url", "origin", target["origin"], cwd=directory)
    return "cloned", f"from Software Heritage {swhid}"


def unpack(archive, destination):
    destination.mkdir(parents=True, exist_ok=True)
    name = archive.name.lower()
    if name.endswith(".zip"):
        with zipfile.ZipFile(archive) as zf:
            zf.extractall(destination)
    elif re.search(r"\.(tar|tgz|tar\.gz|tar\.bz2|tbz2?|tar\.xz|txz)$", name):
        with tarfile.open(archive) as tar:
            tar.extractall(destination, filter="data")
    elif shutil.which("7z"):
        result = subprocess.run(["7z", "x", "-y", f"-o{destination}", str(archive)], capture_output=True)
        if result.returncode != 0:
            return False
    elif ARCHIVE_EXT.search(name):
        return False
    else:
        shutil.copy2(archive, destination / archive.name)
    return True


def fetch_file(target, base, update):
    archive = ARCHIVES / base / dir_name(target["filename"])
    if not archive.exists() or update:
        archive.parent.mkdir(parents=True, exist_ok=True)
        with http(target["fetch"], timeout=600) as response, open(archive, "wb") as out:
            shutil.copyfileobj(response, out)
        state = "downloaded"
    else:
        state = "present"
    stem = re.sub(ARCHIVE_EXT.pattern + "|" + CODE_EXT.pattern, "", archive.name, flags=re.I)
    destination = SRC / base / stem if ARCHIVE_EXT.search(archive.name) else SRC / base
    if not destination.exists() or not any(destination.iterdir()) or update:
        if not unpack(archive, destination):
            return state, f"saved {archive} but could not unpack it"
    return state, f"no history; unpacked into {destination}"


def fetch_family(engine, remotes, args):
    base = dir_name(engine["name"])
    results = []
    targets = plan(engine)
    repo_done = False
    had_files = (SRC / base).is_dir() and any((SRC / base).iterdir())
    for target in targets:
        if target["kind"] == "skip":
            if target.get("manual"):
                results.append({"url": target["url"], "state": "manual", "note": target["manual"]})
            else:
                results.append({"url": target["url"], "state": "skipped", "note": target["reason"]})
            continue
        if repo_done and not args.every:
            results.append({"url": target["url"], "state": "not needed", "note": "family already has a repository"})
            continue
        try:
            if args.dry_run:
                results.append({"url": target["url"], "state": "would fetch", "note": target.get("clone", target.get("fetch", ""))})
                repo_done |= target["kind"] != "file"
                continue
            if target["kind"] == "git":
                directory = remotes.get(target["key"]) or free_dir(base, target["label"])
                state, note = fetch_git(target["clone"], directory, args.update)
                results.append({"url": target["url"], "state": state, "note": note, "dir": directory.name})
                repo_done |= state != "error"
            elif target["kind"] == "sf":
                repos, notes = sourceforge_repos(target)
                for clone in repos:
                    key = "git:" + clone.casefold()
                    directory = remotes.get(key) or free_dir(base, f"sf-{target['project']}-{clone.rsplit('/', 1)[-1]}")
                    state, note = fetch_git(clone, directory, args.update)
                    results.append({"url": clone, "state": state, "note": note, "dir": directory.name})
                    repo_done |= state != "error"
                for note in notes:
                    results.append({"url": target["url"], "state": "skipped", "note": note})
                if not repos and not notes:
                    results.append({"url": target["url"], "state": "skipped", "note": "SourceForge project has no code repository"})
            elif target["kind"] == "swh":
                existing = remotes.get("git:" + re.sub(r"(\.git)?/?$", "", target["origin"]).casefold())
                if existing and (existing / ".git").exists() and not (existing / ".git" / "shallow").exists():
                    results.append({"url": target["url"], "state": "present", "note": "", "dir": existing.name})
                else:
                    directory = free_dir(base, "swh")
                    state, note = fetch_swh(target, directory)
                    results.append({"url": target["url"], "state": state, "note": note, "dir": directory.name})
                    repo_done |= state != "error"
            else:
                existing = SRC / base
                if not args.update and had_files:
                    results.append({"url": target["url"], "state": "present", "note": "", "dir": existing.name})
                    continue
                state, note = fetch_file(target, base, args.update)
                results.append({"url": target["url"], "state": state, "note": note})
        except RefusedInternetArchive as refused:
            results.append({"url": target["url"], "state": "manual", "note": refused.url})
        except Exception as error:  # noqa: BLE001 - one bad link must not stop a full run
            results.append({"url": target["url"], "state": "error", "note": f"{type(error).__name__}: {error}"})
    return {"family": engine["name"], "results": results}


def read_source_list(path=None):
    """Parse engine-sources.txt: family at column 0, '= alias' and URLs indented."""
    engines = []
    for number, line in enumerate(Path(path or SOURCE_LIST).read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip() or line.startswith("# ") or line.strip() == "#":
            continue
        if not line[0].isspace():
            engines.append({"name": line.strip(), "aliases": [], "source_code": []})
        elif not engines:
            raise ValueError(f"{path or SOURCE_LIST}:{number}: indented line before any family")
        elif line.strip().startswith("= "):
            engines[-1]["aliases"].append(line.strip()[2:].strip())
        else:
            engines[-1]["source_code"].append({"url": line.strip()})
    return engines


def export_source_list(path=None):
    """Write engine-sources.txt from the catalog repository's data (not needed when standalone)."""
    sys.path.insert(0, str(HERE))
    import source_status  # catalog repository only

    catalog = json.loads((HERE / "data" / "engines.json").read_text(encoding="utf-8"))
    source_status.attach(catalog, source_status.load_status())
    lines = [
        "# Chess engine families with source links, read by fetch_sources.py.",
        "# Family name at column 0; indented lines are '= alias' or a source URL. Comments start with '# '.",
        "# Regenerate in the catalog repository with: python fetch_sources.py --export",
    ]
    count = 0
    for engine in sorted(catalog["engines"], key=lambda e: source_status.name_sort_key(e["name"])):
        urls = list(dict.fromkeys(c["url"].strip() for c in engine["source_code"] if not c.get("unreachable")))
        if not urls:
            continue
        count += 1
        lines += ["", engine["name"], *(f"  = {a}" for a in engine.get("aliases", []) if a != engine["name"]),
                  *(f"  {u}" for u in urls)]
    Path(path or SOURCE_LIST).write_text("\n".join(lines) + "\n", encoding="utf-8")
    return count


def select(engines, names):
    lookup, loose = {}, {}
    for engine in engines:
        for name in [engine["name"], *engine.get("aliases", [])]:
            lookup.setdefault(name.casefold(), engine)
            loose.setdefault(re.sub(r"\W|_", "", name.casefold()), engine)
    chosen, missing = [], []
    for name in names:
        engine = lookup.get(name.casefold()) or loose.get(re.sub(r"\W|_", "", name.casefold()))
        if engine:
            chosen.append(engine)
        else:
            close = difflib.get_close_matches(name.casefold(), lookup, n=5, cutoff=0.6)
            missing.append(f"{name!r} not found" + (f"; did you mean {', '.join(lookup[c]['name'] for c in close)}?" if close else ""))
    return chosen, missing


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("families", nargs="*", help="family names or aliases (see --list)")
    parser.add_argument("--all", action="store_true", help="every family in the source list")
    parser.add_argument("--list", action="store_true", help="print the family names that can be requested")
    parser.add_argument("--export", action="store_true", help="regenerate engine-sources.txt from the catalog repo")
    parser.add_argument("--sources", type=Path, default=SOURCE_LIST, help=f"source list (default {SOURCE_LIST.name})")
    parser.add_argument("--dest", type=Path, default=HERE / ".cache",
                        help="output root; clones go to DEST/src (default .cache beside this script)")
    parser.add_argument("--update", action="store_true", help="fetch new commits / re-download existing files")
    parser.add_argument("--every", action="store_true", help="fetch every distinct link, not just the main repository")
    parser.add_argument("--jobs", type=int, default=4, help="families fetched in parallel (default 4)")
    parser.add_argument("--dry-run", action="store_true", help="show what would be fetched")
    args = parser.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if args.export:
        print(f"Wrote {export_source_list(args.sources)} families to {args.sources}")
        return 0
    engines = read_source_list(args.sources)
    if args.list:
        for engine in engines:
            print(engine["name"] + (f"  (= {', '.join(engine['aliases'])})" if engine["aliases"] else ""))
        return 0
    if not args.all and not args.families:
        parser.error("name one or more families, or use --all or --list")
    set_dest(args.dest)

    if args.all:
        chosen = engines
    else:
        chosen, missing = select(engines, args.families)
        for message in missing:
            print(message, file=sys.stderr)
        if not chosen:
            return 1
    SRC.mkdir(parents=True, exist_ok=True)
    remotes = existing_remotes()
    print(f"{len(chosen)} families; {len(remotes)} existing clones in {SRC}", flush=True)

    report, started = [], time.monotonic()
    with ThreadPoolExecutor(max_workers=max(1, args.jobs)) as pool:
        for index, outcome in enumerate(pool.map(lambda e: fetch_family(e, remotes, args), chosen), 1):
            report.append(outcome)
            for item in outcome["results"]:
                if item["state"] in {"not needed"}:
                    continue
                where = f" -> {item['dir']}" if item.get("dir") else ""
                note = f" ({item['note']})" if item.get("note") else ""
                print(f"[{index}/{len(chosen)}] {outcome['family']}: {item['state']}{where}{note}  {item['url']}", flush=True)

    counts = {}
    for outcome in report:
        for item in outcome["results"]:
            counts[item["state"]] = counts.get(item["state"], 0) + 1
    print(f"Done in {time.monotonic() - started:.0f}s: " + ", ".join(f"{k} {v}" for k, v in sorted(counts.items())))
    manual = [(o["family"], i["note"]) for o in report for i in o["results"] if i["state"] == "manual"]
    if manual:
        print("\nInternet Archive links to download manually:")
        for family, url in manual:
            print(f"  {family}: {url}")
    if not args.dry_run:
        LOG.parent.mkdir(parents=True, exist_ok=True)
        LOG.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"Log: {LOG}")
    return 1 if counts.get("error") else 0


if __name__ == "__main__":
    sys.exit(main())
