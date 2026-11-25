# Cat Audio Director

《마왕님, 고양이가 도망갑니다》의 Codex 오디오 작업 도구입니다. Codex가 요청을 분해하고 BGM·SFX 담당을 병렬로 실행한 뒤, 결과를 모아 후처리 → 새 Unreal SoundWave 임포트 → QA를 진행합니다. 음악 생성 서버를 흉내 낸 별도 에이전트 프레임워크는 사용하지 않습니다.

## 바로 사용하기

Catrun 프로젝트에서 **새 Codex 채팅**을 열고 아래처럼 요청합니다. 기존 채팅에는 새 설정/스킬이 아직 로드되지 않을 수 있습니다.

> $cat-audio-director 튜토리얼 잠입 BGM과 고양이 방울 효과음을 준비해줘. BGM·SFX 담당에게 병렬로 나눠 맡기고 결과를 취합해줘. 먼저 mock으로 전체 후처리와 새 Unreal 자산 임포트를 검증해. Suno 유료 생성은 구체적인 목록과 크레딧 한도를 보여준 뒤 승인받아.

실제 파일이 있다면:

> $cat-audio-director 이 폴더의 음원을 BGM·SFX 담당에게 나눠 검토시키고, 게임용으로 후처리해서 신규 SoundWave로 적용·검증해줘. 기존 자산과 블루프린트 연결은 보존해.

총괄은 현재 대화의 Codex입니다. `.codex/agents/`의 6개 역할은 director, bgm, sfx, edit, unreal, qa입니다. 먼저 BGM/SFX를 병렬 실행하고, 편집·Unreal·QA는 결과 의존 순서로 실행합니다. 최대 하위 에이전트 3개이며 역할 지시문은 별도 보안 격리가 아닙니다. 현재 클라이언트가 사용자 정의 역할 선택을 노출하지 않으면 일반 하위 에이전트에 해당 역할 지시문을 전달하는 경로도 지원합니다.

## 설치된 구성과 범위

- Python 3.12 / Codex CLI 0.163.0 / UE 5.8.2 환경에서 확인했습니다.
- FFmpeg 9.0.1 Essentials를 WinGet으로 사용자 계정에 설치했습니다. 시스템 관리자 권한이나 게임 소스 변경이 필요하지 않습니다.
- `AGENTS.md`, `.agents/skills/cat-audio-director/SKILL.md`, `.codex/agents/cat_audio_*.toml`에 분업·보호 규칙이 있습니다.
- 기존 `.codex/config.toml`의 Unreal MCP를 보존하고 Suno 주소와 에이전트 동시 실행 설정을 추가했습니다. 글로벌 Codex 설정/Blender 설정은 변경하지 않았습니다.
- `.gitignore`에는 이 프로젝트의 검토된 Codex 설정만 공유할 수 있는 예외를 추가했습니다. 인증 토큰은 저장하지 않습니다.

지원되는 실제 적용 범위는 **새 SoundWave 임포트·루프 속성 설정·저장·메타데이터 재조회**입니다. 기존 맵/BP에 재생 연결하기, SoundCue/MetaSound 그래프 작성, 실제 청감 검수는 자동 완료로 주장하지 않습니다. 게임의 AI 청각/소리 전파 규칙도 변경하지 않습니다.

## Suno 연결 및 승인

공식 주소는 `https://api.suno.com/mcp`이며 프로젝트 설정에 등록되어 있습니다. **사용자가 연결을 보류하여 현재 `enabled = false`입니다.** 모의/로컬 작업은 그대로 사용할 수 있습니다. API 키를 프로젝트 파일에 넣지 않습니다. 나중에 연결을 요청하면 사용자 계정 로그인/접근 승인을 다음 공식 Codex 인증 흐름에서 진행합니다.

```powershell
codex -c 'mcp_servers.suno.url="https://api.suno.com/mcp"' -c 'mcp_servers.suno.enabled=true' mcp login suno
python Scripts/CatAudioDirector/inspect_suno.py
```

CLI 0.163.0의 `mcp login`은 `-C`만으로 프로젝트의 MCP 등록을 찾지 못해 위와 같이 해당 명령에만 URL을 전달합니다. 글로벌 설정은 바꾸지 않습니다. 최초 무인증 조회는 Cloudflare 403/1010, OAuth 첫 권한 목록은 invalid_scope를 반환했습니다. 호환 권한 재시도로 연결 승인 화면까지 도달했지만, 사용자의 요청으로 연결을 중단했습니다. 인증 완료·실제 도구 조회·생성·크레딧 사용은 확인하지 않았습니다. `inspect_suno.py`는 모델/제공자 도구를 호출하지 않고 Codex가 관리하는 인증 연결로 목록만 조회합니다. 인증된 목록 조회가 성공하면 `.codex/config.toml`의 Suno `enabled`를 `true`로 바꾸고 새 Catrun 채팅에서 사용합니다.

