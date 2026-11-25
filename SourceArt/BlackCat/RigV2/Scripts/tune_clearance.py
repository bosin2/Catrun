from pathlib import Path
code=Path(__file__).with_name('scan_uniform_surface.py').read_text(encoding='utf-8-sig');exec(compile(code.split("report={'neutral'")[0],__file__,'exec'))
reset();co,_,_=evaluated();auth=np.array([x.value for x in m.data.attributes['uniform_body_surface'].data]);low=np.where((auth[poly]>0)&(co[tris].max(axis=1)[:,2]<.085))[0];rows=[]
for gain in [0,.3,.6,.9,1.2,1.5]:
 reset();a['shoulder_clearance_gain']=gain;a.animation_data.action=bpy.data.actions['V2_TEST_Body'];tot=0;mx=0;lm=0
 for f in range(1,92,2):
  sc.frame_set(f);a.update_tag();bpy.context.view_layer.update();co,_,_=evaluated();r=surface(co,low);tot+=r['intersection_pairs'];mx=max(mx,r['intersection_pairs']);lm=max(lm,max(surface(co,ids)['intersection_pairs'] for ids in selected.values()))
 rows.append({'gain':gain,'max':mx,'total':tot,'limb_max':lm});print('GAIN',rows[-1],flush=True)
best=min(rows,key=lambda x:(x['max'],x['total'],x['gain']));reset();a['shoulder_clearance_gain']=best['gain'];a.animation_data.action=bpy.data.actions['V2_AUTHORING_TEMPLATE'];sc.frame_set(1);a.update_tag();bpy.context.view_layer.update();bpy.ops.wm.save_as_mainfile(filepath=str(O/'SK_BlackCat_UniformJointRepair.blend'));(O/'QA/clearance_tuning.json').write_text(json.dumps(rows,indent=2))
