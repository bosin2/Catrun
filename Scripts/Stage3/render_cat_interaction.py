"""Native Blender visual evidence for the whole new clip, in an isolated process."""
import bpy,sys,json
from pathlib import Path
OUT=Path('C:/Users/whghk/Catrun/Saved/Stage3Integration20261125/Animation/Review');OUT.mkdir(parents=True,exist_ok=True)
sys.path.insert(0,'C:/Users/whghk/.codex/skills/blender-asset-qa/scripts')
import review_shots
arm=next(o for o in bpy.data.objects if o.type=='ARMATURE');mesh=next(o for o in bpy.data.objects if o.type=='MESH')
arm.animation_data.action=bpy.data.actions['AN_BlackCat_ReleaseRing']
results=[]
for frame in range(1,74):
    bpy.context.scene.frame_set(frame)
    r=review_shots.run(objects=[mesh.name],out=str(OUT/f'Frame_{frame:03}.png'),views=['three_quarter'],mode='material',res=384)
    results.append(r)
for frame in [1,25,37,45,73]:
    bpy.context.scene.frame_set(frame)
    review_shots.run(objects=[mesh.name],out=str(OUT/f'Angles_{frame:03}.png'),views=['front','right','three_quarter'],mode='material',res=512)
bpy.context.scene.frame_set(45)
review_shots.run(objects=[mesh.name],out=str(OUT/'Wire_045.png'),views=['front','right'],mode='wire',res=512)
(OUT/'frames.json').write_text(json.dumps(results,indent=2),encoding='utf8')
print('CAT_VISUAL_FRAMES_READY',len(results))
