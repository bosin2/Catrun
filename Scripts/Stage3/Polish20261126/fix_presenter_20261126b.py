"""Stage3 Polish 2026-11-26 (b): readability fix for BP_S3Polish_Presenter.  Run with UnrealEditor-Cmd -run=pythonscript.

1) OutsideGround: plane enlarged to cover the whole camera view; new lit+emissive material
   M_S3Polish_OutsideGroundBase (world-aligned dark stone/earth) as parent of MI_S3Polish_OutsideGround.
2) Lock devices: light pulse wider/faster (BP PresenterTick pin defaults), sigil emissive pulse in its
   custom HLSL widened and put in phase with the light (same sin(T*speed)), and a soft amber light pillar (LockBeam0..2, new
   M_S3Polish_LockBeam) that stays readable when a wall hides the floor sigil. Beams reuse the existing
   SetCustomPrimitiveDataFloat (extra Target link) so they turn green on release.
Idempotent: rerunning updates values. Cosmetic only. Assets backed up beforehand in
Saved/Stage3Polish20261126/Backup/PresenterFix_*.
"""
import json, math, traceback
import unreal as u

P = {
    'pulse_speed': 5.0,             # rad/s  -> period 1.26 s (BP light and both materials)
    'light_min': 3.0, 'light_max': 36.0, 'light_released': 8.0, 'light_radius': 440.0,
    'sigil_scale': [2.6, 2.15, 2.6],   # lock1 sits next to the outer wall: larger would spill onto OutsideGround
    'sigil_pulse_min': 0.18, 'sigil_pulse_max': 1.15,
    'beam_height': 340.0, 'beam_radius_scale': 0.7, 'beam_intensity': 12.0,
    'ground_loc': (25.0, -2300.0, -8.0), 'ground_scale': (120.0, 160.0, 1.0),
    'ground_brightness': 0.22, 'ground_emissive': 0.8,
    'ground_tint': (0.064, 0.058, 0.051),
}
try:
    import os
    if os.environ.get('S3P_FIX_PARAMS'):
        P.update(json.loads(os.environ['S3P_FIX_PARAMS']))
except Exception:
    pass

DIR = '/Game/Environment/Stage3/Polish_20261126'
BPP = DIR + '/BP_S3Polish_Presenter'
OUTLOG = u.Paths.project_saved_dir() + 'Stage3Polish20261126/Audit/fix_presenter_b.json'
MEL = u.MaterialEditingLibrary
LOG = {'params': P, 'steps': [], 'errors': []}


def note(*a):
    LOG['steps'].append(' '.join(str(x) for x in a)); print('S3PFIX', *a)


def mat_asset(name, cls=u.Material, factory=None):
    path = DIR + '/' + name
    if u.EditorAssetLibrary.does_asset_exist(path):
        m = u.load_asset(path)
        MEL.delete_all_material_expressions(m)
        return m
    return u.AssetToolsHelpers.get_asset_tools().create_asset(name, DIR, cls, factory or u.MaterialFactoryNew())


def expr(m, cls, x, y, **props):
    e = MEL.create_material_expression(m, cls, x, y)
    for k, v in props.items():
        e.set_editor_property(k, v)
    return e


def link(a, aout, b, bin_):
    if not MEL.connect_material_expressions(a, aout, b, bin_):
        raise RuntimeError('connect failed %s.%s -> %s.%s' % (a.get_name(), aout, b.get_name(), bin_))


def custom(m, x, y, code, inputs, out_type, desc):
    c = expr(m, u.MaterialExpressionCustom, x, y)
    c.set_editor_property('code', code)
    c.set_editor_property('description', desc)
    c.set_editor_property('output_type', out_type)
    ins = []
    for n in inputs:
        ci = u.CustomInput(); ci.set_editor_property('input_name', n); ins.append(ci)
    c.set_editor_property('inputs', ins)
    return c


def cpd_param(m, x, y, name, idx):
    p = expr(m, u.MaterialExpressionScalarParameter, x, y, parameter_name=name, default_value=0.0)
    p.set_editor_property('use_custom_primitive_data', True)
    p.set_editor_property('primitive_data_index', idx)
    return p


def sampler_for(tex):
    cs = tex.get_editor_property('compression_settings')
    if cs == u.TextureCompressionSettings.TC_NORMALMAP:
        return u.MaterialSamplerType.SAMPLERTYPE_NORMAL
    if cs == u.TextureCompressionSettings.TC_MASKS:
        return u.MaterialSamplerType.SAMPLERTYPE_MASKS
    if cs == u.TextureCompressionSettings.TC_GRAYSCALE:
        return u.MaterialSamplerType.SAMPLERTYPE_GRAYSCALE if tex.get_editor_property('srgb') else u.MaterialSamplerType.SAMPLERTYPE_LINEAR_GRAYSCALE
    if not tex.get_editor_property('srgb'):
        return u.MaterialSamplerType.SAMPLERTYPE_LINEAR_COLOR
    return u.MaterialSamplerType.SAMPLERTYPE_COLOR


