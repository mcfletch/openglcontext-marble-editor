"""The board editor: draw a board, put mechanisms on it, and play it.

    oglc-marble-editor                    # a blank board to draw on
    oglc-marble-editor spiral.marble      # carry on with one
    oglc-marble-editor --from-seed 7      # start from a generated board

The window is a **map**: the board from straight above, orthographic, so a cell
is the same number of pixels wherever it is. A strip down the left says what the
pointer is for; the menus keep what applies to the whole board.

Keys::

    t h u m k            tiles, height, surface, mechanisms, start/finish
    1 ... 7              what the tool in force puts down
    left / right         do / undo, in every tool
    right drag, wheel    move the map, zoom about the pointer
    f                    fit the whole board in the window
    ctrl-z / ctrl-y      undo, redo
    ctrl-s               save
    ctrl-p               play it

Everything in this file is the window.  What a board *is*, what may be done to
one, and what it looks like drawn are :mod:`marble_editor.board`,
:mod:`marble_editor.editing` and :mod:`marble_editor.scene`, none of which needs
one.
"""
from __future__ import annotations

import argparse
import logging
import os
import subprocess
import sys
from types import SimpleNamespace
from typing import Any

os.environ.setdefault('OPENGLCONTEXT_BACKEND', 'glfw')
os.environ.setdefault('OPENGLCONTEXT_RENDERER', 'pbr')

from OpenGLContext import testingcontext  # noqa: E402
from OpenGLContext.edit.mapview import MapView, MapViewPlatform  # noqa: E402
from OpenGLContext.events.systemtime import systemTime  # noqa: E402
from OpenGLContext.physics.demo import disable_vsync  # noqa: E402
from OpenGLContext.scenegraph.scenegraph import SceneGraph  # noqa: E402
from OpenGLContext.ui.menu import MenuBar, MenuItem  # noqa: E402
from OpenGLContext.ui.overlay import OverlayMixin  # noqa: E402
from OpenGLContext.ui.toolpalette import ToolPalette  # noqa: E402
from OpenGLContext.ui.widgets import Separator  # noqa: E402
from OpenGLContext.video.recorder import RecordingMixin  # noqa: E402
from openglcontext_marble_demo import generator, levelfile  # noqa: E402

from marble_editor import scene  # noqa: E402
from marble_editor.board import (  # noqa: E402
    PLACEABLE,
    PLACEABLE_ORDER,
    SURFACE_NAMES,
    BoardEditor,
    blank,
)
from marble_editor.chapters import CHAPTERS, add_chapter  # noqa: E402
from marble_editor.controls import ZOOM_STEP, MapControls  # noqa: E402
from marble_editor.editing import MechanismTool, SurfaceTool, editor_tools  # noqa: E402
from marble_editor.status import EditorStatus  # noqa: E402
from marble_editor.tour import default_tour, play  # noqa: E402

log = logging.getLogger(__name__)

BaseContext: Any = testingcontext.getInteractive()

#: How much of the top of the window the menu bar takes, in reference pixels,
#: so the read-outs start below it rather than under it.
MENU_BAR_ROOM = 30.0

#: How much board is left round the edge when the view is fitted to it, as a
#: fraction: a board drawn to the window's edge looks like a board that runs off.
MARGIN = 0.15


def _titled(name):
    """A fragment's name as a menu reads it."""
    return name.replace('_', ' ').capitalize()


def board_bounds(level, margin=MARGIN):
    """The world corners of a board, with room round the outside."""
    size = level.cell_size
    if not level.cells:
        return (-size, -size), (size, size)
    columns = [col for col, _ in level.cells]
    rows = [row for _, row in level.cells]
    room = size * (1.0 + 2.0 * margin)
    return ((min(columns) * size - room, min(rows) * size - room),
            (max(columns) * size + room, max(rows) * size + room))


