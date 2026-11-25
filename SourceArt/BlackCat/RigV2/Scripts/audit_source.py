import bpy, json, math, sys
import numpy as np
from pathlib import Path
from mathutils import Vector, Quaternion

OUT=Path(__file__).resolve().parents[1]
arm=next(o for o in bpy.data.objects if o.type=='ARMATURE')
mesh=next(o for o in bpy.data.objects if o.type=='MESH')
sc=bpy.context.scene
sys.path.insert(0,r'C:/Users/whghk/.codex/skills/blender-core/scripts')
import env_report
r={'environment':env_report.run(),'bones':{},'materials':{},'actions':{}}
for b in arm.data.bones:
    r['bones'][b.name]={'head':list(b.head_local),'tail':list(b.tail_local),'matrix':[list(x) for x in b.matrix_local]}
for i,s in enumerate(mesh.material_slots):
    ids=sorted({v for p in mesh.data.polygons if p.material_index==i for v in p.vertices})
    a=np.array([mesh.data.vertices[j].co[:] for j in ids])
    r['materials'][s.name]={'verts':len(ids),'min':a.min(0).tolist(),'max':a.max(0).tolist()}
    if s.material and s.material.node_tree:
        p=next((n for n in s.material.node_tree.nodes if n.type=='BSDF_PRINCIPLED'),None)
        if p:s.material.diffuse_color=p.inputs['Base Color'].default_value
def coords():
    e=mesh.evaluated_get(bpy.context.evaluated_depsgraph_get());m=e.to_mesh()
    a=np.array([v.co[:] for v in m.vertices]);e.to_mesh_clear();return a
for a in bpy.data.actions:
    arm.animation_data.action=a
    worst=0; neg=0; flip=0;prev={};blink=[]
    for f in range(int(a.frame_range[0]),int(a.frame_range[1])+1):
        sc.frame_set(f)
        for p in arm.pose.bones:
            q=p.rotation_quaternion
            if p.name in prev and q.dot(prev[p.name])<0:flip+=1
            prev[p.name]=q.copy()
            worst=max(worst,abs(q.angle));neg+=int(min(p.scale)<=0)
        blink.append((sum(arm.pose.bones[n].rotation_quaternion.angle for n in arm.pose.bones.keys() if n.startswith('Lid_')),f))
    r['actions'][a.name]={'frames':list(a.frame_range),'quaternion_sign_flips':flip,'negative_scale_count':neg,'maximum_rotation_degrees':math.degrees(worst),'blink_peak':max(blink)}
arm.animation_data.action=None
for p in arm.pose.bones:p.matrix_basis.identity()
sc.frame_set(1);bpy.context.view_layer.update()
r['armature_preserve_volume']=mesh.modifiers[0].use_deform_preserve_volume
r['smooth_faces']=sum(p.use_smooth for p in mesh.data.polygons)
r['weight_sums']=[min(sum(g.weight for g in v.groups) for v in mesh.data.vertices),max(sum(g.weight for g in v.groups) for v in mesh.data.vertices)]
# Adjacency discontinuity in weights, with biggest spatial edges recorded.
gids={g.index:g.name for g in mesh.vertex_groups}
edges=[]
for e in mesh.data.edges:
    v,w=[mesh.data.vertices[i] for i in e.vertices]
    a={g.group:g.weight for g in v.groups};b={g.group:g.weight for g in w.groups}
    delta=sum(abs(a.get(i,0)-b.get(i,0)) for i in set(a)|set(b))
    if delta>1.5:edges.append({'vertices':list(e.vertices),'length':(v.co-w.co).length,'delta':delta,'co':list((v.co+w.co)/2),'groups':[[gids[g.group] for g in x.groups if g.weight>.1] for x in [v,w]]})
r['sharp_weight_edges']=sorted(edges,key=lambda x:x['length'],reverse=True)[:30]
(OUT/'QA'/'source_audit.json').write_text(json.dumps(r,indent=2))
camera=bpy.data.objects.new('QA_Camera',bpy.data.cameras.new('QA_Camera'));sc.collection.objects.link(camera);sc.camera=camera
camera.data.type='ORTHO';camera.data.ortho_scale=.31
sc.render.engine='BLENDER_WORKBENCH';sc.render.resolution_x=800;sc.render.resolution_y=800;sc.render.resolution_percentage=100
sc.display.shading.light='STUDIO';sc.display.shading.color_type='MATERIAL';sc.display.shading.show_shadows=True;sc.display.shading.show_cavity=True
sc.display.shading.background_type='WORLD'
if not sc.world:sc.world=bpy.data.worlds.new('QA_World')
sc.world.color=(.18,.18,.18)
sc.render.image_settings.file_format='PNG'
def shot(name, pos, target=(0,0,.105), scale=.31):
    camera.location=pos;camera.rotation_euler=(Vector(target)-camera.location).to_track_quat('-Z','Y').to_euler();camera.data.ortho_scale=scale
    sc.render.filepath=str(OUT/'Previews'/name);bpy.ops.render.render(write_still=True)
shot('before_rest_front.png',(0,-.6,.18))
shot('before_rest_threequarter.png',(.4,-.5,.25))
shot('before_rest_side.png',(.6,0,.16))
arm.animation_data.action=bpy.data.actions['AN_BlackCat_Idle']
peak=r['actions']['AN_BlackCat_Idle']['blink_peak'][1]
for f in [1,peak-2,peak]:
    sc.frame_set(f);shot(f'before_face_{f:03d}.png',(0,-.6,.17),(0,-.057,.14),.16)
(OUT/'QA'/'source_audit.json').write_text(json.dumps(r,indent=2))
print('SOURCE_AUDIT_FINISHED',flush=True)