def compile_save(m):
    MEL.recompile_material(m)
    u.EditorAssetLibrary.save_loaded_asset(m, False)


# ---------------------------------------------------------------- materials
def build_beam():
    m = mat_asset('M_S3Polish_LockBeam')
    m.set_editor_property('blend_mode', u.BlendMode.BLEND_ADDITIVE)
    m.set_editor_property('shading_model', u.MaterialShadingModel.MSM_UNLIT)
    m.set_editor_property('two_sided', False)
    wp = expr(m, u.MaterialExpressionWorldPosition, -900, -200)
    op = expr(m, u.MaterialExpressionObjectPositionWS, -900, -100)
    nrm = expr(m, u.MaterialExpressionVertexNormalWS, -900, 0)
    cam = expr(m, u.MaterialExpressionCameraVectorWS, -900, 100)
    t = expr(m, u.MaterialExpressionTime, -900, 200)
    rel = cpd_param(m, -900, 300, 'Released', 0)
    h = expr(m, u.MaterialExpressionScalarParameter, -900, 400, parameter_name='Height', default_value=P['beam_height'])
    inten = expr(m, u.MaterialExpressionScalarParameter, -900, 500, parameter_name='Intensity', default_value=P['beam_intensity'])
    code = (
        'float hh = max(H, 1.0);\n'
        'float h = saturate((WP.z - (OP.z - hh * 0.5)) / hh);\n'
        'float fade = pow(1.0 - h, 1.4) * smoothstep(0.10, 0.40, h);\n'
        'float facing = saturate(abs(dot(normalize(N.xy + 1e-4), normalize(V.xy + 1e-4))));\n'
        'float core = facing * facing;\n'
        'float p = 0.5 + 0.5 * sin(T * %.4f);\n'
        'float pulse = lerp(lerp(0.22, 1.0, p), 0.10, Rel);\n'
        'float3 col = lerp(float3(1.0, 0.42, 0.10), float3(0.30, 1.0, 0.50), Rel);\n'
        'return col * Intensity * fade * core * pulse;\n') % P['pulse_speed']
    c = custom(m, -500, 0, code, ['WP', 'OP', 'N', 'V', 'T', 'Rel', 'H', 'Intensity'],
               u.CustomMaterialOutputType.CMOT_FLOAT3, 'S3P_LockBeam')
    for e, n in [(wp, 'WP'), (op, 'OP'), (nrm, 'N'), (cam, 'V'), (t, 'T'), (rel, 'Rel'), (h, 'H'), (inten, 'Intensity')]:
        link(e, '', c, n)
    MEL.connect_material_property(c, '', u.MaterialProperty.MP_EMISSIVE_COLOR)
    compile_save(m)
    note('beam material built')
    return m


def patch_sigil():
    m = u.load_asset(DIR + '/M_S3Polish_LockSigil')
    exprs = list(MEL.get_material_expressions(m))
    base = [e for e in exprs if isinstance(e, u.MaterialExpressionCustom) and e.get_editor_property('description') != 'S3P_SigilPulse']
    LOG['sigil_code'] = [e.get_editor_property('code') for e in base]
    old = [e for e in exprs if isinstance(e, u.MaterialExpressionCustom) and e.get_editor_property('description') == 'S3P_SigilPulse']
    old_mul = [e for e in exprs if isinstance(e, u.MaterialExpressionMultiply) and e.get_editor_property('desc') == 'S3P_SigilPulseMul']
    for e in old + old_mul:
        MEL.delete_material_expression(m, e)
    src = base[0]
    import re
    code = src.get_editor_property('code')
    pat = re.compile(r'float pulse=lerp\((.*?),0\.45,rel\);')
    assert pat.search(code), 'sigil pulse line not found'
    code = pat.sub('float pulse=lerp(lerp(%.3f,%.3f,0.5+0.5*sin(T*%.4f)),0.45,rel);' % (P['sigil_pulse_min'], P['sigil_pulse_max'], P['pulse_speed']), code)
    src.set_editor_property('code', code)
    LOG['sigil_code_after'] = code
    MEL.connect_material_property(src, '', u.MaterialProperty.MP_EMISSIVE_COLOR)
    compile_save(m)
    note('sigil material patched')


