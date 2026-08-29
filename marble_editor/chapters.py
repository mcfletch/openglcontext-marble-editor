"""Adding a chapter from the game's library to a board being edited.

The tile tools draw a board one square at a time, which is right for the last
tenth of the work and wrong for the first nine. A **chapter** is the other end of
the same job: choose something out of the library and it is appended to what is
already there — entered where the board currently ends, leaving somewhere new,
bringing its own walls, mechanisms and surfaces — and then the tile tools are
there to change it.

A **story** is several of those at once, composed rather than picked: a run with
a rhythm to it, getting harder as it goes, with a way round something in the
middle. :func:`add_story` puts one on the end of the board the same way
:func:`add_chapter` puts one chapter there, which is what makes the library
something to build a board *out of* rather than only something to start from.
Board → Generate replaces what is open; this adds to it.

Which is the whole argument for putting the library in an editor rather than in a
generator. A generated board is somebody else's board; a board with three
chapters in it and an hour of tile edits on top is the designer's.

Nothing here decides *what* a chapter is. The library
(:mod:`openglcontext_marble_demo.fragments`) holds the fragments and their
variants, and it is discovered by scanning its own directory — so a fragment
added to the game is offered here without the editor being told about it.

    >>> from marble_editor.board import BoardEditor, blank
    >>> editor = BoardEditor(blank())
    >>> add_chapter(editor, 'plateau')
    True
"""
from __future__ import annotations

import random
from typing import Any

from openglcontext_marble_demo import fragments, pieces, storygen
from openglcontext_marble_demo.level import Finish

__all__ = ['CHAPTERS', 'STORY_LENGTHS', 'THEME_NAMES', 'entry_port',
           'add_chapter', 'add_story']

#: The lengths of run the menu offers to put on the end of a board.  Shorter than
#: the ladder Board -> Generate offers, because this one adds to what is there:
#: a designer reaching for it has a board already and wants a stretch more of it.
STORY_LENGTHS = (3, 4, 6, 8)

#: The materials a chapter can be asked for, in the order the menu offers them.
#: A theme is a floor material, a wall material and a sound name together, so
#: choosing one is choosing what the room is made of rather than recolouring it.
THEME_NAMES = tuple(sorted(pieces.THEMES))


def CHAPTERS() -> dict:
    """What the library holds, by name — the menu the editor offers."""
    return dict(fragments.library())


def entry_port(level: Any) -> pieces.Port:
    """Where the next chapter attaches: the end of the board, facing outward.

    The finish is where a board currently ends, so that is where the next
    chapter begins, and the facing is the way the board runs out — laid the
    other way a chapter would be laid on top of the board it came from.
    """
    cell = level.finish_cell
    height = level.cells.get(cell, 0.0)
    return pieces.Port(cell=cell, facing=_outward(level, cell), height=height,
                       width=pieces.LANE)


def _outward(level: Any, cell: tuple) -> tuple:
    """The way the board runs out from ``cell``.

    Whichever of the four directions has least board behind it, so a chapter
    goes where there is room.  Downhill (+row) breaks a tie, because that is the
    way the board leans and the way a player is already going.
    """
    def behind(step):
        return sum(1 for reach in range(1, 5)
                   if (cell[0] + step[0] * reach,
                       cell[1] + step[1] * reach) in level.cells)
    ways = [(0, 1), (1, 0), (-1, 0), (0, -1)]
    return min(ways, key=lambda step: (behind(step), ways.index(step)))


def add_chapter(editor: Any, name: str, variant: str | None = None,
                theme: str | None = None, seed: int | None = None) -> bool:
    """Append the fragment ``name`` to ``editor``'s board; return whether it grew.

    One undoable step, however many tiles the chapter lays: it is one thing the
    designer did.  The finish moves to the end of what was added, because a board
    that still ended where it used to would have the new chapter hanging off the
    far side of the pad.
    """
    port = entry_port(editor.level)
    rng = random.Random(seed if seed is not None else editor_seed(editor))
    piece = fragments.build(name, rng, port, variant=variant)
    if theme is not None:
        piece.theme = theme

    editor.begin_step()
    try:
        standing = len(editor.level.features)
        _lay(editor, piece)
        _open_the_joins(editor.level, standing)
    finally:
        editor.end_step()
    return True


