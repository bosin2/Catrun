"""Independent FBX round trip: every authored frame and bone world matrix."""
import bpy,json
from pathlib import Path
OUT=Path('C:/Users/whghk/Catrun/Saved/Stage3Integration20261125/Animation')
arm=next(o for o in bpy.data.objects if o.type=='ARMATURE')
arm.animation_data.action=bpy.data.actions['AN_BlackCat_ReleaseRing']
names=[b.name for b in arm.data.bones];parents={b.name:b.parent.name if b.parent else None for b in arm.data.bones}
original=[]
for frame in range(1,74):
    bpy.context.scene.frame_set(frame)
    original.append({n:arm.matrix_world@arm.pose.bones[n].matrix.copy() for n in names})
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.context.scene.render.fps=30
bpy.ops.import_scene.fbx(filepath=str(OUT/'AN_BlackCat_ReleaseRing.fbx'),ignore_leaf_bones=False,anim_offset=0.)
arm=next(o for o in bpy.data.objects if o.type=='ARMATURE')
actual_names=[b.name for b in arm.data.bones]
errors=[]
if set(names)!=set(actual_names):errors.append('Bone name mismatch')
if parents!={b.name:b.parent.name if b.parent else None for b in arm.data.bones}:errors.append('Bone hierarchy mismatch')
max_error=0.;worst=None
for frame in range(1,74):
    bpy.context.scene.frame_set(frame)
    for n in set(names)&set(actual_names):
        m=arm.matrix_world@arm.pose.bones[n].matrix
        e=max(abs(m[i][j]-original[frame-1][n][i][j]) for i in range(4) for j in range(4))
        if e>max_error:max_error=e;worst=[frame,n]
if max_error>1e-4:errors.append('Pose round-trip tolerance exceeded')
report={'success':not errors,'frames_checked':73,'bones_checked':len(names),'max_world_matrix_element_error':max_error,'worst':worst,'errors':errors,'actions':[(a.name,list(a.frame_range)) for a in bpy.data.actions]}
(OUT/'fbx_roundtrip.json').write_text(json.dumps(report,indent=2),encoding='utf8');print(report)
assert not errors,errors
