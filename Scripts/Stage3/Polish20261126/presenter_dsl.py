"""Blueprint DSL generator for BP_S3Polish_Presenter (Stage3 door/lock presentation).
Cosmetic only: reads Objectives/Puzzle state; never writes gameplay state.
Korean-locale editor: member access uses Variables|디폴트|Get/Set."""
LATCH = '"/Game/Audio/CatAudioDirector/CAD_20261125_053416_46364406/SW_dock_latch.SW_dock_latch"'
LIFT = '"/Game/Audio/CatAudioDirector/CAD_20261125_053416_46364406/SW_lift_departure.SW_lift_departure"'
CS = '/Game/Environment/Stage2/GameplayPolish_20261125/Presentation/CameraShakeCorrection_20261125/'
MOTION = '"%sCS_GateMotion.CS_GateMotion_C"' % CS
IMPACT = '"%sCS_GateImpact.CS_GateImpact_C"' % CS
def G(n): return '(Variables|디폴트|Get%s)' % n
def S(n, v): return '(Variables|디폴트|Set%s %s)' % (n, v)
def color(r, g, b): return '(Utilities|Struct|MakeLinearColor :R %s :G %s :B %s :A 1.0)' % (r, g, b)
def shake(cls, scale): return '(게임|피드백|ClientStartCameraShake :self pc :Shake %s :Scale %s)' % (cls, scale)
def sound(snd, loc, vol, pitch): return '(오디오|PlaySoundatLocation :Sound %s :Location %s :VolumeMultiplier %s :PitchMultiplier %s)' % (snd, loc, vol, pitch)
def begin():
    return '(fn PresenterBegin ()\n' + '\n'.join('  (콜리전|SetCollisionEnabled :self %s :NewType "NoCollision")' % G(c) for c in ['OutsideGround', 'LockSigil0', 'LockSigil1', 'LockSigil2']) + ')'
def tick():
    L = ['(fn PresenterTick ()',
         '  (bind t (유틸리티|시간|GetGameTimeinSeconds))',
         '  (bind pc (게임|GetPlayerController :PlayerIndex 0))',
         '  (bind wave (수학|Trig|Sin(Radians) (* t 3.2)))',
         '  (bind obj %s)' % G('Objectives'),
         '  (if (유틸리티|IsValid obj)',
         '    (bind devs (Class|CatrunStage3Objectives|GetDevices :self obj))']
    for i in range(3):
        L += ['    (bind dv%d (Utilities|Array|Get(사본) devs %d))' % (i, i),
              '    (bind (h%d r%d p%d b%d c%d rel%d) (Utilities|Struct|BreakCatrunReleaseDevice dv%d))' % ((i,) * 7),
              '    (렌더링|머티리얼|SetCustomPrimitiveDataFloat :self %s :DataIndex 0 :Value (select rel%d 1.0 0.0))' % (G('LockSigil%d' % i), i),
              '    (bind ll%d %s)' % (i, G('LockLight%d' % i)),
              '    (렌더링|컴포넌트|라이트|SetIntensity :self ll%d :NewIntensity (select rel%d 3.0 (+ 9.0 (* 4.0 wave))))' % (i, i),
              '    (렌더링|컴포넌트|라이트|SetLightColor :self ll%d :NewLightColor (select rel%d %s %s) :bSRGB true)' % (i, i, color(0.35, 1.0, 0.6), color(1.0, 0.55, 0.2)),
              '    (if (and rel%d (not %s))' % (i, G('PrevRel%d' % i)),
              '      (bind rl%d (트랜스포메이션|GetActorLocation :self r%d))' % (i, i),
              '      %s)' % sound(LATCH, 'rl%d' % i, 0.9, 1.15),
              '    %s' % S('PrevRel%d' % i, 'rel%d' % i)]
    L += ['    (bind fo (Class|CatrunStage3Objectives|GetFinalGateOpen :self obj))',
          '    (bind fl (수학|벡터|MakeVector :X -250.0 :Y -4540.0 :Z 150.0))',
          '    (if (and fo (not %s))' % G('PrevFinal'),
          '      %s' % S('FinalT', 't'),
          '      %s' % shake(MOTION, 1.6),
          '      %s)' % sound(LIFT, 'fl', 1.6, 0.62),
          '    (bind fage (- t %s))' % G('FinalT'),
          '    (bind fdone %s)' % G('FinalImpactDone'),
          '    (if (and fo (and (not fdone) (> fage 3.45)))',
          '      %s' % S('FinalImpactDone', 'true'),
          '      %s' % shake(IMPACT, 1.4),
          '      %s)' % sound(LATCH, 'fl', 1.6, 0.5),
          '    (렌더링|컴포넌트|라이트|SetIntensity :self %s :NewIntensity (select fo (select %s (수학|플로트|MapRangeClamped fage 3.45 5.0 40.0 14.0) (수학|플로트|MapRangeClamped fage 0.0 3.4 4.0 22.0)) 0.0))' % (G('GateLight2'), G('FinalImpactDone')),
          '    %s)' % S('PrevFinal', 'fo'),
          '  (bind pz %s)' % G('Puzzle'),
          '  (if (유틸리티|IsValid pz)',
          '    (bind links (Class|CatrunStatuePuzzle|GetLinks :self pz))']
    for j in range(2):
        L += ['    (bind lk%d (Utilities|Array|Get(사본) links %d))' % (j, j),
              '    (bind (pid%d st%d pl%d gate%d pr%d ex%d ch%d sa%d gf%d rg%d off%d done%d rp%d rv%d) (Utilities|Struct|BreakCatrunStatuePuzzleLink lk%d))' % ((j,) * 15),
              '    (bind open%d (> off%d 0.5))' % (j, j),
              '    (if (and open%d (not %s))' % (j, G('PrevOpen%d' % j)),
              '      (bind gl%d (트랜스포메이션|GetActorLocation :self gate%d))' % (j, j),
              '      %s' % shake(MOTION, 1.0),
              '      %s)' % sound(LIFT, 'gl%d' % j, 1.2, 0.8),
              '    (if (and done%d (not %s))' % (j, G('PrevDone%d' % j)),
              '      %s' % S('DoneT%d' % j, 't'),
              '      (bind gm%d (트랜스포메이션|GetActorLocation :self gate%d))' % (j, j),
              '      %s' % shake(IMPACT, 1.0),
              '      %s)' % sound(LATCH, 'gm%d' % j, 1.3, 0.6),
              '    (렌더링|컴포넌트|라이트|SetIntensity :self %s :NewIntensity (select done%d (수학|플로트|MapRangeClamped (- t %s) 0.0 1.6 26.0 3.0) (select open%d 12.0 0.0)))' % (G('GateLight%d' % j), j, G('DoneT%d' % j), j),
              '    %s' % S('PrevOpen%d' % j, 'open%d' % j),
              '    %s' % S('PrevDone%d' % j, 'done%d' % j)]
    L[-1] += '))'
    return '\n'.join(L)
