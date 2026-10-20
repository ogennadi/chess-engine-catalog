# Engine sources

One page per source registered in [`sources.json`](../../sources.json), recording how it was found.
Collection timestamps and per-source status are in `data/engines.json`, which `collect.py` generates.

| Source | URL |
|---|---|
| [CCRL 40/15](ccrl.md) | <https://computerchess.org.uk/4040/index.html> |
| [Frank's Chess Page engine list](amateurschach.md) | <https://web.archive.org/web/20260212005235/https://www.amateurschach.de/main/_engines.htm> |
| [Ultimate Bullet Classical](ubc.md) | <https://e4e6.com/> |
| [Lucas Chess bundled Linux engines](lucas-chess.md) | <https://github.com/lukasmonk/lucaschessR6/tree/4bd66bb9cb1d55bd66156f8de8e128e52f66ba79/bin/OS/linux/Engines> |
| [Stefan Pohl full UHO and EAS rating lists](stefan-pohl.md) | <https://www.sp-cc.de/files/uho_full_list.txt> |
| [Engine Programming community engine list](engine-programming.md) | <https://github.com/EngineProgramming/engine-list> |
| [RWBC XB/UCI Engines Chronology](rwbc.md) | <https://rwbc-chess.de/> |
| [CEGT all-version rating lists](cegt.md) | <http://www.cegt.net/> |
| [SSDF historical rating list](ssdf.md) | <https://ssdf.bosjo.net/list.htm> |
| [Chess Engines Diary CEDR rating lists](chess-engines-diary.md) | <https://chessengines.blogspot.com/p/rating-jcer.html> |
| [Chess Programming Wiki alphabetical engine index](wiki-engines.md) | <https://chessprogramming.org/Engines> |
| [OpenBench: Grantnet (Andrew Grant)](openbench-grantnet.md) | <https://chess.grantnet.us/> |
| [OpenBench: chess.swehosting.se](openbench-swehosting.md) | <https://chess.swehosting.se/> |
| [OpenBench: Clockwork](openbench-clockwork.md) | <https://ob.cwchess.org/> |
| [OpenBench: FuryBench](openbench-furybench.md) | <https://furybench.com/> |
| [OpenBench: MattBench](openbench-mattbench.md) | <https://chess.n9x.co/index/> |
| [OpenBench: Sirius (mcthouacbb)](openbench-sirius.md) | <https://mcthouacbb.pythonanywhere.com/> |
| [OpenBench: Lynx](openbench-lynx.md) | <https://openbench.lynx-chess.com/> |
| [OpenBench: Kai Chung (Onslaught)](openbench-kaichung.md) | <https://openbench.kaichung.dev/> |
| [OpenBench: GyatsoChess](openbench-gyatso.md) | <https://gyatsoyt.pythonanywhere.com/> |
| [OpenBench: sscg13](openbench-sscg13.md) | <https://sscg13.pythonanywhere.com/> |
| [OpenBench: Leela Chess Zero](openbench-lczero.md) | <https://bench.lczero.org/> |
| [Computer-Chess Wiki chess engine list](computer-chess-org.md) | <http://computer-chess.org/doku.php?id=computer_chess:wiki:lists:chess_engine_list> |
| [Lichess Selfmade bots](lichess.md) | <https://lichess.org/team/selfmade-bots> |

## OpenBench candidates not registered

| Instance | Reason |
|---|---|
| kelseyde.pythonanywhere.com (CalvinBench) | Named "Calvin" in the Discord list; URL from kelseyde/hobbes-chess-engine `pretty.rs`. HTTP 404 on `/` and `/index/`; no Wayback snapshot. |
| "Adam Grant" | Named in the Discord list; no public URL found. |
| "Paul Sonkoly" | Named in the Discord list; [paulsonkoly/OpenBench](https://github.com/paulsonkoly/OpenBench) exists (engines: chess-3, Stash, Stockfish) but no public instance URL was found. |
| belzedar.duckdns.org | Live, but lists only variant Stockfish derivatives (Spell, Atomic, Alice, KOTH, Horde, Terachess, 3Check, Crazyhouse). |
| openbench.nocturn9x.space | Same instance as MattBench. |
| bench.plutie.ca | Same engine list as bench.lczero.org. |
| somelizard, zzzzz151, pyronomy, programcidusunur, analoghors, peaob, rafiddev, commanderkugel, synthetica.eu, rektdie, engineprogramming, rxjourneyserver (`*.pythonanywhere.com`) | HTTP 404 on 2026-10-18 (free PythonAnywhere apps expire). |
| openbench.seajay-chess.dev | DNS lookup failed on 2026-10-18. |
