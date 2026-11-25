"""Keep exit UI visible when the quarter-view foreground wall covers its floor."""
import unreal as u,json,shutil
from pathlib import Path
root=Path(u.Paths.convert_relative_path_to_full(u.Paths.project_dir())).resolve();out=root/'Saved/BasketRepair20261125'
path='/Game/Systems/Interaction/Hiding/Visual/M_BasketExitArc';disk=root/'Content/Systems/Interaction/Hiding/Visual/M_BasketExitArc.uasset';backup=out/'Before'/disk.name
if not backup.exists():shutil.copy2(disk,backup)
m=u.EditorAssetLibrary.load_asset(path);assert m
r={'blend':str(m.get_blend_mode()),'before':m.get_editor_property('disable_depth_test')}
assert m.get_blend_mode() in [u.BlendMode.BLEND_TRANSLUCENT,u.BlendMode.BLEND_ADDITIVE],r
m.set_editor_property('disable_depth_test',True);u.MaterialEditingLibrary.recompile_material(m)
assert u.EditorAssetLibrary.save_loaded_asset(m,False);r['after']=m.get_editor_property('disable_depth_test')
(out/'guide_visibility.json').write_text(json.dumps(r,indent=2),encoding='utf8')
