"""Single writer for the approved Stage3 altar and newly requested additions.

Run only in the isolated root-owned editor. Back up the latest main map, keep
other chats' changes, abort on disk drift, and save Stage3 only after checks.
Gate impact authoring is a later, separate pass, as requested by the user.
"""
import hashlib
import importlib.util
import json
import os
import shutil
import traceback
from pathlib import Path
import unreal as u

ROOT=Path(u.Paths.project_dir()).resolve()
PASS=os.environ.get('CATRUN_STAGE3_CORE_PASS','Core01')
assert PASS.replace('_','').isalnum()
OUT=ROOT/'Saved/Stage3IntegrationRevision20261125'/PASS
OUT.mkdir(parents=True,exist_ok=True)
assert not (OUT/'result.json').exists(),'Use a fresh run identifier'
MAP=ROOT/'Content/Maps/Stage3.umap'
ED=u.get_editor_subsystem(u.UnrealEditorSubsystem)
LE=u.get_editor_subsystem(u.LevelEditorSubsystem)
EA=u.EditorAssetLibrary
ACT=u.get_editor_subsystem(u.EditorActorSubsystem)
R={'success':False,'level_saved':False,'phase':'preflight','approved_altar':'Explicit user approval in this chat',
   'requested_additions':['gate hall length','pillar cap visibility','connected corners','loud device with two-armour response','four baskets','second exhibition candle enemy']}

def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def persist(): (OUT/'result.json').write_text(json.dumps(R,indent=2,ensure_ascii=False),encoding='utf8')
def phase(name): R['phase']=name;persist()
def module(name,relative):
    spec=importlib.util.spec_from_file_location(name,ROOT/relative)
    result=importlib.util.module_from_spec(spec);spec.loader.exec_module(result);return result

try:
    assert '-SaveToUserDir' in u.SystemLibrary.get_command_line()
    assert not ED.get_game_world()
    assert ED.get_editor_world().get_path_name()=='/Game/Maps/Stage3.Stage3'
    u.SystemLibrary.execute_console_command(ED.get_editor_world(),'Editor.AsyncAssetCompilationFinishAll')
    R['map_sha_before']=sha(MAP)
    backup=OUT/'Before';backup.mkdir(exist_ok=True)
    shutil.copy2(MAP,backup/'Stage3.umap')
    # The cutaway refresh owns these existing Stage3-only packages. Preserve
    # their exact incoming bytes in case a later operation fails.
    camera_dir=ROOT/'Content/Environment/Stage3/GothicRevision_20261125/CameraReadability'
    for source in camera_dir.glob('*.uasset'):
        target=backup/'CameraReadability'/source.name;target.parent.mkdir(exist_ok=True)
        shutil.copy2(source,target)
    R['map_backup']=str(backup/'Stage3.umap')
    phase('join_corners')
    R['corners']=module('s3_core_corners','Scripts/Stage3/GateHallRevision20261125/corners.py').apply_corners()
    phase('approved_altar')
    R['altar']=module('s3_core_altar','Scripts/Stage3/IntegrationRevision20261125/altar.py').apply()
    phase('gate_hall')
    R['hall']=module('s3_core_hall','Scripts/Stage3/GateHallRevision20261125/apply.py').apply(
        pillar_top_cm=900,refresh_cutaway=False,rebuild_grid=False)
    phase('baskets_enemy_dressing')
    R['placement']=module('s3_core_placement','Scripts/Stage3/PlacementRevision20261125/apply.py').apply()
    assert R['placement']['success']
    phase('navigation_and_device_sound')
    lookup={a.get_actor_label():a for a in ACT.get_all_level_actors()}
    grid=lookup['S3_SoundGrid']
    tag=grid.get_editor_property('Settings').get_editor_property('ObstacleTag')
    furniture=['S3_Gothic_LobbyBench','S3_Gothic_LobbyCabinet','S3_Gothic_LowerStrategy',
               'S3_Gothic_LowerBench','S3_Gothic_ExhibitionShield','S3_Gothic_WarehouseMaintenance']
    R['navigation_obstacles']=[]
    for label in furniture:
        actor=lookup[label];component=actor.get_component_by_class(u.StaticMeshComponent)
        assert actor.get_actor_enable_collision()
        assert component.get_collision_response_to_channel(u.CollisionChannel.ECC_PAWN)==u.CollisionResponseType.ECR_BLOCK
        before=list(map(str,actor.tags))
        if str(tag) not in before: actor.tags=list(actor.tags)+[tag]
        R['navigation_obstacles'].append({'label':label,'before':before,'after':list(map(str,actor.tags))})
    R['sound']=module('s3_core_sound','Scripts/Stage3/SoundReactionRevision20261125/prepare_settings.py').prepare(1800.)
    grid.build_grid();assert grid.has_grid()
    R['grid_rebuilt']=True
    phase('camera_cutaway')
    R['cutaway']=module('s3_core_cutaway','Scripts/Stage3/GothicRevision/occlusion.py').apply()
    # Final measured map, after every structural edit. Retired/E23 superseded
    # collision-off bodies must not reappear in the floorplan or navigation.
    rows=[]
    for actor in ACT.get_all_level_actors():
        tags=list(map(str,actor.tags))
        if not actor.get_actor_enable_collision() or not any(t in tags for t in ('SoundFloor','SoundWall')): continue
        components=actor.get_components_by_class(u.PrimitiveComponent)
        if not any(c.get_collision_enabled()!=u.CollisionEnabled.NO_COLLISION for c in components): continue
        center,extent=actor.get_actor_bounds(True,False)
        rows.append({'label':actor.get_actor_label(),'tags':tags,
            'min':[center.x-extent.x,center.y-extent.y,center.z-extent.z],
            'max':[center.x+extent.x,center.y+extent.y,center.z+extent.z]})
    R['hall']['measured_structural_bounds']=rows
    (ROOT/'Saved/Stage3GateHallRevision20261125/applied_unsaved.json').write_text(json.dumps(R['hall'],indent=2),encoding='utf8')
    phase('save_stage3')
    assert sha(MAP)==R['map_sha_before'],'Another writer changed Stage3; abort without overwriting their work'
    assert EA.save_loaded_asset(EA.load_asset(R['sound']['prepared_settings']))
    assert LE.save_current_level()
    R['level_saved']=True;R['map_sha_after']=sha(MAP)
    phase('saved_snapshot')
    qa=module('s3_core_qa','Scripts/Stage3/GothicRevision/verify.py')
    qa.OUT=OUT/'QA';qa.snapshot('after')
    R['success']=True;R['phase']='saved_pending_runtime_qa'
except Exception:
    R['error']=traceback.format_exc()
    R['map_sha_on_failure']=sha(MAP)
finally:
    persist();print('STAGE3_CORE_RESULT',json.dumps({k:R.get(k) for k in ('success','phase','level_saved','error')}))
    u.SystemLibrary.execute_console_command(ED.get_editor_world(),'QUIT_EDITOR')
