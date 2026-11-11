"""Bounded Designer/Blueprint patch. Run only in the root-owned editor commandlet.

Does not launch PIE, instantiate a game widget, change host settings, or restore old
assets. Both current assets are backed up before mutation; neither is saved until
both compile. A rerun reuses widgets/delegates and replaces only tagged task nodes.
"""
import datetime
import hashlib
import json
from pathlib import Path
import shutil
import sys
import traceback
import unreal

ROOT = Path(unreal.Paths.project_dir()).resolve()
sys.path.insert(0, str(ROOT / 'Scripts/Menu'))
from menu_graph import (BP, Graph, add, audit, compile_bp, editor, entry, event as create_bound_event,
                        literal, pin, properties, ui, widgets, wire, PROPERTY_SCHEMAS)

OUT = ROOT / 'Saved/GameplayRepair20261105/UI'
OUT.mkdir(parents=True, exist_ok=True)
RUN = OUT / datetime.datetime.now(datetime.timezone.utc).strftime('run-%Y%m%dT%H%M%S%fZ')
RUN.mkdir()
TAG = 'CATRUN_SETTINGS_REDESIGN_V1'
TAG_KEY = 'CatrunSettingsAuthor'
AS = unreal.EditorAssetLibrary
SETTINGS = '/Game/UI/Settings/WBP_Setting'
MENU = '/Game/UI/WBP_MainMenu'
N = '/Script/Catrun.CatrunSettingsWidget.'
S = '/Script/Catrun.CatrunUserSettings.'
NAV = '/Script/Catrun.CatrunSettingsSubsystem.IsNavigationFocused'
W = '/Script/UMG.Widget.'
T = '/Script/UMG.TextBlock.'
K = '/Script/Engine.KismetMathLibrary.'
SELECTOR = '/Script/UMG.InputKeySelector.'
KEYS = [('Forward', '앞으로 이동', 'W'), ('Back', '뒤로 이동', 'S'),
        ('Left', '왼쪽 이동', 'A'), ('Right', '오른쪽 이동', 'D'),
        ('Run', '달리기', 'LeftShift'), ('Sneak', '살금살금', 'LeftControl'),
        ('Bell', '방울', 'SpaceBar'), ('Interact', '상호작용', 'F')]
CATEGORIES = [('Screen', '화면', '화면 모드와 그래픽 품질을 조절하세요.'),
              ('Audio', '소리', '전체 음량을 조절하세요.'),
              ('Controls', '조작', '항목을 선택한 뒤 사용할 키 하나를 누르세요.'),
              ('Developer', '개발', '개발 테스트 설정은 이번 실행에만 유지됩니다.')]
FUNCTIONS = ['RefreshKeySelectors', 'RefreshBindingStatus', 'ResetAllDrafts',
             'InitializeSettingsPresentation', 'UpdateSettingsAffordances',
             'RebuildSettingsNavigation', 'ConfirmSettingsRestart'] + [
                 'Select' + c[0] + 'Category' for c in CATEGORIES]
MANIFEST = {'version': TAG, 'run': str(RUN), 'assets': [], 'status': 'started'}
CHORD_TYPE = None


def dump(name, value):
    (RUN / name).write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str), encoding='utf-8')


def progress(label):
    (OUT / 'progress.txt').write_text(label, encoding='utf-8')
    unreal.log('SETTINGS_REDESIGN ' + label)


def color(h, alpha=1):
    def c(v):
        f = int(v, 16) / 255
        return f / 12.92 if f <= .04045 else ((f + .055) / 1.055) ** 2.4
    return unreal.LinearColor(c(h[0:2]), c(h[2:4]), c(h[4:6]), alpha)


IVORY, GOLD, MUTED = color('F3E5C8'), color('D8B66B'), color('A4A4AB')
FONT = AS.load_asset('/Game/Environment/Font/HSBombaram3_0_Regular_Font')


def font(size):
    assert FONT
    return unreal.SlateFontInfo(font_object=FONT, typeface_font_name='Default', size=size)


def ensure(bp, cls, name, parent, variable=False, index=-1):
    w = widgets(bp).get(name)
    if w:
        assert w.get_class() == cls.static_class(), (name, w.get_class())
        if parent and w.get_parent() != parent:
            ui('MoveWidget', bp, w, parent, index)
        if variable:
            ui('ToggleWidgetAsVariable', bp, w, True)
        return w
    return add(bp, cls, name, parent, variable, index)


def move(bp, name, parent, index=-1):
    w = widgets(bp)[name]
    if w.get_parent() != parent or index >= 0:
        ui('MoveWidget', bp, w, parent, index)
    return w


def remove(bp, name):
    w = widgets(bp).get(name)
    if w:
        ui('RemoveWidget', bp, w)


def fill(w, weight=1, padding=None):
    kw = dict(size=unreal.SlateChildSize(value=weight, size_rule=unreal.SlateSizeRule.FILL))
    if padding is not None:
        kw['padding'] = unreal.Margin(*padding)
    properties(w.get_editor_property('slot'), **kw)


def txt(bp, name, label, parent, size=22, tint=None, variable=False):
    w = ensure(bp, unreal.TextBlock, name, parent, variable)
    properties(w, text=unreal.Text(label), font=font(size),
               color_and_opacity=unreal.SlateColor(specified_color=tint or IVORY),
               visibility=unreal.SlateVisibility.HIT_TEST_INVISIBLE)
    return w


def box(bp, name, parent, width=None, height=None):
    w = ensure(bp, unreal.SizeBox, name, parent)
    if width is not None:
        w.set_width_override(width)
    if height is not None:
        w.set_height_override(height)
    return w


def canvas(w, amin, amax, z=0):
    properties(w.get_editor_property('slot'), layout_data=unreal.AnchorData(
        anchors=unreal.Anchors(minimum=unreal.Vector2D(*amin), maximum=unreal.Vector2D(*amax)),
        offsets=unreal.Margin(0, 0, 0, 0), alignment=unreal.Vector2D(0, 0)),
        auto_size=False, z_order=z)


def clear_brush(brush):
    brush.set_editor_property('draw_as', unreal.SlateBrushDrawType.NO_DRAW_TYPE)
    brush.set_editor_property('tint_color', unreal.SlateColor(specified_color=unreal.LinearColor(0, 0, 0, 0)))
    return brush


def transparent_style(w):
    st = w.get_editor_property('widget_style')
    for name in ('normal', 'hovered', 'pressed', 'disabled'):
        st.set_editor_property(name, clear_brush(st.get_editor_property(name)))
    st.set_editor_property('normal_padding', unreal.Margin(8, 9, 8, 9))
    st.set_editor_property('pressed_padding', unreal.Margin(8, 10, 8, 8))
    properties(w, widget_style=st)
    w.set_cursor(unreal.MouseCursor.HAND)


