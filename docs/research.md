# Research

Checks that add Chess Programming Wiki links and source-code availability and licensing research to the catalog. See [collecting.md](collecting.md) for the collection pipeline.

## Chess Programming Wiki

`check_wiki.py` checks every catalog family against the wiki's public
`search-index.json` in one bulk request, rather than making hundreds of page
requests. Only main-namespace pages count, not categories, images, or templates.
The site's current read-only recovery has no working MediaWiki API. The same
cached, 1.1-second rate-limited fetcher is used for wiki requests.

Each engine's `chessprogramming_wiki` records `status`, page URL/title,
`checked_at`, title-index evidence, and the names checked. Exact title matches
and catalog aliases are supplemented by reviewed mappings in
`collectors/wiki.py` (for example, Leela Chess to Leela Chess Zero, and Queen
to Queen (engine), not the chess-piece article).

`found` confirms an indexed matching page, not an independently audited engine
identity. `not_found` means no matching indexed title was found under the
checked names; it is not proof that the engine is never mentioned elsewhere.
`needs_review` keeps ambiguous or unrelated lookalikes unlinked (for example,
modern Nu-chess versus historical Nuchess, or the unrelated Atlas program).
No fuzzy name matches are accepted automatically. New engines added after the
last check are `not_checked` until the wiki checker is run again.

The separate wiki-results file survives catalog regeneration; `collect.py`
reattaches saved results to the JSON/CSV without additional wiki requests.
Re-run `check_wiki.py --refresh` to recheck the current catalog against a fresh
index. Failed index requests or malformed responses fail explicitly and do not
overwrite the previous results.

`check_wiki_sources.py` examines wiki-linked families that have no source-code
link from a provenance list (links attached from research records do not count),
plus every family already reviewed in `wiki-source-overrides.json`, so reviewed
results are never dropped. Reviews whose family was renamed or merged are reported
as warnings. `wiki-source-overrides.json` records reviewed engine
links and negative decisions: repository links to dependencies, other engines,
author profiles, and the wiki's own software are not engine-source evidence.
Unreviewed pages are flagged `needs_review`, not automatically accepted.
Source records preserve the wiki evidence URL and fetch timestamp, plus release
scope or archive caveats where relevant. A recorded link means the wiki supplies
it; it does not guarantee the external repository or old archive is still live.
Network or parsing failures leave the previous results unchanged.

Saved wiki-source results are reattached to JSON and CSV on catalog regeneration,
without inventing wiki list membership. Re-running the checker includes families
whose only source links came from the wiki. Changed wiki identities or removed
reviewed links require review instead of silently retaining those links.

## Source-status research

`data/source-status.json` records web research for families that have no source
link from any list (and for families whose only source is a Lucas Chess copy).
Each family is classified on two independent axes, with evidence URLs and a
rationale:

* `licensing`: `open_source`, `source_available`, `proprietary`, or `unknown`
  (freeware binaries stay `unknown`; a wiki Commercial category is enough for
  `proprietary`, but source is still searched for).
* `availability`: `available`, `archived_only`, `released_not_located`,
  `not_located`, or `not_checked`.

Source from a precursor, derivative, or homonym is never attributed. A mirror
makes source available, but originals are preferred and licensing comes only
from the rights holder. "Source not located" never implies closed source.
`source-status-pilot.json` is the approved 51-family pilot, now merged into this
file.

`archived_only` families are not counted as source available (website counts,
filter, and poster), but their archive links stay on their family pages.

`collect.py` attaches `available` and `archived_only` source URLs to the catalog
(source `source-status-research`) and adds a CSV `source_availability` column:
the research result, `linked` for families with list-supplied source links, or
`not_checked`. It also writes one page per family to `docs/families` with all
collected provenance, source links, licenses, and research notes.

```powershell
python source_status.py dossiers      # research inputs in .cache/research
python source_status.py check out.json
python source_status.py record out.json
python source_status.py summary
```
