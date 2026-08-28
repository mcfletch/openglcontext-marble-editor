"""What the editor tells the designer, and where on the screen it goes.

Five read-outs, and each answers a question that is otherwise a guess: which
board this is and whether it is saved; how big it is and how long the clock is,
because those are what a board is judged on; whether it can be played at all;
which tool has the pointer and what that tool is set to; and whatever just
happened.

The **playable** line is the one worth having. A board half-drawn is a normal
thing to be looking at, so nothing here stops a designer making one — but "the
finish cannot be reached from the start" is not something to find out by
playing, and a designer who has just cut the board in two should be told before
they cut it in three.
"""
from __future__ import annotations

from typing import Any

from OpenGLContext.ui.hudwidgets import HUDGroup, HUDLayer, Readout

__all__ = ['EditorStatus', 'NOTE_COLUMNS', 'READY']

#: The most characters the note takes.  It sits at one end of the bottom of the
#: window and the tool read-out at the other, and a message with no bound -- a
#: path, a list of problems -- runs across and through it.
NOTE_COLUMNS = 64

#: What the check says when there is nothing wrong.
READY = 'playable'


class EditorStatus(HUDLayer):
    """The editor's read-outs.  Call :meth:`show` when something changes."""

    def __init__(self, **named: Any) -> None:
        super().__init__(**named)
        self.title = Readout(label='BOARD')
        self.size = Readout(label='TILES')
        self.clock = Readout(label='CLOCK')
        self.check = Readout(label='STATE')
        self.tool = Readout(anchor='bottom-left', label='TOOL')
        self.note = Readout(anchor='bottom-right', align='right', value='',
                            maximumColumns=NOTE_COLUMNS)
        # One block in the corner: anchored separately they would each take the
        # same corner and be drawn over one another.
        self.corner = HUDGroup(anchor='top-left',
                               children=[self.title, self.size, self.clock,
                                         self.check])
        self.children = [self.corner, self.tool, self.note]

    @property
    def message(self) -> str:
        """The last thing that happened, shown until the next thing does."""
        return str(self.note.value)

    @message.setter
    def message(self, text: str) -> None:
        self.note.value = str(text)

    def show(self, title: str = '', tiles: int = 0, clock: float = 0.0,
             problems: Any = (), tool: str = '') -> None:
        """Put the board's state on screen.

        ``problems`` is what :meth:`~marble_editor.board.BoardEditor.problems`
        answered: the first one is shown, because a designer fixes them one at a
        time and a list of four across the corner of the window is a wall.
        """
        problems = list(problems)
        self.title.value = title
        self.size.value = '%d' % tiles
        self.clock.value = '%.0fs' % clock
        self.check.value = problems[0] if problems else READY
        self.tool.value = tool