def rule(bp, name, parent, alpha=.25):
    bounds = box(bp, name + 'Height', parent, height=1)
    line = ensure(bp, unreal.Border, name, bounds, True)
    properties(line, brush_color=color('C3B89F', alpha), visibility=unreal.SlateVisibility.HIT_TEST_INVISIBLE,
               padding=unreal.Margin(0))
    return bounds


def button(bp, name, label, parent):
    w = ensure(bp, unreal.Button, name, parent, True)
    properties(w, is_focusable=True)
    transparent_style(w)
    # Move the original text out before installing a new child container.
    textw = widgets(bp).get(name + 'Text')
    content = widgets(bp).get(name + 'Content')
    if textw and not content:
        ui('MoveWidget', bp, textw, widgets(bp)['List_Setting'], -1)
    content = ensure(bp, unreal.VerticalBox, name + 'Content', w)
    txt(bp, name + 'Text', label, content, 20, variable=True)
    underline = rule(bp, name + 'Underline', content, .8)
    properties(underline, visibility=unreal.SlateVisibility.HIT_TEST_INVISIBLE)
    properties(widgets(bp)[name + 'Underline'], render_opacity=0.)
    return w


def layout(bp):
    sw = widgets(bp)
    root, panel, body = sw['CanvasPanel_29'], sw['Panel_Setting'], sw['List_Setting']
    properties(root, visibility=unreal.SlateVisibility.SELF_HIT_TEST_INVISIBLE)
    move(bp, 'Panel_Setting', root)
    canvas(panel, (.035, .035), (.965, .965), 1)
    properties(panel, background=clear_brush(panel.get_editor_property('background')),
               padding=unreal.Margin(0), visibility=unreal.SlateVisibility.SELF_HIT_TEST_INVISIBLE,
               horizontal_alignment=unreal.HorizontalAlignment.H_ALIGN_FILL,
               vertical_alignment=unreal.VerticalAlignment.V_ALIGN_FILL)
    remove(bp, 'SettingsViewportFit')  # Panel and all descendants have already been moved.
    scrim = ensure(bp, unreal.Border, 'ModalScrim', root)
    canvas(scrim, (0, 0), (1, 1), 0)
    properties(scrim, brush_color=color('101115', .68), visibility=unreal.SlateVisibility.VISIBLE)
    properties(sw['SettingsTitle'], font=font(32))
    properties(sw['SettingsPawBounds'].get_editor_property('slot'), vertical_alignment=unreal.VerticalAlignment.V_ALIGN_CENTER)
    properties(sw['SettingsPaw'], visibility=unreal.SlateVisibility.HIT_TEST_INVISIBLE)
    ui('ToggleWidgetAsVariable', bp, sw['SettingsHint'], True)
    properties(sw['SettingsHint'], font=font(18), auto_wrap_text=True)
    sw['SettingsRuleHeight'].set_height_override(1)
    properties(sw['SettingsRule'], brush_color=color('C3B89F', .25), visibility=unreal.SlateVisibility.HIT_TEST_INVISIBLE)
    columns = ensure(bp, unreal.HorizontalBox, 'SettingsColumns', body)
    fill(columns, padding=(0, 18, 0, 18))
    side = box(bp, 'CategoryWidth', columns, width=148)
    categories = ensure(bp, unreal.VerticalBox, 'CategoryList', side)
    for name, label, _ in CATEGORIES:
        button(bp, name + 'CategoryButton', label, categories)
    divider = box(bp, 'ColumnRuleWidth', columns, width=1)
    line = ensure(bp, unreal.Border, 'ColumnRule', divider)
    properties(line, brush_color=color('C3B89F', .18), visibility=unreal.SlateVisibility.HIT_TEST_INVISIBLE)
    scroll = move(bp, 'SettingsBodyScroll', columns)
    fill(scroll, padding=(20, 0, 0, 0))
    properties(scroll, scroll_when_focus_changes=unreal.ScrollWhenFocusChanges.INSTANT_SCROLL,
               navigation_destination=unreal.DescendantScrollDestination.INTO_VIEW,
               navigation_scroll_padding=8.)
    switcher = ensure(bp, unreal.WidgetSwitcher, 'CategorySwitcher', scroll, True)
    pages = [ensure(bp, unreal.VerticalBox, name + 'Page', switcher) for name in ('Screen', 'Audio', 'Controls')]
    for name in ('WindowModeRow', 'QualityRow', 'FrameLimitRow', 'VSyncRow'):
        move(bp, name + 'Height', pages[0])
    move(bp, 'VolumeRowHeight', pages[1])
    move(bp, 'DeveloperGroup', switcher)
    # Switcher order remains stable on a bounded rerun.
    for i, w in enumerate(pages + [widgets(bp)['DeveloperGroup']]):
        move(bp, w.get_name(), switcher, i)
    remove(bp, 'SettingsBody')
    for name in ('WindowModeRow', 'QualityRow', 'FrameLimitRow', 'VSyncRow', 'VolumeRow', 'NoArmorCaptureRow'):
        current = widgets(bp)
        right = current[name + 'ControlWidth']
        right.clear_width_override()
        fill(current[name + 'Label'], .48)
        fill(right, .52)
        properties(right.get_editor_property('slot'), vertical_alignment=unreal.VerticalAlignment.V_ALIGN_CENTER)
    properties(widgets(bp)['DeveloperSessionHint'], text=unreal.Text('적용 시 반영 · 이번 실행에만 유지'), auto_wrap_text=True)
    for slot, label, default in KEYS:
        height = box(bp, 'Key' + slot + 'RowHeight', pages[2], height=64)
        row = ensure(bp, unreal.HorizontalBox, 'Key' + slot + 'Row', height)
        labels = ensure(bp, unreal.VerticalBox, 'Key' + slot + 'Labels', row)
        fill(labels, .48)
        txt(bp, 'Key' + slot + 'Label', label, labels, 21)
        txt(bp, 'Key' + slot + 'Default', '기본값: ' + default, labels, 15, MUTED)
        control = ensure(bp, unreal.VerticalBox, 'Key' + slot + 'Control', row)
        fill(control, .52)
        properties(control.get_editor_property('slot'), vertical_alignment=unreal.VerticalAlignment.V_ALIGN_CENTER)
        selector = ensure(bp, unreal.InputKeySelector, 'Key' + slot, control, True)
        properties(selector.get_editor_property('slot'), horizontal_alignment=unreal.HorizontalAlignment.H_ALIGN_FILL)
        transparent_style(selector)
        ts = selector.get_editor_property('text_style')
        ts.set_editor_property('font', font(21))
        ts.set_editor_property('color_and_opacity', unreal.SlateColor(specified_color=IVORY))
        properties(selector, text_style=ts, key_selection_text=unreal.Text('키 입력 대기…'),
                   no_key_specified_text=unreal.Text('키를 선택하세요'), allow_modifier_keys=True, allow_gamepad_keys=False)
        underline = rule(bp, 'Key' + slot + 'Underline', control, .8)
        properties(underline, visibility=unreal.SlateVisibility.HIT_TEST_INVISIBLE)
        properties(widgets(bp)['Key' + slot + 'Underline'], brush_color=color('D8B66B', .8), render_opacity=0.)
    # Empty combo faces; only their popup retains a readable dark background.
    for name in ('WindowModeCombo', 'QualityCombo', 'FrameLimitCombo'):
        combo = widgets(bp)[name]
        style = combo.get_editor_property('widget_style')
        cb = style.get_editor_property('combo_button_style')
        bs = cb.get_editor_property('button_style')
        for state in ('normal', 'hovered', 'pressed', 'disabled'):
            bs.set_editor_property(state, clear_brush(bs.get_editor_property(state)))
        cb.set_editor_property('button_style', bs)
        style.set_editor_property('combo_button_style', cb)
        properties(combo, widget_style=style, font=font(21))
        combo.set_cursor(unreal.MouseCursor.HAND)
    slider = widgets(bp)['VolumeSlider']
    ss = slider.get_editor_property('widget_style')
    ss.set_editor_property('bar_thickness', 2.)
    properties(slider, widget_style=ss)
    rule(bp, 'FooterRule', body)
    status = widgets(bp)['SettingsStatus']
    properties(status, auto_wrap_text=True, font=font(18))
    statusbox = box(bp, 'SettingsStatusHeight', body, height=52)
    move(bp, 'SettingsStatus', statusbox)
    footer = ensure(bp, unreal.WrapBox, 'FooterWrap', body)
    properties(footer, explicit_wrap_size=False, inner_slot_padding=unreal.Vector2D(14, 8))
    button(bp, 'DefaultsButton', '기본값', footer)
    gameplay = ensure(bp, unreal.WrapBox, 'GameplayActions', footer, True)
    properties(gameplay, explicit_wrap_size=False, inner_slot_padding=unreal.Vector2D(14, 8))
    button(bp, 'RestartButton', '다시 시작', gameplay)
    button(bp, 'MainMenuButton', '시작 메뉴', gameplay)
    button(bp, 'ApplyButton', '적용', footer)
    button(bp, 'CloseButton', '닫기', footer)
    remove(bp, 'SettingsFooter')
    for i, name in enumerate(('SettingsHeading', 'SettingsHint', 'SettingsRuleHeight', 'SettingsColumns',
                              'FooterRuleHeight', 'SettingsStatusHeight', 'FooterWrap')):
        move(bp, name, body, i)
    fill(widgets(bp)['SettingsColumns'], padding=(0, 18, 0, 18))


