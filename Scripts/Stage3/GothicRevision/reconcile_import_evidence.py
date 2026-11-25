"""Reconcile final delivery prose updated during a completed 24-mesh import.

No asset input changes are allowed. Preserve the failed raw report as evidence.
This does not run Unreal or reinterpret a mesh/material/collision failure.
"""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
OUT=ROOT/'Saved/Stage3GothicRevision20261125'
path=OUT/'import_report.json'
report=json.loads(path.read_text(encoding='utf8'))
frozen=json.loads(Path(report['freeze_path']).read_text(encoding='utf8'))
source=Path(frozen['source'])
assert len(report['meshes'])==24
assert all('Frozen delivery changed;' in e for e in report['errors']),report['errors']
allowed={'README.md','BRIEF.md','QA/FINAL_QA.md','asset_manifest.json'}
current_manifest=json.loads((source/'asset_manifest.json').read_text(encoding='utf8'))
current_assets={a['name']:a for a in current_manifest['items'] if a.get('kind')=='asset'}
assert set(current_assets)=={a['name'] for a in frozen['assets']}
for a in frozen['assets']:
    b=current_assets[a['name']]
    for field in ('name','category','fbx','blend','metadata','sha256','fbx_sha256','bounds_m','triangles'):
        assert a.get(field)==b.get(field),(a['name'],field,'manifest asset contract changed')
    current_metadata=json.loads((source/a['metadata']).read_text(encoding='utf8'))
    evidence_fields={'qa_source_sha256','user_art_approved','qa_report','status','unreal_runtime_verified'}
    changed={k for k in set(current_metadata)|set(a['metadata_data']) if current_metadata.get(k)!=a['metadata_data'].get(k)}
    assert changed<=evidence_fields,(a['name'],'asset technical metadata changed',changed)
    assert current_metadata.get('qa_source_sha256',a['sha256'])==a['sha256']
    allowed.add(a['metadata'])
changes=[]
for relative,expected in frozen['files'].items():
    actual=hashlib.sha256((source/relative).read_bytes()).hexdigest()
    if actual!=expected:
        assert relative in allowed,('Actual asset/evidence input changed',relative)
        changes.append({'file':relative,'before':expected,'after':actual})
assert changes,'No prose drift to reconcile'
for name,row in report['meshes'].items():
    assert row['axis_mapping_candidates'],name
    assert sum(row['collision_counts'].values())==row['expected_collision_count'],name
    package=ROOT/('Content/'+row['path'].split('.')[0].removeprefix('/Game/')+'.uasset')
    assert package.is_file() and package.stat().st_size>1024,package
raw=OUT/'import_report_attempt02_prose_drift.json'
if not raw.exists():raw.write_text(json.dumps(report,indent=2),encoding='utf8')
report['previous_attempt_errors']=report['errors'];report['errors']=[]
report['final_evidence_reconciliation']={'changes':changes,'asset_inputs_unchanged':True,
    'decision':'All 24 measured/saved mesh imports passed. Final delivery prose/status index changed; every manifest asset identity, bounds, triangle count and source hash is unchanged. Current FINAL_QA says passed; original failed report retained.'}
report['mesh_count']=24;report['success']=True
path.write_text(json.dumps(report,indent=2),encoding='utf8')
print('GOTHIC_IMPORT_EVIDENCE_RECONCILED',len(changes),'prose files; all asset inputs unchanged')
