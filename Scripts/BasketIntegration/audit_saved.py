"""Cold, read-only validation of the saved basket variants and map bindings."""
import unreal as u,json,traceback
from pathlib import Path
ROOT=Path(u.Paths.convert_relative_path_to_full(u.Paths.project_dir())).resolve()
OUT=ROOT/'Saved/BasketIntegration20261125';EA=u.EditorAssetLibrary
I=json.loads((OUT/'import_report.json').read_text());A=json.loads((OUT/'apply_report.json').read_text());R={'assets':{},'maps':{}}
def load(p):
    a=EA.load_asset(p);assert a,p;return a
def audit_map(name,data):
    level=u.get_editor_subsystem(u.LevelEditorSubsystem);actors=u.get_editor_subsystem(u.EditorActorSubsystem)
    assert level.load_level('/Game/Maps/'+name)
    baskets=[a for a in actors.get_all_level_actors() if isinstance(a,u.CatrunHideBasket)]
    assert len(baskets)==len(data['baskets']);rows=[]
    for basket in baskets:
        external=basket.get_editor_property('ExternalCloth')
        c=external or next(x for x in basket.get_components_by_class(u.SkeletalMeshComponent) if x.get_name()=='BasketCloth')
        assert c.skeletal_mesh_asset.get_path_name()==I['stages'][str(data['stage'])]['cloth']
        assert len(basket.get_editor_property('ClothEnterDirections'))==8
        assert len(basket.get_editor_property('ClothExitDirections'))==8
        assert basket.get_editor_property('ClothHiddenAnimation')
        rows.append({'actor':basket.get_actor_label(),'cloth':c.skeletal_mesh_asset.get_path_name(),'idle_asset':str(basket.get_editor_property('ClothIdleAnimation')),'anim_data':str(c.get_editor_property('animation_data')),'tick':str(c.get_editor_property('primary_component_tick'))})
    assert all('Stage3' not in str(c.get_editor_property('static_mesh')) for actor in actors.get_all_level_actors() for c in actor.get_components_by_class(u.StaticMeshComponent))
    return rows
try:
    for name,data in A['maps'].items():
        R['maps'][name]=audit_map(name,data)
    skeleton=None
    for stage,data in I['stages'].items():
        body=load(data['body']);cloth=load(data['cloth']);sk=cloth.get_editor_property('skeleton')
        if skeleton is None:skeleton=sk
        assert sk==skeleton
        geometry=body.get_editor_property('body_setup').get_editor_property('agg_geom')
        shapes={n:len(geometry.get_editor_property(n)) for n in ['convex_elems','box_elems','sphere_elems','sphyl_elems']}
        mats=[x.material_interface.get_path_name() for x in body.static_materials]
        assert all('BasketVariants20261125' in x for x in mats)
        R['assets'][stage]={'body':body.get_path_name(),'cloth':cloth.get_path_name(),'skeleton':sk.get_path_name(),'collision_shapes':shapes,'materials':mats}
    assert len(I['animations'])==18
    for name,data in I['animations'].items():
        clip=load(data['path']);assert clip.get_editor_property('skeleton')==skeleton
        assert abs(clip.get_play_length()-(1 if 'Idle' in name else 64/30))<.001
    for data in I['materials'].values():load(data)
    for data in I['textures'].values():load(data)
    assert all(sum(x['collision_shapes'].values())==5 for x in R['assets'].values()),R['assets']
    R['success']=True
except Exception:R['success']=False;R['error']=traceback.format_exc();u.log_error(R['error'])
(OUT/'cold_audit.json').write_text(json.dumps(R,indent=2,ensure_ascii=False),encoding='utf8')
