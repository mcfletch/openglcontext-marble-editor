"""The scripted sitting: what plays, when, and through what.

A tour is what makes a preview of the editor a recording of the editor being
used rather than an animation of it. What a test can hold it to is that every
step is a thing the editor actually answers -- a tool it has, a key it binds --
and that each plays once.
"""
import pytest

from marble_editor import tour
from marble_editor.board import PLACEABLE_ORDER, SURFACE_NAMES, BoardEditor, blank
from marble_editor.editing import editor_tools


def _tour():
    return tour.default_tour()


# -- the shape of a tour -------------------------------------------------------

def test_steps_play_in_the_order_their_times_say():
    made = tour.Tour([tour.Step(2.0, 'key', name='b'),
                      tour.Step(1.0, 'key', name='a')])
    assert [step.name for step in made.steps] == ['a', 'b']


def test_a_step_plays_once_however_many_frames_land_on_it():
    made = tour.Tour([tour.Step(1.0, 'key', name='h')])
    assert made.due(1.5) == made.steps
    assert made.due(1.6) == []
    assert made.due(99.0) == []


def test_nothing_plays_before_its_time():
    made = tour.Tour([tour.Step(5.0, 'key', name='h')])
    assert made.due(4.9) == []


def test_a_tour_knows_when_it_is_done():
    made = tour.Tour([tour.Step(1.0, 'key', name='h')])
    assert not made.finished
    made.due(2.0)
    assert made.finished


def test_rewinding_plays_it_again():
    made = _tour()
    made.due(999.0)
    made.rewind()
    assert made.due(999.0)


def test_a_step_of_no_known_kind_is_refused():
    with pytest.raises(ValueError, match='juggle'):
        tour.Step(0.0, 'juggle')


# -- the tour the editor ships -------------------------------------------------

def test_it_runs_long_enough_to_watch_and_not_much_longer():
    assert 20.0 <= _tour().length <= 40.0


def test_every_tool_the_editor_has_is_shown():
    """A preview that skipped a tool would be a preview of a smaller editor."""
    tools = editor_tools(BoardEditor(blank()), view=None,
                         viewport=lambda: (800, 600))
    shown = {step.name for step in _tour().steps if step.kind == 'key'}
    for tool in tools.tools:
        if tool.shortcut:
            assert tool.shortcut in shown, tool.name


def test_every_key_it_presses_is_one_the_editor_answers():
    known = {'t', 'h', 'u', 'm', 'k', 'f', '<ctrl-z>', '<ctrl-y>'}
    known |= {str(n) for n in range(1, max(len(PLACEABLE_ORDER),
                                           len(SURFACE_NAMES)) + 1)}
    for step in _tour().steps:
        if step.kind == 'key':
            assert step.name in known, step.name


def test_the_pieces_it_places_are_pieces_that_exist():
    """The number keys choose from a list; a tour naming a seventh piece where
    there are six would press a key that does nothing."""
    for step in _tour().steps:
        if step.kind == 'key' and step.name.isdigit():
            assert 1 <= int(step.name) <= len(PLACEABLE_ORDER)


def test_it_says_what_it_is_about_to_do():
    notes = [step for step in _tour().steps if step.kind == 'note']
    assert len(notes) >= 5
    assert all(step.text for step in notes)


def test_every_pointer_step_names_a_cell():
    for step in _tour().steps:
        if step.kind in ('click', 'drag'):
            assert step.where is not None
        if step.kind == 'drag':
            assert step.to is not None


def test_it_shows_both_buttons():
    """Left does and right undoes is the convention worth showing."""
    buttons = {step.button for step in _tour().steps
               if step.kind in ('click', 'drag')}
    assert buttons == {0, 2}


# -- playing one ---------------------------------------------------------------

class _Fake:
    """A context that records what a step delivered to it."""

    def __init__(self):
        self.said = []
        self.events = []

    def _say(self, text):
        self.said.append(text)

    def ProcessEvent(self, event):
        self.events.append(event)
        return None


def _screen(cell):
    return (100.0 + cell[0] * 20.0, 100.0 + cell[1] * 20.0)


def test_a_note_reaches_the_read_out():
    context = _Fake()
    assert tour.play(tour.Step(0.0, 'note', text='hello'), context, _screen)
    assert context.said == ['hello']


def test_a_key_is_delivered_down_and_up():
    """A tour that left a key held would leave the editor in a state nobody
    asked for."""
    context = _Fake()
    tour.play(tour.Step(0.0, 'key', name='h'), context, _screen)
    assert [event.state for event in context.events] == [1, 0]


def test_a_click_is_a_press_and_a_release_over_the_cell():
    context = _Fake()
    tour.play(tour.Step(0.0, 'click', where=(2, 3)), context, _screen)
    assert len(context.events) == 2
    assert [event.state for event in context.events] == [1, 0]


def test_a_drag_moves_between_the_two_cells_with_the_button_down():
    context = _Fake()
    tour.play(tour.Step(0.0, 'drag', where=(0, 0), to=(0, 4)), context, _screen)
    kinds = [event.type for event in context.events]
    assert kinds[0] == 'mousebutton' and kinds[-1] == 'mousebutton'
    assert 'mousemove' in kinds


def test_a_pointer_step_with_nowhere_to_go_does_nothing():
    assert not tour.play(tour.Step(0.0, 'click'), _Fake(), _screen)
