# PROGRESS_BE: 바름 백엔드 진행상황

> 성격: 백엔드 세션 진행 기록(가변). 확정 결정은 `PROJECT.md`, 전체 로드맵은 `ROADMAP.md`, 작업 규칙은 `CLAUDE.md`.
> 갱신일: 2026-08-11. 담당: 백엔드 세션(대수) / 검수: 하니.

> ⚠ **PM 정정 (2026-08-11, 하니 확인)**: 기획서 v1.7 확인 결과 거짓·과장·기만이 개정법(2026.11.27 시행)에서
> **4호 → 5호**로 밀림(AI 전문가보증 조항이 신설 4호). `models.py`·`judge/cosmetic.py`·픽스처·reference를
> `type_5_deception`/`5호_거짓과장기만`으로 이미 정정·검증(pytest 35 passed) 완료. 아래 로그의 "4호" 언급은
> 그 시점 기준 원기록이라 남겨두되, 현재 코드 기준은 5호다. 상세: `reference/cosmetic_kr/statute/law_article_13.md`.

---

## 2026-08-12 · 배포 파이프라인(RagJudge) 재평가 + base 대비 개선폭

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
  검토필요로 완화됨(규칙+grounding 효과). 남은 위반 오탐 6건은 완벽/최적/파워 같은 일반수식어 —
  A1 결정으로 규칙에 안 넣고 VLM에 맡긴 것이라 5호 수식어 규칙 확정(다음 이터레이션) 전엔 유지.
- **발표 스토리**: "base 제로샷 60%/미탐1 → 배포 RagJudge 65%/미탐0/하드오탐 절감".
- 결과 파일은 gitignore(로컬): `data/eval_compare.csv`에 두 판정기 나란히, 상세 `data/eval_result_*.xlsx`.

---

## 2026-08-11 · RagJudge 구축 (규칙집 우선 + VLM fallback)

브랜치: `feature/be-rag-judge` (origin/main 기준). PM2 승인 하 착수(계획 검토 후).

### 무엇
판정 슬롯에 `RagJudge`를 추가했다. 규칙집(`reference/rules.py` + `data/judge_rules.json`)으로
확정 가능한 문장은 규칙이 먼저 판정하고, 규칙에 안 걸린 문장만 내부 `PromptJudge`(VLM)에 위임한다.
규칙 확정분은 VLM을 안 부르므로 과금과 과잉판정을 함께 줄인다(Gemini가 진정·탄력을 1호로 과잉판정하던 문제 원천 차단).

### 구조
- `reference/rules.py` — `match_rule(sentence)`가 정규화 문자열 포함 검사로 규칙집을 대조. 우선순위 스캔: violation > needs_review > legal_allow. 미매칭이면 None(VLM 위임).
- `data/judge_rules.json` — 손 큐레이션(자동추출 아님). §3에서 규정 리서치로 검증된 1호 경계표현. violation(아토피·염증·재생·시술·MTS·병원전용 등)/needs_review(진정·안티에이징·피부장벽 등)/legal_allow(탄력·민감·예민).
- `judge/cosmetic.py` — `RagJudge`가 `PromptJudge`를 합성 재사용. StubJudge·PromptJudge는 안 건드림.
- `api/app.py` — `JUDGE_KIND=rag` 분기 추가.

### 결정(PM2 확정)
- 일반 수식어(완벽·파워·탁월·최적)는 규칙에 안 넣음(A1). `type_5_deception.md`가 "3:1 갈림·미확정"이라 결정론적 규칙에 못박지 않고 VLM에 위임.
- 명백 5호(경쟁사비방·"3배"·"최고")도 이번 스코프 제외. 근거는 있으니(type_5 예시표 "O") **다음 이터레이션 5호 규칙 추가 시 우선순위로**.
- co-occurrence("안티에이징 탄력크림"→검토필요)는 우선순위 스캔으로 처리, 테스트로 못박음.

