# openglcontext-marble-editor

The board editor for the [marble game](https://github.com/mcfletch/marble-demo):
draw a board, put ramps and mechanisms on it, and play it.

```bash
oglc-marble-editor                    # a blank board to draw on
oglc-marble-editor spiral.marble      # carry on with one
oglc-marble-editor --from-seed 7      # start from a generated board
```

The window is a **map**: the board from straight above, orthographic, so a cell
is the same number of pixels wherever it is. A strip down the left says what the
pointer is for; the menus keep what applies to the whole board.

Two conventions run through every tool, and they are the ones you already
expect: **left does and right undoes** — left lays a tile, right takes it away;
left places a mechanism, right clears it — and **a drag is one step**, so
painting twenty tiles across a board comes back in one press of undo.

## Tools

| Tool | Key | The pointer |
|---|---|---|
| **Tiles** | `t` | lays tiles; right takes them away |
| **Height** | `h` | raises a tile a step; right lowers it. A drag *levels* a terrace to the height it started at rather than building a staircase |
| **Surface** | `u` | paints ice, metal or rubber; right paints the board's own surface back |
| **Pieces** | `m` | ramps, launch ramps, rails, bumpers, springs, elevators, rotating arms, and every mechanism the game registers that stands on one cell — doors, levers, magnets, peg boards, rockfalls, water; right clears a cell |
| **Markers** | `k` | left sets the start, right the finish |
| **Pan/zoom** | | moves the map, so a drag close in does not gain tiles |

`1`…`7` choose what the tool in force puts down — which surface, which
mechanism — and the read-out at the bottom says which. Whatever the tool in
force does not want still moves the map: a drag over open space pans, and the
wheel zooms.

The palette's second half is **discovered rather than listed**: the game finds
its mechanisms by scanning its own package directory, so a mechanism it gains is
a new file there and nothing else, and it appears here without the editor being
touched. What is not offered is a mechanism that covers a *field* of cells --
sand, a burner -- because placing one is a gesture that paints an area rather
than a click on a tile.

A **ramp arrives pointing downhill** and a **rail facing the void**, because the
board knows both, so placing one is a click rather than a form.

| Key | |
|---|---|
| `f` | fit the whole board in the window |
| `ctrl-z` / `ctrl-y` | undo, redo |
| `ctrl-s` | save |
| `ctrl-p` | play it |

## What the read-outs say

`BOARD` is the name and whether it is saved; `TILES` and `CLOCK` are what a board
is judged on; `STATE` is `playable`, or the first thing that would stop it being
played — most usefully *the finish cannot be reached from the start*, which is
not something to find out by playing.

Nothing here stops you making a board that is half-drawn: that is a normal thing
to be looking at, and an editor that refused would be fighting you for the whole
middle of the work. It says so instead.

## Showing what it does

```bash
oglc-marble-editor --tour                              # a scripted sitting
oglc-marble-editor --tour --size 1280 720 \
    --record editor.mp4 --record-seconds 31            # ...recorded
```

A **tour** is a list of moments — *at four seconds take the height tool, at five
drag from here to there* — played back through the same `ProcessEvent` a hand's
clicks reach, so what it shows is the editor being used rather than an animation
of it. It runs through every tool in turn and says what it is about to do in the
read-out.

That is also why it is kept rather than thrown away: a step naming a tool the
editor does not offer, or a piece that does not exist, is a step a test catches.

Recording turns vsync off, because an editor asks for a frame only when
something changed and a recording wants every frame it can draw.

## Generating a board

**Board → Generate a board → *n* chapters → difficulty *d*** composes a whole
board out of the library and opens it. It has a rhythm rather than a shuffle:
places and challenges alternate, it begins and ends somewhere safe, the same
question is not asked twice running, it gets harder as it goes, and something on
it has a way round it.

Difficulty is a **ceiling** on what may appear rather than a target, so an easy
board is one with nothing expensive on it and not one with cheap things forced
onto it.

Then it is an ordinary board: one press of undo takes the whole thing back, every
tile is editable, chapters can be added to the end, and it saves like any other.
That is the reason to generate one inside an editor — a generated board nobody
can change is somebody else's board, and here you get to disagree with it.

The name carries the seed, so a board worth keeping can be made again.

## Chapters

The tile tools draw a board one square at a time, which is right for the last
tenth of the work and wrong for the first nine. **Story → *fragment* → *variant***
appends a chapter from the game's library to the end of the board: entered where
the board currently ends, leaving somewhere new, bringing its own walls,
mechanisms and surfaces — and then the tile tools are there to change it.

That is the argument for putting the library in an editor rather than in a
generator. A generated board is somebody else's board; a board with three
chapters in it and an hour of tile edits on top is yours.

A chapter is **one press of undo**, however many tiles it laid. The finish moves
to the end of what was added, so chapters chain.

**Story → Add a run of chapters → *length* → *difficulty*** puts a whole composed
run on the end instead of one chapter: places and challenges alternating, the
cheap ones first, a run-up in front of anything that has to be arrived at fast,
and a way round one of them. Board → Generate replaces what is open; this adds to
it, which is what makes the library something to build a board *out of* rather
than only something to start from. Also one press of undo.

**Story → Material** chooses what chapters added afterwards are built of — stone,
metal, ice or rubber — or leaves each one to whatever it prefers. A theme is a
floor material, a wall material and a sound name together, so choosing one
decides what the room is made of.

Where two chapters meet, the walls that end up between them are taken out again:
a piece rails its own edge against the cells it knows about, and the piece laid
next to it comes afterwards, so a wall that faced the void when it was placed
would otherwise end up across the way on. Only the walls laid by that step are
considered — a rail you drew between two of your own tiles is one you meant.

The menu is the library, and the library is discovered by scanning its own
directory — a fragment added to the game appears here without the editor being
told about it.

## Boards

A board is a `.marble` file: JSON, one cell to a line and one mechanism to a
line, small enough to read and to fix by hand. The format belongs to the game
(`openglcontext_marble_demo.levelfile`), which is what keeps the editor and the
game from ever disagreeing about it.

```bash
oglc-marble --board spiral.marble     # play one without the editor
```

## How the code is organized

```
marble-editor/
  marble_editor/
    board.py      BoardEditor: every change, the rules, and undo
    editing.py    the tools -- gestures only, no rules
    scene.py      a board drawn as a map
    controls.py   pointer -> tools, and what the tools do not want moves the map
    status.py     the read-outs
    app.py        the window
```

Everything but `app.py` is headless and unit tested: the rules about what a board
may be, the gestures that change one, and what the map draws are all asked
without a window. `app.py` is the glue.

### The engine side

The editor is built on the authoring toolkit in `OpenGLContext` itself:
`OpenGLContext.edit` supplies the plan view (`MapView`, `MapViewPlatform`) and
the tool modes (`ToolMode`, `ToolManager`, `Pointer`) that give the tool in force
first refusal of the pointer; `OpenGLContext.ui` supplies the tool palette, the
menu bar and the read-outs. It is the same foundation `glisteel-editor` is built
on.

`OpenGLContext-editor` — the world-authoring package — is deliberately *not* a
dependency: that is DEM terrain, road alignment and 3D Tiles baking, and a board
is a grid of tiles.

## Working with the code

```bash
python -m pytest
ruff check .
mypy marble_editor
```

## Licensing

MIT (`LICENSE`).
