"""Fresh Stage3 materials; root calls build(folder). No source copies or saves."""
import unreal as u

DURATION = .78
RUMBLE_DURATION = .26
STRENGTH = .00055


def build(folder):
    lib = u.MaterialEditingLibrary
    at = u.AssetToolsHelpers.get_asset_tools()

    def make(name):
        path = folder + '/' + name
        assert not u.EditorAssetLibrary.does_asset_exist(path), path
        material = at.create_asset(name, folder, u.Material, u.MaterialFactoryNew())
        assert material
        return material

    def expr(material, cls, **props):
        result = lib.create_material_expression(material, cls, 0, 0)
        for key, value in props.items():
            result.set_editor_property(key, value)
        return result

    def custom(material, code, names, kind):
        inputs = []
        for name in names:
            item = u.CustomInput()
            item.set_editor_property('input_name', name)
            inputs.append(item)
        return expr(material, u.MaterialExpressionCustom, code=code,
                    inputs=inputs, output_type=kind)

    def wire(a, ap, b, bp):
        assert lib.connect_material_expressions(a, ap, b, bp)

    dust = make('M_S3GateImpactDust')
    dust.set_editor_property('blend_mode', u.BlendMode.BLEND_TRANSLUCENT)
    dust.set_editor_property('shading_model', u.MaterialShadingModel.MSM_UNLIT)
    dust.set_editor_property('two_sided', True)
    uv = expr(dust, u.MaterialExpressionTextureCoordinate)
    time = expr(dust, u.MaterialExpressionTime)
    start = expr(dust, u.MaterialExpressionScalarParameter,
                 parameter_name='StartTime', default_value=-100.)
    pos = expr(dust, u.MaterialExpressionObjectPositionWS)
    opacity = custom(dust, '''float age=max(0.,T-S); float life=saturate(age/0.78);
float seed=frac(P.x*0.017+P.y*0.029); float2 p=(UV-.5)*2.;
float noise=.8+.2*sin(p.x*9.+seed*17.+life*3.)*sin(p.y*8.-life*4.);
float edge=pow(saturate(1.-dot(p,p)),1.7);
return edge*noise*saturate(age/.045)*(1.-life)*(1.-life)*.38*step(age,0.78);''',
                     ['UV', 'T', 'S', 'P'], u.CustomMaterialOutputType.CMOT_FLOAT1)
    for a, ap, dest in ((uv, '', 'UV'), (time, '', 'T'), (start, '', 'S'), (pos, '', 'P')):
        wire(a, ap, opacity, dest)
    rise = custom(dust, '''float life=saturate(max(0.,T-S)/0.78);
float seed=frac(P.x*.017+P.y*.029);
return float3(sin(seed*19.)*life*15.,cos(seed*13.)*life*9.,life*25.);''',
                  ['T', 'S', 'P'], u.CustomMaterialOutputType.CMOT_FLOAT3)
    for a, dest in ((time, 'T'), (start, 'S'), (pos, 'P')):
        wire(a, '', rise, dest)
    color = expr(dust, u.MaterialExpressionConstant3Vector,
                 constant=u.LinearColor(.36, .32, .27, 1))
    for node, prop in ((color, u.MaterialProperty.MP_EMISSIVE_COLOR),
                       (opacity, u.MaterialProperty.MP_OPACITY),
                       (rise, u.MaterialProperty.MP_WORLD_POSITION_OFFSET)):
        assert lib.connect_material_property(node, '', prop)

    rumble = make('M_S3GateImpactRumble')
    rumble.set_editor_property('material_domain', u.MaterialDomain.MD_POST_PROCESS)
    rumble.set_editor_property('blendable_location', u.BlendableLocation.BL_SCENE_COLOR_AFTER_TONEMAPPING)
    uv = expr(rumble, u.MaterialExpressionScreenPosition)
    time = expr(rumble, u.MaterialExpressionTime)
    strength = expr(rumble, u.MaterialExpressionScalarParameter,
                    parameter_name='Rumble', default_value=0.)
    offset = custom(rumble, 'return UV + float2(sin(T*57.0),cos(T*71.0))*R;',
                    ['UV', 'T', 'R'], u.CustomMaterialOutputType.CMOT_FLOAT2)
    wire(uv, 'ViewportUV', offset, 'UV')
    wire(time, '', offset, 'T')
    wire(strength, '', offset, 'R')
    scene = expr(rumble, u.MaterialExpressionSceneTexture,
                 scene_texture_id=u.SceneTextureId.PPI_POST_PROCESS_INPUT0)
    wire(offset, '', scene, 'UVs')
    assert lib.connect_material_property(scene, 'Color', u.MaterialProperty.MP_EMISSIVE_COLOR)
    for material in (dust, rumble):
        lib.layout_material_expressions(material)
        lib.recompile_material(material)
    return dust, rumble
