# Chess engine list

A deduplicated catalog of chess-engine families collected from public engine lists
(rating lists, wikis, OpenBench instances and others), with source-code links,
Chess Programming Wiki links, and researched source availability and licensing for
each family. It is published as a static website with search, filters, a printable PDF
and a CSV download (the JSON data stays in the repository).

## Generate the website

Requires Python 3.10 or newer; no third-party packages are needed.

```powershell
python publish.py
```

This writes the site to `dist/` (`--out DIR` for another location) from the committed
catalog and research data, without network access. Open `dist/index.html` or serve
`dist/` from any static host.

## More details

* [Website](docs/website.md): what the pages contain and what `publish.py` reads
* [Collecting the catalog](docs/collecting.md): updating the data, outputs, and how
  families are identified per source
* [Research](docs/research.md): Chess Programming Wiki checks and source availability and
  licensing research
* [Engine sources](docs/sources/README.md): every collected list and how it was found