class Q(Graph):
    def placed(self, node):
        node = super().placed(node)
        # EdGraphNode.NodeComment is not reflected on these installed wrappers.
        # EditorAssetSubsystem accepts any UObject and stores package metadata
        # keyed by that exact object, including Blueprint graph subobjects.
        AS.set_metadata_tag(node, TAG_KEY, TAG)
        assert AS.get_metadata_tag(node, TAG_KEY) == TAG, node.get_path_name()
        return node


def unplug(node, name='then', output=True):
    p = pin(node, name, output)
    for other in list(p.list_connected_pins()):
        p.break_single_pin_link(other)


def graph(bp, name, fresh=False):
    g = BP.add_function_graph(bp, name)
    q = Q(g)
    if fresh:
        start = entry(q)
        nodes = [n for n in BP.find_nodes(g) if n != start]
        if nodes:
            editor(g).remove_nodes(nodes)
    return q


def cleanup_owned(bp):
    for g in BP.list_graphs(bp):
        owned = [n for n in BP.find_nodes(g) if AS.get_metadata_tag(n, TAG_KEY) == TAG]
        if owned:
            editor(g).remove_nodes(owned)


def call(q, name, path, **values):
    return q.fn(path, target=q.ref(name), **values)


def status(q, value):
    return call(q, 'SettingsStatus', T + 'SetText', InText=value)


def visibility(q, name, visible):
    return call(q, name, W + 'SetVisibility', InVisibility='SelfHitTestInvisible' if visible else 'Collapsed')


def callable_nodes(g, suffix):
    return [n.node for n in BP.get_node_infos(BP.find_nodes(g)) if suffix in n.type_id]


def unique_call(g, suffix):
    nodes = callable_nodes(g, suffix)
    assert len(nodes) == 1, (g.get_name(), suffix, [n.get_name() for n in nodes])
    return nodes[0]


def event(bp, widget, delegate):
    """BindToEventProperty returns false when a delegate is already authored."""
    eg = BP.get_graph(bp, 'EventGraph')
    suffix = '|' + delegate + '(' + widget.get_name() + ')'
    existing = [info.node for info in BP.get_node_infos(BP.find_nodes(eg))
                if info.node.get_class().get_name() == 'K2Node_ComponentBoundEvent'
                and info.type_id.endswith(suffix)]
    assert len(existing) <= 1, ('Duplicate bound event', widget.get_name(), delegate)
    return existing[0] if existing else create_bound_event(bp, widget, delegate)


def bind(bp, widget, delegate, func, y):
    ev = event(bp, widgets(bp)[widget], delegate)
    unplug(ev)
    q = Q(BP.get_graph(bp, 'EventGraph'), 12000, y)
    q.chain(ev, q.fn(func))
    return ev


def chord(q, key, setter):
    """Resolve a real MakeStruct node from the typed InputChord context, never a guessed title."""
    global CHORD_TYPE
    context = pin(setter, 'InSelectedKey')
    candidates = [CHORD_TYPE] if CHORD_TYPE else list(dict.fromkeys(str(s) for s in q.e.list_available_nodes([context])))
    dump('input-chord-candidates.json', candidates)
    assert len(candidates) <= 160, ('Unbounded InputChord candidates', len(candidates))
    for candidate in candidates:
        n = q.e.create_node_from_name(candidate, unreal.Vector2D(q.x, q.y), [context])
        if not n:
            continue
        if n.get_class().get_name() == 'K2Node_MakeStruct':
            info = BP.get_node_infos([n])[0]
            inputs = {str(p.name) for p in info.input_pins}
            outputs = [str(p.name) for p in info.output_pins]
            if {'Key', 'bShift', 'bCtrl', 'bAlt', 'bCmd'}.issubset(inputs) and len(outputs) == 1:
                n = q.placed(n)
                wire(key, 'ReturnValue', n, 'Key')
                for mod in ('bShift', 'bCtrl', 'bAlt', 'bCmd'):
                    literal(n, mod, False)
                # CreateNodeFromName auto-wires the typed context. Reconnect explicitly
                # after inspection to avoid treating an already-present link as a failure.
                unplug(setter, 'InSelectedKey', False)
                wire(n, outputs[0], setter, 'InSelectedKey')
                CHORD_TYPE = candidate
                dump('input-chord-node.json', {'type': candidate, 'inputs': sorted(inputs), 'output': outputs[0]})
                return
        q.e.remove_nodes([n])
    raise RuntimeError('No reflected InputChord MakeStruct with Key/bShift/bCtrl/bAlt/bCmd pins')


