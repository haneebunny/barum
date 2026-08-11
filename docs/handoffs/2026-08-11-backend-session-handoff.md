# 백엔드 세션 인수인계 (2026-08-11)

> 받는 사람: 다음 barum 백엔드 세션. 정리: 이전 백엔드 세션(Claude). 결정권자: 하니. 조율: PM.
> 목적: 백엔드 담당 역할을 넘긴다. 이 문서 하나로 현 상태·다음 할 일·주의점을 파악할 수 있게.

## 0. 너의 역할
바름 **백엔드 세션 담당**. 판정 파이프라인·API·레퍼런스 연동을 만든다.
- 착수 규칙: `CLAUDE.md` (코드 전에 인터뷰·단계별 계획·승인 대기, 안 정한 값은 하니에게, em-dash 금지·한국어 짧게).
- Git 규칙: `AGENTS.md` (`feature/be-...` 브랜치 → PR 리뷰어 **haneebunny** → 하니 머지. **main 직접 push 금지**).
- 전체 로드맵 `ROADMAP.md`, 확정 결정 `PROJECT.md`, 진행기록 `PROGRESS_BE.md`.
- 지시·질문은 **PM 2 세션**(`local_18212817-5ee9-49e9-9a6a-802c3623b1c1`, 제목 "PM 2 (현 PM)")에게. PM 1은 옛 세션이니 쓰지 말 것.

## 1. 지금까지 만든 것 (전부 main 머지 완료)

**API·계약** (`backend/src/barum/`)
- `api/app.py` — FastAPI. `POST /check`(multipart: region·ad_text?·image?·ingredients?) + `GET /health`. 동기. CORS 전체허용(개발용).
- `models.py` — I/O 계약(Pydantic). `CheckReport{findings, unjudged, summary}`, `Finding{span, sentence, violation_type, legal_basis, flag, explanation, location}`, enum: `Region(KR/US)`, `ViolationType(합법·1호_의약품오인·2호_기능성오인·5호_거짓과장기만·대상외)`, `JudgmentFlag(위반·검토필요)`.
- `pipeline.py` — 배선: 이미지→tile_split→OCR(vlm)→문장→judge→리포트, 텍스트 경로, ingredients 콤마 분리.

**판정기** (`judge/cosmetic.py`) — `CosmeticJudge` 프로토콜 슬롯 구조.
- `StubJudge` — 키워드 더미(오프라인·`JUDGE_KIND=stub`용, VLM 안 부름).
- `PromptJudge` — VLM 제로샷 실판정. 배치(기본12), 실패는 재시도 없이 미판정(unjudged) 처리. 2호엔 성분 정합 후처리.
- `RagJudge`는 **아직 없음** — 이게 다음 큰 작업(§2).

**레퍼런스 연동** (`reference/`)
- `mapping.py` — T1~T6 ↔ ViolationType 매핑 + `legal_basis_for()` (근거 조항 단일 출처).
- `ingredients.py` — 기능성 성분 정합 조회(정확 조회, 임베딩 X).
- `data/*.json` — 마크다운 표에서 추출한 구조화 데이터(`scripts/extract_reference_tables.py`가 생성).

**스크립트** (`backend/scripts/`) — `run_api.py`, `dump_openapi.py`, `make_fixtures.py`, `extract_reference_tables.py`, `score_eval.py`.

**산출물** — `backend/openapi.json`, `backend/fixtures/check_report_*.json`, `docs/api/README.md`(프론트 계약서).

**레퍼런스 팩** (`reference/cosmetic_kr/`) — 대수 저작 최신본 착지 완료(금지표현 T1~T6·성분표·사례). 1호 경계표현은 실제 규정 리서치로 검증해 판정기준 확정(§3).

**테스트** — `backend/tests/` 9개 파일, **60 통과**. 순수 로직만(VLM은 가짜 어댑터 주입). 실 VLM은 수동 스모크.

## 2. 다음 할 일 (우선순위, PM2 확인 후 착수)

1. **RagJudge 구축** (제일 큼, 이제 착수 가능). PromptJudge 슬롯 옆에 규칙 기반 대조를 얹는다.
   - `prohibited_expressions.json`의 금지표현과 광고 문장을 대조 → 매칭되면 근거조항까지 인용해 확정.
   - **판정 3갈래 반영**(§3): 위반 키워드→위반 / 실증대상 키워드→검토필요 / 상태서술·일반표현→합법.
   - 선행: 금지표현 셀(쉼표·가운뎃점 혼용)을 개별 문구로 정확히 쪼개는 작업(일부러 미뤄둠, `extract_reference_tables.py` 주석 참조).