공식 문서는 음악 생성 및 계정 크레딧 조회를 설명합니다. Suno Sounds의 효과음/루프 기능은 웹앱에서 확인했지만, 이를 MCP `sounds-create` 지원으로 간주하지 않습니다. 인증 후 총괄이 `tools/list` 결과에서 음악·효과음·진행 조회·다운로드를 각각 확인하며, 없는 기능은 차단 상태로 보고합니다. 확인되지 않은 REST 경로나 도구 이름은 구현하지 않았습니다.

유료 생성 전에 총괄이 자산 목록, 실제 도구 인자, 예상 비용/불확실성, 최대 호출 수와 크레딧 한도를 제시합니다. **로그인 승인은 생성 비용 승인이 아닙니다.** 총괄만 승인된 요청을 전송하고 `Saved/CatAudioDirector/<brief-directory>/generation_ledger.json`에 승인 범위·작업 ID·호출 수·상태를 기록합니다. 타임아웃으로 제출 성공 여부가 불명확하면 재생성하지 않고 기존 작업을 확인합니다. 다운로드 도구가 없으면 검증된 결과의 파일 URL 또는 사용자가 내려받은 파일을 사용합니다.

검증된 제공자 결과가 HTTPS 다운로드 URL을 반환한 경우에만 다음 보조 도구를 사용할 수 있습니다. URL 텍스트 파일은 Git에서 제외되는 `Saved`에 두고, 실제 반환 URL/리다이렉트에서 확인한 정확한 호스트만 지정합니다. 이 도구는 Suno API를 호출하거나 로그인을 우회하지 않습니다.

```powershell
python Scripts/CatAudioDirector/download_audio.py --url-file Saved/CatAudioDirector/provider-url.txt --output Saved/CatAudioDirector/inputs/new-source.wav --allowed-host <실제-반환-호스트>
```

기존 파일 거부, 공개 HTTPS 주소/리다이렉트 검사, 256MiB 제한, 최대 3회 다운로드 재시도, SHA-256 영수증을 제공합니다. 서명된 URL과 토큰은 로그에 넣지 않습니다. 다운로드한 바이트의 실제 오디오 유효성은 다음 후처리 단계에서 판정합니다.

## 파이프라인 명령

아래 명령은 Catrun 루트에서 실행합니다. 자연어 해석·역할 위임은 Codex 스킬이 담당하며, Python은 검증 가능한 파일 처리만 수행합니다.

```powershell
# 설치/현재 실행 파일 검증
powershell -ExecutionPolicy Bypass -File Scripts/CatAudioDirector/setup.ps1
python Scripts/CatAudioDirector/cat_audio.py doctor

# 무료 모의 신호 → 실제 FFmpeg 편집 → QA. 에디터 변경 없음.
python Scripts/CatAudioDirector/cat_audio.py run --brief Scripts/CatAudioDirector/example_brief.json --mode mock

# 위 단계부터 새 Unreal 자산 임포트까지 한 번에 (에디터 필요)
python Scripts/CatAudioDirector/cat_audio.py run --brief Scripts/CatAudioDirector/example_brief.json --mode mock --apply-unreal --allow-mock

# source_path가 있는 실제 원본 파일 처리 및 신규 임포트
python Scripts/CatAudioDirector/cat_audio.py run --brief <brief.json> --mode local --apply-unreal

# 완료된 처리 결과를 별도로 임포트 / 독립 QA
python Scripts/CatAudioDirector/cat_audio.py integrate --run <run-directory> --apply
python Scripts/CatAudioDirector/cat_audio.py qa --run <run-directory>

# Unreal 연결과 실제 도구 스키마 조회 / 임포트 계획 검사만
python Scripts/CatAudioDirector/unreal_bridge.py inspect --output <report.json>
python Scripts/CatAudioDirector/unreal_bridge.py import --plan <import_plan.json>

# 회귀 테스트 / 현재 Codex 설정과 스킬 로딩 확인
python -m unittest discover -s Scripts/CatAudioDirector/tests -v
python Scripts/CatAudioDirector/verify_codex.py
# 실제 역할 호출까지 확인 (Codex 사용량 발생, Suno 생성 없음)
python Scripts/CatAudioDirector/verify_codex.py --smoke
```

`--apply-unreal`가 없으면 게임 자산을 변경하지 않습니다. mock을 Unreal에 임포트하려면 `--allow-mock`도 필요합니다. mock은 합성 테스트 톤이며 BGM/효과음 완성품이 아닙니다. `--mode local`은 네트워크를 사용하지 않습니다.

## brief.json 계약

```json
{
  "assets": [
    {
      "id": "BGM_Castle_Stealth",
      "kind": "bgm",
      "prompt": "조용한 마왕성 잠입, 보컬 없음",
      "duration_seconds": 30,
      "loop": true,
      "source_path": "C:/Audio/original.wav",
      "generation": {"provider": "suno", "job_id": "실제-반환-ID"}
    }
  ]
}
```

`source_path`는 local 모드에서 필수이고 상대 경로는 brief 파일 기준입니다. `generation`은 선택적 출처 정보입니다. 원본 파일은 수정하지 않습니다. ID는 영문자로 시작하는 영문/숫자/밑줄 64자 이하이며 대소문자 중복도 거부합니다. 한 배치 1~64개, 길이 0.05~600초, 원본 파일 최대 1GiB입니다. 루프 소스는 요청 길이에 겹침 구간(최대 0.1초)을 더한 길이가 필요합니다. 원본이 짧거나 무음이면 실패로 남기며 가짜 성공 파일을 만들지 않습니다.

