"""Build a text review package against saved pre-task binary/semantic backups."""
import json,difflib,hashlib
from pathlib import Path
root=Path(__file__).resolve().parents[2]
out=root/'Saved/Prototype20261104'
review=root/'.superpowers/sdd/2026-11-04-playable-prototype/task-4a-review.diff'
backup=out/'IntroFixBackups'
manifest=json.loads((backup/'manifest.json').read_text(encoding='utf8'))
chunks=['# Task4a review package\n# Binary baselines are IntroFixBackups, NOT Git HEAD.\n# For BP_TutorialIntro use its preexisting-dirty snapshot as the effective before state.\n# BP semantic before: live pre-edit node inventory plus original baseline pin defaults.\n# Original runtime strict-Z failure remains preserved; tolerance adjudication is separate.\n']
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def emit(old,new,fromfile,tofile):
    chunks.extend(difflib.unified_diff(old.splitlines(True),new.splitlines(True),fromfile=fromfile,tofile=tofile,n=5))
def js(x):return json.dumps(x,ensure_ascii=False,indent=2,sort_keys=True)+'\n'
for entry in manifest['assets']:
    rel=entry['relative_path'];baseline=backup/rel
    dirty=baseline.with_name(baseline.stem+'.preexisting-dirty'+baseline.suffix)
    if entry['was_dirty'] and dirty.exists():baseline=dirty
    chunks.append('\n# Binary package: '+rel+'\n# Effective before: '+str(baseline)+'\n# Before SHA256: '+sha(baseline)+'\n# After SHA256: '+sha(root/rel)+'\n')

def graph(path):
    data=json.loads(path.read_text(encoding='utf8'))
    for n in data:
        n.pop('position',None)
        for side in ['inputs','outputs']:
            for p in n[side]:p['links']=sorted(p['links'],key=lambda q:(q['node'],q['index'],q['direction']))
    return sorted(data,key=lambda n:n['name'])
emit(js(graph(out/'intro-graph-before.json')),js(graph(out/'intro-graph-after.json')),'a/pre-task/BP_TutorialIntro.EventGraph.semantic.json','b/saved/BP_TutorialIntro.EventGraph.semantic.json')

old_refs=[];new_refs=[]
for name in ['SoundTest_Tutorial','Tutorial']:
    prefix='/Game/Maps/'+name+'.'+name+':PersistentLevel.'
    before={'map':'/Game/Maps/'+name,'intro':prefix+'BP_TutorialIntro_C_1','Cat':prefix+'BP_Cat_C_0','StartCamera':prefix+'CineCameraActor_0','GamePlayCamera':prefix+'BP_QuarterViewCamera_C_0','WakeCamera':None}
    after=dict(before);after['WakeCamera']=prefix+'CineCameraActor_3'
    old_refs.append(before);new_refs.append(after)
emit(js(old_refs),js(new_refs),'a/pre-task/tutorial-map-intro-references.json','b/saved/tutorial-map-intro-references.json')

files=['Scripts/Prototype/repair_tutorial_intro.py','Scripts/Prototype/run_intro_patch.py','Scripts/Prototype/assign_legacy_tutorial_intro_camera.py','Scripts/Prototype/validate_saved_intro.py','Scripts/Prototype/reload_saved_intro.py','Scripts/Prototype/summarize_saved_intro.py','Scripts/Prototype/observe_real_menu_start.py']
for rel in files:emit('',(root/rel).read_text(encoding='utf-8-sig'),'/dev/null','b/'+rel)

summary=json.loads((out/'intro-validation-summary.json').read_text(encoding='utf8'))
summary={k:v for k,v in summary.items() if k not in ['changed_original_pins','normal_completion','retry_completion','pose_checks']}
actual=json.loads((out/'ActualMenuStart/observations.json').read_text(encoding='utf8'))
summary['actual_os_start']={k:v for k,v in actual.items() if k not in ['samples']}
summary['actual_os_start']['sample_count']=len(actual['samples'])
summary['actual_os_start']['final_sample']=actual['samples'][-1]
summary['legacy_consumer']=json.loads((out/'intro-legacy-consumer-verification.json').read_text(encoding='utf8'))
emit('',js(summary),'/dev/null','b/evidence/task-4a-summary.json')
emit('',(root/'.superpowers/sdd/2026-11-04-playable-prototype/task-4a-report.md').read_text(encoding='utf8'),'/dev/null','b/.superpowers/sdd/2026-11-04-playable-prototype/task-4a-report.md')
review.write_text(''.join(chunks),encoding='utf8')
print(json.dumps({'path':str(review),'bytes':review.stat().st_size,'sha256':sha(review),'scripts':files},indent=2))
