# Website

`python publish.py` generates a static website in `dist/` (`--out DIR`
for another location); a fresh clone can run it directly because `data/engines.json` is
committed. It reads only local files—`data/engines.json`,
`data/source-status.json`, `sources.json`, `overrides.json`,
`wiki-source-overrides.json`, `docs/sources/` and
`strength-limited/strength-limited-engines.csv`—and never accesses the network or
refreshes collection or research. `dist/` is gitignored; only the generator
(`publish.py`), its assets (`site_assets/`), and tests are committed.

* `index.html`: every family, numbered, with its canonical name linking to its page and
  its source links. Families whose source survives only as an archived copy are marked
  Archived, with no source link; their names still link to their family pages.
  To avoid sending crawlers of this site to archive.org, no page links to
  archive.org: Wayback URLs are shown as their original (broken) URL, crossed out,
  in plain text (family source sections add a note that a copy is on the Wayback
  Machine), and Internet Archive items as
  unlinked text. Search covers
  canonical names and aliases; the availability filter's "Source available" excludes
  archived-only families, which have their own "Archived source only" option. The
  strength-limit filter shows only the families listed in
  `strength-limited/strength-limited-engines.csv` (engines with a built-in way to play
  weaker, confirmed in their source); unknown names there produce a warning. Filters are kept in the URL
  (`?q=...&availability=available|archived|unavailable&strength=limited`) for bookmarking. Without
  JavaScript the full table is shown.
* `families/*.html`: authors (from the CPW engine list, computer-chess.org, the Lucas Chess
  engine configuration and RWBC, falling back to Frank's Chess Page when none of these
  names an author, with
  word-order duplicates merged), aliases, related families, source links (with licence and
  release scope where researched), provenance lists, Chess Programming Wiki link, research
  findings and evidence quotations, and open questions listed apart from reviewed decisions.
  Families in the strength-limited table also get a "Strength limiting" section: the
  reviewed options, whether they are a UCI/xboard option or a console command or startup
  switch, and a pinned permalink to where the source defines them (the CSV's `Options`
  and `Options source` columns, written by `strength-limited/table_pdf.py csv`).
  "Related families" shows reviewed `related_families` entries from `overrides.json`
  (`derived_from`, `successor_of`, `same_name` or `distinct_from`, with a note and evidence URL; shown on both
  pages) and `source_aliases` splits, then lists families sharing the same base name
  (e.g. Atlas and Atlas (1967)) explicitly as not reviewed.
* `sources.html`: all provenance lists with descriptions, collection status, and
  discovery notes from `docs/sources`, plus the methodology and research definitions.
* `downloads/`: a single-page **48 x 36 inch landscape poster PDF** of all
  source-available families, alphabetically indexed, with each name linking to its
  preferred recorded source-code URL, and `engines.csv`. The poster uses the largest
  font that fits on one sheet (at least 16 pt); print at actual size. Link selection
  uses the offline evidence ranking described in [collecting.md](collecting.md),
  not fresh HTTP checks. The
  JSON catalog and research records are not copied into the site, to keep it small; the
  index links to them in the repository instead.

Pages are dark by default; the theme toggle stores the visitor's choice in
`localStorage`. All links are relative, and there are no external scripts, fonts, or
frameworks, so `dist/` can be served by any static host or opened from disk.
