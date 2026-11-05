"""Repeatable saved-settings-only contrast and panel-padding corrections."""
import hashlib
import json
from pathlib import Path
import sys
import unreal

ROOT=Path(unreal.Paths.project_dir()).resolve()
OUT=ROOT/'Saved/Menu20261105'
sys.path.insert(0,str(ROOT/'Scripts/Menu'))
from menu_graph import audit, compile_bp, properties, widgets

def color(value):
    channels=[int(value[i:i+2],16)/255.0 for i in (0,2,4)]
    channels=[c/12.92 if c<=0.04045 else ((c+0.055)/1.055)**2.4 for c in channels]
    return unreal.LinearColor(*channels,1)

path='/Game/UI/Settings/WBP_Setting'
bp=unreal.load_asset(path)
button=widgets(bp)['CloseButton']
style=button.get_editor_property('widget_style')
for name,value in [('hovered','4C4B48'),('pressed','615640')]:
    brush=style.get_editor_property(name)
    brush.set_editor_property('tint_color',unreal.SlateColor(specified_color=color(value)))
    style.set_editor_property(name,brush)
properties(button,widget_style=style)
panel=widgets(bp)['Panel_Setting']
background=panel.get_editor_property('background')
background.set_editor_property('tint_color',unreal.SlateColor(specified_color=unreal.LinearColor(1,1,1,1)))
properties(panel,background=background,padding=unreal.Margin(28,28,28,28))
compile_bp(bp)
assert unreal.EditorAssetLibrary.save_loaded_asset(bp,False)
manifest_path=OUT/'author-manifest.json'
manifest=json.loads(manifest_path.read_text(encoding='utf-8'))
for asset in manifest['assets']:
    if asset['asset']==path:
        asset['after_sha256']=hashlib.sha256((ROOT/'Content/UI/Settings/WBP_Setting.uasset').read_bytes()).hexdigest()
manifest['polish']='CloseButton contrast; Panel_Setting explicit 28-unit padding on all edges and white background brush tint'
manifest_path.write_text(json.dumps(manifest,indent=2,ensure_ascii=False),encoding='utf-8')
(OUT/'close-button-polish-audit.json').write_text(json.dumps(audit(bp),indent=2,ensure_ascii=False),encoding='utf-8')
(OUT/'panel-polish-properties.json').write_text(json.dumps({
    'padding':str(panel.get_editor_property('padding')),
    'background':str(panel.get_editor_property('background')),
    'brush_color':str(panel.get_editor_property('brush_color')),
    'close_button_style':str(button.get_editor_property('widget_style'))
},indent=2,ensure_ascii=False),encoding='utf-8')
print('CATRUN_MENU_SETTINGS_POLISH_COMPLETE')
