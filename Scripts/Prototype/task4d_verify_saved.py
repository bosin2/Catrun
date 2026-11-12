"""Read saved task packages in the existing editor, without graph reconstruction."""
import sys,unreal,json,hashlib,re,copy
from decimal import Decimal
sys.path.insert(0,unreal.Paths.project_dir()+'Scripts/Prototype')
from task4d_assets import *
edworld=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem);lv=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem);assert not edworld.get_game_world()
result={'initial_world':edworld.get_editor_world().get_path_name(),'dirty_before':[p.get_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()]+[p.get_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()]}
bp=AS.load_asset(PRES);result['bp_status']=str(bp.get_editor_property('status'));assert bp.get_editor_property('status')==unreal.BlueprintStatus.BS_UP_TO_DATE
pp=unreal.get_default_object(bp.generated_class()).get_editor_property('RevealPostProcess');result['camera_motion_blur']={'override':pp.get_editor_property('override_motion_blur_amount'),'amount':pp.get_editor_property('motion_blur_amount')};assert result['camera_motion_blur']=={'override':True,'amount':0.}
expected=json.loads((OUT/'presentation-after.json').read_text());actual=dump(bp)
# Pin string serialization normalizes numbers after package reload; links/nodes remain exact.
def normalized(data):
 data=copy.deepcopy(data)
 for g in data['graphs']:
  for n in g['nodes']:
   for p in n['input']:
    if re.fullmatch(r'[+-]?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?(?:,[+-]?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)*',p['value']):p['value']=','.join(str(Decimal(x).normalize()) if Decimal(x) else '0' for x in p['value'].split(','))
 return data
assert normalized(expected)==normalized(actual),'Saved connected graph/pin values differ'
result['graphs']=len(actual['graphs']);result['nodes']=sum(len(g['nodes']) for g in actual['graphs']);result['components']=[]
sds=unreal.get_engine_subsystem(unreal.SubobjectDataSubsystem);seen=set()
for h in sds.k2_gather_subobject_data_for_blueprint(bp):
 c=unreal.SubobjectDataBlueprintFunctionLibrary.get_associated_object(unreal.SubobjectDataBlueprintFunctionLibrary.get_data(h))
 if isinstance(c,unreal.StaticMeshComponent) and c.get_path_name() not in seen:
  seen.add(c.get_path_name());result['components'].append({'name':c.get_name(),'location':str(c.get_editor_property('relative_location')),'rotation':str(c.get_editor_property('relative_rotation')),'scale':str(c.get_editor_property('relative_scale3d')),'shadow':c.get_editor_property('cast_shadow'),'mesh':c.static_mesh.get_path_name(),'material':c.get_material(0).get_path_name()})
result['materials']={}
for path in [BARS,DUST]:
 m=AS.load_asset(path);result['materials'][path]={'domain':str(m.get_editor_property('material_domain')),'expressions':len(unreal.MaterialEditingLibrary.get_material_expressions(m)),'statistics':str(unreal.MaterialEditingLibrary.get_statistics(m)),'custom_code':[e.get_editor_property('code') for e in unreal.MaterialEditingLibrary.get_material_expressions(m) if isinstance(e,unreal.MaterialExpressionCustom)]}
settings=AS.load_asset('/Game/Systems/Interaction/Puzzles/DA_StatuePuzzleSettings');result['settings']={}
for name,expected_value in {'PushSpeed':100.,'PushAcceleration':160.,'PushDeceleration':240.,'ContactDistance':12.,'SeatingOverlap':.8,'SocketAxisTolerance':24.,'SocketHeightTolerance':12.,'PlateTravel':2.,'GateTravel':280.,'GateSpeed':140.,'GateFloorClearance':4.}.items():
 actual_value=settings.get_editor_property(name);assert abs(actual_value-expected_value)<1.e-6;result['settings'][name]=actual_value
result['settings']['bRequireInteractKey']=settings.get_editor_property('bRequireInteractKey');assert result['settings']['bRequireInteractKey']==False
registry=unreal.AssetRegistryHelpers.get_asset_registry();options=unreal.AssetRegistryDependencyOptions(include_soft_package_references=True,include_hard_package_references=True)
result['dependencies']={path:[str(x) for x in registry.get_dependencies(unreal.Name(path),options)] for path in [PRES,BARS,DUST]}
assert all('/Tutorial/' not in dep and '/Editor' not in dep for deps in result['dependencies'].values() for dep in deps)
result['maps']=[]
for mapname in ['Stage2','SoundTest_Stage2']:
 assert lv.load_level('/Game/Maps/'+mapname);actors=unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors();d=next(a for a in actors if isinstance(a,unreal.CatrunStatuePuzzle));row={'map':mapname,'links':[],'presentation':[],'pedestals':[]}
 for l in d.get_editor_property('Links'):
  key=str(l.get_editor_property('PuzzleId'));half=l.get_editor_property('ContactHalfExtent');axis=l.get_editor_property('SocketAxis');assert half.x==60 and half.y==60;assert (axis.x,axis.y)==((1,0) if key=='B' else (0,1));row['links'].append({'id':key,'statue':l.get_editor_property('Statue').get_path_name(),'gate':l.get_editor_property('Gate').get_path_name(),'contact':str(half),'axis':str(axis),'floor_offset':l.get_editor_property('GateFloorOffset')})
 for a in actors:
  if a.get_class()==bp.generated_class():
   assert a.get_editor_property('Director')==d;row['presentation'].append({'actor':a.get_path_name(),'id':str(a.get_editor_property('PuzzleId')),'anchor':str(a.get_actor_location()),'camera_offset':str(a.get_editor_property('CameraOffset')),'width':a.get_editor_property('RevealOrthoWidth')})
  if isinstance(a,unreal.CatrunPuzzleReset):
   assert a.get_editor_property('Puzzle')==d;row['pedestals'].append(a.get_path_name())
 assert len(row['presentation'])==3;result['maps'].append(row)
assert lv.load_level('/Game/Maps/MainMenu');result['final_world']=edworld.get_editor_world().get_path_name();result['dirty_after']=[p.get_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()]+[p.get_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()]
(OUT/'saved-verification.json').write_text(json.dumps(result,indent=2),encoding='utf8');print('TASK4D_SAVED_VERIFIED',json.dumps(result,indent=2))
