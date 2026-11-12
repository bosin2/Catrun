"""Author/audit the BP-owned basket prompt and shorten only the bell recovery pin.

Isolated UE commandlet. -catrunUsabilityAudit reads without saving.
"""
import json
from pathlib import Path
import shutil
import sys
import unreal as u

ROOT = Path(u.Paths.project_dir()).resolve()
sys.path.insert(0, str(ROOT / 'Scripts/Menu'))
from menu_graph import BP, add, compile_bp, properties, ui, widgets

OUT = ROOT / 'Saved/GameplayRepair20261112/BasketUsability'
OUT.mkdir(parents=True, exist_ok=True)
AUDIT = '-catrunusabilityaudit' in u.SystemLibrary.get_command_line().lower()
AS = u.EditorAssetLibrary
PROMPT = '/Game/UI/Interaction/WBP_BasketInteractPrompt'
ACTIONS = '/Game/Systems/Player/Interaction/BP_CatActions'
OWNER = 'BasketUsability20261112'


def main():
    assert not u.get_editor_subsystem(u.UnrealEditorSubsystem).get_game_world()
    assert not u.EditorLoadingAndSavingUtils.get_dirty_map_packages()
    assert not u.EditorLoadingAndSavingUtils.get_dirty_content_packages()
    bp = AS.load_asset(PROMPT) if AS.does_asset_exist(PROMPT) else None
    if not bp:
        assert not AUDIT
        bp = ui('CreateWidgetBlueprint', '/Game/UI/Interaction', 'WBP_BasketInteractPrompt',
                u.load_class(None, '/Script/Catrun.CatrunBasketPromptWidget'))
        AS.set_metadata_tag(bp, 'CatrunAuthor', OWNER)
        root = add(bp, u.CanvasPanel, 'PromptRoot', None)
        label = add(bp, u.TextBlock, 'PromptText', root, variable=True)
        font = label.get_editor_property('font')
        font.set_editor_property('font_object', AS.load_asset('/Game/Environment/Font/HSBombaram3_0_Regular_Font'))
        font.set_editor_property('size', 20)
        properties(label, text=u.Text('[F] 숨기'), font=font, justification=u.TextJustify.CENTER,
                   color_and_opacity=u.SlateColor(specified_color=u.LinearColor(.92,.88,.72,1)),
                   shadow_color_and_opacity=u.LinearColor(0,0,0,.9), shadow_offset=u.Vector2D(0,2),
                   visibility=u.SlateVisibility.HIT_TEST_INVISIBLE)
        properties(label.get_editor_property('slot'), auto_size=True, layout_data=u.AnchorData(
            anchors=u.Anchors(minimum=u.Vector2D(.5,.83), maximum=u.Vector2D(.5,.83)),
            offsets=u.Margin(0,0,0,0), alignment=u.Vector2D(.5,.5)))
        line = add(bp, u.Image, 'PromptUnderline', root)
        properties(line, color_and_opacity=u.LinearColor(.7,.62,.38,.65), visibility=u.SlateVisibility.HIT_TEST_INVISIBLE)
        properties(line.get_editor_property('slot'), auto_size=False, layout_data=u.AnchorData(
            anchors=u.Anchors(minimum=u.Vector2D(.5,.83), maximum=u.Vector2D(.5,.83)),
            offsets=u.Margin(0,21,92,1), alignment=u.Vector2D(.5,0)))
        compile_bp(bp)
        properties(u.get_default_object(bp.generated_class()), is_focusable=False,
                   visibility=u.SlateVisibility.HIT_TEST_INVISIBLE)
        assert AS.save_loaded_asset(bp, False)
    assert AS.get_metadata_tag(bp, 'CatrunAuthor') == OWNER
    assert 'PromptText' in widgets(bp)
    actions = AS.load_asset(ACTIONS)
    g = BP.get_graph(actions, 'TryBell')
    nodes = [x for x in BP.get_node_infos(BP.find_nodes(g)) if 'BeginBellAction' in x.type_id]
    assert len(nodes) == 1
    node = nodes[0].node
    duration = node.find_input_pin('Duration')
    delay = node.find_input_pin('EmitDelay')
    assert not duration.get_connected_pins() if hasattr(duration, 'get_connected_pins') else True
    # Read using reflected node info; graph topology, clip, cooldown and emitted event are untouched.
    values = {p.name: str(p.value) for p in nodes[0].input_pins}
    assert abs(float(values['EmitDelay']) - .566667) < .00001
    defaults = u.get_default_object(actions.generated_class())
    if not AUDIT:
        backup = OUT / 'Before/BP_CatActions.uasset'
        backup.parent.mkdir(parents=True, exist_ok=True)
        if not backup.exists():
            shutil.copy2(ROOT / 'Content/Systems/Player/Interaction/BP_CatActions.uasset', backup)
        assert float(values['Duration']) in (1., 2.8)
        assert duration.set_pin_value('1.0')
        properties(defaults, basket_prompt_widget_class=bp.generated_class())
        compile_bp(actions)
        assert AS.save_loaded_asset(actions, False)
    assert u.get_default_object(actions.generated_class()).get_editor_property('basket_prompt_widget_class') == bp.generated_class()
    values = {p.name: str(p.value) for p in BP.get_node_infos([node])[0].input_pins}
    assert float(values['Duration']) == 1.
    assert abs(float(values['EmitDelay']) - .566667) < .00001
    report = {'completed': True, 'audit_only': AUDIT, 'widget': bp.get_path_name(),
              'action_class': actions.get_path_name(), 'duration': 1., 'emit_delay': float(values['EmitDelay']),
              'scope': 'Prompt visual and class, native BeginBellAction duration pin only; no sound propagation edits.'}
    (OUT / ('prompt_audit.json' if AUDIT else 'prompt_apply.json')).write_text(json.dumps(report, indent=2), encoding='utf8')
    print('CATRUN_BASKET_PROMPT', json.dumps(report))


main()
