import bpy,bmesh,json
from pathlib import Path
from mathutils import Vector
O=Path(__file__).resolve().parents[1];m=bpy.data.objects['SK_BlackCat_RigV2']
bm=bmesh.new();bm.from_mesh(m.data)
cut=[]
def limb(c):
 if c.z>=.059 or abs(c.x)<=.012:return None
 if c.y<-.014:return 'F_'+('L' if c.x>0 else 'R')
 if c.y>.014:return 'H_'+('L' if c.x>0 else 'R')
for f in bm.faces:
 if f.material_index==0 and limb(f.calc_center_median()):cut.append(f)
border=[e for e in bm.edges if sum(f in cut for f in e.link_faces)==1 and len(e.link_faces)==2]
r={}
for k in ['F_L','F_R','H_L','H_R']:
 es=[e for e in border if limb(next(f.calc_center_median() for f in e.link_faces if f in cut))==k]
 vs=set(v for e in es for v in e.verts)
 degrees={v:sum(v in e.verts for e in es) for v in vs}
 r[k]={'edges':len(es),'vertices':len(vs),'non2':sum(d!=2 for d in degrees.values()),'min':[min(v.co[i] for v in vs) for i in range(3)],'max':[max(v.co[i] for v in vs) for i in range(3)],'coordinates':[list(v.co) for v in vs]}
print(json.dumps(r));(O/'QA/retopo_boundaries.json').write_text(json.dumps(r,indent=2))
