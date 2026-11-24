"""Import the final Stage3 delivery into an isolated, reproducible Unreal package.

Run in UE Python after all producing chats have completed. The frozen delivery
manifest is copied to Saved/Stage3Integration20261125 before this script runs.
"""
import json
import os
import traceback
from pathlib import Path
import unreal as u

ROOT = Path(u.Paths.project_dir()).resolve()
OUT = ROOT / 'Saved/Stage3Integration20261125'
SRC = Path(os.environ.get('CATRUN_STAGE3_SOURCE', 'C:/Users/whghk/Desktop/CastleKit/Stage3/Production02_20261125'))
DEST = '/Game/Environment/Stage3/FinalGuard'
EA = u.EditorAssetLibrary
AT = u.AssetToolsHelpers.get_asset_tools()
ML = u.MaterialEditingLibrary
REPORT = {'meshes': {}, 'materials': {}, 'textures': {}, 'errors': []}
if (OUT/'import_report.json').exists():
    REPORT.update(json.loads((OUT/'import_report.json').read_text(encoding='utf8')))
    REPORT.setdefault('previous_attempt_errors',[]).extend(REPORT.get('errors',[]));REPORT['errors']=[];REPORT.pop('success',None)

def write():
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT/'import_report.json').write_text(json.dumps(REPORT, ensure_ascii=False, indent=2), encoding='utf8')

def imported(file, folder, name, options=None):
    path = folder+'/'+name
    if EA.does_asset_exist(path):
        return EA.load_asset(path)
    t = u.AssetImportTask()
    t.filename = str(file)
    t.destination_path = folder
    t.destination_name = name
    t.automated = True
    t.save = True
    t.replace_existing = False
    if options: t.options = options
    AT.import_asset_tasks([t])
    obj = EA.load_asset(path)
    assert obj, (str(file), t.imported_object_paths)
    return obj

def texture(file, name):
    obj = imported(file, DEST+'/Textures', name)
    base = name.endswith('BaseColor')
    normal = name.endswith('Normal_DX')
    obj.set_editor_property('srgb', base)
    if normal:
        obj.set_editor_property('compression_settings', u.TextureCompressionSettings.TC_NORMALMAP)
        obj.set_editor_property('flip_green_channel', False)
    elif not base:
        obj.set_editor_property('compression_settings', u.TextureCompressionSettings.TC_MASKS)
    EA.save_loaded_asset(obj)
    REPORT['textures'][name] = obj.get_path_name()
    return obj

def pbr(key, folder, prefix=''):
    name = 'M_S3_'+key
    path = DEST+'/Materials/'+name
    if EA.does_asset_exist(path):
        m = EA.load_asset(path)
    else:
        m = AT.create_asset(name, DEST+'/Materials', u.Material, u.MaterialFactoryNew())
        for suffix, prop in [('BaseColor', u.MaterialProperty.MP_BASE_COLOR), ('Normal_DX', u.MaterialProperty.MP_NORMAL), ('ORM', None)]:
            file = folder/(prefix+suffix+'.png')
            if not file.exists():
                raise RuntimeError('Missing texture '+str(file))
            tex = texture(file, 'T_S3_'+key+'_'+suffix)
            node = ML.create_material_expression(m, u.MaterialExpressionTextureSample, -600, len(REPORT['textures'])*30)
            node.texture = tex
            node.sampler_type = (u.MaterialSamplerType.SAMPLERTYPE_COLOR if suffix=='BaseColor' else
                                 u.MaterialSamplerType.SAMPLERTYPE_NORMAL if suffix=='Normal_DX' else u.MaterialSamplerType.SAMPLERTYPE_MASKS)
            if prop is not None: ML.connect_material_property(node, 'RGB', prop)
            else:
                for channel, p in [('R', u.MaterialProperty.MP_AMBIENT_OCCLUSION), ('G', u.MaterialProperty.MP_ROUGHNESS), ('B', u.MaterialProperty.MP_METALLIC)]:
                    ML.connect_material_property(node, channel, p)
        # Thin cloth and metal strips retain their authored silhouette from both sides.
        if 'cloth' in key or 'banner' in key or 'runner' in key: m.set_editor_property('two_sided', True)
        ML.recompile_material(m)
        EA.save_loaded_asset(m)
    REPORT['materials'][name] = m.get_path_name()
    return m

