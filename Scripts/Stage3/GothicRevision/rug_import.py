"""Inert Rugs04 importer/placement; only root calls UE functions.

discover() is read-only. freeze(contract) runs outside UE (Pillow required).
main(freeze_path) imports new assets only. place(report, floor_offset_cm=.2)
places one NoCollision rug and hides only fully covered S3_Gothic_GateAxis
overlays; it never saves a map. Existing borders/thresholds remain untouched.

Producer JSON schema is deliberately not assumed. Root adapts the actual final
manifest/metadata into this explicit contract, after reviewing independent QA:
{
  "delivery_ready": true, "technical_qa_passed": true,
  "name": "<actual mesh name>", "fbx": "<relative FBX>",
  "blend": "<relative blend>", "metadata": "<relative metadata JSON>",
  "qa_evidence": ["<relative final QA report>"],
  "expected_sha256": {"<relative FBX>": "...", "<relative blend>": "..."},
  "bounds_cm": [[-150,-450,0],[150,450,0.6]], "pivot_cm": [0,0,0],
  "uv_channels": ["UV0", "UV1_Lightmap"], "collision_count": 0,
  "export_axes": "<actual producer export settings>",
  "slots": [{"name": "<actual ordered slot>", "role": "cloth|border|emblem",
             "textures": {"BaseColor": "...png", "Normal_DX": "...png", "ORM": "...png"}}]
}
Slots may be numerous; every actual slot needs an explicit role/texture mapping.
Color targets are yarn colors. All ORM metallic channels must be zero.
"""
import hashlib
import importlib.util
import json
import math
import re
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SOURCE = Path('C:/Users/whghk/Desktop/CastleKit/Stage3/Rugs04_20261125')
OUT = ROOT / 'Saved/Stage3GothicRevision20261125/RugImport'
DEST = '/Game/Environment/Stage3/GothicRevision_20261125'
OWNER = 'Stage3GrandGateRug20261125_v1'
LABEL = 'S3_GothicRug_GrandGate'
TARGETS = {'cloth': [73, 67, 74], 'border': [150, 134, 107], 'emblem': [150, 134, 107]}


def read(path): return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def write(path, data):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix('.tmp'); temp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding='utf8'); temp.replace(path)
def linear(value):
    x = value / 255.
    return x / 12.92 if x <= .04045 else ((x + .055) / 1.055) ** 2.4
def safe(root, relative):
    p = (root / relative).resolve()
    if not p.is_relative_to(root.resolve()): raise RuntimeError('Source path escapes rug folder: ' + str(relative))
    return p


def discover(source=SOURCE):
    """Inventory only; no files or UE assets written, no inferred readiness."""
    source = Path(source)
    files = sorted(p.relative_to(source).as_posix() for p in source.rglob('*') if p.is_file()) if source.exists() else []
    return {'source': str(source), 'exists': source.exists(), 'files': files,
            'fbx': [p for p in files if p.lower().endswith('.fbx')],
            'candidate_metadata': [p for p in files if p.lower().endswith('.json')],
            'ready_for_import': False,
            'next': 'Review actual final manifest, slot texture contract and independent QA; pass explicit contract to freeze().'}


