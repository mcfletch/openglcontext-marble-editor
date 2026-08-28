"""Composing a whole board in the editor, so a designer starts from something.

The Story menu adds a chapter at a time; this is the other end of the same job.
**Board → Generate** replaces what is open with a board composed out of the
library — a chain of places and challenges with a rhythm to it, several surfaces,
and somewhere to end up when you get something wrong.

And then it is an ordinary board. One press of undo takes the whole thing back,
every tile is editable, chapters can be added to the end of it, and it saves like
any other. That is the point: a generated board nobody can change is somebody
else's board, and the reason to generate one inside an editor rather than in a
game is that the designer gets to disagree with it.

What decides *what* is on it is
:func:`openglcontext_marble_demo.storygen.compose`, and what it holds is the
library — so a fragment added to the game turns up in generated boards without
the editor being told.

    >>> from marble_editor.board import BoardEditor, blank
    >>> editor = BoardEditor(blank())
    >>> generate_story(editor, seed=1, chapters=6)
    True
    >>> editor.problems()
    []
"""
from __future__ import annotations

from typing import Any

from openglcontext_marble_demo import storygen
from openglcontext_marble_demo.pieces import THEMES

__all__ = ['generate_story', 'CHAPTER_COUNTS', 'DIFFICULTIES']

#: The lengths the menu offers.  A ladder rather than a number to type: what a
#: designer is choosing is how long a run should be, and the useful answers for
#: a board of this kind are a handful.
CHAPTER_COUNTS = (4, 6, 8, 12, 16)

#: The difficulties the menu offers, which are ceilings on what may appear.
DIFFICULTIES = (1, 2, 3, 4, 5)


def generate_story(editor: Any, seed: int = 0, chapters: int = 8,
                   difficulty: int = 3, themed: bool = True) -> bool:
    """Replace ``editor``'s board with one composed from the library.

    One undoable step, because it is one thing the designer did — and undoable
    at all, which is why the board is put into the editor's own level rather
    than handed to it as a new one: a New forgets the history, and this must not.
    """
    if chapters < 1:
        raise ValueError('a board of %d chapters is not a board' % chapters)
    story = storygen.compose(seed, chapters=chapters, difficulty=difficulty,
                             themes=sorted(THEMES) if themed else None)
    told = story.build(seed)
    level = told.level(name=story.name)

    editor.begin_step()
    try:
        _adopt(editor.level, level)
    finally:
        editor.end_step()
    return True


def _adopt(target: Any, made: Any) -> None:
    """Put everything of ``made`` into ``target``, in place.

    In place because the editor's history holds snapshots of the level it was
    given, and swapping the object out would leave undo pointing at a board
    nothing is showing.
    """
    target.name = made.name
    target.cells.clear()
    target.cells.update(made.cells)
    target.cell_surfaces.clear()
    target.cell_surfaces.update(made.cell_surfaces)
    target.features = list(made.features)
    target.start_cell = made.start_cell
    target.finish_cell = made.finish_cell
    target.time_limit = made.time_limit
