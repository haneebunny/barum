# PROGRESS_BE: 바름 백엔드 진행상황

> 성격: 백엔드 세션 진행 기록(가변). 확정 결정은 `PROJECT.md`, 전체 로드맵은 `ROADMAP.md`, 작업 규칙은 `CLAUDE.md`.
> 갱신일: 2026-08-11. 담당: 백엔드 세션(대수) / 검수: 하니.

---

## 2026-08-11 · 프론트 연동 지원물 (OpenAPI + 픽스처)

브랜치: `feature/be-frontend-fixtures` (`feature/be-prompt-judge` 위에 stacked, unjudged 필드 의존). push·PR 대기.
목적: 0비용·0의존으로 프론트(정빈)·디자이너를 언블록. 판정 알맹이 없이도 계약(응답 형태)에 바로 붙게 한다.
지시: PM(A 먼저).

### 무엇을 만들었나
- **`scripts/dump_openapi.py`** → `backend/openapi.json`: API 스펙 파일. 프론트가 타입 생성·목킹에 쓴다. (서버 뜨면 `/openapi.json`·`/docs`로도 제공.)
- **`scripts/make_fixtures.py`** → `backend/fixtures/`: 샘플 CheckReport 3종. 모델로 조립해 스키마 100% 유효.
  - `check_report_image.json` — 이미지 입력(타일 하이라이트), 1·2·4호 골고루.
  - `check_report_text.json` — 문구-only(스팬 하이라이트, tile=null).
  - `check_report_with_unjudged.json` — 미판정 상태 포함('재검사 필요' UI용).
- **`docs/api/README.md`**: 엔드포인트 계약 한 장 + 하이라이트 2모드 + enum 값 + 실행법.
- **`tests/test_fixtures.py`**: 픽스처가 계약을 지키는지 검증(모델 바뀌면 여기서 잡음).

### 검증
- `pytest tests/ -q` → **35 passed** (신규 픽스처 5). OpenAPI: multipart 요청 + CheckReport 응답 + 스키마 11종 확인.

### 다음
- 하니 리뷰 반영. prompt-judge 머지되면 이 PR base를 main으로 재지정.
- 이어서 C(규칙집 구조/파서)는 대수와 콘텐츠 형태 합의 후.

---

## 2026-08-11 · VLM 프롬프트 판정기 (PromptJudge)

브랜치: `feature/be-prompt-judge` (origin/main 기준). push·PR 대기.
목적: 규칙집(RAG) 없이도 지금 실판정. StubJudge를 실동작 판정기로 대체해 데모를 end-to-end로 돌린다.

### 무엇을 만들었나
- **`PromptJudge`** (`judge/cosmetic.py`): VLM 제로샷 판정. `score_eval.py`의 검증된 `JUDGE_PROMPT`를 공유(원본을 cosmetic.py로 옮기고 score_eval이 import). 문장 배치(기본 12) 판정 → 위반 라벨만 Finding.
- **판정기 슬롯 계약 변경**: `CosmeticJudge.judge`가 `JudgeResult{findings, unjudged}` 반환. StubJudge도 맞춤.
- **미판정(unjudged) 표현**: 모델 `models.py`에 `UnjudgedSentence` + `CheckReport.unjudged` + `Summary.n_unjudged` 추가.
- **API 배선**: 기본 judge = PromptJudge(JUDGE_PROVIDER, 기본 Gemini). 오프라인/키없음용 `JUDGE_KIND=stub` 스위치.

### 핵심 결정: 배치 실패는 '스킵'이 아니라 '미판정'
recall 우선이라 판정 실패 문장을 조용히 버리면 '합법'으로 오인돼 미탐이 숨는다. 그래서:
- VLM 호출은 재시도 안 함(과금 정책). 하지만 실패 문장을 드롭하지 않고 `unjudged`로 남겨 '재검사 필요'로 드러낸다.
- 모델이 결과를 빠뜨리거나 규격 밖 라벨을 줘도 합법으로 삼키지 않고 미판정 처리.

### 결정점 (하니 승인, veto 가능)
1. span = 전체 문장 (프롬프트가 문장 단위 라벨). span 정밀추출은 후순위.
2. risk = 유형별 고정 매핑(1호=고, 2호=중, 4호=중). 프롬프트가 위험도 안 줌.
3. 배치 ~12문장, 실패 시 미판정.

### 검증 결과
- `pytest tests/ -q` → **30 passed** (신규 test_judge 5 포함). VLM은 가짜 어댑터 주입.
- score_eval `--dry` 정상(공유 프롬프트 일치).
- **실판정 스모크(Gemini)**: 텍스트 4문장 → 3위반(2호 주름개선·1호 아토피치료·4호 3배) 정확, 보습크림은 합법. 실이미지(OCR+판정 2회) → 6문장 4위반(완벽한→4호, 탄력→2호, 파워수분→4호, 진정→1호), 미판정 0, 에러 없음.

