"""Turning what the pointer did into what the map and the tools should do.

The rule is the one every editor has: **the tool in force is asked first, and
what it does not want moves the map**. So a left drag with the tile tool lays
tiles, and a right drag over the same ground — which no tool here wants — pans.

Where the pointer *is* comes from the map rather than from the depth buffer. A
plan view knows exactly which square metre is under a pixel; a pick would answer
with whatever height happened to be drawn there, which is a different question
and a slower one. The board is flat in plan, so the world point is taken at
``y = 0`` and the tools turn it into a cell.

Separated from the window so it can be driven by a made-up event: the window is
GL and a window, and none of this is either.
"""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

import numpy as np
from OpenGLContext.edit.tools import Pointer, ToolManager

__all__ = ['MapControls', 'ZOOM_STEP', 'WHEEL_UP', 'WHEEL_DOWN']

#: What a wheel notch does to the scale.
ZOOM_STEP = 1.25

#: The wheel arrives as a pair of buttons, as it does everywhere in the engine.
WHEEL_UP, WHEEL_DOWN = 4, 3


class MapControls:
    """The pointer, over a map, driving a set of tools."""

    def __init__(self, view: Any, tools: ToolManager,
                 viewport: Callable[[], tuple[int, int]],
                 on_change: Callable[[], None] | None = None) -> None:
        self.view = view
        self.tools = tools
        #: Where the window's size comes from, asked each time: it changes.
        self.viewport = viewport
        #: Called when the map moved.
        self.on_change = on_change
        self._panning = False
        self._from = (0.0, 0.0)

    # -- where the pointer is ----------------------------------------------
    def pointer(self, event: Any) -> Pointer:
        """The pointer, on the screen and on the board."""
        x, y = event.getPickPoint()
        world_x, world_z = self.view.world_from_screen(x, y, self.viewport())
        return Pointer(x=float(x), y=float(y),
                       world=np.array([world_x, 0.0, world_z], dtype='d'),
                       button=int(getattr(event, 'button', 0)),
                       modifiers=tuple(event.getModifiers()))

    # -- what an event does ------------------------------------------------
    def button(self, event: Any) -> bool:
        """A button went down or came up.  True if the editor used it."""
        button = int(getattr(event, 'button', 0))
        down = bool(getattr(event, 'state', 0))
        if button in (WHEEL_UP, WHEEL_DOWN):
            if down:
                notches = 1 if button == WHEEL_UP else -1
                # The tool in force is asked first, as it is for every other
                # input, so a tool that wants the wheel can have it.
                if not self.tools.wheel(self.pointer(event), notches):
                    self.zoom(ZOOM_STEP if button == WHEEL_DOWN else 1.0 / ZOOM_STEP,
                              event.getPickPoint())
            return True
        pointer = self.pointer(event)
        if down:
            if self.tools.press(pointer):
                return True
            # Nothing the tools wanted, so the button moves the map.
            self._panning = True
            self._from = event.getPickPoint()
            return True
        was_panning, self._panning = self._panning, False
        took = bool(self.tools.release(pointer))
        return took or was_panning

    def moved(self, event: Any) -> bool:
        """The pointer moved.  True if the editor used it."""
        if self._panning:
            x, y = event.getPickPoint()
            self.view.pan(x - self._from[0], y - self._from[1], self.viewport())
            self._from = (x, y)
            self._moved()
            return True
        return bool(self.tools.move(self.pointer(event)))

    def key(self, name: str, modifiers: tuple) -> bool:
        return bool(self.tools.key(name, modifiers))

    # -- the map -----------------------------------------------------------
    def zoom(self, factor: float, at: tuple | None = None) -> None:
        """Zoom about a screen point, or about the middle when none is given."""
        self.view.zoom(factor, at=at, viewport=self.viewport())
        self._moved()

    def frame(self, minimum: tuple, maximum: tuple) -> None:
        """Fit a region of the board to the window."""
        self.view.frame(minimum, maximum, self.viewport())
        self._moved()

    def _moved(self) -> None:
        if self.on_change is not None:
            self.on_change()
