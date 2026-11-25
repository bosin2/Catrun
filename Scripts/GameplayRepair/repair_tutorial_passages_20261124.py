"""Apply/audit measured visual trim on the currently loaded tutorial only.

The native door hinge repair is separate. Existing actors, sound tags, passage
collision and all original transforms remain unchanged by this authoring pass.
Set CATRUN_PASSAGES_MODE to 'apply'; default 'audit'. Load/save maps serially.
"""
import hashlib
import json
import shutil
from pathlib import Path
import unreal as u

ROOT = Path(u.Paths.project_dir()).resolve()
OUT = ROOT / 'Saved/GameplayExpansion20261124/Passages'
MODE = globals().get('CATRUN_PASSAGES_MODE', 'audit')
AS = u.EditorAssetLibrary
ED = u.get_editor_subsystem(u.UnrealEditorSubsystem)
ACT = u.get_editor_subsystem(u.EditorActorSubsystem)
LEVEL = u.get_editor_subsystem(u.LevelEditorSubsystem)
LINING = '/Game/Environment/Tutorial/Passages/Meshes/SM_Tutorial_BedroomDoorLining'
TRIM = '/Game/Environment/Shared/Castle/Architecture/CatHoleTrim/Meshes/SM_CatHoleTrim_Stage1'
OWN = 'CatrunTutorialPassages20261124'

def vec(v): return [round(float(v.x), 4), round(float(v.y), 4), round(float(v.z), 4)]
def transform(a): return a.get_actor_transform().export_text()
def package(a): return a.get_path_name().split('.')[0]

