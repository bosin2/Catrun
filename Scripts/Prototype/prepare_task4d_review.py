"""Offline task-local review package; never compares the dirty checkout to HEAD."""
import difflib,hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'Saved/Prototype20261104/Task4d';DOC=ROOT/'.superpowers/sdd/2026-11-04-playable-prototype'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
manifest=json.loads((OUT/'manifest.json').read_text());assets=[]
for row in manifest['existing']:
 p=ROOT/row['file'];assets.append(dict(row,after_sha256=sha(p),after_bytes=p.stat().st_size,baseline_file=str((OUT/'Backups'/row['file']).relative_to(ROOT)).replace('\\','/')))
for path in manifest['new']:
 rel='Content/'+path.removeprefix('/Game/')+'.uasset';p=ROOT/rel;assets.append({'asset':path,'file':rel,'before_sha256':None,'after_sha256':sha(p),'after_bytes':p.stat().st_size,'was_dirty':False})
new=sorted(str(p.relative_to(ROOT)).replace('\\','/') for p in (ROOT/'Scripts/Prototype').glob('*task4d*.py'))
existing=['Docs/Design/PrototypeTuning.md','Scripts/Stage2/verify_statue_routes.py']
texts=[];parts=['# Task4d review relative to captured pre-task baseline, not repository HEAD.\n# Binary assets: see task-4d-asset-manifest.json and task-4d-report.md for semantics.\n']
for rel in existing+new:
 p=ROOT/rel;b=OUT/'Backups'/rel;old=b.read_text(encoding='utf-8-sig') if rel in existing else '';current=p.read_text(encoding='utf-8-sig');texts.append({'file':rel,'before_sha256':sha(b) if rel in existing else None,'after_sha256':sha(p)});parts.extend(difflib.unified_diff(old.splitlines(True),current.splitlines(True),fromfile='baseline/'+rel if rel in existing else '/dev/null',tofile='current/'+rel))
for row in assets:parts.append('\nBinary task asset '+row['file']+'\n  before '+str(row['before_sha256'])+'\n  after  '+row['after_sha256']+'\n')
(DOC/'task-4d-review.diff').write_text(''.join(parts),encoding='utf8')
(DOC/'task-4d-asset-manifest.json').write_text(json.dumps({'baseline_created_utc':manifest['created_utc'],'baseline_scope':'Only the 3 clean-on-entry existing packages and 2 text files this task changed; broader dirty checkout belongs to prior work.','assets':assets,'text_files':texts,'evidence_root':'Saved/Prototype20261104/Task4d','native_source_changed':False},indent=2),encoding='utf8')
print('TASK4D_REVIEW_PREPARED',len(assets),'assets',len(texts),'text files')
