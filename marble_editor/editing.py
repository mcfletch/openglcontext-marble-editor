"""What the pointer does: one tool per kind of change, and nothing else in them.

Every tool here is a :class:`~OpenGLContext.edit.tools.ToolMode` over a
:class:`~marble_editor.board.BoardEditor`, and each is a handful of lines,
because the rules about what a board may be live in the editor and the gestures
live here. A tool that took a press keeps the pointer until the release, so a
drag that wanders off the board still ends where it should.

Two conventions run through all of them, and they are the ones a designer
already expects:

**Left does, right undoes.** Left lays a tile, right takes it away; left places
a mechanism, right clears it; left raises, right lowers. A designer never has to
find a different tool to correct what they just did with this one.

**A drag is one step.** Painting twenty tiles across a board is one thing that
happened and comes back in one press of undo, which is what
:meth:`~marble_editor.board.BoardEditor.begin_step` is for.

What a tool does not want goes to the camera — so the right button over open
space still pans, and the wheel still zooms, in every tool but the one that
takes it.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from OpenGLContext.edit.maptools import PanTool
from OpenGLContext.edit.tools import Pointer, ToolManager, ToolMode

from marble_editor.board import HEIGHT_STEP, PLACEABLE, PLACEABLE_ORDER, SURFACE_NAMES, BoardEditor

__all__ = ['TileTool', 'HeightTool', 'SurfaceTool', 'MechanismTool',
           'MarkerTool', 'editor_tools', 'LEFT', 'RIGHT']

#: The buttons, as the engine reports them.
LEFT, RIGHT = 0, 2


@dataclass
class _BoardTool(ToolMode):
    """Shared plumbing: a board to change, and a cell under the pointer."""

    editor: BoardEditor = None                      # type: ignore[assignment]
    #: Called after a gesture changes something, so the view can be rebuilt.
    on_change: Callable[[], None] | None = None
    _dragging: bool = field(default=False, repr=False)

    def cell(self, pointer: Pointer):
        """The cell under ``pointer``, or None where it is over nothing."""
        if pointer.world is None:
            return None
        size = self.editor.level.cell_size
        return (int(round(float(pointer.world[0]) / size)),
                int(round(float(pointer.world[2]) / size)))

    # -- the gesture -------------------------------------------------------
    def on_press(self, pointer: Pointer) -> bool:
        if pointer.button not in (LEFT, RIGHT) or self.cell(pointer) is None:
            return False
        self.editor.begin_step()
        self._dragging = True
        self.apply(self.cell(pointer), pointer)
        self._changed()
        return True

    def on_drag(self, pointer: Pointer) -> bool:
        if not self._dragging:
            return False
        cell = self.cell(pointer)
        if cell is not None:
            self.apply(cell, pointer)
            self._changed()
        return True

    def on_release(self, pointer: Pointer) -> bool:
        if not self._dragging:
            return False
        self._dragging = False
        self.editor.end_step()
        self._changed()
        return True

    def cancel(self) -> None:
        if self._dragging:
            self._dragging = False
            self.editor.end_step()
            self.editor.undo()
            self._changed()

    def undo(self) -> bool:
        return self.editor.undo()

    def redo(self) -> bool:
        return self.editor.redo()

    def _changed(self) -> None:
        if self.on_change is not None:
            self.on_change()

    # -- what this tool actually does --------------------------------------
    def apply(self, cell, pointer: Pointer) -> bool:
        """Change ``cell``.  Overridden by every tool."""
        return False


@dataclass
class TileTool(_BoardTool):
    """Lay tiles and take them away: the shape of the board itself."""

    name: str = 'tiles'
    label: str = 'Tiles'
    shortcut: str = 't'

    def apply(self, cell, pointer: Pointer) -> bool:
        if pointer.button == RIGHT:
            return self.editor.erase(cell)
        return self.editor.lay(cell)


@dataclass
class HeightTool(_BoardTool):
    """Raise and lower tiles, in the steps a marble can roll.

    A drag holds the height it started at rather than adding a step per cell it
    crosses, so dragging across a terrace *levels* it: pressing on the height
    you want and pulling it along is how a designer says "this much, over here",
    and a tool that added a step per cell would make a staircase instead.
    """

    name: str = 'height'
    label: str = 'Height'
    shortcut: str = 'h'
    _target: float | None = field(default=None, repr=False)

    def on_press(self, pointer: Pointer) -> bool:
        cell = self.cell(pointer)
        if cell is None or cell not in self.editor.level.cells:
            self._target = None
            return super().on_press(pointer)
        steps = -1 if pointer.button == RIGHT else 1
        self._target = round(
            self.editor.level.cells[cell] + steps * HEIGHT_STEP, 6)
        return super().on_press(pointer)

    def apply(self, cell, pointer: Pointer) -> bool:
        if self._target is None:
            return False
        return self.editor.level_to(cell, self._target)


@dataclass
class SurfaceTool(_BoardTool):
    """Paint a tile's material: ice to slide on, rubber to grip, metal between.

    The surface is the tool's own state rather than a separate choice, so the
    palette and the keys 1..4 say what is being painted and the pointer does it.
    Right-click paints the board's own surface, which is how a patch is removed.
    """

    name: str = 'surface'
    label: str = 'Surface'
    shortcut: str = 'u'
    surface: str = SURFACE_NAMES[1] if len(SURFACE_NAMES) > 1 else SURFACE_NAMES[0]

    def apply(self, cell, pointer: Pointer) -> bool:
        wanted = self.editor.level.surface if pointer.button == RIGHT else self.surface
        return self.editor.paint(cell, wanted)

    def on_key(self, name: str, modifiers) -> bool:
        """1..n choose which surface the pointer paints."""
        if name.isdigit() and 1 <= int(name) <= len(SURFACE_NAMES):
            self.surface = SURFACE_NAMES[int(name) - 1]
            self._changed()
            return True
        return False


@dataclass
class MechanismTool(_BoardTool):
    """Put ramps, rails, bumpers, springs, elevators and arms on the board.

    Which one is the tool's state, chosen from the palette or with the number
    keys, because a designer places a run of the same thing and then changes
    their mind once.  A ramp arrives pointing downhill and a rail facing the
    void — the board knows both — so placing one is a click rather than a form.
    """

    name: str = 'mechanisms'
    label: str = 'Pieces'
    shortcut: str = 'm'
    kind: str = PLACEABLE_ORDER[0]

    def apply(self, cell, pointer: Pointer) -> bool:
        if pointer.button == RIGHT:
            return self.editor.clear(cell)
        return self.editor.place(cell, self.kind)

    def on_key(self, name: str, modifiers) -> bool:
        if name.isdigit() and 1 <= int(name) <= len(PLACEABLE_ORDER):
            self.kind = PLACEABLE_ORDER[int(name) - 1]
            self._changed()
            return True
        return False

    @property
    def kind_label(self) -> str:
        return str(PLACEABLE[self.kind][0])


@dataclass
class MarkerTool(_BoardTool):
    """Say where a run begins and where it ends.

    Left sets the start, right the finish: the two ends of a run on the two ends
    of the mouse, which is one fewer thing to choose than a tool apiece.  It is
    a click rather than a drag — there is one start, and dragging it across the
    board would leave it wherever the pointer happened to be let go.
    """

    name: str = 'markers'
    label: str = 'Markers'
    shortcut: str = 'k'

    def apply(self, cell, pointer: Pointer) -> bool:
        if pointer.button == RIGHT:
            return self.editor.set_finish(cell)
        return self.editor.set_start(cell)

    def on_drag(self, pointer: Pointer) -> bool:
        return True                 # took the gesture; a marker does not smear


def editor_tools(editor: BoardEditor, view: Any,
                 viewport: Callable[[], tuple[int, int]],
                 on_change: Callable[[], None] | None = None,
                 on_tool: Callable[[Any], None] | None = None) -> ToolManager:
    """The tools the editor offers, in the order the palette draws them.

    Tiles first, because the shape of the board is what a designer starts with
    and what the pointer is for until they say otherwise.  Moving the map is a
    tool of its own as well as the thing that happens to whatever the tool in
    force left alone: a designer working close in wants to say "just move the
    map" and have the board stop gaining tiles where they meant to drag.
    """
    tools = [TileTool(editor=editor, on_change=on_change),
             HeightTool(editor=editor, on_change=on_change),
             SurfaceTool(editor=editor, on_change=on_change),
             MechanismTool(editor=editor, on_change=on_change),
             MarkerTool(editor=editor, on_change=on_change),
             PanTool(view, viewport, on_change=on_change)]
    return ToolManager(tools, on_change=on_tool)
