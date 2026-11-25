"""Copy-of-record of the 58 Revision 3 checks, run against the re-directed sequence.

The original Scripts/ElevatorTransition/verify_runtime.py is read and executed unchanged except for the
replacements below (each must match exactly once). Every original check stays; new checks are added for the
loaf shot, its lights, the ascent dressing, a late cancel and the loaf hand-over into Stage3.
"""
import unreal as u
from pathlib import Path
ROOT = Path(u.Paths.project_dir()).resolve()
source = (ROOT/'Scripts/ElevatorTransition/verify_runtime.py').read_text(encoding='utf-8')

def rep(a, b):
    global source
    assert source.count(a) == 1, (source.count(a), a)
    source = source.replace(a, b)

rep("OUT=ROOT/'Saved/ElevatorTransition/Runtime'", "OUT=ROOT/'Saved/ElevatorRedirect/Verify'")
rep("'run':'revision3_isolation_blend_peek_arrival'", "'run':'redirect_peek_loaf_20261126'")
rep("time.monotonic()-S['started']<360", "time.monotonic()-S['started']<900")
# helpers for the new dressing
rep("def finish(error=None):", '''def dressing(d):
    return {'lights':[a.get_editor_property('hidden') for a in list(d.peek_lights)+list(d.loaf_lights)],
            'shown':[a.get_editor_property('hidden') for a in d.ascent_shown_actors],
            'hidden':[a.get_editor_property('hidden') for a in d.ascent_hidden_actors]}
def worn(cat):
    return [cat.mesh.get_skeletal_mesh_asset().get_name(),[m.get_name() if m else None for m in cat.mesh.get_materials()],str(cat.mesh.get_anim_instance().get_class().get_name()) if cat.mesh.get_anim_instance() else None]
def cabin_pose(d):
    return [vec(a.get_actor_location()) for a in d.cabin_actors]+[vec(c.get_actor_location()) for c in (d.front_camera,d.peek_camera,d.loaf_camera,d.cabin_camera)]
def finish(error=None):''')
# record the resting state before the first F
rep("S['minimap_before']=[x.get_visibility().name for x in minimaps(w)]", "S['minimap_before']=[x.get_visibility().name for x in minimaps(w)];S['dressing']=dressing(d);S['cabin_pose']=cabin_pose(d);S['worn']=worn(cat)\n            check('redirect_lights_dark_at_rest',all(S['dressing']['lights']) and all(S['dressing']['shown']) and not any(S['dressing']['hidden']))")
# a second cancel inside the loaf shot, before the normal run
rep("            key(w,'F',True);S['at']=game;advance('normal');return\n        if phase=='pause_hold':", '''            key(w,'F',True);S['at']=game;advance('late_cancel');return
        if phase=='late_cancel':
            key(w,'F',False)
            assert game-S['at']<25,'Loaf shot not reached'
            if pc.get_view_target()!=d.loaf_camera:return
            if 'loaf_seen' not in S:
                S['loaf_seen']=game;now=dressing(d)
                check('loaf_shot_dressing_active',now['lights']==[True]*len(d.peek_lights)+[False]*len(d.loaf_lights) and not any(now['shown']) and all(now['hidden']),now)
                check('cinematic_cat_worn',(d.cinematic_mesh is None) or worn(cat)[0]==d.cinematic_mesh.get_name(),worn(cat))
                return
            if game-S['loaf_seen']<1.2:return
            d.cancel_transition();S['at']=game;advance('late_cancel_check');return
        if phase=='late_cancel_check':
            if game-S['at']<.7:return
            check('late_cancel_restores_waiting_and_input',state(d)=='WAITING' and not pc.is_move_input_ignored())
            check('late_cancel_restores_play_cat',worn(cat)==S['worn'],{'before':S['worn'],'after':worn(cat)})
            check('late_cancel_restores_dressing',dressing(d)==S['dressing'])
            check('late_cancel_restores_cabin_and_lenses',max(math.dist(a,b) for a,b in zip(cabin_pose(d),S['cabin_pose']))<.05,{'max':max(math.dist(a,b) for a,b in zip(cabin_pose(d),S['cabin_pose']))})
            check('late_cancel_restores_mesh_transform',max(abs(x-y) for k in ('position','scale','rotation') for x,y in zip(mesh_pose(cat)[k],S['initial_mesh_relative'][k]))<1e-4,{'before':S['initial_mesh_relative'],'after':mesh_pose(cat),'cat':vec(cat.get_actor_location())})
            check('late_cancel_restores_minimap',[x.get_visibility().name for x in minimaps(w)]==S['minimap_before'])
            place(cat,(715,-1530,26.2));S['at']=game;advance('late_cancel_settle');return
        if phase=='late_cancel_settle':
            if game-S['at']<.6:return
            key(w,'F',True);S['at']=game;advance('normal');return
        if phase=='pause_hold':''')