def draft_graphs(bp):
    q = graph(bp, 'RefreshKeySelectors', True)
    last = q.set('bRefreshingKeySelectors', value=True)
    q.chain(entry(q), last)
    for slot, _, _ in KEYS:
        getkey = q.fn(N + 'GetDraftKey', BindingSlot=slot)
        setter = call(q, 'Key' + slot, SELECTOR + 'SetSelectedKey')
        chord(q, getkey, setter)
        q.chain(last, setter)
        last = setter
    q.chain(last, q.set('bRefreshingKeySelectors', value=False))

    q = graph(bp, 'RefreshBindingStatus', True)
    valid = q.fn(N + 'ValidateDraftKeys')
    branch = q.branch((valid, 'ReturnValue'))
    q.chain(entry(q), branch)
    wire(branch, 'then', status(q, '변경한 설정은 적용을 누르면 저장됩니다.'), 'execute')
    wire(branch, 'else', status(q, (valid, 'Error')), 'execute')

    eg = BP.get_graph(bp, 'EventGraph')
    initialized = BP.add_event(bp, 'OnSettingsDraftInitialized', unreal.IntPoint(11600, 8000))
    unplug(initialized)
    q = Q(eg, 12000, 8000)
    q.chain(initialized, q.fn('RefreshKeySelectors'))
    for i, (slot, _, _) in enumerate(KEYS):
        ev = event(bp, widgets(bp)['Key' + slot], 'OnKeySelected')
        unplug(ev)
        q = Q(eg, 12000, 8500 + i * 700)
        guard = q.branch(q.ref('bRefreshingKeySelectors'))
        setkey = q.fn(N + 'SetDraftChord', BindingSlot=slot, Chord=(ev, 'SelectedKey'))
        accepted = q.branch((setkey, 'ReturnValue'))
        q.chain(ev, guard)
        wire(guard, 'else', setkey, 'execute')
        q.chain(setkey, accepted)
        wire(accepted, 'then', q.fn('RefreshBindingStatus'), 'execute')
        restore = q.fn('RefreshKeySelectors')
        wire(accepted, 'else', restore, 'execute')
        q.chain(restore, status(q, (setkey, 'Error')))
        ev2 = event(bp, widgets(bp)['Key' + slot], 'OnIsSelectingKeyChanged')
        unplug(ev2)
        q = Q(eg, 12000, 14500 + i * 450)
        selecting = call(q, 'Key' + slot, SELECTOR + 'GetIsSelectingKey')
        b = q.branch((selecting, 'ReturnValue'))
        q.chain(ev2, b)
        wire(b, 'then', status(q, '키를 누르세요. Esc로 취소합니다.'), 'execute')
        wire(b, 'else', q.fn('RefreshBindingStatus'), 'execute')

    q = graph(bp, 'ResetAllDrafts', True)
    seq = [entry(q), q.fn(N + 'ResetDraftKeys'),
           call(q, 'VolumeSlider', '/Script/UMG.Slider.SetValue', InValue=1)]
    for name, idx in [('WindowModeCombo', 2), ('QualityCombo', 4), ('FrameLimitCombo', 4)]:
        seq.append(call(q, name, '/Script/UMG.ComboBoxString.SetSelectedIndex', Index=idx))
    for name in ('VSyncCheckBox', 'NoArmorCaptureCheckBox'):
        seq.append(call(q, name, '/Script/UMG.CheckBox.SetIsChecked', InIsChecked=False))
    seq += [q.fn('UpdateVolumePercent'), status(q, '기본값으로 바꿨습니다. 적용을 누르면 저장됩니다.')]
    q.chain(*seq)
    bind(bp, 'DefaultsButton', 'OnClicked', 'ResetAllDrafts', 18400)
    # Existing dev initialization remains a read; only the old immediate setter is detached.
    bind(bp, 'NoArmorCaptureCheckBox', 'OnCheckStateChanged', 'MarkDraftChanged', 19000)

    q = graph(bp, 'ApplyDraft')
    start = entry(q)
    unplug(start)
    original_first = unique_call(q.g, 'SetMasterVolume')
    capture = q.fn(N + 'IsCapturingBinding')
    capture_branch = q.branch((capture, 'ReturnValue'))
    valid = q.fn(N + 'ValidateDraftKeys')
    valid_branch = q.branch((valid, 'ReturnValue'))
    commit = q.fn(N + 'ApplyDraftKeys')
    committed = q.branch((commit, 'ReturnValue'))
    q.chain(start, capture_branch)
    wire(capture_branch, 'then', status(q, '키 입력을 마치거나 Esc로 취소한 뒤 적용하세요.'), 'execute')
    wire(capture_branch, 'else', valid_branch, 'execute')
    wire(valid_branch, 'else', status(q, (valid, 'Error')), 'execute')
    wire(valid_branch, 'then', commit, 'execute')
    q.chain(commit, committed)
    wire(committed, 'else', status(q, (commit, 'Error')), 'execute')
    wire(committed, 'then', original_first, 'execute')
    vs = unique_call(q.g, 'SetVSyncEnabled')
    apply = unique_call(q.g, 'ApplySettings')
    unplug(vs)
    developer = q.fn(S + 'IsDeveloperModeAvailable')
    devbranch = q.branch((developer, 'ReturnValue'))
    checked = call(q, 'NoArmorCaptureCheckBox', '/Script/UMG.CheckBox.IsChecked')
    devset = q.fn(S + 'SetNoArmorCaptureEnabled', bEnabled=(checked, 'ReturnValue'))
    q.chain(vs, devbranch)
    wire(devbranch, 'then', devset, 'execute')
    q.chain(devset, apply)
    wire(devbranch, 'else', apply, 'execute')

    q = graph(bp, 'CloseSettings')
    unplug(entry(q))
    q.chain(entry(q), q.fn(N + 'DismissSettings'))


def ring(q, names, previous):
    """Explicit Next/Previous and directional boundaries on exactly active controls."""
    last = previous
    for i, name in enumerate(names):
        for direction, target in [('Next', names[(i + 1) % len(names)]),
                                  ('Previous', names[(i - 1) % len(names)])]:
            node = call(q, name, W + 'SetNavigationRuleExplicit', Direction=direction, InWidget=q.ref(target))
            q.chain(last, node)
            last = node
        for direction in ('Left', 'Right', 'Up', 'Down'):
            node = call(q, name, W + 'SetNavigationRuleBase', Direction=direction, Rule='Stop')
            q.chain(last, node)
            last = node
    return last


