"""Read-only two-map Stage1 corridor, door, binding and cautious gait survey."""
import datetime
import gc
import json
from pathlib import Path
import sys
import traceback

import unreal as u

ROOT = Path(u.Paths.project_dir()).resolve()
sys.path.insert(0, str(ROOT/'Scripts/GameplayRepair'))
import stage1_departure_shots as shots

h = shots.h


def inspect_map(package):
    assert not h.dirty() and h.LEVEL.load_level(package)
    world=h.ED.get_editor_world()
    assert world.get_path_name().split('.')[0]==package
    actors=u.GameplayStatics.get_all_actors_of_class(world,u.Actor)
    cat=h.only(a for a in actors if a.get_name()=='BP_Cat_C_0')
    director=h.only(a for a in actors if 'CatrunAuthoredStage1Exit' in map(str,a.tags))
    door=h.only(a for a in actors if a.get_actor_label()==shots.DOOR_LABEL)
    portal=director.get_editor_property('PortalPresentation')
    assert portal and director.get_editor_property('CinematicActor').get_sequence()==h.load_asset(h.SEQUENCE)
    geometry={}
    for a in actors:
        name=a.get_actor_label()
        if name.startswith('S1_MagicCorridor_') or a==door:
            c=a.get_component_by_class(u.StaticMeshComponent)
            geometry[name]={'transform':a.get_actor_transform().export_text(),
                            'bounds':[h.tuple3(v) for v in a.get_actor_bounds(False)],
                            'mesh':c.get_editor_property('static_mesh').get_path_name() if c else None,
                            'collision':str(c.get_collision_profile_name()) if c else None}
    leaves=[a for a in actors if a.get_actor_label() in (shots.DOOR_LABEL,shots.RIGHT_LABEL)]
    result=dict(portal=h.tuple3(portal.get_actor_location()),portal_scale=h.tuple3(portal.get_actor_scale3d()),
                leaves=[dict(label=a.get_actor_label(),location=h.tuple3(a.get_actor_location()),
                              yaw=a.get_actor_rotation().yaw,collision=str(a.static_mesh_component.get_collision_profile_name()))
                        for a in leaves],geometry=geometry,
                timeout=director.get_editor_property('CinematicTimeout'),
                gait=shots.calibrate(cat.get_component_by_class(u.SkeletalMeshComponent)))
    assert not h.dirty()
    return result


def main():
    out=ROOT/'Saved/StageRevision20261123/DepartureProbe'/datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f')
    out.mkdir(parents=True,exist_ok=False)
    report={'maps':{},'completed':False}
    try:
        assert not h.ED.get_game_world()
        from author_stage1_departure import BP,DIRECTOR,graph_rows
        graph=BP.get_graph(h.load_asset(DIRECTOR),'EventGraph')
        report['graph']=graph_rows(graph)
        if '-catrundeparturegraph' in u.SystemLibrary.get_command_line().lower():
            report['completed']=True
            return
        for package in h.MAPS:
            report['maps'][package]=inspect_map(package)
            gc.collect()
        report['completed']=True
    except Exception:
        report['error']=traceback.format_exc()
        raise
    finally:
        (out/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
        print('CATRUN_DEPARTURE_PROBE',str(out),report['completed'])


if __name__=='__main__':
    main()
