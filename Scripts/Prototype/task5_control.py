"""Explicitly logged runtime staging for final checks; never saves level changes.

Reads Task5/control.json. It does not inject game keys or complete a stage.
"""
import json,time
from pathlib import Path
import unreal

ROOT=Path(unreal.Paths.project_saved_dir())/'Prototype20261104/Task5'
def vec(v): return [v.x,v.y,v.z]
def main():
    request=json.loads((ROOT/'control.json').read_text(encoding='utf-8-sig'))
    ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    lv=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    op=request['op']; result={'request':request,'epoch':time.time()}
    if op=='start':
        assert not ed.get_game_world()
        assert lv.load_level('/Game/Maps/'+request['map'])
        lv.editor_request_begin_play()
    else:
        w=ed.get_game_world(); assert w
        cat=unreal.GameplayStatics.get_player_pawn(w,0); assert cat
        pc=unreal.GameplayStatics.get_player_controller(w,0)
        result.update(world=w.get_path_name(),cat=vec(cat.get_actor_location()),view=pc.get_view_target().get_name(),move_ignored=pc.is_move_input_ignored())
        if op=='basket_stage':
            assert not pc.is_move_input_ignored()
            baskets=unreal.GameplayStatics.get_all_actors_of_class(w,unreal.CatrunHideBasket)
            basket=next(b for b in baskets if request['label'] in b.get_actor_label())
            center=basket.get_hidden_location()
            local=basket.get_editor_property('OpenDirectionLocal')
            direction=basket.get_actor_forward_vector()*local.x+basket.get_actor_right_vector()*local.y
            direction.z=0
            direction=direction/direction.length()
            target=center+direction*95
            capsule=cat.get_component_by_class(unreal.CapsuleComponent)
            floor=unreal.SystemLibrary.line_trace_single_by_profile(w,target+unreal.Vector(0,0,60),target-unreal.Vector(0,0,150),'Pawn',False,[cat,basket],unreal.DrawDebugTrace.NONE,False)
            assert floor, 'No supporting floor'
            fd=floor.to_dict(); assert fd['impact_normal'].z>=.65
            target.z=fd['impact_point'].z+capsule.get_scaled_capsule_half_height()+2.25
            hit=unreal.SystemLibrary.capsule_trace_single_by_profile(w,target,target+unreal.Vector(0,0,.1),capsule.get_scaled_capsule_radius(),capsule.get_scaled_capsule_half_height(),'Pawn',False,[cat],unreal.DrawDebugTrace.NONE,False)
            assert not hit, str(hit.to_dict()) if hit else ''
            distance=(target-center).length(); assert 50<distance<110, distance
            cat.set_actor_location(target,False,True)
            cat.set_actor_rotation(unreal.MathLibrary.find_look_at_rotation(target,center),True)
            result.update(basket=basket.get_actor_label(),hidden=vec(center),open=vec(direction),target=vec(target),distance=distance)
        elif op=='end': lv.editor_request_end_play()
        elif op=='console': unreal.SystemLibrary.execute_console_command(w,request['command'])
        elif op=='inspect':
            result['statues']=[{'id':str(l.get_editor_property('PuzzleId')),'position':vec(l.get_editor_property('Statue').get_actor_location()),'pressed':l.get_editor_property('bPressed'),'complete':l.get_editor_property('bCompleted')} for d in unreal.GameplayStatics.get_all_actors_of_class(w,unreal.CatrunStatuePuzzle) for l in d.get_editor_property('Links')]
        else: raise ValueError(op)
    with (ROOT/'api-staging.jsonl').open('a',encoding='utf8') as f: f.write(json.dumps(result)+'\n')
    print(json.dumps(result))
main()
