"""Shared pieces of the two portal cinematics (main project, 2026-11-26 slow re-direction)."""
import hashlib
import json
import sys
from pathlib import Path

import unreal as u

ROOT = Path(u.Paths.project_dir()).resolve()
assert ROOT == Path('C:/Users/whghk/Catrun').resolve(), ROOT
TOOLS = Path(__file__).resolve().parent
OUT = ROOT / 'Saved/PortalCinematic'
BASE = OUT / 'Base'
MAIN = Path('C:/Users/whghk/Catrun')
SRC = json.loads((TOOLS / 'cat_source.json').read_text(encoding='utf-8'))
FOLDER, MESH = SRC['folder'], SRC['mesh']
MESH_FOLDER = SRC.get('mesh_folder', FOLDER)
RING = FOLDER + '/M_PortalRing'
AS = u.EditorAssetLibrary
RESTORE = u.MovieSceneCompletionMode.RESTORE_STATE
LINEAR, AUTO = u.MovieSceneKeyInterpolation.LINEAR, u.MovieSceneKeyInterpolation.AUTO
TICKS = u.MovieSceneTimeUnit.TICK_RESOLUTION
EASE = u.MovieSceneSectionEasingExtensions
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
tick = lambda f: round(f * 800)
only = lambda items: (lambda l: l[0] if len(l) == 1 else (_ for _ in ()).throw(AssertionError(l)))(list(items))


def mode():
    return getattr(sys, '_compact_mode', 'fresh')


def dirty():
    return sorted(p.get_path_name() for p in (*u.EditorLoadingAndSavingUtils.get_dirty_content_packages(),
                                              *u.EditorLoadingAndSavingUtils.get_dirty_map_packages()))


def pristine(rel):
    """The launcher copies Saved/PortalCinematic/Base/<file> over the main package before the editor starts."""
    path, base = ROOT / rel, BASE / Path(rel).name
    assert sha(path) == sha(base), ('Main package is not the authoring base; run through run_author.ps1', rel)
    return path


def keys(channel, rows, interp=LINEAR, default=None):
    for k in list(channel.get_keys()):
        channel.remove_key(k)
    if default is not None:
        channel.set_default(default)
    for f, v in rows:
        channel.add_key(u.FrameNumber(tick(f)), v, 0., TICKS, interp)


def doubles(section):
    c = section.get_channels_by_type(u.MovieSceneScriptingDoubleChannel)
    assert len(c) == 9
    return c


def transform(binding, rows, end, interp=LINEAR):
    tracks = binding.find_tracks_by_type(u.MovieScene3DTransformTrack)
    s = only(only(tracks).get_sections()) if tracks else binding.add_track(u.MovieScene3DTransformTrack).add_section()
    s.set_range(0, end)
    s.set_completion_mode(RESTORE)
    for i, ch in enumerate(doubles(s)):
        keys(ch, [(f, float(r[i])) for f, r in rows], interp, float(rows[0][1][i]))
    return s


def spawn_range(binding, first, last):
    tracks = binding.find_tracks_by_type(u.MovieSceneSpawnTrack)
    s = only(only(tracks).get_sections()) if tracks else binding.add_track(u.MovieSceneSpawnTrack).add_section()
    s.set_range(first, last)
    s.set_completion_mode(RESTORE)
    only(s.get_all_channels()).set_default(True)


def visible_track(binding, rows, end):
    tracks = binding.find_tracks_by_type(u.MovieSceneVisibilityTrack)
    if tracks:
        s = only(only(tracks).get_sections())
    else:
        t = binding.add_track(u.MovieSceneVisibilityTrack)
        t.set_property_name_and_path('bHidden', 'bHidden')
        s = t.add_section()
    s.set_range(0, end)
    s.set_completion_mode(RESTORE)
    ch = only(s.get_all_channels())
    for k in list(ch.get_keys()):
        ch.remove_key(k)
    ch.set_default(rows[0][1])
    for f, v in rows:
        ch.add_key(u.FrameNumber(f), v)


def no_collision(actor, comp):
    actor.set_actor_enable_collision(False)
    comp.set_collision_profile_name('NoCollision')
    comp.set_editor_property('generate_overlap_events', False)


def cat_spawnable(seq, name, end, tag='CatrunCinematicCat'):
    b = seq.add_spawnable_from_class(u.SkeletalMeshActor.static_class())
    b.set_name(name)
    b.tag_binding(tag)
    t = b.get_object_template()
    m = t.get_editor_property('skeletal_mesh_component')
    m.set_skeletal_mesh_asset(u.load_asset(f'{MESH_FOLDER}/{MESH}'))
    m.set_editor_property('mobility', u.ComponentMobility.MOVABLE)
    m.set_editor_property('bounds_scale', 2.)
    no_collision(t, m)
    spawn_range(b, 0, end)
    return b


def clip(name):
    c = u.load_asset(f'{FOLDER}/{name}')
    assert isinstance(c, u.AnimSequence), name
    return c


def animation(track, asset, first, last, rate, source, ease_in=0, ease_out=0):
    """source < 0 freezes the pose at -source frames."""
    s = track.add_section()
    s.set_range(first, last)
    s.set_completion_mode(RESTORE)
    p = u.MovieSceneSkeletalAnimationParams()
    for n, v in (('animation', asset), ('play_rate', u.MovieSceneTimeWarpExtensions.make_time_warp(rate)),
                 ('start_frame_offset', u.FrameNumber(tick(max(0., source)))),
                 ('first_loop_start_frame_offset', u.FrameNumber(tick(max(0., -source)))),
                 ('force_custom_mode', True), ('skip_anim_notifiers', True)):
        p.set_editor_property(n, v)
    s.set_editor_property('params', p)
    if ease_in:
        EASE.set_ease_in_duration(s, tick(ease_in))
    if ease_out:
        EASE.set_ease_out_duration(s, tick(ease_out))
    return s


