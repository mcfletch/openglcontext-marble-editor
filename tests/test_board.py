"""Every change a designer can make to a board, and taking it back.

:class:`~marble_editor.board.BoardEditor` is the only thing that changes a
level, so this is where the editor's rules are held: what a board may be, what
it may not become by accident, and what one press of undo has to give back.
"""
import dataclasses

import pytest
from openglcontext_marble_demo import mechanisms
from openglcontext_marble_demo.level import Bumper, Finish, Ramp, RotatingArm, Wall

from marble_editor.board import (
    BUILT_IN_ORDER,
    HEIGHT_STEP,
    PLACEABLE,
    PLACEABLE_ORDER,
    BoardEditor,
    blank,
    placeable_mechanisms,
)


def _editor(**named):
    return BoardEditor(blank(**named))


# -- a board to start on -------------------------------------------------------

def test_a_new_board_is_already_playable():
    """Nothing to set up before a designer can see what they are making."""
    editor = _editor()
    assert editor.problems() == []
    assert editor.playable()


def test_a_new_board_runs_from_its_start_to_its_finish():
    level = _editor(width=5, depth=8).level
    assert level.start_cell in level.cells
    assert level.finish_cell in level.cells
    assert level.finish_cell[1] > level.start_cell[1]


# -- tiles ---------------------------------------------------------------------

def test_laying_a_tile_puts_one_where_there_was_none():
    editor = _editor()
    assert editor.lay((9, 9))
    assert (9, 9) in editor.level.cells


def test_laying_a_tile_where_one_is_changes_nothing():
    editor = _editor()
    assert not editor.lay(editor.level.start_cell)


def test_a_new_tile_arrives_level_with_what_it_touches():
    """Extending a terrace continues it rather than dropping a step into it."""
    editor = _editor(width=3, depth=3)
    editor.raise_by((1, 1), 2)
    editor.lay((2, 1))
    assert editor.level.cells[(2, 1)] == editor.level.cells[(1, 1)]


def test_erasing_a_tile_takes_it_away():
    editor = _editor()
    assert editor.erase((1, 3))
    assert (1, 3) not in editor.level.cells


def test_erasing_takes_whatever_stood_on_the_tile_with_it():
    """A mechanism over a hole is one the marble falls straight past."""
    editor = _editor()
    editor.place((1, 3), 'bumper')
    editor.erase((1, 3))
    assert editor.feature_at((1, 3)) is None


def test_the_start_and_the_finish_cannot_be_erased():
    editor = _editor()
    assert not editor.erase(editor.level.start_cell)
    assert not editor.erase(editor.level.finish_cell)
    assert editor.level.start_cell in editor.level.cells


# -- height --------------------------------------------------------------------

def test_raising_a_tile_moves_it_by_one_step():
    editor = _editor()
    editor.raise_by((0, 2), 1)
    assert editor.level.cells[(0, 2)] == pytest.approx(HEIGHT_STEP)


def test_lowering_is_raising_the_other_way():
    editor = _editor()
    editor.raise_by((0, 2), -2)
    assert editor.level.cells[(0, 2)] == pytest.approx(-2 * HEIGHT_STEP)


def test_a_step_never_exceeds_what_a_marble_can_roll():
    """One press cannot build a wall by accident."""
    from openglcontext_marble_demo import generator
    assert HEIGHT_STEP <= generator.MAX_STEP + 1e-9


def test_height_cannot_be_given_to_a_tile_that_is_not_there():
    assert not _editor().raise_by((99, 99), 1)


# -- surfaces ------------------------------------------------------------------

def test_painting_gives_a_tile_its_surface():
    editor = _editor()
    editor.paint((0, 2), 'ice_sheet')
    assert editor.level.surface_of((0, 2)) == 'ice_sheet'


def test_painting_the_boards_own_surface_takes_the_patch_off_again():
    editor = _editor()
    editor.paint((0, 2), 'ice_sheet')
    editor.paint((0, 2), editor.level.surface)
    assert (0, 2) not in editor.level.cell_surfaces


def test_an_unknown_surface_is_refused():
    assert not _editor().paint((0, 2), 'marzipan')


# -- mechanisms ----------------------------------------------------------------

def test_every_offered_mechanism_can_be_placed():
    editor = _editor(width=5, depth=len(PLACEABLE_ORDER) + 1)
    for number, kind in enumerate(PLACEABLE_ORDER):
        cell = (1, number)
        assert editor.place(cell, kind), kind
        assert editor.feature_at(cell) is not None, kind