def main():
    assert not ED.get_game_world(), 'PIE must be stopped'
    world = ED.get_editor_world()
    name = package(world).rsplit('/', 1)[-1]
    assert name in ('Tutorial', 'SoundTest_Tutorial', 'MainMenu'), name
    OUT.mkdir(parents=True, exist_ok=True)
    actors = {a.get_actor_label(): a for a in ACT.get_all_level_actors()}
    adopted = actors.get('SM_CatHoleTrim_Stage1') if name == 'MainMenu' else None
    before = {a.get_path_name(): transform(a) for a in actors.values() if OWN not in map(str, a.tags) and a != adopted}
    wall = actors['SM_Tutorial_Arch_Bedroom'].get_component_by_class(u.StaticMeshComponent)
    if name != 'MainMenu':
        door, corridor = actors['Door_Tutorial_Bedroom'], actors['Door_Tutorial_Corridor']
        assert not door.get_editor_property('bStartOpen') and corridor.get_editor_property('bStartOpen')
        assert corridor.get_component_by_class(u.StaticMeshComponent).static_mesh is None
    if MODE == 'apply':
        source = ROOT / f'Content/Maps/{name}.umap'
        backup = OUT / 'Before' / source.relative_to(ROOT)
        if not backup.exists():
            backup.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(source, backup)
        fbx = ROOT / 'SourceArt/Tutorial/Passages/SM_Tutorial_BedroomDoorLining.fbx'
        source_hash = hashlib.sha256(fbx.read_bytes()).hexdigest()
        existing = u.load_asset(LINING) if AS.does_asset_exist(LINING) else None
        if not existing or AS.get_metadata_tag(existing, 'CatrunPassageSourceSHA256') != source_hash:
            task = u.AssetImportTask()
            task.filename = str(fbx)
            task.destination_path, task.destination_name = LINING.rsplit('/', 1)
            task.automated, task.replace_existing, task.save = True, bool(existing), False
            options = u.FbxImportUI()
            options.import_mesh = True; options.import_materials = False; options.import_textures = False
            options.import_animations = False; options.import_as_skeletal = False
            options.mesh_type_to_import = u.FBXImportType.FBXIT_STATIC_MESH
            options.static_mesh_import_data.combine_meshes = True
            options.static_mesh_import_data.auto_generate_collision = False
            task.options = options
            u.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
            mesh = u.load_asset(LINING)
            assert mesh, task.imported_object_paths
            mesh.set_material(0, wall.get_material(0))
            AS.set_metadata_tag(mesh, 'CatrunPassageSourceSHA256', source_hash)
            assert AS.save_loaded_asset(mesh, False)
    mesh = u.load_asset(LINING)
    assert mesh and u.load_asset(TRIM)
    box = mesh.get_bounding_box()
    assert all(abs(a-b) < .2 for a,b in zip(vec(box.max-box.min), [168,28,226])), str(box)
    spec = [('SM_Tutorial_BedroomDoorLining', LINING, (-130,465,0), 0),
            ('SM_Tutorial_CatHoleTrim_Bedroom', TRIM, (-270,449.8,0), 180),
            ('SM_Tutorial_CatHoleTrim_Corridor', TRIM, (-270,480.2,0), 0)]
    if name == 'MainMenu':
        # Menu has a separately authored static bedroom door; only its matching
        # cat-hole trim is in scope. Adopt its existing actor rather than duplicate.
        spec = [('SM_CatHoleTrim_Stage1', TRIM, (-270,449.8,0), 180),
                ('SM_MainMenu_CatHoleTrim_Outside', TRIM, (-270,480.2,0), 0)]
    if name == 'SoundTest_Tutorial':
        spec = [(label, asset, (-270,450 if yaw == 180 else 480,0) if asset == TRIM else loc, yaw)
                for label, asset, loc, yaw in spec]
    rows = []
    for label, asset, location, yaw in spec:
        a = actors.get(label)
        if MODE == 'apply':
            if a and a == adopted and OWN not in map(str,a.tags):
                assert package(a.get_component_by_class(u.StaticMeshComponent).static_mesh) == TRIM
                assert vec(a.get_actor_location()) == [-270,450,0]
                a.tags = list(a.tags) + [OWN]
            if a is None:
                a = ACT.spawn_actor_from_class(u.StaticMeshActor, u.Vector(*location), u.Rotator(pitch=0,yaw=yaw,roll=0))
                a.set_actor_label(label); a.tags = [OWN]
            assert OWN in map(str,a.tags), 'Do not replace an unowned actor'
            a.set_actor_location(u.Vector(*location), False, False)
            a.set_actor_rotation(u.Rotator(pitch=0,yaw=yaw,roll=0), False)
            a.set_actor_scale3d(u.Vector(1,1,1))
            c = a.get_component_by_class(u.StaticMeshComponent)
            c.set_static_mesh(u.load_asset(asset))
            c.set_editor_property('can_ever_affect_navigation', False)
            c.set_editor_property('generate_overlap_events', False)
            c.set_collision_profile_name('NoCollision')
            c.set_collision_enabled(u.CollisionEnabled.NO_COLLISION)
        assert a, label
        c = a.get_component_by_class(u.StaticMeshComponent)
        assert package(c.static_mesh) == asset and c.get_collision_enabled() == u.CollisionEnabled.NO_COLLISION, (label, package(c.static_mesh), asset, str(c.get_collision_enabled()))
        assert vec(a.get_actor_location()) == list(location) and vec(a.get_actor_scale3d()) == [1,1,1]
        rotation = a.get_actor_rotation()
        assert abs(rotation.pitch) < .001 and abs(rotation.roll) < .001 and abs(abs(rotation.yaw)-yaw) < .001
        rows.append({'label':label,'mesh':asset,'location':vec(a.get_actor_location()),
                     'yaw':a.get_actor_rotation().yaw,'collision':str(c.get_collision_enabled())})
    after = {a.get_path_name():transform(a) for a in ACT.get_all_level_actors() if OWN not in map(str,a.tags) and a != adopted}
    assert before == after, 'Existing actor transforms changed'
    if MODE == 'apply': assert LEVEL.save_current_level()
    report = {'mode':MODE,'map':name,'actors':rows,'existing_actor_transforms_preserved':True,
              'lining_size_cm':vec(box.max-box.min),'runtime_passage_test':'pending'}
    (OUT/f'{name}-{MODE}.json').write_text(json.dumps(report,indent=2),encoding='utf8')
    print('CAT_AUDIO_REPORT:'+json.dumps(report))

main()