def contract_from_delivery(source=SOURCE, *, delivery_ready=False, technical_qa_passed=False,
                           qa_evidence=None, role_map=None):
    """Adapter for the actual Rugs04 JSON observed on 2026-11-25.

    Defaults remain unready. Root passes True only after the producer's final
    handoff/QA is reviewed. Unexpected future schema or slots fail explicitly.
    """
    source=Path(source).resolve()
    candidates=list((source/'Assets').glob('*.asset.json'))
    if len(candidates)!=1:raise RuntimeError('Need exactly one actual Rugs04 asset metadata file')
    metadata=candidates[0];data=read(metadata);textures=read(source/'texture_contract.json')
    geometry=read(source/'QA/geometry_fbx.json')
    if not geometry['skill']['pass'] or geometry['skill']['errors']:
        raise RuntimeError('Current independent geometry QA has not passed')
    if data['collision']!='None; no UCX objects' or data['pivot']!='bottom-centre' or data['gate_axis']!='+Y':
        raise RuntimeError('Unexpected actual rug collision/pivot/axis metadata')
    if data['source']['materials']!=data['fbx_reimport']['materials']:
        raise RuntimeError('Producer FBX roundtrip material slots differ')
    by_name={row['name']:row for row in textures['materials']}
    role_map=role_map or {'M_S3_Rug_Cloth':'cloth','M_S3_Rug_Border':'border','M_S3_Rug_Emblem':'emblem'}
    fbx=metadata.with_name(data['name']+'.fbx').relative_to(source).as_posix()
    blend=metadata.with_name(data['name']+'.blend').relative_to(source).as_posix()
    expected={fbx:data['fbx_sha256'],blend:data['blend_sha256']}
    if geometry['fbx_sha256']!=expected[fbx] or geometry['blend_sha256']!=expected[blend]:
        raise RuntimeError('Independent geometry QA belongs to another source revision')
    slots=[]
    for name in data['source']['materials']:
        if name not in role_map:raise RuntimeError('Need explicit role for actual slot: '+name)
        row=by_name[name];maps={k:row['maps'][k] for k in ('BaseColor','Normal_DX','ORM')}
        expected.update({relative:row['sha256'][suffix] for suffix,relative in maps.items()})
        slots.append({'name':name,'role':role_map[name],'textures':maps})
    exporter=(source/'Scripts/build_rug.py').read_text(encoding='utf8')
    if not re.search(r'axis_forward\s*=\s*[\"\']-Y[\"\']',exporter) or not re.search(r'axis_up\s*=\s*[\"\']Z[\"\']',exporter) or 'FBX_SCALE_UNITS' not in exporter:
        raise RuntimeError('Producer exporter changed; review axes before adapting')
    evidence=list(qa_evidence or ['QA/geometry_fbx.json','QA/PBR_channels.json'])
    return {'delivery_ready':delivery_ready,'technical_qa_passed':technical_qa_passed,
        'name':data['name'],'fbx':fbx,'blend':blend,'metadata':metadata.relative_to(source).as_posix(),
        'qa_evidence':evidence,'extra_evidence':['texture_contract.json','Scripts/build_rug.py'],
        'expected_sha256':expected,'bounds_cm':[[v*100 for v in row] for row in data['source']['bounds_m']],
        'pivot_cm':[v*100 for v in data['source']['origin_m']],'uv_channels':data['source']['uv_layers'],
        'collision_count':0,'export_axes':'Blender -Y forward / Z up; FBX_SCALE_UNITS; Scripts/build_rug.py',
        'slots':slots}


def verify(frozen):
    root = Path(frozen['source'])
    for relative, expected in frozen['files'].items():
        p = safe(root, relative)
        if not p.is_file() or sha(p) != expected:
            raise RuntimeError('Frozen rug input drift: ' + relative)
    return True


