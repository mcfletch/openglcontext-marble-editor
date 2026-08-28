"""The window's own arithmetic, and the ways into it.

Almost all of :mod:`marble_editor.app` is a window and is not testable without
one; what *is* testable is what does not need one -- how a board is fitted to
the view, and which board the editor opens on.
"""
import pytest
from openglcontext_marble_demo import levelfile

from marble_editor import app
from marble_editor.board import blank


def _arguments(**named):
    named.setdefault('board', None)
    named.setdefault('seed', None)
    named.setdefault('difficulty', 2)
    return type('Arguments', (), named)


# -- fitting the board to the window -------------------------------------------

def test_the_bounds_hold_the_whole_board():
    level = blank(width=5, depth=8)
    (left, near), (right, far) = app.board_bounds(level)
    size = level.cell_size
    assert left < min(col for col, _ in level.cells) * size
    assert right > max(col for col, _ in level.cells) * size
    assert near < min(row for _, row in level.cells) * size
    assert far > max(row for _, row in level.cells) * size


def test_there_is_room_left_round_the_outside():
    """A board drawn to the window's edge looks like one that runs off it."""
    level = blank(width=3, depth=3)
    (left, _), (right, _) = app.board_bounds(level, margin=0.5)
    tight = app.board_bounds(level, margin=0.0)
    assert left < tight[0][0] and right > tight[1][0]


def test_a_board_with_no_tiles_still_has_bounds_to_look_at():
    level = blank(width=1, depth=1)
    level.cells.clear()
    (left, _), (right, _) = app.board_bounds(level)
    assert right > left


# -- which board the editor opens on -------------------------------------------

def test_with_nothing_asked_for_the_editor_opens_a_blank_board():
    level, path = app.starting_level(_arguments())
    assert path is None
    assert level.cells


def test_a_seed_opens_a_generated_board():
    level, path = app.starting_level(_arguments(seed=7))
    assert path is None
    assert level.seed == 7


def test_a_named_file_is_opened_and_remembered(tmp_path):
    target = str(tmp_path / 'board.marble')
    levelfile.save(blank(width=3, depth=4), target)
    level, path = app.starting_level(_arguments(board=target))
    assert path == target
    assert len(level.cells) == 12


def test_a_named_file_that_is_not_there_is_an_error_rather_than_a_blank_board():
    """A designer who mistyped a name wants to know rather than to start again
    by accident."""
    with pytest.raises(OSError):
        app.starting_level(_arguments(board='/nowhere/at/all.marble'))


def test_main_reports_a_missing_file_rather_than_opening_a_window(capsys):
    assert app.main(['/nowhere/at/all.marble']) == 1
    assert 'at/all.marble' in capsys.readouterr().err