def navigation_graph(bp):
    q = graph(bp, 'RebuildSettingsNavigation', True)
    pagecontrols = [['WindowModeCombo', 'QualityCombo', 'FrameLimitCombo', 'VSyncCheckBox'], ['VolumeSlider'],
                    ['Key' + k[0] for k in KEYS], ['NoArmorCaptureCheckBox']]
    # Build each base page once, then splice visible optional groups into its ring.
    # This avoids four copies of every navigation setter per page.
    dev = q.branch(q.ref('SettingsDeveloperAvailable'))
    game = q.branch(q.ref('SettingsGameplayAvailable'))
    dev_last = dev
    for source, direction, dest in [('ControlsCategoryButton', 'Next', 'DeveloperCategoryButton'),
                                     ('DeveloperCategoryButton', 'Previous', 'ControlsCategoryButton')]:
        node = call(q, source, W + 'SetNavigationRuleExplicit', Direction=direction, InWidget=q.ref(dest))
        wire(dev_last, 'then', node, 'execute')
        dev_last = node
    # The page-specific last-category -> first-control link is authored below.
    q.chain(dev_last, game)
    wire(dev, 'else', game, 'execute')
    game_last = game
    for source, direction, dest in [('DefaultsButton', 'Next', 'RestartButton'),
                                     ('RestartButton', 'Previous', 'DefaultsButton'),
                                     ('RestartButton', 'Next', 'MainMenuButton'),
                                     ('MainMenuButton', 'Previous', 'RestartButton'),
                                     ('MainMenuButton', 'Next', 'ApplyButton'),
                                     ('ApplyButton', 'Previous', 'MainMenuButton')]:
        node = call(q, source, W + 'SetNavigationRuleExplicit', Direction=direction, InWidget=q.ref(dest))
        wire(game_last, 'then', node, 'execute')
        game_last = node
    # Optional controls receive boundaries before per-page sidebar/body links.
    boundary_last = entry(q)
    for name in ('DeveloperCategoryButton', 'RestartButton', 'MainMenuButton'):
        for direction in ('Left', 'Right', 'Up', 'Down'):
            node = call(q, name, W + 'SetNavigationRuleBase', Direction=direction, Rule='Stop')
            q.chain(boundary_last, node)
            boundary_last = node
    last, lastpin = boundary_last, 'then'
    for index, controls in enumerate(pagecontrols):
        q.x, q.y = 300, index * 2000
        equal = q.fn(K + 'EqualEqual_IntInt', A=q.ref('SettingsCategoryIndex'), B=index)
        page = q.branch((equal, 'ReturnValue'))
        wire(last, lastpin, page, 'execute')
        names = [c[0] + 'CategoryButton' for c in CATEGORIES[:3]] + controls + ['DefaultsButton', 'ApplyButton', 'CloseButton']
        first = q.set('SettingsNavigationReady', value=True)
        wire(page, 'then', first, 'execute')
        tail = ring(q, names, first)
        # Developer is excluded by default, inserted only when it is visible.
        optional = q.branch(q.ref('SettingsDeveloperAvailable'))
        q.chain(tail, optional)
        devforward = call(q, 'DeveloperCategoryButton', W + 'SetNavigationRuleExplicit', Direction='Next', InWidget=q.ref(controls[0]))
        devback = call(q, controls[0], W + 'SetNavigationRuleExplicit', Direction='Previous', InWidget=q.ref('DeveloperCategoryButton'))
        wire(optional, 'then', devforward, 'execute')
        q.chain(devforward, devback, dev)
        wire(optional, 'else', dev, 'execute')
        # Intentional sidebar/body directional links are independent of Tab.
        for cat in [c[0] + 'CategoryButton' for c in CATEGORIES]:
            node = call(q, cat, W + 'SetNavigationRuleExplicit', Direction='Right', InWidget=q.ref(controls[0]))
            # Put these setters before the optional-group branch.
            unplug(tail)
            q.chain(tail, node, optional)
            tail = node
        for control in controls:
            node = call(q, control, W + 'SetNavigationRuleExplicit', Direction='Left', InWidget=q.ref(CATEGORIES[index][0] + 'CategoryButton'))
            unplug(tail)
            q.chain(tail, node, optional)
            tail = node
        last, lastpin = page, 'else'


def category_graphs(bp):
    for index, (name, _, hint) in enumerate(CATEGORIES):
        q = graph(bp, 'Select' + name + 'Category', True)
        idx = q.set('SettingsCategoryIndex', value=index)
        switch = call(q, 'CategorySwitcher', '/Script/UMG.WidgetSwitcher.SetActiveWidgetIndex', Index=index)
        hintnode = call(q, 'SettingsHint', T + 'SetText', InText=hint)
        q.chain(entry(q), idx, switch, hintnode, q.fn('RebuildSettingsNavigation'))
        bind(bp, name + 'CategoryButton', 'OnClicked', 'Select' + name + 'Category', 21000 + index * 400)
    q = graph(bp, 'InitializeSettingsPresentation', True)
    can = q.fn(S + 'IsDeveloperModeAvailable')
    save = q.set('SettingsDeveloperAvailable', source=(can, 'ReturnValue'))
    branch = q.branch((can, 'ReturnValue'))
    q.chain(entry(q), save, branch)
    groups = []
    for branchpin, visible in (('then', True), ('else', False)):
        category = call(q, 'DeveloperCategoryButton', W + 'SetVisibility', InVisibility='Visible' if visible else 'Collapsed')
        group = visibility(q, 'DeveloperGroup', visible)
        wire(branch, branchpin, category, 'execute')
        q.chain(category, group)
        groups.append(group)
    # Use configured gameplay map names discovered from the project flow defaults,
    # plus the authored test aliases. No unknown or MainMenu map gains travel buttons.
    names = {'Tutorial', 'Stage1', 'Stage2', 'SoundTest_Tutorial', 'SoundTest_Stage1', 'SoundTest_Stage2'}
    config = ROOT / 'Config/DefaultGame.ini'
    if config.exists():
        import re
        for line in config.read_text(encoding='utf-8-sig').splitlines():
            if any(k in line for k in ('TutorialMap', 'Stage1Map', 'Stage2Map', '+Stages=')):
                matches = re.findall(r'/Game/[^\s\"\)]+', line)
                names.update(m.rsplit('/', 1)[-1].split('.')[0] for m in matches)
    current = q.fn('/Script/Engine.GameplayStatics.GetCurrentLevelName', bRemovePrefixString=True)
    result = None
    for mapname in sorted(names):
        check = q.fn('/Script/Engine.KismetStringLibrary.EqualEqual_StrStr', A=(current, 'ReturnValue'), B=mapname)
        result = (check, 'ReturnValue') if result is None else (q.fn(K + 'BooleanOR', A=result, B=(check, 'ReturnValue')), 'ReturnValue')
    gameplay = q.set('SettingsGameplayAvailable', source=result)
    # GetCurrentLevelName is BlueprintCallable (impure), so execute it before
    # the comparison expression consumes its return value.
    for node in groups:
        q.chain(node, current)
    q.chain(current, gameplay)
    gamebranch = q.branch(q.ref('SettingsGameplayAvailable'))
    q.chain(gameplay, gamebranch)
    ready = q.set('SettingsInitialFocusPending', value=True)
    for branchpin, visible in (('then', True), ('else', False)):
        show = visibility(q, 'GameplayActions', visible)
        wire(gamebranch, branchpin, show, 'execute')
        q.chain(show, ready)
    q.chain(ready, q.fn('SelectScreenCategory'))
    init = graph(bp, 'InitializeDraft')
    # Remove the previous eager Apply focus; native subsystem focuses the root after Construct.
    oldfocus = unique_call(init.g, 'SetKeyboardFocus')
    unplug(oldfocus, 'execute', False)
    readyset = [n for n in BP.find_nodes(init.g) if n.get_class().get_name() == 'K2Node_VariableSet'
                and n.find_input_pin('DraftReady').is_valid() and str(pin(n, 'DraftReady').get_pin_value()).lower() in ('true', '1')]
    assert len(readyset) == 1, ('DraftReady final setter', readyset)
    unplug(readyset[0])
    init.chain(readyset[0], init.fn('InitializeSettingsPresentation'))


