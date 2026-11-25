"""Actual GPU BaseColor proof for the three new textile slots only."""
import sys,json
from pathlib import Path
import unreal as u
ROOT=Path(u.Paths.project_dir()).resolve()
sys.path.insert(0,str(ROOT/'Scripts/Stage3/GothicRevision'))
import gpu_verify
gpu_verify.OUT=ROOT/'Saved/Stage3GothicRevision20261125/GPU_Rug'
def cases(report):
    imported=json.loads((ROOT/'Saved/Stage3GothicRevision20261125/rug_import_report.json').read_text(encoding='utf8'))
    assert imported['success']
    rows=[{'kind':'rug','role':entry['role'],'material':entry['instance'],'target_srgb':entry['target_srgb8']} for entry in imported['materials'].values()]
    assert len(rows)==3
    report['expected_case_count']=3
    return rows
gpu_verify.select_cases=cases
result=gpu_verify.main()
assert result['success']
print('GOTHIC_RUG_GPU_PASSED')
