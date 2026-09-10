"""A board drawn as a map: what a designer looks at while editing it.

The editor's window is a plan view, so this is not the board as the game renders
it — it is the board as a **drawing**. Everything is unlit and flat-coloured,
because a map is read rather than admired, and shading a plan view hides exactly
the differences it exists to show.

Three things have to be legible at a glance, and each gets its own answer:

**How high a tile is.** Lightness. A terrace steps up and the tiles get paler,
so the fall of the board is visible without a number on every cell.

**What a tile is made of.** Hue, taken from the game's own material table, so
ice on the map is the ice colour in the game.

**What is standing on it.** A mark in the middle of the cell, one shape and
colour per mechanism, with a tick along the direction anything directional
points. The marks are drawn above the tiles rather than on them, so a mechanism
on a low tile is not hidden by a high one beside it.

Faces are grouped by the colour they are drawn in rather than carrying a colour
each: the renderer takes a colour from an appearance, so one shape per colour is
a handful of shapes for a whole board where a colour per vertex would be a
colour the PBR path does not read.

Building a scene touches no GL — it is nodes — so what a board looks like is
something a test can ask about.
"""
from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import numpy as np
from OpenGLContext.scenegraph.basenodes import (
    Appearance,
    Background,
    Coordinate,
    Group,
    IndexedFaceSet,
    IndexedLineSet,
    Shape,
)
from OpenGLContext.scenegraph.pbrmaterial import PBRMaterial
from OpenGLContext.scenegraph.scenegraph import SceneGraph
from openglcontext_marble_demo.level import (
    Bumper,
    Elevator,
    Finish,
    Ramp,
    RotatingArm,
    SpringTrap,
    Wall,
)
from openglcontext_marble_demo.materials import SURFACES

__all__ = ['board_scene', 'tiles', 'marks', 'grid', 'MARK_COLOURS',
           'START_COLOUR', 'FINISH_COLOUR', 'BACKGROUND']

#: The map's own colours.  The ground the board floats over is dark, so the
#: board's edge is where the drawing stops rather than something to look for.
BACKGROUND = (0.10, 0.11, 0.14)
GRID_COLOUR = (0.32, 0.34, 0.40)
START_COLOUR = (0.30, 0.75, 1.00)
FINISH_COLOUR = (0.20, 0.95, 0.50)

#: One colour per mechanism, matched to what the game draws it as, so a board
#: read on the map and a board played look like the same board.
MARK_COLOURS = {
    Ramp: (0.55, 0.60, 0.68),
    Wall: (0.40, 0.41, 0.45),
    Bumper: (0.90, 0.20, 0.30),
    SpringTrap: (0.95, 0.85, 0.20),
    Elevator: (0.30, 0.70, 0.85),
    RotatingArm: (0.90, 0.60, 0.15),
    Finish: FINISH_COLOUR,
}
#: A launch ramp is a ramp that does something else, and is coloured as one.
LAUNCH_COLOUR = (0.85, 0.45, 0.20)

#: How far a mark is drawn above the tile it is on, and the grid above that.
#: Enough to clear a terrace step, so nothing is buried by the tile next to it.
MARK_LIFT = 4.0
GRID_LIFT = 3.0

#: How much of a cell a mark takes up, and how far a direction tick runs.
MARK_SIZE = 0.42
TICK_LENGTH = 0.46

#: Lightness given to the highest terrace and to the lowest.  The range is
#: generous because reading the fall of a board is most of reading a board.
LIGHT_HIGH = 1.35
LIGHT_LOW = 0.55


def _unlit(color: Sequence[float]) -> Appearance:
    """An appearance that draws exactly the colour it is given."""
    return Appearance(material=PBRMaterial(
        baseColor=tuple(color), emissiveColor=tuple(color),
        metallic=0.0, roughness=1.0, unlit=True))


def _shade(color: Sequence[float], height: float, lowest: float,
           highest: float) -> tuple[float, ...]:
    """``color`` lightened toward the top of the board and darkened toward the
    bottom, so a terrace reads as a terrace."""
    span = highest - lowest
    where = 0.5 if span < 1e-9 else (height - lowest) / span
    scale = LIGHT_LOW + (LIGHT_HIGH - LIGHT_LOW) * where
    return tuple(min(1.0, channel * scale) for channel in color)


class _Faces:
    """Faces being collected, kept apart by the colour they are drawn in.

    One shape per colour rather than one per cell: a board is a few materials
    over a few terraces, so this is a handful of shapes however many tiles there
    are, and each is flat-coloured by its own appearance -- which is where the
    renderer takes a colour from.
    """

    def __init__(self) -> None:
        self.by_colour: dict = {}

    def add(self, colour: Sequence[float],
            corners: Sequence[Any]) -> None:
        points, index = self.by_colour.setdefault(_key(colour), ([], []))
        at = len(points)
        points.extend(corners)
        index.extend(list(range(at, at + len(corners))) + [-1])

    def group(self) -> Group | None:
        children = [
            Shape(geometry=IndexedFaceSet(coord=Coordinate(point=points),
                                          coordIndex=index, solid=False),
                  appearance=_unlit(colour))
            for colour, (points, index) in sorted(self.by_colour.items())]
        return Group(children=children) if children else None


