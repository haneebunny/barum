# preflight: 푸시 전 검사

푸시하기 전에 유출 방지와 기본 품질을 한 번에 검사하는 게이트다. 검사만 하고 git 명령은 대신 실행하지 않는다. 모두 통과하면 마지막에 복사해서 쓸 git 명령을 보여준다.

## 실행

맥/리눅스:

```bash
./preflight.sh
```

윈도우 PowerShell:

```powershell
.\preflight.ps1
```

빌드까지 확인 (배포 전이나 프론트를 크게 바꿨을 때, 느림):

```bash
./preflight.sh --build
```

윈도우는 `.\preflight.ps1 --build`. 옵션은 두 OS 모두 `--build`로 같다.

## 무엇을 검사하나

### 1. 유출 방지 스캔

차단(FAIL):

- 비밀 파일이 추적/스테이징됨: 실제 `.env`, `*.key`, `*.pem` 등. `.env.example`은 정상으로 봐준다.
- 하드코딩된 키: OpenAI(`sk-`), Gemini(`AIza`), AWS, GitHub, Slack 토큰.
- 민감 문서/대용량 데이터: `.docx`, `.hwp`, `.xlsx` 등 문서, 2MB 넘는 데이터 파일(`.csv`, `.zip` 등).

경고(WARN, 막지 않음):

- 이메일(PII): 소스에 박힌 이메일 주소.
- 추적 안 된 민감 파일: 아직 add 안 했지만 민감해 보이는 파일. 실수로 add 하지 말라는 알림.
- 5MB 넘는 큰 파일.

### 2. 품질 검사

- 백엔드 문법검사: `python -m compileall` (실패 시 차단).
- 백엔드 테스트: `pytest`가 있으면 실행, 없으면 건너뛴다.
- 프론트 lint: `npm run lint` (실패 시 차단).
- 프론트 build: `--build`를 줬을 때만 `npm run build` (실패 시 차단).

## 결과 읽기

- 전부 통과: 종료코드 0. 마지막에 `git add`/`commit`/`push` 안내가 뜬다.
- 차단이 하나라도 있으면: 종료코드 1로 멈추고 git 안내를 띄우지 않는다. 위에 뜬 사유를 고치고 다시 실행한다.
- 경고는 막지 않는다. 확인만 하고 넘어간다.

## 오탐(잘못 잡힘) 처리

일부러 커밋해야 하는 파일이거나, 키처럼 보이지만 진짜 비밀이 아니면:

- 파일 통째로 봐주기: `scripts/preflight.py`의 `ALLOWLIST`에 저장소 기준 경로를 추가한다.
- 한 줄만 봐주기: 그 줄에 `preflight-allow` 표시를 단다. 예: `sample = "sk-not-a-real-key"  # preflight-allow`

## 파일

- `scripts/preflight.py`: 검사 로직 전부. 크로스 플랫폼.
- `preflight.sh`: 맥/리눅스 런처.
- `preflight.ps1`: 윈도우 런처.

로직은 파이썬 한 곳에만 있고 런처 둘은 파이썬을 호출만 한다. 검사 내용을 바꾸려면 `preflight.py`만 고치면 된다.

## 문제 해결

- "pytest 건너뜀": 테스트를 돌리려면 backend 가상환경에 pytest가 있어야 한다. 스크립트가 `backend/venv` 등을 자동으로 찾는다.
- "node_modules 없음": `cd frontend && npm install` 후 다시 실행한다.
- 윈도우에서 `.ps1` 실행이 막히면: `powershell -ExecutionPolicy Bypass -File .\preflight.ps1`

## 자동 실행(선택)

지금은 손으로 돌리는 방식이다. 푸시할 때마다 자동으로 돌게 하려면 git `pre-push` 훅에 연결할 수 있다. 필요하면 별도로 요청한다.
