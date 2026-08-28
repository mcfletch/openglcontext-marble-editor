"""The gestures: what the pointer does in each tool, driven with no window.

A :class:`~OpenGLContext.edit.tools.Pointer` is a plain object, so every tool
can be worked exactly as a designer works it — press, drag, release — and the
board asked what happened. That is the whole reason the tools hold no rules:
these tests are about *gestures*, and ``test_board`` is about rules.
"""
import pytest
from OpenGLContext.edit.tools import Pointer

from marble_editor.board import HEIGHT_STEP, BoardEditor, blank
from marble_editor.editing import (
    LEFT,
    RIGHT,
    HeightTool,
    MarkerTool,
    MechanismTool,
    SurfaceTool,
    TileTool,
    editor_tools,
)

CELL = 4.0


def _editor(**named):
    return BoardEditor(blank(**named))


def _at(cell, button=LEFT):
    """A pointer over the middle of ``cell``."""
    return Pointer(x=0.0, y=0.0, button=button,
                   world=[cell[0] * CELL, 0.0, cell[1] * CELL])


def _click(tool, cell, button=LEFT):
    tool.on_press(_at(cell, button))
    tool.on_release(_at(cell, button))


def _drag(tool, cells, button=LEFT):
    tool.on_press(_at(cells[0], button))
    for cell in cells[1:]:
        tool.on_drag(_at(cell, button))
    tool.on_release(_at(cells[-1], button))


# -- where the pointer is ------------------------------------------------------

def test_a_pointer_lands_on_the_cell_under_it():
    tool = TileTool(editor=_editor())
    assert tool.cell(_at((3, -2))) == (3, -2)


def test_a_pointer_anywhere_in_a_cell_lands_on_that_cell():
    tool = TileTool(editor=_editor())
    nearly = Pointer(world=[2 * CELL + CELL * 0.4, 0.0, 0.0])
    assert tool.cell(nearly) == (2, 0)


def test_a_pointer_over_nothing_lands_nowhere():
    assert TileTool(editor=_editor()).cell(Pointer(world=None)) is None


# -- tiles ---------------------------------------------------------------------

def test_the_left_button_lays_tiles():
    editor = _editor()
    _click(TileTool(editor=editor), (9, 9))
    assert (9, 9) in editor.level.cells


def test_the_right_button_takes_them_away():
    editor = _editor()
    _click(TileTool(editor=editor), (1, 3), button=RIGHT)
    assert (1, 3) not in editor.level.cells


def test_a_drag_lays_every_cell_it_crosses():
    editor = _editor()
    _drag(TileTool(editor=editor), [(9, row) for row in range(4)])
    assert all((9, row) in editor.level.cells for row in range(4))


def test_a_drag_is_one_press_of_undo():
    editor = _editor()
    _drag(TileTool(editor=editor), [(9, row) for row in range(4)])
    editor.undo()
    assert not any((9, row) in editor.level.cells for row in range(4))


def test_a_press_over_nothing_is_left_for_the_camera():
    """What a tool does not want moves the map."""
    assert not TileTool(editor=_editor()).on_press(Pointer(world=None))


def test_the_middle_button_is_left_for_the_camera():
    assert not TileTool(editor=_editor()).on_press(_at((0, 0), button=1))


def test_escape_abandons_a_drag_and_puts_the_board_back():
    editor = _editor()
    tool = TileTool(editor=editor)
    tool.on_press(_at((1, 3), button=RIGHT))
    tool.on_drag(_at((1, 4), button=RIGHT))
    tool.cancel()
    assert (1, 3) in editor.level.cells
    assert (1, 4) in editor.level.cells


# -- height --------------------------------------------------------------------

def test_dragging_up_raises_a_tile():
    editor = _editor()
    _click(HeightTool(editor=editor), (0, 2))
    assert editor.level.cells[(0, 2)] == pytest.approx(HEIGHT_STEP)


def test_the_right_button_lowers():
    editor = _editor()
    _click(HeightTool(editor=editor), (0, 2), button=RIGHT)
    assert editor.level.cells[(0, 2)] == pytest.approx(-HEIGHT_STEP)


def test_dragging_levels_a_terrace_rather_than_building_a_staircase():
    """Pressing on the height you want and pulling it along says "this much,
    over here"; a step per cell would make a staircase instead."""
    editor = _editor(width=5, depth=8)
    _drag(HeightTool(editor=editor), [(0, row) for row in range(4)])
    heights = {editor.level.cells[(0, row)] for row in range(4)}
    assert len(heights) == 1
    assert heights.pop() == pytest.approx(HEIGHT_STEP)


