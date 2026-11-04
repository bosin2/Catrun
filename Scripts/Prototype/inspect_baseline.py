import unreal
import json
from pathlib import Path
from editor_toolset.toolsets.blueprint import BlueprintTools as BP

out = Path(unreal.Paths.project_saved_dir()) / 'Prototype20261104'
out.mkdir(parents=True, exist_ok=True)
result = {'maps': {}, 'graphs': {}, 'sequences': {}}
levels = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not editor.get_game_world(), 'Stop PIE before inspection'
for path in ['/Game/Maps/Tutorial','/Game/Maps/SoundTest_Tutorial','/Game/Maps/Stage1','/Game/Maps/Stage2','/Game/Maps/SoundTest_Stage2']:
    if not levels.load_level(path):
        result['maps'][path] = {'error': 'load failed'}; continue
    world = editor.get_editor_world()
    actors = unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Actor)
    rows=[]
    for a in actors:
        cls=a.get_class().get_name()
        if any(s in cls for s in ['Cat','Camera','Armor','Candle','Sound','Intro','Stair','LevelExit']):
            row={'label':a.get_actor_label(),'path':a.get_path_name(),'class':cls,'location':str(a.get_actor_location())}
            cams=a.get_components_by_class(unreal.CameraComponent)
            row['cameras']=[{'path':c.get_path_name(),'projection':str(c.projection_mode),'ortho_width':c.ortho_width,'fov':c.field_of_view} for c in cams]
            if cls=='BP_TutorialIntro_C':
                for p in ['IntroSequence','IntroPlayer','Cat','PlayerCat','IntroActor']:
                    try: row[p]=str(a.get_editor_property(p))
                    except Exception: pass
            rows.append(row)
    result['maps'][path]=rows
for path in ['/Game/Blueprints/BP_TutorialIntro','/Game/Characters/BlackCat/Blueprints/BP_Cat','/Game/UI/WBP_MainMenu']:
    bp=unreal.load_asset(path)
    if not bp: continue
    rows=[]
    for g in BP.list_graphs(bp):
        for n in BP.get_node_infos(BP.find_nodes(g)):
            rows.append({'graph':g.get_name(),'name':n.node.get_name(),'type':n.type_id,
                'inputs':[{'name':p.name,'value':str(p.value),'links':str(p.connected_pins)} for p in n.input_pins],
                'outputs':[{'name':p.name,'links':str(p.connected_pins)} for p in n.output_pins]})
    result['graphs'][path]=rows
for data in unreal.AssetRegistryHelpers.get_asset_registry().get_assets_by_class(unreal.TopLevelAssetPath('/Script/LevelSequence','LevelSequence'),True):
    if 'Tutorial' not in str(data.asset_name): continue
    seq=data.get_asset(); binds=[]
    for b in seq.get_bindings():
        tracks=[]
        for t in b.get_tracks():
            sections=[]
            for s in t.get_sections():
                row={'class':s.get_class().get_name()}
                if s.has_start_frame() and s.has_end_frame():
                    row['range']=[s.get_start_frame(),s.get_end_frame()]
                if isinstance(s,unreal.MovieSceneSkeletalAnimationSection):
                    row['animation']=str(s.params.animation)
                sections.append(row)
            tracks.append({'class':t.get_class().get_name(),'sections':sections})
        binds.append({'name':b.get_name(),'id':str(b.get_id()),'tracks':tracks})
    result['sequences'][seq.get_path_name()]=binds
(out/'baseline-inspection.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
print('INSPECTION_SAVED',str(out/'baseline-inspection.json'))