def affordance(q, button_name, decorations, next_node, selected=None, capture=False):
    hovered = call(q, button_name, W + 'IsHovered')
    focused = q.fn(NAV, Widget=q.ref(button_name))
    active = q.fn(K + 'BooleanOR', A=(hovered, 'ReturnValue'), B=(focused, 'ReturnValue'))
    if capture:
        selecting = call(q, button_name, SELECTOR + 'GetIsSelectingKey')
        active = q.fn(K + 'BooleanOR', A=(active, 'ReturnValue'), B=(selecting, 'ReturnValue'))
    if selected is not None:
        eq = q.fn(K + 'EqualEqual_IntInt', A=q.ref('SettingsCategoryIndex'), B=selected)
        active = q.fn(K + 'BooleanOR', A=(active, 'ReturnValue'), B=(eq, 'ReturnValue'))
    enabled = call(q, button_name, W + 'GetIsEnabled')
    active = q.fn(K + 'BooleanAND', A=(active, 'ReturnValue'), B=(enabled, 'ReturnValue'))
    root_enabled = q.fn(W + 'GetIsEnabled')
    active = q.fn(K + 'BooleanAND', A=(active, 'ReturnValue'), B=(root_enabled, 'ReturnValue'))
    b = q.branch((active, 'ReturnValue'))
    for branchpin, show in (('then', True), ('else', False)):
        previous = b
        pp = branchpin
        for name in decorations:
            node = call(q, name, W + 'SetVisibility', InVisibility='HitTestInvisible' if show else 'Hidden')
            wire(previous, pp, node, 'execute')
            previous, pp = node, 'then'
            opacity = call(q, name, W + 'SetRenderOpacity', InOpacity=1 if show else 0)
            q.chain(previous, opacity)
            previous = opacity
        wire(previous, pp, next_node, 'execute')
    return b


def presentation(bp, main=False):
    name = 'UpdateMenuAffordances' if main else 'UpdateSettingsAffordances'
    q = graph(bp, name, True)
    targets = [('StartButton', ['Start_CatJelly', 'MenuLine_1'], None),
               ('ContinueButton', ['Continue_CatJelly', 'MenuLine_2'], None),
               ('OptionButton', ['Option_CatJelly', 'MenuLine_3'], None),
               ('EndButton', ['End_CatJelly', 'MenuLine_4'], None)] if main else [
                   (c[0] + 'CategoryButton', [c[0] + 'CategoryButtonUnderline'], i) for i, c in enumerate(CATEGORIES)] + [
                       (n, [n + 'Underline'], None) for n in ('DefaultsButton', 'RestartButton', 'MainMenuButton', 'ApplyButton', 'CloseButton')]
    key_names = {'Key' + key[0] for key in KEYS}
    if not main:
        targets += [('Key' + key[0], ['Key' + key[0] + 'Underline'], None) for key in KEYS]
    last = q.placed(q.e.add_return_node())
    for buttonname, deco, selected in reversed(targets):
        last = affordance(q, buttonname, deco, last, selected, buttonname in key_names)
    q.chain(entry(q), last)
    eg = BP.get_graph(bp, 'EventGraph')
    tick = editor(eg).find_event_node('Tick') or BP.add_event(bp, 'Tick', unreal.IntPoint(11600, 24000))
    assert not pin(tick, 'then', True).list_connected_pins(), 'Unexpected existing Tick behavior; refusing to replace it'
    q = Q(eg, 12000, 24000)
    update = q.fn(name)
    q.chain(tick, update)
    if not main:
        pending = q.branch(q.ref('SettingsInitialFocusPending'))
        clear = q.set('SettingsInitialFocusPending', value=False)
        focus = call(q, 'ScreenCategoryButton', W + 'SetKeyboardFocus')
        q.chain(update, pending)
        wire(pending, 'then', clear, 'execute')
        q.chain(clear, focus)


def restart_graph(bp):
    q = graph(bp, 'ConfirmSettingsRestart', True)
    b = q.branch(q.ref('SettingsRestartConfirmed'))
    q.chain(entry(q), b)
    restart = q.fn(N + 'RestartFromSettings')
    wire(b, 'then', restart, 'execute')
    confirm = q.set('SettingsRestartConfirmed', value=True)
    wire(b, 'else', confirm, 'execute')
    label = call(q, 'RestartButtonText', T + 'SetText', InText='한 번 더 눌러 다시 시작')
    q.chain(confirm, label, status(q, '현재 스테이지의 시작 지점으로 돌아갑니다. 다시 시작을 한 번 더 누르세요.'))
    bind(bp, 'RestartButton', 'OnClicked', 'ConfirmSettingsRestart', 25000)
    ev = event(bp, widgets(bp)['MainMenuButton'], 'OnClicked')
    unplug(ev)
    q = Q(BP.get_graph(bp, 'EventGraph'), 12000, 25500)
    q.chain(ev, q.fn(N + 'ReturnToMenuFromSettings'))