def test_the_palette_offers_every_mechanism_the_game_can_put_on_a_cell():
    """Discovered rather than listed.  A mechanism the game gains is a new file
    in its own package and nothing else, and one the editor could not place
    would be one only a generated board ever had."""
    wanted = {name for name, factory in mechanisms.registry().items()
              if 'cell' in {f.name for f in dataclasses.fields(factory)}}
    assert wanted <= set(PLACEABLE_ORDER), \
        'the palette cannot place %s' % sorted(wanted - set(PLACEABLE_ORDER))
    assert wanted, 'the game registers no single-cell mechanism at all'


def test_a_field_mechanism_is_not_offered_as_something_to_click():
    """Sand and a burner cover an area.  Placing one is a gesture that paints,
    and this tool puts a thing on a tile."""
    for name, (_, factory, _) in PLACEABLE.items():
        assert hasattr(factory, '__dataclass_fields__'), name
        assert 'cell' in factory.__dataclass_fields__, \
            '%r covers a field of cells rather than standing on one' % name


def test_the_built_in_pieces_keep_the_front_of_the_palette():
    """The number keys are muscle memory: a mechanism arriving in the game
    should not move the ramp off 1."""
    assert PLACEABLE_ORDER[:len(BUILT_IN_ORDER)] == BUILT_IN_ORDER
    assert set(placeable_mechanisms()) <= set(PLACEABLE_ORDER)


def test_only_one_mechanism_stands_on_a_cell():
    """Two arms on one tile is not something a designer means, and the second
    would be invisible under the first."""
    editor = _editor()
    editor.place((0, 3), 'bumper')
    editor.place((0, 3), 'arm')
    on_it = [f for f in editor.level.features if getattr(f, 'cell', None) == (0, 3)]
    assert len(on_it) == 1
    assert isinstance(on_it[0], RotatingArm)


def test_a_ramp_arrives_pointing_downhill():
    """The board knows which way it falls, so placing a ramp is a click."""
    editor = _editor(width=3, depth=3)
    editor.raise_by((0, 1), 2)          # a step down toward +row
    editor.place((0, 1), 'ramp')
    assert editor.feature_at((0, 1)).direction == (0, 1)


def test_a_launch_ramp_is_a_ramp_that_launches():
    editor = _editor()
    editor.place((0, 3), 'launch')
    ramp = editor.feature_at((0, 3))
    assert isinstance(ramp, Ramp) and ramp.launch


def test_a_rail_arrives_facing_the_void():
    editor = _editor(width=3, depth=3)
    editor.place((1, 1), 'wall')        # the +X edge of the board
    assert editor.feature_at((1, 1)).side == 'E'


def test_clearing_takes_the_mechanism_and_leaves_the_tile():
    editor = _editor()
    editor.place((0, 3), 'bumper')
    editor.clear((0, 3))
    assert editor.feature_at((0, 3)) is None
    assert (0, 3) in editor.level.cells


def test_clearing_never_takes_the_finish_pad():
    """A board that lost the thing which ends a run cannot be finished."""
    editor = _editor()
    editor.clear(editor.level.finish_cell)
    assert any(isinstance(f, Finish) for f in editor.level.features)


def test_a_mechanism_cannot_be_placed_off_the_board():
    assert not _editor().place((99, 99), 'bumper')


# -- start and finish ----------------------------------------------------------

def test_the_start_can_be_moved_to_another_tile():
    editor = _editor()
    assert editor.set_start((1, 2))
    assert editor.level.start_cell == (1, 2)


def test_the_finish_takes_its_pad_with_it():
    editor = _editor()
    editor.set_finish((1, 5))
    pads = [f for f in editor.level.features if isinstance(f, Finish)]
    assert len(pads) == 1
    assert pads[0].cell == (1, 5)


def test_a_marker_never_lands_on_the_other_one():
    editor = _editor()
    assert not editor.set_start(editor.level.finish_cell)
    assert not editor.set_finish(editor.level.start_cell)


def test_a_marker_never_lands_off_the_board():
    editor = _editor()
    assert not editor.set_start((99, 99))


def test_moving_a_marker_onto_a_mechanism_clears_it():
    """A bumper under the start would have the marble land on it."""
    editor = _editor()
    editor.place((1, 2), 'bumper')
    editor.set_start((1, 2))
    assert editor.feature_at((1, 2)) is None


# -- undo ----------------------------------------------------------------------

def test_undo_gives_back_what_the_last_change_took():
    editor = _editor()
    editor.erase((1, 3))
    assert editor.undo()
    assert (1, 3) in editor.level.cells


def test_redo_does_it_again():
    editor = _editor()
    editor.erase((1, 3))
    editor.undo()
    assert editor.redo()
    assert (1, 3) not in editor.level.cells