def freeze(contract, source=SOURCE, out=OUT):
    """Require reviewed final inputs; reject unready delivery before any import."""
    from PIL import Image
    contract = read(contract) if isinstance(contract, (str, Path)) else json.loads(json.dumps(contract))
    source, out = Path(source).resolve(), Path(out)
    if contract.get('delivery_ready') is not True or contract.get('technical_qa_passed') is not True:
        raise RuntimeError('Delivery and independent technical QA are not ready')
    if not re.fullmatch(r'SM_[A-Za-z0-9_]+', contract['name']): raise RuntimeError('Invalid mesh name')
    lo, hi = contract['bounds_cm']; size = [b-a for a,b in zip(lo,hi)]
    if any(abs(v-t) > .02 for v,t in zip(lo,[-150,-450,0])) or abs(size[0]-300) > .02 or abs(size[1]-900) > .02 or not .49 <= size[2] <= .81:
        raise RuntimeError('Source rug is not bottom-centered 300x900x0.5-0.8 cm')
    if max(abs(v) for v in contract['pivot_cm']) > .001 or contract['collision_count'] != 0:
        raise RuntimeError('Rug pivot/collision contract failed')
    if len(contract['uv_channels']) < 2 or not contract.get('export_axes') or not contract.get('qa_evidence'):
        raise RuntimeError('Need explicit UV0/UV1, exporter axes and final QA evidence')
    slots = contract['slots']
    if not slots or len({s['name'] for s in slots}) != len(slots): raise RuntimeError('Empty or duplicate material slots')
    frozen = {'success': False, 'source': str(source), 'contract': contract, 'files': {}, 'materials': []}
    paths = [contract[k] for k in ('fbx','blend','metadata')] + contract['qa_evidence'] + contract.get('extra_evidence',[])
    if (source/'BRIEF.md').exists(): paths.append('BRIEF.md')
    for slot in slots:
        if slot['role'] not in TARGETS: raise RuntimeError('Unknown slot role: ' + slot['role'])
        for suffix in ('BaseColor','Normal_DX','ORM'): paths.append(slot['textures'][suffix])
    for relative in sorted(set(paths)):
        frozen['files'][relative] = sha(safe(source, relative))
    for key in ('fbx','blend'):
        relative = contract[key]
        if frozen['files'][relative] != contract['expected_sha256'].get(relative):
            raise RuntimeError('Missing/stale producer hash: ' + relative)
    for relative, expected in contract['expected_sha256'].items():
        if relative in frozen['files'] and frozen['files'][relative]!=expected:
            raise RuntimeError('Stale producer texture/evidence hash: '+relative)
    for slot in slots:
        with Image.open(safe(source, slot['textures']['BaseColor'])) as image:
            rgb = image.convert('RGB'); hist = rgb.histogram(); count = rgb.width*rgb.height
            mean = [sum(hist[c*256+i]*linear(i) for i in range(256))/count for c in range(3)]
        if min(mean) <= 1e-8: raise RuntimeError('Zero BaseColor normalization mean')
        with Image.open(safe(source, slot['textures']['ORM'])) as image:
            metallic = image.convert('RGB').getchannel('B').getextrema()
        if metallic != (0,0): raise RuntimeError('Rug is textile; nonzero metallic ORM: ' + slot['name'])
        frozen['materials'].append(dict(slot, target_srgb8=TARGETS[slot['role']],
            color_tint=[linear(x) for x in TARGETS[slot['role']]], source_mean_linear=mean,
            normalization=[1/x for x in mean], brightness=1., metallic_extrema=metallic))
    verify(frozen)
    frozen['input_sha256'] = hashlib.sha256(json.dumps({'files':frozen['files'],'contract':contract,'targets':TARGETS,'owner':OWNER},sort_keys=True).encode()).hexdigest()
    frozen['success'] = True
    path = out / ('freeze_'+frozen['input_sha256']+'.json')
    if not path.exists(): write(path,frozen)
    write(out/'latest_freeze.json',{'freeze_path':str(path),'input_sha256':frozen['input_sha256']})
    return {'freeze_path':str(path),'input_sha256':frozen['input_sha256'],'slots':len(slots)}


