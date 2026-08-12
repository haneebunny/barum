# ROADMAP: barum 실행 로드맵 (v1.8)

> 성격: 가변 상태 문서(진행·할 일·담당·일정). 확정 결정은 `PROJECT.md`, 작업 규칙은 `CLAUDE.md`.
> 갱신일: 2026-08-11(D-16). 발표일: 2026-08-27(수). 기준 기획서: `2조_최종프로젝트_기획서_v1.8.docx`.
> 방향: 화장품 광고 컴플라이언스 자가검증(브랜드용). 국내 1단계 + 미국 프리플라이트(조건부 2단계). LLM+RAG.

---

## 0. 30초 요약

- 광고(이미지/글)를 넣으면 화장품법 위반 위험을 문구별로 짚어 주고, 무슨 조항 위반인지 근거까지 보여 주는 서비스.
- 화면 4개(홈 · 새 검사 · 결과 리포트 · 콘텐츠 생성, v1.7부터 콘텐츠생성 추가) + 판정 프로그램 + 규칙집(법령·금지표현·성분표) + Supabase 이력/증거보존.
- v1.8: 위험도(고/중/저) 등급을 폐지하고 **위반/검토필요 이진 플래그**로 단순화. 화장품법 위반유형은 개정법 기준 **5호**(4호는 AI조항, 판정 라벨 아님).
- **판정 백엔드는 이미 안정화 단계.** 규칙집 완성 + RagJudge(규칙 우선 + VLM fallback) + RAG grounding(규정 인라인 + 실사례 벡터검색) + Supabase 이력저장까지 구현·코드리뷰·머지 완료(PR 7개). 다음은 프론트 통합과 다음 우선순위 결정.
- 판정 AI는 GPT-5-mini(2026-08-11 전환 완료, 43문장 평가셋 비교 근거 있음). OCR은 Gemini. 개발은 Antigravity·Claude Code. 돈은 사실상 0.

---

## 1. 지금 상태 (2026-08-11 기준)

### 백엔드: 완료
- 화장품법 4→5호 리네임(2026.11.27 개정법 반영).
- v1.8 위험도 폐지 → `JudgmentFlag`(위반/검토필요) 이진화.
- 레퍼런스 팩(`reference/cosmetic_kr/`): 금지표현 T1~T6, 성분표, 적발사례, 1호 경계표현 규정 리서치.
- `RagJudge`: 규칙 우선(검증된 경계표현) + 미매칭만 VLM fallback.
- RAG grounding: 규정문서는 fallback LLM에 인라인, 실사례는 Supabase pgvector로 유사 top-K만 검색.
- Supabase DB 도입(FR-1 증거보존 + 검사 이력): 로그인 없이 추측불가 `result_id`로 "다시 보기"(`GET /reports/{id}`, `/image`). 스키마 `backend/db/schema.sql` 적용 완료.
- 판정 오프바이원 버그 수정(RagJudge/PromptJudge 전체에 영향 있던 신뢰도 문제, 회귀테스트 있음).
- Location 좌표 확장(이미지 밴드 하이라이트용), score_eval.py 500버그 수정, provider Gemini→GPT-5-mini 전환.
- **PR 7개 전부 main 머지 완료.**

### 프론트/디자인: 진행 중
- 홈(`barum.html`)·검사 화면(`barum-inspect.html`) v1.8 반영 완료(등급배지 제거, 대상국 미국만 활성화, 검수지시 섹션 제거, 제품정보 입력 블록 신설, 용어 정리).
- **결과 리포트 화면(`barum-report.html`)은 아직 파일 자체가 없음.** 콘텐츠 생성 화면도 착수 전.
- 열린 질문 2건 답변 대기: 지적카드(Finding) 액션 인터랙션 수준, tsx vs HTML 목업 진행 방식.

### 안 한 것 (다음 우선순위, 하니 결정 필요)
- FR-14(수정 권고안 생성) · FR-11/13(콘텐츠 생성, 이미지 포함): 규칙집·판정엔진 안정화 조건은 충족, 아직 착수 전.
- 미국 프리플라이트(2단계).
- score_eval.py 43문장 재검증(5호 리네임·규칙집 반영 후 재실행 안 함).
- 리포트 화면·콘텐츠생성 화면 프론트 구현, 화면↔판정 프로그램 연결.

---

## 2. 앞으로 (남은 D-16, 결정 대기 항목 포함)

### 이번 주 (~8/15)
- [하니 결정 필요] 다음 백엔드 우선순위: FR-14 먼저? 콘텐츠생성(FR-11/13)? 미국 프리플라이트?
- [정빈] 디자이너 열린질문 2건 답변받고 리포트 화면(`barum-report.html`) 착수.
- [정빈] tsx vs HTML 목업 진행방식 결정에 따라 화면 코딩 착수.

### 2주차 (8/18~22) · 통합
- 화면 ↔ 판정 프로그램 연결(리포트 화면이 실제 `CheckReport`/이력 API 소비).
- 콘텐츠 생성 화면(결정되면) 착수.
- 다음 우선순위 기능(FR-14 또는 FR-11/13) 구현.

### 3주차 (8/25~27) · 합치고 발표
- 진짜 광고 넣으면 리포트까지 한 번에 나오게 마무리.
- 채점: 판정 프로그램을 평가셋(43문장, 갱신된 규칙집 기준 재실행)에 돌려 "몇 % 맞히나" 확인.
- 발표 시연 1개 확실히(미백 크림 이미지 업로드 → 위반 뜸 → 문구 수정 → 재검사하니 사라짐) + 2분 녹화 백업.
- 여유되면 미국 선크림 1건 시연.

---

## 3. 담당

| 일 | 담당 | 비고 |
|---|---|---|
| 판정 프로그램 + 규칙집 | 대수 | **완료.** 다음 우선순위 결정 대기 중(대기 세션) |
| 화면(리포트·콘텐츠생성) | 정빈 | 열린질문 2건 답변 후 착수 |
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
2. 다음 우선순위(FR-14 vs 콘텐츠생성 vs 미국)를 빨리 정해야 D-16 안에 뭐라도 하나 끝낸다.
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
| `src/barum/judge/rag_judge.py` 등 | RagJudge(규칙우선+VLM fallback), RAG grounding | 완료 |
| `backend/db/schema.sql` | Supabase 스키마(이력+증거보존, RLS) | 적용 완료 |
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
