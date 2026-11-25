from pathlib import Path
import hashlib
ROOT=Path(__file__).parent.parent
__file__=str(ROOT/'create_revision.py')
exec(compile((ROOT/'create_revision.py').read_text(encoding='utf8').split('# BEGIN_PREVIEW')[0],__file__,'exec'))
QDIR=ROOT/'QA_Retained';QDIR.mkdir(exist_ok=True)
cases=[('touch',1),('touch',32),('touch',55),('touch',79),('prepare',1),('prepare',20),('prepare',53),('launch',7),('walk',1),('walk',32),('flight',1)]
action_map={'touch':'AN_CompactPortal_SeatedListenTouch','prepare':'AN_CompactPortal_HipsBackWiggle','launch':'AN_CompactPortal_SeatedTakeoff','walk':'AN_CompactPortal_WalkReview','flight':'AN_CompactPortal_AirReach'}
reference={}
def evaluated_vertices(ob):
 ev=ob.evaluated_get(bpy.context.evaluated_depsgraph_get());me=ev.to_mesh();vs=[v.co.copy() for v in me.vertices];ev.to_mesh_clear();return vs
weights={v.index:[(m.vertex_groups[g.group].name,g.weight) for g in v.groups if g.weight>1e-5] for v in m.data.vertices}
materials={i:set() for i in range(len(m.data.vertices))}
for poly in m.data.polygons:
 for i in poly.vertices:materials[i].add(m.material_slots[poly.material_index].name)
for kind,f in cases:
 evaluate(kind,f);reference[(kind,f)]={'verts':evaluated_vertices(m),'bones':{n:a.pose.bones[n].matrix.copy() for n in original_names}}
native=ROOT/'SK_BlackCat_CompactPortal.blend';bpy.ops.wm.open_mainfile(filepath=str(native));sc=bpy.context.scene;a=next(o for o in sc.objects if o.type=='ARMATURE');m=bpy.data.objects['SK_BlackCat_Final']
rows=[];region_max={};top=[]
def region(i):
 names=[n for n,w in weights[i]]
 if any(n.startswith('tail_') for n in names):return 'tail'
 if any(n.startswith(('ear_','ear_tip_')) for n in names):return 'ear'
 if any(n.startswith('Lid_') for n in names):return 'lid'
 if any(n=='collar' for n in names):return 'collar'
 if any(n=='bell' for n in names):return 'bell'
 return 'head_face'
for kind,f in cases:
 a.animation_data.action=bpy.data.actions[action_map[kind]];sc.frame_set(f);bpy.context.view_layer.update();actual=evaluated_vertices(m);ref=reference[(kind,f)]
 ds=[(x-y).length for x,y in zip(actual,ref['verts'])];indices=sorted(range(len(ds)),key=lambda i:ds[i],reverse=True)
 bone_max=max(max(abs(a.pose.bones[n].matrix[r][c]-ref['bones'][n][r][c]) for r in range(4) for c in range(4)) for n in ref['bones'])
 per={}
 for i,d in enumerate(ds):
  k=region(i);per[k]=max(per.get(k,0.),d);region_max[k]=max(region_max.get(k,0.),d)
 top_items=[{'index':i,'distance_m':ds[i],'region':region(i),'materials':sorted(materials[i]),'weights':weights[i],'before':list(ref['verts'][i]),'after':list(actual[i])} for i in indices[:6]]
 rows.append({'kind':kind,'frame':f,'bone_max_matrix_difference':bone_max,'per_region_max_m':per,'top_vertices':top_items})
 top.extend([dict(item,kind=kind,frame=f) for item in top_items])
result={'native_file':str(native),'region_max_m':region_max,'cases':rows,'global_top':sorted(top,key=lambda x:x['distance_m'],reverse=True)[:12]}
(QDIR/'rebind_error_classification.json').write_text(json.dumps(result,indent=2))
print(json.dumps({'region_max_m':region_max,'global_top':result['global_top'][:4]},indent=2),flush=True)