### 다음
- (여전히 블로커) 규칙집 완성 → `RagJudge`로 근거 조항·성분정합 정밀화. PromptJudge는 그 전까지의 실판정 베이스라인.
- 규칙집+실judge 후 43문장 Gemini vs GPT 비교표(과금, 하니 승인).

---

## 2026-08-11 · 판정 백엔드 API 골격 (규칙집 없이 선구축)

브랜치: `feature/be-api-skeleton` (로컬 커밋 `52e1367`, push·PR 대기).
지시: `docs/handoffs/2026-08-11-backend-api-skeleton.md`.
로드맵 위치: 2주차 "판정 프로그램" + "화면 뼈대 넘김"의 선행 골격. 규칙집(1주차 크리티컬 패스) 대기 중에 그 주변을 먼저 만들어 프론트를 언블록하는 작업.

### 무엇을 만들었나
- **I/O 계약(Pydantic)** `src/barum/models.py`: `CheckReport` · `Finding` · `Summary` · `Location` · enum(`Region`·`ViolationType`·`RiskLevel`).
- **FastAPI 스켈레톤** `src/barum/api/app.py`: `POST /check`(multipart, 동기) + `GET /health`.
- **파이프라인 배선** `src/barum/pipeline.py`: 이미지 → tile_split → OCR(vlm) → 문장 → judge → 리포트. 텍스트 경로 포함.
- **Judge 슬롯** `src/barum/judge/cosmetic.py`: `CosmeticJudge` 프로토콜 + `StubJudge`(더미).
- **실행/테스트**: `scripts/run_api.py`, `conftest.py`, `tests/test_{models,pipeline,api}.py`.

### 확정 사항 (이번 인터뷰, 하니 승인)
- **위반유형 enum = 5값**: `합법` + `1호_의약품오인` + `2호_기능성오인` + `4호_거짓과장기만` + `대상외`. 화장품 체계라 3호 없음(`reference/cosmetic_kr` 기준). 직렬화 값은 한국어 라벨(score_eval·reference와 일치).
- **입력 = multipart/form-data**: `region`(form) + `ad_text`(form, optional) + `image`(UploadFile, optional). 둘 다 없으면 422. base64 안 씀.
- **동기 응답**. stateless 정합·데모 규모·프론트 fetch 한 번·되돌릴 수 있음이 근거. 타임아웃 넉넉히(keep-alive 120s).
- **Provider = env 스왑**(`OCR_PROVIDER`/`JUDGE_PROVIDER`), 기본값 **Gemini**. GPT 하드코딩 안 함. 로드맵 "판정 AI=Gemini 무료 키" 원칙.
- **Supabase 안 붙임**. 자가검증=요청/응답이라 DB 불필요. 현 `schema.sql`은 식품 감시용이라 형태 안 맞음.

### 착수 중 default로 정한 것 (하니 veto 가능)
1. `location = {tile, order}`. OCR이 bbox를 안 줘 좌표 대신 타일명+문장순서.
2. 이미지+글 둘 다 오면 이미지 문장 뒤에 글 문장 append(order 이어짐).
3. CORS `allow_origins=["*"]`. 프론트 dev 서버 언블록용. 서비스화 때 좁힘.

### 검증 결과
- `pytest tests/ -q` → **25 passed**(신규 13 + 기존 검수기 12). VLM은 목킹 없이 가짜 어댑터 주입으로 순수 로직만.
- 서버 스모크: `/health` ok, 텍스트 `/check` 200, 빈 입력 422, region 밖 값 422.
- **실이미지 OCR 스모크**(Gemini 1회, `08_24505724_detail_007.png` 1타일): 6문장 추출 → 1건 판정(StubJudge). `location.tile` 채워짐. 이미지→타일→OCR 실동작 확인.

### 실행법
```bash
cd backend
./venv/bin/python scripts/run_api.py            # 0.0.0.0:8000
./venv/bin/python -m pytest tests/ -q
```
> ⚠️ venv의 `pip` 스크립트 shebang이 리네임 전 경로(`final-project/venv`)를 물고 있어 깨져 있음. 의존성 설치는 `./venv/bin/python -m pip install ...`로 우회. venv 재생성 여부는 하니 판단 대기.

### 안 한 것 (이번 컷)
실제 판정 로직(규칙집 RAG), Supabase/DB, 인증, 리포트 UI, 미국 세부 규제, Gemini vs GPT 비교표 실행.

### 다음
- (블로커) 규칙집(레퍼런스팩) 완성 → `RagJudge`를 `judge/cosmetic.py` 슬롯에 구현. 나머지 코드 불변.
- 규칙집+실judge 붙은 뒤 43문장으로 Gemini vs GPT 비교표(과금, 하니 승인).
- 프론트(정빈)가 `CheckReport` 스키마에 붙기 시작.
