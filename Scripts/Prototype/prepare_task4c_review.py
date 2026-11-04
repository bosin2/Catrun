"""Filesystem-only task-local review bundle; run after verify_task4c_assets.py."""
from pathlib import Path
import hashlib,json,difflib,collections,datetime
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'Saved/Prototype20261104/Task4c'
REVIEW=ROOT/'.superpowers/sdd/2026-11-04-playable-prototype'
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def lines(path):return path.read_text(encoding='utf-8-sig').splitlines(keepends=True)
def diff(before,after,label):
 return ''.join(difflib.unified_diff(before,after,fromfile='task4c-before/'+label,tofile=label))
manifest=json.loads((OUT/'manifest.json').read_text())
final={'created_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'existing':[],'new':[],'native_build_matches':{},'files':{}}
for item in manifest['existing']:
 backup=OUT/'Backups'/item['file'];assert sha(backup)==item['before_sha256']
 final['existing'].append({**item,'after_sha256':sha(ROOT/item['file'])})
for asset in manifest['new']:
 file='Content/'+asset.removeprefix('/Game/')+'.uasset';final['new'].append({'asset':asset,'file':file,'sha256':sha(ROOT/file)})
for path,record in json.loads((OUT/'native-built-manifest.json').read_text()).items():
 assert sha(ROOT/path)==record['sha256'],path
 final['native_build_matches'][path]=record['sha256']
parts=['# Task4c task-local review. Baseline is immediate task snapshots, not git HEAD.\n# Binary package changes are represented semantically below; immutable binaries/hashes are in Task4c/Backups and final-manifest.json.\n']
for item in json.loads((OUT/'Backups/Source/manifest.json').read_text()):
 assert sha(Path(item['backup']))==item['sha256'];parts.append(diff(lines(Path(item['backup'])),lines(ROOT/item['path']),item['path']))
for name in ['CapturePresentation.md','PrototypeTuning.md']:
 rel='Docs/Design/'+name;parts.append(diff(lines(OUT/'Backups'/rel),lines(ROOT/rel),rel));final['files'][rel]=sha(ROOT/rel)
supported=['setup_task4c_presentation.py','task4c_assets.py','task4c_context_scaffold.py','task4c_context.py','task4c_armor.py','task4c_tune_hold_final.py','task4c_reload.py','verify_task4c_assets.py','prepare_task4c_review.py']
focused=['task4c_cancel_final.py','task4c_lifetime_probe.py','task4c_turn_timing.py','task4c_door_final.py','task4c_intro_verify.py','task4c_tutorial_retry_final.py','task4c_capture_fixed_yaw08.py']
for name in supported+focused:
 rel='Scripts/Prototype/'+name;parts.append(diff([],lines(ROOT/rel),rel));final['files'][rel]=sha(ROOT/rel)
final['canonical_entrypoints']=supported[:1]+['task4c_reload.py','verify_task4c_assets.py','prepare_task4c_review.py']
final['focused_runtime_harnesses']=focused
before={'BP_LivingArmor':{'bUseBlueprintAnimation':False,'bUseBlueprintPresentation':False,'armor_anim_class':None,'CatPickupAnimation':None,'graphs':json.loads((OUT/'armor-before.json').read_text())},'DA_SoundSettings':{'CatchHoldOffset':[0,0,-10]},'new_packages':[]}
after=json.loads((OUT/'presentation-after.json').read_text())
summary={k:v for k,v in after.items() if k!='blueprints'}
summary['graphs']=[{'asset':b['asset'],'status':b['status'],'graphs':[{'name':g['name'],'node_types':dict(sorted(collections.Counter(n['type'] for n in g['nodes']).items()))} for g in b['graphs']]} for b in after['blueprints']]
summary['new_packages']=manifest['new'];summary['authored_cat']=json.loads((OUT/'cat-authoring.json').read_text());summary['raw_graphs']='Saved/Prototype20261104/Task4c/presentation-after.json'
(OUT/'semantic-before.json').write_text(json.dumps(before,indent=2,ensure_ascii=False),encoding='utf8')
(OUT/'semantic-after.json').write_text(json.dumps(summary,indent=2,ensure_ascii=False),encoding='utf8')
parts.append(diff(lines(OUT/'semantic-before.json'),lines(OUT/'semantic-after.json'),'Task4c/semantic-presentation.json'))
(OUT/'final-manifest.json').write_text(json.dumps(final,indent=2),encoding='utf8')
(REVIEW/'task-4c-review.diff').write_text(''.join(parts),encoding='utf8')
print('TASK4C_REVIEW_READY',len(''.join(parts).splitlines()),'lines',len(final['files']),'script/docs hashes')
