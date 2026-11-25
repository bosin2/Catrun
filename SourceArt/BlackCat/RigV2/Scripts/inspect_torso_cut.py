import bpy,bmesh,json
m=bpy.data.objects['SK_BlackCat_RigV2'];bm=bmesh.new();bm.from_mesh(m.data);dv=bm.verts.layers.deform.verify()
head={g.index for g in m.vertex_groups if g.name=='head' or g.name.startswith(('jaw','ear_','lid_','eye_','tongue'))}
for threshold in [.1,.4,.7]:
 cut={f for f in bm.faces if f.material_index==0 and all(v.co.z<.14 for v in f.verts) and sum(sum(w for g,w in v[dv].items() if g in head) for v in f.verts)/len(f.verts)<threshold and all(v.co.y<.075 for v in f.verts)}
 edges=[e for e in bm.edges if len(e.link_faces)==2 and sum(f in cut for f in e.link_faces)==1]
 adj={}
 for e in edges:
  for v in e.verts:adj.setdefault(v,[]).append(e.other_vert(v))
 groups=[];unseen=set(adj)
 while unseen:
  stack=[unseen.pop()];found=[]
  while stack:
   v=stack.pop();found.append(v)
   for n in adj[v]:
    if n in unseen:unseen.remove(n);stack.append(n)
  groups.append({'count':len(found),'bounds':[[min(v.co[k] for v in found),max(v.co[k] for v in found)] for k in range(3)],'degrees':sorted(set(len(adj[v]) for v in found))})
 print('CUT',threshold,len(cut),'LOOPS',json.dumps(groups))
