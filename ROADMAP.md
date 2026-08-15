# ROADMAP: barum 실행 로드맵 (v1.9)

> 성격: 가변 상태 문서(진행·할 일·담당·일정). 확정 결정은 `PROJECT.md`, 작업 규칙은 `CLAUDE.md`.
> 갱신일: 2026-08-13(저장소 정리, `PROGRESS_BE.md`·`PROGRESS_FE.md` 이 문서로 통합·원본 삭제). 발표일: 2026-08-27(수). 기준 기획서: `2조_최종프로젝트_기획서_v1.9.docx`.
> 방향: 화장품 광고 컴플라이언스 자가검증(브랜드용). 국내 1단계 + 미국 프리플라이트(조건부 2단계). LLM+RAG.
> 상세 작업 이력은 §8(백엔드)·§9(프론트엔드)에 날짜순으로 있다(구 `PROGRESS_BE.md`/`PROGRESS_FE.md` 전문).

---

## 0. 30초 요약

- 광고(이미지/글)를 넣으면 화장품법 위반 위험을 문구별로 짚어 주고, 무슨 조항 위반인지 근거까지 보여 주는 서비스.
- 화면 5개(홈 · 새 검사 · 결과 리포트 · 콘텐츠 생성 · 마이페이지, v1.9에서 마이페이지=FR-15 신규). 판정 프로그램 + 규칙집(법령·금지표현·성분표) + Supabase 이력/증거보존.
- v1.8: 위험도(고/중/저) 등급을 폐지하고 **위반/검토필요 이진 플래그**로 단순화. 화장품법 위반유형은 개정법 기준 **5호**(4호는 AI조항, 판정 라벨 아님).
- v1.9: FR-1~14는 v1.8과 문구 동일(실질 변경 없음). 요금제 확정(Free 0원·Basic 4.9만원·Pro 14.9만원·Export 애드온 건당 4.9만원)과 **수정 권고안(FR-14)은 Basic부터** 제공이 명문화됨. 회원가입·로그인·결제(PG)는 MVP 범위 밖, 마이페이지는 단일 데모 계정으로 시연.
- **판정 백엔드는 이미 안정화 단계.** 규칙집 완성 + RagJudge(규칙 우선 + VLM fallback) + RAG grounding(규정 인라인 + 실사례 벡터검색) + Supabase 이력저장까지 구현·코드리뷰·머지 완료. **FR-11/13(콘텐츠 생성, improve 모드) MVP도 완료**(`POST /generate` — 위반 조건표 치환 + LLM 저위험 서술 + PII 제거 + 이미지 가드레일 + 재검증). 백엔드 PR 총 10여 개 전부 main 머지. 다음은 프론트 통합과 다음 우선순위(신규 생성 모드 / FR-14 UI 게이팅 / 미국 프리플라이트) 결정.
- 판정 AI는 GPT-5-mini(2026-08-11 전환 완료, 43문장 평가셋 비교 근거 있음). OCR은 Gemini. 개발은 Antigravity·Claude Code. 돈은 사실상 0.

---

## 1. 지금 상태 (2026-08-12 기준)

### 백엔드: 완료
- 화장품법 4→5호 리네임(2026.11.27 개정법 반영).
- v1.8 위험도 폐지 → `JudgmentFlag`(위반/검토필요) 이진화.
- 레퍼런스 팩(`reference/cosmetic_kr/`): 금지표현 T1~T6, 성분표, 적발사례, 1호 경계표현 규정 리서치.
- `RagJudge`(`judge/cosmetic.py`): 규칙 우선(검증된 경계표현) + 미매칭만 VLM fallback.
- RAG grounding: 규정문서는 fallback LLM에 인라인, 실사례는 Supabase pgvector로 유사 top-K만 검색.
- Supabase DB 도입(FR-1 증거보존 + 검사 이력): 로그인 없이 추측불가 `result_id`로 "다시 보기"(`GET /reports/{id}`, `/image`). 스키마 `backend/db/schema.sql` 적용 완료.
- 판정 오프바이원 버그 수정(RagJudge/PromptJudge 전체에 영향 있던 신뢰도 문제, 회귀테스트 있음).
- Location 좌표 확장(이미지 밴드 하이라이트용), score_eval.py 500버그 수정, provider Gemini→GPT-5-mini 전환.
- **FR-11/13(콘텐츠 생성, improve MVP) 완료**(`POST /generate`, `generate/` 모듈): 위반 문구 조건표 치환 + LLM 저위험 서술 생성 + PII 자동제거 + 이미지 배치·사칭 가드레일 + 생성물 재검증. 신규 생성(create) 모드는 미착수.
- **PR 전부 main 머지 완료** (RagJudge/RAG보강/DB/콘텐츠생성 계 10여 개). 상세 이력은 `PROGRESS_BE.md`.

### 프론트/디자인: 진행 중
- 홈(`barum.html`)·검사 화면(`barum-inspect.html`) v1.8 반영 완료(등급배지 제거, 대상국 미국만 활성화, 검수지시 섹션 제거, 제품정보 입력 블록 신설, 용어 정리).
- **결과 리포트 화면·마이페이지 화면은 이미 존재·구현 진행 중** (`app/report/[id]/ReportClient.tsx`, `app/mypage/page.tsx`, 목업 `design/mockups/barum-report.html`·`barum-mypage.html`). 2026-08-12 기준 지적카드 액션(수용/제외/보류)·재검사필요 섹션·마이페이지 요금제전환·Pro 대시보드 스파크라인까지 구현됨(상세 §9). 콘텐츠 생성 화면은 착수 전이었음(이후 진행 상황은 별도 확인 필요).
- 열린 질문 2건 답변 대기(당시 시점): 지적카드(Finding) 액션 인터랙션 수준, tsx vs HTML 목업 진행 방식 — §9 로그 상으로는 tsx 방식으로 정리된 것으로 보임.

### 안 한 것 (다음 우선순위, 하니 결정 필요)
- **FR-14는 이미 구현됨**(`POST /remediate`, 별도 백엔드 세션·팀원B 완료) — 남은 건 프론트 티어 게이팅(무료는 탐지·근거까지만, Basic부터 수정권고안 노출)뿐. 로그인·계정이 MVP 범위 밖이라 "티어를 어떻게 판별할지"는 하니 확인 필요(요청 파라미터? 데모 계정 고정 티어? 프론트 UI만 숨김?).
- **콘텐츠생성(FR-11/13) improve 모드는 완료.** 다음 후보: 신규 생성(create, 원본 없이 자료만으로) 모드, 재검증 findings 자동 재치환 루프, 이미지 실제 생성기 도입 여부.
- 미국 프리플라이트(2단계) — 아직 미착수.
- score_eval.py(base 제로샷) 43문장 재검증은 팀원B 세션 소관. **배포 파이프라인(RagJudge) 재평가는 완료**(2026-08-12): base 제로샷 60.0%/미탐1/오탐11 → RagJudge 65.0%/**미탐0**/오탐11(위반6+검토필요5). 상세 PROGRESS_BE.
- 리포트 화면·콘텐츠생성 화면 프론트 구현, 화면↔판정 프로그램(`/check`·`/generate`·`/remediate`) 연결.
- `remediation_rules.json`(FR-14 조건표) 데이터 품질 점검 — 일부 대체표현 자체가 위반 소지 있음(콘텐츠생성 재검증 스모크 중 발견, 팀원B 소관).

---

## 2. 앞으로 (남은 D-16, 결정 대기 항목 포함)

### 이번 주 (~8/15)
- [하니 결정 필요] 다음 백엔드 우선순위: FR-14 티어 게이팅 방식 확정? 콘텐츠생성 create 모드? 미국 프리플라이트?
- [팀원A] 디자이너 열린질문 2건 답변받고 리포트 화면(`barum-report.html`) 착수.
- [팀원A] tsx vs HTML 목업 진행방식 결정에 따라 화면 코딩 착수.

### 2주차 (8/18~22) · 통합
- 화면 ↔ 판정 프로그램 연결(리포트 화면이 실제 `CheckReport`/이력 API 소비, 콘텐츠생성 화면이 `/generate` 소비).
- 다음 우선순위 기능(하니 결정) 구현.

### 3주차 (8/25~27) · 합치고 발표
- 진짜 광고 넣으면 리포트까지 한 번에 나오게 마무리.
- 채점: 판정 프로그램을 평가셋(43문장, 갱신된 규칙집 기준 재실행)에 돌려 "몇 % 맞히나" 확인.
- 발표 시연 1개 확실히(미백 크림 이미지 업로드 → 위반 뜸 → 문구 수정 → 재검사하니 사라짐) + 2분 녹화 백업.
- 여유되면 미국 선크림 1건 시연.

---

## 3. 담당

