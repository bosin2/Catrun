"""Restore the authored five UCX boxes that Interchange omitted on import.
Dimensions are copied from Saved/BasketVariants20261125/build_variants.py:131.
Only this run's three new StaticMeshes are changed. No top lid collision.
"""
import unreal as u,json,shutil
from pathlib import Path
ROOT=Path(u.Paths.convert_relative_path_to_full(u.Paths.project_dir())).resolve();OUT=ROOT/'Saved/BasketIntegration20261125'
I=json.loads((OUT/'import_report.json').read_text());REPORT={}
BOXES=[((0,0,2.25),(69,69,4.5)),((-36.9,0,24.75),(4.2,78,40.5)),((36.9,0,24.75),(4.2,78,40.5)),((0,-36.9,24.75),(69.6,4.2,40.5)),((0,36.9,24.75),(69.6,4.2,40.5))]
for stage,data in I['stages'].items():
    path=data['body'];assert '/BasketVariants20261125/' in path
    disk=ROOT/'Content'/(path.split('.')[0].removeprefix('/Game/')+'.uasset');backup=OUT/'Before/ImportedCollision'/disk.name
    backup.parent.mkdir(parents=True,exist_ok=True)
    if not backup.exists():shutil.copy2(disk,backup)
    mesh=u.EditorAssetLibrary.load_asset(path);setup=mesh.get_editor_property('body_setup');geometry=setup.get_editor_property('agg_geom')
    before={n:len(geometry.get_editor_property(n)) for n in ['box_elems','convex_elems','sphere_elems','sphyl_elems']}
    boxes=[]
    for center,dimensions in BOXES:
        box=u.KBoxElem();box.set_editor_property('center',u.Vector(*center));box.set_editor_property('rotation',u.Rotator())
        for name,value in zip(['x','y','z'],dimensions):box.set_editor_property(name,float(value))
        boxes.append(box)
    geometry.set_editor_property('box_elems',boxes)
    for name in ['convex_elems','sphere_elems','sphyl_elems']:geometry.set_editor_property(name,[])
    setup.set_editor_property('agg_geom',geometry)
    setup.set_editor_property('collision_trace_flag',u.CollisionTraceFlag.CTF_USE_SIMPLE_AND_COMPLEX)
    assert u.EditorAssetLibrary.save_loaded_asset(mesh,False)
    REPORT[stage]={'asset':path,'before':before,'boxes_cm':[{'center':c,'dimensions':d} for c,d in BOXES]}
(OUT/'collision_repair.json').write_text(json.dumps(REPORT,indent=2),encoding='utf8')
