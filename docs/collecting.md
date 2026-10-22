# Collecting the catalog

How `collect.py` builds the engine-family catalog from the [registered sources](sources/README.md). Research and wiki checks are in [research.md](research.md); the website is described in [website.md](website.md).

## Outputs

`python collect.py` generates these. `data/engines.json` is committed so that a fresh
clone can rebuild the website without network access; the others are not committed, so
run `collect.py` to create them locally (see [Updating](#updating)):

* `data/engine-names.txt`: engine-family names
* `data/engines.csv`: spreadsheet-friendly catalog
* `data/engines.json`: full catalog with provenance and source-code evidence
* `data/unresolved-lichess.json`: Lichess accounts awaiting engine-identity review
* `docs/families/`: per-family pages

`python names_pdf.py` (after `collect.py`) writes `data/source-available-engines.pdf`,
a numbered, multi-column list (portrait by default, `--orientation landscape` for landscape) of every family with available source code,
in the largest type (at least 16 pt) that fits on 15 single-sided pages (`--max-pages N`; `0` = fewest pages) (also not committed).

For an experimental single-sheet, 48 x 36 inch landscape poster with the same
alphabetical index numbers:

```powershell
python names_pdf.py --paper poster --orientation landscape --max-pages 1 --out data\source-available-engines-poster.pdf
```

Print at **100% / actual size** on 48 x 36 inch paper, not scaled to a smaller sheet.
The generator chooses the largest font that fits all source-available families on
one page. Families whose source survives only as an archived copy are left off.
The current 1,196-family catalog fits at 23 pt (85% horizontal scale). Each column's number field is only as
wide as its largest index, and leftover width is spread across the gaps between
columns so the left and right margins match. Family names use Atkinson
Hyperlegible, whose serifed `I` and tailed `l` stay distinct from a distance, and
index numbers use Atkinson Hyperlegible Mono so they line up; both are embedded
from `fonts/` (SIL Open Font License 1.1). The header shows the site logo, drawn as
vector shapes, beside a Helvetica title and a subtitle with the generation date and
a link to the repository; pages carry no page numbers. This is an experiment targeting
9-foot viewing, not a guarantee of comfortable readability at that distance;
check a full-size print sample before printing the whole poster.

Each name in the PDF links to one recorded source-code URL. Selection favors
researched links, then corroborated repository links over bundled copies and old
download pages; research notes indicating missing or incomplete content lower a
link's priority, and archive.org or Software Heritage copies are never chosen
over another link. Equal-ranked links retain their catalog order. `poster_source_urls` in
`overrides.json` maps a family to a reviewed choice that replaces the ranking; it must be one
of that family's source links (BabyChess uses the author's GitHub repository rather than
the Savannah project page). This is an offline ranking of collected
evidence, not a fresh HTTP check or a guarantee against future 404s.
PNG copies are for printing and cannot retain clickable links.

Committed inputs:

* [Chess Programming Wiki checks for every family](../data/chessprogramming-wiki.json)
* [Reviewed wiki source-code link checks](../data/chessprogramming-source-code.json)
* [Source-status research (licensing and availability)](../data/source-status.json)

The current scope is family names, list membership, and explicitly linked source
code. Properties listed under [Deferred properties](#deferred-properties) are not
yet collected. Missing source-code links mean "not
found in the collected sources," not "closed source." Links are recorded from
source pages; their repositories are not independently audited.
Chess Programming Wiki links are also included in the JSON and CSV.
The CSV is sorted by name descending (`-name`), case-insensitively; the JSON
and plain-text name list retain ascending name order.

## Updating

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

After changing `overrides.json`, `collectors/wiki.py` or research records, regenerate
offline in this order and commit the updated `data/` files:

```powershell
python collect.py --offline
python check_wiki.py --offline
python collect.py --offline
python check_wiki_sources.py --offline
python publish.py
python -m unittest discover -s tests
```

`--offline` needs the HTTP cache in `.cache`, which is not committed; on a fresh clone,
`python publish.py` alone rebuilds the website from the committed `data/engines.json`.

`sources.json` registers the [sources](sources/README.md). Adding a new site requires both a
registry entry and a parser in `collectors`; arbitrary sites cannot be parsed
reliably just by adding a link. `overrides.json` records reviewed name
aliases, source-scoped homonym splits, and Lichess account-to-engine mappings,
which survive refreshes.

## Identity and coverage

Names are deduplicated case-insensitively, with explicit aliases for reviewed
spelling differences. Versions/builds are collapsed by each source's parser;
forks, ports, and derivatives remain separate. CCRL's own family grouping is
preferred. UBC's ancestry groups are **not** treated as a single engine: for
example, Stockfish and other Glaurung descendants stay distinct. UBC version
stripping is heuristic, so unusual release names may still need manual aliases.
Cross-source aliases also reconcile CCRL family labels with observed version
names (for example, BugChess2 under BugChess, Vajolet2 under Vajolet, and
Dragon by Komodo under Dragon). Original names remain in aliases/provenance.
Zoe Opponent Engine merges into Zoe: both lists identify James Stanley's
`jes/zoe` repository (RWBC lists his name surname-first).
Joker2 merges into Joker IT: both identify Manlio Morini's `morinim/joker`
repository. Joker NL (H.G. Muller) and Joker (Baudot and Weill) remain separate.
Cyclone xTreme merges into Cyclone, Norman Schmidt's engine; its published source
is `FireFather/cyclone-xTreme`. The research retains the caveat that correspondence
to individual CEGT-tested builds is unverified.
Numpty merges into Numpty chess, Chris Tatham's FreeBASIC engine; both Omega and
Recharged source archives and their different licensing notes are preserved.
BlitzKibitz/Amaterasu merges into BlitzKibitz: both list Valentin Stanciu and
Claudiu Bogdan Mihail and the `svalentin/blitzkibitz` repository.
MicroChess 1976 merges into MicroChess, Peter Jennings' 1976 KIM-1 program; both
cite the benlo.com 6502 listing and Andre Adrian's WinBoard port.
Mango and MangoPaolaAjedrez merge into MangoPaola, José Andrés Morales Linares'
engine published in the `mango-computer/mango-paola` and `mango-paola-xboard`
repositories.
Nicarao_Chess merges into Nicarao, Deybis Melendez's engine; both of his
repositories (`DeybisMelendez/NicaraoChess` and `DeybisMelendez/nicarao`) are kept.
Other list spellings of one engine (same author and repository) are aliased:
ApepCE, Julien's Chess3, Electronic Grand Master, Emerald Chess, LittleLelouch,
LunaChess, NatesBot, PLP (PoorLittlePinkus), rusty-redtail (Redtail), Chesslib
(CL-U-E), Bongcloud (sireButItsAnEngine), and The Flying Dutchman (Flying-Dutchman,
whose crate is version 0.1.0). Version-named entries join their family: Prophet3
and Prophet4, Maxima2, CalculonX, Armageddon II, Kallisto II, Quanticade Aurora,
Teki Random Mover (Teki v0.1), Throne (Shadow's former name), Umko (MinkoChess's
former name, renamed in 2012), and GFCv2 (Guillermo
Filia's GFC v2, predecessor of Chronos, merged into GFC). Families whose name
differs from their linked repository's were also checked: Chestnut (UBC's "dev
892e476" is a commit in AriaKafie/chestnut, chessnut's repository) merges into
chessnut; DreamChess into Dreamer, its engine; CrazyAra into ClassicAra, the
standard-chess build the lists rate; and SimpleLearnerBot, the lichess bot running
alexsyrom/chess-engine, into ChessEngine. The wiki's Toledo
article (Óscar Toledo Gutiérrez's Toledo Chess 1/2, Nanochess and Picochess)
merges into Toledo NanoChess, the member the lists rate; his separate x86
program Atomchess is not counted as its source. Toledo 2000 is another author's
program. MessChess is
Mridul Muralidharan's private engine, not Rak Laptudirm's Mess, and stays separate.
SharpChess is Peter Hughes' engine (the wiki article and SharpChess2); RWBC and
computer-chess.org's SharpChess rows are Albert Bertilsson's program, the wiki's #Chess.
PyChess is cataloged as PychessEngine (its RWBC alternate name) because the
lists rate the built-in XBoard engine (`pychess-engine`), not the PyChess GUI.
RWBC sorts some names by a trailing qualifier, such as "Shredder (Deep)" and "Critter
(Chess)"; reviewed aliases merge these into the base family when the author and links
match. Where the lists group a commercial successor with an open predecessor (Deep Sjeng
under Sjeng), the research record's release scope states which releases the source covers.
Dedicated-computer product lines can be grouped as one family when the wiki treats them
as one: the wiki's Fidelity and Mephisto pages each group a manufacturer's models (for
example Chess Challenger, Elite, Excel and Phantom; Mephisto I-III, Amsterdam and MM V),
so these are aliases of Fidelity and Mephisto. The research notes record that the models
run different programs by different authors. Novag groups the dedicated computers with
David Kittinger's programs (1981 onward); Novag's earlier models by other authors, and
Kittinger's PC programs MyChess and WChess, stay separate. Saitek/SciSys groups the
SciSys (until 1987) and Saitek models listed on the wiki's Saitek page, from Super System
III to the RISC 2500; SC 2 absorbs its SC 1 prototype, both GDR clones of Fidelity's Chess
Challenger program.

Same-named but different programs are kept apart. `source_aliases` in
`overrides.json` reassigns a source's entries (optionally only labels matching a
pattern) to a disambiguated family before name aliases apply, using the wiki's
qualified article name where one exists (for example CCRL/RWBC Joker → Joker NL,
H.G. Muller's engine, while the wiki's Joker remains Baudot and Weill's program).
Otherwise the author's surname is appended, as in Robin (Dachtera) and
Pawn (Coelho). Each rule cites author evidence, usually the CCRL details page;
affected provenance records carry it as `identity_evidence_url`. A rule that
matches nothing is reported as a warning during collection.

Some lists label binary-only release repositories as source code. Reviewed
`not_source_urls` rules in `overrides.json` (family, URL, note, evidence URL)
keep such a link out of that family's `source_code`; it is recorded under
`rejected_source_code` and shown with the evidence on the family page. Examples
are Cheng's `cheng4_releases` and Bumblebee's `BumblebeeReleases`. Unmatched
rules are reported as warnings.

Source links that stopped working are reviewed in `unreachable_source_urls`
(family, URL, check date, observed status, optional replacement). Matching
`source_code` links stay in the catalog but carry an `unreachable` note, and the
poster never picks them over a live link. A replacement is a verified working
copy: the author's new home (Feeks, smallchesslib), a packaging repository
(Fairy-Max on Debian salsa), a Software Heritage archive of the deleted
repository, or a dated Wayback snapshot. A family whose only live links are
Software Heritage, Wayback or Internet Archive copies counts as archived only,
even if research marked it available: it is not counted as source available or
put on the poster, and the website marks it Archived with no source link. The 2026-10-21
poster link check, at one request per host, found 46 broken links; 39 now
resolve. No copy was found for Gideon's Chess Engine, Kimbo, MagiC-engine,
ProChess IT, Sinobyl, StoneChess and Viper. Kimbo is recorded as
`released_not_located`: its author's later engine akimbo is not counted as its
source.

CCRL contributes all six lists linked from its home page: 40/15, Blitz, Chess960,
the 40/2 Archive, Chess324, and DFRC. Each family appears once, with the lists it
appears on joined in its provenance section, and source links from every list's
details pages are merged. Only 40/15 is required; any other list that fails to
load is reported as a warning and skipped. Spelling variants on the other lists
map to existing families through reviewed aliases (for example Purple Panda,
TRex, Rebel Century, Leelenstein under Leela Chess, mACE under iCE), and CCRL's
Genesis is Omid David's Genesis IL.

Lucas Chess is collected from the pinned Linux-engine directory revision registered
in `sources.json`. Its engine configuration is parsed without executing it and checked
against the repository's directory listing. Multiple Maia strength models and
GreKo releases collapse to one family each; the legacy `komodo` directory
contains Dragon, not an additional Komodo release. Bundled source archives,
explicit source shortcuts, and repository links in the configuration are kept
as source-code evidence. No engine binaries are downloaded or executed.
Change the revision constants in `collectors/lucas_chess.py` and the matching
`sources.json`/[docs/sources](sources/README.md) links together when intentionally updating this snapshot.

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

The TCEC wiki's **Engines and authors** page contributes only its Engine
Information table, not the per-season TCEC appearance table or UCI-option notes.
Its `**` marker (4k-event engines that fit in 4096 bytes), basic type, language,
and author are kept in provenance. The page styles AllieStein as "Allie...
(engine)" and "...Stein (network)"; both map to Allie. Release and network
suffixes (Fritz 18, Toga II, ScorpioNN, FireNN, Leela Chess Zero, Komodo
Dragon, ...) map to existing families. Raptor (Steve Webber) is Raptor LU,
Nightmare (Joost Buijs) is Nightmare NL, and Nirvana is NirvanaChess. Direct
repository links count as source links; the moonfish homepage links its
SourceHut repository, which is recorded with the homepage as evidence.

The same `tcec-wiki` source also reads **Current Engine Status**, which lists
engines by upcoming TCEC event plus two "Not playing" sections (engines TCEC
will invite, and engines invited only if the author makes contact). Each bolded
engine becomes a row whose section is kept in provenance; placeholders without a
bolded name and the "Suggested engines" and "See also" sections are skipped. The
family is the first word of the bolded name, so "Stoofvlees II d10" is
Stoofvlees; LCZero, KomodoDragon, DeepSjeng, Bagatur.cpp, and Mr_Bob are aliases.
The page has no repository links, so reviewed repositories for CatGPT, molly,
Soul, and SSSimpler come from their TCEC questionnaires, which are the evidence.

Lichess team membership is not proof of a distinct engine family. Non-BOT
accounts are excluded. BOT accounts are linked by reviewed profile evidence or
an unambiguous match of their account name to an already collected family.
Profile bios and the separate profile links field are both scanned for GitHub,
GitLab, Codeberg, Bitbucket, and SourceHut repositories. When a bot publishes
its own engine repository but no engine name, the reviewed family is named
after the account. Accounts running third-party engines such as Stockfish are
excluded. Remaining accounts are kept in `data/unresolved-lichess.json` rather
than presented as engine names; most have no repository link and no engine name
beyond the account handle. A reviewed `"unresolved": true` override keeps a bot
there when its handle merely collides with an unrelated family's name.
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
and evidence URLs for source-code links. Timestamps, in the data and on the website,
are RFC 3339 UTC without fractional seconds (`YYYY-MM-DDTHH:MM:SSZ`); see
`timestamps.py`. UBC observations also preserve POST
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
excluded, as are the chess problem solvers Alybadix, Chest, Gustav, and Popeye,
which solve composed problems but do not play games. Reviewed same-family labels (including Wita/Awit, the Greenblatt
Chess Program/Mac Hack, and Stockfish's NNUE branch) are reconciled while
preserving their original index labels. Source-code coverage excludes
standalone tuning tools and controller software.
Qualified homonymous programs stay separate; historical Atlas (1967) is not
modern Spanish Atlas. Index-linked page titles also supply exact wiki identity
evidence when the displayed engine name differs from its article title.

The Computer-Chess Wiki list (last modified June 2020) contributes its yearly
release tables plus the Dead, Source Code Only, and Withdrawn engine lists; the
"Someday Announcement" list of unreleased projects is excluded. Author, version,
protocol, comment (for example "C++ source"), and all row links are kept in
provenance. Repository links in the engine column are source links, as are
download links explicitly labelled source/code; other download repositories
count only when named after the engine, since many are third-party build
collections. Author profiles are not source. The list's numbered homonyms
(`Chess(2)`, `ChessEngine(3)`, ...) and same-named programs whose authors differ
from the catalog's (Armageddon, Crab, Morphy, Phoenix, Neptune, Savant, Turochamp, Zugzwang)
are split by author surname in `collectors/computer_chess_org.py`; reviewed
spelling variants map to existing families there as well.

Each OpenBench instance contributes only the engine directory in its sidebar
(the stock "Engines" list, or a restyled collapsible directory), not test
authors, diff links, or networks. The listed repository is the source link.
The first five instances were named from the `#openbench-instances` channel of
the OpenBench Discord (linked from the OpenBench README); since the Discord
requires a login, their URLs were confirmed from public repositories. The
remaining instances were found by GitHub code search for OpenBench instance
URLs. Each instance's discovery evidence, plus the candidates that were not
registered (offline, mirrors, or variant-only), is in
[docs/sources](sources/README.md).
Reviewed exceptions in `collectors/openbench.py` credit testing forks such as
AndyGrant/Stockfish to the repository GitHub reports as their parent. They map
renamed repositories to their current location, drop private links, and skip
variant-only (e.g. shatranj) and non-chess (the shogi engine Stoat) engines. MattBench's Torch entry points to a
non-public Chess.com repository.

## Deferred properties

Properties to track per engine in future:

* UCI v xboard v Custom
* chess960
* strength limiting options
* Language(s) its written in
* chessprogrammingwiki link
* open source or not
* What engine lists it is in
* HCE v NN v both

## Colophon

`python colophon.py` writes `COLOPHON.md`, which records how long the catalog took to
build and the prompts that guided it. It reads the local GitHub Copilot session logs
(`~/.copilot/session-state`) and git history. Only the script is committed: the file is
gitignored because it depends on logs that exist only on the machine that ran the
sessions. Pass `--no-prompts` to leave out the prompt text.