### 후속 조정 대상(오탐 나오면 보고)
- MTS·니들: `type_1`은 "시술 병행·묘사" 맥락일 때 1호. 제품명에 "마이크로니들"이 그냥 들어가면 5호(사용방법 오인)에 가까울 수 있음. 지금은 1호로 분류(근거 있음), 제품명 오탐 나오면 PM2에 보고.
- 짧은 키워드 substring 오매칭: "진정" vs "진정한", "재생" vs "재생성" 등. 광고 카피 특성상 대부분 긍정 표방이라 단순 매칭 유지(CLAUDE.md 단순·안정), 오탐 관측 시 조정.

### 테스트
`test_rag_rules.py`(7) + `test_rag_judge.py`(6) + `test_api.py` 팩토리 1 = 신규 14. 전체 **74 통과**. §3 경계표현 12건 오프라인 스모크 일치 확인.

---

## 2026-08-11 · 백엔드 세션 인수인계 + 1호 경계표현 규정 리서치

이 세션(백엔드 담당) 종료. 다음 세션 인수인계 문서: `docs/handoffs/2026-08-11-backend-session-handoff.md`.

### 1호 경계표현 규정 검증 (평가셋 4자분열 해소)
대수의 43문장 4자 상호비교에서 안정성 0.00이던 1호 경계표현을 실제 규정·해석으로 검증:
- **진정** = 실증대상(law.go.kr 1차해석), **탄력** = 일반허용, **민감/예민** = 상태서술 → 그 자체로 1호 아님.
- **아토피·염증·재생·치료·소독·약국/병원전용·MTS 시술묘사** = 위반.
- 뒤집힌 것: Gemini가 진정·탄력을 과잉판정, 합법으로 본 사람이 규정에 더 부합. `reference/cosmetic_kr`에 출처와 함께 반영(PR #14 머지).

### 판정 3축 확정(대수 재확인 대상)
① 성분·브랜드표기→대상외, ② 일반수식어→5호, ③ 니즈서술문→효능어 기준, ④ 1호경계→표현별. 상세는 핸드오프 §3.

### 이 세션이 완료한 것 (전부 main 머지)
API 골격 → PromptJudge → 프론트 픽스처 → 레퍼런스 팩 반영·T매핑·구조화·성분정합 → v1.8 위반/검토필요 플래그 → provider GPT-5-mini 전환 → 1호 리서치 검증. 테스트 60 통과.

### 다음 세션이 이어갈 것
RagJudge 구축(최우선, 착수조건 성립), Location 좌표 확장(병행 가능), score_eval.py 500-버그. 상세·주의점은 핸드오프 문서.

---

## 2026-08-11 · 판정 provider 기본값 전환: Gemini → GPT-5-mini

브랜치: `feature/be-provider-default` (origin/main 기준). 대수의 43문장 4자 상호비교 평가 결과 반영, 하니 승인.

### 근거
| Provider | 일치율 | 미탐(1급 지표) |
|---|---|---|
| Gemini | 52.5% | 4건 |
| GPT-5 | 62.5% | 0건 |
| GPT-5-mini | 65.0% | 1건 |

recall 우선 정책엔 GPT-5가 제일 맞지만 유료. GPT-5-mini는 미탐 1건에 비용이 거의 공짜라(하니: "GPT-5-mini도 거의 공짜라서 그거 써도 돼") 이걸로 전환.

### 무엇을 바꿨나
- `api/app.py`의 `_build_judge()`: `JUDGE_PROVIDER` 기본값 `"gemini"` → `"openai"`(모델은 `vlm.py`가 이미 `gpt-5-mini` 기본).
- **OCR_PROVIDER는 안 건드림.** 이 비교는 판정 정확도(문장 라벨링)에 대한 것이지 이미지 글자 읽기(OCR) 품질에 대한 게 아니다.
- `ROADMAP.md` §3·30초 요약: "판정 AI=Gemini 무료 키" 확정 문구를 GPT-5-mini로 갱신.

### 검증
- `pytest tests/ -q` → 60 passed(변경 없음, 테스트는 provider 무관).
- 실판정 스모크: env에 provider를 아예 안 정한 상태로 `/check` 호출 → gpt-5-mini가 자동으로 잡혀 정상 판정.

### 다음
- 판정 기준 3축(성분/브랜드표기·일반수식어·니즈서술문) + 1호 재정의는 정책 결정이라 하니에게 선택지 제시 예정. 확정되면 RagJudge 착수.
- Location 좌표 확장은 이 결정과 무관하게 병행 가능(다음 작업).

---

## 2026-08-11 · v1.8: 위험도(고/중/저) 폐지 → 위반/검토필요 이진 플래그

브랜치: `feature/be-judgment-flag` (origin/main 기준). PM2 지시(기획서 v1.8, FR-5·FR-7), 착수 전 계획 승인받고 진행.

### 무엇을 바꿨나
- `RiskLevel`(고/중/저) 삭제 → `JudgmentFlag`(위반/검토필요) 신설. `Finding.risk` → `Finding.flag`로 필드명도 변경(개념이 달라져서).
- `Summary`에 `n_violation`·`n_needs_review` 추가(`n_findings`는 합계로 유지). `n_unjudged`는 별개 개념 그대로.

### 핵심 설계: 근거 없는 유형은 어떻게 판단하나 (RagJudge 오기 전)
"근거 있으면 위반, 근거 없으면 검토필요"(FR-5)인데, 지금 규칙집 대조 수단이 있는 건 2호(기능성오인)의 성분 정합뿐이다.
- **1호·5호**: 대조 수단 없음 → 항상 `위반`(recall 우선, 근거 없다고 함부로 안 낮춤). RagJudge 붙으면 이것도 매칭 성공 여부로 갈릴 예정(범위 밖).
- **2호**: `ingredients` 있고 고시원료 **없음** → `위반`(근거로 확증). 고시원료 **있음** → `검토필요`(등록 여부는 모르니 단정 못 함, 하니 승인). `ingredients` 미입력/카테고리 불명 → `검토필요`(대조 근거 자체 없음).
- StubJudge: 항상 `위반`(데모용, 근거 인프라 없음).

### 부수로 잡은 버그
`PromptJudge`에서 `res.get("results", [])` 호출이 try/except 밖에 있어서, VLM이 가끔 `{"results":[...]}` 대신 통짜 리스트를 뱉으면 `AttributeError`로 **요청 전체가 500** 났다. try 안으로 옮겨 예상된 실패로 흡수(→ 그 배치는 미판정 처리). 실판정 스모크 중 실제로 재현·수정 확인함. `score_eval.py`에도 같은 패턴이 있는데 이번 범위 밖이라 안 건드림(하니 판단 필요, 별도 이슈).

### 검증
- `pytest tests/ -q` → **60 passed**.
- 실판정 스모크(Gemini) 3회: 성분 있음→검토필요, 성분 없음(1호)→위반, 그리고 위 버그 실제 재현 후 정상적으로 미판정 처리되는 것까지 확인.
- fixtures·openapi 재생성, `docs/api/README.md`에 위반/검토필요 vs unjudged 구분 명시.

### 다음
- Location 좌표 확장(타일 y범위, 밴드 하이라이트용) — PM2가 이 작업 다음으로 지정.
- 대수의 4자 상호비교 평가 결과(43문장 라벨링 완료, Gemini/GPT-5/GPT-5-mini 비교)가 나와서, provider 기본값·"검토필요" 범위 확장 여부를 하니와 논의 예정(하니: "GPT-5-mini도 거의 공짜라 써도 됨").

---

## 2026-08-11 · 화장품 레퍼런스 팩 반영 + T-체계 매핑 + 구조화 추출 + 성분 정합

브랜치: `feature/be-reference-pack` (`feature/be-frontend-fixtures` 이후, origin/main 기준 재구성). 커밋 여러 개로 분리.
경위: 대수 연락 두절 중 하니가 대수의 최신 산출물(Downloads의 index·prohibited_expressions·functional_ingredients·cases.md)을
전달, 이 세션이 검토·반영. PM2 승인 받음(방향·T-매핑 확정).

### 1. 4호→5호 리네임 (PM2 작업, 이 세션이 커밋)
개정법(화장품법 제13조, 시행 2026.11.27)에서 AI 생성물 관련 조항이 신설 4호로 들어오며
기존 4호(거짓·과장·기만)가 5호로 밀림. 발표(8/27)가 시행 3주 전이라 개정법 기준으로 미리 맞춤.
`ViolationType.type_5_deception`(라벨 `5호_거짓과장기만`)로 전체 동기화. 신설 4호(AI)는 문구
판정 라벨이 아니라 콘텐츠 생성 가드레일(FR-13) 영역이라 enum에 없음.

### 2. 레퍼런스 팩 최신본 반영
옛 빈 뼈대(`reference/cosmetic_kr/*.md`)를 대수의 채워진 최신본으로 교체:
- 금지표현 목록: T1~T6 유형체계로 상세화(별표1·별표5·실증대상)
- 기능성 성분표: 미백9·주름4·자외선27종 + 기준함량(고시 제2023-61호 별표4 원문 대조 완료)
- 적발사례: 식약처 11개 업체 실사례 + 대규모 점검 집계

### 3. T-체계 ↔ ViolationType 매핑 모듈
`src/barum/reference/mapping.py`: 레퍼런스의 T1~T6과 판정 enum(5값)이 안 맞아서(T5·T6이
둘 다 5호로 접힘, T3·T4는 판정 라벨 아님) 매핑을 코드 한 곳에 뒀다. `legal_basis_for()`로
근거 조항 문자열도 여기서 단일 출처화 — `judge/cosmetic.py`·`make_fixtures.py`의 하드코딩된
근거 문자열을 이걸로 교체(드리프트 방지).

### 4. 금지표현·성분표 구조화 추출
`scripts/extract_reference_tables.py`: 마크다운 표(사람이 읽기용)를
`src/barum/reference/data/*.json`(기계가 정확 조회용)으로 파싱. 성분 정합 같은 대조는
의미검색이 아니라 정확 조회 문제라는 판단(PM2 확정). 금지표현 셀은 쉼표·가운뎃점이
섞여 자동 분리 위험 커서 행 단위까지만 구조화, 문구 리스트는 원문 유지.

### 5. 성분 정합 후처리 (CheckRequest 스키마 확장)
계획에 있던 "성분 정합"은 원래 입력 스키마에 전성분이 없어 막혔던 지점 — 하니에게 확인
후 `POST /check`에 `ingredients`(콤마구분, optional) 폼 필드 추가로 해결.
- PromptJudge가 2호(기능성오인) finding에 한해 표방 기능을 키워드로 추정 →
  `functional_ingredients.json`과 정규화 대조 → explanation에 "확인됨"/"위반 소지 큼" 안내
- StubJudge는 파라미터만 받고 무시(오프라인 시연용)
- 실판정 스모크(Gemini) 확인: 나이아신아마이드 있음→"확인됨, 기준 2~5%", 없음→"고시원료가 전성분에 없음"

### 안 한 것(이번 컷)
RAG(임베딩 검색)는 보류. 금지표현 문구를 개별 항목으로 자동 분리하는 것도 보류(수동 검토 필요 판단).

### ⚠ 알아둘 것: 동시 커밋 이슈
작업 중 다른 세션(디자이너)이 같은 워킹트리에서 동시에 커밋하면서, 내가 스테이징해둔
성분정합 관련 파일들이 그 세션의 커밋(`e2029be`, "docs: AGENTS.md 브랜치명 예시 최신화")에
같이 묶여 들어갔다. **데이터 유실은 없음**(내용 대조로 확인 완료, 테스트 57 통과)이지만
커밋 메시지가 실제 변경 내용과 안 맞는 상태. 여러 세션이 같은 디렉터리(워크트리 아님)에서
동시에 git 작업 중이라 생기는 구조적 리스크라 하니에게 별도 플래그.

### 검증
- `pytest tests/ -q` → **57 passed** (신규 22: 매핑 5·구조화추출 5·성분정합 3·judge 4·pipeline 2·api 1... 등)
- 실판정 스모크(Gemini) 2건: legal_basis 실제 조항 인용 확인, 성분 정합 있음/없음 양쪽 확인

### 다음
- RagJudge로 승격할 때 이 매핑·구조화 데이터를 그대로 재사용(슬롯만 교체).
- 대수 연락되면 T1~T6→5값 매핑, ingredients 필드 추가가 의도와 맞는지 재확인.
- docs/api/README.md에 ingredients 필드 문서화 필요(다음 프론트 지원 라운드).

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
