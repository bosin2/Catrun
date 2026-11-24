"""Focused two-sequence cinematic authoring. Import and call apply() inside Unreal."""
import datetime
import hashlib
import json
import shutil
from pathlib import Path

import unreal as u

import stage1_departure_shots as departure
import stage2_arrival_revision as arrival
import stage2_arrival_shots as tracks


DEPARTURE = '/Game/Cinematics/Stage1/Portal/LS_Stage1_PortalExit'
ARRIVAL = '/Game/Cinematics/Stage2/Arrival/LS_Stage2_PortalArrival'


def dirty():
    return {p.get_name() for p in (*u.EditorLoadingAndSavingUtils.get_dirty_map_packages(),
                                   *u.EditorLoadingAndSavingUtils.get_dirty_content_packages())}


def handoff(seq):
    bindings=tracks.bindings(seq)
    channels=tracks.section(bindings['FaceReturn'],u.MovieScene3DTransformTrack).get_channels_by_type(u.MovieSceneScriptingDoubleChannel)
    lens,=tracks.section(bindings['FaceReturnLens'],u.MovieSceneFloatTrack).get_all_channels()
    def last(channel):
        key=channel.get_keys()[-1]
        assert tracks.frameof(key)==336
        return key.get_value()
    x,y,z,roll,pitch,yaw=map(last,channels[:6])
    camera=bindings['FaceReturn'].get_object_template().get_editor_property('CameraComponent')
    assert camera.projection_mode==u.CameraProjectionMode.ORTHOGRAPHIC
    return dict(xyz=[x,y,z],pyr=[pitch,yaw,roll],width=last(lens),fov=camera.field_of_view,aspect=camera.aspect_ratio)


def protected(seq,stage):
    # Compare all binding IDs, parents, tags, animation data and non-presentation track keys.
    state=tracks.signature(seq)
    if stage==DEPARTURE:
        cameras=departure.CAMERA_NAMES
        lens_names=set()
        lights={'BlueLight',departure.SOFT_FILL}
    else:
        cameras=arrival.PERSPECTIVE|{'FaceReturn'}
        lens_names={'PuzzleLens','FaceReturnLens'}
        lights={name+'Bulb' for name in arrival.FILLS}
    for name,data in state.items():
        if name in cameras:
            data.pop('lens',None)
            data['tracks']=[t for t in data['tracks'] if t['type']!='MovieScene3DTransformTrack']
        if name in lens_names|lights:
            data['tracks']=[t for t in data['tracks'] if t['type']!='MovieSceneFloatTrack']
    if stage==DEPARTURE:
        fade,=[t for t in seq.get_tracks() if isinstance(t,u.MovieSceneFadeTrack)]
        section,=fade.get_sections()
        channel,=section.get_all_channels()
        state['__fade__']=[departure.h.span(section),departure.h.key_data(channel)]
    return state


def apply():
    root=Path(u.Paths.project_dir()).resolve()
    dest=root/'Saved/VisualRepair20261124/CinematicAuthor'/datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f')
    packages=(DEPARTURE,ARRIVAL)
    before_dirty=dirty()
    assert not before_dirty.intersection(packages),('Target sequence contains unsaved edits',before_dirty)
    assert not u.get_editor_subsystem(u.UnrealEditorSubsystem).get_game_world(),'End PIE before authoring'
    sequences={p:u.EditorAssetLibrary.load_asset(p) for p in packages}
    for (p,seq),end in zip(sequences.items(),(departure.END,arrival.END),strict=True):
        assert seq and seq.get_path_name().split('.')[0]==p
        assert seq.get_playback_start()==0 and seq.get_playback_end()==end
        rate=seq.get_display_rate()
        assert (rate.numerator,rate.denominator)==(30,1)
    endpoint=handoff(sequences[ARRIVAL])
    def audit(p):
        if p==DEPARTURE:
            departure.verify_sequence(sequences[p])
        else:
            arrival.audit_cameras(sequences[p],endpoint)
            arrival.audit_lights(sequences[p])
    pending=[]
    for pkg in packages:
        try:
            audit(pkg)
        except (AssertionError,ValueError):
            pending.append(pkg)
    report={'saved':[],'backups':{},'handoff':endpoint,'completed':False,'directory':str(dest)}
    if not pending:
        report.update(completed=True,directory=None)
        return report
    before={p:protected(sequences[p],p) for p in pending}
    dest.mkdir(parents=True)
    try:
        for pkg in pending:
            source=root/'Content'/(pkg.removeprefix('/Game/')+'.uasset')
            target=dest/source.name
            shutil.copy2(source,target)
            digest=hashlib.sha256(target.read_bytes()).hexdigest()
            assert digest==hashlib.sha256(source.read_bytes()).hexdigest()
            report['backups'][pkg]={'path':str(target),'sha256':digest}
        if DEPARTURE in pending:
            departure.apply_presentation(sequences[DEPARTURE])
        if ARRIVAL in pending:
            seq=sequences[ARRIVAL]
            arrival.apply_cameras(seq,endpoint)
            arrival.retune_lights(seq)
        for pkg in pending:
            audit(pkg)
            assert protected(sequences[pkg],pkg)==before[pkg],('Protected binding/track changed',pkg)
        assert dirty()-before_dirty<=set(pending),('Unexpected dirty packages',dirty()-before_dirty)
        for pkg in pending:
            assert u.EditorAssetLibrary.save_loaded_asset(sequences[pkg],False),pkg
            report['saved'].append(pkg)
        assert dirty()==before_dirty,('Unexpected dirty packages after save',dirty(),before_dirty)
        report['completed']=True
        return report
    except Exception as exc:
        report['error']=repr(exc)
        raise
    finally:
        (dest/'report.json').write_text(json.dumps(report,indent=2),encoding='utf8')