| 일 | 담당 | 비고 |
|---|---|---|
| 판정 프로그램 + 규칙집 + 콘텐츠생성(FR-11/13) | 백엔드2 | **완료.** 다음 우선순위 결정 대기 중(대기 세션) |
| 화면(리포트·콘텐츠생성) | 팀원A | 열린질문 2건 답변 후 착수 |
| 조율·PR 리뷰·머지 | 하니 | 결정권자. 머지 버튼은 하니만 |
| 세션 조율 | PM(루루) | 계획 승인·코드리뷰까지, 머지는 안 함 |

---

## 4. 돈 / AI (비용 사실상 0)

- **판정 AI = GPT-5-mini(전환 완료).** 43문장 평가셋 비교 결과 Gemini는 미탐 4건(52.5% 일치), GPT-5-mini는 미탐 1건(65.0% 일치)에 비용도 거의 공짜라 전환. GPT-5는 미탐 0건으로 제일 정확했으나 비용 문제로 데모 단계는 mini. `JUDGE_PROVIDER` env로 스왑 가능.
- **OCR(이미지→문자 추출)은 그대로 Gemini.**
- 큰 배치 재실행 금지. 데모는 광고 몇 개 + 문장 43개뿐.
- 프롬프트 실험은 무료 웹(AI Studio, ChatGPT 무료)에서.

---

## 5. 리스크 (제일 조심할 것)

1. 리포트 화면이 아직 없다. 판정 백엔드는 완성됐는데 화면이 못 따라가면 발표에서 못 보여준다.
2. 다음 우선순위(FR-14 티어게이팅 vs 콘텐츠생성 create모드 vs 미국)를 빨리 정해야 D-16 안에 뭐라도 하나 끝낸다.
3. 평가셋 재검증을 3주차로 미루면 "몇 % 맞혀요"를 발표 직전에야 알게 된다. 가능하면 앞당길 것.
4. 미국은 마지막에 선크림 1건만. 국내부터 확실히.
5. 통합(화면↔판정)은 처음에 잘 안 붙는다. 미리 한 번 붙여 볼 것.

---

## 6. 데이터 현황 (2026-08-11)

| 자료 | 규모 | 위치 |
|---|---|---|
| 화장품 레퍼런스 팩(규칙집) | T1~T6 금지표현·성분표·적발사례·경계표현 리서치 | `reference/cosmetic_kr/`: **완료** |
| 화장품 상세(프로브) | 상품 8개, 이미지 142장 | `backend/11st_probe_cosmetic/` (gitignore) |
| 화장품 평가셋 | 43문장(라벨링 완료, provider 3종 비교함, 5호 리네임 후 재실행 필요) | `backend/data/cosmetic_eval_labeling.xlsx` |
| 이미지 판독 실측 | 14장, 사람 정답 + LLM 판독 | `backend/11st_probe_cosmetic/read_test/` |
| Supabase DB | 이력 + 이미지·해시 증거보존, RLS 켜짐 | `backend/db/schema.sql`: **적용 완료** |
| (식품, 재활용) 11번가 상세 | 상품 279개, 타일 274개 | `backend/11st_output/` |
| (식품, 재활용) goldset/holdout | 215 / 331문장 | `backend/data/` |

---

## 7. 기술 참고 (재활용 파이프라인 + 실행 명령어)

| 파일(backend/) | 역할 | 상태 |
|---|---|---|
| `collect_11st_details.py` | 11번가 상세 수집(중복제거 내장) | 재활용 |
| `tile_split.py` | 긴 상세 이미지를 조각으로 절단 | 재활용 |
| `src/barum/vlm.py` | Gemini/GPT-5-mini 어댑터(provider 교체 가능) | 완료 |
| `src/barum/preprocess/ocr.py` | 이미지→문장 판독(Gemini) | 완료 |
| `src/barum/judge/prescreen.py` | 문장 keep + 유형 hint | 완료 |
| `src/barum/judge/cosmetic.py` | `RagJudge`(규칙우선+VLM fallback), `PromptJudge`, `StubJudge` | 완료 |
| `src/barum/reference/context.py`·`case_retriever.py` | RAG grounding(규정 인라인 + 사례 pgvector) | 완료 |
| `src/barum/storage/` | Supabase 클라이언트·이력·증거·사례 저장 어댑터 | 완료 |
| `src/barum/generate/` | 콘텐츠생성(FR-11/13) 오케스트레이션(`content.py`·`replace.py`) | 완료(improve만) |
| `src/barum/reference/remediation.py` | FR-14 수정권고안 조건표(`POST /remediate`) | 완료 |
| `backend/db/schema.sql` | Supabase 스키마(이력+증거보존+사례임베딩, RLS) | 적용 완료 |
| `reference/cosmetic_kr/` | 화장품 레퍼런스 팩 | 완료 |

### 실행 환경 & 명령어
- Python 3.11.9, venv = `backend/venv/`.
- 키(`backend/.env`, gitignore됨): `GOOGLE_API_KEY`(OCR) · `OPENAI_API_KEY`(판정) · `SUPABASE_URL` · `SUPABASE_KEY`(service_role) 전부 설정 완료.
- 스크립트는 `backend/`에서 실행.

```bash
cd backend

# 판독(OCR) → prescreen
./venv/bin/python scripts/run_ocr.py
./venv/bin/python scripts/run_prescreen.py

# 평가셋 재실행
./venv/bin/python score_eval.py

# 테스트
./venv/bin/python -m pytest -q
```

### 11번가 상세 취득 경로
```
https://www.11st.co.kr/products/{상품번호}/view-desc
```
- plain HTML, `<img src>`에 상세 이미지 직접. 안티봇 없음. 연구목적 소량(crawl-delay ≥ 1s) 수집.


---

## 8. 백엔드 상세 이력 (구 `PROGRESS_BE.md` 통합, ~2026-08-12까지)

> 담당: 백엔드 세션. 아래는 시간 역순(최신이 위) 작업 로그 원문이다.

### 2026-08-12 · 2호 판정에 함량 대조 추가 (`/check`, `_functional_evidence`)

하니 지시(대화 중 발견): 2호(기능성오인) 판정이 성분 "이름"만 대조하고 함량은 안 봤다. 이름+함량이
맞아도 그 자체로 "합법"은 아니고(실제 기능성 심사·보고 등록 여부는 우리 데이터에 없음), 이 한계를
설명문에 명시하는 게 필요하다는 논의 끝에, 함량 대조 자체를 판정에 넣기로 결정(선택지 제시 후 승인).

#### 로직 (`_functional_evidence`, 4단계)
1. 고시원료 이름 없음 → 위반(기존 동일).
2. 이름 있음 + 함량 미입력 → 검토필요(기존과 동일한 메시지, 회귀 없음).
3. 이름 있음 + 함량 줬는데 고시 기준 미달 → **위반**(신규 — "정식 심사 대상인데 안 밟은 근거").
4. 이름 있음 + 함량 기준 충족 → 검토필요 유지, 다만 "등록 확인되면 합법 전환 가능" 명시(신규 — 인증
   마크만으론 합법 확정 안 됨을 사용자에게 보여주기 위함).

#### 구현
- `reference/ingredients.py`: `find_amount_for(row, ingredient_amounts)` 신설(고시원료 행에 대응하는
  함량을 찾음). `parse_amount`·`check_amount_threshold`는 create 모드용으로 이미 있던 걸 그대로 재사용.
- `judge/cosmetic.py`: `CosmeticJudge` 프로토콜·`StubJudge`·`PromptJudge`·`RagJudge` 전부
  `ingredient_amounts: list[tuple[str,str]] | None = None` 파라미터 추가(기본값이라 회귀 없음).
  `RagJudge`는 내부 fallback `PromptJudge` 호출에 그대로 전달.
- `pipeline.py`: `_parse_ingredient_amounts()`("성분:함량" 콤마문자열 파싱, ":" 없는 항목은 건너뜀) +
  `run_check(ingredient_amounts=...)` 신설 파라미터.
- `api/app.py`: `/check`에 새 폼 필드 `ingredient_amounts`(예: `"나이아신아마이드:3%,알부틴:10%"`).
  기존 `ingredients`(이름만)는 안 건드림, 안 보내면 기존 동작 100% 그대로.

#### 테스트·검증
- 신규 유닛 8개(`find_amount_for` 2·`_functional_evidence` 3단계 3·RagJudge 전달 1·pipeline 파싱 2) +
  기존 회귀 — **182 통과**(기존 174 + 신규 8).
- API 실 스모크(`JUDGE_KIND=rag`, gpt-5-mini 실호출, `/check`):
  - 알부틴 10%(기준 2~5% 초과) → **위반**, 설명에 "함량 10%이 고시 기준(2~5%) 미달" 확인.
  - 나이아신아마이드 3%(기준 충족) → **검토필요 유지**, 설명에 "등록 확인되면 합법 전환 가능" 확인.

