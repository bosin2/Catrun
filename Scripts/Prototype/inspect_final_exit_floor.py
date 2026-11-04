"""Read-only editor-world traces at the tutorial stair entrance."""
import json
from pathlib import Path
import unreal

def inspect():
    w=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    assert w.get_name()=='Tutorial'
    rows=[]
    for y in (1380,1420,1460,1480,1500,1520,1548):
        start=unreal.Vector(-130,y,30)
        for profile in ('Pawn','BlockAll'):
            hit=unreal.SystemLibrary.line_trace_single_by_profile(w,start,start-unreal.Vector(0,0,600),profile,False,[],unreal.DrawDebugTrace.NONE,False)
            rows.append({'y':y,'profile':profile,'hit':{k:str(v) for k,v in hit.to_dict().items()} if hit else None})
    exits=[]
    for a in unreal.GameplayStatics.get_all_actors_of_class(w,unreal.Actor):
        if a.get_class().get_name() in ('BP_LevelExit_C','BP_StairDescentDirector_C'):
            exits.append({'label':a.get_actor_label(),'loc':str(a.get_actor_location()),'components':[{'name':c.get_name(),'type':c.get_class().get_name(),'location':str(c.get_world_location()),'bounds':str(c.get_scaled_box_extent()) if isinstance(c,unreal.BoxComponent) else None} for c in a.get_components_by_class(unreal.SceneComponent)]})
    return {'traces':rows,'exits':exits}
result=inspect()
(Path(unreal.Paths.project_saved_dir())/'Prototype20261104/Task5/exit-floor-inspection.json').write_text(json.dumps(result,indent=2),encoding='utf8')
print(json.dumps(result))