def _key(colour: Sequence[float]) -> tuple[float, ...]:
    """A colour rounded to what an eye can tell apart, so near-identical
    shades share a shape instead of each getting one."""
    return tuple(round(float(channel), 3) for channel in colour)


def tiles(level: Any) -> Group | None:
    """One flat quad per cell, coloured by surface and shaded by height."""
    if not level.cells:
        return None
    size = level.cell_size
    heights = list(level.cells.values())
    lowest, highest = min(heights), max(heights)
    faces = _Faces()
    half = size * 0.5 - size * 0.03            # a hairline gap, so cells read apart
    for (col, row), height in sorted(level.cells.items()):
        x, z = col * size, row * size
        base = SURFACES[level.surface_of((col, row))].base_color
        faces.add(_shade(base, height, lowest, highest),
                  [(x - half, height, z - half), (x + half, height, z - half),
                   (x + half, height, z + half), (x - half, height, z + half)])
    return faces.group()


def grid(level: Any) -> Shape | None:
    """A line round every cell, so the squares a designer clicks are visible."""
    if not level.cells:
        return None
    size = level.cell_size
    half = size * 0.5
    points: list = []
    index: list = []
    for (col, row), height in sorted(level.cells.items()):
        x, z = col * size, row * size
        y = height + GRID_LIFT
        at = len(points)
        points.extend([(x - half, y, z - half), (x + half, y, z - half),
                       (x + half, y, z + half), (x - half, y, z + half)])
        index.extend([at, at + 1, at + 2, at + 3, at, -1])
    return Shape(geometry=IndexedLineSet(coord=Coordinate(point=points),
                                         coordIndex=index, color=None),
                 appearance=_unlit(GRID_COLOUR))


def _diamond(faces: _Faces, x: float, z: float, y: float, radius: float,
             colour: Sequence[float]) -> None:
    faces.add(colour, [(x, y, z - radius), (x + radius, y, z),
                       (x, y, z + radius), (x - radius, y, z)])


def marks(level: Any) -> Group | None:
    """A mark per mechanism, and one each for the start and the finish."""
    size = level.cell_size
    radius = size * MARK_SIZE
    faces = _Faces()

    for feature in level.features:
        cell = getattr(feature, 'cell', None)
        if cell is None or cell not in level.cells:
            continue
        colour = MARK_COLOURS.get(type(feature), (1.0, 0.0, 1.0))
        if isinstance(feature, Ramp) and feature.launch:
            colour = LAUNCH_COLOUR
        x, z = cell[0] * size, cell[1] * size
        y = level.cells[cell] + MARK_LIFT
        if isinstance(feature, Wall):
            _rail(faces, feature, x, z, y, size, colour)
        else:
            _diamond(faces, x, z, y, radius * 0.6, colour)
        direction = getattr(feature, 'direction', None)
        if direction is not None:
            _tick(faces, x, z, y, direction, size, colour)

    for cell, colour in ((level.start_cell, START_COLOUR),
                         (level.finish_cell, FINISH_COLOUR)):
        if cell in level.cells:
            _diamond(faces, cell[0] * size, cell[1] * size,
                     level.cells[cell] + MARK_LIFT, radius, colour)
    return faces.group()


def _rail(faces: _Faces, wall: Any, x: float, z: float, y: float,
          size: float, colour: Sequence[float]) -> None:
    """A rail is drawn where it stands: a bar along one edge of the cell."""
    dcol, drow = Wall._OFFSET[wall.side]
    half = size * 0.5
    thick = size * 0.10
    centre_x, centre_z = x + dcol * half, z + drow * half
    along_x = half if drow else thick
    along_z = half if dcol else thick
    faces.add(colour, [(centre_x - along_x, y, centre_z - along_z),
                       (centre_x + along_x, y, centre_z - along_z),
                       (centre_x + along_x, y, centre_z + along_z),
                       (centre_x - along_x, y, centre_z + along_z)])


def _tick(faces: _Faces, x: float, z: float, y: float, direction: Any,
          size: float, colour: Sequence[float]) -> None:
    """A stub along the way something points, so a ramp's direction is visible."""
    step = np.array([direction[0], 0.0, direction[1]], dtype='d')
    length = np.linalg.norm(step)
    if length < 1e-9:
        return
    step = step / length * size * TICK_LENGTH
    across = np.array([-step[2], 0.0, step[0]]) * 0.18
    faces.add(colour, [(x + across[0], y, z + across[2]),
                       (x + step[0], y, z + step[2]),
                       (x - across[0], y, z - across[2])])


def board_scene(level: Any,
                background: Sequence[float] = BACKGROUND) -> SceneGraph:
    """The whole map: tiles, the grid over them, and the marks over that.

    A ``Background`` node leads the children, which is how a scene says what
    the frame is cleared to: the ground the board floats over is dark, so the
    board's edge is where the drawing stops rather than something to look for.
    """
    children: list[Any] = [Background(skyColor=[tuple(background)])]
    children.extend(shape for shape in
                    (tiles(level), grid(level), marks(level))
                    if shape is not None)
    return SceneGraph(children=children)
