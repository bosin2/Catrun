from pathlib import Path
code=Path(__file__).with_name('scan_uniform_surface.py').read_text(encoding='utf-8-sig');exec(compile(code.split("report={'neutral'")[0],__file__,'exec'))
rows=[]
for gain in [0,.1,.2,.3]:
 a['joint_fold_compression']=gain;mx=tot=0
 for stem,angles,limb in [('forearm_',[-90,-85,115,120],'F'),('shin_',range(80,121,5),'H')]:
  for side in ['L','R']:
   for angle in angles:
    reset();a.pose.bones['CTRL_'+stem+side].rotation_quaternion=Quaternion((1,0,0),math.radians(angle));a.update_tag();bpy.context.view_layer.update();co,_,_=evaluated();n=surface(co,selected[limb+'_'+side])['intersection_pairs'];mx=max(mx,n);tot+=n
 rows.append({'gain':gain,'max':mx,'total':tot});print('FOLD_GAIN',rows[-1],flush=True)
best=min(rows,key=lambda r:(r['max'],r['total'],r['gain']));reset();a['joint_fold_compression']=best['gain'];a.animation_data.action=bpy.data.actions['V2_AUTHORING_TEMPLATE'];sc.frame_set(1);a.update_tag();bpy.context.view_layer.update();bpy.ops.wm.save_as_mainfile(filepath=str(O/'SK_BlackCat_UniformJointRepair.blend'));(O/'QA/fold_support.json').write_text(json.dumps(rows,indent=2))
