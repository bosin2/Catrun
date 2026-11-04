"""Build a task-local semantic/hash review, never a diff against stale Git art."""
from pathlib import Path
import json,hashlib,difflib,re,collections
root=Path(__file__).resolve().parents[2];out=root/'Saved/Prototype20261104/CanonicalMaps'
docs=root/'.superpowers/sdd/2026-11-04-playable-prototype'
def read(name):return json.loads((out/name).read_text(encoding='utf8'))
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def t3d_text(path):
    data=path.read_bytes();return data.decode('utf16' if data.startswith(b'\xff\xfe') else 'utf8')
before=read('preflight.json');after=read('disk-verification.json');runtime=read('Runtime2/observations.json');action=read('BellAction2/observations.json');passage=read('TutorialPass/observations.json')
assert runtime['error'] is None and action['error'] is None and passage['error'] is None
semantic={}
for stage in before['maps']:
    old={a['name']:a for a in before['maps'][stage]};new={a['name']:a for a in after['maps'][stage]['actors']}
    delta={}
    for name in old.keys()&new.keys():
        changes={p:{'before':old[name].get(p),'after':new[name].get(p)} for p in ['label','class','location','scale','mesh'] if old[name].get(p)!=new[name].get(p)}
        rot=[round(float(v),3) for v in re.findall(r'(?:pitch|yaw|roll): (-?[\d.]+)',old[name]['rotation'])]
        new_rot=[round(v,3) for v in new[name]['rotation']]
        if rot!=new_rot:changes['rotation']={'before':rot,'after':new_rot}
        if changes:delta[name]=changes
    semantic[stage]={'source_count':len(old),'canonical_count':len(new),'removed':[old[k] for k in sorted(old.keys()-new.keys())],'added':[new[k] for k in sorted(new.keys()-old.keys())],'changed':delta,'stale_test_map_references_in_t3d':re.findall(r'/Game/Maps/SoundTest_[\w.]+',t3d_text(out/(stage+'.t3d')))}
    assert not semantic[stage]['removed'] and not semantic[stage]['stale_test_map_references_in_t3d']
assert set(semantic['Tutorial']['changed'])=={'BP_LivingArmor_C_0'}
assert not semantic['Stage1']['changed'] and not semantic['Stage2']['changed']
logs=(root/'Saved/Prototype20261104/EditorAssets3.log').read_text(encoding='utf8',errors='replace')
emission=[]
for match in re.finditer(r'CANONICAL_BELL_(DENIED|ALLOWED|DELAYED)_BEGIN ([^\r\n]+)',logs):
    kind=match.group(1);end=logs.find('CANONICAL_BELL_'+kind+'_END',match.end())
    segment=logs[match.end():end]
    row={'scenario':kind,'location':match.group(2),'emit_count':segment.count('LogCatrunSound: EmitSound:'),'denied_log_count':segment.count('The bell is forbidden here')};emission.append(row)
    assert row['emit_count']==(1 if kind=='ALLOWED' else 0),row
for kind in ['OUTSIDE','INSIDE']:
    start=logs.rfind('BELL_ACTION_'+kind+'_BEGIN');end=logs.find('BELL_ACTION_'+kind+'_END',start)
    row={'scenario':'ACTION_'+kind,'emit_count':logs[start:end].count('LogCatrunSound: EmitSound:')};emission.append(row)
    assert row['emit_count']==(1 if kind=='OUTSIDE' else 0),row
semantic['emission_logs']=emission
prior=json.loads((root/'Saved/Prototype20261104/intro-final-save-verification.json').read_text())
semantic['protected_intro_hashes']={p:{'sha256':sha(root/p),'unchanged':sha(root/p)==h} for p,h in prior['hashes'].items()}
assert all(r['unchanged'] for r in semantic['protected_intro_hashes'].values())
(out/'semantic-delta.json').write_text(json.dumps(semantic,ensure_ascii=False,indent=2),encoding='utf8')
manifest=read('manifest.json')
new_scripts=['inspect_canonical_maps.py','duplicate_canonical_maps.py','promote_canonical_maps.py','verify_canonical_maps.py','validate_canonical_runtime.py','inspect_canonical_input.py','inspect_active_contexts.py','inspect_key_profiles.py','validate_bell_action_path.py','validate_tutorial_pass.py','finish_canonical_maps.py','build_canonical_review.py']
for name in new_scripts:
    rel='Scripts/Prototype/'+name
    if not any(r['path']==rel for r in manifest['files']):manifest['files'].append({'path':rel,'before_sha256':None,'new_task_file':True})
for row in manifest['files']:
    row['after_sha256']=sha(root/row['path']);row['changed']=row['before_sha256']!=row['after_sha256']
    if 'SoundTest_' in row['path']:assert not row['changed'],row
(out/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf8')
parts=['# Task4b scoped review. Baseline = exact task-entry backups, not Git HEAD.\n', '# Binary map semantic deltas relative to enhanced source maps:\n',json.dumps(semantic,ensure_ascii=False,indent=2)+'\n']
for row in manifest['files']:
    if not row['changed']:continue
    path=root/row['path']
    if path.suffix in ['.py','.ini']:
        old=Path(row['backup']).read_text(encoding='utf-8-sig').splitlines(True) if row.get('backup') else []
        parts.extend(difflib.unified_diff(old,path.read_text(encoding='utf-8-sig').splitlines(True),fromfile='before/'+row['path'],tofile='after/'+row['path']))
    else:parts.append('Binary '+row['path']+'\n  before '+str(row['before_sha256'])+'\n  after  '+row['after_sha256']+'\n')
(docs/'task-4b-review.diff').write_text(''.join(parts),encoding='utf8')
print('REVIEW_READY',len(manifest['files']),'tracked files;',sum(r['changed'] for r in manifest['files']),'changed;',len(emission),'emission scenarios')
