from pathlib import Path
code=Path(__file__).with_name('scan_uniform_surface.py').read_text(encoding='utf-8-sig').split("report={'neutral'")[0];exec(compile(code,__file__,'exec'));O=O/'UniformDensity';rows=[]
def threshold(degrees):
 t=math.radians(degrees)
 for side in ['L','R']:
  a.pose.bones['shin_'+side].constraints['Deep FK fold distribution'].max_x=t
  path=a.pose.bones['hock_'+side].constraints['Deep FK hock continuation'].path_from_id('influence')
  next(fc for fc in a.animation_data.drivers if fc.data_path==path).driver.expression=f'on*(1-ik)*max(0,r-{t})/max(0.001,abs(r))'
for degrees in [100,95,90,85,80]:
 threshold(degrees);mx=tot=0
 for side in ['L','R']:
  for angle in range(85,121,5):
   reset();a.pose.bones['CTRL_shin_'+side].rotation_quaternion=Quaternion((1,0,0),math.radians(angle));a.update_tag();bpy.context.view_layer.update();co,_,_=evaluated();n=surface(co,selected['H_'+side])['intersection_pairs'];mx=max(mx,n);tot+=n
 rows.append({'threshold':degrees,'max':mx,'total':tot});print(rows[-1],flush=True)
best=min(rows,key=lambda r:(r['max'],r['total'],-r['threshold']));threshold(best['threshold']);reset();a.animation_data.action=bpy.data.actions['V2_AUTHORING_TEMPLATE'];sc.frame_set(1);a.update_tag();bpy.context.view_layer.update();a['deep_fold_note']=f"In FK, knee control rotation above {best['threshold']} degrees continues through the hock. IK unaffected; bake deform bones for export."
bpy.ops.wm.save_as_mainfile(filepath=bpy.data.filepath);(O/'QA/deep_fold_tuning.json').write_text(json.dumps(rows,indent=2))
