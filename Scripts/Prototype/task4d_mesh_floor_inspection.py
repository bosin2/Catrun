import unreal,json
from pathlib import Path
lv=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem);ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem);assert not ed.get_game_world();assert lv.load_level('/Game/Maps/Stage2')
w=ed.get_editor_world();d=next(a for a in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors() if isinstance(a,unreal.CatrunStatuePuzzle));r=[]
for l in d.get_editor_property('Links'):
 key=str(l.get_editor_property('PuzzleId'));gate=l.get_editor_property('Gate');statue=l.get_editor_property('Statue');mesh=statue.get_component_by_class(unreal.StaticMeshComponent).static_mesh;body=mesh.get_editor_property('body_setup');geom=body.get_editor_property('agg_geom');row={'puzzle':key,'statue_collision':{},'gate_floor_hits':[]}
 for name in ['box_elems','convex_elems','sphere_elems','sphyl_elems']:
  elems=geom.get_editor_property(name);row['statue_collision'][name]=[]
  for elem in elems:
   info={k:str(v) for k,v in elem.to_dict().items() if k!='vertex_data'}
   row['statue_collision'][name].append(info)
 row['base_contact_traces']=[]
 for direction in [unreal.Vector(1,0,0),unreal.Vector(-1,0,0),unreal.Vector(0,1,0),unreal.Vector(0,-1,0)]:
  q=statue.get_actor_location()+unreal.Vector(0,0,15);hit=unreal.SystemLibrary.line_trace_single(w,q+direction*100,q-direction*100,unreal.TraceTypeQuery.TRACE_TYPE_QUERY1,False,[],unreal.DrawDebugTrace.NONE,True)
  hd=hit.to_dict() if hit else {};pt=hd.get('impact_point');row['base_contact_traces'].append({'direction':str(direction),'relative_impact':str(pt-statue.get_actor_location()) if pt else None,'fields':{k:str(v) for k,v in hd.items() if k in ['actor','hit_actor','hit_component','component']}})
 for dx,dy in [(0,0),(0,15),(15,0)]:
  center,extent=gate.get_actor_bounds(False);q=unreal.Vector(center.x+dx,center.y+dy,50);hit=unreal.SystemLibrary.line_trace_single(w,q,q-unreal.Vector(0,0,100),unreal.TraceTypeQuery.TRACE_TYPE_QUERY1,False,[gate],unreal.DrawDebugTrace.NONE,True)
  row['gate_floor_hits'].append({k:str(v) for k,v in hit.to_dict().items() if k in ['blocking_hit','location','impact_point','impact_normal','hit_object_handle','component']} if hit else None)
 r.append(row)
out=Path(unreal.Paths.project_saved_dir())/'Prototype20261104/Task4d/mesh-floor-inspection.json';out.write_text(json.dumps(r,indent=2),encoding='utf8');print(json.dumps(r,indent=2))