#### 다음
- `docs/api/README.md`에 `/check`의 새 폼 필드(`ingredient_amounts`) 반영 필요(기존에도 미반영 상태였던
  `/generate` 등과 함께 한 번에 정리하는 게 나을 듯 — 백엔드2 인수인계 문서 §2에 이미 있던 항목).
- 프론트가 함량 입력 UI를 만들 계획이 있으면(성분명+% 입력) 이 필드로 붙이면 됨, 없으면 이름만 보내는
  기존 흐름 그대로 써도 무방(신규 필드는 순수 opt-in).

---

### 2026-08-12 · 콘텐츠 생성 create 모드 착수 (인정문구 소비 로직, 데이터는 비비 대기)

PM4 지시(순서: FR-14 티어게이팅 → create 모드). FR-14는 하니 결정으로 **프론트 전용 토글**(백엔드 무변경, 디디 담당) 확정. create 모드는 착수 전 인터뷰로 "효능표현을 어떻게 안전하게 다룰지" 확정 후 진행: **인증서 기반 인정문구 조합**(improve의 "자유창작 금지, 조건표 치환" 원칙을 create에도 유지, 소스만 조건표 대신 인증서-인정문구 매칭).

#### 발견한 갭 (진행 중 하니 재점검으로 정정 2건 포함)
- barum 레퍼런스에 "인정문구"(기능성 카테고리별로 실제 써도 되는 정형 문구) 데이터가 없었음. `functional_ingredients.json`은 성분명-카테고리 정합만 있고 문구 데이터는 없음. → **데이터 적재는 비비(DB담당)에게 이관, 나는 소비 로직만 먼저 구현**(PM 승인). 소비 로직 짜는 도중 비비가 실제로 `data/approved_efficacy_statements.json`(PR #54)을 merge — 스키마가 처음 설계한 스텁(`certification`별 문구)과 달리 **카테고리별 문구 목록**이라 소비 로직을 실데이터 스키마에 맞춰 다시 씀(아래 구현 참조).
- **비비 데이터는 처음엔 `status: "draft"`(최상위)** — easylaw.go.kr + 해설서 교차검증만 했고 「기능성화장품 심사에 관한 규정」 별표4 고시 원문 대조는 아직이라, `match_approved_claim`에 최상위 draft 게이트를 먼저 넣었음. **이후 하니가 원문을 확보해 비비가 대조 완료, 스키마가 카테고리별 status로 바뀜**(`categories[카테고리]["status"]` = `confirmed`/`needs_confirmation`, `feature/be-approved-efficacy-phrases` 06d6c0f). 최상위 status 필드 자체가 없어져 원래 게이트가 무력화됨(우연히 안전했던 건 자외선차단이 `candidate_statement` 키를 써서 빈 statements로 처리됐기 때문 — 스키마 조금만 바뀌면 위험했음, 비비가 발견·PM4가 지시). **카테고리 단위 게이트로 수정**: `categories[category]["status"] == "confirmed"`만 통과, `candidate_statement`는 아예 안 읽음. 미백·주름개선(confirmed)은 살아나고 자외선차단(needs_confirmation, 하니 확인 대기)은 계속 막힘 — 카테고리마다 대조 완료 시점이 달라도 안전.
- 함량 기준 대조 로직에 두 가지 정정 반영(하니 지적): ① IU/g 단위(레티놀·레티닐팔미테이트)도 지원 ② 범위 기준함량(예 알부틴 2~5%)은 하한만 볼 게 아니라 **범위 안에 있어야 통과**(상한 초과=정식 심사 대상, create 모드는 스킵).

#### 구현
- `models.py`: `GenerateRequest.mode`(improve|create, 기본 improve) 추가, `content`는 improve만 필수(model_validator). `IngredientAmount{name, amount}`(create 전용, 함량 원문 표기 그대로 — "2%"·"2,500 IU/g"). `GenerateResponse.skipped_claims[]`(조건 미충족으로 안 만든 카테고리+사유, 조용히 안 빠지게).
- `reference/ingredients.py`: `parse_amount`(%·IU/g 파싱, 주석 섞인 값은 의도적으로 파싱 실패 처리) · `check_amount_threshold`(범위는 구간 내, 단일값은 이상/이하) · `match_ingredient_strict`(이름+함량+기준 셋 다 통과해야 매칭 — improve의 `match_ingredient`는 이름만 보므로 안 건드림).
- `reference/approved_claims.py`: 비비의 `data/approved_efficacy_statements.json`을 읽어 `match_approved_claim(category, certifications)` — 인증서 문자열이 카테고리를 가리키고(예: "미백 기능성 인증") **동시에 그 카테고리의 `status`가 `confirmed`여야** 문구 반환(카테고리별 게이트, 최상위 status 아님).
- `generate/content.py`: `build_approved_claim_sections`(카테고리별 ①인증서매칭 ②성분명 ③함량명시 ④기준충족 4개 다 통과해야 생성, 실패 시 `skipped_claims`에 사유), `_generate_create_content`(원본검사 없음, `replacements` 항상 빈배열, 나머지는 improve와 공유 로직 재사용), 기존 로직은 `_generate_improve_content`로 이름만 바꾸고 무변경, `generate_content`가 `mode`로 분기(엔드포인트 시그니처 불변).

#### 테스트·검증
- 신규 유닛 19개(파싱·함량비교·strict매칭·approved_claims 카테고리별 게이트(confirmed/needs_confirmation 혼재 케이스 포함)·모델검증·오케스트레이션) + 기존 회귀 — **174 통과**(기존 155 + 신규 19).
- 알부틴 10%(범위 2~5% 상한 초과) → 스킵 케이스 테스트로 확인(하니 정정사항 커버).
- 카테고리 독립성 테스트 추가: 미백이 confirmed라고 자외선차단(needs_confirmation)까지 같이 안 풀리는지 확인(비비 발견 버그 재발 방지).
- API 수동 스모크는 비비의 `feature/be-approved-efficacy-phrases`(카테고리별 status 스키마)가 main에 merge된 뒤 다시 돌릴 예정 — 지금 이 브랜치의 데이터 파일은 아직 구 스키마(최상위 status)라 실제론 안전(모든 카테고리 status 키 없음 → confirmed 아님 → 스킵) 확인만 함.

#### 다음
- 비비의 카테고리별 status 스키마 PR이 main에 merge되면, 미백·주름개선(confirmed)은 코드 변경 없이 바로 문구가 나온다. 자외선차단은 하니가 `candidate_statement`를 정형 문구로 써도 되는지 확인해서 status를 confirmed로 바꾸기 전까진 계속 막힘(의도된 동작).
- `Section.source="approved_claim"` 프론트 라벨 추가는 디디에게 전달 예정(create 모드 화면 자체가 아직 없어 급하지 않음).
- IU/g 외 단위(예: 다른 표기법)는 create 모드에서 여전히 비지원(안전하게 스킵) — 필요해지면 확장.

---

### 2026-08-12 · 콘텐츠 생성 FR-11/13 (improve MVP, A+B단계 완료)

브랜치 `feature/be-generate-a`(PR #48) → `feature/be-generate-b`(PR #49, A 위 스택). PM4 지시, 착수 전 하니 인터뷰로 스코프 확정 → 디디(프론트)와 `POST /generate` 계약 조율 → CLAUDE.md B규칙대로 계획 승인 후 착수.

#### 확정 스코프 (하니 인터뷰)
- **모드 = 개선(improve) 우선.** 신규 생성(원본 없이 자료만으로 처음부터)은 후순위.
- **효능·기능 표현은 자유창작 금지, 조건표(기존 `remediation.py`)로 결정적 치환** — FR-14와 같은 원칙 재사용.
- **저위험 서술(제품개요·사용법·주의사항)만 LLM 실제 생성** + 실패 시 템플릿 폴백(기획서 "완성도 미달 시 큐레이션 폴백" 반영).
- **FR-13 이미지는 배치 + 가드레일만.** 실제 이미지 생성기(provider)는 안 붙임 — 업로드 사진 배치, 생성요청은 사칭(의사·의료진·전문가) 키워드 필터로 허용/거부만 판단.
- **생성물은 반드시 `/check`(RagJudge)로 재검증.**
- 내보내기(PNG/PDF/HTML)는 **프론트 클라이언트 export**로 확정, 백엔드 스코프 제외(하니 결정).

#### API 계약 (디디와 조율, `POST /generate`)
입력: `content`(필수, 원본 텍스트 — 저장된 검사엔 위반 문장만 있고 원문 전체가 없어 프론트가 넘김) + `result_id`?(이미지·맥락 참조) + `materials`(ingredients·certifications·notes) + `image_generation`?.
출력: `sections[]`(kind·text·source={llm|remediation|template}) · `replacements[]`(원문→대체, "이렇게 고쳤어요" 대조용) · `image_plan`(placed·generation) · `pii_removed[]` · `risk_confirmations[]`(id 포함, 체크리스트 UI) · `recheck`(safe·n_findings·n_violation·n_needs_review — safe=false만 빨강 배지, 색규칙 정합) · `disclaimer`.

#### 구현 (A단계 = 순수 로직, B단계 = LLM+오케스트레이션)
- `reference/pii.py`: 이메일·전화·주민번호 정규식 제거(순수, TDD).
- `reference/impersonation.py`: 이미지 생성요청 사칭 키워드 필터(순수, TDD).
- `generate/replace.py`: 위반 finding → `remediation.get_remediation()`으로 안전표현 조립(기존 조건표 재사용만, remediation.py 안 건드림).
- `generate/content.py`: 검사(judge 주입) → 조건표 치환 → LLM 저위험 서술(vlm 주입, 전용 프롬프트로 효능표현 명시적 금지) → PII 제거 → 이미지 배치·가드레일 → **재검증**(run_check 재사용) → 남은 위반은 `risk_confirmations`로 노출. 계획의 "C단계(재검증 통합)"가 오케스트레이션에 흡수돼 B로 완결.
- `POST /generate` 엔드포인트(`api/app.py`), `_section_vlm()` seam으로 테스트 가짜 주입.
- **판정기(RagJudge·PromptJudge)·remediation.py는 안 건드림, 재사용만.**

#### 재검증 안전망 확인 (실 스모크, RagJudge+gpt-5-mini)
입력 "아토피 완화에 좋은 재생 크림, 병원에서도 추천, 전화번호 포함" → 치환(아토피→"극건성 피부용 보습", 병원추천→remediation 대체) → LLM 섹션 생성(효능표현 없음) → PII 제거 확인. **재검증에서 `safe=False`로 남은 위험 2건이 정직하게 노출됨**:
1. 한 문장에 위반 여럿이면 첫 것만 치환됨("재생"이 안 잡힘) — 다음 이터레이션에서 "재검증 findings 재치환 루프" 넣으면 개선 가능.
2. `remediation_rules.json`의 일부 대체표현 자체가 위반 소지("우수한 효과" 등, 데이터 품질 이슈, `reference/data/remediation_rules.json` 소관).
둘 다 안전에는 문제없음(숨기지 않고 확인 요청으로 노출).

#### 테스트
신규 20(A: pii 5·impersonation 3·models 3·replace 3, B: content 4·api 2, 합 20) — 전체 **155 통과**.

#### 다음(미착수)
- 신규 생성(create) 모드.
- 재검증 findings 재치환 자동 루프.
- 이미지 실제 생성기 도입 여부(현재는 가드레일만).
- remediation_rules.json 데이터 품질(대체표현 자체 위반 소지 있는 항목 점검) — 팀원B 소관.

---

### 2026-08-12 · 배포 파이프라인(RagJudge) 재평가 + base 대비 개선폭

score_eval 재평가(작업A)는 팀원B 세션 소관으로 확정돼 이 세션은 안 함. 대신 하니 지시로, 실제
배포되는 RagJudge 파이프라인의 정확도를 같은 40문장 라벨셋으로 쟀다(`scripts/eval_ragjudge.py`).
score_eval.py는 base PromptJudge(제로샷)만 재므로 실제 제품 정확도를 과소평가한다.

| 지표 | base 제로샷(score_eval) | 배포 RagJudge(eval_ragjudge) |
|---|---|---|
| 일치율 | 60.0% (24/40) | **65.0% (26/40)** |
| 미탐(위반 놓침, 1급) | 1건 | **0건** |
| 오탐(합법→위반 flag) | 11건(전부 위반) | 11건(위반 6 + 검토필요 5) |

- **미탐 1→0**: base가 놓친 #33 "약국 입점 화장품"을 RagJudge가 잡음. 규칙엔 "약국전용"만 있고
  "약국 입점"은 없어 규칙이 아니라 규정 grounding LLM이 잡았다(규칙집 확장 후보로 기록).
- **하드 오탐 11→6**: base가 위반으로 과잉판정하던 경계표현 5건(진정·미백니즈 등)이 RagJudge에선
  검토필요로 완화됨(규칙+grounding 효과). 남은 위반 오탐 6건은 완벽/최적/파워 같은 일반수식어다.
  A1 결정으로 규칙에 안 넣고 VLM에 맡긴 것이라 5호 수식어 규칙 확정(다음 이터레이션) 전엔 유지.
- **발표 스토리**: "base 제로샷 60%/미탐1 → 배포 RagJudge 65%/미탐0/하드오탐 절감".
- 결과 파일은 gitignore(로컬): `data/eval_compare.csv`에 두 판정기 나란히, 상세 `data/eval_result_*.xlsx`.

---

### 2026-08-11 · RagJudge 구축 (규칙집 우선 + VLM fallback)

브랜치: `feature/be-rag-judge` (origin/main 기준). PM2 승인 하 착수(계획 검토 후).

#### 무엇
판정 슬롯에 `RagJudge`를 추가했다. 규칙집(`reference/rules.py` + `data/judge_rules.json`)으로
확정 가능한 문장은 규칙이 먼저 판정하고, 규칙에 안 걸린 문장만 내부 `PromptJudge`(VLM)에 위임한다.
규칙 확정분은 VLM을 안 부르므로 과금과 과잉판정을 함께 줄인다(Gemini가 진정·탄력을 1호로 과잉판정하던 문제 원천 차단).

#### 구조
- `reference/rules.py` — `match_rule(sentence)`가 정규화 문자열 포함 검사로 규칙집을 대조. 우선순위 스캔: violation > needs_review > legal_allow. 미매칭이면 None(VLM 위임).
- `data/judge_rules.json` — 손 큐레이션(자동추출 아님). §3에서 규정 리서치로 검증된 1호 경계표현. violation(아토피·염증·재생·시술·MTS·병원전용 등)/needs_review(진정·안티에이징·피부장벽 등)/legal_allow(탄력·민감·예민).
- `judge/cosmetic.py` — `RagJudge`가 `PromptJudge`를 합성 재사용. StubJudge·PromptJudge는 안 건드림.
- `api/app.py` — `JUDGE_KIND=rag` 분기 추가.

#### 결정(PM2 확정)
- 일반 수식어(완벽·파워·탁월·최적)는 규칙에 안 넣음(A1). `type_5_deception.md`가 "3:1 갈림·미확정"이라 결정론적 규칙에 못박지 않고 VLM에 위임.
- 명백 5호(경쟁사비방·"3배"·"최고")도 이번 스코프 제외. 근거는 있으니(type_5 예시표 "O") **다음 이터레이션 5호 규칙 추가 시 우선순위로**.
- co-occurrence("안티에이징 탄력크림"→검토필요)는 우선순위 스캔으로 처리, 테스트로 못박음.

#### 후속 조정 대상(오탐 나오면 보고)
- MTS·니들: `type_1`은 "시술 병행·묘사" 맥락일 때 1호. 제품명에 "마이크로니들"이 그냥 들어가면 5호(사용방법 오인)에 가까울 수 있음. 지금은 1호로 분류(근거 있음), 제품명 오탐 나오면 PM2에 보고.
- 짧은 키워드 substring 오매칭: "진정" vs "진정한", "재생" vs "재생성" 등. 광고 카피 특성상 대부분 긍정 표방이라 단순 매칭 유지(CLAUDE.md 단순·안정), 오탐 관측 시 조정.

#### 테스트
`test_rag_rules.py`(7) + `test_rag_judge.py`(6) + `test_api.py` 팩토리 1 = 신규 14. 전체 **74 통과**. §3 경계표현 12건 오프라인 스모크 일치 확인.

---

### 2026-08-11~12 · Location 좌표 · score_eval 버그 · RAG 보강(4 Phase) · Supabase DB

RagJudge(PR #16) 위에 이어서 진행한 작업들. 브랜치는 각각 origin/main 기준(또는 명시한 대로 스택), PR 별도, 전부 TDD.

#### Location 좌표 확장 (PR #18)
이미지 밴드 하이라이트용. `tile_split.split_image()`가 `(path, top, bot)` 튜플로 밴드 좌표를 함께 반환하게 확장 → `pipeline._ocr_image`가 원본 크기 읽어 문장 dict에 `y_start/y_end/source_h/source_w` 실음 → `judge._loc()`이 `Location`에 채움. 텍스트 입력은 전부 None. fixtures·openapi 재생성.

#### score_eval.py 500버그 수정 (PR #21)
`judge_batch`의 `res.get("results")`가 VLM이 리스트를 뱉으면 `AttributeError`로 터지던 것(`PromptJudge`는 이미 고쳐져 있었음). try 안으로 옮겨 예상된 실패로 흡수.

#### RAG 보강 — 4 Phase (PR #17·#19·#20, 계획은 하니 인터뷰로 확정)
RagJudge 미매칭 문장이 LLM으로 갈 때, "규정 문서·판정기준·실사례를 실제로 참고해 판단"하게 하는 작업.
- **Phase1 — 규정 인라인 grounding** (`reference/context.py`): 판정 근거 md(금지표현·판정기준·성분표)를 프롬프트에 통째로 인라인. `PromptJudge`에 선택적 `context` 파라미터 추가(기본 `''`라 기존 동작·score_eval 무영향). 벡터검색 안 씀(코퍼스가 작아 통째 인라인으로 충분, PM 확정). 실 스모크: LLM이 별표1·2·5 조항을 실제 인용해 판정.
- **Phase2 — Supabase 기반** (`storage/client.py`, `db/schema.sql`): env(`SUPABASE_URL`·`SUPABASE_KEY`)로 클라이언트 생성. **주의**: 대시보드에서 REST 엔드포인트 전체(`.../rest/v1/`)를 URL로 복사하는 실수가 흔해 `PGRST125`로 깨진다 — 클라이언트가 URL을 자동 정규화(`/rest/v1`·끝슬래시 제거)하게 방어 처리함.
- **Phase3 — 사례 pgvector 검색** (`reference/cases.py`, `storage/cases_store.py`, `reference/case_retriever.py`): `cases.md`의 실사례를 `text-embedding-3-small`로 임베딩해 `reference_cases`에 적재(`scripts/load_cases.py`, 배포 시 1회, 멱등) → 판정 시 문장 임베딩으로 유사 top-K(기본 3, cap 6)만 검색해 프롬프트에 삽입(cases.md 통째 대신). 검색 실패해도 빈 블록으로 degrade(판정은 규정만으로 계속). **부수로 잡은 버그**: 모델이 1-based n을 주면(우리 항목은 0-based) 조회가 빗나가 판정이 조용히 미판정으로 흐르던 것 — 결과 수=문장 수면 순서로 매칭하게 고침(개수 다르면 fallback 안 함=안전). grounded 긴 프롬프트에서 특히 잘 재현됨, `PromptJudge` 전체에 영향 있던 신뢰도 문제.
- RagJudge는 `case_retriever` 선택 주입(없으면 Phase1 방식, 있으면 규정+검색사례).

#### Supabase DB 도입 — 이력·증거 저장 (PR #22/#25, Task2)
FR-1(증거보존)·FR-8(다시보기) 충족. **로그인 없음** — 추측불가 `result_id`(`secrets.token_urlsafe(32)`)가 접근권. 기존 `schema.sql`(식품/감독기관용 7테이블)은 재사용 안 하고 `db/schema.sql`에 신규 최소 스키마(`checks`·`reference_cases`, RLS 켜짐 — secret key는 우회하니 백엔드 접근엔 문제없고 anon 직접접근만 막는 방어층).
- `models`: `CheckReport.result_id`(optional) + `StoredCheck`(리포트 감싸는 다시보기 응답).
- `storage/checks_store.py`: sha256 해시 + private Storage 버킷(`evidence`) 업/다운로드.
- API: `POST /check`가 결과·증거 저장 후 `result_id` 응답(저장 실패해도 응답은 살아있음, 예상된 실패 스킵) · `GET /reports/{id}`(다시보기) · `GET /reports/{id}/image`(백엔드 프록시 스트리밍, 서명URL 없음).

#### 검증 (전체, RagJudge 이후 누계)
`pytest tests/ -q` → **155 passed**(신규 총 81). 실 Supabase 스모크: 버킷 생성 → 이미지 라운드트립(바이트 일치) → 이력 저장/조회 전부 확인. `data/eval_ragjudge.py` 재평가(PR #29): base 제로샷 60.0%/미탐1 → 배포 RagJudge 65.0%/**미탐0**(상세는 위 "배포 파이프라인 재평가" 항목).

#### 사고 1건 — 공유 워크트리 git checkout
작업A(score_eval 재평가, 팀원B 소관으로 최종 확정) 착수 전 "최신 코드로 돌리려고" 메인 워크트리에서 `git checkout main`을 실행했다가, 로컬 main이 origin/main보다 70커밋 뒤처진 낡은 지점으로 HEAD가 튐(PM3가 복구, 유실 없음). **재발 방지**: 이후 전부 `git worktree add <임시경로> ... origin/main`으로 격리해서 작업, 메인 워크트리 HEAD는 안 건드림.

---

### 2026-08-11 · 백엔드 세션 인수인계 + 1호 경계표현 규정 리서치

이 세션(백엔드 담당) 종료. 다음 세션 인수인계 문서: `docs/handoffs/2026-08-11-backend-session-handoff.md`.

#### 1호 경계표현 규정 검증 (평가셋 4자분열 해소)
팀원B의 43문장 4자 상호비교에서 안정성 0.00이던 1호 경계표현을 실제 규정·해석으로 검증:
- **진정** = 실증대상(law.go.kr 1차해석), **탄력** = 일반허용, **민감/예민** = 상태서술 → 그 자체로 1호 아님.
- **아토피·염증·재생·치료·소독·약국/병원전용·MTS 시술묘사** = 위반.
- 뒤집힌 것: Gemini가 진정·탄력을 과잉판정, 합법으로 본 사람이 규정에 더 부합. `reference/cosmetic_kr`에 출처와 함께 반영(PR #14 머지).

#### 판정 3축 확정(팀원B 재확인 대상)
① 성분·브랜드표기→대상외, ② 일반수식어→5호, ③ 니즈서술문→효능어 기준, ④ 1호경계→표현별. 상세는 핸드오프 §3.

#### 이 세션이 완료한 것 (전부 main 머지)
API 골격 → PromptJudge → 프론트 픽스처 → 레퍼런스 팩 반영·T매핑·구조화·성분정합 → v1.8 위반/검토필요 플래그 → provider GPT-5-mini 전환 → 1호 리서치 검증. 테스트 60 통과.

#### 다음 세션이 이어갈 것
RagJudge 구축(최우선, 착수조건 성립), Location 좌표 확장(병행 가능), score_eval.py 500-버그. 상세·주의점은 핸드오프 문서.

---

### 2026-08-11 · 판정 provider 기본값 전환: Gemini → GPT-5-mini

브랜치: `feature/be-provider-default` (origin/main 기준). 팀원B의 43문장 4자 상호비교 평가 결과 반영, 하니 승인.

#### 근거
| Provider | 일치율 | 미탐(1급 지표) |
|---|---|---|
| Gemini | 52.5% | 4건 |
| GPT-5 | 62.5% | 0건 |
| GPT-5-mini | 65.0% | 1건 |

recall 우선 정책엔 GPT-5가 제일 맞지만 유료. GPT-5-mini는 미탐 1건에 비용이 거의 공짜라(하니: "GPT-5-mini도 거의 공짜라서 그거 써도 돼") 이걸로 전환.

#### 무엇을 바꿨나
- `api/app.py`의 `_build_judge()`: `JUDGE_PROVIDER` 기본값 `"gemini"` → `"openai"`(모델은 `vlm.py`가 이미 `gpt-5-mini` 기본).
- **OCR_PROVIDER는 안 건드림.** 이 비교는 판정 정확도(문장 라벨링)에 대한 것이지 이미지 글자 읽기(OCR) 품질에 대한 게 아니다.
- `ROADMAP.md` §3·30초 요약: "판정 AI=Gemini 무료 키" 확정 문구를 GPT-5-mini로 갱신.

#### 검증
- `pytest tests/ -q` → 60 passed(변경 없음, 테스트는 provider 무관).
- 실판정 스모크: env에 provider를 아예 안 정한 상태로 `/check` 호출 → gpt-5-mini가 자동으로 잡혀 정상 판정.

#### 다음
- 판정 기준 3축(성분/브랜드표기·일반수식어·니즈서술문) + 1호 재정의는 정책 결정이라 하니에게 선택지 제시 예정. 확정되면 RagJudge 착수.
- Location 좌표 확장은 이 결정과 무관하게 병행 가능(다음 작업).

---

### 2026-08-11 · v1.8: 위험도(고/중/저) 폐지 → 위반/검토필요 이진 플래그

브랜치: `feature/be-judgment-flag` (origin/main 기준). PM2 지시(기획서 v1.8, FR-5·FR-7), 착수 전 계획 승인받고 진행.

#### 무엇을 바꿨나
- `RiskLevel`(고/중/저) 삭제 → `JudgmentFlag`(위반/검토필요) 신설. `Finding.risk` → `Finding.flag`로 필드명도 변경(개념이 달라져서).
- `Summary`에 `n_violation`·`n_needs_review` 추가(`n_findings`는 합계로 유지). `n_unjudged`는 별개 개념 그대로.

#### 핵심 설계: 근거 없는 유형은 어떻게 판단하나 (RagJudge 오기 전)
"근거 있으면 위반, 근거 없으면 검토필요"(FR-5)인데, 지금 규칙집 대조 수단이 있는 건 2호(기능성오인)의 성분 정합뿐이다.
- **1호·5호**: 대조 수단 없음 → 항상 `위반`(recall 우선, 근거 없다고 함부로 안 낮춤). RagJudge 붙으면 이것도 매칭 성공 여부로 갈릴 예정(범위 밖).
- **2호**: `ingredients` 있고 고시원료 **없음** → `위반`(근거로 확증). 고시원료 **있음** → `검토필요`(등록 여부는 모르니 단정 못 함, 하니 승인). `ingredients` 미입력/카테고리 불명 → `검토필요`(대조 근거 자체 없음).
- StubJudge: 항상 `위반`(데모용, 근거 인프라 없음).

#### 부수로 잡은 버그
`PromptJudge`에서 `res.get("results", [])` 호출이 try/except 밖에 있어서, VLM이 가끔 `{"results":[...]}` 대신 통짜 리스트를 뱉으면 `AttributeError`로 **요청 전체가 500** 났다. try 안으로 옮겨 예상된 실패로 흡수(→ 그 배치는 미판정 처리). 실판정 스모크 중 실제로 재현·수정 확인함. `score_eval.py`에도 같은 패턴이 있는데 이번 범위 밖이라 안 건드림(하니 판단 필요, 별도 이슈).

#### 검증
- `pytest tests/ -q` → **60 passed**.
- 실판정 스모크(Gemini) 3회: 성분 있음→검토필요, 성분 없음(1호)→위반, 그리고 위 버그 실제 재현 후 정상적으로 미판정 처리되는 것까지 확인.
- fixtures·openapi 재생성, `docs/api/README.md`에 위반/검토필요 vs unjudged 구분 명시.

#### 다음
- Location 좌표 확장(타일 y범위, 밴드 하이라이트용) — PM2가 이 작업 다음으로 지정.
- 팀원B의 4자 상호비교 평가 결과(43문장 라벨링 완료, Gemini/GPT-5/GPT-5-mini 비교)가 나와서, provider 기본값·"검토필요" 범위 확장 여부를 하니와 논의 예정(하니: "GPT-5-mini도 거의 공짜라 써도 됨").

---

### 2026-08-11 · 화장품 레퍼런스 팩 반영 + T-체계 매핑 + 구조화 추출 + 성분 정합

브랜치: `feature/be-reference-pack` (`feature/be-frontend-fixtures` 이후, origin/main 기준 재구성). 커밋 여러 개로 분리.
경위: 팀원B 연락 두절 중 하니가 팀원B의 최신 산출물(Downloads의 index·prohibited_expressions·functional_ingredients·cases.md)을
전달, 이 세션이 검토·반영. PM2 승인 받음(방향·T-매핑 확정).

#### 1. 4호→5호 리네임 (PM2 작업, 이 세션이 커밋)
개정법(화장품법 제13조, 시행 2026.11.27)에서 AI 생성물 관련 조항이 신설 4호로 들어오며
기존 4호(거짓·과장·기만)가 5호로 밀림. 발표(8/27)가 시행 3주 전이라 개정법 기준으로 미리 맞춤.
`ViolationType.type_5_deception`(라벨 `5호_거짓과장기만`)로 전체 동기화. 신설 4호(AI)는 문구
판정 라벨이 아니라 콘텐츠 생성 가드레일(FR-13) 영역이라 enum에 없음.

#### 2. 레퍼런스 팩 최신본 반영
옛 빈 뼈대(`reference/cosmetic_kr/*.md`)를 팀원B의 채워진 최신본으로 교체:
- 금지표현 목록: T1~T6 유형체계로 상세화(별표1·별표5·실증대상)
- 기능성 성분표: 미백9·주름4·자외선27종 + 기준함량(고시 제2023-61호 별표4 원문 대조 완료)
- 적발사례: 식약처 11개 업체 실사례 + 대규모 점검 집계

#### 3. T-체계 ↔ ViolationType 매핑 모듈
`src/barum/reference/mapping.py`: 레퍼런스의 T1~T6과 판정 enum(5값)이 안 맞아서(T5·T6이
둘 다 5호로 접힘, T3·T4는 판정 라벨 아님) 매핑을 코드 한 곳에 뒀다. `legal_basis_for()`로
근거 조항 문자열도 여기서 단일 출처화 — `judge/cosmetic.py`·`make_fixtures.py`의 하드코딩된
근거 문자열을 이걸로 교체(드리프트 방지).

#### 4. 금지표현·성분표 구조화 추출
`scripts/extract_reference_tables.py`: 마크다운 표(사람이 읽기용)를
`src/barum/reference/data/*.json`(기계가 정확 조회용)으로 파싱. 성분 정합 같은 대조는
의미검색이 아니라 정확 조회 문제라는 판단(PM2 확정). 금지표현 셀은 쉼표·가운뎃점이
섞여 자동 분리 위험 커서 행 단위까지만 구조화, 문구 리스트는 원문 유지.

#### 5. 성분 정합 후처리 (CheckRequest 스키마 확장)
계획에 있던 "성분 정합"은 원래 입력 스키마에 전성분이 없어 막혔던 지점 — 하니에게 확인
후 `POST /check`에 `ingredients`(콤마구분, optional) 폼 필드 추가로 해결.
- PromptJudge가 2호(기능성오인) finding에 한해 표방 기능을 키워드로 추정 →
  `functional_ingredients.json`과 정규화 대조 → explanation에 "확인됨"/"위반 소지 큼" 안내
- StubJudge는 파라미터만 받고 무시(오프라인 시연용)
- 실판정 스모크(Gemini) 확인: 나이아신아마이드 있음→"확인됨, 기준 2~5%", 없음→"고시원료가 전성분에 없음"

#### 안 한 것(이번 컷)
RAG(임베딩 검색)는 보류. 금지표현 문구를 개별 항목으로 자동 분리하는 것도 보류(수동 검토 필요 판단).

#### ⚠ 알아둘 것: 동시 커밋 이슈
작업 중 다른 세션(디자이너)이 같은 워킹트리에서 동시에 커밋하면서, 내가 스테이징해둔
성분정합 관련 파일들이 그 세션의 커밋(`e2029be`, "docs: AGENTS.md 브랜치명 예시 최신화")에
같이 묶여 들어갔다. **데이터 유실은 없음**(내용 대조로 확인 완료, 테스트 57 통과)이지만
커밋 메시지가 실제 변경 내용과 안 맞는 상태. 여러 세션이 같은 디렉터리(워크트리 아님)에서
동시에 git 작업 중이라 생기는 구조적 리스크라 하니에게 별도 플래그.

#### 검증
- `pytest tests/ -q` → **57 passed** (신규 22: 매핑 5·구조화추출 5·성분정합 3·judge 4·pipeline 2·api 1... 등)
- 실판정 스모크(Gemini) 2건: legal_basis 실제 조항 인용 확인, 성분 정합 있음/없음 양쪽 확인

#### 다음
- RagJudge로 승격할 때 이 매핑·구조화 데이터를 그대로 재사용(슬롯만 교체).
- 팀원B 연락되면 T1~T6→5값 매핑, ingredients 필드 추가가 의도와 맞는지 재확인.
- docs/api/README.md에 ingredients 필드 문서화 필요(다음 프론트 지원 라운드).

---

### 2026-08-11 · 프론트 연동 지원물 (OpenAPI + 픽스처)

브랜치: `feature/be-frontend-fixtures` (`feature/be-prompt-judge` 위에 stacked, unjudged 필드 의존). push·PR 대기.
목적: 0비용·0의존으로 프론트(팀원A)·디자이너를 언블록. 판정 알맹이 없이도 계약(응답 형태)에 바로 붙게 한다.
지시: PM(A 먼저).

#### 무엇을 만들었나
- **`scripts/dump_openapi.py`** → `backend/openapi.json`: API 스펙 파일. 프론트가 타입 생성·목킹에 쓴다. (서버 뜨면 `/openapi.json`·`/docs`로도 제공.)
- **`scripts/make_fixtures.py`** → `backend/fixtures/`: 샘플 CheckReport 3종. 모델로 조립해 스키마 100% 유효.
  - `check_report_image.json` — 이미지 입력(타일 하이라이트), 1·2·4호 골고루.
  - `check_report_text.json` — 문구-only(스팬 하이라이트, tile=null).
  - `check_report_with_unjudged.json` — 미판정 상태 포함('재검사 필요' UI용).
- **`docs/api/README.md`**: 엔드포인트 계약 한 장 + 하이라이트 2모드 + enum 값 + 실행법.
- **`tests/test_fixtures.py`**: 픽스처가 계약을 지키는지 검증(모델 바뀌면 여기서 잡음).

#### 검증
- `pytest tests/ -q` → **35 passed** (신규 픽스처 5). OpenAPI: multipart 요청 + CheckReport 응답 + 스키마 11종 확인.

#### 다음
- 하니 리뷰 반영. prompt-judge 머지되면 이 PR base를 main으로 재지정.
- 이어서 C(규칙집 구조/파서)는 팀원B와 콘텐츠 형태 합의 후.

---

### 2026-08-11 · VLM 프롬프트 판정기 (PromptJudge)

브랜치: `feature/be-prompt-judge` (origin/main 기준). push·PR 대기.
목적: 규칙집(RAG) 없이도 지금 실판정. StubJudge를 실동작 판정기로 대체해 데모를 end-to-end로 돌린다.

#### 무엇을 만들었나
- **`PromptJudge`** (`judge/cosmetic.py`): VLM 제로샷 판정. `score_eval.py`의 검증된 `JUDGE_PROMPT`를 공유(원본을 cosmetic.py로 옮기고 score_eval이 import). 문장 배치(기본 12) 판정 → 위반 라벨만 Finding.
- **판정기 슬롯 계약 변경**: `CosmeticJudge.judge`가 `JudgeResult{findings, unjudged}` 반환. StubJudge도 맞춤.
- **미판정(unjudged) 표현**: 모델 `models.py`에 `UnjudgedSentence` + `CheckReport.unjudged` + `Summary.n_unjudged` 추가.
- **API 배선**: 기본 judge = PromptJudge(JUDGE_PROVIDER, 기본 Gemini). 오프라인/키없음용 `JUDGE_KIND=stub` 스위치.

#### 핵심 결정: 배치 실패는 '스킵'이 아니라 '미판정'
recall 우선이라 판정 실패 문장을 조용히 버리면 '합법'으로 오인돼 미탐이 숨는다. 그래서:
- VLM 호출은 재시도 안 함(과금 정책). 하지만 실패 문장을 드롭하지 않고 `unjudged`로 남겨 '재검사 필요'로 드러낸다.
- 모델이 결과를 빠뜨리거나 규격 밖 라벨을 줘도 합법으로 삼키지 않고 미판정 처리.

#### 결정점 (하니 승인, veto 가능)
1. span = 전체 문장 (프롬프트가 문장 단위 라벨). span 정밀추출은 후순위.
2. risk = 유형별 고정 매핑(1호=고, 2호=중, 4호=중). 프롬프트가 위험도 안 줌.
3. 배치 ~12문장, 실패 시 미판정.

#### 검증 결과
- `pytest tests/ -q` → **30 passed** (신규 test_judge 5 포함). VLM은 가짜 어댑터 주입.
- score_eval `--dry` 정상(공유 프롬프트 일치).
- **실판정 스모크(Gemini)**: 텍스트 4문장 → 3위반(2호 주름개선·1호 아토피치료·4호 3배) 정확, 보습크림은 합법. 실이미지(OCR+판정 2회) → 6문장 4위반(완벽한→4호, 탄력→2호, 파워수분→4호, 진정→1호), 미판정 0, 에러 없음.

#### 다음
- (여전히 블로커) 규칙집 완성 → `RagJudge`로 근거 조항·성분정합 정밀화. PromptJudge는 그 전까지의 실판정 베이스라인.
- 규칙집+실judge 후 43문장 Gemini vs GPT 비교표(과금, 하니 승인).

---

### 2026-08-11 · 판정 백엔드 API 골격 (규칙집 없이 선구축)

브랜치: `feature/be-api-skeleton` (로컬 커밋 `52e1367`, push·PR 대기).
지시: `docs/handoffs/2026-08-11-backend-api-skeleton.md`.
로드맵 위치: 2주차 "판정 프로그램" + "화면 뼈대 넘김"의 선행 골격. 규칙집(1주차 크리티컬 패스) 대기 중에 그 주변을 먼저 만들어 프론트를 언블록하는 작업.

#### 무엇을 만들었나
- **I/O 계약(Pydantic)** `src/barum/models.py`: `CheckReport` · `Finding` · `Summary` · `Location` · enum(`Region`·`ViolationType`·`RiskLevel`).
- **FastAPI 스켈레톤** `src/barum/api/app.py`: `POST /check`(multipart, 동기) + `GET /health`.
- **파이프라인 배선** `src/barum/pipeline.py`: 이미지 → tile_split → OCR(vlm) → 문장 → judge → 리포트. 텍스트 경로 포함.
- **Judge 슬롯** `src/barum/judge/cosmetic.py`: `CosmeticJudge` 프로토콜 + `StubJudge`(더미).
- **실행/테스트**: `scripts/run_api.py`, `conftest.py`, `tests/test_{models,pipeline,api}.py`.

#### 확정 사항 (이번 인터뷰, 하니 승인)
- **위반유형 enum = 5값**: `합법` + `1호_의약품오인` + `2호_기능성오인` + `4호_거짓과장기만` + `대상외`. 화장품 체계라 3호 없음(`reference/cosmetic_kr` 기준). 직렬화 값은 한국어 라벨(score_eval·reference와 일치).
- **입력 = multipart/form-data**: `region`(form) + `ad_text`(form, optional) + `image`(UploadFile, optional). 둘 다 없으면 422. base64 안 씀.
- **동기 응답**. stateless 정합·데모 규모·프론트 fetch 한 번·되돌릴 수 있음이 근거. 타임아웃 넉넉히(keep-alive 120s).
- **Provider = env 스왑**(`OCR_PROVIDER`/`JUDGE_PROVIDER`), 기본값 **Gemini**. GPT 하드코딩 안 함. 로드맵 "판정 AI=Gemini 무료 키" 원칙.
- **Supabase 안 붙임**. 자가검증=요청/응답이라 DB 불필요. 현 `schema.sql`은 식품 감시용이라 형태 안 맞음.

#### 착수 중 default로 정한 것 (하니 veto 가능)
1. `location = {tile, order}`. OCR이 bbox를 안 줘 좌표 대신 타일명+문장순서.
2. 이미지+글 둘 다 오면 이미지 문장 뒤에 글 문장 append(order 이어짐).
3. CORS `allow_origins=["*"]`. 프론트 dev 서버 언블록용. 서비스화 때 좁힘.

#### 검증 결과
- `pytest tests/ -q` → **25 passed**(신규 13 + 기존 검수기 12). VLM은 목킹 없이 가짜 어댑터 주입으로 순수 로직만.
- 서버 스모크: `/health` ok, 텍스트 `/check` 200, 빈 입력 422, region 밖 값 422.
- **실이미지 OCR 스모크**(Gemini 1회, `08_24505724_detail_007.png` 1타일): 6문장 추출 → 1건 판정(StubJudge). `location.tile` 채워짐. 이미지→타일→OCR 실동작 확인.

#### 실행법
```bash
cd backend
./venv/bin/python scripts/run_api.py            # 0.0.0.0:8000
./venv/bin/python -m pytest tests/ -q
```
> ⚠️ venv의 `pip` 스크립트 shebang이 리네임 전 경로(`final-project/venv`)를 물고 있어 깨져 있음. 의존성 설치는 `./venv/bin/python -m pip install ...`로 우회. venv 재생성 여부는 하니 판단 대기.

#### 안 한 것 (이번 컷)
실제 판정 로직(규칙집 RAG), Supabase/DB, 인증, 리포트 UI, 미국 세부 규제, Gemini vs GPT 비교표 실행.

#### 다음
- (블로커) 규칙집(레퍼런스팩) 완성 → `RagJudge`를 `judge/cosmetic.py` 슬롯에 구현. 나머지 코드 불변.
- 규칙집+실judge 붙은 뒤 43문장으로 Gemini vs GPT 비교표(과금, 하니 승인).
- 프론트(팀원B)가 `CheckReport` 스키마에 붙기 시작.

---

## 9. 프론트엔드 상세 이력 (구 `PROGRESS_FE.md` 통합, ~2026-08-12까지)

> 담당: 프론트엔드 세션(안티그래비티). 아래는 시간 역순(최신이 위) 작업 로그 원문이다.

### 2026-08-12 · [Micro-step 13] 마이페이지 Pro 전용 대시보드 및 SVG 스파크라인 차트 구현 완료

#### 무엇
- [mypage/page.tsx](file:///c:/dev/barum/frontend/app/mypage/page.tsx)에서 Pro 등급 활성화 시에만 노출되는 "이력 통합 대시보드" 및 8주 주별 추이 스파크라인 SVG 차트를 정밀하게 구현했습니다.
  - 막대 너비 `28px`, 막대 간 갭 `2px` 등간격 분배 (시작 x 좌표 `1px + i * 30px` 계산으로 정확한 2px 갭 간격 준수).
  - 막대 상단 4px 라운드 처리(`rx="4"`)를 하되, 하단부 라운딩은 SVG 경계선 바깥으로 height를 연장하여 자연스럽게 잘리도록 처리.
  - 마지막 8주차 막대만 `var(--crit)` 빨간색 강조하고 이전 1~7주차 막대는 무채색 `var(--ink-3)` 처리.
  - 마우스 호버 시 주차별 상세 검사 건수가 native 툴팁으로 뜨도록 `<title>` 노드를 삽입해 보완.

---

### 2026-08-12 · [Micro-step 12] 마이페이지 요금제 전환 스위치 및 비교 모달 구현 완료

#### 무엇
- [mypage/page.tsx](file:///c:/dev/barum/frontend/app/mypage/page.tsx)에서 요금제 등급(Free, Basic, Pro)을 테스트용으로 동적 전환할 수 있는 `tierSwitch`를 바인딩하고 사용량 한도 및 기능 활성화 상태가 실시간으로 재계산되도록 UI를 연동했습니다.
- 요금제 비교 모달(`compareModal`) 노출 여부 상태 제어를 연동하고, Esc 키 입력 및 모달 백드롭 클릭 시 모달이 닫히도록 접근성 키보드 제어 및 포커스를 보완했습니다.

---

### 2026-08-12 · [Micro-step 11] 마이페이지 요금제 및 사용량 대시보드 정적 UI 구현 완료

#### 무엇
- `/mypage` 라우트에 마이페이지를 새로 개설하고, 요금제별 카드 목록과 이번 달 사용량 게이지(Progress Bar) 정적 뼈대 레이아웃을 이식했습니다.
- 사용량 게이지는 비긴급 상태 피드백 성격에 맞춰 무채색 회색 계열(`var(--ink-3)`)로 렌더링되도록 디자인 가이드라인을 반영했습니다.

---

### 2026-08-12 · [Micro-step 10] 리포트 화면 지적 카드 및 액션 구현 완료

#### 무엇
- [ReportClient.tsx](file:///c:/dev/barum/frontend/app/report/%5Bid%5D/ReportClient.tsx)에 지적 카드 목록 동적 렌더링을 구현하고, `@phosphor-icons/react` 아이콘 및 텍스트 조합을 활용하여 디자인 규격(삼중 경보 신호)을 준수했습니다.
- 지적 카드의 "수용", "제외", "보류" 액션을 상태 관리에 연동하였으며, "제외" 처리 시 헤더의 위반 카운트 및 유형별 칩 개수가 실시간으로 재계산되어 업데이트되도록 수치 연동을 완료했습니다.
- 미판정 데이터가 존재할 시 알파벳 기호 배지와 함께 노출되는 "재검사 필요" 섹션을 하단에 구현했습니다.
- Windows 로컬 preflight 테스트(pytest 182건 전부 통과)를 완료했습니다.

---

### 2026-08-12 · [Micro-step 2] 홈 화면(HomePage) 정적 레이아웃 이식 완료

#### 무엇
- `barum.html` 목업을 기반으로 홈 화면의 정적 마크업을 [page.tsx](file:///c:/dev/barum/frontend/app/page.tsx)에 완벽히 이식하였습니다.
  - 미확인 알림 바(`needbar`), 히어로 영역, 국내/해외 2입구 카드, 최근 프로젝트 목록, 하단 컴플라이언스 및 상태바 마크업 이식.
  - 대상국 선택 모달(`regionModal`)은 `hidden` 상태로 마크업만 배치 완료. (상태 제어는 Micro-step 3에서 추가 예정)
- [globals.css](file:///c:/dev/barum/frontend/app/globals.css) 하단에 홈 화면 전용 CSS 스타일 및 모바일 반응형 미디어 쿼리를 이식하였습니다.
- 로컬 PC 환경에 대응하여 PATH 환경 변수를 갱신하고 `npm run lint` 및 `npm run build` 검증(Turbopack)을 성공적으로 마쳤습니다.
- Windows 환경에서의 preflight 실행 호환성을 위해 [preflight.py](file:///c:/dev/barum/scripts/preflight.py)의 `cp949` 유니코드 인코딩 크래시 오류(em-dash)를 수정하였으며, 최종 preflight 빌드 및 테스트 패스를 확인하였습니다.

---

### 2026-08-12 · [Micro-step 1] AppShell 사이드바 내비게이션 활성화 완료

#### 무엇
- [AppShell.tsx](file:///c:/dev/barum/frontend/components/AppShell/AppShell.tsx) 사이드바 내비게이션 메뉴에 마이페이지 (`/mypage`) 항목을 추가하였습니다.
- 목업 파일에 사용된 프로필/유저 형태의 SVG 아이콘과 라벨을 활성화하고, 현재 경로가 `/mypage`일 때 활성화 스타일(`on`)이 적용되도록 연동하였습니다.
- 브랜드 아이덴티티(BI)가 수립되지 않은 임시 레이아웃 상태로 뼈대를 선구축하였습니다.

---

### 2026-08-12 · 안티그래비티 연동 세팅 + 진행기록 분리

#### 무엇
프론트엔드 개발을 안티그래비티(Antigravity)에서 진행하기로 하면서, 이 파일(`PROGRESS_FE.md`)을 새로 만들어
프론트 세션 기록을 백엔드(`PROGRESS_BE.md`)와 분리했다. `ROADMAP.md`는 하니 소관 팀 공용 문서라 이 세션에서
건드리지 않는다.

#### 문제: 안티그래비티가 작업 규칙을 자동으로 못 읽음
안티그래비티는 프로젝트 루트의 `AGENTS.md`를 자동으로 읽는다(Claude Code의 `CLAUDE.md`와 같은 위치의
자동로드 파일, `@파일명` import 문법 지원). 그런데:
- 이 프로젝트의 실제 작업 규칙(착수 시 인터뷰 우선·코드 취향·디자인 안티슬롭 규칙)은 `CLAUDE.md`에 있고,
  `CLAUDE.md`는 Claude Code 전용 자동로드 파일명이라 안티그래비티는 그 존재를 모른다.
- `.claude/`(`launch.json`, `commands/interview.md`)는 Claude Code 전용 설정이라 안티그래비티가 못 읽는다.
  다만 `commands/interview.md`(인터뷰 우선 슬래시커맨드)는 내용이 `CLAUDE.md` §A와 중복이고,
  `launch.json`은 Claude Code 프리뷰 전용 dev서버 설정이라 안티그래비티엔 해당 없음(자체 실행 방식 사용).
  → 둘 다 별도 이관 불필요.

**조치**: 루트 `AGENTS.md`에 `@CLAUDE.md` import 한 줄을 추가해, `AGENTS.md`만 자동으로 읽는 툴(안티그래비티)도
`CLAUDE.md`의 작업 규칙을 같이 로드하게 함. `AGENTS.md`의 Git 협업 규칙 스코프 자체는 안 건드리고,
import 옆에 목적을 명시하는 인용구만 추가함.

#### 확인 안 된 것 (다음 세션이 검증)
- 안티그래비티가 실제로 `AGENTS.md`의 `@CLAUDE.md`를 로드해서 규칙을 지키는지 아직 실기 검증 안 함
  (문서상 지원 확인만 함). 첫 안티그래비티 세션에서 "CLAUDE.md 규칙 알고 있어?" 등으로 로드 여부부터 확인할 것.
- `design/mockups/barum-report.html`, `barum-mypage.html`이 이미 존재하는데(오늘 반영), `ROADMAP.md`는 아직
  "리포트 화면 파일 자체가 없음"으로 돼 있어 최신 상태와 어긋남. 이 세션은 `ROADMAP.md`를 안 건드리므로
  갱신은 하니 확인 후 별도 처리.

#### 다음
- 안티그래비티에서 실제 프론트 작업 착수 전, `CLAUDE.md` §A(착수 규칙)대로 인터뷰부터 한다.
- 디자인 작업 착수 시 `design/mockups/DESIGN.md`(규칙 마스터)·`design/mockups/HANDOFF.md` §3(안티슬롭 5규칙)·
  §4(색각이상 검증 절차) 먼저 확인한다(CLAUDE.md §F).
