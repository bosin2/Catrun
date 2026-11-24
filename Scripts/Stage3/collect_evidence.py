"""Archive compact, actually completed integration checks; never infer a pass."""
import json, re, shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RUN = ROOT / 'Saved/Stage3Integration20261125'
DEST = ROOT / 'Docs/Reviews/Stage3Evidence'
DEST.mkdir(parents=True, exist_ok=True)

def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))

def write(name, value):
    (DEST / name).write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf8')

native = read(RUN / 'Automation_Final/Report/index.json')
assert native['failed'] == native['notRun'] == native['inProcess'] == 0
write('AutomationSummary.json', {
    'source': 'Saved/Stage3Integration20261125/Automation_Final/Report/index.json',
    'report_created_on': native['reportCreatedOn'],
    'total': len(native['tests']), 'succeeded': native['succeeded'],
    'succeeded_with_warnings': native['succeededWithWarnings'], 'failed': native['failed'],
    'tests': [{'name': t['fullTestPath'], 'state': t['state'],
               'warnings': t['entries'] if t['warnings'] else []} for t in native['tests']],
})
log = (RUN / 'blueprint_compile.log').read_text(encoding='utf8', errors='replace')
result = re.search(r'Compiling Completed with 0 errors and 0 warnings and 0 blueprints that failed to load\.', log)
assert result, 'Blueprint compilation did not complete cleanly'
write('BlueprintCompile.json', {'source': 'Saved/Stage3Integration20261125/blueprint_compile.log',
                              'blueprints': len(re.findall(r"LogBlueprint: Compiling Blueprint '/Game/", log)), 'result': result.group(0)})
for source, target in [('cold_qa.json', 'SavedMapChecks.json'),
                       ('PIE/report.json', 'Stage3PIE.json'),
                       ('Campaign/observations.json', 'CampaignTransitions.json')]:
    value = read(RUN / source)
    assert value.get('success') is True, source
    write(target, value)
expansion = sorted((ROOT/'Saved/GameplayExpansion20261124/ExpansionPIE').glob('*/report.json'))[-1]
value = read(expansion)
assert value.get('success') is True, str(expansion)
write('Stage2ExpansionPIE.json', value)
visual = DEST / 'Visual'
visual.mkdir(exist_ok=True)
for name in ['Overview', 'Device', 'GateHall']:
    shutil.copy2(RUN / 'Visual' / (name+'.png'), visual / (name+'.png'))
for name in ['Contact', 'Pull', 'Completion']:
    shutil.copy2(RUN / 'PIE' / (name+'.png'), visual / ('PIE_'+name+'.png'))
print(json.dumps({'native': len(native['tests']), 'stage3_checks': len(read(RUN/'PIE/report.json')['checks']),
                  'expansion_source': str(expansion)}, ensure_ascii=False))