def add_story(editor: Any, seed: int | None = None, chapters: int = 4,
              difficulty: int = 3, themed: bool = True) -> bool:
    """Append a whole composed run of chapters to ``editor``'s board.

    Entered where the board ends, exactly as one chapter is, and one undoable
    step however many chapters it lays: it is one thing the designer did.

    ``storygen`` decides what is in it -- places and challenges alternating, the
    cheap ones first, a run-up in front of anything that has to be arrived at
    fast, and a way round one of them.  What comes back is laid cell by cell
    like anything else, so every tile of it is then editable.
    """
    if chapters < 1:
        raise ValueError('a story of %d chapters is not a story' % chapters)
    seed = editor_seed(editor) if seed is None else seed
    story = storygen.compose(seed, chapters=chapters, difficulty=difficulty,
                             themes=list(THEME_NAMES) if themed else None)
    told = story.build(seed, entry=entry_port(editor.level))

    editor.begin_step()
    try:
        standing = len(editor.level.features)
        for piece in told.placed.values():
            _lay(editor, piece)
        # The connectors a story lays between chapters belong to no piece, and
        # a board without them has a one-cell hole wherever a branch rejoined.
        for cell, height in told.cells.items():
            editor.level.cells.setdefault(cell, height)
        _open_the_joins(editor.level, standing)
        _finish_at(editor.level, told.finish)
    finally:
        editor.end_step()
    return True


def _open_the_joins(level: Any, standing: int) -> None:
    """Drop the walls just laid that turned out to stand between two floors.

    A piece walls its own edge against the cells *it* knows about, and the piece
    laid next to it comes afterwards -- so a wall that faced the void when it was
    placed ends up across the way on.  Every board the game builds is finished
    this way; a board assembled in the editor needs it for the same reason.

    ``standing`` is how many features the board had before this step, and only
    what came after it is considered: a wall the designer put down between two
    of their own tiles is a wall they meant, and an editor that quietly removed
    it would be an editor that cannot draw a rail.
    """
    laid = level.features[standing:]
    level.features[standing:] = pieces.open_the_joins(level.cells, laid)


def editor_seed(editor: Any) -> int:
    """A seed that moves on as a board grows, so two chapters differ.

    From the board rather than from a counter: an editor reopened on a saved
    board carries on from where it was, and a chapter added to the same board
    twice is the same chapter.
    """
    return len(editor.level.cells) * 7919 + len(editor.level.features)


def _lay(editor: Any, piece: Any) -> None:
    """Put a built piece into the level the editor is holding."""
    level = editor.level
    theme = pieces.THEMES[piece.theme]
    for cell, height in piece.cells.items():
        level.cells[cell] = height
        level.cell_surfaces[cell] = theme.floor
    for feature in piece.features:
        if isinstance(feature, Finish):
            continue                      # the board has one, and it is moving
        level.features.append(_themed(feature, theme))
    _finish_at(level, piece.exit.cell)


def _finish_at(level: Any, cell: tuple) -> None:
    """Move the board's finish to ``cell``, taking the old pad with it.

    A board that still ended where it used to would have the new work hanging
    off the far side of the pad.
    """
    level.features = [feature for feature in level.features
                      if not isinstance(feature, Finish)]
    level.finish_cell = cell
    level.features.append(Finish(cell))


def _themed(feature: Any, theme: Any) -> Any:
    """A wall in the theme's material; anything else as it came."""
    from openglcontext_marble_demo.level import Wall
    if not isinstance(feature, Wall):
        return feature
    return Wall(cell=feature.cell, side=feature.side, height=feature.height,
                thickness=feature.thickness, material=theme.wall)