기본 결과는 PCM16 WAV, 48kHz, BGM 스테레오 -18 LUFS / SFX 모노 -20 LUFS입니다. 뒤→앞 크로스페이드로 원래 요청 길이의 반복 경계를 만들고, 원샷에는 짧은 페이드를 적용합니다. 2단계 loudnorm을 사용하며 0.5초 미만 신호는 **측정 시만 0.5초로 무음 패딩**하고 결과 길이는 원래대로 유지합니다. QA에도 동일 측정 기준을 적용합니다.

QA는 길이/채널/형식, 무음, 표본·true peak, LUFS 오차(±1.5), DC, 루프 경계 차이, 파일 SHA-256 및 원래 요청 항목 누락을 검사합니다. 수치 통과는 음악적 루프나 청감 품질을 보장하지 않습니다.

## Unreal 연결과 기존 파일 보호

기존 공식 UE MCP 주소 `http://127.0.0.1:8000/mcp`를 사용합니다. 에디터가 닫혀 있으면 Catrun 에디터를 열고 MCP 서버를 켜야 합니다. 명령행 실행 시 설치된 UE의 `-ModelContextProtocolStartServer`를 사용할 수 있습니다. 프로젝트의 기존 플러그인 설정은 바꾸지 않습니다.

기본 MCP 도구에는 오디오 임포트/범용 Python 실행이 없어, 브리지는 다음 검증된 순서를 사용합니다.

1. Epic MCP initialize → tools/list → describe_toolset → 현재 레벨/PIE 조회.
2. 기존 Python 원격 설정이 loopback `127.0.0.1`인지 확인.
3. 필요한 동안만 원격 Python을 메모리에서 활성화하고 Epic의 설치된 `remote_execution.py`로 연결.
4. 실제 프로젝트/UE5.8/PIE/미저장 패키지/원본 해시/기존 자산 여부를 전체 사전 검사.
5. `/Game/Audio/CatAudioDirector/<run_id>/SW_<id>`에 새 SoundWave만 임포트·개별 저장하고 속성 확인.
6. `finally`에서 원격 설정 원복. 맵 저장·전체 저장·BP 수정 없음.

미저장 패키지가 있거나 같은 자산이 이미 있으면 중단합니다. 읽기 조회는 제한 재시도하지만 임포트는 자동 재시도하지 않습니다. 일부 성공/응답 불명확 시 보고서를 읽고 남은 자산을 확인해야 합니다. 새 실행 ID로 반복하면 **새 자산 세트**가 생기므로, 실패 원인을 확인하지 않고 반복 실행하지 마세요.

## 결과 및 실패 기록

실행마다 `Saved/CatAudioDirector/CAD_<time>_<id>/`를 만듭니다.

| 파일 | 내용 |
|---|---|
| `brief.json` | 요청 자산 목록 스냅샷 |
| `manifest.json` | 파일·해시·QA·오류·mock 여부·Unreal 진행 상태 |
| `work/<id>/` | 보존된 원본과 편집 중간 파일 |
| `final/*.wav` | 후처리 결과 |
| `import_plan.json` | 모든 파일이 QA를 통과한 경우에만 생성 |
| `logs.jsonl` | 로컬 처리 시작/실패/재시도 기록 |
| `qa_report.json` | 독립 재검증 결과 |
| `unreal_report.json` | 실제 임포트 결과 또는 실패 정보 |

이번 설치 검증 보고서는 채팅의 출력 폴더에도 별도 제공됩니다. 게임 플레이 연결/청감 검수/인증된 Suno 생성은 해당 증거가 없으면 완료로 표시하지 않습니다. 새 테스트 SoundWave는 전용 경로에 남으며 실제 게임에서 참조하지 않습니다.

## 확인 근거 (2026-11-11)

- [Codex 공식 Subagents](https://learn.chatgpt.com/docs/agent-configuration/subagents.md): 역할 TOML, 상속, 병렬 위임.
- [Codex 공식 App Server](https://learn.chatgpt.com/docs/app-server.md): 실제 config/read·skills/list 로딩 확인에 사용.
- [Suno 공식 MCP](https://suno.com/mcp), [연결 절차](https://help.suno.com/en/articles/14551425), [지원 기능](https://help.suno.com/en/articles/14551361), [크레딧 안내](https://help.suno.com/en/articles/14486145).
- [Suno Sounds](https://help.suno.com/en/articles/10625537), [다운로드 안내](https://help.suno.com/en/articles/2409921): 웹 기능과 MCP 지원 여부를 구분.
- [Epic 공식 UE 5.8 MCP](https://dev.epicgames.com/documentation/unreal-engine/unreal-mcp-in-unreal-editor?application_version=5.8), 설치된 Epic 플러그인/remote_execution.py 및 실제 에디터 조회.
- FFmpeg 설치 경로의 `ffmpeg -version`, 실제 필터 실행/회귀 테스트로 후처리 동작 검증.
