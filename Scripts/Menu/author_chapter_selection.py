"""Author and cold-audit the chapter selector, main menu wiring and arrival title.

Run in the root-owned UnrealEditor-Cmd lease with UMGToolSet enabled.
CATRUN_CHAPTER_MODE accepts probe, author, maps, or audit. Author and maps
are separate so all changes to each level can share the same editor lease.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sys
import traceback

import unreal as u

ROOT = Path(u.Paths.project_dir()).resolve()
sys.path.insert(0, str(ROOT / 'Scripts/Menu'))
from menu_graph import BP, Graph, add, compile_bp, editor, entry, event, literal, pin, properties, ui, widgets, wire

OUT = ROOT / 'Saved/Chapters20261112'
OUT.mkdir(parents=True, exist_ok=True)
AS = u.EditorAssetLibrary
MAIN = '/Game/UI/WBP_MainMenu'
BASE = '/Game/UI/Continue/'
SELECTOR = BASE + 'WBP_ChapterSelect'
TITLE = BASE + 'WBP_StageTitle'
DIRECTOR = BASE + 'BP_StageEntryPresentation'
FONT_PATH = '/Game/Environment/Font/HSBombaram3_0_Regular_Font'
CHAPTERS = (('Tutorial', '마왕의 침실'), ('Stage1', '연회장'), ('Stage2', '마법회랑'))
MAPS = tuple('/Game/Maps/' + prefix + stage for stage, _ in CHAPTERS for prefix in ('', 'SoundTest_'))
NATIVE_MENU = '/Script/Catrun.CatrunMenuProgressWidget'
NATIVE_SELECTOR = '/Script/Catrun.CatrunChapterSelectWidget'
FLOW = '/Script/Catrun.CatrunLevelFlowLibrary:'
WIDGET = '/Script/UMG.Widget:'
USER_WIDGET = '/Script/UMG.UserWidget:'
TEXT = '/Script/UMG.TextBlock:'
SYSTEM = '/Script/Engine.KismetSystemLibrary:'
MATH = '/Script/Engine.KismetMathLibrary:'
WHITE = u.LinearColor(1, 1, 1, 1)
IVORY = u.LinearColor(.90, .79, .61, 1)
MUTED = u.LinearColor(.63, .59, .54, 1)
GOLD = u.LinearColor(.77, .53, .20, 1)
RULE = u.LinearColor(.49, .32, .13, .68)
FRAME = u.LinearColor(.33, .22, .10, .9)
LOCKED_TEXT = '아직 도달하지 않음'
PANEL_WIDTH, PANEL_HEIGHT = 1176, 440
CARD_WIDTH, CARD_HEIGHT = 360, 276
TITLE_Y, TITLE_IN, TITLE_HOLD, TITLE_OUT = 88, .5, 2.5, .7
TITLE_END = TITLE_IN + TITLE_HOLD + TITLE_OUT


def dump(name, data):
    (OUT / name).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')


def progress(label):
    print('CATRUN_CHAPTER_PROGRESS ' + label)
    (OUT / 'progress.txt').write_text(label, encoding='utf-8')


def file_for(path):
    return ROOT / 'Content' / (path.removeprefix('/Game/') + ('.umap' if path in MAPS else '.uasset'))


def sha(file):
    return hashlib.sha256(file.read_bytes()).hexdigest()


def asset(path):
    result = AS.load_asset(path)
    assert result, path
    return result


def save(bp):
    assert AS.save_loaded_asset(bp, False), bp.get_path_name()


def dirty_packages():
    io = u.EditorLoadingAndSavingUtils
    return {p.get_path_name() for p in (*io.get_dirty_map_packages(), *io.get_dirty_content_packages())}


def backup(path):
    assert path not in dirty_packages(), ('Unexpected dirty package', path)
    source = file_for(path)
    destination = OUT / 'Backups' / source.relative_to(ROOT / 'Content')
    destination.parent.mkdir(parents=True, exist_ok=True)
    if not destination.exists():
        shutil.copy2(source, destination)
    return {'asset': path, 'backup': str(destination), 'backup_sha256': sha(destination), 'before_sha256': sha(source)}


def brush(color, draw_as=u.SlateBrushDrawType.BOX):
    return u.SlateBrush(tint_color=u.SlateColor(specified_color=color), draw_as=draw_as, margin=u.Margin(0))


def rect(widget, x, y, width, height, anchor=(0, 0), align=(0, 0), z=0):
    slot = widget.get_editor_property('slot')
    properties(slot, z_order=z, layout_data=u.AnchorData(
        offsets=u.Margin(x, y, width, height), alignment=u.Vector2D(*align),
        anchors=u.Anchors(minimum=u.Vector2D(*anchor), maximum=u.Vector2D(*anchor))))
    return widget


def stretch(widget, margin=0, z=0):
    slot = widget.get_editor_property('slot')
    properties(slot, z_order=z, layout_data=u.AnchorData(
        offsets=u.Margin(margin, margin, margin, margin),
        anchors=u.Anchors(minimum=u.Vector2D(margin, margin), maximum=u.Vector2D(1-margin, 1-margin))))
    return widget


def block(bp, name, parent, color, variable=False):
    widget = add(bp, u.Border, name, parent, variable)
    properties(widget, background=brush(WHITE), brush_color=color, padding=u.Margin(0),
               visibility=u.SlateVisibility.HIT_TEST_INVISIBLE)
    return widget


def label(bp, name, parent, value, size, color, variable=False, centered=True):
    widget = add(bp, u.TextBlock, name, parent, variable)
    properties(widget, text=u.Text(value), font=u.SlateFontInfo(font_object=asset(FONT_PATH),
               typeface_font_name='Default', size=size), color_and_opacity=u.SlateColor(specified_color=color),
               justification=u.TextJustify.CENTER if centered else u.TextJustify.LEFT,
               visibility=u.SlateVisibility.HIT_TEST_INVISIBLE)
    return widget


def transparent_button(bp, name, parent):
    widget = add(bp, u.Button, name, parent, True)
    invisible = brush(WHITE, u.SlateBrushDrawType.NO_DRAW_TYPE)
    style = widget.get_editor_property('widget_style')
    for state in ('normal', 'hovered', 'pressed', 'disabled'):
        style.set_editor_property(state, invisible)
    style.set_editor_property('normal_padding', u.Margin(0))
    style.set_editor_property('pressed_padding', u.Margin(0))
    properties(widget, widget_style=style, is_focusable=False)
    return widget


def thumbnail(stage):
    path = BASE + 'Thumbnails/T_Chapter_' + stage
    if not AS.does_asset_exist(path):
        return None
    texture = asset(path)
    assert isinstance(texture, u.Texture2D), path
    return texture


def make_widget(path, parent):
    folder, name = path.rsplit('/', 1)
    assert not AS.does_asset_exist(path), ('Refusing to replace an existing asset', path)
    bp = ui('CreateWidgetBlueprint', folder, name, parent)
    assert bp, path
    return bp


def call(q, widget, function, **values):
    return q.fn(function, target=q.ref(widget), **values)


def add_event(bp, name, y):
    node = BP.add_event(bp, name, u.IntPoint(0, y))
    assert node and node.get_class().get_name() == 'K2Node_Event', (bp.get_name(), name)
    return node


def set_visible(q, widget, show):
    return call(q, widget, WIDGET + 'SetVisibility', InVisibility='HitTestInvisible' if show else 'Hidden')


def hover_underline(bp, button, name, y):
    graph = BP.get_graph(bp, 'EventGraph')
    for delegate, show in (('OnHovered', True), ('OnUnhovered', False)):
        node = event(bp, button, delegate)
        node.set_node_pos(u.IntPoint(0, y))
        q = Graph(graph, 350, y)
        q.chain(node, set_visible(q, name, show))
        y += 225


def make_selector():
    bp = make_widget(SELECTOR, u.CatrunChapterSelectWidget.static_class())
    root = add(bp, u.CanvasPanel, 'ChapterCanvas', None)
    scrim = block(bp, 'ChapterScrim', root, u.LinearColor(.013, .012, .015, .88))
    properties(scrim, visibility=u.SlateVisibility.VISIBLE)
    stretch(scrim)
    fit = add(bp, u.ScaleBox, 'ChapterViewportFit', root)
    properties(fit, stretch=u.Stretch.SCALE_TO_FIT, stretch_direction=u.StretchDirection.DOWN_ONLY)
    stretch(fit, .04, 1)
    bounds = add(bp, u.SizeBox, 'ChapterPanelBounds', fit)
    bounds.set_width_override(PANEL_WIDTH)
    bounds.set_height_override(PANEL_HEIGHT)
    properties(bounds.get_editor_property('slot'), horizontal_alignment=u.HorizontalAlignment.H_ALIGN_CENTER,
               vertical_alignment=u.VerticalAlignment.V_ALIGN_CENTER)
    panel = add(bp, u.CanvasPanel, 'ChapterPanel', bounds)
    rect(label(bp, 'ChapterHeading', panel, '이어하기', 40, IVORY), 24, 0, 1128, 57)
    rect(block(bp, 'ChapterRule', panel, RULE), 24, 69, 1128, 1)
    cards = add(bp, u.HorizontalBox, 'ChapterCards', panel)
    rect(cards, 24, 94, 1128, CARD_HEIGHT)
    for index, (stage, name) in enumerate(CHAPTERS):
        card = add(bp, u.SizeBox, stage + 'Bounds', cards)
        card.set_width_override(CARD_WIDTH)
        card.set_height_override(CARD_HEIGHT)
        properties(card.get_editor_property('slot'), padding=u.Margin(24 if index else 0, 0, 0, 0))
        content = add(bp, u.CanvasPanel, stage + 'Card', card)
        button = transparent_button(bp, stage + 'Button', content)
        properties(button, is_enabled=False)
        stretch(button)
        artwork = add(bp, u.CanvasPanel, stage + 'Artwork', content, True)
        properties(artwork, visibility=u.SlateVisibility.HIT_TEST_INVISIBLE, render_opacity=.46)
        stretch(artwork, z=1)
        rect(block(bp, stage + 'Frame', artwork, FRAME), 0, 0, 360, 203.375)
        image = add(bp, u.Image, stage + 'Image', artwork)
        texture = thumbnail(stage)
        if texture:
            image.set_brush_from_texture(texture, False)
        else:
            properties(image, brush=brush(u.LinearColor(.038, .032, .033, 1)))
            rect(label(bp, stage + 'MissingPreview', artwork, '미리보기 없음', 20, MUTED),
                 12, 84, 336, 35, z=1)
        properties(image, visibility=u.SlateVisibility.HIT_TEST_INVISIBLE)
        rect(image, 1, 1, 358, 201.375)
        rect(label(bp, stage + 'Name', artwork, name, 30, IVORY, True), 8, 212, 344, 38)
        rect(label(bp, stage + 'Locked', content, LOCKED_TEXT, 18, MUTED, True), 8, 248, 344, 28, z=2)
        line = rect(block(bp, stage + 'Underline', content, GOLD, True), 101, 248, 158, 1, z=3)
        properties(line, visibility=u.SlateVisibility.HIDDEN)
    rect(block(bp, 'ChapterFooterRule', panel, RULE), 24, 381, 1128, 1)
    back = transparent_button(bp, 'ChapterBack', panel)
    rect(back, 24, 394, 106, 42)
    rect(label(bp, 'ChapterBackLabel', panel, '뒤로', 26, IVORY, centered=False), 24, 399, 106, 36, z=1)
    line = rect(block(bp, 'ChapterBackUnderline', panel, GOLD, True), 24, 432, 50, 1, z=2)
    properties(line, visibility=u.SlateVisibility.HIDDEN)
    rect(label(bp, 'ChapterStatus', panel, '', 21, MUTED, True), 162, 400, 852, 38, z=1)
    compile_bp(bp)

    graph = BP.get_graph(bp, 'EventGraph')
    refresh = add_event(bp, 'RefreshChapterPresentation', 0)
    status = (Graph(graph, 100, -150).get('StatusMessage', NATIVE_SELECTOR), 'StatusMessage')
    q = Graph(graph, 400, 0)
    last = q.chain(refresh, call(q, 'ChapterStatus', TEXT + 'SetText', InText=status))
    for index, (stage, _) in enumerate(CHAPTERS):
        presentation = chapter_function(bp, stage)
        compile_bp(bp)
        q.chain(last, q.fn(presentation))
        last = q.nodes[-1]
        y = 800 + 950 * index
        button = widgets(bp)[stage + 'Button']
        clicked = event(bp, button, 'OnClicked')
        clicked.set_node_pos(u.IntPoint(0, y))
        click_graph = Graph(graph, 350, y)
        click_graph.chain(clicked, click_graph.fn(NATIVE_SELECTOR + ':SelectChapter', StageId=stage))
        hover_underline(bp, button, stage + 'Underline', y + 325)
    back = widgets(bp)['ChapterBack']
    clicked = event(bp, back, 'OnClicked')
    clicked.set_node_pos(u.IntPoint(0, 3650))
    q = Graph(graph, 350, 3650)
    q.chain(clicked, q.fn(NATIVE_SELECTOR + ':CloseChapterSelection'))
    hover_underline(bp, back, 'ChapterBackUnderline', 3975)
    compile_bp(bp)
    return bp


def make_break_chapter(q, source):
    typed = pin(source, 'ReturnValue', True)
    actions = list(dict.fromkeys(str(name) for name in q.e.list_available_nodes([typed])))
    matches = [name for name in actions if re.sub(r'[^a-z0-9]', '', name.lower()).endswith('breakcatrunchapterinfo')]
    assert len(matches) == 1, ('Break Chapter Info action', matches, actions)
    node = q.placed(q.e.create_node_from_name(matches[0], u.Vector2D(q.x, q.y), [typed]))
    assert node.get_class().get_name() == 'K2Node_BreakStruct'
    inputs = BP.get_node_infos([node])[0].input_pins
    assert len(inputs) == 1, inputs
    target = pin(node, inputs[0].name)
    if not target.list_connected_pins():
        wire(source, 'ReturnValue', node, inputs[0].name)
    return node


def chapter_function(bp, stage):
    name = 'Refresh' + stage + 'Card'
    q = Graph(BP.add_function_graph(bp, name), 300, 0)
    chapter = q.fn(NATIVE_SELECTOR + ':GetChapter', StageId=stage)
    fields = make_break_chapter(q, chapter)
    available = q.fn(NATIVE_SELECTOR + ':CanSelectChapter', StageId=stage)
    title = call(q, stage + 'Name', TEXT + 'SetText', InText=(fields, 'DisplayName'))
    enabled = call(q, stage + 'Button', WIDGET + 'SetIsEnabled', bInIsEnabled=(available, 'ReturnValue'))
    clear_hover = set_visible(q, stage + 'Underline', False)
    state = q.branch((fields, 'bUnlocked'))
    q.chain(entry(q), title, enabled, clear_hover, state)
    for outgoing, opacity, locked in (('then', 1, False), ('else', .46, True)):
        q.y += 225
        q.x = 1900
        tint = call(q, stage + 'Artwork', WIDGET + 'SetRenderOpacity', InOpacity=opacity)
        wire(state, outgoing, tint, 'execute')
        q.chain(tint, set_visible(q, stage + 'Locked', locked))
    return bp.generated_class().get_path_name() + ':' + name


def node_infos(graph):
    return BP.get_node_infos(BP.find_nodes(graph))


def names(graph):
    return {item.node.get_name(): item.node for item in node_infos(graph)}


def graph_snapshot(graph, omitted=()):
    result = {}
    for item in node_infos(graph):
        node = item.node
        if node.get_name() in omitted:
            continue
        pins = []
        for p in node.list_all_pins():
            pins.append((str(p.get_pin_direction()), str(p.get_pin_name()), str(p.get_pin_value()), sorted(
                (other.get_owning_node().get_name(), str(other.get_pin_name()))
                for other in p.list_connected_pins() if other.get_owning_node().get_name() not in omitted)))
        result[node.get_name()] = [item.type_id, item.position.x, item.position.y, pins]
    return result


def digest(data):
    return hashlib.sha256(json.dumps(data, ensure_ascii=False, sort_keys=True).encode('utf-8')).hexdigest()


def main_widgets_snapshot(bp):
    return {name: [item.get_class().get_path_name(), item.get_parent().get_name() if item.get_parent() else None,
                   str(item.get_editor_property('visibility')), str(item.get_editor_property('render_opacity'))]
            for name, item in widgets(bp).items()}


def target_pin_key(p):
    return p.get_owning_node().get_name(), str(p.get_pin_name())


def linked_to(node, out, expected):
    links = [target_pin_key(other) for other in pin(node, out, True).list_connected_pins()]
    assert links == [expected], (node.get_name(), out, links, expected)


LEGACY_REFRESH = {
    'K2Node_CallFunction_1', 'K2Node_VariableGet_0', 'K2Node_CallFunction_2', 'K2Node_CallFunction_3',
    'K2Node_CallFunction_24', 'K2Node_CommutativeAssociativeBinaryOperator_0', 'K2Node_CallFunction_25',
    'K2Node_IfThenElse_0', 'K2Node_VariableGet_1', 'K2Node_CallFunction_26',
    'K2Node_VariableGet_2', 'K2Node_CallFunction_27',
}
LEGACY_CLICK = {'K2Node_CallFunction_28', 'K2Node_IfThenElse_1'}


def validate_main_menu_original(bp):
    graph = BP.get_graph(bp, 'EventGraph')
    items = {item.node.get_name(): item for item in node_infos(graph)}
    assert BP.get_parent(bp) == u.UserWidget.static_class(), ('Original MainMenu parent', BP.get_parent(bp))
    for name, action in (
        ('K2Node_CallFunction_0', 'StartNewGame'), ('K2Node_CallFunction_1', 'HasContinueGame'),
        ('K2Node_CallFunction_3', 'GetContinueStageLabel'), ('K2Node_CallFunction_28', 'ContinueGame'),
        ('K2Node_ComponentBoundEvent_0', 'OnClicked(ContinueButton)'),
        ('K2Node_ComponentBoundEvent_1', 'OnClicked(EndButton)'),
        ('K2Node_ComponentBoundEvent_2', 'OnClicked(OptionButton)'),
    ):
        assert items[name].type_id.endswith('|' + action), (name, items[name].type_id)
    for origin, out, destination, incoming in (
        ('K2Node_Event_1', 'then', 'K2Node_CallFunction_2', 'execute'),
        ('K2Node_ComponentBoundEvent_0', 'then', 'K2Node_CallFunction_28', 'execute'),
        ('K2Node_IfThenElse_1', 'else', 'K2Node_CallFunction_29', 'execute'),
    ):
        linked_to(items[origin].node, out, (destination, incoming))
    # The designer content, all unrelated graphs and surviving EventGraph nodes
    # will be checked again after the narrowly scoped Continue replacement.
    for item in [items[name] for name in LEGACY_REFRESH | LEGACY_CLICK]:
        for p in item.node.list_all_pins():
            for other in p.list_connected_pins():
                endpoint, label = target_pin_key(other)
                assert endpoint in LEGACY_REFRESH | LEGACY_CLICK or (endpoint, label) in {
                    ('K2Node_Event_1', 'then'), ('K2Node_ComponentBoundEvent_0', 'then'),
                    ('K2Node_CallFunction_29', 'execute'),
                }, (item.node.get_name(), endpoint, label)
    return graph


def named_action(q, name, ending):
    options = sorted(set(BP.find_node_types(q.g, name)))
    matches = [kind for kind in options if re.sub(r'[^a-z0-9]', '', kind.lower()).endswith(ending)]
    assert len(matches) == 1, (name, options)
    return q.placed(BP.create_node(q.g, matches[0], u.IntPoint(q.x, q.y)))


def graph_digests(bp, owned):
    return {g.get_name(): digest(graph_snapshot(g, owned if g.get_name() == 'EventGraph' else ()))
            for g in BP.list_graphs(bp)}


def patch_main_menu(bp):
    graph = validate_main_menu_original(bp)
    original_graphs = graph_digests(bp, LEGACY_REFRESH | LEGACY_CLICK)
    original_widgets = digest(main_widgets_snapshot(bp))
    before = names(graph)
    editor(graph).remove_nodes([before[name] for name in sorted(LEGACY_REFRESH | LEGACY_CLICK)])
    BP.set_parent(bp, u.CatrunMenuProgressWidget.static_class())
    assert BP.get_parent(bp) == u.CatrunMenuProgressWidget.static_class()
    refresh = add_event(bp, 'RefreshContinue', 4700)
    q = Graph(graph, 400, 4700)
    available = q.fn(FLOW + 'HasContinueGame')
    status = q.fn(FLOW + 'GetContinueStageLabel')
    enable = call(q, 'ContinueButton', WIDGET + 'SetIsEnabled', bInIsEnabled=(available, 'ReturnValue'))
    text = call(q, 'ContinueStageHint', TEXT + 'SetText', InText=(status, 'ReturnValue'))
    q.chain(refresh, enable, text)

    q = Graph(graph, 400, 5000)
    owner = q.fn(WIDGET + 'GetOwningPlayer')
    self_node = named_action(q, 'Variables|Getareferencetoself', 'getareferencetoself')
    assert self_node.get_class().get_name() == 'K2Node_Self'
    (self_output,) = BP.get_node_infos([self_node])[0].output_pins
    opened = q.fn(NATIVE_SELECTOR + ':OpenChapterSelection', PlayerController=(owner, 'ReturnValue'),
                  SourcePanel=(self_node, self_output.name), ReturnFocus=q.ref('ContinueButton'))
    valid = q.fn(SYSTEM + 'IsValid', Object=(opened, 'ReturnValue'))
    accepted = q.branch((valid, 'ReturnValue'))
    q.chain(before['K2Node_ComponentBoundEvent_0'], opened, accepted)
    wire(accepted, 'else', before['K2Node_CallFunction_29'], 'execute')
    compile_bp(bp)
    added = sorted(names(graph).keys() - before.keys())
    # Unreal may reuse freed numeric node suffixes. Include all nodes whose
    # objects were explicitly authored, even when the new name equals a removed one.
    added = sorted(set(added) | {n.get_name() for n in [refresh, *q.nodes, available, status, enable, text]
                                if n} | (set(names(graph)) & (LEGACY_REFRESH | LEGACY_CLICK)))
    assert original_graphs == graph_digests(bp, added), 'Unrelated MainMenu graph content changed'
    assert original_widgets == digest(main_widgets_snapshot(bp)), 'MainMenu designer changed'
    linked_to(before['K2Node_ComponentBoundEvent_0'], 'then', (opened.get_name(), 'execute'))
    return {'preserved_graph_digests': original_graphs, 'preserved_widget_digest': original_widgets,
            'new_event_nodes': added}


def make_title():
    bp = make_widget(TITLE, u.UserWidget.static_class())
    canvas = add(bp, u.CanvasPanel, 'StageTitleCanvas', None)
    properties(canvas, visibility=u.SlateVisibility.HIT_TEST_INVISIBLE)
    title = label(bp, 'StageTitleText', canvas, '', 46, IVORY, True)
    properties(title, render_opacity=0.0, shadow_offset=u.Vector2D(1.5, 2),
               shadow_color_and_opacity=u.LinearColor(0, 0, 0, .90))
    rect(title, 0, TITLE_Y, 760, 72, anchor=(.5, 0), align=(.5, 0))
    BP.add_variable(bp, 'ElapsedSeconds', 'float')
    set_title = BP.add_function_graph(bp, 'SetStageTitle')
    BP.add_function_param(set_title, 'TitleText', 'text', True)
    compile_bp(bp)

    q = Graph(set_title, 350, 0)
    start = entry(q)
    q.chain(start, call(q, 'StageTitleText', TEXT + 'SetText', InText=(start, 'TitleText')))

    graph = BP.get_graph(bp, 'EventGraph')
    tick = add_event(bp, 'Tick', 0)
    q = Graph(graph, 350, 0)
    next_time = q.fn(MATH + 'Add_DoubleDouble', A=q.ref('ElapsedSeconds'), B=(tick, 'InDeltaTime'))
    elapsed = q.set('ElapsedSeconds', source=(next_time, 'ReturnValue'))
    current = q.ref('ElapsedSeconds')
    done = q.fn(MATH + 'GreaterEqual_DoubleDouble', A=current, B=TITLE_END)
    finished = q.branch((done, 'ReturnValue'))
    q.chain(tick, elapsed, finished)
    remove = q.fn(WIDGET + 'RemoveFromParent')
    wire(finished, 'then', remove, 'execute')
    fade_in = q.fn(MATH + 'MapRangeClamped', Value=current, InRangeA=0, InRangeB=TITLE_IN,
                   OutRangeA=0, OutRangeB=1)
    fade_out = q.fn(MATH + 'MapRangeClamped', Value=current, InRangeA=TITLE_IN + TITLE_HOLD, InRangeB=TITLE_END,
                    OutRangeA=1, OutRangeB=0)
    opacity = q.fn(MATH + 'FMin', A=(fade_in, 'ReturnValue'), B=(fade_out, 'ReturnValue'))
    apply = call(q, 'StageTitleText', WIDGET + 'SetRenderOpacity', InOpacity=(opacity, 'ReturnValue'))
    wire(finished, 'else', apply, 'execute')
    # 등장 0.5초 / 유지 2.5초 / 퇴장 0.7초. 끝나면 위젯을 제거합니다.
    compile_bp(bp)
    return bp


def make_director(title):
    assert not AS.does_asset_exist(DIRECTOR), ('Refusing to replace an existing asset', DIRECTOR)
    folder, name = DIRECTOR.rsplit('/', 1)
    bp = BP.create(folder, name, u.Actor.static_class())
    BP.add_object_variable(bp, 'TitleWidget', title.generated_class())
    compile_bp(bp)
    cdo = u.get_default_object(bp.generated_class())
    tick = cdo.get_editor_property('primary_actor_tick')
    tick.set_editor_property('start_with_tick_enabled', False)
    properties(cdo, primary_actor_tick=tick)

    graph = BP.get_graph(bp, 'EventGraph')
    graph_editor = editor(graph)
    template_tick = graph_editor.find_event_node('ReceiveTick')
    if template_tick:
        assert not any(p.list_connected_pins() for p in template_tick.list_all_pins())
        graph_editor.remove_nodes([template_tick])
    begin = add_event(bp, 'ReceiveBeginPlay', 0)
    q = Graph(graph, 350, 0)
    delay = q.fn(SYSTEM + 'Delay', Duration=.45)
    owner = q.fn('/Script/Engine.GameplayStatics:GetPlayerController', PlayerIndex=0)
    controller = (owner, 'ReturnValue')
    is_valid = q.fn(SYSTEM + 'IsValid', Object=controller)
    has_owner = q.branch((is_valid, 'ReturnValue'))
    wire(begin, 'then', delay, 'execute')
    wait = q.fn(FLOW + 'WaitForStageTitleWindow')
    q.chain(delay, wait, has_owner)
    local = q.fn('/Script/Engine.Controller:IsLocalPlayerController', target=controller)
    local_gate = q.branch((local, 'ReturnValue'))
    wire(has_owner, 'then', local_gate, 'execute')
    consume = q.fn(FLOW + 'ConsumeStageTitle')
    wire(local_gate, 'then', consume, 'execute')
    allowed = q.branch((consume, 'ReturnValue'))
    q.chain(consume, allowed)
    create = named_action(q, 'CreateWidget', 'createwidget')
    literal(create, 'Class', title.generated_class().get_path_name())
    wire(owner, 'ReturnValue', create, 'OwningPlayer')
    wire(allowed, 'then', create, 'execute')
    cache = q.set('TitleWidget', source=(create, 'ReturnValue'))
    update = q.fn(title.generated_class().get_path_name() + ':SetStageTitle', target=q.ref('TitleWidget'),
                  TitleText=(consume, 'OutTitle'))
    passive = call(q, 'TitleWidget', WIDGET + 'SetVisibility', InVisibility='HitTestInvisible')
    viewport = call(q, 'TitleWidget', USER_WIDGET + 'AddToViewport', ZOrder=65)
    q.chain(create, cache, update, passive, viewport)
    # 도착 확정 시 발행한 제목을 한 번만 소비합니다.

    end = add_event(bp, 'ReceiveEndPlay', 1150)
    q = Graph(graph, 350, 1150)
    valid = q.fn(SYSTEM + 'IsValid', Object=q.ref('TitleWidget'))
    has_title = q.branch((valid, 'ReturnValue'))
    q.chain(end, has_title)
    remove = call(q, 'TitleWidget', WIDGET + 'RemoveFromParent')
    wire(has_title, 'then', remove, 'execute')
    compile_bp(bp)
    return bp


DIRECTOR_TAG = 'CatrunStageEntryPresentation'


def load_map(package):
    ed = u.get_editor_subsystem(u.UnrealEditorSubsystem)
    level = u.get_editor_subsystem(u.LevelEditorSubsystem)
    assert not dirty_packages(), ('Refusing dirty world switch', package, sorted(dirty_packages()))
    assert level.load_level(package), package
    world = ed.get_editor_world()
    assert world and world.get_path_name().split('.')[0] == package and not ed.get_game_world()
    return world, level


def map_actors(world):
    return list(u.GameplayStatics.get_all_actors_of_class(world, u.Actor))


def title_directors(world, bp):
    cls = bp.generated_class()
    return [a for a in map_actors(world) if a.get_class() == cls or DIRECTOR_TAG in {str(t) for t in a.tags}]


def stage_actor_snapshot(world, excluded=()):
    return {a.get_name(): [a.get_class().get_path_name(), a.get_actor_transform().export_text(),
                           sorted(str(t) for t in a.tags)]
            for a in map_actors(world) if a.get_name() not in excluded}


def place_director_in_loaded_map(world, bp):
    """Place a single passive director; caller owns the level transaction and save."""
    actors = title_directors(world, bp)
    assert len(actors) <= 1, ('Duplicated stage title actors', world.get_path_name())
    if actors:
        (actor,) = actors
        assert actor.get_class() == bp.generated_class() and DIRECTOR_TAG in {str(t) for t in actor.tags}
        return actor
    before = stage_actor_snapshot(world)
    subsystem = u.get_editor_subsystem(u.EditorActorSubsystem)
    actor = subsystem.spawn_actor_from_class(bp.generated_class(), u.Vector(), u.Rotator())
    assert actor and actor.get_world() == world
    actor.set_actor_label('Stage Entry Presentation')
    actor.set_editor_property('tags', [u.Name(DIRECTOR_TAG)])
    assert stage_actor_snapshot(world, {actor.get_name()}) == before, 'An existing actor changed'
    return actor


def author_maps():
    director = asset(DIRECTOR)
    report = {}
    for package in MAPS:
        progress('Placing stage title in ' + package)
        world, level = load_map(package)
        original = backup(package)
        actor = place_director_in_loaded_map(world, director)
        dirty = dirty_packages()
        assert dirty <= {package}, ('Unexpected dirty package', sorted(dirty))
        if dirty:
            assert level.save_current_level(), package
        report[package] = {**original, 'actor': actor.get_path_name(), 'saved_sha256': sha(file_for(package))}
        dump('maps.json', report)


def exactly_one(graph, suffix):
    matches = [i.node for i in node_infos(graph) if str(i.type_id).endswith(suffix)]
    assert len(matches) == 1, (graph.get_name(), suffix, len(matches))
    return matches[0]


def no_action(graph, suffix):
    assert not any(str(i.type_id).endswith(suffix) for i in node_infos(graph)), (graph.get_name(), suffix)


def audit_designer(selector, title):
    tree = widgets(selector)
    fit = tree['ChapterViewportFit']
    assert fit.get_editor_property('stretch') == u.Stretch.SCALE_TO_FIT
    assert fit.get_editor_property('stretch_direction') == u.StretchDirection.DOWN_ONLY
    assert tree['ChapterPanelBounds'].get_editor_property('width_override') == PANEL_WIDTH
    assert tree['ChapterPanelBounds'].get_editor_property('height_override') == PANEL_HEIGHT
    assert 0 < tree['ChapterScrim'].get_editor_property('brush_color').a < 1
    horizontal = tree['ChapterCards']
    assert horizontal.get_children_count() == 3 and isinstance(horizontal, u.HorizontalBox)
    cards = []
    for index, (stage, name) in enumerate(CHAPTERS):
        size = tree[stage + 'Bounds']
        assert horizontal.get_child_at(index) == size
        assert size.get_editor_property('width_override') == CARD_WIDTH
        assert size.get_editor_property('height_override') == CARD_HEIGHT
        assert size.get_editor_property('slot').get_editor_property('padding').left == (24 if index else 0)
        image = tree[stage + 'Image']
        layout = image.get_editor_property('slot').get_editor_property('layout_data').get_editor_property('offsets')
        assert abs(layout.right / layout.bottom - 16 / 9) < 0.0001
        resource = image.get_editor_property('brush').get_editor_property('resource_object')
        assert resource == thumbnail(stage)
        assert bool(resource) != (stage + 'MissingPreview' in tree)
        if resource:
            assert abs(resource.blueprint_get_size_x() / resource.blueprint_get_size_y() - 16 / 9) < .02
        assert str(tree[stage + 'Name'].get_editor_property('text')) == name
        assert str(tree[stage + 'Locked'].get_editor_property('text')) == LOCKED_TEXT
        assert tree[stage + 'Underline'].get_editor_property('visibility') == u.SlateVisibility.HIDDEN
        assert tree[stage + 'Name'].get_editor_property('font').get_editor_property('font_object') == asset(FONT_PATH)
        assert not tree[stage + 'Button'].get_editor_property('is_enabled')
        cards.append({'stage': stage, 'name': name, 'texture': resource.get_path_name() if resource else None,
                      'preview_size': [layout.right, layout.bottom]})
    title_tree = widgets(title)
    text = title_tree['StageTitleText']
    title_slot = text.get_editor_property('slot').get_editor_property('layout_data')
    anchors = title_slot.get_editor_property('anchors')
    assert anchors.minimum == anchors.maximum == u.Vector2D(.5, 0)
    assert title_slot.get_editor_property('alignment') == u.Vector2D(.5, 0)
    assert title_slot.get_editor_property('offsets').top == TITLE_Y
    assert text.get_editor_property('justification') == u.TextJustify.CENTER
    assert text.get_editor_property('font').get_editor_property('font_object') == asset(FONT_PATH)
    assert text.get_editor_property('render_opacity') == 0
    assert title_tree['StageTitleCanvas'].get_editor_property('visibility') == u.SlateVisibility.HIT_TEST_INVISIBLE
    return cards


def audit_graphs(main, selector, title, director, preservation):
    assert BP.get_parent(main) == u.CatrunMenuProgressWidget.static_class()
    assert BP.get_parent(selector) == u.CatrunChapterSelectWidget.static_class()
    for bp in (main, selector, title, director):
        assert bp.get_editor_property('status') == u.BlueprintStatus.BS_UP_TO_DATE, bp.get_path_name()
    assert preservation['preserved_graph_digests'] == graph_digests(main, preservation['new_event_nodes'])
    assert preservation['preserved_widget_digest'] == digest(main_widgets_snapshot(main))

    g = BP.get_graph(main, 'EventGraph')
    open_modal = exactly_one(g, '|OpenChapterSelection')
    click = exactly_one(g, '|OnClicked(ContinueButton)')
    linked_to(click, 'then', (open_modal.get_name(), 'execute'))
    no_action(g, '|ContinueGame')
    exactly_one(g, '|HasContinueGame')
    exactly_one(g, '|GetContinueStageLabel')
    assert editor(g).find_event_node('RefreshContinue')

    g = BP.get_graph(selector, 'EventGraph')
    assert editor(g).find_event_node('RefreshChapterPresentation')
    close = exactly_one(g, '|CloseChapterSelection')
    back = exactly_one(g, '|OnClicked(ChapterBack)')
    linked_to(back, 'then', (close.get_name(), 'execute'))
    selects = [i.node for i in node_infos(g) if str(i.type_id).endswith('|SelectChapter')]
    assert len(selects) == len(CHAPTERS)
    for stage, _ in CHAPTERS:
        (select,) = [n for n in selects if str(pin(n, 'StageId').get_pin_value()) == stage]
        click = exactly_one(g, '|OnClicked(' + stage + 'Button)')
        linked_to(click, 'then', (select.get_name(), 'execute'))
        for delegate in ('OnHovered', 'OnUnhovered'):
            exactly_one(g, '|' + delegate + '(' + stage + 'Button)')
        lane = BP.get_graph(selector, 'Refresh' + stage + 'Card')
        exactly_one(lane, '|GetChapter')
        exactly_one(lane, '|CanSelectChapter')
        exactly_one(lane, '|SetIsEnabled')

    g = BP.get_graph(title, 'EventGraph')
    assert editor(g).find_event_node('Tick')
    assert sum(str(i.type_id).endswith('|MapRangeClamped') for i in node_infos(g)) == 2
    exactly_one(g, '|SetRenderOpacity')
    exactly_one(g, '|RemoveFromParent')

    g = BP.get_graph(director, 'EventGraph')
    assert editor(g).find_event_node('ReceiveBeginPlay') and editor(g).find_event_node('ReceiveEndPlay')
    assert not editor(g).find_event_node('ReceiveTick')
    assert not u.get_default_object(director.generated_class()).get_editor_property(
        'primary_actor_tick').get_editor_property('start_with_tick_enabled')
    audit_title_wait(director)
    consume = exactly_one(g, '|ConsumeStageTitle')
    accept = pin(consume, 'ReturnValue', True).list_connected_pins()
    assert len(accept) == 1 and str(accept[0].get_pin_name()) == 'Condition'
    create = exactly_one(g, '|CreateWidget')
    linked_to(accept[0].get_owning_node(), 'then', (create.get_name(), 'execute'))
    set_title = exactly_one(g, '|SetStageTitle')
    linked_to(consume, 'OutTitle', (set_title.get_name(), 'TitleText'))
    exactly_one(g, '|AddToViewport')
    exactly_one(g, '|RemoveFromParent')


def audit_title_wait(director):
    graph = BP.get_graph(director, 'EventGraph')
    delay = exactly_one(graph, '|Delay')
    wait = exactly_one(graph, '|WaitForStageTitleWindow')
    linked_to(delay, 'then', (wait.get_name(), 'execute'))
    (resume,) = pin(wait, 'then', True).list_connected_pins()
    branch = resume.get_owning_node()
    assert str(resume.get_pin_name()) == 'execute' and branch.get_class().get_name() == 'K2Node_IfThenElse'
    consume = exactly_one(graph, '|ConsumeStageTitle')
    (local_check,) = pin(branch, 'then', True).list_connected_pins()
    linked_to(local_check.get_owning_node(), 'then', (consume.get_name(), 'execute'))
    assert director.get_editor_property('status') == u.BlueprintStatus.BS_UP_TO_DATE


def defer_existing_title():
    director = asset(DIRECTOR)
    graph = BP.get_graph(director, 'EventGraph')
    if any(str(i.type_id).endswith('|WaitForStageTitleWindow') for i in node_infos(graph)):
        audit_title_wait(director)
        return
    assert DIRECTOR not in dirty_packages()
    delay = exactly_one(graph, '|Delay')
    (resume,) = pin(delay, 'then', True).list_connected_pins()
    owner_gate = resume.get_owning_node()
    assert str(resume.get_pin_name()) == 'execute' and owner_gate.get_class().get_name() == 'K2Node_IfThenElse'
    output = pin(delay, 'then', True)
    BP.break_pins(BP._pin_to_id(output), BP._pin_to_id(resume))
    q = Graph(graph, 700, -280)
    wait = q.fn(FLOW + 'WaitForStageTitleWindow')
    q.chain(delay, wait, owner_gate)
    compile_bp(director)
    audit_title_wait(director)
    save(director)


def audit_saved(include_maps):
    preservation = json.loads((OUT / 'author.json').read_text(encoding='utf-8'))['menu']
    main, selector, title, director = [asset(p) for p in (MAIN, SELECTOR, TITLE, DIRECTOR)]
    audit_graphs(main, selector, title, director, preservation)
    cards = audit_designer(selector, title)
    report = {'cards': cards, 'stage_title_fade_seconds': [TITLE_IN, TITLE_HOLD, TITLE_OUT], 'maps': {}}
    if include_maps:
        for package in MAPS:
            progress('Cold reading stage title in ' + package)
            world, _ = load_map(package)
            (actor,) = title_directors(world, director)
            assert actor.get_class() == director.generated_class() and DIRECTOR_TAG in {str(t) for t in actor.tags}
            report['maps'][package] = {'actor': actor.get_path_name(), 'sha256': sha(file_for(package))}
    assert not dirty_packages(), sorted(dirty_packages())
    dump('audit.json', report)
    return report


def probe():
    main = asset(MAIN)
    graph = validate_main_menu_original(main)
    report = {'main_sha256': sha(file_for(MAIN)), 'main_menu_event_graph': graph_snapshot(graph),
              'main_menu_widgets': main_widgets_snapshot(main), 'font': asset(FONT_PATH).get_path_name(),
              'compiled_selector_base': u.CatrunChapterSelectWidget.static_class().get_path_name(),
              'compiled_menu_base': (u.CatrunMenuProgressWidget.static_class().get_path_name()
                                     if hasattr(u, 'CatrunMenuProgressWidget') else None),
              'thumbnail_paths': {stage: bool(thumbnail(stage)) for stage, _ in CHAPTERS}}
    dump('probe.json', report)


def author():
    assert not dirty_packages(), ('Unexpected dirty packages', sorted(dirty_packages()))
    main = asset(MAIN)
    validate_main_menu_original(main)
    report = {'main_menu_backup': backup(MAIN)}
    dump('author.json', report)
    progress('Chapter card designer and graphs')
    selector = make_selector()
    progress('Stage title designer and fade graph')
    title = make_title()
    progress('Stage entry presentation actor graph')
    director = make_director(title)
    progress('Main menu Continue click and save-state refresh')
    report['menu'] = patch_main_menu(main)
    progress('Saving verified assets')
    audit_graphs(main, selector, title, director, report['menu'])
    report['cards'] = audit_designer(selector, title)
    for bp in (selector, title, director, main):
        save(bp)
    report['after_sha256'] = {path: sha(file_for(path)) for path in (MAIN, SELECTOR, TITLE, DIRECTOR)}
    dump('author.json', report)


def main():
    ed = u.get_editor_subsystem(u.UnrealEditorSubsystem)
    assert ed and not ed.get_game_world()
    mode = os.environ.get('CATRUN_CHAPTER_MODE', 'probe').lower()
    actions = {'probe': probe, 'author': author, 'maps': author_maps, 'audit': lambda: audit_saved(True),
               'audit_widgets': lambda: audit_saved(False), 'defer_title': defer_existing_title,
               'audit_deferred_title': lambda: audit_title_wait(asset(DIRECTOR))}
    actions[mode]()
    print('CATRUN_CHAPTER_' + mode.upper() + '_COMPLETE')


if __name__ == '__main__':
    try:
        main()
    except Exception:
        (OUT / 'error.txt').write_text(traceback.format_exc(), encoding='utf-8')
        raise