def menu_graphs(bp):
    sw = widgets(bp)
    for name in ('StartButton', 'ContinueButton', 'OptionButton', 'EndButton'):
        ui('ToggleWidgetAsVariable', bp, sw[name], True)
        sw[name].set_cursor(unreal.MouseCursor.HAND)
    for name in ('Start_CatJelly', 'Continue_CatJelly', 'Option_CatJelly', 'End_CatJelly',
                 'MenuLine_1', 'MenuLine_2', 'MenuLine_3', 'MenuLine_4'):
        ui('ToggleWidgetAsVariable', bp, sw[name], True)
        if sw[name].get_editor_property('visibility') == unreal.SlateVisibility.VISIBLE:
            properties(sw[name], visibility=unreal.SlateVisibility.HIT_TEST_INVISIBLE)
    eg = BP.get_graph(bp, 'EventGraph')
    # Preserve original hover event chains and simply make their shown decoration non-interactive.
    for info in BP.get_node_infos(BP.find_nodes(eg)):
        if 'InVisibility' not in {str(p.name) for p in info.input_pins}:
            continue
        p = info.node.find_input_pin('InVisibility')
        if p and p.is_valid() and str(p.get_pin_value()) == 'Visible':
            literal(info.node, 'InVisibility', 'HitTestInvisible')
    compile_bp(bp)
    ev = event(bp, sw['OptionButton'], 'OnClicked')
    unplug(ev)
    q = Q(eg, 12000, 26000)
    selves = [n for n in BP.find_nodes(eg) if n.get_class().get_name() == 'K2Node_Self']
    assert selves, 'Original Option chain has no self reference'
    selfnode = selves[0]
    selfout = [p.name for n in BP.get_node_infos([selfnode]) for p in n.output_pins][0]
    # Get declares WorldContext="Context". UMG supplies self implicitly and
    # this installed node omits that hidden context pin altogether.
    subsystem = q.fn('/Script/Catrun.CatrunSettingsSubsystem.Get')
    owner = q.fn(W + 'GetOwningPlayer')
    openwidget = q.fn('/Script/Catrun.CatrunSettingsSubsystem.OpenSettings', target=(subsystem, 'ReturnValue'),
                      PlayerController=(owner, 'ReturnValue'), SourcePanel=(selfnode, selfout))
    # Get is BlueprintPure in the compiled native contract.
    if subsystem.find_execute_pin().is_valid():
        q.chain(ev, subsystem, openwidget)
    else:
        q.chain(ev, openwidget)
    presentation(bp, main=True)


def backup_and_load():
    dirty = list(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages())
    dirty += list(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())
    assert not dirty, 'Dirty-package guard: ' + ', '.join(p.get_name() for p in dirty)
    loaded = []
    for path in (SETTINGS, MENU):
        source = ROOT / 'Content' / (path.removeprefix('/Game/') + '.uasset')
        dest = RUN / 'Before' / (path.removeprefix('/Game/') + '.uasset')
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, dest)
        asset = AS.load_asset(path)
        assert asset
        loaded.append(asset)
        MANIFEST['assets'].append({'asset': path, 'backup': str(dest), 'before_sha256': hashlib.sha256(dest.read_bytes()).hexdigest()})
    scripts = RUN / 'Before/Scripts/Menu'
    scripts.mkdir(parents=True)
    for script in (ROOT / 'Scripts/Menu').glob('*.py'):
        shutil.copy2(script, scripts / script.name)
    dump('manifest.json', MANIFEST)
    dump('before-audit.json', {'settings': audit(loaded[0]), 'main_menu': audit(loaded[1])})
    return loaded


def vector_audit(value):
    return {axis: float(value.get_editor_property(axis)) for axis in ('x', 'y')}


def margin_audit(value):
    return {side: float(value.get_editor_property(side)) for side in ('left', 'top', 'right', 'bottom')}


def slot_audit(slot):
    """Read actual reflected layout values; generic ObjectTools returns {} here."""
    kind = slot.get_class().get_name()
    result = {'class': kind}
    if kind == 'CanvasPanelSlot':
        layout = slot.get_editor_property('layout_data')
        anchors = layout.get_editor_property('anchors')
        result.update(layout_data={
            'anchors': {'minimum': vector_audit(anchors.get_editor_property('minimum')),
                        'maximum': vector_audit(anchors.get_editor_property('maximum'))},
            'offsets': margin_audit(layout.get_editor_property('offsets')),
            'alignment': vector_audit(layout.get_editor_property('alignment'))},
            auto_size=bool(slot.get_editor_property('auto_size')),
            z_order=int(slot.get_editor_property('z_order')))
    elif kind in ('HorizontalBoxSlot', 'VerticalBoxSlot'):
        size = slot.get_editor_property('size')
        size_rule = size.get_editor_property('size_rule')
        result.update(size={'value': float(size.get_editor_property('value')),
                            'size_rule': str(size_rule), 'is_fill': size_rule == unreal.SlateSizeRule.FILL},
                      padding=margin_audit(slot.get_editor_property('padding')),
                      horizontal_alignment=str(slot.get_editor_property('horizontal_alignment')),
                      vertical_alignment=str(slot.get_editor_property('vertical_alignment')))
    else:
        # Other slot classes have differing layout contracts. Capture their real
        # shared fields when present, without letting them weaken mandatory
        # Canvas/HorizontalBox/VerticalBox reads above.
        for prop in ('padding', 'horizontal_alignment', 'vertical_alignment'):
            try:
                value = slot.get_editor_property(prop)
                result[prop] = margin_audit(value) if prop == 'padding' else str(value)
            except Exception:
                pass
    return result


def detailed_audit(bp):
    data = audit(bp)
    data['parent_class'] = BP.get_parent(bp).get_path_name()
    current_widgets = widgets(bp)
    for row in data['widgets']:
        slot = current_widgets[row['name']].get_editor_property('slot')
        if slot:
            row['slot_properties'] = slot_audit(slot)
    data['designer'] = {}
    for name, w in current_widgets.items():
        row = {}
        for prop in ('background', 'brush_color', 'widget_style', 'text_style', 'cursor', 'override_cursor',
                     'width_override', 'override_width_override', 'height_override', 'render_opacity',
                     'key_selection_text', 'allow_modifier_keys', 'allow_gamepad_keys', 'navigation',
                     'scroll_when_focus_changes', 'navigation_destination', 'navigation_scroll_padding'):
            try:
                row[prop] = str(w.get_editor_property(prop))
            except Exception:
                pass
        data['designer'][name] = row
    return data


