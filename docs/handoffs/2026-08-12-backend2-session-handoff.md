# 백엔드 세션 인수인계 (2026-08-12, 백엔드2 → 다음 세션)

> 받는 사람: 다음 barum 백엔드 세션. 정리: 이전 백엔드 세션(백엔드2, Claude). 결정권자: 하니. 조율: PM.
> 목적: 백엔드 담당 역할을 넘긴다. 이 문서 하나로 현 상태·다음 할 일·주의점을 파악할 수 있게.

## 0. 너의 역할
바름 **백엔드 세션 담당**. 판정 파이프라인·API·콘텐츠생성을 이어간다.
- 착수 규칙: `CLAUDE.md` (코드 전에 인터뷰·단계별 계획·승인 대기, **§G 공유 워크트리 규칙 필독**, em-dash 금지·한국어 짧게).
- Git 규칙: `AGENTS.md` + `CLAUDE.md §G`. `feature/be-...` 브랜치 → PR 리뷰어 **haneebunny** → 하니 머지. **main 직접 push 금지.**
- 전체 로드맵 `ROADMAP.md`, 확정 결정 `PROJECT.md`, 진행기록 `PROGRESS_BE.md`(이 세션이 최신화 완료, 상세는 여기 참조).
- 지시·질문은 **현재 PM**에게. 세션 이름이 자주 바뀌므로(PM 1→2→3→4) `list_sessions`로 "(현)" 표시·최신 활동시각을 매번 확인. 이 문서 작성 시점 현 PM = **PM 4대 루루** (`local_b545b157-4c53-468c-9b3a-a41415524309`), 늦게 갱신되는 구 세션(제목에 "(현)"이 남아있어도)에 속지 말 것 — 인수인계 브랜치 존재 등으로 교차검증.

## 1. 지금까지 만든 것 (전부 main 머지 완료, PR 다수)

**API·계약** (`backend/src/barum/`)
- `api/app.py` — FastAPI. `POST /check`(판정) · `GET /health` · `GET /reports/{id}`(다시보기) · `GET /reports/{id}/image`(이미지 프록시) · `POST /remediate`(FR-14 수정권고안) · `POST /generate`(FR-11/13 콘텐츠생성, improve 모드).
- `models.py` — I/O 계약 전부(Pydantic). `CheckReport`(+`result_id`) · `Finding` · `Location`(밴드좌표 포함) · `StoredCheck` · `RemediationRequest/Response` · `GenerateRequest/Response`(Section·Replacement·ImagePlan·RiskConfirmation·RecheckSummary).
- `pipeline.py` — 이미지→tile_split→OCR(vlm)→문장(밴드좌표 포함)→judge→리포트.

**판정기** (`judge/cosmetic.py`)
- `StubJudge` — 오프라인 키워드 더미(`JUDGE_KIND=stub`).
- `PromptJudge` — VLM 제로샷. 선택적 `context` 파라미터로 grounding 지원(기본 빈 문자열, 회귀 없음).
- `RagJudge`(**기본, `JUDGE_KIND=rag`**) — 규칙(`reference/rules.py`) 우선 판정 + 미매칭만 fallback LLM. fallback은 규정문서 인라인(`reference/context.py`) + 사례 pgvector 검색(`reference/case_retriever.py`, `case_retriever` 미주입 시 cases.md 통째 인라인으로 degrade) 둘 다 참고.

**레퍼런스·규칙집** (`reference/`)
- `rules.py`+`data/judge_rules.json` — §3 검증된 1호 경계표현 규칙(violation/needs_review/legal_allow).
- `context.py` — 규정문서 grounding 블록 로더.
- `cases.py`+`case_retriever.py` — 실사례 추출·유사검색.
- `remediation.py`+`data/remediation_rules.json` — FR-14 조건표(결정적 대체표현).
- `mapping.py`, `ingredients.py` — T체계 매핑, 성분정합.
- `pii.py`, `impersonation.py` — 콘텐츠생성용 PII 제거·사칭필터.

**콘텐츠생성** (`generate/`) — FR-11/13, improve 모드 완료
- `content.py` — 검사→조건표치환→LLM 저위험서술→PII제거→이미지배치·가드레일→**재검증** 오케스트레이션.
- `replace.py` — 위반 finding → remediation 조건표 치환 조립.
- 신규 생성(create) 모드는 미착수.

**Supabase 인프라** (`storage/`)
- `client.py` — env(`SUPABASE_URL`·`SUPABASE_KEY`) 클라이언트, URL 자동정규화(`/rest/v1` 실수 방어).
- `checks_store.py` — 이력(`checks` 테이블) 저장/조회 + 증거이미지(private `evidence` 버킷).
- `cases_store.py`, `embeddings.py` — 사례 임베딩 적재(`reference_cases` 테이블)·유사검색.
- `db/schema.sql` — 신규 최소 스키마(**적용 완료**, RLS 켜짐). 기존 `backend/schema.sql`(식품/감독기관용 7테이블)은 안 씀.

**스크립트** — `run_api.py`, `dump_openapi.py`, `make_fixtures.py`, `extract_reference_tables.py`, `score_eval.py`, `load_cases.py`, `eval_ragjudge.py`.

**산출물** — `backend/openapi.json`, `backend/fixtures/*`, `docs/api/README.md`(프론트 계약서, 최신 반영 필요 — 아래 §2 참조).

**테스트** — `backend/tests/`, **155 통과**(2026-08-12 기준). 순수 로직만 유닛, VLM·Supabase는 가짜 주입 또는 수동 스모크.

