"""A board being edited: every change a designer can make, and taking it back.

:class:`BoardEditor` owns a
:class:`~openglcontext_marble_demo.level.Level` and is the only thing that
changes one. It knows nothing about a window, a pointer or a tool — it is asked
to lay a tile at a cell, raise one, put a bumper on one — so every rule about
what a board may be is a question a test can ask, and the tools in
:mod:`marble_editor.editing` are left with nothing in them but gestures.

**Undo is a snapshot.** A board is tens of cells and a handful of mechanisms, so
the whole of one costs less to keep than the bookkeeping for undoing each kind of
change would, and a snapshot cannot get an inverse wrong. What makes that usable
rather than maddening is :meth:`begin_step`: a drag across twenty cells is one
thing the designer did, and comes back in one.

**A board is kept playable.** The start and the finish always sit on a tile, and
a mechanism never survives the tile under it being erased — the alternative is a
file that loads and then drops the marble through the floor.

    >>> editor = BoardEditor(blank(3, 3))
    >>> editor.lay((5, 5))
    True
    >>> (5, 5) in editor.level.cells
    True
    >>> editor.undo()
    True
    >>> (5, 5) in editor.level.cells
    False
"""
from __future__ import annotations

import copy
import dataclasses
from collections.abc import Callable
from typing import Any

from openglcontext_marble_demo import levelfile, mechanisms
from openglcontext_marble_demo.level import (
    CELL_SIZE,
    Bumper,
    Elevator,
    Finish,
    Level,
    Ramp,
    RotatingArm,
    SpringTrap,
    Wall,
)
from openglcontext_marble_demo.materials import SURFACES

__all__ = ['BoardEditor', 'blank', 'PLACEABLE', 'PLACEABLE_ORDER', 'SURFACE_NAMES',
           'HEIGHT_STEP', 'UNTITLED']

#: What a board is called before it has a file.
UNTITLED = 'Untitled'

#: How far one press of raise/lower moves a tile.  Matched to the game's slope
#: budget, so a single step is always something a marble can roll up or down and
#: a designer cannot build a wall by accident.
HEIGHT_STEP = 0.9

#: The pieces the board itself is built out of, in the order the palette offers
#: them, with what each is called on screen.  The classes come from the game and
#: the names from the file format, so the editor and the game can never disagree
#: about what a board holds.
BUILT_IN_ORDER = ('ramp', 'launch', 'wall', 'bumper', 'spring', 'elevator', 'arm')
BUILT_IN = {
    'ramp': ('Ramp', Ramp, {}),
    'launch': ('Launch ramp', Ramp, {'launch': True, 'rise': 1.0, 'boost_speed': 7.0}),
    'wall': ('Rail', Wall, {}),
    'bumper': ('Bumper', Bumper, {}),
    'spring': ('Spring', SpringTrap, {}),
    'elevator': ('Elevator', Elevator, {}),
    'arm': ('Rotating arm', RotatingArm, {}),
}


def placeable_mechanisms() -> dict:
    """Every registered mechanism the editor can put down with one click.

    Discovered rather than listed.  The game finds ``mechanisms/`` by scanning
    its own directory, so a new mechanism is a new file and nothing else; a
    palette that had to be edited as well would be exactly the shared file that
    design exists to avoid, and a mechanism nobody could place would be one
    only a generated board ever had.

    A mechanism that covers a *field* of cells rather than standing on one --
    sand, a burner -- is not here.  Placing one is a gesture that paints an area,
    and the tool that does that is a different tool from this one.
    """
    found: dict[str, tuple] = {}
    for name, factory in sorted(mechanisms.registry().items()):
        fields = {field.name for field in dataclasses.fields(factory)}
        if 'cell' in fields:
            found[name] = (factory.__name__, factory, {})
    return found


def _palette() -> tuple[tuple, dict]:
    """The order the palette offers, and what each entry puts down."""
    offered = dict(BUILT_IN)
    order = list(BUILT_IN_ORDER)
    for name, entry in placeable_mechanisms().items():
        if name not in offered:
            offered[name] = entry
            order.append(name)
    return tuple(order), offered


PLACEABLE_ORDER, PLACEABLE = _palette()

