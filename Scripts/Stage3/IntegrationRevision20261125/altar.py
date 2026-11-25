"""Approved B1 altar edit. Import is inert; root alone calls apply and saves.

The user's approval covers six wall runs, E3 +50cm canonicalY and the four
patrol points. Old actors remain recoverable and hidden; no source asset edits.
"""
import json
from pathlib import Path
import unreal as u

OWNER='Stage3ApprovedAltar20261125'
# Same union as the tested boxes; abutting corners avoid overlapping top faces.
BOXES=[('UpperLeft',(110,2375,140,2550)),('UpperRight',(610,2375,640,2550)),
       ('LowerLeftVertical',(110,2100,140,2250)),('LowerLeftHorizontal',(140,2100,260,2130)),
       ('LowerRightVertical',(610,2100,640,2250)),('LowerRightHorizontal',(490,2100,610,2130))]
PATROL=[(550,2190),(550,2380),(200,2380),(200,2190)]

def vec(v): return [v.x,v.y,v.z]

def bounds(actor):
    c,e=actor.get_actor_bounds(False,False)
    return [vec(c-e),vec(c+e)]

def apply():
    root=Path(u.Paths.project_dir()).resolve()
    ed=u.get_editor_subsystem(u.UnrealEditorSubsystem)
    actors=u.get_editor_subsystem(u.EditorActorSubsystem)
    assert not ed.get_game_world()
    assert ed.get_editor_world().get_path_name()=='/Game/Maps/Stage3.Stage3'
    lookup={a.get_actor_label():a for a in actors.get_all_level_actors()}
    assert not any(OWNER in map(str,a.tags) for a in lookup.values()),'Altar already applied'
    source=lookup['S3_Wall_0127'].static_mesh_component
    mesh=source.static_mesh
    mats=[source.get_material(i) for i in range(source.get_num_materials())]
    groups=json.loads((root/'Saved/Stage3GothicRevision20261125/occlusion_report.json').read_text(encoding='utf8'))['groups']
    retired=set()
    for label in ('S3_Wall_0126','S3_Wall_0127'):
        retired.add(label); retired.update(groups[label]['members'])
    report={'approved':True,'packages_saved':False,'retired':[],'walls':[],
            'device_moved':[],'patrol':PATROL,'room_outer_cm':[1000,600]}
    for label in sorted(retired):
        actor=lookup[label]
        actor.set_actor_enable_collision(False)
        actor.set_actor_hidden_in_game(True)
        for component in actor.get_components_by_class(u.PrimitiveComponent):
            component.set_collision_enabled(u.CollisionEnabled.NO_COLLISION)
            component.set_visibility(False,True)
        # Exclude retired walls from nearest supporting-wall cutaway grouping.
        actor.set_actor_label('S3_RetiredAltar_'+label.removeprefix('S3_'))
        original_tags=list(map(str,actor.tags))
        actor.tags=[t for t in actor.tags if str(t) not in ('SoundWall','SoundObstacle')]+[u.Name(OWNER),u.Name('Stage3RetiredArchitecture')]
        actor.set_folder_path('Stage3/RetiredAltar20261125')
        report['retired'].append({'label':label,'path':actor.get_path_name(),'original_tags':original_tags})
    for suffix,(x0,y0,x1,y1) in BOXES:
        vertical=(y1-y0)>(x1-x0)
        actor=actors.spawn_actor_from_class(u.StaticMeshActor,u.Vector(),u.Rotator(yaw=90 if vertical else 0))
        assert actor
        actor.set_actor_label('S3_Wall_Altar_'+suffix)
        actor.tags=[u.Name(OWNER),u.Name('SoundWall')]
        actor.set_folder_path('Stage3/ApprovedAltar20261125')
        component=actor.static_mesh_component
        component.set_static_mesh(mesh)
        for i,material in enumerate(mats): component.set_material(i,material)
        component.set_collision_profile_name('BlockAll')
        component.set_collision_enabled(u.CollisionEnabled.QUERY_AND_PHYSICS)
        actor.set_actor_enable_collision(True)
        # Imported closure is 150x30x300cm. Fit its actual transformed AABB.
        c,e=actor.get_actor_bounds(False,False)
        target=u.Vector(x1-x0,y1-y0,300)
        world_scale=u.Vector(target.x/(2*e.x),target.y/(2*e.y),target.z/(2*e.z))
        actor.set_actor_scale3d(u.Vector(world_scale.y,world_scale.x,world_scale.z) if vertical else world_scale)
        c,e=actor.get_actor_bounds(False,False)
        wanted=u.Vector(x0,-y1,0)
        actor.set_actor_location(wanted-(c-e),False,True)
        b=bounds(actor)
        expected=[[x0,-y1,0],[x1,-y0,300]]
        assert all(abs(a-bv)<.03 for aa,bb in zip(b,expected) for a,bv in zip(aa,bb)),(suffix,b,expected)
        report['walls'].append({'label':actor.get_actor_label(),'bounds':b,'mesh':mesh.get_path_name()})
    director=lookup['S3_Objectives']
    fixed_bolt=director.get_editor_property('Devices')[2].get_editor_property('LockBolt')
    fixed_before=fixed_bolt.get_actor_transform().export_text()
    roots={a for name,a in lookup.items() if name.startswith('S3_Release3_') and a!=fixed_bolt}
    selected=set(roots)
    for actor in lookup.values():
        parent=actor.get_attach_parent_actor()
        while parent:
            if parent in roots:
                selected.add(actor); break
            parent=parent.get_attach_parent_actor()
    before={a:a.get_actor_location() for a in selected}
    def depth(actor):
        count=0
        while actor.get_attach_parent_actor(): actor=actor.get_attach_parent_actor();count+=1
        return count
    for actor in sorted(selected,key=depth):
        target=before[actor]+u.Vector(0,-50,0)
        actor.set_actor_location(target,False,True)
        report['device_moved'].append({'label':actor.get_actor_label(),'before':vec(before[actor]),'after':vec(actor.get_actor_location())})
    assert fixed_bolt.get_actor_transform().export_text()==fixed_before
    report['fixed_gate_lock']=fixed_bolt.get_path_name()
    armor=lookup['S3_Armor_ControlPatrol']
    for point,(x,y) in zip(armor.get_editor_property('PatrolPoints'),PATROL):
        point.set_actor_location(u.Vector(x,-y,point.get_actor_location().z),False,True)
    armor.set_actor_location(u.Vector(550,-2190,armor.get_actor_location().z),False,True)
    armor.set_editor_property('bPatrolLoop',True)
    report['success']=True
    out=root/'Saved/Stage3IntegrationRevision20261125';out.mkdir(parents=True,exist_ok=True)
    (out/'altar_applied_unsaved.json').write_text(json.dumps(report,indent=2),encoding='utf8')
    return report