def validate_shape(bp, main_bp, original_menu):
    sw = widgets(bp)
    assert BP.get_parent(bp).get_path_name() == '/Script/Catrun.CatrunSettingsWidget'
    assert len([w for w in sw.values() if w.get_class() == unreal.InputKeySelector.static_class()]) == 8
    assert all(sw['Key' + k[0]].get_class() == unreal.InputKeySelector.static_class() for k in KEYS)
    assert 'SettingsViewportFit' not in sw and 'SettingsPanelBounds' not in sw
    assert sw['Panel_Setting'].get_parent() == sw['CanvasPanel_29']
    assert sw['Panel_Setting'].get_editor_property('background').get_editor_property('draw_as') == unreal.SlateBrushDrawType.NO_DRAW_TYPE
    assert sw['CategorySwitcher'].get_children_count() == 4
    assert original_menu.issubset({n.get_name() for n in BP.find_nodes(BP.get_graph(main_bp, 'EventGraph'))}), 'Original main-menu nodes were removed'
    for name, minimum, maximum, z in [('ModalScrim', 0., 1., 0), ('Panel_Setting', .035, .965, 1)]:
        slot = slot_audit(sw[name].get_editor_property('slot'))
        assert slot['class'] == 'CanvasPanelSlot', (name, slot)
        layout = slot['layout_data']
        for axis in ('x', 'y'):
            assert abs(layout['anchors']['minimum'][axis] - minimum) < 1e-5, (name, slot)
            assert abs(layout['anchors']['maximum'][axis] - maximum) < 1e-5, (name, slot)
            assert abs(layout['alignment'][axis]) < 1e-5, (name, slot)
        assert all(abs(v) < 1e-5 for v in layout['offsets'].values()), (name, slot)
        assert slot['auto_size'] is False and slot['z_order'] == z, (name, slot)
    fills = [('SettingsColumns', 1.), ('SettingsBodyScroll', 1.)]
    for name in ('WindowModeRow', 'QualityRow', 'FrameLimitRow', 'VSyncRow', 'VolumeRow', 'NoArmorCaptureRow'):
        fills += [(name + 'Label', .48), (name + 'ControlWidth', .52)]
    for key, _, _ in KEYS:
        fills += [('Key' + key + 'Labels', .48), ('Key' + key + 'Control', .52)]
        assert sw['Key' + key].get_parent() == sw['Key' + key + 'Control']
        assert 'Key' + key + 'Underline' in sw
        assert abs(sw['Key' + key + 'UnderlineHeight'].get_editor_property('height_override') - 1.) < 1e-5
    for name, expected in fills:
        slot = slot_audit(sw[name].get_editor_property('slot'))
        assert slot['size']['is_fill'] and abs(slot['size']['value'] - expected) < 1e-5, (name, expected, slot)
    assert slot_audit(sw['SettingsColumns'].get_editor_property('slot'))['padding'] == dict(left=0., top=18., right=0., bottom=18.)
    assert slot_audit(sw['SettingsBodyScroll'].get_editor_property('slot'))['padding'] == dict(left=20., top=0., right=0., bottom=0.)
    scroll = sw['SettingsBodyScroll']
    assert scroll.get_editor_property('scroll_when_focus_changes') == unreal.ScrollWhenFocusChanges.INSTANT_SCROLL
    assert scroll.get_editor_property('navigation_destination') == unreal.DescendantScrollDestination.INTO_VIEW
    assert abs(scroll.get_editor_property('navigation_scroll_padding') - 8.) < 1e-5


def main():
    progress('backing up current clean packages')
    bp, main_bp = backup_and_load()
    original_menu = {n.get_name() for n in BP.find_nodes(BP.get_graph(main_bp, 'EventGraph'))
                     if AS.get_metadata_tag(n, TAG_KEY) != TAG}
    MANIFEST['original_menu_nodes'] = sorted(original_menu)
    cleanup_owned(bp)
    cleanup_owned(main_bp)
    progress('reparenting actual WBP_Setting')
    BP.set_parent(bp, unreal.load_class(None, '/Script/Catrun.CatrunSettingsWidget'))
    compile_bp(bp)
    progress('authoring fullscreen Designer hierarchy')
    layout(bp)
    for name, kind in [('bRefreshingKeySelectors', 'bool'), ('SettingsCategoryIndex', 'int'),
                       ('SettingsDeveloperAvailable', 'bool'), ('SettingsGameplayAvailable', 'bool'),
                       ('SettingsNavigationReady', 'bool'), ('SettingsInitialFocusPending', 'bool'),
                       ('SettingsRestartConfirmed', 'bool')]:
        if name not in {str(v) for v in BP.list_variables(bp)}:
            BP.add_variable(bp, name, kind)
    for name in FUNCTIONS:
        BP.add_function_graph(bp, name)
    BP.add_function_graph(main_bp, 'UpdateMenuAffordances')
    compile_bp(bp)
    properties(unreal.get_default_object(bp.generated_class()), is_focusable=True)
    progress('wiring key drafts and atomic Apply gate')
    draft_graphs(bp)
    progress('wiring categories and bounded focus rings')
    navigation_graph(bp)
    category_graphs(bp)
    restart_graph(bp)
    presentation(bp)
    progress('wiring shared menu entry and original hover/focus affordances')
    menu_graphs(main_bp)
    progress('compiling both packages before any save')
    compile_bp(bp)
    compile_bp(main_bp)
    validate_shape(bp, main_bp, original_menu)
    dump('authored-audit.json', {'settings': detailed_audit(bp), 'main_menu': detailed_audit(main_bp)})
    dump('property-schemas.json', PROPERTY_SCHEMAS)
    progress('saving both compiled assets')
    for asset in (bp, main_bp):
        assert AS.save_loaded_asset(asset, False), asset.get_path_name()
    for row in MANIFEST['assets']:
        source = ROOT / 'Content' / (row['asset'].removeprefix('/Game/') + '.uasset')
        row['after_sha256'] = hashlib.sha256(source.read_bytes()).hexdigest()
    MANIFEST['status'] = 'saved-awaiting-fresh-process-reload-audit'
    dump('manifest.json', MANIFEST)
    # Loading an already-loaded package is not a reload. Root executes the audit
    # entrypoint below in its next fresh commandlet for honest saved-byte evidence.
    (OUT / 'latest-run.txt').write_text(str(RUN), encoding='utf-8')
    progress('saved; fresh-process reload audit is required')
    unreal.log('CATRUN_SETTINGS_REDESIGN_SAVED ' + str(RUN))


def reload_audit():
    bp, main_bp = AS.load_asset(SETTINGS), AS.load_asset(MENU)
    compile_bp(bp)
    compile_bp(main_bp)
    latest = OUT / 'latest-run.txt'
    assert latest.exists(), 'No completed settings authoring run is recorded'
    authored = Path(latest.read_text(encoding='utf-8').strip())
    prior = json.loads((authored / 'manifest.json').read_text(encoding='utf-8'))
    validate_shape(bp, main_bp, set(prior['original_menu_nodes']))
    for row in prior['assets']:
        source = ROOT / 'Content' / (row['asset'].removeprefix('/Game/') + '.uasset')
        assert hashlib.sha256(source.read_bytes()).hexdigest() == row['after_sha256'], ('Saved asset changed after author run', row['asset'])
    dump('saved-reload-audit.json', {'settings': detailed_audit(bp), 'main_menu': detailed_audit(main_bp)})
    dump('reload-source.json', {'authoring_run': str(authored), 'original_menu_nodes_retained': True,
                              'saved_hashes_match': True, 'saved': False})
    progress('fresh-process reload/compile audit completed')
    unreal.log('CATRUN_SETTINGS_REDESIGN_RELOAD_AUDIT ' + str(RUN))


if __name__ == '__main__':
    try:
        if '--audit-only' in sys.argv:
            reload_audit()
        else:
            main()
    except Exception:
        MANIFEST['status'] = 'failed'
        dump('manifest.json', MANIFEST)
        (RUN / 'error.txt').write_text(traceback.format_exc(), encoding='utf-8')
        progress('FAILED; see ' + str(RUN / 'error.txt'))
        raise
