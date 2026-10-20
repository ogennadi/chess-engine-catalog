# Website

`python publish.py` generates a static website in `dist/` (`--out DIR`
for another location); a fresh clone can run it directly because `data/engines.json` is
committed. It reads only local files—`data/engines.json`,
`data/source-status.json`, `sources.json`, `overrides.json`,
`wiki-source-overrides.json`, and `docs/sources/`—and never accesses the network or
refreshes collection or research. `dist/` is gitignored; only the generator
(`publish.py`), its assets (`site_assets/`), and tests are committed.

* `index.html`: every family, numbered, with its canonical name linking to its page and
  its source links. Search covers canonical names and aliases; the availability filter's
  "Source available" includes archived-only copies. Filters are kept in the URL
  (`?q=...&availability=available|archived|unavailable`) for bookmarking. Without
  JavaScript the full table is shown.
* `families/*.html`: authors (from the CPW engine list, computer-chess.org, the Lucas Chess
  engine configuration and RWBC, falling back to Frank's Chess Page when none of these
  names an author, with
  word-order duplicates merged), aliases, related families, source links (with licence and
  release scope where researched), provenance lists, Chess Programming Wiki link, research
  findings and evidence quotations, and open questions listed apart from reviewed decisions.
  "Related families" shows reviewed `related_families` entries from `overrides.json`
  (`derived_from`, `successor_of`, `same_name` or `distinct_from`, with a note and evidence URL; shown on both
  pages) and `source_aliases` splits, then lists families sharing the same base name
  (e.g. Atlas and Atlas (1967)) explicitly as not reviewed.
* `sources.html`: all provenance lists with descriptions, collection status, and
  discovery notes from `docs/sources`, plus the methodology and research definitions.
* `downloads/`: the printable PDF (as `names_pdf.py` makes it) and `engines.csv`. The
  JSON catalog and research records are not copied into the site, to keep it small; the
  index links to them in the repository instead.

Pages are dark by default; the theme toggle stores the visitor's choice in
`localStorage`. All links are relative, and there are no external scripts, fonts, or
frameworks, so `dist/` can be served by any static host or opened from disk.