## 2. 다음 할 일 (우선순위, PM 확인 후 착수)

1. **`docs/api/README.md` 갱신** — `/generate`·`/remediate`·`/reports/*` 계약이 프론트 문서에 최신 반영 안 됐을 수 있음. 착수 전 diff 확인.
2. **하니 결정 대기 항목** (PM에 먼저 확인):
   - FR-14 티어 게이팅 방식(로그인 없는 MVP에서 티어를 어떻게 판별?) — 이미 짐작 금지로 보류된 상태.
   - 콘텐츠생성 create 모드(신규 생성, 원본 없이) 착수 여부.
   - 미국 프리플라이트(2단계) 착수 여부.
3. **콘텐츠생성 후속 개선** (안전엔 문제없음, 알려진 개선점):
   - 재검증(`/generate`)에서 남은 위반을 자동 재치환하는 루프(지금은 1패스 치환 후 재검증만, 놓친 건 `risk_confirmations`로 노출만 함).
   - `remediation_rules.json` 데이터 품질 — 일부 대체표현 자체가 위반 소지 있음(스모크 중 발견, 재검증이 잡아냄).
4. **`reference/rules.py` 규칙집 확장 후보**: "약국 입점"(현재 "약국전용"만 있음, RagJudge 재평가에서 grounding LLM이 대신 잡음), MTS/니들 제품명 오탐 관측되면 조정.

## 3. 확정된 판정 기준 (변경 없음, 참고)
1호 경계표현(진정=검토필요/실증대상, 탄력=합법/일반허용, 민감·예민=합법/상태서술, 아토피·염증·재생·치료·소독·약국전용·MTS 시술묘사=위반) — `reference/cosmetic_kr/violation_types/type_1_drug_misperception.md` 참조. RagJudge 규칙에 이미 encode됨.

## 4. 확정 결정 (되돌리지 말 것)
- **판정 provider = GPT-5-mini**(`JUDGE_PROVIDER=openai` 기본). OCR은 Gemini.
- **DB 도입됨(Supabase)** — "stateless" 결정은 뒤집혔다. 이력·증거이미지 저장, 로그인 없이 추측불가 `result_id`가 접근권.
- **화장품 위반유형 = 개정법 기준(5호).** 3호 삭제, 신설 4호(AI)는 판정 enum 아님(FR-13 가드레일 영역).
- **RagJudge가 기본 판정기 방향** — 규칙 우선 + grounding fallback. 벡터검색은 사례에만 씀(규정문서는 통째 인라인, 코퍼스 작아서).
- **콘텐츠생성은 improve 모드만, 효능표현은 자유창작 금지**(조건표로 결정적 치환) — 재검증 없이 생성물을 그대로 내보내지 않는다.
- **내보내기(PNG/PDF/HTML)는 프론트 클라이언트 몫**, 백엔드 export API 없음.

## 5. 주의점 (안 지키면 사고남)
- **공유 워크트리 — CLAUDE.md §G 필독.** 여러 세션(PM·디자이너·백엔드·DB담당)이 **같은 디렉터리**에서 동시 작업.
  - `git add .` 절대 금지 → `git add <내 파일 지정>`.
  - **메인 워크트리에서 `git checkout <다른 브랜치>` 절대 금지.** 브랜치 작업은 `git worktree add <임시경로> -b <브랜치> origin/main`으로 격리, 끝나면 `git worktree remove`. 실제 사고 있었음(2026-08-12, 로컬 main이 origin보다 70커밋 뒤처진 걸 모르고 checkout해서 HEAD가 튐 — PM이 복구).
  - 남의 파일 건드리지 말 것: `design/mockups/*`(디자이너), `docs/handoffs/*`·`docs/standup/*`(PM), `.gitignore` 제외.
- **venv pip 깨짐**: `./venv/bin/pip` shebang 에러. `./venv/bin/python -m pip install ...`로 우회.
- **gh CLI 없음**: PR은 push 후 `https://github.com/haneebunny/barum/pull/new/<브랜치>` 링크를 하니에게 전달.
- **VLM·임베딩은 과금 호출**: 재시도 없이 실패 기록·스킵. 큰 배치 재실행 금지.
- **팀원 실명 → 코드네임.** 커밋·문서에 실명 쓰지 않는다(memory에 매핑 있음, 확실치 않으면 역할명).
- **PM 라우팅**: 매번 `list_sessions`로 현재 PM 확인. "(현)" 제목이 늦게 갱신되는 구세션일 수 있음, 인수인계 브랜치 등으로 교차검증.

## 6. 실행
```bash
cd backend
./venv/bin/python scripts/run_api.py            # 서버 (localhost:8000, /docs)
./venv/bin/python -m pytest tests/ -q           # 테스트 (155 통과)
./venv/bin/python scripts/dump_openapi.py       # openapi.json 갱신
./venv/bin/python scripts/make_fixtures.py      # fixtures 갱신
./venv/bin/python scripts/load_cases.py         # 사례 재적재(cases.md 바뀌면)
./venv/bin/python scripts/eval_ragjudge.py      # 배포 파이프라인 재평가
```
- 키: `backend/.env`에 `GOOGLE_API_KEY`(OCR)·`OPENAI_API_KEY`(판정·임베딩)·`SUPABASE_URL`·`SUPABASE_KEY` 전부 있음.
- 오프라인/키없이 UI만 붙일 때: `JUDGE_KIND=stub`, `CHECKS_PERSIST=0`.
