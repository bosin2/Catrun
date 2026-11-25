"""Root-only representative saved-material GPU pillar/interaction acceptance.

Import is inert. Call main() in a disposable unattended -SaveToUserDir process
already on saved Stage3. No PIE, package save, asset/material reassignment, cat
actor movement or enemy changes. A transient SceneCapture and restored world
CatPosition MPC provide controlled alpha0/alpha1 comparisons. This is actual
GPU BaseColor coverage, not a final Lit beauty or gameplay-camera screenshot.
"""
import hashlib
import importlib.util
import json
import math
import os
import time
import traceback
from pathlib import Path

WIDTH, HEIGHT = 768, 432
ROTATION = (-55., -135., 0.)
OFFSET = (147.7898938366867, 147.78989383668707, 409.57602214449524)
MPC = '/Game/Characters/BlackCat/Materials/MPC_CatOcclusion'


def module(path, name):
    spec=importlib.util.spec_from_file_location(name,path)
    result=importlib.util.module_from_spec(spec);spec.loader.exec_module(result)
    return result


def xyz(v):
    return [float(v.x),float(v.y),float(v.z)]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def camera_basis():
    pitch,yaw=map(math.radians,ROTATION[:2])
    return ((math.cos(pitch)*math.cos(yaw),math.cos(pitch)*math.sin(yaw),math.sin(pitch)),
            (-math.sin(yaw),math.cos(yaw),0.),
            (-math.sin(pitch)*math.cos(yaw),-math.sin(pitch)*math.sin(yaw),math.cos(pitch)))


def measure(pixels):
    assert len(pixels)==WIDTH*HEIGHT,len(pixels)
    mask=set();total=[0.,0.,0.]
    for i,p in enumerate(pixels):
        rgb=(p.r,p.g,p.b)
        assert all(math.isfinite(v) and v>=0 for v in rgb)
        if max(rgb)>=1.e-6:mask.add(i)
        for k,v in enumerate(rgb):total[k]+=v
    return {'raw_nonblack_pixels':len(mask),'raw_black_pixels':len(pixels)-len(mask),
            'total_pixels':len(pixels),'raw_mean_linear':[v/len(pixels) for v in total]},mask


