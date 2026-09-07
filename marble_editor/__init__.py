"""The marble board editor: draw a board, put mechanisms on it, and play it.

The editor is a **map**: the board from straight above, orthographic, so a cell
is the same number of pixels wherever it is.  A strip down the left says what
the pointer is for; the menus keep what applies to the whole board.

Nothing here knows what a board *is* — that comes from
``openglcontext_marble_demo``, so the editor and the game cannot disagree about
the format — and nothing but :mod:`marble_editor.app` knows there is a window.

    oglc-marble-editor                 # a blank board to draw on
    oglc-marble-editor spiral.marble   # carry on with one
"""

__version__ = "1.0.0a1"
