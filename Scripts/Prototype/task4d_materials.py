import sys,unreal
sys.path.insert(0,unreal.Paths.project_dir()+'Scripts/Prototype')
from task4d_assets import *
M=unreal.MaterialEditingLibrary
def expr(m,cls,**p):
 e=M.create_material_expression(m,cls,0,0)
 for k,v in p.items():e.set_editor_property(k,v)
 return e
def wire(a,ap,b,bp):assert M.connect_material_expressions(a,ap,b,bp)
def custom(m,code,inputs,typ):
 rows=[]
 for n in inputs:
  x=unreal.CustomInput();x.set_editor_property('input_name',n);rows.append(x)
 e=expr(m,unreal.MaterialExpressionCustom,code=code,output_type=typ,inputs=rows);return e
if not AS.does_asset_exist(BARS) or not M.get_material_property_input_node(AS.load_asset(BARS),unreal.MaterialProperty.MP_EMISSIVE_COLOR):
 m=new(BARS,unreal.Material,unreal.MaterialFactoryNew());m.set_editor_property('material_domain',unreal.MaterialDomain.MD_POST_PROCESS);m.set_editor_property('blendable_location',unreal.BlendableLocation.BL_SCENE_COLOR_AFTER_TONEMAPPING)
 M.delete_all_material_expressions(m)
 uv=expr(m,unreal.MaterialExpressionScreenPosition);time=expr(m,unreal.MaterialExpressionTime)
 rumble=expr(m,unreal.MaterialExpressionScalarParameter,parameter_name='Rumble',default_value=0.)
 shifted=custom(m,'return UV + float2(sin(T*57.0),cos(T*71.0))*R;', ['UV','T','R'],unreal.CustomMaterialOutputType.CMOT_FLOAT2)
 wire(uv,'ViewportUV',shifted,'UV');wire(time,'',shifted,'T');wire(rumble,'',shifted,'R')
 scene=expr(m,unreal.MaterialExpressionSceneTexture,scene_texture_id=unreal.SceneTextureId.PPI_POST_PROCESS_INPUT0);wire(shifted,'',scene,'UVs')
 bar=expr(m,unreal.MaterialExpressionScalarParameter,parameter_name='BarHeight',default_value=.075)
 mask=custom(m,'return Scene.rgb * step(H,UV.y) * step(UV.y,1.0-H);',['Scene','UV','H'],unreal.CustomMaterialOutputType.CMOT_FLOAT3)
 wire(scene,'Color',mask,'Scene');wire(uv,'ViewportUV',mask,'UV');wire(bar,'',mask,'H');assert M.connect_material_property(mask,'',unreal.MaterialProperty.MP_EMISSIVE_COLOR)
 M.layout_material_expressions(m);M.recompile_material(m);assert AS.save_loaded_asset(m,False)
if not AS.does_asset_exist(DUST):
 m=new(DUST,unreal.Material,unreal.MaterialFactoryNew());m.set_editor_property('blend_mode',unreal.BlendMode.BLEND_TRANSLUCENT);m.set_editor_property('shading_model',unreal.MaterialShadingModel.MSM_UNLIT);m.set_editor_property('two_sided',True)
 uv=expr(m,unreal.MaterialExpressionTextureCoordinate);time=expr(m,unreal.MaterialExpressionTime);start=expr(m,unreal.MaterialExpressionScalarParameter,parameter_name='StartTime',default_value=0.);pos=expr(m,unreal.MaterialExpressionObjectPositionWS)
 opacity=custom(m,'float seed=frac(P.x*0.017+P.y*0.029); float life=frac((T-S)*0.95+seed); float2 p=(UV-0.5)*2.; float n=0.84+0.16*sin(p.x*9.0+life*6.0)*sin(p.y*7.0-life*5.0); return pow(saturate(1.-dot(p,p)),2.)*sin(life*3.14159)*0.22*n;',['UV','T','S','P'],unreal.CustomMaterialOutputType.CMOT_FLOAT1)
 for a,ap,p in [(uv,'','UV'),(time,'','T'),(start,'','S'),(pos,'','P')]:wire(a,ap,opacity,p)
 rise=custom(m,'float seed=frac(P.x*0.017+P.y*0.029); float life=frac((T-S)*0.95+seed); return float3(sin(seed*19.+life*3.)*7.,cos(seed*13.+life*3.)*5.,life*42.);',['T','S','P'],unreal.CustomMaterialOutputType.CMOT_FLOAT3)
 for a,p in [(time,'T'),(start,'S'),(pos,'P')]:wire(a,'',rise,p)
 color=expr(m,unreal.MaterialExpressionConstant3Vector,constant=unreal.LinearColor(.72,.66,.56,1))
 assert M.connect_material_property(color,'',unreal.MaterialProperty.MP_EMISSIVE_COLOR);assert M.connect_material_property(opacity,'',unreal.MaterialProperty.MP_OPACITY);assert M.connect_material_property(rise,'',unreal.MaterialProperty.MP_WORLD_POSITION_OFFSET)
 M.layout_material_expressions(m);M.recompile_material(m);assert AS.save_loaded_asset(m,False)
bp=AS.load_asset(PRES)
sds=unreal.get_engine_subsystem(unreal.SubobjectDataSubsystem)
components=[unreal.SubobjectDataBlueprintFunctionLibrary.get_associated_object(unreal.SubobjectDataBlueprintFunctionLibrary.get_data(h)) for h in sds.k2_gather_subobject_data_for_blueprint(bp)]
if not any(isinstance(c,unreal.StaticMeshComponent) and c.get_name().startswith('Dust00') for c in components):
 for i in range(8):
  c=ActorTools.add_component(bp,unreal.StaticMeshComponent.static_class(),'Dust%02d'%i)
  c.set_static_mesh(AS.load_asset('/Engine/BasicShapes/Plane'));c.set_material(0,AS.load_asset(DUST));c.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION);c.set_editor_property('cast_shadow',False);c.set_editor_property('hidden_in_game',True);c.set_editor_property('generate_overlap_events',False)
  c.set_editor_property('relative_location',unreal.Vector(-62+i*18,(-1 if i%2 else 1)*7,14));c.set_editor_property('relative_rotation',unreal.Rotator(pitch=65,yaw=25,roll=0));c.set_editor_property('relative_scale3d',unreal.Vector(.23,.28,.23))
strict(bp)
print('TASK4D_MATERIALS_SAVED')