def main():
    frozen = OUT/'delivery_manifest.json'
    if not frozen.exists(): frozen = ROOT/'Docs/Design/Stage3/DeliveryManifest_20261125.json'
    manifest = json.loads(frozen.read_text(encoding='utf8'))
    for folder in sorted((SRC/'Shared/Textures').iterdir()):
        if folder.is_dir() and (folder/'BaseColor.png').exists(): pbr(folder.name, folder)
    for a in manifest['assets']:
        if not a.get('primary_fbx'): continue
        directory = SRC/a['directory']
        if a['key']=='D01': pbr('Guardian_FineLimestone',directory/'Textures','T_D01_Limestone_')
        if a.get('kind')=='runner': pbr(a['name'].removeprefix('SM_S3_'),directory/'Textures/woven_runner','woven_runner_')
        contract = directory/'texture_contract.json'
        if contract.exists():
            for key, settings in json.loads(contract.read_text()).items():
                if 'M_S3_'+key not in REPORT['materials']:
                    pbr(key, directory/settings['path'], key+'_')
        for rel in [a['primary_fbx']]+a.get('additional_fbx', []):
            file = SRC/rel
            options = u.FbxImportUI()
            options.set_editor_property('automated_import_should_detect_type', False)
            options.set_editor_property('mesh_type_to_import', u.FBXImportType.FBXIT_STATIC_MESH)
            options.set_editor_property('import_as_skeletal', False)
            options.set_editor_property('import_materials', False)
            options.set_editor_property('import_textures', False)
            data = options.static_mesh_import_data
            for key, value in {'combine_meshes':True, 'auto_generate_collision':False, 'convert_scene':True,
                               'convert_scene_unit':True, 'force_front_x_axis':False, 'generate_lightmap_u_vs':False,
                               'import_uniform_scale':1.0}.items(): data.set_editor_property(key,value)
            data.set_editor_property('normal_import_method', u.FBXNormalImportMethod.FBXNIM_IMPORT_NORMALS_AND_TANGENTS)
            mesh = imported(file, DEST+'/Meshes', file.stem, options)
            for index, slot in enumerate(mesh.get_editor_property('static_materials')):
                name = str(slot.material_slot_name).split('.')[0]
                path = REPORT['materials'].get(name)
                if not path:
                    raise RuntimeError('Unmapped material '+name+' on '+file.stem)
                mesh.set_material(index, EA.load_asset(path))
            mesh.set_editor_property('light_map_coordinate_index', 1)
            mesh.set_editor_property('light_map_resolution', 64)
            box = mesh.get_bounding_box()
            lo,hi = box.min,box.max
            # UE render geometry is the authoritative collision for apertures.
            # Imported UCX remains available for movable statues/doors.
            body = mesh.get_editor_property('body_setup')
            geometry=body.get_editor_property('agg_geom')
            convex=len(geometry.get_editor_property('convex_elems'))
            simple=sum(len(geometry.get_editor_property(k)) for k in ['box_elems','sphere_elems','sphyl_elems'])
            if convex+simple==0:
                body.set_editor_property('collision_trace_flag', u.CollisionTraceFlag.CTF_USE_COMPLEX_AS_SIMPLE)
            EA.save_loaded_asset(mesh)
            REPORT['meshes'][file.stem] = {'path':mesh.get_path_name(), 'source':rel, 'id':a['key'],
                'bounds':[[lo.x,lo.y,lo.z],[hi.x,hi.y,hi.z]],
                'materials':[str(s.material_slot_name) for s in mesh.static_materials],
                'convex':convex, 'simple':simple}
            write()
    animation_file=OUT/'Animation/AN_BlackCat_ReleaseRing.fbx'
    if not animation_file.exists():animation_file=ROOT/'SourceArt/Stage3/BlackCatInteraction/AN_BlackCat_ReleaseRing.fbx'
    if animation_file.exists():
        skeleton=EA.load_asset('/Game/Characters/BlackCat/Final/Meshes/SK_BlackCat_Final').get_editor_property('skeleton')
        options=u.FbxImportUI()
        for key,value in {'automated_import_should_detect_type':False,'import_mesh':False,'import_animations':True,
                'import_materials':False,'import_textures':False,'mesh_type_to_import':u.FBXImportType.FBXIT_ANIMATION,'skeleton':skeleton}.items():options.set_editor_property(key,value)
        data=options.anim_sequence_import_data
        for key,value in {'import_uniform_scale':1.,'convert_scene':True,'convert_scene_unit':True,'force_front_x_axis':False,'use_default_sample_rate':False,'custom_sample_rate':30}.items():data.set_editor_property(key,value)
        animation=imported(animation_file,DEST+'/Animations',animation_file.stem,options)
        animation.set_editor_property('enable_root_motion',False);EA.save_loaded_asset(animation)
        assert abs(animation.get_play_length()-2.4)<.001,animation.get_play_length()
        assert animation.get_editor_property('skeleton')==skeleton
        REPORT['animation']={'path':animation.get_path_name(),'seconds':animation.get_play_length(),'skeleton':skeleton.get_path_name()}
    REPORT['success'] = True
    write()
    print('STAGE3_IMPORT_OK', len(REPORT['meshes']))

if __name__ == '__main__':
    try: main()
    except Exception:
        REPORT['errors'].append(traceback.format_exc()); write(); raise