def build_ground():
    m = mat_asset('M_S3Polish_OutsideGroundBase')
    m.set_editor_property('blend_mode', u.BlendMode.BLEND_OPAQUE)
    # Unlit: point lights here cast no shadows and would otherwise leak through the outer walls onto the ground
    m.set_editor_property('shading_model', u.MaterialShadingModel.MSM_UNLIT)
    TX = '/Game/Environment/Stage3/FinalGuard/Textures/'
    tb = u.load_asset(TX + 'T_S3_dark_stone_BaseColor'); tn = u.load_asset(TX + 'T_S3_dark_stone_Normal_DX'); to = u.load_asset(TX + 'T_S3_dark_stone_ORM')
    wp = expr(m, u.MaterialExpressionWorldPosition, -1400, 0)
    mask = expr(m, u.MaterialExpressionComponentMask, -1200, 0, r=True, g=True, b=False, a=False)
    link(wp, '', mask, '')
    uv1 = expr(m, u.MaterialExpressionMultiply, -1000, -100, const_b=1.0 / 360.0); link(mask, '', uv1, 'A')
    uv2 = expr(m, u.MaterialExpressionMultiply, -1000, 150, const_b=1.0 / 1900.0); link(mask, '', uv2, 'A')
    sa = expr(m, u.MaterialExpressionTextureSample, -800, -200, texture=tb, sampler_type=sampler_for(tb)); link(uv1, '', sa, 'UVs')
    sb = expr(m, u.MaterialExpressionTextureSample, -800, 100, texture=tb, sampler_type=sampler_for(tb)); link(uv2, '', sb, 'UVs')
    sn = expr(m, u.MaterialExpressionTextureSample, -800, 400, texture=tn, sampler_type=sampler_for(tn)); link(uv1, '', sn, 'UVs')
    so = expr(m, u.MaterialExpressionTextureSample, -800, 700, texture=to, sampler_type=sampler_for(to)); link(uv1, '', so, 'UVs')
    tint = expr(m, u.MaterialExpressionVectorParameter, -800, -450, parameter_name='ColorTint',
                default_value=u.LinearColor(*P['ground_tint'], 1.0))
    br = expr(m, u.MaterialExpressionScalarParameter, -400, -450, parameter_name='Brightness', default_value=P['ground_brightness'])
    em = expr(m, u.MaterialExpressionScalarParameter, -400, -350, parameter_name='EmissiveStrength', default_value=P['ground_emissive'])
    code = ('float m = saturate(dot(B, float3(0.333, 0.333, 0.333)) * 12.0);\n'
            'return A * Tint * lerp(0.55, 1.35, m) * 16.6;\n')
    alb = custom(m, -500, -100, code, ['A', 'B', 'Tint'], u.CustomMaterialOutputType.CMOT_FLOAT3, 'S3P_GroundAlbedo')
    link(sa, 'RGB', alb, 'A'); link(sb, 'RGB', alb, 'B'); link(tint, '', alb, 'Tint')
    bc = expr(m, u.MaterialExpressionMultiply, -200, -200); link(alb, '', bc, 'A'); link(br, '', bc, 'B')
    ecode = ('float relief = saturate(0.78 + 1.8 * dot(N.xy, float2(0.6, 0.45)));\n'
             'return Alb * relief * E;\n')
    ec = custom(m, -200, 0, ecode, ['Alb', 'N', 'E'], u.CustomMaterialOutputType.CMOT_FLOAT3, 'S3P_GroundEmissive')
    link(alb, '', ec, 'Alb'); link(sn, 'RGB', ec, 'N'); link(em, '', ec, 'E')
    # (unlit) MEL.connect_material_property(bc, '', u.MaterialProperty.MP_BASE_COLOR)
    MEL.connect_material_property(ec, '', u.MaterialProperty.MP_EMISSIVE_COLOR)
    # (unlit) MEL.connect_material_property(sn, 'RGB', u.MaterialProperty.MP_NORMAL)
    # (unlit) MEL.connect_material_property(so, 'G', u.MaterialProperty.MP_ROUGHNESS)
    compile_save(m)
    mi = u.load_asset(DIR + '/MI_S3Polish_OutsideGround')
    LOG['mi_parent_before'] = str(mi.get_editor_property('parent').get_path_name())
    MEL.set_material_instance_parent(mi, m)
    MEL.set_material_instance_scalar_parameter_value(mi, 'Brightness', P['ground_brightness'])
    MEL.set_material_instance_scalar_parameter_value(mi, 'EmissiveStrength', P['ground_emissive'])
    MEL.set_material_instance_vector_parameter_value(mi, 'ColorTint', u.LinearColor(*P['ground_tint'], 1.0))
    MEL.update_material_instance(mi)
    u.EditorAssetLibrary.save_loaded_asset(mi, False)
    note('ground material built; MI reparented')
    return m


