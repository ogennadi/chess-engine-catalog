# How chess engines limit their strength

This report covers the 55 engine families in `strength-limited-engines.csv`, plus Patricia and Gaia as reference points. Sections 1–4 cover the 47 that have a UCI or xboard strength option. Section 5 covers the 8 whose level is set only by a console command or startup switch; these are marked `*` in the table. Each engine's weakening code was read in its source. Line-level permalinks for the first 47 are in the session `all.json`.

PolarChess was dropped from the table. Its `setoption` handler has the condition `else if ("UCI_LimitStrength")`, which is always true, so `UCI_Elo` never reaches the search.

## 1. Taxonomy

| Mechanism | What it does | Engines (examples) |
|---|---|---|
| **Depth cap** | Stops iterative deepening at a fixed number of plies. | CHEKMO-II, Cheops, MeikeChess, Vajolet, Igel, Galjoen, Arasan; also inside Stockfish-style schemes |
| **Node budget** | Gives a fixed node count per move, usually exponential in Elo. | DiscoCheck, GOOB, Rodent, Velvet, Snaky, Demolito, Hypersion, Cheese (nodes mode) |
| **Speed throttle (NPS)** | Sleeps to hold a target nodes-per-second rate. The result depends on wall-clock time. | GreKo, CT800, MadChess, Cheese (default), Texel and CuckooChess (under `UCI_LimitStrength`), Irina |
| **Eval noise** | Adds random centipawns to every static evaluation. | Cheng, Mayhem, Reglisse, Sapeli, Kreveta, Demolito, CT800 |
| **Eval degradation** | Uses a deliberately worse evaluation, either by blending or by switching. | Eguzki (3-way blend), Zahak (under-trained nets), MadChess (Elo-faded terms), RapChess (random PST blend), Snail-Chess (cruder tables), Snaky (material-only below 1300) |
| **Hash-seeded eval distortion** | Scales or flips the evaluation by a factor taken from a hash. | EXchess (pawn-hash multiplier in {−3, −1, +1, +3}) |
| **Root choice within a margin** | Searches several lines (MultiPV), then picks a weaker one within N cp. | Stockfish, Fairy-Stockfish, Minic, Peras, Avalanche (softmax), Zurichess, Galjoen, Alfil, PyTuroChamp, MadChess, Arasan |
| **Blunder chance** | Has a per-move probability of using a much wider margin, or a random top-half move. | MadChess, Hypersion (25%→5%), PyTuroChamp, Arasan, Gaia |
| **Move blindness** | Never sees some moves in the search tree. | Texel, CuckooChess, ChessV, EXchess (hash-seeded); Karballo (random rejection of improvements); Gaia |
| **Pruning or quiescence damage** | Removes the quiescence search, adds extra reductions, or randomly skips quiescence. | Igel, PychessEngine, ChessV, CT800 (drops checks in quiescence) |
| **Human policy net** | Samples moves from a neural net trained on human games of a given rating. | Sapling |
| **Personality or strategy mix** | Each move, picks a crude move-picker by weight. | Irina (random / king-hunt / capture / material / full), Sjaak (Clueless / Random / Static), Annie ("anarchy" parameters) |
| **Book limit** | Uses a shallower book, or consults it with some probability. | Karballo, Arasan, Irina, Gaia (Rodent computes a book limit but never uses it) |
| **Random mover** | Plays a uniformly random move at the lowest level. | Mayhem, Sapeli, Minic, Igel, Texel, CuckooChess, Sjaak, Irina |

Tallies across the 47 non-reference engines:
- **Randomness:** 29 are clock- or OS-seeded, 14 deterministic, 6 hash-seeded.
- **Hardware:** only about 18 are hardware-independent, meaning they use depth or node limits and the clock cannot change the move.
- **Calibration:** only about a dozen have a *measured* Elo calibration: Stockfish, Peras, Texel, CuckooChess, Cheese, Snaky, Velvet, Zahak, Hypersion, Annie, Kreveta, and partly CT800. The rest use linear or hand-picked formulas.

## 2. Is anyone like Patricia (blunder budget)?

**No.** No other engine carries an error allowance across moves. Patricia adds `cp_loss` per move to a running budget, spends it on the worst top-5 move it can afford, and deducts what it spent.

