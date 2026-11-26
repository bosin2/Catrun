import json
# Stage3Polish20261126: builds BP_S3Polish_Presenter graphs node-by-node through the Unreal MCP
# BlueprintTools (the DSL cannot wire exec pins in the Korean editor locale).
# Cosmetic only: reads CatrunStage3Objectives / CatrunStatuePuzzle state, never writes gameplay state.
BT = 'editor_toolset.toolsets.blueprint.BlueprintTools.'
BP = {'refPath': '/Game/Environment/Stage3/Polish_20261126/BP_S3Polish_Presenter.BP_S3Polish_Presenter'}
LATCH = '/Game/Audio/CatAudioDirector/CAD_20261125_053416_46364406/SW_dock_latch.SW_dock_latch'
LIFT = '/Game/Audio/CatAudioDirector/CAD_20261125_053416_46364406/SW_lift_departure.SW_lift_departure'
CSD = '/Game/Environment/Stage2/GameplayPolish_20261125/Presentation/CameraShakeCorrection_20261125/'
MOTION = CSD + 'CS_GateMotion.CS_GateMotion_C'
IMPACT = CSD + 'CS_GateImpact.CS_GateImpact_C'
T = {
    'time': '유틸리티|시간|GetGameTimeinSeconds', 'pc': '게임|GetPlayerController', 'sin': '수학|Trig|Sin(Radians)',
    'mul': '유틸리티|연산자|곱하기', 'sub': '유틸리티|연산자|빼기', 'gt': '유틸리티|연산자|보다큼(>)',
    'and': '수학|부울|ANDBoolean', 'not': '수학|부울|NOTBoolean', 'self_valid': '유틸리티|IsValid',
    'branch': 'Utilities|FlowControl|Branch', 'self_f': '수학|플로트|SelectFloat', 'self_c': '수학|컬러|SelectColor',
    'mrc': '수학|플로트|MapRangeClamped', 'devs': 'Class|CatrunStage3Objectives|GetDevices',
    'final': 'Class|CatrunStage3Objectives|GetFinalGateOpen', 'links': 'Class|CatrunStatuePuzzle|GetLinks',
    'aget': 'Utilities|Array|Get(사본)', 'bdev': 'Utilities|Struct|BreakCatrunReleaseDevice',
    'blink': 'Utilities|Struct|BreakCatrunStatuePuzzleLink', 'cpd': '렌더링|머티리얼|SetCustomPrimitiveDataFloat',
    'inten': '렌더링|컴포넌트|라이트|SetIntensity', 'color': '렌더링|컴포넌트|라이트|SetLightColor',
    'loc': '트랜스포메이션|GetActorLocation', 'sound': '오디오|PlaySoundatLocation',
    'shake': '게임|피드백|ClientStartCameraShake', 'vec': '수학|벡터|MakeVector', 'coll': '콜리전|SetCollisionEnabled',
}
class Graph:
    def __init__(self, name):
        self.g = execute_tool(BT + 'get_graph', json.dumps({'blueprint': BP, 'graph_name': name}))['returnValue']
        self.x = 0
        self.log = []
    def clear(self, keep_entry=True):
        for n in execute_tool(BT + 'find_nodes', json.dumps({'graph': self.g, 'title': '', 'node_class': None, 'entry_points_only': False}))['returnValue']:
            info = execute_tool(BT + 'get_node_infos', json.dumps({'nodes': [n]}))['returnValue'][0]
            if keep_entry and (info['type_id'].startswith('|') or info['type_id'].startswith('이벤트추가')):
                continue
            execute_tool(BT + 'delete_node', json.dumps({'node': n}))
    def find(self, prefix):
        for n in execute_tool(BT + 'find_nodes', json.dumps({'graph': self.g, 'title': '', 'node_class': None, 'entry_points_only': True}))['returnValue']:
            info = execute_tool(BT + 'get_node_infos', json.dumps({'nodes': [n]}))['returnValue'][0]
            if info['type_id'].startswith(prefix):
                return self.wrap(n)
        raise RuntimeError('entry not found ' + prefix)
    def wrap(self, n):
        info = execute_tool(BT + 'get_node_infos', json.dumps({'nodes': [n]}))['returnValue'][0]
        return {'ref': n, 'in': {p['name']: p['pin_id'] for p in info['input_pins']},
                'out': {p['name']: p['pin_id'] for p in info['output_pins']}, 'type': info['type_id']}
    def node(self, key, **values):
        tid = T.get(key, key)
        self.x += 260
        n = execute_tool(BT + 'create_node', json.dumps({'graph': self.g, 'type_id': tid, 'pos': {'x': self.x, 'y': (self.x // 260 % 6) * 180}, 'declaring_class': None}))['returnValue']
        w = self.wrap(n)
        for k, v in values.items():
            self.val(w, k, v)
        return w
    def val(self, w, pin, v):
        if isinstance(v, dict) and 'out' in v:  # (node, pinname) not used
            raise RuntimeError('bad')
        if isinstance(v, tuple):
            self.link(v[0], v[1], w, pin)
        else:
            if isinstance(v, bool): v = 'true' if v else 'false'
            execute_tool(BT + 'set_pin_value', json.dumps({'pin': w['in'][pin], 'value': str(v)}))
    def link(self, a, apin, b, bpin):
        a2 = self.wrap(a['ref']); b2 = self.wrap(b['ref'])
        if apin not in a2['out']:
            raise RuntimeError('no out pin %s on %s: %s' % (apin, a2['type'], list(a2['out'])))
        if bpin not in b2['in']:
            raise RuntimeError('no in pin %s on %s: %s' % (bpin, b2['type'], list(b2['in'])))
        execute_tool(BT + 'connect_pins', json.dumps({'output_pin': a2['out'][apin], 'input_pin': b2['in'][bpin]}))
    def ex(self, a, b, apin='then'):
        self.link(a, apin, b, 'execute')
def O(w, pin=None):
    if pin is None:
        pin = [k for k in w['out'] if k not in ('then',)][0]
    return (w, pin)
def var(g, name): return g.node('Variables|디폴트|Get' + name)
def setv(g, name, value):
    s = g.node('Variables|디폴트|Set' + name)
    g.val(s, name, value)
    return s
def build_begin():
    g = Graph('PresenterBegin'); g.clear()
    prev, pin = g.find('|PresenterBegin'), 'then'
    for c in ['OutsideGround', 'LockSigil0', 'LockSigil1', 'LockSigil2']:
        v = var(g, c)
        n = g.node('coll', NewType='NoCollision')
        g.val(n, 'self', O(v))
        g.ex(prev, n, pin); prev, pin = n, 'then'
def edge(g, cur, curpin, cond, prevname, body):
    """Branch(cond && !prev) -> body nodes chain; returns (join node list) tail."""
    pv = var(g, prevname)
    nt = g.node('not'); g.val(nt, 'A', O(pv))
    an = g.node('and'); g.val(an, 'A', cond); g.val(an, 'B', O(nt))
    br = g.node('branch'); g.val(br, 'Condition', O(an))
    g.ex(cur, br, curpin)
    first, last = body[0], body[-1]
    g.ex(br, first, 'then')
    for a, b in zip(body, body[1:]):
        g.ex(a, b)
    return br, last
def join(g, br, last, nxt):
    g.ex(last, nxt); g.ex(br, nxt, 'else')
def build_tick():
    g = Graph('PresenterTick'); g.clear()
    entry = g.find('|PresenterTick')
    t = g.node('time'); pc = g.node('pc', PlayerIndex=0)
    m = g.node('mul'); g.val(m, 'A', O(t)); g.val(m, 'B', 3.2)
    s = g.node('sin'); g.val(s, list(s['in'])[0], O(m))
    pulse = g.node('mrc', InRangeA=-1.0, InRangeB=1.0, OutRangeA=5.0, OutRangeB=13.0); g.val(pulse, 'Value', O(s))
    obj = var(g, 'Objectives')
    ok = g.node('self_valid'); g.val(ok, 'Object', O(obj))
    br0 = g.node('branch'); g.val(br0, 'Condition', O(ok)); g.ex(entry, br0)
    cur, curpin = br0, 'then'
    devs = g.node('devs'); g.val(devs, 'self', O(obj))
    for i in range(3):
        ag = g.node('aget'); g.val(ag, 'Array', O(devs, 'Devices')); g.val(ag, 'Dimension 1', i)
        bd = g.node('bdev'); g.val(bd, list(bd['in'])[0], O(ag, 'Output'))
        rel = O(bd, 'bReleased')
        sig = var(g, 'LockSigil%d' % i)
        sf = g.node('self_f', A=1.0, B=0.0); g.val(sf, 'bPickA', rel)
        n1 = g.node('cpd', DataIndex=0); g.val(n1, 'self', O(sig)); g.val(n1, 'Value', O(sf))
        g.ex(cur, n1, curpin)
        ll = var(g, 'LockLight%d' % i)
        si = g.node('self_f', A=3.0); g.val(si, 'B', O(pulse)); g.val(si, 'bPickA', rel)
        n2 = g.node('inten'); g.val(n2, 'self', O(ll)); g.val(n2, 'NewIntensity', O(si)); g.ex(n1, n2)
        sc = g.node('self_c', A='(R=0.350000,G=1.000000,B=0.600000,A=1.000000)', B='(R=1.000000,G=0.550000,B=0.200000,A=1.000000)'); g.val(sc, 'bPickA', rel)
        n3 = g.node('color', bSRGB=True); g.val(n3, 'self', O(ll)); g.val(n3, 'NewLightColor', O(sc)); g.ex(n2, n3)
        rl = g.node('loc'); g.val(rl, 'self', O(bd, 'Ring'))
        snd = g.node('sound', Sound=LATCH, VolumeMultiplier=0.9, PitchMultiplier=1.15); g.val(snd, 'Location', O(rl))
        br, last = edge(g, n3, 'then', rel, 'PrevRel%d' % i, [snd])
        sp = setv(g, 'PrevRel%d' % i, rel); join(g, br, last, sp)
        cur, curpin = sp, 'then'
    # final gate
    fo = g.node('final'); g.val(fo, 'self', O(obj))
    fl = g.node('vec', X=-250.0, Y=-4540.0, Z=150.0)
    sft = setv(g, 'FinalT', O(t))
    sh1 = g.node('shake', Shake=MOTION, Scale=1.6); g.val(sh1, 'self', O(pc))
    so1 = g.node('sound', Sound=LIFT, VolumeMultiplier=1.6, PitchMultiplier=0.62); g.val(so1, 'Location', O(fl))
    br, last = edge(g, cur, curpin, O(fo, 'bFinalGateOpen'), 'PrevFinal', [sft, sh1, so1])
    ft = var(g, 'FinalT'); fage = g.node('sub'); g.val(fage, 'A', O(t)); g.val(fage, 'B', O(ft))
    gt = g.node('gt'); g.val(gt, 'A', O(fage)); g.val(gt, 'B', 3.45)
    a2 = g.node('and'); g.val(a2, 'A', O(fo, 'bFinalGateOpen')); g.val(a2, 'B', O(gt))
    sfi = setv(g, 'FinalImpactDone', True)
    sh2 = g.node('shake', Shake=IMPACT, Scale=1.4); g.val(sh2, 'self', O(pc))
    so2 = g.node('sound', Sound=LATCH, VolumeMultiplier=1.6, PitchMultiplier=0.5); g.val(so2, 'Location', O(fl))
    br2, last2 = edge(g, last, 'then', O(a2), 'FinalImpactDone', [sfi, sh2, so2])
    g.ex(br, br2, 'else')
    gl2 = var(g, 'GateLight2'); fdone = var(g, 'FinalImpactDone')
    m1 = g.node('mrc', InRangeA=3.45, InRangeB=5.0, OutRangeA=40.0, OutRangeB=14.0); g.val(m1, 'Value', O(fage))
    m2 = g.node('mrc', InRangeA=0.0, InRangeB=3.4, OutRangeA=4.0, OutRangeB=22.0); g.val(m2, 'Value', O(fage))
    s1 = g.node('self_f'); g.val(s1, 'A', O(m1)); g.val(s1, 'B', O(m2)); g.val(s1, 'bPickA', O(fdone))
    s2 = g.node('self_f', B=0.0); g.val(s2, 'A', O(s1)); g.val(s2, 'bPickA', O(fo, 'bFinalGateOpen'))
    li = g.node('inten'); g.val(li, 'self', O(gl2)); g.val(li, 'NewIntensity', O(s2))
    join(g, br2, last2, li)
    spf = setv(g, 'PrevFinal', O(fo, 'bFinalGateOpen')); g.ex(li, spf)
    cur, curpin = spf, 'then'
    # D1 / D2
    pz = var(g, 'Puzzle'); okp = g.node('self_valid'); g.val(okp, 'Object', O(pz))
    brp = g.node('branch'); g.val(brp, 'Condition', O(okp)); g.ex(cur, brp, curpin)
    g.ex(br0, brp, 'else')
    cur, curpin = brp, 'then'
    links = g.node('links'); g.val(links, 'self', O(pz))
    for j in range(2):
        ag = g.node('aget'); g.val(ag, 'Array', O(links, 'Links')); g.val(ag, 'Dimension 1', j)
        bl = g.node('blink'); g.val(bl, list(bl['in'])[0], O(ag, 'Output'))
        gtj = g.node('gt'); g.val(gtj, 'A', O(bl, 'GateOffset')); g.val(gtj, 'B', 0.5)
        glc = g.node('loc'); g.val(glc, 'self', O(bl, 'Gate'))
        sh = g.node('shake', Shake=MOTION, Scale=1.0); g.val(sh, 'self', O(pc))
        so = g.node('sound', Sound=LIFT, VolumeMultiplier=1.2, PitchMultiplier=0.8); g.val(so, 'Location', O(glc))
        brA, lastA = edge(g, cur, curpin, O(gtj), 'PrevOpen%d' % j, [sh, so])
        sdt = setv(g, 'DoneT%d' % j, O(t))
        shb = g.node('shake', Shake=IMPACT, Scale=1.0); g.val(shb, 'self', O(pc))
        sob = g.node('sound', Sound=LATCH, VolumeMultiplier=1.3, PitchMultiplier=0.6); g.val(sob, 'Location', O(glc))
        brB, lastB = edge(g, lastA, 'then', O(bl, 'bCompleted'), 'PrevDone%d' % j, [sdt, shb, sob])
        g.ex(brA, brB, 'else')
        dt = var(g, 'DoneT%d' % j); age = g.node('sub'); g.val(age, 'A', O(t)); g.val(age, 'B', O(dt))
        mi = g.node('mrc', InRangeA=0.0, InRangeB=1.6, OutRangeA=26.0, OutRangeB=3.0); g.val(mi, 'Value', O(age))
        so2 = g.node('self_f', A=12.0, B=0.0); g.val(so2, 'bPickA', O(gtj))
        sd = g.node('self_f'); g.val(sd, 'A', O(mi)); g.val(sd, 'B', O(so2)); g.val(sd, 'bPickA', O(bl, 'bCompleted'))
        lj = var(g, 'GateLight%d' % j)
        li = g.node('inten'); g.val(li, 'self', O(lj)); g.val(li, 'NewIntensity', O(sd))
        join(g, brB, lastB, li)
        s1 = setv(g, 'PrevOpen%d' % j, O(gtj)); g.ex(li, s1)
        s2 = setv(g, 'PrevDone%d' % j, O(bl, 'bCompleted')); g.ex(s1, s2)
        cur, curpin = s2, 'then'
def build_events():
    g = Graph('EventGraph')
    bp_ev = g.find('이벤트추가|BeginPlay'); tk = g.find('이벤트추가|Tick')
    cb = g.node('함수호출|PresenterBegin'); g.ex(bp_ev, cb)
    ct = g.node('함수호출|PresenterTick'); g.ex(tk, ct)
def run():
    build_begin(); build_tick(); build_events()
    execute_tool(BT + 'compile_blueprint', json.dumps({'blueprint': BP, 'warnings_as_errors': False}))
    return {'ok': True}
