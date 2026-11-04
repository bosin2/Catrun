"""Offline evidence summary; never edits editor/assets or prior runtime traces."""
import json,re,hashlib,subprocess
from pathlib import Path
root=Path(__file__).resolve().parents[2]
out=root/'Saved/Prototype20261104'
before=json.loads((out/'intro-live-graph.json').read_text(encoding='utf8'))
baseline=json.loads((out/'baseline-inspection.json').read_text(encoding='utf8'))['graphs']['/Game/Blueprints/BP_TutorialIntro']
baseline={n['name']:n for n in baseline if n['graph']=='EventGraph'}
after=json.loads((out/'intro-graph-after.json').read_text(encoding='utf8'))
def normalize_links(links):
    links=' '.join(links) if isinstance(links,list) else links
    return [{'node':name,'index':int(index),'direction':'<EdGraphPinDirection.'+('EGPD_INPUT: 0>' if direction=='EGPD_Input' else 'EGPD_OUTPUT: 1>')} for name,index,direction in re.findall(r"EventGraph\.([^']+)'\", index_id: (\d+), direction: (\w+)",links)]
for n in before:
    n.pop('position',None)
    for side in ['inputs','outputs']:
        for p in n[side]:
            p.pop('pin',None);p['links']=normalize_links(p['links'])
            if side=='inputs':p['value']=next(q['value'] for q in baseline[n['name']]['inputs'] if q['name']==p['name'])
(out/'intro-graph-before.json').write_text(json.dumps(before,ensure_ascii=False,indent=2),encoding='utf8')
before_by={n['name']:n for n in before};after_by={n['name']:n for n in after}
changes=[]
for name,n in before_by.items():
    assert name in after_by,'Original node deleted: '+name
    for side in ['inputs','outputs']:
        for p in n[side]:
            q=next(x for x in after_by[name][side] if x['name']==p['name'])
            if p!=q:changes.append({'node':name,'side':side,'before':p,'after':q})
data=json.loads((out/'saved-intro-api-run1/observations.json').read_text(encoding='utf8'))
initial=[s for s in data['samples'] if s.get('phase')=='initial' and s.get('intro_exists')]
playing=[s for s in initial if s['intro_playing']]
normal=initial[-1]
retry=[s for s in data['samples'] if s['phase']=='retry' and not s['intro_player']]
last=retry[-1]
cut_changes=[]
for s in initial:
    if not cut_changes or cut_changes[-1]['camera']!=s['view']:cut_changes.append({'sequence_seconds':s.get('sequence_seconds'),'camera':s['view']})
phases={}
for name,start,end in [('sleep',0,2.95),('wake',3,5.1),('stand',12.5,14.3),('walk',14.3,15.7),('jump',17.7,19),('land',19,20.2)]:
    rows=[s for s in playing if start<=s['sequence_seconds']<end]
    phases[name]={'samples':len(rows),'distinct_head_local_positions':len(set(tuple(s['head_local']) for s in rows)),'actor_locations':[s['location'] for s in rows]}
assert all(v['samples'] for v in phases.values())
print('POSE_PHASES',json.dumps(phases))
assert all(len(s['bindings']['BP_Cat_Player'])==1 and s['bindings']['BP_Cat_Player'][0]==s['cat'] for s in playing)
assert all(not s['intro_player'] and 'WBP_Tutorial_KeyHint_C' not in s['widgets'] for s in retry)
assert normal['animation_instance']==last['animation_instance']=='ABP_Cat_Final_C'
assert normal['view']==last['view']=='BP_QuarterViewCamera_C_0'
assert normal['camera_width']==last['camera_width']==900
assert not normal['move_ignored'] and not last['move_ignored']
assert normal['location'][:2]==last['location'][:2]==[170,-95]
assert abs(normal['location'][2]-last['location'][2])<1
assert 'WBP_Tutorial_KeyHint_C' in normal['widgets']
assert last['movement']=='<MovementMode.MOVE_WALKING: 1>'
seq_rel='Content/Cinematics/LS_Tutorial.uasset'
seq_git=subprocess.check_output(['git','show','HEAD:'+seq_rel],cwd=root)
seq_unchanged=hashlib.sha256(seq_git).digest()==hashlib.sha256((root/seq_rel).read_bytes()).digest()
assert seq_unchanged
summary={'status':'PASS_WITH_DOCUMENTED_FLOOR_TOLERANCE','original_probe_error_preserved':data['error'],'original_probe_retry_complete':data['retry_complete'],'scope':'Native API route, not OS Start button/key input','original_nodes_preserved':len(before),'added_nodes':[n['name'] for n in after if n['name'] not in before_by],'changed_original_pins':changes,'sequence_bytes_match_HEAD':seq_unchanged,'samples':len(data['samples']),'camera_cuts':cut_changes,'pose_checks':phases,'normal_completion':normal,'retry_completion':last,'authored_transform':{'location':[170,-95,23.5],'yaw':90},'settled_z_difference':last['location'][2]-normal['location'][2],'interpretation':'Character floor/capsule collision resolves authored23.5 to26.25 after original FinishIntro and26.5 after collision-safe native TeleportTo; original floor and collision untouched.'}
(out/'intro-validation-summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps({k:v for k,v in summary.items() if k not in ['changed_original_pins','normal_completion','retry_completion','pose_checks']},ensure_ascii=True,indent=2))