# ---------------------------------------------------------------- blueprint components
def scs(bp):
    sub = u.get_engine_subsystem(u.SubobjectDataSubsystem)
    out = {}
    for h in sub.k2_gather_subobject_data_for_blueprint(bp):
        d = u.SubobjectDataBlueprintFunctionLibrary.get_data(h)
        o = u.SubobjectDataBlueprintFunctionLibrary.get_object(d)
        if o is not None:
            out[o.get_name().replace('_GEN_VARIABLE', '')] = (h, o)
    return sub, out


def fix_components(bp, beam_mat):
    sub, comps = scs(bp)
    g = comps['OutsideGround'][1]
    g.set_editor_property('relative_location', u.Vector(*P['ground_loc']))
    g.set_editor_property('relative_scale3d', u.Vector(*P['ground_scale']))
    for i in range(3):
        s = comps['LockSigil%d' % i][1]
        s.set_editor_property('relative_scale3d', u.Vector(P['sigil_scale'][i], P['sigil_scale'][i], 1.0))
        comps['LockLight%d' % i][1].set_editor_property('attenuation_radius', P['light_radius'])
    root_h = comps['DefaultSceneRoot'][0]
    cyl = u.load_asset('/Engine/BasicShapes/Cylinder')
    for i in range(3):
        name = 'LockBeam%d' % i
        if name not in comps:
            params = u.AddNewSubobjectParams(parent_handle=root_h, new_class=u.StaticMeshComponent, blueprint_context=bp)
            h, fail = sub.add_new_subobject(params)
            if not u.SubobjectDataBlueprintFunctionLibrary.is_handle_valid(h):
                raise RuntimeError('add_new_subobject failed: %s' % fail)
            sub.rename_subobject(h, u.Text(name))
            sub, comps = scs(bp)
        b = comps[name][1]
        sl = comps['LockSigil%d' % i][1].get_editor_property('relative_location')
        b.set_editor_property('static_mesh', cyl)
        b.set_editor_property('override_materials', [beam_mat])
        b.set_editor_property('relative_location', u.Vector(sl.x, sl.y, 1.2 + P['beam_height'] * 0.5))
        b.set_editor_property('relative_scale3d', u.Vector(P['beam_radius_scale'], P['beam_radius_scale'], P['beam_height'] / 100.0))
        b.set_editor_property('cast_shadow', False)
        b.set_editor_property('can_ever_affect_navigation', False)
        b.set_editor_property('translucency_sort_priority', 2)
        b.set_collision_profile_name('NoCollision')
        b.set_editor_property('generate_overlap_events', False)
    note('components updated', sorted(comps))


# ---------------------------------------------------------------- blueprint graph
def pins(n, direction=None):
    return [p for p in n.list_all_pins() if direction is None or p.get_pin_direction() == direction]


def pin(n, name, direction=u.EdGraphPinDirection.EGPD_INPUT):
    for p in pins(n, direction):
        if str(p.get_pin_name()) == name:
            return p
    raise RuntimeError('pin %s not on %s' % (name, n.get_name()))


def type_id(n):
    return ''.join(str(n.get_node_category()).split()) + '|' + ''.join(str(n.get_node_title()).split())


