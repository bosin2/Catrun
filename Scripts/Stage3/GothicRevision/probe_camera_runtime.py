import sys,json,time,traceback
from pathlib import Path
import unreal as u
ROOT=Path(u.Paths.project_dir()).resolve()
OUT=ROOT/'Saved/Stage3GothicRevision20261125/camera_runtime_probe.json'
ED=u.get_editor_subsystem(u.UnrealEditorSubsystem);LE=u.get_editor_subsystem(u.LevelEditorSubsystem)
FIELDS=('projection_mode','auto_calculate_ortho_planes','update_ortho_planes','ortho_near_clip_plane','ortho_far_clip_plane','ortho_width')
def sample(a):
    c=a.get_component_by_class(u.CameraComponent)
    return {k:str(c.get_editor_property(k)) for k in FIELDS}
assert LE.load_level('/Game/Maps/Stage3')
actor=next(a for a in u.get_editor_subsystem(u.EditorActorSubsystem).get_all_level_actors() if a.get_actor_label()=='S3_FollowCamera')
S={'editor':sample(actor),'runtime':[],'graphs':[],'started':time.monotonic(),'done':False}
from editor_toolset.toolsets.blueprint import BlueprintTools as BP
bp=u.load_asset('/Game/Systems/Camera/BP_QuarterViewCamera')
for g in BP.list_graphs(bp):
    nodes=[]
    for info in BP.get_node_infos(BP.find_nodes(g)):
        n=info.node
        nodes.append({'name':n.get_name(),'type':str(info.type_id),'pins':[(str(p.get_pin_name()),str(p.get_pin_value()),[(x.get_owning_node().get_name(),str(x.get_pin_name())) for x in p.list_connected_pins()]) for p in n.list_all_pins()]})
    S['graphs'].append({'name':g.get_name(),'nodes':nodes})
def persist():OUT.write_text(json.dumps({k:v for k,v in S.items() if k!='handle'},indent=2),encoding='utf8')
def tick(dt):
    try:
        if S['done']:
            if not ED.get_game_world():
                u.unregister_slate_post_tick_callback(S['handle']);u.SystemLibrary.execute_console_command(ED.get_editor_world(),'QUIT_EDITOR')
            return
        w=ED.get_game_world()
        if w:
            t=u.GameplayStatics.get_time_seconds(w)
            if t>=len(S['runtime'])+1:
                a=next(a for a in u.GameplayStatics.get_all_actors_of_class(w,u.Actor) if a.get_actor_label()=='S3_FollowCamera')
                S['runtime'].append({'time':t,'camera':sample(a)})
                persist()
            if t>5:S['done']=True;persist();LE.editor_request_end_play()
        assert time.monotonic()-S['started']<180
    except Exception:
        S['error']=traceback.format_exc();S['done']=True;persist();LE.editor_request_end_play()
S['handle']=u.register_slate_post_tick_callback(tick)
LE.editor_request_begin_play()