Closest (each decision is per move, with no memory between moves):
- **MadChess** and **PyTuroChamp** search all root moves exactly. They pick at random within a *move-error* margin, and with a set probability within a much larger *blunder* margin.
- **Arasan** substitutes a root move within a tolerance, with an Elo-scaled probability. At low strength it may ignore the tolerance.
- **Zurichess** picks at random among 2–5 PVs within `H²/2 + 10H + 5` cp.
- **Stockfish, Fairy-Stockfish, Minic, Peras and Avalanche** use a weighted pick from the top MultiPV lines.
- **Galjoen** picks at random among MultiPV lines within `(2100 − Elo)` cp. It only works if MultiPV > 1.

Patricia's two distinctive ideas appear nowhere else. One is per-game error accounting, so the total loss per game is bounded and spread out. The other is a deliberate preference for "human-looking" material sacrifices.

## 3. Is anyone like Gaia (several deterministic, hash-seeded weakenings)?

**No engine matches it fully.** Gaia combines 7 knobs per rung, makes every decision from `hash(position ^ seed)`, runs single-threaded with no time dependence, and uses a measured ladder. The partial matches fall into two groups.

**Deterministic or hash-seeded, but with fewer knobs:**

| Engine | What matches Gaia | What is missing |
|---|---|---|
| **EXchess** | Two hash-derived knobs: eval distortion from the pawn hash, plus move blindness from the position hash. No RNG, so it is reproducible across games. | Search is still time-based; no depth, book or root-variety knobs; not calibrated. |
| **Texel / CuckooChess** | Stable blind spots from `zobrist ^ move ^ seed`, deeper in the tree and on quiet moves (essentially Gaia's *vision* knob), a root-move subset at low strength, a measured Elo table, and Texel forces 1 thread. | The seed is re-randomized each game; the NPS cap under `UCI_LimitStrength` makes it time-dependent; essentially one knob. |
| **ChessV** | Hash-slice blind spots plus extra LMR and razoring; deterministic when Variation = None. | Time-based; no Elo mapping. |
| **Snaky** | Calibrated node budget, forced single thread, and Zobrist-seeded tie-breaks in a material-only greedy search below 1300. | One knob per level. |

**Several knobs, but random and time-dependent:**

| Engine | Knobs |
|---|---|
| **MadChess** | NPS throttle, Elo-faded eval terms, move-error margin, blunder chance — the closest design to Gaia's overall structure. |
| **Hypersion** | Calibrated buckets setting a node cap, a depth cap and a blunder probability; hardware-independent; turns off in won endgames; auto-matches the opponent's rating. |
| **CT800** | NPS cap, eval-noise blend, mate blindness that grows with depth, and no checks in quiescence at high noise. |
| **Arasan** | Depth table, root substitution with blunders, and book thinning. |
| **Annie** | 13 tuned parameters per level, each measured in a gauntlet. |
| **Irina** | A weighted per-move strategy draw. |

In short, Gaia is the only engine that combines **multiple knobs, hash-seeded determinism and hardware independence** in one design. EXchess and Texel/CuckooChess show that the hash-seeded "blind spot" idea predates it.

## 4. Other notable designs

- **Human imitation:** Sapling (formerly iBlunder) uses a policy net conditioned on rating to sample over depth-8 root moves.
- **Evaluation ladders:** Eguzki blends three evaluations by Elo; Zahak ships six deliberately under-trained NNUE nets.
- **Game-phase awareness:** Hypersion lifts its limits in won endgames; Demolito raises its level as pieces come off; MadChess slows down further in endgames.
- **Opponent matching:** Hypersion's `UCI_MatchOpponent` sets its Elo just below the opponent's rating.

## 5. Strength limits outside the protocol

These engines are not in the table above, because they don't advertise a UCI or xboard strength option. Their levels are set by a startup switch or a console command instead. Crafty's source was read from the `MichaelB7/Crafty` mirror; the others came from the source cache.

| Engine | Lang | Set by | Mechanism |
|---|---|---|---|
| **Phalanx** | C | `-e 0..100` switch or `easy` command | **Human-like blindness (unique among all engines reviewed).** At each node it drops moves with a probability built from what humans tend to miss. Long, diagonal, backward, knight, underpromotion and off-centre moves, and moves far from the opponent's last move, are missed more often. Short captures, captures of valuable pieces, recaptures, best-line moves and moves by the piece moved two plies ago are seen more often. Also caps speed at `500 − 3·level` nodes per second, adds randomness of `10 + level/2`, shuffles root moves, stops at random and adds think delays (`easy.c`, `phalanx.c:306-310`, `search.c:265-310`). Level 0 is full strength. |
| **KnightCap** | C | `weakness`, `dementia` commands | **Evaluation distortion:** `weakness` scales each eval coefficient up by a random 0–`weakness`×100% but never flips its sign (`eval.c:2160`). **Forgetting:** `dementia` drops generated moves at random; longer moves are dropped more often (10–30% by distance) and captures twice as often (`generate.c:1267`). |
| **Beowulf** | C | `skill 1..10` command (per side) or personality file | **Feature ladder.** As skill falls it turns off internal iterative deepening (above 8), pawn-push extensions (above 7), history (above 5), killers and recapture extensions (above 4), good-capture ordering (above 3) and check extensions (above 2). Adds `(10−skill)·8` random noise to move ordering and about `(10−skill)·4` noise to the eval. Weaker levels resign later (`comp.c`, `eval.c:362-364`). |
| **Cupcake** | Java | `skill 0..9` command or `.per` file | **Depth cap that grows as material comes off** (`skill·(100 + (7800−material)/39)/100`). Skill 1 picks at random from root moves within 50 cp of the best. The unofficial skill 0 plays the best move by 1-ply quiescence search. Skill 7 and below use up leftover time when a search ends early (`Search.java:619-723`). A separate `style 1..9` command scales aggression. |
| **Crafty** | C | `elo 800..3600` command (built in by default: the shipped Makefile sets `-DELO`) | **Speed throttle by busy-loop plus eval blending.** Interpolates a target speed from a 15-point table (1 thousand nodes/s at 800 Elo, 750 thousand at 2600, 300 million at 3600). Each eval call runs a CPU-burning loop, which is retuned after every iteration to hit the target speed (`data.c:679`, `evaluate.c:34`, `iterate.c:546`). The eval becomes `r%·eval + (100−r)%·random[0, 1 pawn)`, where `r = min(1800, Elo−800)/18`. At 800 Elo the eval is pure noise; at 2600 and above, none (`option.c:644`, `evaluate.c:306`). Replaced the older `skill 1..100` command. |
| **Puca** | C | `beginner`…`grandmaster` startup argument | Random eval noise (`knowledge`) plus a depth cap, both drawn at random within ranges for each level, e.g. beginner gets depth 2–3 and noise of 220–499 (`puca.c:46-55`). |
| **ChessbotX** | Java | easy/normal/hard/ultra startup mode | Depth cap only (3–7). |
| **SilChess** | C++ | depth startup argument | Depth cap only. |

Maia also fits here: its strength comes from loading separate rating-trained nets (1100–1900) through Lc0's weights-file option, not from a strength setting.

## 6. Bugs and quirks found

- **PolarChess:** the always-true `else if` means `UCI_Elo` is never applied, so the engine always plays at full strength.
- **GreKo:** `UCI_Elo` only takes effect if `UCI_LimitStrength` was set *before* it.
- **Alfil:** `UCI_LimitStrength` is effectively ignored; `UCI_Elo` below 3000 alone weakens it.
- **Cheese:** an integer-division bug makes the personality "Randomness" evaluation pure noise.
- **Galjoen:** the handicap margin does nothing unless MultiPV > 1, and a 2600 setting keeps an earlier depth cap.
- **Rodent:** the book-depth limit is computed but never used.
- **Irina:** its per-piece personality weights are parsed but never used.
- **Cheng:** "Skill" is pure eval noise, not a weaker evaluation as the CSV notes suggest.
- **Crafty:** in pawnless positions, the Elo noise is assigned to `score` but the function returns `tree->score_eg`, so there is no randomisation there (`evaluate.c:124-128`). Also, `elo 800` reads `elo_burnc[-1]`, out of bounds (multiplied by 0, but still undefined behaviour) (`option.c:646-649`).
- **Crafty:** the code comments disagree on the baseline: 6M nodes per second is called both "about 2600" and "about 2800" (`option.c:610`, `data.c:676`).