def main(freeze_path=None, out=OUT):
    """Import only. A new source revision always gets a new isolated folder."""
    out = Path(out)
    frozen = read(freeze_path or read(out/'latest_freeze.json')['freeze_path'])
    if not frozen.get('success'): raise RuntimeError('No successful reviewed rug freeze')
    verify(frozen)
    import unreal as u
    ea, ml, at = u.EditorAssetLibrary, u.MaterialEditingLibrary, u.AssetToolsHelpers.get_asset_tools()
    digest = frozen['input_sha256']; destination = DEST+'/Rug_'+digest[:16]
    report = {'success':False,'input_sha256':digest,'source':frozen['source'],'destination':destination,
              'textures':{},'materials':{},'mesh':{},'errors':[],'map_modified':False,
              'source_qa':frozen['contract']['qa_evidence'],'source_export_axes':frozen['contract']['export_axes']}
    def save(obj):
        if not ea.save_loaded_asset(obj): raise RuntimeError('Asset save failed: '+obj.get_path_name())
    def tag(obj):
        ea.set_metadata_tag(obj,'GothicRugOwner',OWNER); ea.set_metadata_tag(obj,'GothicRugInputHash',digest)
    def owned(path,cls):
        if not ea.does_asset_exist(path): return None
        obj=ea.load_asset(path)
        if not isinstance(obj,cls) or ea.get_metadata_tag(obj,'GothicRugOwner')!=OWNER or ea.get_metadata_tag(obj,'GothicRugInputHash')!=digest:
            raise RuntimeError('Refusing unknown existing asset: '+path)
        return obj
    def import_file(relative,folder,name,cls,options=None):
        path=folder+'/'+name; obj=owned(path,cls)
        if obj: return obj
        source=safe(Path(frozen['source']),relative)
        if sha(source)!=frozen['files'][relative]: raise RuntimeError('Source drift before import: '+relative)
        task=u.AssetImportTask();task.filename=str(source);task.destination_path=folder;task.destination_name=name
        task.automated=True;task.save=False;task.replace_existing=False
        if options is not None: task.options=options;task.factory=u.FbxFactory()
        at.import_asset_tasks([task]);obj=ea.load_asset(path)
        if not isinstance(obj,cls): raise RuntimeError('Import failed: '+str((relative,list(task.imported_object_paths))))
        tag(obj);save(obj);return obj
    try:
        instances={}
        for index,cal in enumerate(frozen['materials']):
            key='Slot%02d_%s'%(index,re.sub('[^A-Za-z0-9_]','_',cal['name']))
            textures={}
            for suffix,relative in cal['textures'].items():
                if suffix not in ('BaseColor','Normal_DX','ORM'): continue
                tex=import_file(relative,destination+'/Textures','T_Rug_'+key+'_'+suffix,u.Texture2D)
                tex.set_editor_property('srgb',suffix=='BaseColor')
                tex.set_editor_property('address_x',u.TextureAddress.TA_WRAP)
                tex.set_editor_property('address_y',u.TextureAddress.TA_WRAP)
                tex.set_editor_property('compression_settings',u.TextureCompressionSettings.TC_NORMALMAP if suffix=='Normal_DX' else u.TextureCompressionSettings.TC_MASKS if suffix=='ORM' else u.TextureCompressionSettings.TC_DEFAULT)
                if suffix=='Normal_DX': tex.set_editor_property('flip_green_channel',False)
                save(tex);textures[suffix]=tex
                report['textures'][key+'_'+suffix]={'path':tex.get_path_name(),'srgb':tex.get_editor_property('srgb'),'compression':str(tex.get_editor_property('compression_settings'))}
            name='M_Rug_'+key;parent=owned(destination+'/Parents/'+name,u.Material)
            if not parent:
                parent=at.create_asset(name,destination+'/Parents',u.Material,u.MaterialFactoryNew());tag(parent)
                samples={}
                for i,suffix in enumerate(('BaseColor','Normal_DX','ORM')):
                    node=ml.create_material_expression(parent,u.MaterialExpressionTextureSample,-900,i*220)
                    node.texture=textures[suffix]
                    node.sampler_type=u.MaterialSamplerType.SAMPLERTYPE_COLOR if suffix=='BaseColor' else u.MaterialSamplerType.SAMPLERTYPE_NORMAL if suffix=='Normal_DX' else u.MaterialSamplerType.SAMPLERTYPE_MASKS
                    samples[suffix]=node
                assert ml.connect_material_property(samples['Normal_DX'],'RGB',u.MaterialProperty.MP_NORMAL)
                for channel,prop in [('R',u.MaterialProperty.MP_AMBIENT_OCCLUSION),('G',u.MaterialProperty.MP_ROUGHNESS),('B',u.MaterialProperty.MP_METALLIC)]:
                    assert ml.connect_material_property(samples['ORM'],channel,prop)
                norm=ml.create_material_expression(parent,u.MaterialExpressionConstant3Vector,-900,-220)
                norm.set_editor_property('constant',u.LinearColor(*cal['normalization'],1))
                tint=ml.create_material_expression(parent,u.MaterialExpressionVectorParameter,-600,-220)
                tint.set_editor_property('parameter_name','ColorTint');tint.set_editor_property('default_value',u.LinearColor(*cal['color_tint'],1))
                bright=ml.create_material_expression(parent,u.MaterialExpressionScalarParameter,-300,-220)
                bright.set_editor_property('parameter_name','Brightness');bright.set_editor_property('default_value',1.)
                for node in (tint,bright):node.set_editor_property('group','Stage3 Rug Color')
                previous,output=samples['BaseColor'],'RGB'
                for i,(node,channel) in enumerate(((norm,''),(tint,'RGB'),(bright,''))):
                    multiply=ml.create_material_expression(parent,u.MaterialExpressionMultiply,-600+300*i,0)
                    assert ml.connect_material_expressions(previous,output,multiply,'A')
                    assert ml.connect_material_expressions(node,channel,multiply,'B')
                    previous,output=multiply,''
                assert ml.connect_material_property(previous,'',u.MaterialProperty.MP_BASE_COLOR)
                ml.recompile_material(parent);save(parent)
            name='MI_Rug_'+key;mi=owned(destination+'/Instances/'+name,u.MaterialInstanceConstant)
            if not mi:mi=at.create_asset(name,destination+'/Instances',u.MaterialInstanceConstant,u.MaterialInstanceConstantFactoryNew());tag(mi)
            ml.set_material_instance_parent(mi,parent)
            ml.set_material_instance_vector_parameter_value(mi,'ColorTint',u.LinearColor(*cal['color_tint'],1))
            ml.set_material_instance_scalar_parameter_value(mi,'Brightness',1.)
            color=ml.get_material_instance_vector_parameter_value(mi,'ColorTint')
            assert max(abs(a-b) for a,b in zip((color.r,color.g,color.b),cal['color_tint']))<1e-6
            assert abs(ml.get_material_instance_scalar_parameter_value(mi,'Brightness')-1)<1e-6
            ml.update_material_instance(mi);save(mi);instances[cal['name']]=mi
            report['materials'][cal['name']]=dict(cal,parent=parent.get_path_name(),instance=mi.get_path_name(),
                formula='BaseColor_linear / mean(BaseColor_linear) * ColorTint_linear * Brightness')
        options=u.FbxImportUI()
        for key,value in {'automated_import_should_detect_type':False,'mesh_type_to_import':u.FBXImportType.FBXIT_STATIC_MESH,'import_as_skeletal':False,'import_materials':False,'import_textures':False,'import_animations':False}.items():options.set_editor_property(key,value)
        for key,value in {'combine_meshes':True,'auto_generate_collision':False,'convert_scene':True,'convert_scene_unit':True,'force_front_x_axis':False,'generate_lightmap_u_vs':False,'import_uniform_scale':1.,'normal_import_method':u.FBXNormalImportMethod.FBXNIM_IMPORT_NORMALS_AND_TANGENTS}.items():options.static_mesh_import_data.set_editor_property(key,value)
        contract=frozen['contract'];mesh=import_file(contract['fbx'],destination+'/Meshes',contract['name'],u.StaticMesh,options)
        slots=mesh.get_editor_property('static_materials');names=[str(s.material_slot_name).split('.')[0] for s in slots]
        if names!=[s['name'] for s in contract['slots']]:raise RuntimeError('Imported slot order does not match final metadata: '+str(names))
        for index,name in enumerate(names):mesh.set_material(index,instances[name])
        mesh.set_editor_property('light_map_coordinate_index',1);mesh.set_editor_property('light_map_resolution',128)
        # This module's subsystem is not instantiated in Python commandlets;
        # the read-only UFUNCTION uses no subsystem state (UE5.8 source audited).
        mesh_editor=u.get_editor_subsystem(u.StaticMeshEditorSubsystem) or u.get_default_object(u.StaticMeshEditorSubsystem)
        uv=mesh_editor.get_num_uv_channels(mesh,0)
        if uv<2:raise RuntimeError('Imported UV1 missing')
        box=mesh.get_bounding_box();lo=[box.min.x,box.min.y,box.min.z];hi=[box.max.x,box.max.y,box.max.z];dims=[b-a for a,b in zip(lo,hi)]
        if max(abs(lo[0]+hi[0]),abs(lo[1]+hi[1]),abs(lo[2]))>.05 or not .49<=dims[2]<=.81:raise RuntimeError('Imported bottom-center/thickness mismatch')
        if abs(dims[0]-300)<.05 and abs(dims[1]-900)<.05:yaw=0
        elif abs(dims[0]-900)<.05 and abs(dims[1]-300)<.05:yaw=90
        else:raise RuntimeError('Imported rug dimensions mismatch: '+str(dims))
        body=mesh.get_editor_property('body_setup');counts={}
        if body:
            geom=body.get_editor_property('agg_geom');counts={k:len(geom.get_editor_property(k)) for k in ('convex_elems','box_elems','sphere_elems','sphyl_elems')}
        if sum(counts.values()):raise RuntimeError('Rug unexpectedly contains collision primitives')
        save(mesh);verify(frozen)
        report['mesh']={'path':mesh.get_path_name(),'bounds_cm':[lo,hi],'dimensions_cm':dims,'placement_yaw':yaw,'uv_channels':uv,'slots':names,'collision_counts':counts,
                        'orientation_note':'Long axis aligned with world Y from imported dimensions; sign cannot be inferred from symmetric bounds.'}
        report['success']=True;return report
    except Exception:
        report['errors'].append(traceback.format_exc());raise
    finally:
        write(out/('import_report_'+digest+'.json'),report);write(OUT.parent/'rug_import_report.json',report)


