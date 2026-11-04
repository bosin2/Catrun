"""Apply focused placement/config after a separate supported duplication call.

Keeps the exact first backup/measurement baseline and saves only intended maps.
"""
import unreal,json,shutil,hashlib,datetime,gc
from pathlib import Path
root=Path(unreal.Paths.project_dir()).resolve()
out=root/'Saved/Prototype20261104/CanonicalMaps'
backup=out/'before';backup.mkdir(parents=True,exist_ok=True)
levels=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
editor=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
actors_api=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
assert not editor.get_game_world()
manifest_path=out/'manifest.json'
manifest=json.loads(manifest_path.read_text()) if manifest_path.exists() else {'created':datetime.datetime.now(datetime.timezone.utc).isoformat(),'files':[]}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def backup_file(rel):
    old=next((r for r in manifest['files'] if r['path']==rel),None)
    if old:return old
    src=root/rel;dst=backup/rel;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dst)
    row={'path':rel,'before_sha256':sha(src),'backup':str(dst)};manifest['files'].append(row)
    manifest_path.write_text(json.dumps(manifest,indent=2));return row
for stage in ['Tutorial','Stage1','Stage2']:
    for name in [stage,'SoundTest_'+stage]:backup_file('Content/Maps/'+name+'.umap')
for rel in ['Config/DefaultGame.ini','Scripts/Prototype/repair_tutorial_intro.py']:backup_file(rel)
# Preserve exact unsaved packages if a caller starts from a dirty intended map.
for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages():
    rel='Content/'+p.get_name().removeprefix('/Game/')+'.umap'
    row=next((r for r in manifest['files'] if r['path']==rel),None)
    if row:
        assert unreal.EditorLoadingAndSavingUtils.save_packages([p],False)
        dst=backup/(rel+'.preexisting-dirty');shutil.copy2(root/rel,dst)
        row['dirty_snapshot']=str(dst);row['dirty_sha256']=sha(dst)
manifest_path.write_text(json.dumps(manifest,indent=2))
changes={}
preflight=json.loads((out/'preflight.json').read_text(encoding='utf8'))
assert all((root/('Content/Maps/'+stage+'.umap')).exists() for stage in ['Tutorial','Stage1','Stage2']), 'Run duplicate_canonical_maps.py in a prior isolated remote call'
for stage in ['Tutorial','Stage1','Stage2']:
    assert levels.load_level('/Game/Maps/'+stage)
    world=editor.get_editor_world()
    actors=actors_api.get_all_level_actors()
    rows={'world':world.get_path_name(),'source_actor_count':len(preflight['maps'][stage]),'zones':[]}
    if stage=='Tutorial':
        armor=next(a for a in actors if a.get_actor_label()=='Armor_Tutorial')
        rows['armor_before']=next(r for r in preflight['maps']['Tutorial'] if r['label']=='Armor_Tutorial')['location']
        armor.set_actor_location(unreal.Vector(-80,820,100),False,False)
        rows['armor_after']=[-80,820,100]
        intro=next(a for a in actors if a.get_class().get_name()=='BP_TutorialIntro_C')
        intro.set_actor_label('BP_TutorialIntro')
        rows['intro_bindings']={}
        for prop in ['Cat','StartCamera','WakeCamera','GamePlayCamera']:
            target=intro.get_editor_property(prop)
            assert target and target.get_outermost()==world.get_outermost(),(prop,str(target))
            rows['intro_bindings'][prop]=target.get_path_name()
    zones={'Tutorial':[('NoBell_CatHole_Tutorial',(-270,465,100),(50,35,100))],
           'Stage1':[],
           'Stage2':[('NoBell_CatHole_06',(2000,2460,100),(50,35,100)),('NoBell_CatHole_13',(1630,315,100),(35,50,100))]}[stage]
    for label,location,extent in zones:
        a=next((a for a in actors if a.get_actor_label()==label),None)
        if not a:a=actors_api.spawn_actor_from_class(unreal.CatrunNoBellZone,unreal.Vector(*location));a.set_actor_label(label)
        a.get_component_by_class(unreal.BoxComponent).set_box_extent(unreal.Vector(*extent),False)
        rows['zones'].append({'label':label,'location':location,'extent':extent})
    manager=next(a for a in actors if a.get_class().get_name()=='SoundGridManager')
    settings=manager.get_editor_property('Settings')
    rows['sound_settings']=settings.get_path_name() if settings else None
    rows['mark_attracts_armors']=manager.get_editor_property('bMarkAttractsArmors')
    rows['mark_call_radius']=settings.get_editor_property('MarkCallRadius') if settings else None
    assert rows['mark_attracts_armors'] and rows['mark_call_radius']==1500,rows
    rows['bell_notice']=str(settings.get_editor_property('BellBlockedNotice')) if settings else None
    rows['effective_bell_notice']='방울을 울릴수없습니다' # native CatrunNoticeLibrary::ShowBellDenied
    assert levels.save_current_level()
    changes[stage]=rows
    actors=None;a=None;intro=None;armor=None;manager=None;settings=None;world=None;target=None;gc.collect()
# Persist disk route AND synchronize this editor's cached config object.
config=root/'Config/DefaultGame.ini'
content=config.read_text(encoding='utf-8-sig')
for stage in changes:content=content.replace('SoundTest_'+stage,stage)
config.write_text(content,encoding='utf8')
s=unreal.get_default_object(unreal.load_class(None,'/Script/Catrun.CatrunLevelFlowSettings'))
routes=[]
for stage in changes:
    route=unreal.CatrunStageRoute();route.import_text('(StageId="'+stage+'",Map="/Game/Maps/'+stage+'.'+stage+'")');routes.append(route)
s.set_editor_property('Stages',routes)
changes['cached_stages']=[r.export_text() for r in s.get_editor_property('Stages')]
packaging=unreal.get_default_object(unreal.load_class(None,'/Script/DeveloperToolSettings.ProjectPackagingSettings'))
cook=[]
for name in ['MainMenu','Tutorial','Stage1','Stage2']:
    entry=unreal.FilePath();entry.set_editor_property('file_path','/Game/Maps/'+name);cook.append(entry)
packaging.set_editor_property('MapsToCook',cook)
changes['cached_cook_maps']=[str(x.get_editor_property('file_path')) for x in packaging.get_editor_property('MapsToCook')]
assert 'SoundTest_' not in config.read_text(encoding='utf8')
patch=root/'Scripts/Prototype/repair_tutorial_intro.py'
patch.write_text(patch.read_text(encoding='utf-8-sig').replace("assert 'ERROR' not in str(bp.get_editor_property('status')).upper(),str(bp.get_editor_property('status'))","assert bp.get_editor_property('status') == unreal.BlueprintStatus.BS_UP_TO_DATE, str(bp.get_editor_property('status'))"),encoding='utf8')
for row in manifest['files']:row['after_sha256']=sha(root/row['path']);row['changed']=row['after_sha256']!=row['before_sha256']
manifest_path.write_text(json.dumps(manifest,indent=2))
(out/'promotion.json').write_text(json.dumps(changes,ensure_ascii=False,indent=2),encoding='utf8')
assert levels.load_level('/Game/Maps/MainMenu')
print('CANONICAL_PROMOTION',json.dumps(changes,ensure_ascii=False))

