"""Import isolated provisional local Foley and bind only the E23 directors."""
import json,hashlib,wave
from pathlib import Path
import unreal as u
ROOT=Path(u.Paths.project_dir()).resolve();RUN='CAD_20261125_053416_46364406'
PLAN=json.loads((ROOT/'Saved/CatAudioDirector'/RUN/'import_plan.json').read_text(encoding='utf8'))
EA=u.EditorAssetLibrary;AT=u.AssetToolsHelpers.get_asset_tools();LE=u.get_editor_subsystem(u.LevelEditorSubsystem);AC=u.get_editor_subsystem(u.EditorActorSubsystem)
DEST='/Game/Audio/CatAudioDirector/'+RUN
assets={};report={'provisional':True,'assets':{},'maps':[]}
for item in PLAN['assets']:
    p=Path(item['path']);assert hashlib.sha256(p.read_bytes()).hexdigest()==item['sha256']
    with wave.open(str(p),'rb') as wav:assert (wav.getframerate(),wav.getnchannels(),wav.getsampwidth())==(48000,1,2)
    name='SW_'+item['id'];path=DEST+'/'+name
    if not EA.does_asset_exist(path):
        t=u.AssetImportTask();t.filename=str(p);t.destination_path=DEST;t.destination_name=name;t.automated=True;t.save=True
        AT.import_asset_tasks([t])
    a=EA.load_asset(path);assert isinstance(a,u.SoundWave)
    a.set_editor_property('looping',False);EA.save_loaded_asset(a);assets[item['id']]=a;report['assets'][item['id']]=a.get_path_name()
for mapname in ['Stage2','Stage3']:
    assert LE.load_level('/Game/Maps/'+mapname)
    ds=[a for a in AC.get_all_level_actors() if isinstance(a,u.CatrunElevatorTransition)]
    assert len(ds)==1
    for key,id in [('pull_sound','chain_ring_pull'),('start_sound','lift_departure'),('dock_latch_sound','dock_latch')]:ds[0].set_editor_property(key,assets[id])
    assert LE.save_current_level();report['maps'].append(mapname)
    del ds
(ROOT/'Saved/ElevatorTransition/audio_report.json').write_text(json.dumps(report,indent=2),encoding='utf8')