def test_a_whole_drag_comes_back_in_one():
    """Painting twenty tiles is one thing the designer did."""
    editor = _editor(width=5, depth=8)
    editor.begin_step()
    for row in range(8):
        editor.erase((2, row))
    editor.end_step()
    editor.undo()
    assert all((2, row) in editor.level.cells for row in range(8))


def test_a_gesture_that_changed_nothing_is_not_a_step_to_undo():
    """A click on a tile that is already there must not eat the last real undo."""
    editor = _editor()
    editor.erase((1, 3))
    editor.begin_step()
    editor.lay(editor.level.start_cell)      # already a tile: no change
    editor.end_step()
    editor.undo()
    assert (1, 3) in editor.level.cells


def test_undo_with_nothing_behind_it_says_so():
    assert not _editor().undo()
    assert not _editor().redo()


def test_a_new_change_forgets_what_was_undone():
    editor = _editor()
    editor.erase((1, 3))
    editor.undo()
    editor.erase((1, 4))
    assert not editor.redo()


def test_the_history_is_bounded():
    editor = _editor(width=3, depth=3)
    for step in range(BoardEditor.HISTORY + 20):
        editor.raise_by((0, 1), 1 if step % 2 == 0 else -1)
    assert len(editor._past) <= BoardEditor.HISTORY


def test_opening_another_board_forgets_the_history():
    """Undoing across a New would put half of one board inside another."""
    editor = _editor()
    editor.erase((1, 3))
    editor.open_level(blank())
    assert not editor.undo()


# -- what is wrong with it -----------------------------------------------------

def test_a_board_cut_in_two_reports_that_the_finish_cannot_be_reached():
    editor = _editor(width=3, depth=5)
    editor.begin_step()
    for col in (-1, 0, 1):
        editor.erase((col, 2))
    editor.end_step()
    assert 'the finish cannot be reached from the start' in editor.problems()
    assert not editor.playable()


def test_a_board_a_marble_can_cross_reports_nothing():
    assert _editor().problems() == []


def test_an_empty_clock_is_reported():
    editor = _editor()
    editor.set_time_limit(0.0)
    assert 'the clock is empty' in editor.problems()


def test_problems_are_reported_rather_than_prevented():
    """A board half-drawn is a normal thing to be looking at."""
    editor = _editor(width=3, depth=5)
    editor.begin_step()
    for col in (-1, 0, 1):
        editor.erase((col, 2))
    editor.end_step()
    assert (0, 2) not in editor.level.cells      # the change was allowed


# -- the file ------------------------------------------------------------------

def test_saving_and_opening_gives_back_the_same_board(tmp_path):
    editor = _editor()
    editor.place((0, 3), 'bumper')
    editor.paint((0, 4), 'ice_sheet')
    editor.raise_by((0, 5), -1)
    path = str(tmp_path / 'board.marble')
    editor.save(path)

    read = BoardEditor()
    read.open(path)
    assert read.level.cells == editor.level.cells
    assert read.level.features == editor.level.features
    assert read.level.cell_surfaces == editor.level.cell_surfaces


def test_a_board_with_no_file_has_to_be_told_where_to_go():
    with pytest.raises(ValueError):
        _editor().save()


def test_saving_marks_the_board_unmodified(tmp_path):
    editor = _editor()
    editor.erase((1, 3))
    assert editor.modified
    editor.save(str(tmp_path / 'board.marble'))
    assert not editor.modified


def test_the_title_says_when_there_is_work_not_in_the_file():
    editor = _editor()
    assert not editor.title.endswith('*')
    editor.erase((1, 3))
    assert editor.title.endswith('*')


# -- what the game makes of it -------------------------------------------------

def test_an_edited_board_builds_into_a_game_and_plays(tmp_path):
    """The point of the editor: the game plays what was drawn."""
    from openglcontext_marble_demo import levelfile
    from openglcontext_marble_demo.game import PLAYING, MarbleGame

    editor = _editor(width=5, depth=10)
    editor.place((1, 3), 'bumper')
    editor.place((0, 4), 'ramp')
    editor.place((-1, 5), 'spring')
    editor.place((1, 6), 'arm')
    editor.place((0, 7), 'elevator')
    editor.place((2, 4), 'wall')
    editor.paint((0, 5), 'ice_sheet')
    editor.raise_by((0, 6), -1)
    path = str(tmp_path / 'played.marble')
    editor.save(path)

    game = MarbleGame(levelfile.load(path))
    for _ in range(180):
        game.lean(0.0, 0.2)
        game.advance(1 / 120.0)
    assert game.state in (PLAYING, 'won', 'lost')
    assert isinstance(editor.feature_at((1, 3)), Bumper)
    assert isinstance(editor.feature_at((2, 4)), Wall)