# -- surfaces ------------------------------------------------------------------

def test_the_surface_tool_paints_what_it_is_set_to():
    editor = _editor()
    tool = SurfaceTool(editor=editor, surface='ice_sheet')
    _click(tool, (0, 2))
    assert editor.level.surface_of((0, 2)) == 'ice_sheet'


def test_the_right_button_paints_the_boards_own_surface_back():
    editor = _editor()
    tool = SurfaceTool(editor=editor, surface='ice_sheet')
    _click(tool, (0, 2))
    _click(tool, (0, 2), button=RIGHT)
    assert (0, 2) not in editor.level.cell_surfaces


def test_a_number_key_chooses_the_surface():
    tool = SurfaceTool(editor=_editor())
    assert tool.on_key('2', (0, 0, 0))
    from marble_editor.board import SURFACE_NAMES
    assert tool.surface == SURFACE_NAMES[1]


def test_a_key_the_tool_has_no_use_for_is_left_alone():
    assert not SurfaceTool(editor=_editor()).on_key('q', (0, 0, 0))


# -- mechanisms ----------------------------------------------------------------

def test_the_mechanism_tool_places_what_it_is_set_to():
    editor = _editor()
    tool = MechanismTool(editor=editor, kind='bumper')
    _click(tool, (0, 3))
    assert editor.feature_at((0, 3)) is not None


def test_the_right_button_clears_a_cell():
    editor = _editor()
    tool = MechanismTool(editor=editor, kind='bumper')
    _click(tool, (0, 3))
    _click(tool, (0, 3), button=RIGHT)
    assert editor.feature_at((0, 3)) is None


def test_a_number_key_chooses_the_mechanism():
    from marble_editor.board import PLACEABLE_ORDER
    tool = MechanismTool(editor=_editor())
    assert tool.on_key('4', (0, 0, 0))
    assert tool.kind == PLACEABLE_ORDER[3]


def test_the_tool_says_what_it_will_put_down():
    tool = MechanismTool(editor=_editor(), kind='spring')
    assert tool.kind_label == 'Spring'


# -- start and finish ----------------------------------------------------------

def test_the_buttons_set_the_two_ends_of_a_run():
    editor = _editor()
    tool = MarkerTool(editor=editor)
    _click(tool, (1, 2))
    _click(tool, (1, 5), button=RIGHT)
    assert editor.level.start_cell == (1, 2)
    assert editor.level.finish_cell == (1, 5)


def test_a_marker_does_not_smear_across_a_drag():
    """There is one start; dragging it would leave it wherever the pointer was
    let go rather than where it was put."""
    editor = _editor()
    tool = MarkerTool(editor=editor)
    _drag(tool, [(1, 2), (1, 3), (1, 4)])
    assert editor.level.start_cell == (1, 2)


# -- the set of them -----------------------------------------------------------

def test_the_editor_offers_a_tool_for_each_kind_of_change():
    tools = editor_tools(_editor(), view=None, viewport=lambda: (800, 600))
    names = [tool.name for tool in tools.tools]
    assert names == ['tiles', 'height', 'surface', 'mechanisms', 'markers', 'pan']


def test_tiles_have_the_pointer_to_start_with():
    """The shape of the board is what a designer opens the editor to draw."""
    tools = editor_tools(_editor(), view=None, viewport=lambda: (800, 600))
    assert tools.active.name == 'tiles'


def test_every_tool_has_a_key_of_its_own():
    tools = editor_tools(_editor(), view=None, viewport=lambda: (800, 600))
    shortcuts = [tool.shortcut for tool in tools.tools if tool.shortcut]
    assert len(shortcuts) == len(set(shortcuts))


def test_undo_reaches_the_board_through_whichever_tool_is_in_force():
    editor = _editor()
    tools = editor_tools(editor, view=None, viewport=lambda: (800, 600))
    _click(tools.active, (9, 9))
    tools.select('mechanisms')
    assert tools.undo()
    assert (9, 9) not in editor.level.cells


def test_a_tool_cannot_be_swapped_out_from_under_a_gesture():
    editor = _editor()
    tools = editor_tools(editor, view=None, viewport=lambda: (800, 600))
    tools.press(_at((9, 9)))
    assert not tools.select('mechanisms')
    tools.release(_at((9, 9)))
    assert tools.select('mechanisms')


def test_a_change_tells_whoever_asked_to_be_told():
    """The window redraws off this rather than polling the board."""
    told = []
    editor = _editor()
    tool = TileTool(editor=editor, on_change=lambda: told.append(1))
    _click(tool, (9, 9))
    assert told
