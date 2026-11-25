import bpy,sys,json
from pathlib import Path
O=Path(__file__).resolve().parents[1]/'SitSleep';sys.path.insert(0,'C:/Users/whghk/.codex/skills/blender-asset-qa/scripts');import qa_check,review_shots
obs=[o.name for o in bpy.context.scene.objects if o.type=='MESH'];q=qa_check.run(objects=obs,profile='game',eps=.0001,tol=.002)
(O/'sit_mesh_qa.json').write_text(json.dumps(q,indent=2,default=str),encoding='utf8');print(json.dumps(q,default=str),flush=True)
for mode in ['random','wire']:review_shots.run(objects=obs,out=str(O/'Previews'/f'sit_review_{mode}.png'),mode=mode,res=420)
