"""Accept root's saved integration evidence without replaying editor scenarios."""
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]/'Saved/Prototype20261104/Task5'
def read(folder):
    data=json.loads((ROOT/folder/'observations.json').read_text(encoding='utf8'))
    assert data.get('error') is None,(folder,data.get('error'))
    return data

def main():
    exits=read('ExitOverlaps02')
    assert exits['success'] and exits['saw_intro'] and exits['saw_stairs']
    names=[x['name'] for x in exits['events']]
    for name in ('automatic-stage1-arrival','automatic-stage2-arrival','stage2-complete-without-stage3'):
        assert names.count(name)==1,(name,names)
    clear=[x for x in exits['events'] if x['name']=='checkpoint-clearance']
    assert len(clear)==3 and all(x['blocking_hit'] is None and len(x['floor_point'])==3 for x in clear)
    manual=read('ManualInputs01');assert manual['final']
    baskets={}
    for world,width in (('Tutorial',900),('Stage1',1035)):
        rows=[s for s in manual['samples'] if s['world'].endswith('.'+world)]
        phases={s.get('basket',{}).get('phase','') for s in rows}
        assert all(any(name in phase for phase in phases) for name in ('OUTSIDE','ENTERING','HIDDEN','EXITING'))
        last=rows[-1]
        assert last['collision'] and 'WALKING' in last['movement'] and not last['move_ignored']
        assert last['animation']['class']=='ABP_Cat_Final_C'
        assert last['camera']['ortho_width']==width and not last['basket']['busy'] and not last['basket']['hidden']
        baskets[world]={'sample_count':len(rows),'phases':sorted(phases),'restored':True,'camera_width':width}
    statue=read('PhysicalStatue01');last=statue['samples'][-1]
    assert statue['ratio']<.8 and any(sum(abs(x) for x in s['input'])>.01 for s in statue['samples'])
    assert last['complete'] and last['pressed'] and last['gate_offset']<=-279
    assert last['phase']=='INACTIVE' and not last['move_ignored'] and last['view']=='BP_QuarterViewCamera_C_0'
    assert set(statue['shots'])=={'TO_GATE','OPENING','RETURNING','INACTIVE'}
    inputs=[json.loads(line) for line in (ROOT/'os-inputs.jsonl').read_text(encoding='utf-8-sig').splitlines() if line]
    for checkpoint in ('tutorial-basket-entry','tutorial-basket-exit','stage1-basket-entry-retry','stage1-basket-exit','stage2-A-threshold-push','stage2-bell'):
        assert any(x['checkpoint']==checkpoint for x in inputs),checkpoint
    result={'accepted':True,'scope':'Saved root OS-input/overlap evidence acceptance; not a replay or full keyboard walkthrough',
            'exit_samples':len(exits['samples']),'manual_samples':manual['sample_count'],'baskets':baskets,
            'statue_samples':len(statue['samples']),'statue_final':last,'os_inputs':len(inputs),
            'stage2_manual_final_boundary':'Observer ended during subsequent armor capture after bell; no final restore assertion from that row'}
    (ROOT/'root-evidence-acceptance.json').write_text(json.dumps(result,indent=2),encoding='utf8')
    print(json.dumps(result))

if __name__=='__main__':main()
