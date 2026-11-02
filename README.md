# 부자의 심리학 — 쇼츠 제작 코드

책에서 얻은 생각을 우화·비유·현대극으로 풀어내는 쇼츠의 제작 스크립트와 PC용 관리페이지다. 현재까지 4편의 제작 코드와 대본, 채널 기획·창작 규칙을 보관한다.

## 구성

- `manager/`: Python 표준 라이브러리 기반 관리페이지, 보관함 메타데이터, 실제 제작 진행 기록 명령.
- `episode-001/` ~ `episode-004/`: 편별 대본·연출, 이미지·모션 입력문, 음성 정렬·그래픽·편집·검수 코드와 자막.
- `스토리_창작_규칙.md`: 주제 선정·제목·대본 전개의 현재 단일 기준(2026-11-03 개정).
- `AGENTS.md`: 제작·도구 사용 규칙. vidIQ 사용은 금지한다.
- `handoff.md`: 현재 제작 상태와 다음 행동. 첫머리의 최신 요약을 따른다.
- `근거/`: 벤치마킹 분석 문서와 공개 영상 목록. `근거/채널3종_20261102/분석.md`가 현재 기준의 근거다. 참고 영상의 자막 원자료는 로컬에 보존한다.

## 관리페이지 실행

Python 3.10 이상에서 저장소 루트 기준으로 실행한다. 관리페이지 자체에는 외부 Python 패키지가 필요하지 않다.

```powershell
python manager/server.py
```

브라우저에서 `http://127.0.0.1:8901`을 열면 된다. 이 주소는 로컬 실행용이다. 외부 공유 시에는 `AGENTS.md`의 Cloudflare 주소 검증 규칙을 따른다. Windows의 `manager/관리페이지 열기.cmd`는 기존 Codex Python 런타임을 사용하는 로컬 실행 보조 파일이다.

`manager/library.json`과 `manager/production.json`은 초기 업로드 시점의 보관함·진행 상태를 포함한다. 상태 표시는 제작을 자동으로 실행하지 않는다. 기존 보류·중지·완료 기록을 읽고 작업한다.

## macOS 제작 환경 준비

```bash
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python pillow numpy faster-whisper
brew install ffmpeg
brew install --cask font-noto-sans-kr font-noto-serif-kr
```

- 글꼴·음성 정렬 모델 경로는 `platform_paths.py`가 Windows/macOS를 구분해 찾는다(episode-002~004 스크립트 적용). 001의 이전 스크립트는 기록용으로 Windows 경로를 그대로 둔다.
- faster-whisper `small` 모델은 macOS에서 `~/.cache/wistom_shorts/faster-whisper`에 둔다. 다른 위치는 `WHISPER_MODEL_DIR` 환경변수로 지정한다.
- 편별 스크립트는 `.venv/bin/python episode-00N/<스크립트>.py`로 실행한다.

## 제작 환경과 파일

영상 제작 코드는 편마다 사용한 입력과 수정 이력을 보존한 개별 스크립트다. 해당 편의 `대본과_연출.md`와 코드의 입력 경로를 먼저 확인한다.

- 그래픽·편집: Pillow, NumPy, FFmpeg/FFprobe.
- 음성 정렬: faster-whisper와 기존 로컬 모델 파일.
- 글꼴: Windows에 설치된 Noto Sans KR·Noto Serif KR 등. 일부 이전 스크립트는 맑은 고딕·한컴 글꼴을 참조한다.
- 일부 정렬 스크립트의 모델 경로와 실행 보조 파일은 기존 제작 PC 환경을 참조한다. 다른 PC에서는 설치 위치를 확인해야 한다.

영상·음성·원화·대표 이미지·검수 이미지 등 약 1.2GB의 생성 미디어와 캐시·로그·중간 검수 결과는 Git에서 제외한다. 이 파일들은 기존 제작 폴더에 그대로 보존한다. 새 clone에서 보관함의 실제 영상 재생이나 최종본 재렌더를 하려면 해당 미디어를 별도로 복사해야 한다. 필요한 최종 영상·대표 이미지의 상대 경로는 `manager/library.json`에 있다.

이미지·모션·TTS의 웹 생성은 현재 로그인된 Chrome에서 해당 편의 제작 지침에 따라 진행하며, 이 저장소를 내려받거나 관리페이지를 실행하는 것만으로 생성·게시·예약을 시작하지 않는다.
