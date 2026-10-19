"""Team accounts are candidates, not necessarily distinct engine families."""

import json
import re


TEAM_URL = "https://lichess.org/team/selfmade-bots"
MEMBERS_URL = "https://lichess.org/api/team/selfmade-bots/users"
USERS_URL = "https://lichess.org/api/users"
EXCLUDED_REPOSITORIES = {
    "lichess-bot", "botli",
}


def name_key(name):
    return re.sub(r"[\W_]+", "", name.casefold())


FORGE_URL = re.compile(
    r"(?<![\w.@/-])(?:https?://)?(?:www\.)?"
    r"(github\.com|gitlab\.com|codeberg\.org|bitbucket\.org|git\.sr\.ht)"
    r"(/[^\s<>]*)?",
    re.I,
)


def repository_links(*texts):
    """Repository roots linked from profile text; deeper paths keep owner/repo."""
    links = {}
    for text in texts:
        for match in FORGE_URL.finditer(text or ""):
            host = match.group(1).casefold()
            path = (match.group(2) or "").rstrip(".,!;:)]}\"'")
            parts = [part for part in path.split("/") if part]
            if len(parts) < 2 or (host == "git.sr.ht" and not parts[0].startswith("~")):
                continue
            # GitLab namespaces can be nested, so only an exact owner/repo is unambiguous.
            if host == "gitlab.com" and len(parts) != 2:
                continue
            owner, repo = parts[0], parts[1].removesuffix(".git")
            if repo.casefold() in EXCLUDED_REPOSITORIES:
                continue
            url = f"https://{host}/{owner}/{repo}"
            # Forge owner/repo paths are case-insensitive; keep the first spelling.
            links.setdefault(url.casefold(), url)
    return sorted(links.values())


def collect(fetch, known_names, overrides):
    members = [json.loads(line) for line in fetch(MEMBERS_URL).splitlines() if line]
    if not members:
        raise ValueError("Lichess returned an empty member list")
    profiles = []
    for start in range(0, len(members), 300):
        ids = ",".join(member["id"] for member in members[start:start + 300])
        profiles.extend(json.loads(fetch(USERS_URL, ids)))
    if {p["id"] for p in profiles} != {m["id"] for m in members}:
        raise ValueError("Lichess bulk profiles did not cover all team members")

    known = {}
    for name in known_names:
        known.setdefault(name_key(name), set()).add(name)
    observations, unresolved = [], []
    non_bots = 0
    for profile in profiles:
        if profile.get("title") != "BOT":
            non_bots += 1
            continue
        account = profile["username"]
        account_id = profile["id"]
        url = "https://lichess.org/@/" + account
        details = profile.get("profile", {})
        repos = repository_links(details.get("bio"), details.get("links"))
        override = overrides.get(account_id)
        if override and override.get("exclude"):
            continue
        family = override.get("family") if override else None
        method = "reviewed-profile" if family else None
        if family is None:
            # Match only to already attested families; never turn an arbitrary
            # account handle or generic repository name into an engine name.
            keys = {name_key(account)}
            stripped = re.sub(r"(?:[-_ ]?(?:bot|engine|chess))+$", "", account, flags=re.I)
            keys.add(name_key(stripped))
            matches = set().union(*(known.get(key, set()) for key in keys))
            if len(matches) == 1:
                family = matches.pop()
                method = "account-name-match"
        observation = {
            "family": family, "label": account, "url": url,
            "membership_url": TEAM_URL, "membership_api_url": MEMBERS_URL,
            "code_urls": [{"url": repo, "evidence_url": url} for repo in repos],
        }
        if family:
            observation["identity_method"] = method
            if override and override.get("identity_evidence_url"):
                observation["identity_evidence_url"] = override["identity_evidence_url"]
            if override and "code_urls" in override:
                if not set(override["code_urls"]).issubset(repos):
                    raise ValueError(f"Reviewed repository is no longer in {account}'s profile")
                observation["code_urls"] = [
                    {"url": repo, "evidence_url": url} for repo in override["code_urls"]
                ]
            elif method != "reviewed-profile":
                # A matched account may link to wrappers or unrelated projects.
                observation["code_urls"] = []
            observations.append(observation)
        else:
            observation.pop("family")
            observation["reason"] = "Engine-family identity requires review; account names are not engine names."
            unresolved.append(observation)
    return observations, unresolved, {
        "members": len(members), "bot_accounts": len(profiles) - non_bots,
        "non_bot_accounts_excluded": non_bots,
        "resolved_accounts": len(observations), "unresolved_accounts": len(unresolved),
    }
