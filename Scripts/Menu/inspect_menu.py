"""Read-only saved widget/tree/graph evidence. Does not create widgets or worlds."""
import hashlib
import json
from pathlib import Path
import sys
import unreal

ROOT=Path(unreal.Paths.project_dir()).resolve()
OUT=ROOT/'Saved/Menu20261105'
sys.path.insert(0,str(ROOT/'Scripts/Menu'))
from menu_graph import audit, compile_bp, ui, widgets

paths=['/Game/UI/WBP_MainMenu','/Game/UI/Settings/WBP_Setting']
result={'assets':{},'binary_files':{},'world':None,'game_world':None}
for path in paths:
    bp=unreal.load_asset(path)
    compile_bp(bp)
    result['assets'][path]=audit(bp)
    if path.endswith('/WBP_Setting'):
        panel=widgets(bp)['Panel_Setting']
        padding=panel.get_editor_property('padding')
        background=panel.get_editor_property('background')
        tint=background.get_editor_property('tint_color').get_editor_property('specified_color')
        gain=panel.get_editor_property('brush_color')
        result['saved_panel_properties']={
            'padding':{k:float(padding.get_editor_property(k)) for k in ('left','top','right','bottom')},
            'background_tint':{k:float(tint.get_editor_property(k)) for k in ('r','g','b','a')},
            'brush_color':{k:float(gain.get_editor_property(k)) for k in ('r','g','b','a')},
            'background_draw_as':str(background.get_editor_property('draw_as')),
            'background_resource':str(background.get_editor_property('resource_object'))}
        assert result['saved_panel_properties']['padding']==dict.fromkeys(('left','top','right','bottom'),28.0)
        assert result['saved_panel_properties']['background_tint']==dict.fromkeys(('r','g','b','a'),1.0)
    description=ui('GetWidgetDescription',bp,None,-1)
    (OUT/(bp.get_name()+'-saved-tree.txt')).write_text(str(description.description),encoding='utf-8')
    file=ROOT/'Content'/(path.removeprefix('/Game/')+'.uasset')
    result['binary_files'][path]={'sha256':hashlib.sha256(file.read_bytes()).hexdigest(),'size':file.stat().st_size}

before=json.loads((OUT/'before.json').read_text(encoding='utf-8'))
main=result['assets'][paths[0]]
original_nodes={n['node'] for n in before['assets'][paths[0]]['graphs'] if n['graph'].endswith(':EventGraph')}
actual_nodes={n['name'] for g in main['graphs'] if g['name']=='EventGraph' for n in g['nodes']}
assert original_nodes.issubset(actual_nodes)
original_widgets={n['name'] for n in before['assets'][paths[0]]['widgets']}
actual_widgets={n['name'] for n in main['widgets']}
assert original_widgets.issubset(actual_widgets)
assert actual_widgets-original_widgets=={'ContinueStageHint'}
result['original_main_menu_nodes_retained']=len(original_nodes)
result['original_main_menu_widgets_retained']=len(original_widgets)
result['added_main_menu_widgets']=sorted(actual_widgets-original_widgets)
assert not any('OnPreviewKeyDown'==g['name'] for g in result['assets'][paths[1]]['graphs'])
(OUT/'saved-reload-audit.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print('CATRUN_MENU_SAVED_RELOAD_AUDIT_COMPLETE')