def main():
    import unreal as u
    root=Path(u.Paths.project_dir()).resolve()
    suffix=os.environ.get('CATRUN_GATE_HALL_GPU_PASS','01')
    assert suffix.replace('_','').isalnum()
    out=root/'Saved/Stage3GateHallRevision20261125'/('RuntimeQAGPU'+suffix)
    assert not out.exists(),'Preserve prior GPU evidence: '+str(out)
    out.mkdir(parents=True)
    old=module(root/'Scripts/Stage3/ReadabilityPushFix20261125/gpu_occlusion.py','gate_legacy_gpu_helpers')
    cpu=module(root/'Scripts/Stage3/ReadabilityPushFix20261125/test_occlusion.py','gate_cpu_ray_helpers')
    ed=u.get_editor_subsystem(u.UnrealEditorSubsystem)
    actor_api=u.get_editor_subsystem(u.EditorActorSubsystem)
    report={'success':False,'execution_complete':False,'save_count':0,'rows':[], 'cpu_all_pillars':[],
            'scope':__doc__,'resolution':[WIDTH,HEIGHT],'camera_rotation':list(ROTATION),'camera_offset_cm':list(OFFSET),
            'method':'Unmodified saved component(s) exclusively rendered to SCS_BASE_COLOR RGBA16F. CatPosition.a=0 visible control versus a=1 enabled cutaway. Raw linear nonblack coverage compared.',
            'limits':['Two pillar stacks receive foreground/background GPU comparisons; a third receives the extreme near-plane comparison. Remaining seven receive CPU/CPD consistency checks only.',
                      'Release3 Housing/Ring/Pin are representative pre-interaction materials. No actual interaction animation tested.',
                      'No baseline pixels means invalid/failure, never a transparent PASS.',
                      'Transient SceneCapture uses measured gameplay orientation, width900, 16:9, actual saved near-4000/far10000; final possessed-camera Lit review is separate.'],
            'compilation_barriers':[]}
    def persist():
        (out/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    original_mpc=collection=capture_actor=world=None
    protected={};original_paths=None;snapshots={};all_transforms={}
    try:
        assert u.SystemLibrary.is_unattended() and '-savetouserdir' in u.SystemLibrary.get_command_line().lower()
        assert not ed.get_game_world(),'No PIE; render saved editor components only'
        world=ed.get_editor_world()
        assert world.get_path_name()=='/Game/Maps/Stage3.Stage3','Root must load saved Stage3'
        actors=list(actor_api.get_all_level_actors())
        original_paths={a.get_path_name() for a in actors}
        all_transforms={a.get_path_name():a.get_actor_transform().export_text() for a in actors}
        labels={}
        for actor in actors:labels.setdefault(actor.get_actor_label(),[]).append(actor)
        def one(label):
            rows=labels.get(label,[]);assert len(rows)==1,(label,len(rows));return rows[0]
        files=[root/'Content/Maps'/(name+'.umap') for name in ('Stage1','Stage2','Stage3')]
        for folder in ('CameraReadability','InteractiveReadability'):
            files+=list((root/'Content/Environment/Stage3/GothicRevision_20261125'/folder).rglob('*.uasset'))
        protected={str(p):digest(p) for p in files if p.exists()}
        report['protected_hashes_before']=protected
        follow=one('S3_FollowCamera').get_component_by_class(u.CameraComponent)
        assert 'ORTHOGRAPHIC' in str(follow.get_editor_property('projection_mode'))
        assert abs(follow.get_editor_property('ortho_width')-900)<.01
        assert abs(follow.get_editor_property('aspect_ratio')-16/9)<.0001
        near=float(follow.get_editor_property('ortho_near_clip_plane'))
        far=float(follow.get_editor_property('ortho_far_clip_plane'))
        assert near==-4000. and far==10000.,'Run GPU acceptance after Stage3-only near-plane fix'
        assert not follow.get_editor_property('auto_calculate_ortho_planes') and not follow.get_editor_property('update_ortho_planes')
        report['saved_camera_near_far_cm']=[near,far]
        groups={}
        for label,rows in labels.items():
            if label.startswith('S3_GrandPillar_'):
                assert len(rows)==1
                groups.setdefault(label.rsplit('_',1)[0],[]).append(rows[0])
        assert len(groups)==10,len(groups)
        forward,right,up=camera_basis()
        numeric={}
        for stem,members in sorted(groups.items()):
            lo=[math.inf]*3;hi=[-math.inf]*3
            for a in members:
                center,extent=a.get_actor_bounds(False,False)
                for i,(c,e) in enumerate(zip(xyz(center),xyz(extent))):lo[i]=min(lo[i],c-e);hi[i]=max(hi[i],c+e)
            center=[(a+b)/2 for a,b in zip(lo,hi)];extent=[(b-a)/2 for a,b in zip(lo,hi)]
            assert abs(hi[2]-3450)<.1
            expected=center+[1.]+extent+[1.]
            for a in members:
                component=a.get_component_by_class(u.StaticMeshComponent)
                cp=list(component.get_editor_property('custom_primitive_data').get_editor_property('data'))
                assert len(cp)>=24 and max(abs(a-b) for a,b in zip(cp[16:24],expected))<.15,a.get_actor_label()
            poses={role:[center[0]+sign*125,center[1]+sign*125,26.2]
                   for role,sign in [('foreground',-1),('background',1)]}
            hits={role:cpu.hit_samples(cat,[cat[i]+OFFSET[i] for i in range(3)],forward,right,up,center,extent)
                  for role,cat in poses.items()}
            assert hits['foreground']>0 and hits['background']==0,(stem,hits)
            row={'group':stem,'members':len(members),'center':center,'extent':extent,'poses':poses,'nine_ray_hits':hits,
                 'kind':'CPU numeric plus actual saved CPD, NOT GPU','passed':True}
            report['cpu_all_pillars'].append(row);numeric[stem]=row
        cases=[]
        for stem in ('S3_GrandPillar_-670_2','S3_GrandPillar_GateExtR4'):
            for role in ('foreground','background'):
                cases.append({'name':stem+'_'+role,'actors':groups[stem],'cat':numeric[stem]['poses'][role],
                              'expected':'cut' if role=='foreground' else 'opaque','kind':'pillar_stack',
                              'numeric_hits':numeric[stem]['nine_ray_hits'][role]})
        extreme_cat=[-945.,-4545.,26.2]
        extreme_stem='S3_GrandPillar_270_2'
        extreme_hits=cpu.hit_samples(extreme_cat,[extreme_cat[i]+OFFSET[i] for i in range(3)],forward,right,up,
                                    numeric[extreme_stem]['center'],numeric[extreme_stem]['extent'])
        assert extreme_hits==0,'Extreme clipping specimen must remain opaque to isolate clip plane'
        cases.append({'name':'GateExtreme_near_plane_recovery','actors':groups[extreme_stem],
                      'cat':extreme_cat,'expected':'opaque','kind':'near_plane_regression',
                      'numeric_hits':extreme_hits,'compare_old_near':True})
        report['interactive_material_static_checks']=[]
        protected_labels=['S3_Release%d_%s'%(n,part) for n in (1,2,3) for part in ('Housing','Ring','Pin')]
        protected_labels+=['S3_FinalGate_'+part for part in ('LowerFrame','UpperFrame','Leaf_L','Leaf_R')]
        for label in protected_labels:
            comp=one(label).get_component_by_class(u.StaticMeshComponent);assert comp
            materials=[]
            for slot in range(comp.get_num_materials()):
                material=comp.get_material(slot)
                assert u.EditorAssetLibrary.get_metadata_tag(material,'Stage3InteractiveOwner'),label
                assert material.get_base_material().get_editor_property('blend_mode')==u.BlendMode.BLEND_OPAQUE,label
                overrides=material.get_editor_property('base_property_overrides')
                assert not overrides.get_editor_property('override_blend_mode') or overrides.get_editor_property('blend_mode')==u.BlendMode.BLEND_OPAQUE,label
                materials.append(material.get_path_name())
            assert materials,label
            report['interactive_material_static_checks'].append({'actor':label,'materials':materials,'passed':True,'GPU_tested_here':False})
        for part in ('Housing','Ring','Pin'):
            actor=one('S3_Release3_'+part)
            center,extent=actor.get_actor_bounds(False,False)
            c,e=xyz(center),xyz(extent)
            # Aim the central ray through this specific device at cat center
            # height26.2. This is an adversarial MATERIAL probe, not a claim
            # that a physical cat can stand at this synthetic MPC coordinate.
            dz=max(c[2]-26.2,10.)
            cat=[c[0]-dz*(-forward[0])/(-forward[2]),c[1]-dz*(-forward[1])/(-forward[2]),c[2]-dz]
            hits=cpu.hit_samples(cat,[cat[i]+OFFSET[i] for i in range(3)],forward,right,up,c,e)
            assert hits>0,'Device probe must challenge an occluding ray'
            comp=actor.get_component_by_class(u.StaticMeshComponent)
            for slot in range(comp.get_num_materials()):
                material=comp.get_material(slot)
                assert u.EditorAssetLibrary.get_metadata_tag(material,'Stage3InteractiveOwner'),actor.get_actor_label()
                assert material.get_base_material().get_editor_property('blend_mode')==u.BlendMode.BLEND_OPAQUE
            cases.append({'name':actor.get_actor_label()+'_opaque_challenge','actors':[actor],'cat':cat,
                          'expected':'opaque','kind':'interactive_synthetic_material_probe','numeric_hits':hits})
        for case in cases:
            for a in case['actors']:
                label=a.get_actor_label()
                snapshots[label]=old.snapshot_component(a,a.get_component_by_class(u.StaticMeshComponent))
        report['initial_component_snapshots']=snapshots
        collection=u.load_asset(MPC);assert collection
        original_mpc=u.MaterialLibrary.get_vector_parameter_value(world,collection,'CatPosition')
        capture_actor=actor_api.spawn_actor_from_class(u.SceneCapture2D,u.Vector(0,0,0),
                   u.Rotator(pitch=ROTATION[0],yaw=ROTATION[1],roll=ROTATION[2]),transient=True)
        assert capture_actor
        capture=capture_actor.get_component_by_class(u.SceneCaptureComponent2D)
        settings={'capture_every_frame':False,'capture_on_movement':False,
            'projection_type':u.CameraProjectionMode.ORTHOGRAPHIC,'ortho_width':900.,
            'auto_calculate_ortho_planes':False,'update_ortho_planes':False,
            'override_custom_near_clipping_plane':True,'custom_near_clipping_plane':near,
            'max_view_distance_override':far,'use_custom_projection_matrix':False,
            'capture_source':u.SceneCaptureSource.SCS_BASE_COLOR,
            'primitive_render_mode':u.SceneCapturePrimitiveRenderMode.PRM_USE_SHOW_ONLY_LIST}
        for name,value in settings.items():
            capture.set_editor_property(name,value);assert capture.get_editor_property(name)==value,name
        report['capture_settings_readback']={name:str(capture.get_editor_property(name)) for name in settings}
        target=u.RenderingLibrary.create_render_target2d(world,WIDTH,HEIGHT,u.TextureRenderTargetFormat.RTF_RGBA16F,u.LinearColor(0,0,0,0),False)
        capture.set_editor_property('texture_target',target)
        for case in cases:
            capture.clear_show_only_components()
            for actor in case['actors']:capture.show_only_component(actor.get_component_by_class(u.StaticMeshComponent))
            camera=[case['cat'][i]+OFFSET[i] for i in range(3)]
            capture_actor.set_actor_location(u.Vector(*camera),False,True)
            before=time.monotonic()
            u.SystemLibrary.execute_console_command(world,'Editor.AsyncAssetCompilationFinishAll')
            report['compilation_barriers'].append({'case':case['name'],'seconds':time.monotonic()-before,'returned':True})
            row={key:value for key,value in case.items() if key!='actors'}
            row.update(camera=camera,actors=[a.get_actor_label() for a in case['actors']])
            masks={}
            if case.get('compare_old_near'):
                capture.set_editor_property('custom_near_clipping_plane',-2000.)
                u.MaterialLibrary.set_vector_parameter_value(world,collection,'CatPosition',u.LinearColor(*case['cat'],0.))
                for _ in range(2):
                    capture.capture_scene()
                    pixels=u.RenderingLibrary.read_render_target_raw_pixel_area(world,target,0,0,WIDTH,HEIGHT,False)
                row['old_near_opaque_baseline'],masks['old_near']=measure(pixels)
                u.RenderingLibrary.export_render_target(world,target,str(out),case['name']+'_old_near_minus2000.hdr')
                capture.set_editor_property('custom_near_clipping_plane',near)
            for alpha,name in ((0.,'opaque_baseline'),(1.,'cutaway_enabled')):
                u.MaterialLibrary.set_vector_parameter_value(world,collection,'CatPosition',u.LinearColor(*case['cat'],alpha))
                value=u.MaterialLibrary.get_vector_parameter_value(world,collection,'CatPosition')
                assert max(abs(a-b) for a,b in zip(old.rgba(value),case['cat']+[alpha]))<.001
                for _ in range(2):
                    capture.capture_scene()
                    pixels=u.RenderingLibrary.read_render_target_raw_pixel_area(world,target,0,0,WIDTH,HEIGHT,False)
                row[name],masks[name]=measure(pixels)
                u.RenderingLibrary.export_render_target(world,target,str(out),case['name']+'_'+name+'.hdr')
            row.update(old.evaluate(row['opaque_baseline'],row['cutaway_enabled'],masks['opaque_baseline'],masks['cutaway_enabled'],case['expected']))
            if case.get('compare_old_near'):
                restored=len(masks['opaque_baseline']-masks['old_near'])
                lost=len(masks['old_near']-masks['opaque_baseline'])
                row['near_recovery']={'restored_pixels':restored,'unexpected_lost_pixels':lost,
                    'old_near':-2000.,'new_near':near,'passed':restored>=16 and lost<=max(4,int(len(masks['old_near'])*.005))}
                row['passed']=row['passed'] and row['near_recovery']['passed']
            report['rows'].append(row);persist()
            print('GATE_HALL_GPU',case['name'],row['opaque_baseline']['raw_nonblack_pixels'],row['cutaway_enabled']['raw_nonblack_pixels'],row['passed'])
        report['execution_complete']=True
        report['success']=len(report['rows'])==8 and all(row['passed'] for row in report['rows'])
    except Exception:
        report['error']=traceback.format_exc()
    finally:
        errors=[]
        if original_mpc is not None:
            try:
                u.MaterialLibrary.set_vector_parameter_value(world,collection,'CatPosition',original_mpc)
                value=u.MaterialLibrary.get_vector_parameter_value(world,collection,'CatPosition')
                report['mpc_restored']=max(abs(a-b) for a,b in zip(old.rgba(value),old.rgba(original_mpc)))<1.e-6
            except Exception:errors.append(traceback.format_exc())
        if capture_actor:
            try:actor_api.destroy_actor(capture_actor)
            except Exception:errors.append(traceback.format_exc())
        try:
            after=list(actor_api.get_all_level_actors());by_label={a.get_actor_label():a for a in after}
            report['actor_set_preserved']=original_paths=={a.get_path_name() for a in after}
            report['actor_transforms_preserved']=all_transforms=={a.get_path_name():a.get_actor_transform().export_text() for a in after}
            report['material_bindings_cpd_preserved']=all(old.snapshot_component(by_label[label],by_label[label].get_component_by_class(u.StaticMeshComponent))==saved
                                                        for label,saved in snapshots.items())
            report['protected_hashes_after']={p:digest(Path(p)) for p in protected}
            report['protected_files_preserved']=bool(protected) and protected==report['protected_hashes_after']
        except Exception:errors.append(traceback.format_exc())
        report['cleanup_errors']=errors
        report['success']=report['success'] and not errors and all(report.get(k,False) for k in
            ('mpc_restored','actor_set_preserved','actor_transforms_preserved','material_bindings_cpd_preserved','protected_files_preserved'))
        persist()
    assert report['success'],'GPU coverage failed or incomplete: '+str(out/'report.json')
    if os.environ.get('CATRUN_GATE_HALL_GPU_QUIT')=='1':u.SystemLibrary.execute_console_command(world,'QUIT_EDITOR')
    return report


if __name__=='__main__':
    main()