2. **Location 좌표 확장** (PM2 큐, RagJudge와 무관해 병행 가능). 리포트에서 이미지 위 밴드 하이라이트용. `split_image()`가 이미 계산하는 top/bot(cuts)을 `(경로, top, bot)`로 반환하도록 확장 → `_ocr_image`가 원본 크기 읽어 문장 dict에 실음 → `_loc()`이 `Location{y_start,y_end,source_h,source_w}` 채움. 텍스트 입력은 전부 None.
3. **score_eval.py 500-버그 수정**(사소). `judge_batch`의 `res.get("results")`가 VLM이 리스트를 뱉으면 터짐. `PromptJudge`는 이미 고침(try 안으로), score_eval만 남음.
4. (대수 몫) 평가셋 표본 150~200건 확대 + 교차 라벨링 — 내 작업 아님.

## 3. 확정된 판정 기준 (평가셋 4자분열 + 규정 리서치로 확정, 대수 재확인 대상)
- **① 성분명·브랜드명·함량 표기만** → `대상외`.
- **② 근거 없는 일반 수식어**(완벽한/파워/탁월한/최적의) → 그 자체로 `5호`.
- **③ 니즈 서술문("~하신 분")** → 안에 **기능성 효능어**(미백효과 등)가 있으면 `2호`, 없으면 합법.
- **④ 1호 경계표현** → 표현별로 갈림:
  - 진정(단독)·탄력·민감/예민 피부 → 위반 아님(진정=실증대상→검토필요, 탄력=일반허용, 민감/예민=상태서술).
  - 아토피·염증·재생·치료·소독·약국/병원전용·의료기기(MTS) 시술묘사 → 위반.
  - 근거: `reference/cosmetic_kr/violation_types/type_1_drug_misperception.md`, `cosmetic_sources.md` §1-1.
- **핵심**: 평가에서 Gemini가 진정·탄력을 1호로 과잉판정했고, 합법으로 본 사람이 규정에 더 맞았다. RagJudge는 이 기준을 encode해야 한다.

## 4. 확정 결정 (되돌리지 말 것)
- **판정 provider = GPT-5-mini**(`JUDGE_PROVIDER=openai` 기본). 43문장 평가서 Gemini 미탐 4건 vs mini 1건, 비용 거의 0(하니 승인). OCR은 Gemini 유지.
- **stateless**. Supabase 안 붙임(자가검증=요청/응답).
- **v1.8: 위험도(고/중/저) 폐지 → 위반/검토필요 이진 플래그.** "근거 있으면 위반, 없으면 검토필요."
- **화장품 위반유형 = 개정법 기준(5호).** 3호 삭제, 신설 4호(AI)는 판정 enum 아님(FR-13 가드레일).
- **검토필요 ≠ 미판정(unjudged).** 검토필요=판정은 했으나 근거 약함. 미판정=VLM 호출 실패로 판정 자체 못함. 분리 유지.

## 5. 주의점 (안 지키면 사고남)
- **공유 워크트리**: 여러 세션(PM·디자이너·백엔드)이 **같은 디렉터리**에서 동시에 git 작업 중. `git add .` 절대 금지 → 반드시 `git add <내 파일 지정>`. 안 그러면 남의 커밋에 내 파일이 딸려 들어감(이번 세션에 2번 발생, 유실은 없었으나 이력 오염). 커밋은 바로바로.
- **남의 파일 건드리지 말 것**: `design/mockups/*`(디자이너), `docs/handoffs/*`·`docs/standup/*`(PM), `.gitignore`는 스테이징 제외.
- **venv pip 깨짐**: `./venv/bin/pip`은 리네임 전 경로(`final-project/venv`)를 물어 shebang 에러. 의존성 설치는 `./venv/bin/python -m pip install ...`로 우회. (venv 재생성 여부는 하니 판단 대기.)
- **gh CLI 없음**: PR은 내가 못 열어. push 후 `https://github.com/haneebunny/barum/pull/new/<브랜치>` 링크를 하니에게 주고 수동 생성.
- **VLM은 과금 호출**: 재시도 없이 실패 기록·스킵. 큰 배치 재실행 금지. 실판정 스모크는 소량 1회.
- **디자인·색**: 차트/색/KPI 타일 만들기 전 `dataviz` 스킬 먼저(CLAUDE.md §F). 백엔드라 자주 안 쓰지만 리포트 관련 나오면.

## 6. 실행
```bash
cd backend
./venv/bin/python scripts/run_api.py            # 서버 (localhost:8000, /docs)
./venv/bin/python -m pytest tests/ -q           # 테스트 (60 통과)
./venv/bin/python scripts/dump_openapi.py       # openapi.json 갱신
./venv/bin/python scripts/make_fixtures.py      # fixtures 갱신
./venv/bin/python scripts/extract_reference_tables.py  # reference md → json
```
- 키: `backend/.env`에 `GOOGLE_API_KEY`(OCR)·`OPENAI_API_KEY`(판정) 둘 다 있음. 하드코딩 금지.
- 오프라인/키없이 UI만 붙일 때: `JUDGE_KIND=stub`.