class EditorContext(RecordingMixin, OverlayMixin, BaseContext):    # pragma: no cover - needs a window
    """The editor's window: a map, a menu bar, and the tools in between."""

    config: Any = None

    def OnInit(self) -> None:
        self.editor = BoardEditor(self.config.level, on_change=self._board_changed)
        self.editor.path = self.config.path
        self.view = MapView(centre=(0.0, 0.0), span=80.0, smallest=8.0,
                            largest=4000.0)
        # The platform the context made for itself is a perspective camera; this
        # one reads the map.  It has to be told the window's size, because the
        # context told the one it is replacing and will not do it again until
        # the window is resized.
        self.platform = MapViewPlatform(self.view, self.getViewPort())
        self.platform.setViewport(*self.getViewPort())
        # The map platform is the sole driver of the camera, so unbind the
        # default free-fly movement manager or the two fight over it.
        manager = getattr(self, 'movementManager', None)
        if manager is not None:
            manager.unbind(self)
            self.movementManager = None

        self.tools = editor_tools(self.editor, self.view, self.getViewPort,
                                  on_change=self._board_changed,
                                  on_tool=self._tool_changed)
        self.controls = MapControls(self.view, self.tools, self.getViewPort,
                                    on_change=self._report)
        self.sg = SceneGraph(children=[])
        self._rebuild()
        self._frame_all()

        # Panels rather than HUD layers: a HUD takes no events, and a menu bar
        # and a tool palette are nothing but events.  Neither is modal, so a
        # click that misses both reaches the map underneath.
        self.menus = MenuBar(menus=self._menus(), stack=self.overlays)
        self.overlays.push(self.menus)
        self.palette = ToolPalette(tools=self.tools, reserved=MENU_BAR_ROOM)
        self.overlays.push(self.palette)
        self.status = EditorStatus()
        #: The interface scale the read-outs were last given room for.
        self._reserved_at: float | None = None
        self._reserve_room()
        self.addHUDLayer(self.status)
        self._report()
        # Bound methods, not lambdas: handlers are held by weak reference, so a
        # callback with nothing else keeping it alive is collected the moment
        # this returns and the key is silently dead.
        self.addEventHandler('keypress', name='f', function=self._on_frame)
        # A tour drives the editor through the same handlers a hand does, so a
        # recording of one is a recording of the editor being used.
        self.tour = default_tour() if self.config.tour else None
        self._started = None
        if self.config.record:
            # A recording wants frames as fast as they can be drawn.  Left on,
            # the swap waits for the display, and an editor -- which is
            # event-driven and asks for a frame only when something changed --
            # then draws almost none at all.
            disable_vsync()
            self.setupRecording(self.config.record, **self.config.record_options)
        print(__doc__)

    # -- showing itself ----------------------------------------------------
    def screen_of(self, cell: tuple) -> tuple:
        """The window pixel over the middle of ``cell``.

        The one thing a tour cannot work out for itself, because it depends on
        where the map is looking.
        """
        size = self.editor.level.cell_size
        x, y = self.view.screen_from_world(
            (cell[0] * size, 0.0, cell[1] * size), self.getViewPort())
        return (float(x), float(y))

    def playTour(self) -> None:
        """Play whatever of the tour has come due."""
        if self.tour is None:
            return
        now = systemTime()
        if self._started is None:
            self._started = now
        for step in self.tour.due(now - self._started):
            play(step, self, self.screen_of)

    def presentFrame(self) -> Any:
        """Present the frame, giving it to the recording first.

        The back buffer holds the finished frame only until it is swapped away.
        """
        if self.recording:
            self.tickRecording()
        return super().presentFrame()

    def _reserve_room(self) -> None:
        """Keep the read-outs out from under the bar and beside the palette.

        The palette's width is its labels, so it changes with the interface
        scale and with which tools the editor has; the read-outs are told in
        reference pixels and scale it themselves, which is why this is settled
        against the metrics the interface is actually drawn at rather than once
        at startup.
        """
        metrics = self.overlayMetrics()
        self._reserved_at = float(getattr(metrics, 'scale', 0.0)) if metrics else 0.0
        self.status.reserved = (MENU_BAR_ROOM, 0.0, 0.0, self.palette.room(metrics))

    def OnIdle(self, *args: Any) -> int:
        """Between frames: play the tour, and put right what a resize left stale."""
        self.playTour()
        if self.recording:
            self.triggerRedraw(1)       # a recording wants every frame drawn
        metrics = self.overlayMetrics()
        if metrics is not None and float(metrics.scale) != self._reserved_at:
            self._reserve_room()
        return 1

    # -- the board changed -------------------------------------------------
    def _board_changed(self) -> None:
        self._rebuild()
        self._report()

    def _rebuild(self) -> None:
        """Draw the board as it now is."""
        self.sg.children = list(scene.board_scene(self.editor.level).children)
        self.triggerRedraw(1)

    def _report(self) -> None:
        status = getattr(self, 'status', None)
        if status is None:
            return
        level = self.editor.level
        status.show(title=self.editor.title, tiles=len(level.cells),
                    clock=level.time_limit, problems=self.editor.problems(),
                    tool=self._tool_text())
        self.triggerRedraw(1)

    def _tool_text(self) -> str:
        """Which tool has the pointer, and what it is set to put down."""
        tool = self.tools.active
        if tool is None:
            return ''
        if isinstance(tool, MechanismTool):
            return '%s: %s' % (tool.label, tool.kind_label)
        if isinstance(tool, SurfaceTool):
            return '%s: %s' % (tool.label, tool.surface)
        return str(tool.label)

    def _tool_changed(self, tool: Any) -> None:
        self._report()

    # -- events ------------------------------------------------------------
    def ProcessEvent(self, event: Any) -> Any:
        if self.overlaySinks(event):
            return None
        if self._toolTook(event):
            self.triggerRedraw(1)
            return None
        return super().ProcessEvent(event)

    def _toolTook(self, event: Any) -> bool:
        kind = getattr(event, 'type', None)
        if kind == 'keyboard' and getattr(event, 'state', 0):
            name = event.name
            if name == '<ctrl-z>':
                return self._undo()
            if name == '<ctrl-y>':
                return self._redo()
            if name == '<ctrl-s>':
                self._save()
                return True
            if name == '<ctrl-p>':
                self._play()
                return True
            if self.tools.select(self._tool_for_key(name)):
                return True
            return self.controls.key(name, tuple(event.getModifiers()))
        if kind == 'mousebutton':
            return bool(self.controls.button(event))
        if kind == 'mousemove':
            return bool(self.controls.moved(event))
        return False

    def _tool_for_key(self, name: str) -> str:
        for tool in self.tools.tools:
            if tool.shortcut and tool.shortcut == name:
                return str(tool.name)
        return ''

    def _on_frame(self, event: Any = None) -> None:
        self._frame_all()

    def _frame_all(self) -> None:
        """Fit the whole board in the window."""
        minimum, maximum = board_bounds(self.editor.level)
        self.controls.frame(minimum, maximum)
        self.triggerRedraw(1)

    # -- the file ----------------------------------------------------------
    def _default_path(self) -> str:
        name = (self.editor.level.name or 'board').replace(' ', '-')
        return self.editor.path or (name + levelfile.SUFFIX)

    def _save(self) -> None:
        try:
            path = self.editor.save(self._default_path())
        except (OSError, ValueError) as error:
            self._say(str(error))
            return
        self._say('Saved %s' % path)

    def _undo(self) -> bool:
        if self.editor.undo():
            return True
        self._say('Nothing to undo.')
        return True

    def _redo(self) -> bool:
        if self.editor.redo():
            return True
        self._say('Nothing to redo.')
        return True

    def _play(self) -> None:
        """Save the board and play it, in a window of its own.

        A separate process rather than a mode of this one: the game wants a
        perspective camera, the physics and the PBR renderer, and an editor that
        became a game and came back would be two applications sharing one GL
        context and one set of key bindings.
        """
        problems = self.editor.problems()
        if problems:
            self._say('Not playable yet: %s' % problems[0])
            return
        try:
            path = self.editor.save(self._default_path())
        except (OSError, ValueError) as error:
            self._say(str(error))
            return
        try:
            subprocess.Popen([sys.executable, '-m', 'openglcontext_marble_demo',
                              '--board', path])
        except OSError as error:
            self._say('Could not start the game: %s' % error)
            return
        self._say('Playing %s' % path)

    def _say(self, text: str) -> None:
        self.status.message = text
        log.info('%s', text)
        self.triggerRedraw(1)

    # -- menus -------------------------------------------------------------
    def _menus(self) -> list:
        return [
            ('File', [
                MenuItem(text='New', on_activate=lambda w: self._new()),
                MenuItem(text='Save', shortcut='<ctrl-s>',
                         on_activate=lambda w: self._save()),
                Separator(),
                MenuItem(text='Play it', shortcut='<ctrl-p>',
                         on_activate=lambda w: self._play()),
                Separator(),
                MenuItem(text='Quit', on_activate=lambda w: self.OnQuit()),
            ]),
            ('Edit', [
                MenuItem(text='Undo', shortcut='<ctrl-z>',
                         on_activate=lambda w: self._undo()),
                MenuItem(text='Redo', shortcut='<ctrl-y>',
                         on_activate=lambda w: self._redo()),
            ]),
            ('Board', [
                MenuItem(text='Clock', submenu=self._clock_items()),
                Separator(),
                MenuItem(text='Start again from a generated board',
                         on_activate=lambda w: self._regenerate()),
            ]),
            ('Story', self._chapter_items()),
            ('Place', self._mechanism_items()),
            ('Surface', self._surface_items()),
            ('View', [
                MenuItem(text='Fit the board', shortcut='f',
                         on_activate=lambda w: self._frame_all()),
                MenuItem(text='Zoom in',
                         on_activate=lambda w: self.controls.zoom(1.0 / ZOOM_STEP)),
                MenuItem(text='Zoom out',
                         on_activate=lambda w: self.controls.zoom(ZOOM_STEP)),
            ]),
        ]

    def _chapter_items(self) -> list:
        """The library, as a menu: a chapter added to the end of the board.

        A submenu per fragment holding its variants, because what a designer is
        choosing is not only *which* chapter but which of its faces -- the icy
        plateau and the ordinary one are the same chapter and different rooms.
        """
        items = []
        for name, entry in sorted(CHAPTERS().items()):
            variants = []
            for variant in entry.variants:
                item = MenuItem(text=variant)
                item.on_activate = (lambda widget, name=name, variant=variant:
                                    self._add_chapter(name, variant))
                variants.append(item)
            items.append(MenuItem(text=_titled(name), submenu=variants))
        return items

    def _add_chapter(self, name: str, variant: str) -> None:
        """Put a chapter on the end of the board, and frame what is now there."""
        try:
            add_chapter(self.editor, name, variant=variant)
        except (KeyError, ValueError) as error:
            self._say(str(error))
            return
        self._frame_all()
        rule = CHAPTERS()[name].rule
        self._say('Added %s/%s%s' % (name, variant, ': ' + rule if rule else ''))

    def _mechanism_items(self) -> list:
        """What the mechanism tool puts down, and which it is on."""
        tool = self.tools.named('mechanisms')
        items = [MenuItem(text='%s  (%d)' % (PLACEABLE[kind][0], number),
                          checkable=True, checked=(kind == tool.kind))
                 for number, kind in enumerate(PLACEABLE_ORDER, start=1)]
        for item, kind in zip(items, PLACEABLE_ORDER, strict=True):
            item.on_activate = (lambda widget, kind=kind, items=items:
                                self._choose_mechanism(kind, items))
        return items

    def _choose_mechanism(self, kind: str, items: list) -> None:
        for item, offered in zip(items, PLACEABLE_ORDER, strict=True):
            item.checked = (offered == kind)
        self.tools.named('mechanisms').kind = kind
        self.tools.select('mechanisms')
        self._report()

    def _surface_items(self) -> list:
        tool = self.tools.named('surface')
        items = [MenuItem(text='%s  (%d)' % (name, number), checkable=True,
                          checked=(name == tool.surface))
                 for number, name in enumerate(SURFACE_NAMES, start=1)]
        for item, name in zip(items, SURFACE_NAMES, strict=True):
            item.on_activate = (lambda widget, name=name, items=items:
                                self._choose_surface(name, items))
        return items

    def _choose_surface(self, name: str, items: list) -> None:
        for item, offered in zip(items, SURFACE_NAMES, strict=True):
            item.checked = (offered == name)
        self.tools.named('surface').surface = name
        self.tools.select('surface')
        self._report()

    def _clock_items(self) -> list:
        """The clocks a board is offered.  A ladder rather than a number to
        type: what a designer chooses is how much time a run has, and the useful
        settings for a board of this size are a handful."""
        offered = (15.0, 20.0, 30.0, 45.0, 60.0, 90.0)
        items = [MenuItem(text='%d seconds' % seconds, checkable=True,
                          checked=(seconds == self.editor.level.time_limit))
                 for seconds in offered]
        for item, seconds in zip(items, offered, strict=True):
            item.on_activate = (lambda widget, seconds=seconds, items=items,
                                offered=offered: self._choose_clock(
                                    seconds, items, offered))
        return items

    def _choose_clock(self, seconds: float, items: list, offered: tuple) -> None:
        for item, value in zip(items, offered, strict=True):
            item.checked = (value == seconds)
        self.editor.set_time_limit(seconds)

    def _new(self) -> None:
        self.editor.open_level(blank())
        self._frame_all()
        self._say('A new board.')

    def _regenerate(self) -> None:
        """Replace the board with a freshly generated one, to edit from.

        Generating is the quickest way to a board worth changing, and a designer
        who wants a hand-made one starts from New instead.  The seed moves on
        each time, so asking again is asking for a different board.
        """
        self.config.seed += 1
        self.editor.open_level(generator.generate(seed=self.config.seed,
                                                  difficulty=self.config.difficulty))
        self._frame_all()
        self._say('Generated board %d.' % self.config.seed)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description='Edit a marble board')
    parser.add_argument('board', nargs='?', default=None,
                        help='a %s file to open; a blank board without one'
                             % levelfile.SUFFIX)
    parser.add_argument('--from-seed', type=int, default=None, dest='seed',
                        metavar='SEED',
                        help='start from a generated board instead of a blank one')
    parser.add_argument('--difficulty', type=int, default=2,
                        help='difficulty of the generated board')
    parser.add_argument('--size', nargs=2, type=int, default=None,
                        metavar=('WIDTH', 'HEIGHT'),
                        help="the window's size in pixels, which is a "
                             "recording's size too")
    parser.add_argument('--tour', action='store_true',
                        help='play a scripted sitting at the editor -- every '
                             'tool in turn, through the handlers a hand uses')
    parser.add_argument('--record', metavar='PATH',
                        help='record the session to PATH (an .mp4) and quit '
                             'when the recording is done')
    parser.add_argument('--record-seconds', type=float, default=30.0,
                        metavar='SECONDS', help='how long a recording runs for')
    parser.add_argument('--record-fps', type=int, default=30, metavar='FPS',
                        help='frames a second in the recording')
    parser.add_argument('--record-bitrate', type=int, default=0, metavar='BITS',
                        help='bits a second; 0 lets the encoder choose')
    return parser


