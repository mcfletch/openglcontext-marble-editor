"""A scripted sitting at the editor: what it does, shown rather than described.

An editor is a thing you use, and a page of screenshots is not one. A
:class:`Tour` is a list of moments — *at four seconds, take the height tool; at
five, drag from here to there* — played back through the **real event path**, so
what a viewer sees is the editor being used rather than an animation of it being
used. Nothing here reaches past the handlers a hand would reach.

That is also what makes it worth keeping. A tour that plays start to finish is a
run through every tool the editor has, and it fails where a hand would fail: a
step that names a tool the editor does not offer, or clicks where nothing
happens, is a step whose effect is measurable and therefore a step a test can
hold to.

    >>> tour = Tour([Step(0.0, 'key', name='h'), Step(1.0, 'key', name='t')])
    >>> tour.due(0.5), tour.due(1.5)
    ([Step(0.0, key)], [Step(1.0, key)])

Times are seconds from the moment the tour starts, and a step is played once
however many frames land on it. Because the clock a recording installs advances
by exactly one frame's worth per frame kept, a tour recorded to video plays at
the times it says regardless of how fast the machine drew it.
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

from OpenGLContext.events import synthetic

__all__ = ['Step', 'Tour', 'play', 'default_tour']

#: What a step can be.  ``key`` and ``press`` are a key transition and a typed
#: character; ``click`` and ``drag`` are the pointer; ``note`` puts a line in the
#: read-out, which is how a tour says what it is about to do.
KINDS = ('key', 'press', 'click', 'drag', 'note')


@dataclass
class Step:
    """One thing that happens, at ``at`` seconds into the tour.

    ``where`` and ``to`` are in **cells** rather than pixels: a tour that named
    pixels would show something different in a window of another size, and what
    it means is "the tile two along from the start".
    """

    at: float
    kind: str
    name: str = ''
    where: Any = None
    to: Any = None
    button: int = 0
    text: str = ''

    def __post_init__(self) -> None:
        if self.kind not in KINDS:
            raise ValueError('%r is not one of %s' % (self.kind, ', '.join(KINDS)))

    def __repr__(self) -> str:
        return 'Step(%.1f, %s)' % (self.at, self.kind)


@dataclass
class Tour:
    """A list of steps, played once each as their times come round."""

    steps: Sequence[Step] = field(default_factory=list)
    _played: set = field(default_factory=set, repr=False)

    def __post_init__(self) -> None:
        self.steps = sorted(self.steps, key=lambda step: step.at)

    @property
    def length(self) -> float:
        """How long the tour runs for, in seconds."""
        return max((step.at for step in self.steps), default=0.0)

    @property
    def finished(self) -> bool:
        return len(self._played) >= len(self.steps)

    def due(self, elapsed: float) -> list:
        """The steps whose time has come and which have not been played."""
        ready = []
        for index, step in enumerate(self.steps):
            if index not in self._played and step.at <= elapsed:
                self._played.add(index)
                ready.append(step)
        return ready

    def rewind(self) -> None:
        self._played.clear()


def _deliver(context: Any, record: dict) -> bool:
    """Build one event and hand it to ``context.ProcessEvent``.

    Through ``ProcessEvent`` rather than
    :func:`OpenGLContext.events.synthetic.dispatch`, which routes a pointer
    event to the *event manager*: that is the road a replay takes, after a pick
    pass has said what is under the cursor.  An editor intercepts the pointer in
    ``ProcessEvent`` and works out the cell from the map itself, so this is the
    road a real click takes here -- and delivering by the other one would
    demonstrate a path the editor does not use.
    """
    event = synthetic.build(record)
    if event is None:
        return False
    event.context = context
    if hasattr(event, 'setObjectPaths'):
        event.setObjectPaths([])
    context.ProcessEvent(event)
    return True


def play(step: Step, context: Any, screen: Any) -> bool:
    """Deliver one step to ``context``, as the platform would have.

    ``screen`` turns a cell into the window pixel over its middle -- the one
    piece a tour cannot know for itself, because it depends on where the map is
    looking.  Answers whether the step was delivered.
    """
    if step.kind == 'note':
        note = getattr(context, '_say', None)
        if note is not None:
            note(step.text)
        return True
    if step.kind == 'key':
        return _both(context, {'type': 'keyboard', 'key': step.name,
                               'modifiers': [0, 0, 0]})
    if step.kind == 'press':
        return _deliver(context, {'type': 'keypress', 'key': step.name,
                                  'modifiers': [0, 0, 0]})
    if step.where is None:
        return False
    x, y = screen(step.where)
    if step.kind == 'click':
        return _button(context, x, y, step.button, 1) \
            and _button(context, x, y, step.button, 0)
    # A drag: press where it starts, move across, release where it ends.
    to_x, to_y = screen(step.to if step.to is not None else step.where)
    delivered = _button(context, x, y, step.button, 1)
    for fraction in (0.25, 0.5, 0.75, 1.0):
        _deliver(context, {
            'type': 'mousemove', 'buttons': [step.button],
            'x': x + (to_x - x) * fraction, 'y': y + (to_y - y) * fraction,
            'modifiers': [0, 0, 0]})
    return delivered and _button(context, to_x, to_y, step.button, 0)


def _both(context: Any, record: dict) -> bool:
    """A key down and up: a tour never leaves a key held."""
    down = _deliver(context, dict(record, state=1))
    _deliver(context, dict(record, state=0))
    return down


def _button(context: Any, x: float, y: float, button: int, state: int) -> bool:
    return _deliver(context, {
        'type': 'mousebutton', 'button': button, 'state': state,
        'x': x, 'y': y, 'modifiers': [0, 0, 0]})


#: The tour the editor plays when asked to show itself: every tool in turn, on a
#: board being built out of nothing.  Times are chosen so each change is on
#: screen long enough to read before the next one starts, and each note says
#: what is about to happen so a viewer is not guessing.
def default_tour() -> Tour:
    """The tour the editor plays when asked to show itself."""
    def note(at: float, text: str) -> Step:
        return Step(at, 'note', text=text)

    def key(at: float, name: str) -> Step:
        return Step(at, 'key', name=name)

    def click(at: float, where: tuple, button: int = 0) -> Step:
        return Step(at, 'click', where=where, button=button)

    def drag(at: float, where: tuple, to: tuple, button: int = 0) -> Step:
        return Step(at, 'drag', where=where, to=to, button=button)

    return Tour([
        note(0.6, 'Tiles: left lays, right takes away'),
        key(1.2, 't'),
        drag(1.8, (-1, 2), (-1, 6)),
        drag(2.8, (0, 2), (0, 6)),
        drag(3.8, (1, 2), (1, 6)),
        drag(4.6, (1, 6), (1, 6), button=2),

        note(5.2, 'Height: a drag levels a terrace'),
        key(5.8, 'h'),
        drag(6.4, (-1, 4), (1, 4)),
        drag(7.4, (-1, 5), (1, 5)),
        drag(8.4, (-1, 6), (1, 6)),

        note(9.4, 'Surface: ice to slide on'),
        key(10.0, 'u'),
        key(10.6, '2'),
        drag(11.2, (-1, 3), (1, 3)),

        note(12.4, 'Pieces: a ramp arrives pointing downhill'),
        key(13.0, 'm'),
        key(13.6, '1'),
        click(14.2, (0, 4)),
        key(15.0, '4'),
        click(15.6, (-1, 5)),
        key(16.4, '5'),
        click(17.0, (1, 5)),
        key(17.8, '7'),
        click(18.4, (0, 6)),

        note(19.4, 'Right clears a cell'),
        click(20.0, (0, 6), button=2),

        note(21.0, 'Markers: left the start, right the finish'),
        key(21.6, 'k'),
        click(22.2, (0, 2)),
        click(23.0, (0, 7), button=2),

        note(24.0, 'ctrl-z takes back a whole drag'),
        key(24.6, '<ctrl-z>'),
        key(25.6, '<ctrl-z>'),
        key(26.6, '<ctrl-y>'),

        note(27.6, 'f fits the board to the window'),
        key(28.2, 'f'),
    ])
