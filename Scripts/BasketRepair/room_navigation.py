"""Read-only capsule graph diagnostic; never substitutes for the walking test."""
import unreal as u,math,collections
def xyz(v):return [v.x,v.y,v.z]
def exit_obstructions(w,cat,basket,landing):
 cap=cat.get_component_by_class(u.CapsuleComponent);r=cap.get_scaled_capsule_radius();h=cap.get_scaled_capsule_half_height()
 origin=basket.get_hidden_location();body=basket.get_editor_property('ExternalBody');ignore=[cat,basket]+([body] if body else [])
 def trace(a,b,ignored):
  hit=u.SystemLibrary.capsule_trace_single_by_profile(w,a,b,r,h,'Pawn',False,ignored,u.DrawDebugTrace.NONE,False)
  if not hit:return None
  d=hit.to_dict();actor=d['hit_actor']
  return {'actor':actor.get_actor_label() if actor else None,'class':actor.get_class().get_name() if actor else None,'location':xyz(d['location']),'normal':xyz(d['impact_normal']),'initial_overlap':d['initial_overlap']}
 return {'origin_support':trace(origin+u.Vector(0,0,h+50),origin+u.Vector(0,0,h-100),ignore),
  'landing_support':trace(u.Vector(landing.x,landing.y,origin.z+h+50),u.Vector(landing.x,landing.y,origin.z+h-100),ignore),
  'transit':trace(u.Vector(origin.x,origin.y,landing.z),landing,ignore),
  'landing_overlap':trace(landing,landing+u.Vector(0,0,.01),[cat])}
def navigation(w,cat,basket):
 cap=cat.get_component_by_class(u.CapsuleComponent);r=cap.get_scaled_capsule_radius();h=cap.get_scaled_capsule_half_height();ignore=[cat]
 def trace(a,b):
  return u.SystemLibrary.capsule_trace_single_by_profile(w,a,b,r,h,'Pawn',False,ignore,u.DrawDebugTrace.NONE,False)
 nodes={};blocked=collections.Counter();edges={};step=20
 for x in range(500,1021,step):
  for y in range(1540,1961,step):
   hit=trace(u.Vector(x,y,100),u.Vector(x,y,-100))
   if not hit:blocked['no support']+=1;continue
   d=hit.to_dict();a=d['hit_actor'];label=a.get_actor_label() if a else '?'
   if d['initial_overlap'] or d['impact_normal'].z<.65 or isinstance(a,u.Pawn):blocked[label]+=1;continue
   p=d['location']+u.Vector(0,0,2)
   if p.z>40:blocked[label]+=1;continue
   hit=trace(p,p+u.Vector(0,0,.01))
   if hit:
    a=hit.to_dict()['hit_actor'];blocked[a.get_actor_label() if a else '?']+=1;continue
   nodes[(x,y)]=p
 for k,p in nodes.items():
  edges[k]=[]
  for dx,dy in [(20,0),(-20,0),(0,20),(0,-20),(20,20),(20,-20),(-20,20),(-20,-20)]:
   q=(k[0]+dx,k[1]+dy)
   if q in nodes and not trace(p,nodes[q]):edges[k].append(q)
 # Multi-source distance from middle corridor, staying on reachable actual floor.
 todo=collections.deque(k for k in nodes if k[0]<=580);parent={k:None for k in todo}
 while todo:
  k=todo.popleft()
  for q in edges[k]:
   if q not in parent:parent[q]=k;todo.append(q)
 def route(start):
  choices=sorted(parent,key=lambda k:(nodes[k]-start).length())
  first=next((k for k in choices if (nodes[k]-start).length()<75 and not trace(start,nodes[k])),None)
  if first is None:return []
  path=[];k=first
  while k is not None:path.append(nodes[k]);k=parent[k]
  # Greedy line-of-sight shortening retains capsule clearance on each segment.
  result=[];current=start
  while path:
   i=next((i for i in reversed(range(len(path))) if not trace(current,path[i])),0)
   current=path[i];result.append(current);path=path[i+1:]
  return [xyz(p) for p in result]
 result={'radius':r,'half_height':h,'clear_nodes':len(nodes),'connected_nodes':len(parent),'blocked_by':dict(blocked),'paths':[]}
 center=basket.get_hidden_location()
 for i in range(8):
  a=i*math.pi/4;dist=82 if i%2==0 else 94;p=u.Vector(center.x+math.cos(a)*dist,center.y+math.sin(a)*dist,26)
  result['paths'].append({'direction_index':i,'start':xyz(p),'route':route(p)})
 result['from_cat']=route(cat.get_actor_location())
 result['nodes']=[{'p':xyz(p),'connected':k in parent} for k,p in nodes.items()]
 return result