def fix_graph(bp):
    ge = u.BlueprintGraphEditor.get_graph_editor_by_name(bp, u.Name('PresenterTick'))
    nodes = list(ge.list_all_nodes())
    title = lambda n: str(n.get_node_title())
    # pulse speed: the float*float fed by GetGameTimeinSeconds whose result goes to Sin
    sin = [n for n in nodes if title(n).startswith('Sin')][0]
    mul = pin(sin, 'A').list_connected_pins()[0].get_owning_node()
    assert pin(mul, 'B').set_pin_value('%.4f' % P['pulse_speed'])
    pulse = [p.get_owning_node() for p in pin(sin, 'ReturnValue', u.EdGraphPinDirection.EGPD_OUTPUT).list_connected_pins()][0]
    assert 'MapRange' in title(pulse), title(pulse)
    assert pin(pulse, 'OutRangeA').set_pin_value('%.3f' % P['light_min'])
    assert pin(pulse, 'OutRangeB').set_pin_value('%.3f' % P['light_max'])
    sels = [p.get_owning_node() for p in pin(pulse, 'ReturnValue', u.EdGraphPinDirection.EGPD_OUTPUT).list_connected_pins()]
    for s in sels:
        assert pin(s, 'A').set_pin_value('%.3f' % P['light_released'])
    note('graph pulse: mul', mul.get_name(), 'maprange', pulse.get_name(), 'selects', len(sels))
    # beams share the sigil CPD call (extra Target link)
    getters = {}
    for n in nodes:
        t = title(n)
        for i in range(3):
            if t.replace(' ', '').endswith('LockSigil%d' % i) and pins(n, u.EdGraphPinDirection.EGPD_OUTPUT):
                getters.setdefault(i, []).append(n)
    for i in range(3):
        cpd_nodes = []
        for g in getters.get(i, []):
            for p in pins(g, u.EdGraphPinDirection.EGPD_OUTPUT):
                for q in p.list_connected_pins():
                    if 'CustomPrimitiveData' in title(q.get_owning_node()).replace(' ', ''):
                        cpd_nodes.append((q.get_owning_node(), q))
        assert cpd_nodes, 'no CPD node for sigil %d' % i
        cn, target = cpd_nodes[0]
        if any('LockBeam%d' % i in title(x.get_owning_node()).replace(' ', '') for x in target.list_connected_pins()):
            note('beam %d already linked' % i); continue
        made = ge.add_get_member_variable_node(u.Name('LockBeam%d' % i))
        if made:
            pos = cn.get_node_pos()
            made.set_node_pos(u.IntPoint(pos.x - 220, pos.y + 160)) if hasattr(made, 'set_node_pos') else None
        assert made, 'could not create getter for LockBeam%d' % i
        outp = pins(made, u.EdGraphPinDirection.EGPD_OUTPUT)[0]
        orig = list(target.list_connected_pins())
        ok = outp.try_create_connection(target)
        after = list(target.list_connected_pins())
        note('beam %d target links' % i, len(orig), '->', [title(x.get_owning_node()) for x in after], ok)
        if ok and len(after) == len(orig) + 1:
            continue
        # fallback: own SetCustomPrimitiveDataFloat call chained right after the sigil one
        for x in list(target.list_connected_pins()):
            if x not in orig: x.break_single_pin_link(target) if hasattr(x, 'break_single_pin_link') else None
        for o in orig:
            if o not in list(target.list_connected_pins()): assert o.try_create_connection(target)
        call = ge.add_call_function_node('/Script/Engine.PrimitiveComponent:SetCustomPrimitiveDataFloat')
        assert call, 'call node failed'
        assert outp.try_create_connection(pin(call, 'self'))
        assert pin(call, 'DataIndex').set_pin_value('0')
        vsrc = pin(cn, 'Value').list_connected_pins()
        assert vsrc and vsrc[0].try_create_connection(pin(call, 'Value'))
        then = pin(cn, 'then', u.EdGraphPinDirection.EGPD_OUTPUT)
        nxt = list(then.list_connected_pins())
        for q in nxt: then.break_single_pin_link(q)
        assert then.try_create_connection(pin(call, 'execute'))
        for q in nxt: assert pin(call, 'then', u.EdGraphPinDirection.EGPD_OUTPUT).try_create_connection(q)
        note('beam %d via own CPD call' % i)


def main():
    beam = build_beam()
    patch_sigil()
    build_ground()
    bp = u.load_asset(BPP)
    fix_components(bp, beam)
    u.BlueprintEditorLibrary.compile_blueprint(bp)
    fix_graph(bp)
    u.BlueprintEditorLibrary.compile_blueprint(bp)
    u.EditorAssetLibrary.save_loaded_asset(bp, False)
    note('blueprint compiled and saved')
    # read-only: post-process exposure in Stage3 for tuning notes
    try:
        u.get_editor_subsystem(u.LevelEditorSubsystem).load_level('/Game/Maps/Stage3')
        pp = []
        for a in u.get_editor_subsystem(u.EditorActorSubsystem).get_all_level_actors():
            if isinstance(a, u.PostProcessVolume):
                s = a.get_editor_property('settings')
                pp.append({k: str(s.get_editor_property(k)) for k in ['override_auto_exposure_method', 'auto_exposure_method', 'auto_exposure_bias',
                           'auto_exposure_min_brightness', 'auto_exposure_max_brightness', 'override_auto_exposure_bias']})
        LOG['postprocess'] = pp
    except Exception:
        LOG['errors'].append(traceback.format_exc())


try:
    main(); LOG['ok'] = True
except Exception:
    LOG['ok'] = False; LOG['errors'].append(traceback.format_exc())
open(OUTLOG, 'w', encoding='utf8').write(json.dumps(LOG, indent=1, ensure_ascii=False, default=str))
print('S3PFIX_DONE', LOG['ok'])