def starting_level(arguments):
    """The board the editor opens on, and where it came from.

    Three ways in, in the order they are asked for: a file named on the command
    line, a generated board, or a blank rectangle.  A named file that is not
    there is an error rather than a blank board, because a designer who mistyped
    a name wants to know rather than to start again by accident.
    """
    if arguments.board:
        return levelfile.load(arguments.board), arguments.board
    if arguments.seed is not None:
        return generator.generate(seed=arguments.seed,
                                  difficulty=arguments.difficulty), None
    return blank(), None


def main(argv=None) -> int:
    logging.basicConfig(level=logging.INFO)
    arguments = build_parser().parse_args(argv)
    try:
        level, path = starting_level(arguments)
    except (OSError, ValueError) as error:
        print('%s' % error, file=sys.stderr)
        return 1

    EditorContext.config = SimpleNamespace(
        level=level, path=path, difficulty=arguments.difficulty,
        tour=arguments.tour, record=arguments.record,
        record_options={
            'fps': arguments.record_fps, 'seconds': arguments.record_seconds,
            **({'bitrate': arguments.record_bitrate}
               if arguments.record_bitrate else {})},
        # Where "start again from a generated board" counts from; it moves on
        # each time, so asking again asks for a different board.
        seed=arguments.seed if arguments.seed is not None else 0)
    if arguments.size:
        EditorContext.ContextMainLoop(size=tuple(arguments.size))
    else:
        EditorContext.ContextMainLoop()
    return 0


if __name__ == '__main__':
    sys.exit(main())
