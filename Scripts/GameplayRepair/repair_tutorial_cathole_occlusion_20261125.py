"""Give the extended cat-hole walls the existing Tutorial silhouette behavior.

Each copied instance retains its original surface parameters and uses an explicit
WallPlane matching the extended geometry. A local parent adds a smooth approach
fade around this aperture; away from it the original silhouette behavior applies.
No shared material/function, collision, actor transform, or Blueprint is edited.
"""
import json
import shutil
from pathlib import Path
import unreal as u

ROOT = Path(u.Paths.project_dir()).resolve()
OUT = ROOT / 'Saved/CatHoleOcclusion20261125'
SOURCE = '/Game/Environment/Tutorial/Materials/WallSilhouette/MI_Tutorial_'
DEST = '/Game/Environment/Tutorial/Passages/CatHoleWallExtension20261125/Materials/'
RECIPES = {
    'SM_Tutorial_Wall_EastBottom_01': ('BedroomEast', (0,465,-320,400)),
    'SM_Tutorial_Arch_Bedroom': ('BedroomEast', (0,465,-320,400)),
    'SM_Tutorial_Wall_South_06': ('BedroomSouth', (1,-335,380,480)),
    'SM_CatHole_BedroomWallExtension': ('BedroomEast', (0,465,-320,400)),
    'SM_CatHole_BedroomReturn': ('BedroomSouth', (0,395,-350,-300)),
    'SM_CatHole_CorridorWallExtension': ('CorridorSouth', (1,-205,480,550)),
    'SM_CatHole_CorridorReturn': ('CorridorSouth', (0,565,-250,-190)),
}


def parent_material():
    source = u.load_asset('/Game/Systems/Camera/Occlusion/Materials/M_WallSilhouette')
    path = DEST+'M_CatHoleApproachSilhouette'
    if u.EditorAssetLibrary.does_asset_exist(path):
        return u.load_asset(path)
    master = u.EditorAssetLibrary.duplicate_asset(source.get_path_name(),path)
    ml = u.MaterialEditingLibrary
    original_opacity = ml.get_material_property_input_node(master,u.MaterialProperty.MP_OPACITY)
    cat = ml.create_material_expression(master,u.MaterialExpressionCollectionParameter,-450,1400)
    cat.set_editor_property('collection',u.load_asset('/Game/Characters/BlackCat/Materials/MPC_CatOcclusion'))
    cat.set_editor_property('parameter_name','CatPosition')
    fade = ml.create_material_expression(master,u.MaterialExpressionCustom,0,1400)
    fade.set_editor_property('output_type',u.CustomMaterialOutputType.CMOT_FLOAT1)
    fade.set_editor_property('code',
        'float nearHole = 1.0 - smoothstep(85.0,140.0,length(Cat.xy-float2(-270.0,465.0)));\n'
        'nearHole *= step(0.5,Cat.a)*step(-20.0,Cat.z)*step(Cat.z,130.0);\n'
        'return min(Existing,lerp(1.0,0.04,nearHole));')
    inputs=[]
    for name in ('Existing','Cat'):
        i=u.CustomInput();i.set_editor_property('input_name',name);inputs.append(i)
    fade.set_editor_property('inputs',inputs)
    assert ml.connect_material_expressions(original_opacity,'',fade,'Existing')
    assert ml.connect_material_expressions(cat,'',fade,'Cat')
    assert ml.connect_material_property(fade,'',u.MaterialProperty.MP_OPACITY)
    for field in ('BASE_COLOR','NORMAL','ROUGHNESS','METALLIC','AMBIENT_OCCLUSION','EMISSIVE_COLOR'):
        prop=getattr(u.MaterialProperty,'MP_'+field)
        a=ml.get_material_property_input_node(source,prop); b=ml.get_material_property_input_node(master,prop)
        assert (a.get_name() if a else None)==(b.get_name() if b else None),field
    ml.recompile_material(master)
    assert u.EditorAssetLibrary.save_loaded_asset(master,False)
    return master


def state(a):
    c = a.get_component_by_class(u.StaticMeshComponent)
    return {'transform':a.get_actor_transform().export_text(), 'tags':list(map(str,a.tags)),
            'mesh':c.static_mesh.get_path_name() if c and c.static_mesh else None,
            'collision':str(c.get_collision_enabled()) if c else None,
            'profile':str(c.get_collision_profile_name()) if c else None,
            'materials':[m.get_path_name() if m else None for m in c.get_materials()] if c else []}


def apply(save=True):
    ed = u.get_editor_subsystem(u.UnrealEditorSubsystem)
    assert not ed.get_game_world(), 'Editor asset changes require PIE stopped'
    name = ed.get_editor_world().get_name()
    assert name in ('Tutorial','MainMenu')
    actors = {a.get_actor_label():a for a in u.get_editor_subsystem(u.EditorActorSubsystem).get_all_level_actors()}
    assert set(RECIPES) <= set(actors)
    before = {label:state(a) for label,a in actors.items()}
    OUT.mkdir(parents=True,exist_ok=True)
    backup = OUT/'Before'; backup.mkdir(exist_ok=True)
    src = ROOT/f'Content/Maps/{name}.umap'
    if not (backup/src.name).exists(): shutil.copy2(src,backup/src.name)
    variants = {}
    parent = parent_material()
    for label,(source,plane) in RECIPES.items():
        original = u.load_asset(SOURCE+source)
        path = DEST+'MI_'+label.removeprefix('SM_')+'_Silhouette'
        mi = u.load_asset(path) if u.EditorAssetLibrary.does_asset_exist(path) else None
        if mi is None:
            mi = u.EditorAssetLibrary.duplicate_asset(SOURCE+source,path)
            assert mi
            u.EditorAssetLibrary.set_metadata_tag(mi,'CatHoleOcclusionSource',original.get_path_name())
        assert u.EditorAssetLibrary.get_metadata_tag(mi,'CatHoleOcclusionSource') == original.get_path_name()
        u.MaterialEditingLibrary.set_material_instance_parent(mi,parent)
        u.MaterialEditingLibrary.set_material_instance_scalar_parameter_value(mi,'UseObjectBounds',0.)
        u.MaterialEditingLibrary.set_material_instance_vector_parameter_value(mi,'WallPlane',u.LinearColor(*plane))
        u.MaterialEditingLibrary.update_material_instance(mi)
        assert u.EditorAssetLibrary.save_loaded_asset(mi,False)
        c = actors[label].get_component_by_class(u.StaticMeshComponent)
        for slot in range(c.get_num_materials()): c.set_material(slot,mi)
        variants[label] = {'material':path,'WallPlane':plane,'source':original.get_path_name()}
    after = {label:state(a) for label,a in actors.items()}
    for label in before:
        expected = dict(before[label])
        if label in RECIPES: expected['materials'] = after[label]['materials']
        assert expected == after[label], ('Unexpected non-material change',label)
    if save: assert u.get_editor_subsystem(u.LevelEditorSubsystem).save_current_level()
    report = {'map':name,'assignments':variants,'geometry_collision_blueprints_preserved':True,
              'approach_fade':{'center_xy':[-270,465],'full_fade_radius_cm':85,'restore_radius_cm':140,'near_opacity':.04},
              'before':{k:before[k] for k in RECIPES},'after':{k:after[k] for k in RECIPES}}
    (OUT/f'{name}-repair.json').write_text(json.dumps(report,indent=2),encoding='utf8')
    print('CAT_HOLE_OCCLUSION_APPLIED',name,len(variants),'walls')
    return report


if __name__ in ('__main__','__catrun_remote_script__'):
    apply()
