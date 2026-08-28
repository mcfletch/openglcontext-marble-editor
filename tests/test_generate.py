"""Generating a whole board in the editor, and then editing it.

The Story menu adds one chapter at a time. This is the other end: a board
composed out of the library in one go, which a designer then changes. Both
matter, and the second is why the first is worth having — a generated board
nobody can edit is somebody else's board.

What a test holds this to is that what comes out is playable, that it is a
*different* board each time asked, and that it is still an ordinary level
underneath: undoable, saveable, and editable a tile at a time.
"""
import pytest

from marble_editor.board import BoardEditor, blank
from marble_editor.generate import generate_story


def _editor():
    return BoardEditor(blank())


# -- what comes out --------------------------------------------------------------

def test_generating_replaces_the_board_with_a_composed_one():
    editor = _editor()
    before = len(editor.level.cells)
    generate_story(editor, seed=1, chapters=8)
    assert len(editor.level.cells) > before


def test_a_generated_board_is_playable():
    for seed in range(4):
        editor = _editor()
        generate_story(editor, seed=seed, chapters=8)
        assert editor.problems() == [], seed


def test_a_generated_board_can_be_played_by_the_game():
    from openglcontext_marble_demo.game import PLAYING, MarbleGame
    editor = _editor()
    generate_story(editor, seed=2, chapters=8)
    game = MarbleGame(editor.level)
    for _ in range(300):
        game.advance(1 / 120.0)
    assert game.state in (PLAYING, 'won', 'lost')


def test_asking_twice_gives_two_different_boards():
    """A generator that answered the same thing every time is a preset."""
    boards = set()
    for seed in range(6):
        editor = _editor()
        generate_story(editor, seed=seed, chapters=8)
        boards.add(tuple(sorted(editor.level.cells)))
    assert len(boards) == 6


def test_the_same_seed_gives_the_same_board():
    made = []
    for _ in range(2):
        editor = _editor()
        generate_story(editor, seed=9, chapters=8)
        made.append(dict(editor.level.cells))
    assert made[0] == made[1]


def test_a_generated_board_carries_more_than_one_surface():
    """A board that changes underfoot is one you can navigate by."""
    editor = _editor()
    generate_story(editor, seed=3, chapters=10)
    assert len(set(editor.level.cell_surfaces.values())) > 1


def test_a_longer_board_is_asked_for_and_given():
    short, long_one = _editor(), _editor()
    generate_story(short, seed=4, chapters=4)
    generate_story(long_one, seed=4, chapters=12)
    assert len(long_one.level.cells) > len(short.level.cells)


def test_a_generated_board_is_named_after_what_made_it():
    """So a board worth keeping can be made again."""
    editor = _editor()
    generate_story(editor, seed=7, chapters=6)
    assert '7' in editor.level.name


# -- it is still an ordinary board ------------------------------------------------

def test_generating_is_one_press_of_undo():
    editor = _editor()
    before = dict(editor.level.cells)
    generate_story(editor, seed=1, chapters=6)
    editor.undo()
    assert editor.level.cells == before


def test_a_generated_board_can_be_edited_tile_by_tile():
    editor = _editor()
    generate_story(editor, seed=1, chapters=6)
    cell = editor.level.finish_cell
    assert editor.raise_by(cell, 1)


def test_a_chapter_can_be_added_to_a_generated_board():
    """The two halves of the job meet: compose, then extend by hand."""
    from marble_editor.chapters import add_chapter
    editor = _editor()
    generate_story(editor, seed=1, chapters=6)
    before = len(editor.level.cells)
    add_chapter(editor, 'plateau')
    assert len(editor.level.cells) > before


def test_a_generated_board_saves_and_loads(tmp_path):
    editor = _editor()
    generate_story(editor, seed=5, chapters=8)
    path = str(tmp_path / 'made.marble')
    editor.save(path)
    read = BoardEditor()
    read.open(path)
    assert read.level.cells == editor.level.cells


def test_generating_marks_the_board_modified():
    editor = _editor()
    generate_story(editor, seed=1, chapters=6)
    assert editor.modified


def test_an_impossible_request_says_so_rather_than_making_a_wreck():
    editor = _editor()
    with pytest.raises(ValueError):
        generate_story(editor, seed=1, chapters=0, difficulty=99)