# observe the new shots during the normal run
rep("            if idx==6:shot(w,'08_DarkAscent')", '''            spine=cat.mesh.get_socket_location('spine');pivot=d.cabin_pivot.get_actor_location()
            if pc.get_view_target()==d.loaf_camera:
                rows=S.setdefault('loaf_rows',[]);rows.append([game,spine.x-pivot.x,spine.y-pivot.y])
                age=game-rows[0][0]
                for delay,name in [(.4,'07d_EdgeLookDown'),(1.9,'07e_TurnInside'),(3.6,'07f_WalkInside'),(6.2,'07g_Settle'),(7.9,'07h_Loaf')]:
                    if age>delay:shot(w,name)
            if idx==6:
                S['ride_last_spine']=[spine.x-pivot.x,spine.y-pivot.y];S['ride_seen']=S.get('ride_seen',0)+1
                S['ride_first']=S.get('ride_first',game);S['ride_last']=game
                if game-S['ride_first']>.5:shot(w,'08_DarkAscent')''')
rep("                check('below_face_shot_holds_three_seconds'", '''                rows=S.get('loaf_rows',[])
                check('loaf_shot_observed',len(rows)>100 and 7<rows[-1][0]-rows[0][0]<10,{'seconds':rows[-1][0]-rows[0][0] if rows else 0})
                check('cat_starts_at_edge_and_ends_inside_in_frame',rows[0][2]>60 and abs(rows[-1][2])<12 and abs(rows[-1][1])<8,{'first':rows[0],'last':rows[-1]})
                # one frame is 1/30-1/60 s of walking; a cut or teleport would be far larger
                check('walk_inside_is_continuous',max(math.dist(a[1:],b[1:])/max(1e-3,b[0]-a[0]) for a,b in zip(rows,rows[1:]))<110,{'max_cm_per_s':max(math.dist(a[1:],b[1:])/max(1e-3,b[0]-a[0]) for a,b in zip(rows,rows[1:]))})
                check('ride_holds_loaf_before_blackout',3.0<S['ride_last']-S['ride_first']<4.4,{'seconds':S['ride_last']-S['ride_first']})
                check('below_face_shot_holds_three_seconds\'''')
rep("            row=snap(w,cat,d);S['samples'].append(row)\n            if state(d) in ('ARRIVAL'", '''            row=snap(w,cat,d);S['samples'].append(row)
            if state(d)=='ARRIVAL' and d.get_active_clip_index()==0 and 'arrival_spine' not in S:
                sp=cat.mesh.get_socket_location('spine');pv=d.cabin_pivot.get_actor_location()
                S['arrival_spine']=[sp.x-pv.x,sp.y-pv.y]
                # Stage3 cabin is turned 180 degrees around its pivot
                check('loaf_position_carries_over_blackout',math.dist(S['arrival_spine'],[-v for v in S['ride_last_spine']])<3,{'stage2':S['ride_last_spine'],'stage3':S['arrival_spine']})
            if state(d) in ('ARRIVAL\'''')
rep("                check('arrival_restores_input',not pc.is_move_input_ignored())", "                check('arrival_restores_input',not pc.is_move_input_ignored())\n                check('arrival_restores_play_cat',worn(cat)==S['worn'],{'before':S['worn'],'after':worn(cat)})")
rep("            check('skip_travel_and_arrival_restore',not pc.is_move_input_ignored())", "            check('skip_travel_and_arrival_restore',not pc.is_move_input_ignored())\n            check('skip_restores_play_cat',worn(cat)==S['worn'],worn(cat))")
exec(compile(source, 'verify_runtime.py(redirect)', 'exec'), globals())