#: The surfaces a cell can be painted with; the first is "no override".
SURFACE_NAMES = ('stone', *sorted(name for name in SURFACES if name != 'stone'))

_SIDES = {(0, -1): 'N', (0, 1): 'S', (1, 0): 'E', (-1, 0): 'W'}
NEIGHBOURS = tuple(_SIDES)


def blank(width=5, depth=8, cell_size=CELL_SIZE):
    """A rectangle of flat tiles to start drawing on.

    A board with nothing in it is a board a designer cannot see, so a new one is
    a plain rectangle with a start at one end and a finish at the other: already
    playable, and every part of it something to change.
    """
    cells = {(col, row): 0.0
             for col in range(-(width // 2), width - width // 2)
             for row in range(depth)}
    start = (0, 0)
    finish = (0, depth - 1)
    return Level(name=UNTITLED, cells=cells, start_cell=start, finish_cell=finish,
                 time_limit=30.0, features=[Finish(finish)], cell_size=cell_size)


class BoardEditor:
    """A level, the changes that can be made to it, and its history."""

    #: How many steps back a designer can go.  A board is small; this is bounded
    #: because a session is hours long rather than because a step is expensive.
    HISTORY = 128

    def __init__(self, level: Level | None = None,
                 on_change: Callable[[], None] | None = None) -> None:
        self.level = level if level is not None else blank()
        self.on_change = on_change
        self.path: str | None = None
        #: Whether there are changes not in the file.
        self.modified = False
        self._past: list[dict] = []
        self._future: list[dict] = []
        self._step: dict | None = None

    # -- history ---------------------------------------------------------
    def begin_step(self) -> None:
        """Start one undoable step, however many changes go into it.

        A drag that paints twenty tiles is one thing the designer did.  Calling
        this again before :meth:`end_step` does nothing, so a tool can be honest
        about where its gesture starts without counting.
        """
        if self._step is None:
            self._step = self._snapshot()

    def end_step(self) -> None:
        """Finish the step, keeping it only if anything actually changed."""
        step, self._step = self._step, None
        if step is None:
            return
        if step == self._snapshot():
            return                          # a drag that touched nothing
        self._past.append(step)
        del self._past[:-self.HISTORY]
        self._future.clear()
        self.modified = True
        self._changed()

    def undo(self) -> bool:
        """Take back the last step.  False when there is none."""
        return self._travel(self._past, self._future)

    def redo(self) -> bool:
        """Do again what :meth:`undo` took back.  False when there is none."""
        return self._travel(self._future, self._past)

    def _travel(self, source: list, destination: list) -> bool:
        if not source:
            return False
        destination.append(self._snapshot())
        self._restore(source.pop())
        self.modified = True
        self._changed()
        return True

    def _snapshot(self) -> dict:
        return copy.deepcopy(levelfile.to_json(self.level))

    def _restore(self, document: dict) -> None:
        self.level = levelfile.from_json(document)

    def _changed(self) -> None:
        if self.on_change is not None:
            self.on_change()

    def _edit(self, work: Callable[[], bool]) -> bool:
        """Run ``work`` as a step of its own unless one is already open."""
        alone = self._step is None
        if alone:
            self.begin_step()
        changed = work()
        if alone:
            self.end_step()
        elif changed:
            self.modified = True
        return changed

    # -- tiles -----------------------------------------------------------
    def lay(self, cell: tuple) -> bool:
        """Put a tile at ``cell``, level with whatever it touches.

        A new tile takes the height of its neighbours rather than zero, so
        extending a board off the side of a terrace continues that terrace
        instead of dropping a step into it.
        """
        def work() -> bool:
            if cell in self.level.cells:
                return False
            self.level.cells[cell] = self._height_beside(cell)
            return True
        return self._edit(work)

    def erase(self, cell: tuple) -> bool:
        """Take the tile at ``cell`` away, and whatever was standing on it.

        The start and the finish are not erasable: a board without them is not a
        board, and the designer meant to move them rather than to lose them.
        """
        def work() -> bool:
            if cell not in self.level.cells:
                return False
            if cell in (self.level.start_cell, self.level.finish_cell):
                return False
            del self.level.cells[cell]
            self.level.cell_surfaces.pop(cell, None)
            # A mechanism over a hole is a mechanism the marble falls past.
            self.level.features = [feature for feature in self.level.features
                                   if getattr(feature, 'cell', None) != cell]
            return True
        return self._edit(work)

    def _height_beside(self, cell: tuple) -> float:
        heights = [self.level.cells[(cell[0] + dcol, cell[1] + drow)]
                   for dcol, drow in NEIGHBOURS
                   if (cell[0] + dcol, cell[1] + drow) in self.level.cells]
        return max(heights) if heights else 0.0

    def raise_by(self, cell: tuple, steps: int = 1,
                 step: float = HEIGHT_STEP) -> bool:
        """Move a tile up (or down, for a negative ``steps``) by whole steps."""
        def work() -> bool:
            if cell not in self.level.cells:
                return False
            self.level.cells[cell] = round(
                self.level.cells[cell] + steps * step, 6)
            return True
        return self._edit(work)

    def level_to(self, cell: tuple, height: float) -> bool:
        """Set a tile's height outright."""
        def work() -> bool:
            if cell not in self.level.cells or self.level.cells[cell] == height:
                return False
            self.level.cells[cell] = float(height)
            return True
        return self._edit(work)

    def paint(self, cell: tuple, surface: str) -> bool:
        """Give a tile a surface, or take its override away with ``'stone'``.

        ``stone`` is the board's own surface rather than a fourth material, so
        painting stone is how a designer undoes a patch.
        """
        def work() -> bool:
            if cell not in self.level.cells or surface not in SURFACES:
                return False
            if surface == self.level.surface:
                return self.level.cell_surfaces.pop(cell, None) is not None
            if self.level.cell_surfaces.get(cell) == surface:
                return False
            self.level.cell_surfaces[cell] = surface
            return True
        return self._edit(work)

    # -- mechanisms ------------------------------------------------------
    def place(self, cell: tuple, kind: str, **named: Any) -> bool:
        """Put a mechanism of ``kind`` on ``cell``, replacing what was there.

        One mechanism to a cell: two rotating arms on the same tile is not
        something a designer means, and the second would be invisible under the
        first.  A ramp points the way the board runs, and a rail faces the
        nearest void — both worked out here rather than asked for, because both
        are almost always what is wanted and both are then adjustable.
        """
        def work() -> bool:
            if cell not in self.level.cells or kind not in PLACEABLE:
                return False
            _, factory, fixed = PLACEABLE[kind]
            arguments = dict(fixed)
            arguments.update(self._defaults(cell, factory))
            arguments.update(named)
            self.clear(cell)
            self.level.features.append(factory(cell=cell, **arguments))
            return True
        return self._edit(work)

    def clear(self, cell: tuple) -> bool:
        """Take any mechanism off ``cell``, leaving the tile.

        The finish is not one of them: it moves with :meth:`set_finish` rather
        than being deleted, so a board never loses the thing that ends a run.
        """
        def work() -> bool:
            before = len(self.level.features)
            self.level.features = [
                feature for feature in self.level.features
                if getattr(feature, 'cell', None) != cell
                or isinstance(feature, Finish)]
            return len(self.level.features) != before
        return self._edit(work)

    def feature_at(self, cell: tuple) -> Any:
        """Whatever mechanism stands on ``cell``, or None."""
        for feature in self.level.features:
            if getattr(feature, 'cell', None) == cell \
                    and not isinstance(feature, Finish):
                return feature
        return None

    def _defaults(self, cell: tuple, factory: type) -> dict:
        if factory is Ramp:
            return {'direction': self._downhill(cell)}
        if factory is Wall:
            return {'side': self._void_side(cell)}
        return {}

    def _downhill(self, cell: tuple) -> tuple:
        """The neighbouring direction that drops the most, or straight on.

        A ramp put down by hand should point the way the marble is already
        going, and on a terraced board that is the way the board falls.
        """
        best, drop = (0, 1), 0.0
        here = self.level.cells[cell]
        # Forward first, and a tie keeps it: the board leans toward +row, so
        # where several sides fall equally the way the marble is already going
        # is the one a ramp should point.
        for dcol, drow in ((0, 1), *NEIGHBOURS):
            beside = (cell[0] + dcol, cell[1] + drow)
            if beside in self.level.cells and here - self.level.cells[beside] > drop:
                best, drop = (dcol, drow), here - self.level.cells[beside]
        return best

    def _void_side(self, cell: tuple) -> str:
        """The side of ``cell`` facing the void; the downhill side if enclosed."""
        for direction, name in _SIDES.items():
            beside = (cell[0] + direction[0], cell[1] + direction[1])
            if beside not in self.level.cells:
                return name
        return _SIDES[self._downhill(cell)]

    # -- the two markers -------------------------------------------------
    def set_start(self, cell: tuple) -> bool:
        """Move where a run begins.  Only onto a tile, and never onto the finish."""
        def work() -> bool:
            if cell not in self.level.cells or cell == self.level.finish_cell:
                return False
            if cell == self.level.start_cell:
                return False
            self.level.start_cell = cell
            self.clear(cell)
            return True
        return self._edit(work)

    def set_finish(self, cell: tuple) -> bool:
        """Move where a run ends, taking the pad with it."""
        def work() -> bool:
            if cell not in self.level.cells or cell == self.level.start_cell:
                return False
            if cell == self.level.finish_cell:
                return False
            self.level.finish_cell = cell
            self.level.features = [feature for feature in self.level.features
                                   if not isinstance(feature, Finish)]
            self.clear(cell)
            self.level.features.append(Finish(cell))
            return True
        return self._edit(work)

    # -- the whole board -------------------------------------------------
    def set_time_limit(self, seconds: float) -> bool:
        def work() -> bool:
            if self.level.time_limit == seconds:
                return False
            self.level.time_limit = float(seconds)
            return True
        return self._edit(work)

    def rename(self, name: str) -> bool:
        def work() -> bool:
            if self.level.name == name:
                return False
            self.level.name = name
            return True
        return self._edit(work)

    # -- what is wrong with it -------------------------------------------
    def problems(self) -> list:
        """What would stop this board being played, in words a designer reads.

        Reported rather than prevented: a board half-drawn is a normal thing to
        be looking at, and an editor that refused to let one exist would be
        fighting the designer for the whole of the middle of the work.
        """
        found = []
        level = self.level
        if level.start_cell not in level.cells:
            found.append('the start is not on a tile')
        if level.finish_cell not in level.cells:
            found.append('the finish is not on a tile')
        if not any(isinstance(feature, Finish) for feature in level.features):
            found.append('there is no finish pad')
        elif not self.finish_reachable():
            found.append('the finish cannot be reached from the start')
        if level.time_limit <= 0:
            found.append('the clock is empty')
        return found

    def finish_reachable(self) -> bool:
        """Whether a marble could get from the start to the finish over tiles."""
        from collections import deque
        cells = self.level.cells
        if self.level.start_cell not in cells:
            return False
        seen = {self.level.start_cell}
        queue = deque(seen)
        while queue:
            col, row = queue.popleft()
            for dcol, drow in NEIGHBOURS:
                beside = (col + dcol, row + drow)
                if beside in cells and beside not in seen:
                    seen.add(beside)
                    queue.append(beside)
        return self.level.finish_cell in seen

    def playable(self) -> bool:
        return not self.problems()

    # -- the file --------------------------------------------------------
    def save(self, path: str | None = None) -> str:
        target = path or self.path
        if not target:
            raise ValueError('a board with no file must be told where to go')
        levelfile.save(self.level, target)
        self.path = target
        self.modified = False
        self._changed()
        return target

    def open(self, path: str) -> None:
        """Load a board, forgetting the history of whatever was open before."""
        self.open_level(levelfile.load(path), path=path)

    def open_level(self, level: Level, path: str | None = None) -> None:
        """Start on a different board, forgetting the last one's history.

        Undoing across a New would put back half of one board inside another,
        which is not a state a designer ever meant to be in.
        """
        self.level = level
        self.path = path
        self.modified = False
        self._past.clear()
        self._future.clear()
        self._step = None
        self._changed()

    @property
    def title(self) -> str:
        """What to put in the window: the board's name, and whether it is saved."""
        return '%s%s' % (self.level.name or UNTITLED, '*' if self.modified else '')
