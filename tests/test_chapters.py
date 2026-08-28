"""Adding a chapter from the library to a board being edited.

The editor draws tiles one at a time, which is right for the last ten percent of
a board and wrong for the first ninety. A chapter is the other end of the same
work: pick something out of the library and it is appended to what is already
there, entered where the board currently ends and leaving somewhere new -- and
then the tile tools are there to adjust it.

What a test can hold that to is that the board grows, stays one connected
region, stays playable, and that undo takes the whole chapter back in one.
"""
import pytest
from openglcontext_marble_demo import fragments

from marble_editor.board import BoardEditor, blank
from marble_editor.chapters import CHAPTERS, add_chapter, entry_port


def _editor(**named):
    return BoardEditor(blank(**named))


# -- what the editor offers -----------------------------------------------------

def test_the_editor_offers_what_the_library_holds():
    """Discovered, not listed: a fragment added to the game is offered here
    without the editor being told."""
    assert set(CHAPTERS()) == set(fragments.library())


def test_every_offered_chapter_names_its_variants():
    for name, entry in CHAPTERS().items():
        assert entry.variants, name


# -- where a chapter attaches ---------------------------------------------------

def test_a_chapter_is_entered_where_the_board_currently_ends():
    editor = _editor(width=5, depth=8)
    port = entry_port(editor.level)
    assert port.cell == editor.level.finish_cell
    assert port.height == pytest.approx(editor.level.cells[port.cell])


def test_the_entry_faces_away_from_the_board_it_is_leaving():
    """A chapter laid back over the board it came from would be laid on top of
    it, so the facing is the way the board runs out."""
    editor = _editor(width=5, depth=8)
    assert entry_port(editor.level).facing == (0, 1)


def test_a_board_with_no_tiles_still_offers_somewhere_to_start():
    level = blank(width=3, depth=3)
    level.cells.clear()
    assert entry_port(level) is not None


# -- adding one ------------------------------------------------------------------

def test_adding_a_chapter_grows_the_board():
    editor = _editor(width=5, depth=8)
    before = len(editor.level.cells)
    assert add_chapter(editor, 'plateau')
    assert len(editor.level.cells) > before


def test_the_board_is_still_one_region_afterwards():
    from openglcontext_marble_demo import pieces
    editor = _editor(width=5, depth=8)
    add_chapter(editor, 'ramp_down')
    assert pieces.joined(editor.level.cells, editor.level.start_cell,
                         editor.level.finish_cell)


def test_the_finish_moves_to_the_end_of_what_was_added():
    editor = _editor(width=5, depth=8)
    was = editor.level.finish_cell
    add_chapter(editor, 'plateau')
    assert editor.level.finish_cell != was
    assert editor.level.finish_cell in editor.level.cells


def test_only_one_finish_pad_survives():
    from openglcontext_marble_demo.level import Finish
    editor = _editor()
    add_chapter(editor, 'plateau')
    add_chapter(editor, 'ramp_down')
    assert sum(isinstance(f, Finish) for f in editor.level.features) == 1


def test_the_board_stays_playable():
    editor = _editor(width=5, depth=8)
    for name in ('ramp_down', 'plateau', 'hairpin', 'plateau'):
        add_chapter(editor, name)
    assert editor.problems() == []


def test_a_chapter_brings_its_own_surfaces():
    editor = _editor()
    add_chapter(editor, 'plateau', variant='rink')
    assert 'ice_sheet' in set(editor.level.cell_surfaces.values())


def test_a_chapter_brings_its_own_mechanisms():
    from openglcontext_marble_demo.level import Bumper
    editor = _editor()
    add_chapter(editor, 'scatter')
    assert any(isinstance(f, Bumper) for f in editor.level.features)


def test_asking_for_a_chapter_that_is_not_there_says_so():
    with pytest.raises(KeyError, match='trampoline'):
        add_chapter(_editor(), 'trampoline')


def test_asking_for_a_variant_that_is_not_there_says_so():
    with pytest.raises(KeyError, match='nonesuch'):
        add_chapter(_editor(), 'plateau', variant='nonesuch')


# -- it is one edit --------------------------------------------------------------

def test_undo_takes_a_whole_chapter_back_in_one():
    """A chapter is one thing the designer did, however many tiles it laid."""
    editor = _editor(width=5, depth=8)
    before = dict(editor.level.cells)
    add_chapter(editor, 'scatter')
    editor.undo()
    assert editor.level.cells == before


def test_adding_a_chapter_marks_the_board_modified():
    editor = _editor()
    add_chapter(editor, 'plateau')
    assert editor.modified


def test_a_chapter_can_still_be_edited_tile_by_tile_afterwards():
    """The point of adding one to an editor rather than to a generator."""
    editor = _editor(width=5, depth=8)
    add_chapter(editor, 'plateau')
    cell = editor.level.finish_cell
    editor.raise_by((cell[0] + 1, cell[1]), 1)
    assert editor.level.cells[(cell[0] + 1, cell[1])] != 0.0


# -- several in a row -------------------------------------------------------------

def test_chapters_chain_one_after_another():
    editor = _editor(width=5, depth=6)
    sizes = []
    for name in ('ramp_down', 'plateau', 'ramp_down', 'plateau'):
        add_chapter(editor, name)
        sizes.append(len(editor.level.cells))
    assert sizes == sorted(sizes)
    assert len(set(sizes)) == len(sizes)


def test_a_chained_board_descends_as_it_goes():
    editor = _editor(width=5, depth=6)
    top = editor.level.cells[editor.level.start_cell]
    for _ in range(3):
        add_chapter(editor, 'ramp_down')
    assert editor.level.cells[editor.level.finish_cell] < top


def test_the_board_a_chapter_built_can_be_played():
    from openglcontext_marble_demo.game import PLAYING, MarbleGame
    editor = _editor(width=5, depth=6)
    for name in ('ramp_down', 'plateau', 'scatter', 'plateau'):
        add_chapter(editor, name)
    game = MarbleGame(editor.level)
    for _ in range(240):
        game.advance(1 / 120.0)
    assert game.state in (PLAYING, 'won', 'lost')
