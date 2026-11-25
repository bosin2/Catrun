import bpy,sys,json,math,numpy as np,hashlib
from pathlib import Path
from mathutils.bvhtree import BVHTree
main_path=Path('C:/Users/whghk/.codex/worktrees/110f/Catrun/SourceArt/BlackCat/PortalCompact20261125/create_revision.py');__file__=str(main_path);exec(compile(main_path.read_text().split('# BEGIN_PREVIEW')[0],__file__,'exec'))
qa_root=Path('C:/Users/whghk/.codex/worktrees/110f/Catrun/SourceArt/BlackCat/PortalCompact20261125');src=(qa_root.parent/'RigV2'/'Scripts'/'scan_uniform_surface.py').read_text();exec(src[src.index('def crosses('):src.index('report=')].replace('def surface(','def scan_surface('))
mesh=body.data;mesh.calc_loop_triangles();tris=np.array([t.vertices[:] for t in mesh.loop_triangles]);state=json.loads(a['portal_surface_state']);groups={k:set(v) for k,v in state['limb_vertices'].items()};groups['BODY']=set(state['body_vertices']);selected={k:np.array([i for i,t in enumerate(tris) if set(t)<=ids]) for k,ids in groups.items()};rows=[]
for kind,end in [('walk',121),('touch',91),('prepare',53),('launch',13),('flight',19)]:
 for f in range(1,end+1):
  evaluate(kind,f);e=body.evaluated_get(bpy.context.evaluated_depsgraph_get());me=e.to_mesh();co=np.array([v.co[:] for v in me.vertices]);e.to_mesh_clear();stats={k:scan_surface(co,ids) for k,ids in selected.items()};rows.append({'kind':kind,'frame':f,'regions':stats,'floor_z_mm':{k:float(co[list(ids),2].min()*1000) for k,ids in groups.items()}})
 print('SCANNED',kind,flush=True)
report={'scope':'Per-region self-intersections, including every integer frame; does not certify cross-region or retained original face intersections','sample_count':len(rows),'triangles':len(tris),'module_sha256':hashlib.sha256((qa_root/'body_surface.py').read_bytes()).hexdigest(),'pose_sha256':hashlib.sha256((qa_root/'create_revision.py').read_bytes()).hexdigest(),'max_intersections':{k:max(r['regions'][k]['intersection_pairs'] for r in rows) for k in selected},'max_near_zero_triangles':{k:max(r['regions'][k]['near_zero_triangles'] for r in rows) for k in selected},'min_region_z_mm':{k:min(r['floor_z_mm'][k] for r in rows) for k in groups},'floor_penetration_gt_0_2mm':[{'kind':r['kind'],'frame':r['frame'],'floor_z_mm':r['floor_z_mm']} for r in rows if min(r['floor_z_mm'].values())<-.2],'bad_frames':[r for r in rows if any(q['intersection_pairs'] or q['near_zero_triangles'] for q in r['regions'].values())]};(qa_root/'QA_Surface'/'motion_scan_all_frames.json').write_text(json.dumps(report,indent=2));print(json.dumps({k:v for k,v in report.items() if k!='bad_frames'}),flush=True)



