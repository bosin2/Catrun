import ast,bpy,json,pathlib,hashlib
OUT=pathlib.Path(__file__).resolve().parents[1]
SOURCE=pathlib.Path(r'C:/Users/whghk/Desktop/CastleKit/BlackCat/Final/SK_BlackCat_Final.blend')
tree=ast.parse((OUT/'Scripts/author.py').read_text())
funcs=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in ['curves','signature']]
code=ast.unparse(ast.Module(body=funcs,type_ignores=[])).replace("if not a.name.startswith('AN_BlackCat_Elevator_')","if a.name.startswith('AN_BlackCat_') and not a.name.startswith('AN_BlackCat_Elevator_')")
exec(code)
results=[]
for path in [SOURCE,OUT/'SK_BlackCat_Elevator.blend']:
 bpy.ops.wm.open_mainfile(filepath=str(path));arm=bpy.data.objects['ARM_BlackCat_Final'];mesh=bpy.data.objects['SK_BlackCat_Final']
 mesh.data.calc_loop_triangles()
 results.append({'file':str(path),'signature':signature(),'vertices':len(mesh.data.vertices),'triangles':len(mesh.data.loop_triangles),'materials':[m.name for m in mesh.data.materials],'bones':len(arm.data.bones),'original_actions':sorted(a.name for a in bpy.data.actions if a.name.startswith('AN_BlackCat_') and not a.name.startswith('AN_BlackCat_Elevator_'))})
result={'original_data_equal_after_save_reload':results[0]['signature']==results[1]['signature'],'snapshots':results,'source_sha256':hashlib.sha256(SOURCE.read_bytes()).hexdigest()}
(OUT/'QA/preservation_reload.json').write_text(json.dumps(result,indent=2));print('PRESERVATION_RELOAD',result['original_data_equal_after_save_reload']);assert result['original_data_equal_after_save_reload']
