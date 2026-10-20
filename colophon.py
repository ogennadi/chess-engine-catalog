"""Write COLOPHON.md: how long building this catalog took, reconstructed from local
GitHub Copilot session logs (~/.copilot/session-state) and git history.

    python colophon.py [--sessions DIR] [--no-prompts]

Only sessions whose workspace is this repository are read. The logs exist only on the
machine that ran the sessions, so the output is gitignored rather than committed.
"""

import argparse
import json
import re
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DEFAULT_SESSIONS = Path.home() / ".copilot" / "session-state"


def _time(stamp):
    return datetime.fromisoformat(stamp.replace("Z", "+00:00")).astimezone()


def _duration(delta):
    minutes = round(delta.total_seconds() / 60)
    return f"{minutes // 60} h {minutes % 60:02d} min" if minutes >= 60 else f"{minutes} min"


def _union(intervals):
    total, end = timedelta(), None
    for start, stop in sorted(intervals):
        if end is None or start > end:
            total += stop - start
            end = stop
        elif stop > end:
            total += stop - end
            end = stop
    return total


def sessions(directory):
    for folder in sorted(directory.iterdir()):
        workspace, events = folder / "workspace.yaml", folder / "events.jsonl"
        if not (workspace.exists() and events.exists()):
            continue
        cwd = re.search(r"^cwd: (.+)$", workspace.read_text(encoding="utf-8"), re.M)
        if cwd and Path(cwd.group(1).strip()).resolve() == ROOT:
            yield folder.name, events


def summarize(name, path):
    s = {"id": name, "prompts": [], "turns": [], "agents": [], "waits": [], "premium": 0,
         "models": set(), "tool_calls": 0, "first": None, "last": None}
    open_turns, requested = {}, {}
    with path.open(encoding="utf-8") as lines:
        for line in lines:
            event = json.loads(line)
            kind, data, when = event["type"], event.get("data") or {}, event.get("timestamp")
            if not when:
                continue
            when = _time(when)
            s["first"] = s["first"] or when
            s["last"] = when
            scope = event.get("agentId")
            if kind == "user.message" and scope is None:
                s["prompts"].append((when, (data.get("content") or "").strip()))
            elif kind == "assistant.turn_start":
                open_turns[scope] = when
            elif kind == "assistant.turn_end" and scope in open_turns:
                s["turns"].append((open_turns.pop(scope), when))
            elif kind == "tool.execution_start":
                s["tool_calls"] += 1
            elif kind == "subagent.completed":
                start = when - timedelta(milliseconds=data.get("durationMs") or 0)
                s["agents"].append({**data, "start": start, "end": when})
                s["models"].add(data.get("model"))
            elif kind == "permission.requested":
                requested[data.get("requestId")] = when
            elif kind == "permission.completed" and data.get("requestId") in requested:
                s["waits"].append(when - requested.pop(data["requestId"]))
            elif kind == "session.usage_checkpoint":
                s["premium"] = max(s["premium"], data.get("totalPremiumRequests") or 0)
                s["models"].update(m.get("modelId") for m in data.get("modelCacheState") or [])
    s["models"].discard(None)
    return s


def git_log():
    out = subprocess.run(["git", "log", "--reverse", "--format=%aI%x09%s"], cwd=ROOT,
                         capture_output=True, text=True, encoding="utf-8", check=True).stdout
    return [(datetime.fromisoformat(d), msg) for d, msg in (l.split("\t", 1) for l in out.splitlines())]


def render(all_sessions, commits, prompts=True):
    first = min(s["first"] for s in all_sessions)
    last = max(s["last"] for s in all_sessions)
    working = _union([t for s in all_sessions for t in s["turns"]]
                     + [(a["start"], a["end"]) for s in all_sessions for a in s["agents"]])
    agents = [a for s in all_sessions for a in s["agents"]]
    waits = [w for s in all_sessions for w in s["waits"]]
    manual = [w for w in waits if w.total_seconds() >= 5]
    models = sorted(set().union(*(s["models"] for s in all_sessions)))
    lines = [
        "# Colophon",
        "",
        "This catalog was built interactively with GitHub Copilot (agent mode in IntelliJ).",
        "The figures below are reconstructed from the local Copilot session logs and git",
        "history by `python colophon.py`; nothing was tracked by hand.",
        "",
        "## Time",
        "",
        f"- **Span:** {first:%Y-%m-%d %H:%M} to {last:%Y-%m-%d %H:%M} ({first:%Z}), "
        f"{_duration(last - first)} wall-clock across {len(all_sessions)} sessions",
        f"- **Copilot working:** {_duration(working)} (union of main-agent turns and sub-agent runs)",
        f"- **Prompts from the owner:** {sum(len(s['prompts']) for s in all_sessions)}",
        f"- **Sub-agents:** {len(agents)} runs, {_duration(sum((a['end'] - a['start'] for a in agents), timedelta()))} "
        f"total, {sum(a.get('totalToolCalls') or 0 for a in agents)} tool calls, "
        f"{sum(a.get('totalTokens') or 0 for a in agents) / 1e6:.1f} M tokens",
        f"- **Main-agent tool calls:** {sum(s['tool_calls'] for s in all_sessions)}",
        f"- **Permission prompts:** {len(waits)}; {len(manual)} waited on the owner "
        f"(5 s or more), {_duration(sum(manual, timedelta()))} in total",
        f"- **Premium requests:** {sum(s['premium'] for s in all_sessions)}",
        f"- **Models:** {', '.join(models) or 'unknown'}",
        "",
        "## Sessions",
        "",
        "| Session | Start | End | Prompts | Copilot working | Sub-agents |",
        "|---|---|---|---|---|---|",
    ]
    for s in sorted(all_sessions, key=lambda s: s["first"]):
        busy = _union(s["turns"] + [(a["start"], a["end"]) for a in s["agents"]])
        lines.append(f"| `{s['id'][:8]}` | {s['first']:%Y-%m-%d %H:%M} | {s['last']:%Y-%m-%d %H:%M} | "
                     f"{len(s['prompts'])} | {_duration(busy)} | {len(s['agents'])} |")
    lines += ["", "## Commits", ""]
    lines += [f"- {when.astimezone():%Y-%m-%d %H:%M} {message}" for when, message in commits]
    if prompts:
        lines += ["", "## Prompts", "",
                  "The owner's messages, in order (Copilot's replies and tool output are omitted).", ""]
        for when, text in sorted(p for s in all_sessions for p in s["prompts"]):
            quoted = "\n".join(("> " + l).rstrip() for l in text.splitlines()) or ">"
            lines += [f"**{when:%Y-%m-%d %H:%M}**", "", quoted, ""]
    return "\n".join(lines).rstrip() + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--sessions", type=Path, default=DEFAULT_SESSIONS)
    parser.add_argument("--no-prompts", action="store_true", help="Omit the owner's prompts")
    args = parser.parse_args()
    found = [summarize(name, path) for name, path in sessions(args.sessions)]
    found = [s for s in found if s["first"]]
    if not found:
        raise SystemExit(f"No Copilot sessions for {ROOT} under {args.sessions}")
    (ROOT / "COLOPHON.md").write_text(render(found, git_log(), not args.no_prompts), encoding="utf-8")
    print(f"Wrote COLOPHON.md from {len(found)} sessions")


if __name__ == "__main__":
    main()
