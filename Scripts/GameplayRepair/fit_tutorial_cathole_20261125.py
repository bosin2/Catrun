"""Extend the cat-hole wall bay in Tutorial/MainMenu; match Stage1 scale 1.

Run on one loaded map via ue_remote.py --isolated. The 60x65 aperture and
84x89 surround stay full size. Short return walls reconnect the extended bay
to the original layout before either human door. Original assets are retained.
"""
import json
import importlib.util
import shutil
from pathlib import Path
import unreal as u

ROOT = Path(u.Paths.project_dir()).resolve()
OUT = ROOT / 'Saved/CatHoleFit20261125'
AS = u.EditorAssetLibrary
ACT = u.get_editor_subsystem(u.EditorActorSubsystem)
ED = u.get_editor_subsystem(u.UnrealEditorSubsystem)
LEVEL = u.get_editor_subsystem(u.LevelEditorSubsystem)
BASE = '/Game/Environment/Tutorial/Passages/CatHoleWallExtension20261125/'
TRIM = '/Game/Environment/Shared/Castle/Architecture/CatHoleTrim/Meshes/SM_CatHoleTrim_Stage1'
WALL = '/Game/Environment/Shared/Castle/Architecture/Meshes/SM_StoneWall_L100_H300_T030'
FLOOR = '/Game/Environment/Shared/Castle/Architecture/Meshes/SM_Floor_Stone_A'
OWN = 'CatrunCatHoleWallExtension20261125'


def snapshot(a):
    c = a.get_component_by_class(u.StaticMeshComponent)
    return {'transform': a.get_actor_transform().export_text(), 'tags': list(map(str,a.tags)),
            'mesh': c.static_mesh.get_path_name() if c and c.static_mesh else None,
            'collision': str(c.get_collision_enabled()) if c else None,
            'materials': [m.get_path_name() if m else None for m in c.get_materials()] if c else []}


def shorten_corridor_wall(actor, name):
    c = actor.get_component_by_class(u.StaticMeshComponent)
    target = BASE + f'SM_{name}_CorridorWallAfterExtension'
    source = c.static_mesh
    if source.get_path_name().split('.')[0] == target: return
    assert not AS.does_asset_exist(target), target
    mesh = AS.duplicate_asset(source.get_path_name().split('.')[0], target)
    dyn, result = u.GeometryScript_AssetUtils.copy_mesh_from_static_mesh(
        source, u.new_object(u.DynamicMesh), u.GeometryScriptCopyMeshFromAssetOptions(), u.GeometryScriptMeshReadLOD())
    assert result == u.GeometryScriptOutcomePins.SUCCESS
    cutter = u.GeometryScript_Primitives.append_box(
        u.new_object(u.DynamicMesh), u.GeometryScriptPrimitiveOptions(),
        u.Transform(location=u.Vector(34.5,-15,150)), 71,100,400,
        origin=u.GeometryScriptPrimitiveOriginMode.CENTER)
    u.GeometryScript_MeshBooleans.apply_mesh_boolean(
        dyn,u.Transform(),cutter,u.Transform(),u.GeometryScriptBooleanOperation.SUBTRACT,
        u.GeometryScriptMeshBooleanOptions(fill_holes=True))
    _, result = u.GeometryScript_AssetUtils.copy_mesh_to_static_mesh(
        dyn,mesh,u.GeometryScriptCopyMeshToAssetOptions(enable_recompute_normals=False,enable_recompute_tangents=True),
        u.GeometryScriptMeshWriteLOD())
    assert result == u.GeometryScriptOutcomePins.SUCCESS
    # Exact static-wall collision preserves the existing door cutout and removes
    # collision from the extended bay, without retaining a stale convex hull.
    mesh.get_editor_property('body_setup').set_editor_property(
        'collision_trace_flag',u.CollisionTraceFlag.CTF_USE_COMPLEX_AS_SIMPLE)
    assert AS.save_loaded_asset(mesh,False)
    c.set_static_mesh(mesh)