def layout_placement():
    """Read the current plan without depending on a cached editor layout module."""
    spec=importlib.util.spec_from_file_location('stage3_rug_layout',ROOT/'Scripts/Stage3/layout.py')
    layout=importlib.util.module_from_spec(spec);spec.loader.exec_module(layout)
    x0,y0,x1,y1=layout.ROOMS['GateHall']
    center=((x0+x1)/2,(y0+y1)/2-50)
    footprint=[[center[0]-150,center[1]-450],[center[0]+150,center[1]+450]]
    if not (x0<=footprint[0][0]<footprint[1][0]<=x1 and y0<=footprint[0][1]<footprint[1][1]<=y1):
        raise RuntimeError('The 300x900 cm rug does not fit the current GateHall')
    return center,footprint


def place(import_report=None, floor_offset_cm=.2):
    """Root placement only; no level save and no material or source changes."""
    import unreal as u
    if not 0<floor_offset_cm<=.5:raise RuntimeError('Use a small positive floor offset in (0,0.5] cm')
    report=import_report or read(OUT.parent/'rug_import_report.json')
    if not report.get('success'):raise RuntimeError('Successful rug import required')
    (rug_x,rug_y),footprint=layout_placement()
    (rug_x0,rug_y0),(rug_x1,rug_y1)=footprint
    world=u.get_editor_subsystem(u.UnrealEditorSubsystem).get_editor_world()
    if world.get_path_name()!='/Game/Maps/Stage3.Stage3':raise RuntimeError('Load Stage3 explicitly')
    ea,act=u.EditorAssetLibrary,u.get_editor_subsystem(u.EditorActorSubsystem)
    mesh=ea.load_asset(report['mesh']['path'])
    if not mesh or ea.get_metadata_tag(mesh,'GothicRugOwner')!=OWNER or ea.get_metadata_tag(mesh,'GothicRugInputHash')!=report['input_sha256']:
        raise RuntimeError('Unowned or mismatched rug mesh')
    current=mesh.get_bounding_box()
    actual=[[current.min.x,current.min.y,current.min.z],[current.max.x,current.max.y,current.max.z]]
    if max(abs(actual[r][i]-report['mesh']['bounds_cm'][r][i]) for r in range(2) for i in range(3))>.05:
        raise RuntimeError('Rug mesh bounds changed after import validation')
    actors={a.get_actor_label():a for a in act.get_all_level_actors()}
    reflected=any('Stage3ReferenceOrientationYMinus20261125' in map(str,a.tags) for a in actors.values())
    placement_yaw=report['mesh']['placement_yaw']
    if reflected:
        rug_y=-rug_y
        rug_y0,rug_y1=-rug_y1,-rug_y0
        footprint=[[rug_x0,rug_y0],[rug_x1,rug_y1]]
        placement_yaw=-placement_yaw
    axis=[]
    for label,actor in actors.items():
        if not re.fullmatch(r'S3_Gothic_GateAxis\d+',label):continue
        center,extent=actor.get_actor_bounds(False);lo=center-extent;hi=center+extent
        if lo.x>=rug_x0-.05 and hi.x<=rug_x1+.05 and lo.y>=rug_y0-.05 and hi.y<=rug_y1+.05:
            axis.append(actor)
    old=actors.get(LABEL)
    if old and OWNER not in [str(t) for t in old.tags]:raise RuntimeError('Refusing unowned rug actor')
    if old:actor=old
    else:
        actor=act.spawn_actor_from_class(u.StaticMeshActor,u.Vector(rug_x,rug_y,floor_offset_cm),u.Rotator(yaw=placement_yaw))
        if not actor:raise RuntimeError('Could not spawn rug actor')
    actor.set_actor_label(LABEL);actor.tags=[u.Name(OWNER)];actor.set_folder_path('Stage3/GothicRevision/Rug')
    comp=actor.static_mesh_component;comp.set_mobility(u.ComponentMobility.MOVABLE);comp.set_static_mesh(mesh)
    comp.set_editor_property('override_materials',[])
    comp.set_collision_enabled(u.CollisionEnabled.NO_COLLISION);comp.set_collision_response_to_all_channels(u.CollisionResponseType.ECR_IGNORE)
    comp.set_editor_property('can_ever_affect_navigation',False)
    actor.set_actor_location(u.Vector(rug_x,rug_y,floor_offset_cm),False,True)
    actor.set_actor_rotation(u.Rotator(yaw=placement_yaw),False);actor.set_actor_scale3d(u.Vector(1,-1 if reflected else 1,1))
    # Editor reconstruction during transforms can restore BlockAll unless the
    # final profile is also explicit, so validate after every transform.
    comp.set_collision_profile_name('NoCollision')
    comp.set_collision_enabled(u.CollisionEnabled.NO_COLLISION)
    assert comp.get_collision_enabled()==u.CollisionEnabled.NO_COLLISION
    assert str(comp.get_collision_profile_name())=='NoCollision'
    center,extent=actor.get_actor_bounds(False);minimum,maximum=center-extent,center+extent
    bounds=[[minimum.x,minimum.y,minimum.z],[maximum.x,maximum.y,maximum.z]]
    expected=[[rug_x0,rug_y0,floor_offset_cm],[rug_x1,rug_y1,floor_offset_cm+report['mesh']['dimensions_cm'][2]]]
    if max(abs(bounds[r][i]-expected[r][i]) for r in range(2) for i in range(3))>.05:
        raise RuntimeError('Placed rug world bounds mismatch; overlays left visible')
    hidden=[]
    for overlay in axis:
        c=overlay.get_component_by_class(u.StaticMeshComponent)
        c.set_visibility(False,False);c.set_hidden_in_game(True,False);c.set_cast_shadow(False)
        hidden.append(overlay.get_actor_label())
    result={'success':True,'actor':LABEL,'mesh':mesh.get_path_name(),'location':[rug_x,rug_y,floor_offset_cm],
            'world_footprint_cm':footprint,'hidden_gate_axis_overlays':hidden,
            'verified_world_bounds_cm':bounds,
            'collision':'NoCollision','map_saved':False,'borders_and_thresholds_changed':False}
    write(OUT.parent/'rug_placement_report.json',result);return result


if __name__=='__main__':
    print(json.dumps(discover(),indent=2))
