"""Run in a separate Blender process; author only a new fitted masonry lining.

Dimensions are centimeters, measured from the original doorframe's inner profile.
Original frame/leaf geometry and the shared Blender scene are never modified.
"""
import json
from pathlib import Path
import bpy
import bmesh

ROOT = Path('C:/Users/whghk/Catrun')
DEST = ROOT / 'SourceArt/Tutorial/Passages'
DEST.mkdir(parents=True, exist_ok=True)
NAME = 'SM_Tutorial_BedroomDoorLining'
# A 3 cm reveal behind the wooden inner edge avoids changing the clear opening.
PROFILE = [(0, 62.8), (120, 61.78), (130, 61.53), (140, 60.53),
           (150, 58.39), (160, 55.02), (170, 50.78), (180, 43.89),
           (190, 35.35), (200, 23.39), (205, 16.12), (210, 5.78),
           (214, 0), (226, 0)]
scene = bpy.data.scenes.new('TutorialPassageLining_Source')
scene.unit_settings.system = 'METRIC'
scene.unit_settings.scale_length = .01
bpy.context.window.scene = scene
vertices, faces = [], []
for side in (-1, 1):
    for index, ((z0, inner0), (z1, inner1)) in enumerate(zip(PROFILE, PROFILE[1:])):
        start = len(vertices)
        # FBX UE's Y flip is irrelevant for this symmetric asset.
        vertices.extend([(side*inner0, -14, z0), (side*84, -14, z0),
                         (side*84, -14, z1), (side*inner1, -14, z1),
                         (side*inner0, 14, z0), (side*84, 14, z0),
                         (side*84, 14, z1), (side*inner1, 14, z1)])
        shell = [(0,3,2,1),(4,5,6,7),(1,2,6,5)]
        if inner0 > 0 or inner1 > 0: shell.append((3,0,4,7))
        if index == 0: shell.append((0,1,5,4))
        if index == len(PROFILE)-2: shell.append((2,3,7,6))
        faces.extend([tuple(start+i for i in face) for face in shell])
mesh = bpy.data.meshes.new(NAME)
mesh.from_pydata(vertices, [], faces)
mesh.update()
bm = bmesh.new(); bm.from_mesh(mesh)
bmesh.ops.remove_doubles(bm, verts=list(bm.verts), dist=.001)
bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
assert all(edge.is_manifold for edge in bm.edges), 'Lining must be a closed clean shell'
bm.to_mesh(mesh); bm.free()
obj = bpy.data.objects.new(NAME, mesh)
scene.collection.objects.link(obj)
bpy.context.view_layer.objects.active = obj
obj.select_set(True)
bpy.ops.object.mode_set(mode='EDIT')
bpy.ops.mesh.select_all(action='SELECT')
bpy.ops.uv.smart_project(angle_limit=1.1519, island_margin=.02)
bpy.ops.object.mode_set(mode='OBJECT')
bpy.data.libraries.write(str(DEST/(NAME+'.blend')), {scene}, fake_user=True)
bpy.ops.export_scene.fbx(filepath=str(DEST/(NAME+'.fbx')), use_selection=True,
                        object_types={'MESH'}, apply_unit_scale=True,
                        apply_scale_options='FBX_SCALE_NONE', axis_forward='-Y', axis_up='Z',
                        use_mesh_modifiers=True, add_leaf_bones=False, bake_anim=False)
result = {'asset':NAME,'bounds_cm':[-84,84,-14,14,0,226],
          'profile_z_halfwidth_cm':PROFILE,'vertices':len(mesh.vertices),
          'faces':len(mesh.polygons),'original_scene_saved':False}
(DEST/'dimensions.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf8')