def main():
    assert not ED.get_game_world()
    name = ED.get_editor_world().get_name()
    assert name in ('Tutorial','MainMenu')
    OUT.mkdir(parents=True,exist_ok=True)
    backup = OUT/'Before'; backup.mkdir(exist_ok=True)
    src = ROOT/f'Content/Maps/{name}.umap'
    if not (backup/src.name).exists(): shutil.copy2(src,backup/src.name)
    actors = {a.get_actor_label():a for a in ACT.get_all_level_actors()}
    before = {n:snapshot(a) for n,a in actors.items()}
    trims = [a for a in actors.values() if snapshot(a)['mesh']==TRIM+'.SM_CatHoleTrim_Stage1']
    assert len(trims)==2
    labels = {'SM_Tutorial_Wall_South_06','SM_Tutorial_Wall_CorridorSouth_01','SM_Tutorial_Floor_Bedroom_05'}
    labels.update(a.get_actor_label() for a in trims)
    threshold = 'SM_Tutorial_Annex_Threshold_CatHole' if name=='Tutorial' else 'SM_MainMenu_Threshold_CatHole'
    labels.add(threshold)
    assert all('/CatHoleFit20261125/' not in (r['mesh'] or '') for r in before.values()), 'Revert rejected corner-seat pass first'
    actors['SM_Tutorial_Wall_South_06'].set_actor_location(u.Vector(-350,380,0),False,False)
    shorten_corridor_wall(actors['SM_Tutorial_Wall_CorridorSouth_01'],name)
    for label,location,scale in [
            ('SM_Tutorial_Floor_Bedroom_05',(-320,450,-5.154676437),(.975,.9,1)),
            (threshold,(-320,480,-5.154676437),(.4,.15,1))]:
        a=actors[label]; a.set_actor_location(u.Vector(*location),False,False); a.set_actor_scale3d(u.Vector(*scale))
    specs = [
        ('BedroomWallExtension',WALL,(-320,480,0),0,(.2,1,1)),
        ('BedroomReturn',WALL,(-350,410,0),0,(.5,1,1)),
        ('CorridorWallExtension',WALL,(-220,480,0),90,(.7,1,1)),
        ('CorridorReturn',WALL,(-250,580,0),0,(.6,1,1)),
        ('CorridorFloorExtension',FLOOR,(-250,550,-5.154676437),0,(.15,.35,1))]
    for suffix,asset,location,yaw,scale in specs:
        label='SM_CatHole_'+suffix
        a=actors.get(label)
        if a is None:
            a=ACT.spawn_actor_from_class(u.StaticMeshActor,u.Vector(*location))
            a.set_actor_label(label); a.tags=[OWN]
        assert OWN in map(str,a.tags)
        a.set_actor_location(u.Vector(*location),False,False)
        a.set_actor_rotation(u.Rotator(pitch=0,yaw=yaw,roll=0),False)
        a.set_actor_scale3d(u.Vector(*scale))
        a.get_component_by_class(u.StaticMeshComponent).set_static_mesh(u.load_asset(asset))
        labels.add(label)
    for a in trims:
        bedroom=a.get_actor_location().y<465
        a.set_actor_location(u.Vector(-270,449.8 if bedroom else 480.2,0),False,False)
        a.set_actor_rotation(u.Rotator(pitch=0,yaw=180 if bedroom else 0,roll=0),False)
        a.set_actor_scale3d(u.Vector(1,1,1))
        assert a.get_component_by_class(u.StaticMeshComponent).get_collision_enabled()==u.CollisionEnabled.NO_COLLISION
    # Newly spawned architecture must inherit the existing camera silhouette
    # behavior, including plane coordinates for the moved wall and new returns.
    module_spec = importlib.util.spec_from_file_location('cat_hole_occlusion',
        ROOT/'Scripts/GameplayRepair/repair_tutorial_cathole_occlusion_20261125.py')
    occlusion = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(occlusion)
    occlusion.apply(save=False)
    labels.update(occlusion.RECIPES)
    after={a.get_actor_label():snapshot(a) for a in ACT.get_all_level_actors()}
    assert {k:v for k,v in before.items() if k not in labels}=={k:v for k,v in after.items() if k not in labels}
    sweeps=[]
    for x in (-275,-270,-265):
        for y0,y1 in ((420,520),(520,420)):
            hit=u.SystemLibrary.capsule_trace_single_by_profile(
                ED.get_editor_world(),u.Vector(x,y0,26.25),u.Vector(x,y1,26.25),
                20,24,'Pawn',False,[],u.DrawDebugTrace.NONE)
            assert hit is None,(x,y0,str(hit))
            sweeps.append({'x':x,'from_y':y0,'to_y':y1,'clear':True})
    ground=[]
    for x,y in [(-310,430),(-310,465),(-235,510),(-270,465),(-270,520)]:
        hit=u.SystemLibrary.line_trace_single_by_profile(
            ED.get_editor_world(),u.Vector(x,y,20),u.Vector(x,y,-20),'Pawn',False,[],u.DrawDebugTrace.NONE)
        assert hit,(x,y,'floor gap')
        assert abs(hit.to_dict()['impact_point'].z)<.1
        ground.append([x,y])
    assert LEVEL.save_current_level()
    report={'map':name,'stage1_aperture_cm':[60,65],'stage1_trim_cm':[84,4,89],
            'trim_scale':[1,1,1],'bedroom_wall_extension_cm':20,'corridor_wall_extension_cm':30,
            'before':{k:v for k,v in before.items() if k in labels},'after':{k:after[k] for k in labels},
            'unrelated_actors_preserved':True,'editor_capsule_sweeps':sweeps,'floor_support_checks':ground}
    (OUT/f'{name}-wall-extension.json').write_text(json.dumps(report,indent=2),encoding='utf8')
    print('CAT_HOLE_WALL_EXTENSION',name,'saved; Stage1 scale 1; 6 sweeps + 5 floor checks passed')


main()
