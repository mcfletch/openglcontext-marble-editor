"""The board as a drawing: what a designer can tell at a glance.

Building a scene is nodes rather than GL, so what the map shows is something to
assert rather than something to squint at. The three questions it has to answer
are how high a tile is, what it is made of, and what is standing on it.
"""
from openglcontext_marble_demo import generator
from openglcontext_marble_demo.level import Bumper, Finish, Ramp, Wall

from marble_editor import scene
from marble_editor.board import BoardEditor, blank


def _key(colour):
    return tuple(round(float(part), 4) for part in colour)


def _shapes(group):
    """The shapes a colour-grouped node holds, or the node itself."""
    if group is None:
        return []
    return list(getattr(group, 'children', [group]))


def _quads(group):
    """How many faces a node draws (each face's index run ends in a -1)."""
    return sum(list(shape.geometry.coordIndex).count(-1)
               for shape in _shapes(group))


def _colours(group):
    """The colour each shape of a node is drawn in."""
    return [tuple(round(float(part), 4)
                  for part in shape.appearance.material.baseColor)
            for shape in _shapes(group)]


def _points(group):
    """Every vertex of a node, in the order the shapes hold them."""
    return [tuple(float(part) for part in point)
            for shape in _shapes(group)
            for point in shape.geometry.coord.point]


def _colour_of(group, level, cell):
    """The colour the shape covering ``cell`` is drawn in.

    A quad's corners sit half a cell out from its centre, so the lookup is by
    which shape has a corner within half a cell of it at that cell's height.
    """
    size = level.cell_size
    x, z, y = cell[0] * size, cell[1] * size, level.cells[cell]
    for shape in _shapes(group):
        for point in shape.geometry.coord.point:
            if (abs(float(point[1]) - y) < 1e-6
                    and abs(float(point[0]) - x) <= size * 0.5 + 1e-6
                    and abs(float(point[2]) - z) <= size * 0.5 + 1e-6):
                return tuple(round(float(part), 4)
                             for part in shape.appearance.material.baseColor)
    raise AssertionError('nothing drawn at %r' % (cell,))


# -- the tiles -----------------------------------------------------------------

def test_there_is_one_quad_per_tile():
    level = blank(width=4, depth=6)
    assert _quads(scene.tiles(level)) == len(level.cells) == 24


def test_a_board_with_no_tiles_draws_none():
    level = blank(width=1, depth=1)
    level.cells.clear()
    assert scene.tiles(level) is None
    assert scene.grid(level) is None


def test_a_higher_tile_is_drawn_lighter():
    """Lightness is how the fall of a board is read without a number on it."""
    editor = BoardEditor(blank(width=3, depth=3))
    editor.raise_by((0, 1), 3)
    drawn = scene.tiles(editor.level)
    high = _colour_of(drawn, editor.level, (0, 1))
    low = _colour_of(drawn, editor.level, (0, 0))
    assert sum(high) > sum(low)


def test_a_tile_is_drawn_in_its_own_surfaces_colour():
    from openglcontext_marble_demo.materials import SURFACES
    editor = BoardEditor(blank(width=3, depth=3))
    editor.paint((0, 1), 'ice_sheet')
    painted = _colour_of(scene.tiles(editor.level), editor.level, (0, 1))
    ice, stone = SURFACES['ice_sheet'], SURFACES['stone']
    # Ice is bluer than stone; the shading scales a colour and cannot turn one
    # hue into another, so the comparison holds whatever height it is drawn at.
    assert painted[2] / max(painted[0], 1e-6) > ice.base_color[2] / ice.base_color[0] * 0.9
    assert ice.base_color[2] / ice.base_color[0] > stone.base_color[2] / stone.base_color[0]


def test_every_tile_is_drawn_flat_at_its_own_height():
    editor = BoardEditor(blank(width=3, depth=3))
    editor.raise_by((0, 1), 2)
    raised = round(editor.level.cells[(0, 1)], 6)
    at_height = [point for point in _points(scene.tiles(editor.level))
                 if round(point[1], 6) == raised]
    assert len(at_height) == 4                    # the one raised tile, flat


# -- the marks -----------------------------------------------------------------

def test_the_start_and_the_finish_are_both_marked():
    level = blank()
    level.features = []                       # even with no pad drawn
    assert _quads(scene.marks(level)) == 2


def test_a_mechanism_gets_a_mark():
    editor = BoardEditor(blank())
    before = _quads(scene.marks(editor.level))
    editor.place((0, 3), 'bumper')
    assert _quads(scene.marks(editor.level)) == before + 1


def test_a_ramp_is_marked_with_the_way_it_points():
    """A ramp and its tick: two faces where a bumper is one."""
    editor = BoardEditor(blank())
    plain = _quads(scene.marks(editor.level))
    editor.place((0, 3), 'ramp')
    assert _quads(scene.marks(editor.level)) == plain + 2


def test_a_launch_ramp_is_drawn_as_the_different_thing_it_is():
    level = blank()
    level.features = [Ramp(cell=(0, 3), launch=True)]
    assert _key(scene.LAUNCH_COLOUR) in [_key(c) for c in _colours(scene.marks(level))]


def test_a_rail_is_drawn_where_it_stands_rather_than_in_the_middle():
    level = blank(width=3, depth=3)
    level.features = [Wall(cell=(1, 1), side='E')]
    # The rail's corners sit beyond the cell's centre in +X; the markers for
    # the start and the finish are elsewhere on the board.
    beyond = [point for point in _points(scene.marks(level))
              if point[0] > 1 * level.cell_size]
    assert len(beyond) == 4


def test_a_mark_is_drawn_clear_of_the_tiles():
    """A mechanism on a low tile must not be buried by the high one beside it."""
    editor = BoardEditor(blank(width=3, depth=3))
    editor.place((0, 1), 'bumper')
    editor.raise_by((1, 1), 3)
    lifted = [point[1] for point in _points(scene.marks(editor.level))]
    assert min(lifted) > max(editor.level.cells.values())


def test_a_mechanism_on_a_cell_that_is_not_there_is_not_drawn():
    level = blank(width=3, depth=3)
    level.features = [Bumper(cell=(9, 9)), Finish(level.finish_cell)]
    quads = _quads(scene.marks(level))
    assert quads == 3          # the finish pad, the start marker, the finish marker


# -- the whole map -------------------------------------------------------------

def test_the_map_is_tiles_then_the_grid_then_the_marks():
    """Drawn in that order so nothing that matters is under something else."""
    from OpenGLContext.scenegraph.basenodes import Background

    level = generator.generate(seed=3, difficulty=2)
    graph = scene.board_scene(level)
    assert len(graph.children) == 4
    assert isinstance(graph.children[0], Background)


def test_the_board_says_what_the_frame_is_cleared_to():
    """A Background node, which is how a scene says it: set on the graph as a
    plain attribute it reached nothing, and the editor drew on whatever the
    window happened to start with."""
    from OpenGLContext.scenegraph.basenodes import Background

    level = generator.generate(seed=3, difficulty=2)
    graph = scene.board_scene(level, background=(0.2, 0.3, 0.4))
    background = graph.children[0]
    assert isinstance(background, Background)
    assert [round(float(channel), 3) for channel in background.skyColor[0]] == [
        0.2, 0.3, 0.4]


def test_every_generated_board_can_be_drawn():
    for seed in range(8):
        graph = scene.board_scene(generator.generate(seed=seed, difficulty=3))
        assert graph.children
