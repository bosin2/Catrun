import bpy,json,hashlib
from pathlib import Path
O=Path(__file__).resolve().parents[1]/'UniformJointRepair'/'UniformDensity';a=bpy.data.objects['ARM_BlackCat_RigV2'];m=bpy.data.objects['SK_BlackCat_RigV2']
t=bpy.data.texts.get('START_HERE_RigV2.txt') or bpy.data.texts.new('START_HERE_UniformLowPoly.txt');t.name='START_HERE_UniformLowPoly.txt';t.clear();t.write((O/'README.md').read_text(encoding='utf-8'))
a['uniform_topology_note']='Connected torso and legs; five broad surface rings per leg; flat-shaded triangular facets. Revised bind pose: legacy actions require retesting.'
a['review_status']='358 isolated FK inputs and 273 frames in 3 diagnostic clips checked. See START_HERE_UniformLowPoly.txt for scope. No Unreal import.'
a.animation_data.action=bpy.data.actions['V2_AUTHORING_TEMPLATE'];a['controls_enabled']=1.;bpy.context.scene.frame_set(1);a.update_tag();bpy.context.view_layer.update()
invalid=[]
for owner in list(bpy.data.objects)+[m.data.shape_keys]:
 if owner and owner.animation_data:
  for fc in owner.animation_data.drivers:
   if not fc.driver.is_valid:invalid.append({'owner':owner.name,'path':fc.data_path})
assert not invalid,invalid
path=O/'SK_BlackCat_UniformLowPoly.blend';bpy.ops.wm.save_as_mainfile(filepath=str(path))
(O/'QA/final_file.json').write_text(json.dumps({'file':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'invalid_drivers':invalid,'mesh_vertices':len(m.data.vertices),'mesh_triangles':sum(len(p.vertices)-2 for p in m.data.polygons),'active_action':a.animation_data.action.name},indent=2))
