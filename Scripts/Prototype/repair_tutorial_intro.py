"""Permanent focused intro repair. Run through ue_remote.py with PIE stopped.

Only BP_TutorialIntro and its SoundTest_Tutorial instance are saved. The original
sequence, spawnable cameras, FinishIntro, cat BP and menu assets are preserved.
"""
import unreal, json, shutil, hashlib, datetime
from pathlib import Path
from editor_toolset.toolsets.blueprint import BlueprintTools as BP
from toolset_registry.helpers import compile_blueprint as compile_checked

root=Path(unreal.Paths.project_dir()).resolve()
out=root/'Saved/Prototype20261104'
backup=out/'IntroFixBackups'
backup.mkdir(parents=True,exist_ok=True)
assets=unreal.EditorAssetLibrary
levels=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
editor=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not editor.get_game_world(), 'Stop PIE first'
bp=assets.load_asset('/Game/Blueprints/BP_TutorialIntro')
assert levels.load_level('/Game/Maps/SoundTest_Tutorial')
world=editor.get_editor_world()
manifest_path=backup/'manifest.json'
manifest=json.loads(manifest_path.read_text()) if manifest_path.exists() else {'created_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'assets':[]}

def back_up(obj,rel,save):
    target=backup/rel
    if any(x['relative_path']==rel for x in manifest['assets']):return
    target.parent.mkdir(parents=True,exist_ok=True)
    shutil.copy2(root/rel,target)
    dirty=[p.get_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()]+[p.get_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()]
    package=obj.get_outermost().get_name()
    entry={'relative_path':rel,'package':package,'was_dirty':package in dirty,'disk_before_sha256':hashlib.sha256(target.read_bytes()).hexdigest()}
    # Preserve unsaved preexisting work in the same intended package before edits.
    if package in dirty:
        assert save()
        dirty_target=target.with_name(target.stem+'.preexisting-dirty'+target.suffix)
        shutil.copy2(root/rel,dirty_target)
        entry['preexisting_dirty_snapshot']=str(dirty_target)
    manifest['assets'].append(entry)
    manifest_path.write_text(json.dumps(manifest,indent=2),encoding='utf8')

back_up(bp,'Content/Blueprints/BP_TutorialIntro.uasset',lambda:assets.save_loaded_asset(bp,False))
back_up(world,'Content/Maps/SoundTest_Tutorial.umap',levels.save_current_level)
g=BP.get_graph(bp,'EventGraph')

def info(n):return BP.get_node_infos([n])[0]
def pin(n,name,out=False):
    ps=info(n).output_pins if out else info(n).input_pins
    return next(p.pin_id for p in ps if p.name==name)
def link(a,an,b,bn):BP.connect_pins(pin(a,an,True),pin(b,bn))
def val(n,name,value):BP.set_pin_value(pin(n,name),value)
def find_type(suffix):
    choices=unreal.BlueprintGraphEditor.get_graph_editor(g).list_available_nodes([])
    matches=list(dict.fromkeys(x for x in choices if x.endswith('|'+suffix)))
    assert len(matches)==1,(suffix,matches)
    return matches[0]
new_nodes=[]
def make(suffix,x,y,cls=None):
    n=BP.create_node(g,find_type(suffix),unreal.IntPoint(x,y),cls)
    new_nodes.append(n)
    return n
nodes={n.node.get_name():n.node for n in BP.get_node_infos(BP.find_nodes(g))}
existing=any(n.type_id=='Catrun|LevelFlow|RestorePlayableStart' for n in BP.get_node_infos(BP.find_nodes(g)))
if not existing:
    BP.add_object_variable(bp,'WakeCamera',unreal.CameraActor.static_class())
    BP.set_variable_instance_editable(bp,'WakeCamera',True)
    BP.set_variable_category(bp,'WakeCamera','Intro Bindings')
    # The sequence's relative IDs are serialized directly; editor scripting APIs
    # are not used by gameplay. Only these three actor possessables are rebound.
    seq=assets.load_asset('/Game/Cinematics/LS_Tutorial')
    ids={b.get_name():seq.get_binding_id(b).export_text() for b in seq.get_possessables() if b.get_name() in ['BP_Cat_Player','CINE_Tutorial_MainMenuStart','CINE_Tutorial_MainMenuCatWakeUp']}
    assert len(ids)==3
    before=nodes['K2Node_AddDelegate_0']; play=nodes['K2Node_CallFunction_7']; create=nodes['K2Node_CallFunction_6']
    BP.break_pins(pin(before,'then',True),pin(play,'execute'))
    chain=before
    for index,(name,var) in enumerate([('BP_Cat_Player','Cat'),('CINE_Tutorial_MainMenuStart','StartCamera'),('CINE_Tutorial_MainMenuCatWakeUp','WakeCamera')]):
        x=2800+index*440
        getter=make('Get'+var,x,500)
        binding=make('SetBinding',x,120,unreal.LevelSequenceActor.static_class())
        array_types=[x for x in unreal.BlueprintGraphEditor.get_graph_editor(g).list_available_nodes([]) if x.startswith('Utilities|Array|')]
        array_type=next(x for x in array_types if x.rsplit('|',1)[-1] in ['배열만들기','MakeArray'])
        array=BP.create_node(g,array_type,unreal.IntPoint(x,350));new_nodes.append(array)
        link(array,'Array',binding,'Actors')
        link(getter,var,array,'[0]')
        link(create,'OutActor',binding,'self')
        val(binding,'Binding',ids[name]);val(binding,'bAllowBindingsFromAsset','false')
        link(chain,'then',binding,'execute');chain=binding
    link(chain,'then',play,'execute')
    BP.set_node_position(play,unreal.IntPoint(4200,120))

    # Inspect retry token before camera tick/input/movement locks can be issued.
    begin=nodes['K2Node_Event_0']; first=nodes['K2Node_CallFunction_0']
    skip=BP.create_node(g,'Catrun|LevelFlow|ShouldSkipStageIntro',unreal.IntPoint(-1200,-250),unreal.CatrunLevelFlowLibrary.static_class());new_nodes.append(skip)
    branch=make('Branch',-900,0)
    BP.break_pins(pin(begin,'then',True),pin(first,'execute'))
    link(begin,'then',skip,'execute');link(skip,'then',branch,'execute');link(skip,'ReturnValue',branch,'Condition');link(branch,'else',first,'execute')
    cat=make('GetCat',-1200,-700)
    mesh=nodes['K2Node_VariableGet_6']
    anim=make('SetAnimInstanceClass',-650,-500,unreal.SkeletalMeshComponent.static_class())
    link(mesh,'Mesh',anim,'self')
    val(anim,'NewClass','/Game/Characters/BlackCat/Final/Animations/ABP_Cat_Final.ABP_Cat_Final_C')
    link(branch,'then',anim,'execute')
    restore=make('RestorePlayableStart',-300,-500,unreal.CatrunLevelFlowLibrary.static_class())
    camera=make('GetGamePlayCamera',-600,-900)
    link(anim,'then',restore,'execute');link(cat,'Cat',restore,'Pawn');link(camera,'GamePlayCamera',restore,'GameplayViewTarget')
    transform=make('MakeTransform',-600,-1150,unreal.MathLibrary.static_class())
    val(transform,'Location','170.000000,-95.000000,23.500000')
    val(transform,'Rotation','0.000000,90.000000,0.000000')
    val(transform,'Scale','1.000000,1.000000,1.000000')
    link(transform,'ReturnValue',restore,'PlayableTransform')

# Normalize an interrupted prior attempt as well as the final repeatable patch.
infos=BP.get_node_infos(BP.find_nodes(g))
skip=next(n.node for n in infos if n.type_id=='Catrun|LevelFlow|ShouldSkipStageIntro')
restore=next(n.node for n in infos if n.type_id=='Catrun|LevelFlow|RestorePlayableStart')
branch=next(n.node for n in infos if isinstance(n.node,unreal.K2Node_IfThenElse))
begin=nodes['K2Node_Event_0']
for old in list(next(p for p in info(branch).input_pins if p.name=='execute').connected_pins):
    if old.node==begin:BP.break_pins(old,pin(branch,'execute'))
link(begin,'then',skip,'execute');link(skip,'then',branch,'execute')
if not next(p for p in info(restore).input_pins if p.name=='PlayableTransform').connected_pins:
    transform=make('MakeTransform',-600,-1150,unreal.MathLibrary.static_class())
    val(transform,'Location','170.000000,-95.000000,23.500000')
    val(transform,'Rotation','0.000000,90.000000,0.000000')
    val(transform,'Scale','1.000000,1.000000,1.000000')
    link(transform,'ReturnValue',restore,'PlayableTransform')
# Use the undecorated helper: tool_call wrappers report errors to Unreal's log
# and may not propagate them back as Python exceptions.
compile_checked(bp,True)
assert bp.get_editor_property('status') == unreal.BlueprintStatus.BS_UP_TO_DATE, str(bp.get_editor_property('status'))
print('CHECKED_COMPILE_STATUS',str(bp.get_editor_property('status')))

actors=unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
intro=next(a for a in actors if a.get_class().get_name()=='BP_TutorialIntro_C')
wake=next(a for a in actors if a.get_actor_label()=='CINE_Tutorial_MainMenuCatWakeUp')
intro.set_editor_property('WakeCamera',wake)
assert assets.save_loaded_asset(bp,False)
assert levels.save_current_level()
result={'status':'saved','blueprint':bp.get_path_name(),'map':world.get_path_name(),'wake_camera':wake.get_path_name(),'created_nodes':[n.get_name() for n in new_nodes],'existing_patch':existing,'backup_manifest':str(manifest_path),'zzz_owner':'FX_DemonKing_SleepZzz belongs to sleeping demon, separate from cat; preserved'}
(out/'intro-permanent-patch.json').write_text(json.dumps(result,indent=2),encoding='utf8')
print('INTRO_PERMANENT_PATCH',json.dumps(result))

