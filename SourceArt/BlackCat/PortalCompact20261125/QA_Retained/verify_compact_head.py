from pathlib import Path
ROOT=Path(__file__).parent.parent
__file__=str(ROOT/'create_revision.py')
exec(compile((ROOT/'create_revision.py').read_text(encoding='utf8').split('# BEGIN_PREVIEW')[0],__file__,'exec'))
QDIR=ROOT/'QA_Retained';QDIR.mkdir(exist_ok=True)
cam=preview_setup();samples=[]
head_group=m.vertex_groups['head'].index
ids=[v.index for v in m.data.vertices if len(v.groups)==1 and v.groups[0].group==head_group and abs(v.groups[0].weight-1)<1e-6]
for kind,f,label,loc in [('walk',1,'side',(.50,.03,.15)),('touch',32,'threequarter',(.38,-.42,.17)),('prepare',53,'rear',(.40,.33,.17))]:
 evaluate(kind,f)
 ev=m.evaluated_get(bpy.context.evaluated_depsgraph_get());me=ev.to_mesh();transform=a.pose.bones['head'].matrix@a.data.bones['head'].matrix_local.inverted()
 maximum=max((me.vertices[i].co-transform@m.data.vertices[i].co).length for i in ids);ev.to_mesh_clear()
 samples.append({'kind':kind,'frame':f,'rigid_head_vertex_count':len(ids),'max_rigid_transform_error_m':maximum})
 cam.location=loc;cam.rotation_euler=(Vector((0,-.015,.12))-cam.location).to_track_quat('-Z','Y').to_euler();sc.render.filepath=str(QDIR/f'{kind}_{f}_{label}_after.png');bpy.ops.render.render(write_still=True)
(QDIR/'compact_head_validation.json').write_text(json.dumps({'samples':samples,'head_rest_geometry_edited':False,'scope':'Connected head fur shell weights only; unchanged separate eye, ear, eyelid, collar, bell and tail islands'},indent=2))
print('COMPACT_HEAD_QA',samples,flush=True)