def ring_material(custom_expression):
    if AS.does_asset_exist(RING):
        return u.load_asset(RING)
    m = u.AssetToolsHelpers.get_asset_tools().create_asset('M_PortalRing', FOLDER, u.Material, u.MaterialFactoryNew())
    for k, v in (('blend_mode', u.BlendMode.BLEND_ADDITIVE), ('shading_model', u.MaterialShadingModel.MSM_UNLIT), ('two_sided', True)):
        m.set_editor_property(k, v)
    e = u.MaterialEditingLibrary
    uv = e.create_material_expression(m, u.MaterialExpressionTextureCoordinate, -600, 0)
    op = e.create_material_expression(m, u.MaterialExpressionScalarParameter, -600, 250)
    op.set_editor_property('parameter_name', 'RippleOpacity')
    op.set_editor_property('default_value', 0.)
    color = custom_expression(m, (-250, 0), 'One blue portal contact wave',
                              'float r=length((UV-.5)*2); float ring=exp(-pow((r-.63)/.115,2)); '
                              'float core=.12*exp(-r*r*10); return float3(.03,.30,1.15)*(ring+core);',
                              u.CustomMaterialOutputType.CMOT_FLOAT3, [('UV', uv)])
    assert e.connect_material_property(color, '', u.MaterialProperty.MP_EMISSIVE_COLOR)
    assert e.connect_material_property(op, '', u.MaterialProperty.MP_OPACITY)
    e.recompile_material(m)
    return m


def ring(seq, material, name, first, frames, location, scales, opacity, end):
    """An additive wave on the vertical portal plane (normal along world Y)."""
    actors = u.get_editor_subsystem(u.EditorActorSubsystem)
    tmp = actors.spawn_actor_from_class(u.StaticMeshActor.static_class(), u.Vector(), u.Rotator(), transient=True)
    mesh = tmp.get_editor_property('static_mesh_component')
    mesh.set_static_mesh(u.load_asset('/Engine/BasicShapes/Plane'))
    mesh.set_material(0, material)
    mesh.set_editor_property('cast_shadow', False)
    mesh.set_editor_property('mobility', u.ComponentMobility.MOVABLE)
    no_collision(tmp, mesh)
    b = seq.add_spawnable_from_instance(tmp)
    b.set_name(name)
    b.get_object_template().set_actor_enable_collision(False)
    spawn_range(b, first, first + frames)
    n = len(scales) - 1
    transform(b, [(first + frames * i / n, (*location, 90., 0., 0., s, s, 1.)) for i, s in enumerate(scales)], end)
    child = seq.add_possessable(mesh)
    parent = child.get_parent()
    child.set_parent(b)
    child.set_name(name + 'Material')
    if parent.get_id().export_text() != b.get_id().export_text():
        assert not parent.get_child_possessables()
        parent.remove()
    assert actors.destroy_actor(tmp)
    t = child.add_track(u.MovieSceneComponentMaterialTrack)
    t.set_material_info(u.ComponentMaterialInfo(material_slot_index=0, material_type=u.ComponentMaterialType.INDEXED_MATERIAL))
    s = t.add_section()
    s.set_range(first, first + frames)
    s.set_completion_mode(RESTORE)
    info = u.MaterialParameterInfo(name='RippleOpacity')
    n = len(opacity) - 1
    for i, v in enumerate(opacity):
        s.add_scalar_parameter_key(info, u.FrameNumber(tick(first + (frames - 1) * i / n)), v, '', '', LINEAR)
    return b


def drop(seq, names):
    for b in list(seq.get_bindings()):
        if b.get_name() in names:
            for child in b.get_child_possessables():
                child.remove()
            b.remove()


def lens(comp, focus=None, fstop=None, blur=None, exposure=None, bloom=None, near=None):
    comp.modify()
    if near is not None:
        comp.set_editor_property('override_custom_near_clipping_plane', True)
        comp.set_editor_property('custom_near_clipping_plane', near)
    st = comp.get_editor_property('post_process_settings').copy()
    for n, v in (('depth_of_field_focal_distance', focus), ('depth_of_field_fstop', fstop), ('motion_blur_amount', blur),
                 ('auto_exposure_bias', exposure), ('bloom_intensity', bloom)):
        if v is not None:
            st.set_editor_property('override_' + n, True)
            st.set_editor_property(n, v)
    comp.set_editor_property('post_process_settings', st)
    comp.set_editor_property('post_process_blend_weight', 1.)


def finish(seq, others, rep):
    allowed = {a.get_path_name().split('.')[0] for a in (seq, *others)}
    if mode() == 'dry':
        rep['dry_dirty'] = dirty()
        assert {d.split('.')[0] for d in dirty()} <= allowed | {d.split('.')[0] for d in rep.get('preexisting', [])}, dirty()
        return
    assert {d.split('.')[0] for d in dirty()} <= allowed, dirty()
    for a in (*others, seq):
        assert AS.save_loaded_asset(a, False), a.get_path_name()
