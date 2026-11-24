"""Restore simple collision omitted by the UE 5.8 Interchange FBX path.

Only isolated Stage3 packages are changed. Aperture boxes preserve the authored
clear rectangles; complex traces retain the render surface for sound occlusion.
"""
import unreal as u,json
from pathlib import Path
ROOT=Path(u.Paths.project_dir()).resolve();OUT=ROOT/'Saved/Stage3Integration20261125'
report={}; imported=json.loads((OUT/'import_report.json').read_text())
for name,row in imported['meshes'].items():
    lo,hi=row['bounds'];center=[(a+b)*.5 for a,b in zip(lo,hi)];size=[b-a for a,b in zip(lo,hi)]
    boxes=None
    if name.startswith(('SM_S3_Floor_','SM_S3_Wall_')) or name in ['SM_S3_GuardianStatue','SM_S3_PuzzleGate_Bars','SM_S3_ArmorDoor_Leaf','SM_S3_FinalGate_Leaf_L','SM_S3_FinalGate_Leaf_R']:
        boxes=[(center,size)]
    elif name in ['SM_S3_CatHoleWall','SM_S3_ArmorDoor_Frame','SM_S3_PuzzleGate_Frame']:
        clear,height=(60,65) if name=='SM_S3_CatHoleWall' else (150,240) if name=='SM_S3_ArmorDoor_Frame' else (140,240)
        side=(200-clear)/2
        boxes=[((side*.5,-15,150),(side,30,300)),((200-side*.5,-15,150),(side,30,300)),((100,-15,(height+300)*.5),(clear,30,300-height))]
    elif name=='SM_S3_FinalGate_LowerFrame':
        boxes=[((-350,0,150),(100,100,300)),((350,0,150),(100,100,300))]
    elif name=='SM_S3_FinalGate_UpperFrame':
        boxes=[((-350,0,250),(100,100,500)),((350,0,250),(100,100,500)),((0,0,599.6),(800,100,199.2))]
    if boxes is None:continue
    asset=u.EditorAssetLibrary.load_asset(row['path']);body=asset.get_editor_property('body_setup');geo=body.get_editor_property('agg_geom')
    elems=[]
    for location,dimensions in boxes:
        b=u.KBoxElem();b.set_editor_property('center',u.Vector(*location));b.set_editor_property('rotation',u.Rotator())
        for key,value in zip(['x','y','z'],dimensions):b.set_editor_property(key,float(value))
        elems.append(b)
    geo.set_editor_property('box_elems',elems)
    for key in ['convex_elems','sphere_elems','sphyl_elems']:geo.set_editor_property(key,[])
    body.set_editor_property('agg_geom',geo);body.set_editor_property('collision_trace_flag',u.CollisionTraceFlag.CTF_USE_SIMPLE_AND_COMPLEX)
    assert u.EditorAssetLibrary.save_loaded_asset(asset,False)
    report[name]={'boxes':boxes,'path':row['path']}
    row['simple']=len(boxes);row['convex']=0
(OUT/'collision_repair.json').write_text(json.dumps(report,indent=2),encoding='utf8')
(OUT/'import_report.json').write_text(json.dumps(imported,indent=2,ensure_ascii=False),encoding='utf8')
print('STAGE3_COLLISION_RESTORED',len(report))
