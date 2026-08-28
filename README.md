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
| **Pieces** | `m` | ramps, launch ramps, rails, bumpers, springs, elevators, rotating arms; right clears a cell |
| **Markers** | `k` | left sets the start, right the finish |
| **Pan/zoom** | | moves the map, so a drag close in does not gain tiles |

`1`…`7` choose what the tool in force puts down — which surface, which
mechanism — and the read-out at the bottom says which. Whatever the tool in
force does not want still moves the map: a drag over open space pans, and the
wheel zooms.

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
