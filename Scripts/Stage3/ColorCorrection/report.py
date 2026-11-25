"""Publish untouched actual-camera captures and quantitative correction evidence."""
import json
import shutil
from pathlib import Path

from PIL import Image
import numpy as np

ROOT = Path(__file__).resolve().parents[3]
RUN = ROOT / 'Saved/Stage3MaterialCorrection20261125'
OUT = ROOT / 'Docs/Reviews/Stage3ColorCorrection20261125'
LABELS = {'Entrance': '입구', 'Lobby': '로비', 'Exhibition': '전시방',
          'Warehouse': '창고', 'Altar': '제단실', 'GateHall': '성문 홀'}
ROLES = {'Wall':'벽', 'Pillar':'기둥', 'Floor':'바닥', 'FloorDiamond':'바닥 마름모',
         'GateDecorStone':'성문 홀 장식 석재', 'BlackIron':'흑철', 'Brass':'황동',
         'Banner':'군기', 'Wood':'목재', 'Carpet':'카펫'}


def read(path):
    return json.loads(path.read_text(encoding='utf8'))


def main():
    before, after = [read(RUN / phase / 'report.json') for phase in ('before','after')]
    assert before['success'] and after['success'] and after['compilation_wait_completed']
    app = read(RUN / 'application.json')
    gpu = read(RUN / 'QA/basecolor_gpu.json')
    gpu_analysis = read(RUN / 'QA/gpu_analysis.json')
    loaded = read(RUN / 'QA/loaded_materials.json')
    math = read(RUN / 'QA/calibration_independent.json')
    comparison = read(RUN / 'QA/comparison.json')
    regression = read(RUN / 'regression_final/report.json')
    assert regression['success'] and all(c['passed'] for c in regression['checks'])
    assert app['map_saved'] and gpu_analysis['success'] and gpu['original_actor_set_preserved']
    assert loaded['success'] and math['success']
    assert all(c['passed'] for c in comparison['checks'] if c['name'].startswith(
        ('Actor ', 'All changed', 'Full exported')))
    OUT.mkdir(parents=True, exist_ok=True)
    camera_checks, images, sections = [], {}, []
    for b,a in zip(before['views'],after['views']):
        assert b['name']==a['name']
        errors = {key:max(abs(x-y) for x,y in zip(b[key],a[key]))
                  for key in ('cat','camera','rotation')}
        errors['camera_distance_cm']=sum((x-y)**2 for x,y in zip(b['camera'],a['camera']))**.5
        assert errors['cat'] == 0 and errors['rotation'] < .01
        assert errors['camera_distance_cm'] < 5, (b['name'],errors)
        camera_checks.append({'view':b['name'],'max_delta':errors})
        cells = []
        for phase, label in (('before','수정 전'),('after','수정 후')):
            name = f"{b['name']}_{phase}.png"
            source = RUN / phase / (b['name']+'.png')
            shutil.copy2(source, OUT / name)
            rgb=np.asarray(Image.open(source).convert('RGB'),dtype=float)
            # Display-encoded screenshot brightness is NOT material BaseColor.
            luminance=rgb @ np.array([.2126,.7152,.0722])
            valid=rgb.max(axis=2)>5
            images[name]={'mean_display_luma_nonblack':float(luminance[valid].mean()),
                          'p95_display_luma_nonblack':float(np.percentile(luminance[valid],95))}
            cells.append(f'<figure><figcaption>{label}</figcaption><img src="{name}" alt="{LABELS[b["name"]]} {label}"></figure>')
        sections.append(f'<section><h2>{LABELS[b["name"]]}</h2><div class="pair">'+''.join(cells)+'</div></section>')
    result = {'camera_comparisons':camera_checks,'screen_luma_not_basecolor':images,
              'basecolor_gpu_raw':gpu,'basecolor_gpu_analysis':gpu_analysis,
              'loaded_material_checks':loaded,'source_calibration':math,
              'world_checks':comparison['checks'], 'lighting':app['lighting'],
              'counts':{k:len(app['materials'][k]) for k in ('parents','instances','assignments','preserved_slots')}}
    result['stage3_dx12_regression']={'success':regression['success'],
        'checks':regression['checks'],'scope':regression['scope']}
    readability=read(RUN/'readability/report.json')
    assert readability['success'] and readability['compilation_wait_completed']
    result['readability_capture']=readability
    for row in readability['views']:
        name=row['name']+'.png'
        shutil.copy2(RUN/'readability'/name,OUT/name)
        sections.append(f'<section><h2>추가 가시성 확인 — {row["name"]}</h2><img src="{name}" alt="추가 실제 플레이 카메라 검사"></section>')
    (OUT/'evidence.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
    rows=[]
    for role,label in ROLES.items():
        values=[r for r in gpu['rows'] if r['role']==role]
        assert values,role
        target=', '.join(map(str,values[0]['target_srgb']))
        error=max(r['max_srgb_error'] for r in values)
        rows.append(f'| {label} | {target} | {error:.2f} |')
    delta=[c for c in comparison['checks'] if not c['passed']]
    concurrent='\n'.join('- '+p for c in delta for p in c.get('detail',[]) or [])
    text='''# Stage3 재질·조명 수정 검증 (2026-11-25)

Unreal의 Stage3 전용 부모 18개와 Material Instance 24개를 생성해 716슬롯에 적용했다.
Blender 메시, Stage3 구조·충돌·게임플레이 속성은 변경하지 않았다.
카메라는 앞선 요청대로 yaw -135°에서 45°로 반전했으며, 아래 전후 비교는 둘 다 45°다.

## 최종 Base Color

ColorTint는 목표 sRGB를 IEC 공식으로 디코딩한 **Linear RGB**, Brightness는 1이다.
최종 식은 `원본 BaseColor / 원본 Linear RGB 평균 × ColorTint × Brightness`다.
대표색은 원본 mip0 전체 텍셀의 선형 RGB 평균이며, 텍스처의 밝고 어두운 무늬까지
모두 같은 RGB로 평탄화하는 방식이 아니다. 원본 텍스처/UV/Normal/ORM과 가림 처리를 보존했다.
화면의 조명·톤매핑 결과는 이 Base Color 수치와 다르다.

| 재질 | 목표 sRGB (0–255) | 실제 GPU 최대 채널 오차 |
|---|---|---:|
'''+ '\n'.join(rows)+'''

GPU 수치는 조명·노출 전 GBuffer BaseColor를 256×256 UV 평면에서 RGBA16F로 읽어
선형 평균 후 sRGB로 변환했다. 원본 mip0 계산과 GPU 압축·밉·GBuffer 양자화는 구분한다.
저장본의 24개 인스턴스를 모두 검사했으며 허용 오차는 2.5/255다.
석재는 GPU에서도 질감 변화가 확인된다. 흑철 5종은 BaseColor 표본의 미세 편차가 0이어서
처음의 일괄 질감 검사에서 표시됐다. 변경하지 않은 원본 흑철과 보정본을 256·1024 해상도로
직접 비교하니 모두 같은 특성이었다. 색 보정으로 새로 발생한 손실은 아니며, 원시 검사
표시를 증거에 그대로 남겼다. 흑철의 원래 BaseColor 무늬가 화면에서 보인다고 주장하지 않는다.

## 조명과 실제 카메라

키/필/스카이 강도를 1.4/1.7/2.0에서 0.45/0.14/0.35로 변경했다.
스카이는 중립 회색 큐브맵, 보조등은 220/500cd에서 18/40cd, 노출은 수동·보정 0이다.
물리 카메라 노출은 끄고 광원의 위치·색·반경은 유지했다.

입구·로비·전시방·창고·제단실·성문 홀에서 실제 소유된 플레이 카메라로 촬영했다.
고양이 위치와 카메라 각도는 동일하고, 카메라 위치는 추적·렌더 타이밍에 따라
최대 4.57cm 차이가 있다. NPC 정지 시점의 포즈·시야 표시도 소폭 다를 수 있다.
비교를 위해 별도 PIE에서 고양이 위치를 고정하고 NPC 틱을 정지했다. 패키지는 저장하지 않았으며,
이 촬영 자체는 수동 전체 플레이 완료 검사가 아니다. 셰이더 컴파일 완료 후 촬영한 최종본이다.
추가로 시야 표시 밖의 성문 홀 카펫과 가림 없는 로비를 확인했다. 고양이의 귀·꼬리·윤곽과
초록 눈은 구분된다. 가장 어두운 카펫 위에서는 몸·얼굴 내부 디테일의 대비가 낮다.

[전후 화면 6곳 비교](comparison.html) · [수치와 검사 증거](evidence.json)

## 보존 검사와 동시 작업

452개 액터의 변환·메시·컴포넌트·충돌이 동일하다. 전체 T3D를 비교해 정확한 재질
슬롯 및 허용된 조명·노출 필드를 제외한 게임플레이 속성 차이가 없음을 확인했다.
원본 그래프와 실제 1,095슬롯 검사 85건, 독립 색상 계산 172건을 통과했다.
379슬롯은 지정하지 않은 재질(모르타르·강철·양초·수호상 등)이라 원본을 유지했다.

수정된 저장 맵의 DX12 PIE 회귀검사 53건도 통과했다. 실제 순찰·타이머를 관찰한 뒤
위치를 제어하는 테스트 조건에서 석상 밀기, D1/D2, 장치 3개, 고양이 당기기 애니메이션,
중단·일시정지·입력 복구 및 마지막 문을 걸어 통과하는 완료 판정을 검사했다.
수동 전체 플레이나 난이도 평가로 주장하지 않는다.

동시에 진행된 바구니 채팅에서 다음 파일이 변경되어 전체 작업 폴더의 보존 해시 검사는
이 경로들을 별도 차이로 기록했다. 이 Stage3 수정은 해당 파일을 쓰거나 커밋에 포함하지 않는다.
Stage3 FinalGuard 원본과 나머지 보호 대상은 비교 기준과 같다.

'''+concurrent+'''

## 파일 위치와 재실행

- 레벨: `/Game/Maps/Stage3`
- 새 재질: `/Game/Environment/Stage3/ColorCorrection_20261125/Instances`
- 부모: 같은 폴더의 `Parents`
- 검색어: `MI_CC_`
- 실행 지침: `Scripts/Stage3/ColorCorrection/Materials/README.md`

기존 `finalize_map.py`는 과거 조명과 장치 재질을 덮어쓰므로 수정된 레벨에 다시 실행하지 않는다.
검사 중 발견한 UE5.8 setter의 false 반환은 실제 값 재조회로 검증하도록 보완했고,
컴파일 도중의 임시 체크무늬 캡처는 최종 화면에서 제외했다.
'''
    (OUT/'README.md').write_text(text,encoding='utf8')
    page='''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Stage3 실제 플레이 카메라 전후 비교</title><style>body{margin:32px;background:#17171b;color:#eee;font:16px/1.6 system-ui}h1{font-size:24px}h2{font-size:19px}.pair{display:grid;grid-template-columns:1fr 1fr;gap:16px}figure{margin:0}img{width:100%;display:block}section{margin:32px 0}figcaption{padding:8px}a{color:#9ccaff}@media(max-width:800px){.pair{grid-template-columns:1fr}body{margin:16px}}</style>
<h1>Stage3 실제 플레이 카메라 — 수정 전 / 후</h1><p>동일한 고양이 위치와 카메라 각도. 카메라 추적 위치 최대 4.57cm 차이. 원본 캡처를 보정 없이 표시합니다. 밝기 비교 화면은 최종 Base Color 수치 검사가 아닙니다.</p><p><a href="README.md">검증 보고서</a> · <a href="evidence.json">수치 증거</a></p>'''+''.join(sections)+'</html>'
    (OUT/'comparison.html').write_text(page,encoding='utf8')
    print('STAGE3_COLOR_REPORT_OK', OUT)


if __name__=='__main__':
    main()
