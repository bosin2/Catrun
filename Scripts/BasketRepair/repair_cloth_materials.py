"""Persist actual skeletal material slots, not copies returned by array iteration."""
import unreal as u,json,shutil
from pathlib import Path
ROOT=Path(u.Paths.convert_relative_path_to_full(u.Paths.project_dir())).resolve();OUT=ROOT/'Saved/BasketRepair20261125';OUT.mkdir(parents=True,exist_ok=True)
BASE='/Game/Environment/Shared/Castle/Props/Hiding/BasketVariants20261125';R={}
for stage in [1,2,3]:
 path=BASE+f'/Stage{stage}/Meshes/SK_HideBasket_Stage{stage}_Cloth'
 disk=ROOT/'Content'/(path.removeprefix('/Game/')+'.uasset');backup=OUT/'Before'/disk.name;backup.parent.mkdir(parents=True,exist_ok=True)
 if not backup.exists():shutil.copy2(disk,backup)
 mesh=u.EditorAssetLibrary.load_asset(path);mat=u.EditorAssetLibrary.load_asset(BASE+f'/Shared/Materials/M_Cloth_Stage{stage}');assert mesh and mat
 u.MaterialEditingLibrary.set_material_usage(mat,u.MaterialUsage.MATUSAGE_SKELETAL_MESH)
 slots=mesh.get_editor_property('materials');before=[str(x.material_interface) for x in slots]
 for i in range(len(slots)):
  slot=slots[i];slot.set_editor_property('material_interface',mat);slots[i]=slot
 mesh.set_editor_property('materials',slots)
 assert all(x.material_interface==mat for x in mesh.get_editor_property('materials'))
 u.MaterialEditingLibrary.recompile_material(mat)
 assert u.EditorAssetLibrary.save_loaded_asset(mat,False);assert u.EditorAssetLibrary.save_loaded_asset(mesh,False)
 R[str(stage)]={'before':before,'after':[x.material_interface.get_path_name() for x in mesh.get_editor_property('materials')]}
(OUT/'material_repair.json').write_text(json.dumps(R,indent=2),encoding='utf8')
