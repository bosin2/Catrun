import unreal as u,json,sys
from pathlib import Path
ROOT=Path(u.Paths.project_dir()).resolve();OUT=ROOT/'Saved/Stage3Integration20261125'
EA=u.EditorAssetLibrary;LEVEL=u.get_editor_subsystem(u.LevelEditorSubsystem);ACT=u.get_editor_subsystem(u.EditorActorSubsystem)
task=u.AssetImportTask();task.filename=str(OUT/'T_Floorplan_Stage3.png');task.destination_path='/Game/UI/Minimap';task.destination_name='T_Floorplan_Stage3';task.automated=True;task.save=True;task.replace_existing=True
u.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
tex=EA.load_asset('/Game/UI/Minimap/T_Floorplan_Stage3');assert tex
tex.set_editor_property('compression_settings',u.TextureCompressionSettings.TC_EDITOR_ICON);tex.set_editor_property('mip_gen_settings',u.TextureMipGenSettings.TMGS_NO_MIPMAPS);EA.save_loaded_asset(tex)
assert LEVEL.load_level('/Game/Maps/Stage3')
actors=list(ACT.get_all_level_actors())
sys.path.insert(0,str(ROOT/'Scripts/Stage3'))
from build_map import device_readability,DEST
for housing in [a for a in actors if a.get_actor_label() in ('S3_Release1_Housing','S3_Release2_Housing','S3_Release3_Housing')]:
    c=housing.get_component_by_class(u.StaticMeshComponent)
    for i in range(c.get_num_materials()):
        material=c.get_material(i)
        name='MI_'+housing.get_actor_label()+'_'+str(i)+'_Readability'
        path=DEST+'/Materials/'+name
        parent=device_readability(material)
        if material.get_name()==name:instance=material
        else:
            instance=EA.load_asset(path) if EA.does_asset_exist(path) else u.AssetToolsHelpers.get_asset_tools().create_asset(name,DEST+'/Materials',u.MaterialInstanceConstant,u.MaterialInstanceConstantFactoryNew())
        u.MaterialEditingLibrary.set_material_instance_parent(instance,parent)
        u.MaterialEditingLibrary.update_material_instance(instance);EA.save_loaded_asset(instance);c.set_material(i,instance)
skies=[a for a in actors if a.get_actor_label()=='S3_AmbientSkyLight']
sky=skies[0] if skies else ACT.spawn_actor_from_class(u.SkyLight,u.Vector(0,2000,1200))
sky.set_actor_label('S3_AmbientSkyLight');sky.set_folder_path('Stage3/Lighting');sky.tags=[u.Name('CatrunStage3_20261125')]
sc=sky.get_component_by_class(u.SkyLightComponent);sc.set_mobility(u.ComponentMobility.MOVABLE)
sc.set_editor_property('source_type',u.SkyLightSourceType.SLS_SPECIFIED_CUBEMAP)
sc.set_editor_property('cubemap',u.load_object(None,'/Engine/MapTemplates/Sky/DaylightAmbientCubemap.DaylightAmbientCubemap'))
sc.set_editor_property('lower_hemisphere_is_black',False);sc.set_intensity(2.);sc.set_cast_shadows(False);sc.recapture_sky()
for light in [a for a in actors if isinstance(a,u.DirectionalLight)]:
    if light.get_actor_label()=='S3_FillLight':
        light.set_actor_rotation(u.Rotator(pitch=-45,yaw=90),True)
        light.get_component_by_class(u.DirectionalLightComponent).set_intensity(1.7)
    elif light.get_actor_label()=='S3_KeyLight':light.get_component_by_class(u.DirectionalLightComponent).set_intensity(1.4)
for armor in [a for a in actors if isinstance(a,u.CatrunArmor) and a.get_actor_label() in ('S3_Armor_GateLeft','S3_Armor_GateRight')]:
    p=armor.get_actor_location();p.y=3900;p.z=100;armor.set_actor_location(p,False,True)
    for point in armor.get_editor_property('PatrolPoints'):
        p=point.get_actor_location();p.y=3900;point.set_actor_location(p,False,True)
for candle in [a for a in actors if isinstance(a,u.CatrunCandle)]:
    candle.get_editor_property('BlockingCapsule').set_relative_location(u.Vector(0,0,62.25),False,False)
    fixed={'S3_Candle_WarehouseNorth':(380,1310,0),'S3_Candle_WarehouseSouth':(1135,855,0)}
    if candle.get_actor_label() in fixed:candle.set_actor_location(u.Vector(*fixed[candle.get_actor_label()]),False,True)
    if candle.get_actor_label()=='S3_Candle_Exhibition':
        p=candle.get_actor_location();p.x=-700;candle.set_actor_location(p,False,True)
        for point in candle.get_editor_property('PatrolPoints'):
            p=point.get_actor_location();p.x=-700;point.set_actor_location(p,False,True)
cat_class=EA.load_blueprint_class('/Game/Characters/BlackCat/Blueprints/BP_Cat')
cats=[a for a in actors if isinstance(a,u.Character) and a.get_class()==cat_class]
assert len(cats)<=1
cat=cats[0] if cats else ACT.spawn_actor_from_class(cat_class,u.Vector(150,110,26.2),u.Rotator(yaw=90))
cat.set_actor_label('S3_Player');cat.set_folder_path('Stage3/Gameplay')
cat.set_actor_location(u.Vector(150,110,26.2),False,True)
cat.tags=list(set(list(cat.tags)+[u.Name('CatrunStage3_20261125')]))
cat.set_editor_property('auto_possess_player',u.AutoReceiveInput.PLAYER0)
maps=[a for a in actors if isinstance(a,u.CatrunMinimapPresenter)]
assert len(maps)<=1
a=maps[0] if maps else ACT.spawn_actor_from_class(u.CatrunMinimapPresenter,u.Vector())
a.set_actor_label('S3_Minimap');a.set_folder_path('Stage3/Gameplay')
a.set_editor_property('WidgetClass',EA.load_blueprint_class('/Game/UI/Minimap/WBP_Minimap_Floorplan'))
a.set_editor_property('BackgroundTexture',tex);a.set_editor_property('MapCenter',u.Vector2D(100,2125));a.set_editor_property('MapSize',u.Vector2D(4250,2200));a.set_editor_property('CaptureYawDegrees',0.)
assert LEVEL.save_current_level();print('STAGE3_FINALIZE_OK')
w=u.get_editor_subsystem(u.UnrealEditorSubsystem).get_editor_world()
gm=w.get_world_settings().get_editor_property('default_game_mode')
(OUT/'startup_probe.json').write_text(json.dumps({'game_mode':gm.get_path_name(),'default_pawn_class':str(u.get_default_object(gm).get_editor_property('default_pawn_class'))},indent=2),encoding='utf8')
