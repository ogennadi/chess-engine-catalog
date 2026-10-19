## Engine Lists
* [CCRL](https://computerchess.org.uk/4040/index.html)
* [Frank's Chess Page](https://web.archive.org/web/20260212005235/https://www.amateurschach.de/main/_engines.htm)
* [Ultimate Bullet Classical](https://e4e6.com/)
* [Lichess selfmade bots](https://lichess.org/team/selfmade-bots)
* [Lucas Chess](https://github.com/lukasmonk/lucaschessR6/tree/4bd66bb9cb1d55bd66156f8de8e128e52f66ba79/bin/OS/linux/Engines)
* [Stefan Pohl Lists](https://www.sp-cc.de/files/uho_full_list.txt)
* [Engine Programming community list](https://github.com/EngineProgramming/engine-list)
* [RWBC XB/UCI Engines Chronology](https://rwbc-chess.de/) ([alphabetic spreadsheet](https://docs.google.com/spreadsheets/d/1Qm_YC4Do6Edj-bTCO5IGc6e4SeDSqRijJjSkHiiSQO0/))
* [CEGT](http://www.cegt.net/)
* [SSDF](https://ssdf.bosjo.net/list.htm)
* [Chess Engines Diary rating lists](https://chessengines.blogspot.com/p/rating-jcer.html)
* [Chess Programming Wiki engine index](https://chessprogramming.org/Engines)
* OpenBench instances: [Grantnet](https://chess.grantnet.us/),
  [chess.swehosting.se](https://chess.swehosting.se/),
  [Clockwork](https://ob.cwchess.org/), [FuryBench](https://furybench.com/),
  [MattBench](https://chess.n9x.co/index/),
  [Sirius](https://mcthouacbb.pythonanywhere.com/),
  [Lynx](https://openbench.lynx-chess.com/),
  [Kai Chung](https://openbench.kaichung.dev/),
  [GyatsoChess](https://gyatsoyt.pythonanywhere.com/),
  [sscg13](https://sscg13.pythonanywhere.com/),
  [Leela Chess Zero](https://bench.lczero.org/)

How each source was found is recorded in [docs/sources](docs/sources/README.md).

## Catalog

* [Engine-family names](data/engine-names.txt)
* [Spreadsheet-friendly catalog](data/engines.csv)
* [Full catalog with provenance and source-code evidence](data/engines.json)
* [Chess Programming Wiki checks for every family](data/chessprogramming-wiki.json)
* [Reviewed wiki source-code link checks](data/chessprogramming-source-code.json)
* [Lichess accounts awaiting engine-identity review](data/unresolved-lichess.json)
* [Source-status research (licensing and availability)](data/source-status.json)
* [Per-family pages](docs/families/README.md)

The current scope is family names, list membership, and explicitly linked source
code. Other properties below are deferred. Missing source-code links mean "not
found in the collected sources," not "closed source." Links are recorded from
source pages; their repositories are not independently audited.
Chess Programming Wiki links are also included in the JSON and CSV.
The CSV is sorted by name descending (`-name`), case-insensitively; the JSON
and plain-text name list retain ascending name order.

### Updating

Requires Python 3.10 or newer; no third-party packages are needed.

```powershell
python collect.py
python collect.py --refresh
python collect.py --offline
python check_wiki.py
python check_wiki.py --refresh
python check_wiki.py --offline
python check_wiki_sources.py
python check_wiki_sources.py --refresh
python check_wiki_sources.py --offline
```

The default run reuses cached HTTP responses in `.cache`. `--refresh` downloads
them again; `--offline` requires cached responses and never accesses the network.
Every network request, including redirects and retries, is spaced at least 1.1
seconds apart within the collector. Run only one collector process at a time.
HTTP 429 responses trigger a wait of at least 60 seconds before retrying.

`sources.json` registers the README sources. Adding a new site requires both a
registry entry and a parser in `collectors`; arbitrary sites cannot be parsed
reliably just by adding a README link. `overrides.json` records reviewed name
aliases, source-scoped homonym splits, and Lichess account-to-engine mappings,
which survive refreshes.

### Chess Programming Wiki

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
link from another source. `wiki-source-overrides.json` records reviewed engine
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

### Source-status research

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

`collect.py` attaches `available` and `archived_only` source URLs to the catalog
(source `source-status-research`) and adds a CSV `source_availability` column:
the research result, `linked` for families with list-supplied source links, or
`not_checked`. It also writes one page per family to
[`docs/families`](docs/families/README.md) with all collected provenance,
source links, licenses, and research notes.

```powershell
python source_status.py dossiers      # research inputs in .cache/research
python source_status.py check out.json
python source_status.py record out.json
python source_status.py summary
```

### Identity and coverage

Names are deduplicated case-insensitively, with explicit aliases for reviewed
spelling differences. Versions/builds are collapsed by each source's parser;
forks, ports, and derivatives remain separate. CCRL's own family grouping is
preferred. UBC's ancestry groups are **not** treated as a single engine: for
example, Stockfish and other Glaurung descendants stay distinct. UBC version
stripping is heuristic, so unusual release names may still need manual aliases.
Cross-source aliases also reconcile CCRL family labels with observed version
names (for example, BugChess2 under BugChess, Vajolet2 under Vajolet, and
Dragon by Komodo under Dragon). Original names remain in aliases/provenance.

Same-named but different programs are kept apart. `source_aliases` in
`overrides.json` reassigns a source's entries (optionally only labels matching a
pattern) to a disambiguated family before name aliases apply, using the wiki's
qualified article name where one exists (for example CCRL/RWBC Joker → Joker NL,
H.G. Muller's engine, while the wiki's Joker remains Baudot and Weill's program).
Otherwise the author's surname is appended, as in Robin (Dachtera) and
Pawn (Coelho). Each rule cites author evidence, usually the CCRL details page;
affected provenance records carry it as `identity_evidence_url`. A rule that
matches nothing is reported as a warning during collection.

Lucas Chess is collected from the pinned Linux-engine directory revision linked
above. Its engine configuration is parsed without executing it and checked
against the repository's directory listing. Multiple Maia strength models and
GreKo releases collapse to one family each; the legacy `komodo` directory
contains Dragon, not an additional Komodo release. Bundled source archives,
explicit source shortcuts, and repository links in the configuration are kept
as source-code evidence. No engine binaries are downloaded or executed.
Change the revision constants in `collectors/lucas_chess.py` and the matching
README/registry links together when intentionally updating this snapshot.

Stefan Pohl's linked text file contributes both the full UHO rating table and
the EAS summary table. All observed release labels, section names, ranks, and
table update dates are preserved; repeated releases collapse into families.
The repeated detailed EAS statistics are not extra engines. CS Tal/CSTal maps
to Chess System Tal, KomodoDragon to Dragon, and playing-style settings stay
within their original family. Cerberus is a distinct composite engine switching
between Patricia and Velvet. Stockfish BAE is a distinct fork replacing the
classical evaluation with big array eval; its repository README supplies
identity and source-code evidence. The rating text itself contains no source
links. Reviewed external evidence adds Gaia's repository, historical Rebel
14.1.02/Tal source, and the old Slow Chess 2.96 source archive. The latter two
are family-level historical links, **not** verified source for the listed
Rebel 16.3/Extreme/EAS or modern Slow Chess Blitz 2.9 releases. Release scope
and caveats are preserved on the JSON source-code records. Cerberus's Patricia
and Velvet dependencies are not mislabelled as source for Cerberus itself.

The Engine Programming community list contributes its Chess and Chess960
sections, plus general-game entries explicitly listing Chess or Chess960.
Ataxx-only, Go, Tetris, and fairy-chess-only entries are excluded. Engine names
come from the project-link labels, not release numbers or author handles.
Chess/Chess960 duplicates merge into families while preserving each section's
provenance. Direct repository links count as source links; generic homepages
and download folders do not. This source is pinned to the revision in
`collectors/engine_programming.py` for reproducible observations; updating that
constant selects a newer snapshot.

Lichess team membership is not proof of a distinct engine family. Non-BOT
accounts are excluded. BOT accounts are linked by reviewed profile evidence or
an unambiguous match of their account name to an already collected family.
Profile bios and the separate profile links field are both scanned for GitHub,
GitLab, Codeberg, Bitbucket, and SourceHut repositories. When a bot publishes
its own engine repository but no engine name, the reviewed family is named
after the account. Accounts running third-party engines such as Stockfish are
excluded. Remaining accounts are kept in `data/unresolved-lichess.json` rather
than presented as engine names; most have no repository link and no engine name
beyond the account handle.
Only reviewed profile mappings contribute Lichess source-code links; generic
bot wrappers, move-generator dependencies, and repositories that returned
HTTP 404 when reviewed are not engine source links.

Frank's Chess Page is collected from the linked February 12, 2026 Wayback
snapshot because the live engine-list URL returns HTTP 404. Only its engine
table is included, not navigation links, GUIs, or engines mentioned in exclusion
notes. Named derivatives remain separate from their ancestors. Archived links
are unwrapped to their original source-repository URLs, while provenance and
source-link evidence point to the snapshot. Neural-network downloads and
programmer profile links are not treated as engine source code.
Source errors and Lichess coverage counts are
recorded in `data/engines.json`. A failed source refresh retains its previous
observations, marked by the source's unavailable status and original check
timestamps.

The JSON preserves observed labels, provenance URLs, collection timestamps,
and evidence URLs for source-code links. UBC observations also preserve POST
parameters needed to reproduce the listing. Generated files are UTF-8.

RWBC uses the spreadsheet's complete **Chronology - Alpha List**, not the
release-calendar worksheet. Original names, authors, source-availability flags,
alternate/previous names, and download links remain in JSON provenance. Ancestry
and previous-name fields do not automatically merge engines. Source flags alone
do not turn homepages or binary downloads into source-code links.

CEGT contributes both all-version Blitz and 40/20 tables. Versions, CPU settings,
and reviewed release names collapse into families; Chessmaster personalities are
not separate engines. SSDF contributes its full historical text list, including
distinct named dedicated chess-computer programs; bare unidentified hardware is
excluded with a recorded warning. Hardware configurations collapse, but named
models remain distinct unless the label explicitly identifies the shared engine.
SSDF detail-page links are attached only when their labels agree with the text
list, since the site's HTML and text lists can differ.

Chess Engines Diary contributes both tables on its current CEDR rating page.
This does not crawl its entire news archive, GUI downloads, opening books, or
binary megapacks. The wiki index contributes only linked programs in its manual
alphabetical list, not categories, authors, forum links, or GUI references.
GUI/controller projects such as DroidFish, PicoChess, and Raspberry Turk are
excluded. Reviewed same-family labels (including Wita/Awit, the Greenblatt
Chess Program/Mac Hack, and Stockfish's NNUE branch) are reconciled while
preserving their original index labels. Source-code coverage excludes
standalone tuning tools and controller software.
Qualified homonymous programs stay separate; historical Atlas (1967) is not
modern Spanish Atlas. Index-linked page titles also supply exact wiki identity
evidence when the displayed engine name differs from its article title.

Each OpenBench instance contributes only the engine directory in its sidebar
(the stock "Engines" list, or a restyled collapsible directory), not test
authors, diff links, or networks. The listed repository is the source link.
The first five instances were named from the `#openbench-instances` channel of
the OpenBench Discord (linked from the OpenBench README); since the Discord
requires a login, their URLs were confirmed from public repositories. The
remaining instances were found by GitHub code search for OpenBench instance
URLs. Each instance's discovery evidence, plus the candidates that were not
registered (offline, mirrors, or variant-only), is in
[docs/sources](docs/sources/README.md).
Reviewed exceptions in `collectors/openbench.py` credit testing forks such as
AndyGrant/Stockfish to the repository GitHub reports as their parent. They map
renamed repositories to their current location, drop private links, and skip
variant-only (e.g. shatranj) engines. MattBench's Torch entry points to a
non-public Chess.com repository.

## properties
* UCI v xboard v Custom
* chess960
* strength limiting options
* Language(s) its written in
* chessprogrammingwiki link
* open source or not
* What engine lists it is in
* HCE v NN v both

## Rules
* Please do not access the sites more than once a second to avoid rate limits
* Keep temporary files inside this repository (for example, under `.cache`),
  not in the system TEMP directory.
* When adding new engines, try to fill in as many columns in the CSV as possible
  (for things like source code link, chessprogrammingwiki link, etc.)