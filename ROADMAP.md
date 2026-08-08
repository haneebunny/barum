# ROADMAP: vericops 가변 상태(진행·할 일·데이터)

> **성격:** 가변 상태 문서(진행상황·우선순위 할 일·데이터 현황). 프로젝트 정의·아키텍처·확정 결정은 `PROJECT.md`, 작업 규칙은 `CLAUDE.md`, 도메인 정의는 `reference/`.
> **작업 폴더:** `/Users/hani/Desktop/project/vericops/`. **모노레포**(`backend/` Python, `frontend/` Next.js).
> **갱신일:** 2026-08-07 (모노레포 재구성 + 선생-학생 전략 반영. 이전 08-04 판은 순수 VLM 판정 프레이밍이라 폐기.)

---

## 0. 30초 요약

- **목표:** 이커머스(11번가/쿠팡) **다이어트 보조제 상세페이지 이미지**에서 **과대·부당광고**(식약처 기준 위반)를 판정한다.
- **판정 전략 = 지식 증류(선생·학생).** VLM(Gemini/Claude)=자동 라벨러+베이스라인(선생), 우리 DL 문장분류기=코어 산출물(학생). **상세·확정 결정은 `PROJECT.md` §2·§3 참조(되돌리지 말 것).**
- **현재까지:** 수집→타일분할→OCR→VLM prescreen→goldset/holdout 빌드까지 **파이프라인 가동**. 식약처 레퍼런스·DB 스키마·VLM 어댑터 **완료**. 사람 라벨링 **진행 중**.
- **다음 1순위:** 사람 라벨 확정 → **DB 임포트 관**(병렬) → **DL 코어 ① 학습·평가**.

---

## 1. 전략 (선생-학생, 2026-08-04 확정 · PROJECT.md 소관)

순수 VLM 판정에서 **VLM 라벨러(선생) + 우리 DL 코어(학생: ① 한국어 문장 분류기 + ② 이미지유형 CNN 라우터)**로 재설계.

- 옛 "VLM 판정 스크립트"는 폐기가 아니라 **자동 라벨러(prescreen)로 재활용**(이미 구현됨: `src/vericops/judge/prescreen.py`).
- 진짜 1순위 산출물 = **DL 코어 ① 학습 파이프라인** (Phase 1: 문장+주변 문맥 / Phase 2: +원료 메타).
- 미탐 회수 = 캐스케이드(1차 VLM → 2차 타모델 재판정 F19 → 3차 표본 관리자 F15).
- **판정 라벨 체계(현행, `reference/violation_types/` 기준):** {합법, 1호_질병표방, 2호_의약품오인, 3호_건기식오인, 4호_거짓과장, 5호_소비자기만, 대상외}. ※ 08-04 옛 6종(후기보증·안전성단정 등)은 폐기, reference와 일치시킴.

---

## 2. 현재 파이프라인 진척도

```
수집(11st view-desc)✅ → 타일분할✅ → OCR✅ → 회피표기 정규화(⑤)❌
  → VLM prescreen(product_type+keep+hint)✅ → goldset·holdout 빌드✅ → 사람 라벨링⏳
  → [schema.sql✅] DB 임포트❌ → 학생① 학습❌ → 평가(미탐율/recall)❌ → 캐스케이드 F19/F15❌ → F18 재학습❌
② 이미지유형 CNN 라우터❌   ·   웹앱(reviewer/admin)❌(목업만)
```

### 구현 완료 (✅): 파일별 (경로는 `backend/` 기준)

| 파일 | 역할 | 상태 |
|---|---|---|
| `collect_11st_details.py` | 11번가 상세 수집기. Open API 검색/`--codes`/`--from-json` → `view-desc` 이미지 다운로드. 중복제거 A(상품)+B(해시) 내장. | ✅ |
| `tile_split.py` | 스마트 타일 분할(글자 없는 줄에서 절단 +80px 겹침). | ✅ |
| `eleventh_st_crawler.py` | 11번가 Open API 크롤러(썸네일). **API 키 env화 완료**(`ELEVENTH_ST_API_KEY`). | ✅ |
| `fetch_11st_desc.py` / `probe_11st_detail.py` | 상세 URL 취득 함수 / Playwright 네트워크 프로브(참고용). | ✅ |
| `src/vericops/vlm.py` | **VLM provider 어댑터**(Gemini). provider-agnostic, RPM 스로틀. Claude 교체는 어댑터 추가만. | ✅ |
| `src/vericops/preprocess/ocr.py` + `scripts/run_ocr.py` | OCR 파이프라인(상세이미지→문장). | ✅ |
| `src/vericops/judge/prescreen.py` + `scripts/run_prescreen.py` | **prescreen**: product_type 판정 + 문장 keep + 유형 hint(층화용). | ✅ |
| `scripts/build_goldset.py` · `build_holdout.py` · `validate_holdout.py` | 정답셋/홀드아웃 빌드·검증. | ✅ |
| `schema.sql` | Supabase Postgres 7테이블 + `current_labels` 뷰. | ✅ (적용 대기) |
| `reference/` | 법령 5 + 위반유형 7 + 사례 40건. (옛 "2순위 레퍼런스", **완료**) | ✅ |
| `legacy/vlm_judge.py` | 폐기된 옛 상품단위 VLM 판정 스크립트(보관용). | 🗄️ |

### 중복제거 A/B (수집기 내장, 실측 작동)
- **A. 크로스런 상품 스킵:** `11st_output/details/{code}/`에 있으면 재수집 안 함. `--force`로 무시.
- **B. 완전동일 해시 dedup:** 바이트 같은 이미지는 1회만 저장. 인덱스 `11st_output/.dedup_index.json`.

---

## 3. 데이터 현황 (2026-08-07)

| 자료 | 규모 | 위치(gitignore) |
|---|---|---|
| 11번가 상세 수집 | **상품 279개**, 타일 분할 **274개** | `backend/11st_output/` |
| 쿠팡 상세(데모 시드) | 상품 5개, 이미지 45장 | `backend/coupang_output/` |
| OCR 문장 | 40상품(초기 배치) | `backend/data/ocr_sentences*.jsonl` |
| VLM prescreen | **132상품 / 4,225 keep 문장** | `backend/data/prescreen.jsonl` |
| **goldset**(정확도 측정용) | 48상품 / **215문장** | `backend/data/goldset_master.jsonl` (+ `goldset_A/B.xlsx`) |
| **holdout**(미탐율 평가용) | 65상품 / **331문장** | `backend/data/holdout_master_v1.jsonl` (+ `holdout_B.xlsx`) |
| A/B 교차검증 라운드 | round3·4 | `backend/data/alignment_round*.{jsonl,xlsx}` |

- **사람 라벨링 진행 중** (~200~300문장 규모, goldset 우선 / A·B 두 라벨러 교차검증). ⚠️ goldset/holdout의 `hint`는 VLM 층화용 내부 정보다. **사람 정답 라벨은 xlsx에서 확정**되며 아직 미완.
- 라벨 분포(현재 VLM hint 기준, 참고): goldset은 합법 75·1호 46·4호 32·5호 31·3호 29·2호 2 / holdout은 합법 202·5호 44·1호 37·3호 26·4호 20·2호 2. **2호(의약품오인) 극소 → 실측 시 클래스 불균형 유의.**

---

## 4. 앞으로 할 일 (우선순위 순)

지금은 **하류 작업 대부분이 "사람 라벨 확정"에 묶여 있다**(학습·평가·웹앱 실데이터). 두 갈래로 진행.

### 🥇 1순위: 라벨 확정 + (병렬) DB 임포트 관
- **(A) 사람 라벨 확정**: goldset/holdout xlsx 라벨링 마무리 + **A/B 정합성(κ·불일치 리졸브)** = 학습 데이터 품질 게이트. `alignment_round*` 데이터 재활용.
- **(B, 병렬·비블로킹) DB 임포트 파이프라인**: `schema.sql`을 Supabase에 적용 + **xlsx→DB 로더**. 라벨 끝나면 즉시 흘려보낼 관. (append-only labels, `label_source`, `approved_for_training` 가드레일 준수. 사람 승인 라벨만 학습.)

### 🥈 2순위: DL 코어 ① 학습·평가 (진짜 핵심 산출물)
- **KoELECTRA-base** 출발, 입력 = 문장(span) + 주변 문맥. holdout으로 **정밀도/재현율·미탐율(recall 우선)** 측정, VLM 베이스라인과 비교.
- 백본 후보(KLUE-RoBERTa 등) 실측 비교로 최종 확정. Colab T4(~$0).

### 🥉 3순위: 미탐 회수 캐스케이드 (F19/F15)
- 1차 "합법"을 **다른 모델**로 재판정(F19, 저비용 자동) → 표본 관리자 최종(F15). 판정자 상관 낮춰 미탐 회수.

### 4순위: 웹앱 (frontend, reviewer/admin)
- Next.js + backend API. MVP B단계(로그인, reviewer/admin 2역할). 디자인 = `design/mockups/`. **← 이번에 착수.**

### 5순위: ② 이미지유형 CNN 라우터
- 전이학습(인증서·후기·성분표·제품컷 세그먼트). "이미지 DL 요건" 충족용, 재학습 루프 제외.

### 6순위: 회피표기 정규화(⑤) 룰 사전 · near-dup(pHash) · lazy-load 폴백(Plan A)
- 룰 기반 사전(관리자 갱신) / 시각적 중복 pHash / `view-desc` 빈 셀러 Playwright 폴백. 모두 옵션·후속.

---

## 5. 실행 환경 & 명령어

- **Python 3.11.9**, venv = `backend/venv/` (설치: `pip install -r backend/requirements.txt`).
- **키:** `backend/.env`에 `GOOGLE_API_KEY`(Gemini), `ELEVENTH_ST_API_KEY`(11번가). 예시 = `backend/.env.example`. **하드코딩 금지(public 리포).**
- **⚠️ 스크립트는 `backend/`에서 실행** (상대경로로 `data/`·`11st_output/` 참조).

```bash
cd backend

# 11번가 상세 수집 (중복 자동 스킵)
./venv/bin/python collect_11st_details.py "다이어트 보조제" --max-products 30

# 수집분 타일 분할
./venv/bin/python tile_split.py 11st_output/details --recursive

# OCR → prescreen
./venv/bin/python scripts/run_ocr.py
./venv/bin/python scripts/run_prescreen.py

# 정답셋/홀드아웃 빌드·검증
./venv/bin/python scripts/build_goldset.py
./venv/bin/python scripts/build_holdout.py
./venv/bin/python scripts/validate_holdout.py

# 테스트
./venv/bin/python -m pytest -q
```
- 타일 노브: `--target-h 1400` `--max-ratio 2.0` `--overlap 80`.

### 기술 메모: 11번가 상세 취득 경로
```
https://www.11st.co.kr/products/{상품번호}/view-desc
```
- plain HTML 조각, `<img src>`에 상세 이미지 직접 박힘(lazy-load 아님, 안티봇 없음). `product_code == prdNo`.
- 실측: 상세 메인 860×21,800~29,000px 통짜 → 타일 분할 필수. 일부에 **광고심의번호** 노출(합법/위반 신호).

---

## 6. MVP 완성 체크리스트

- [x] 데이터 수집 (11번가 view-desc)
- [x] 중복 제거 A(상품) + B(완전동일 해시)
- [x] 타일 분할
- [x] OCR 파이프라인
- [x] VLM 어댑터(provider-agnostic, Gemini)
- [x] VLM prescreen (product_type + keep + hint)
- [x] goldset / holdout 빌드·검증
- [x] 식약처 레퍼런스(`reference/`)
- [x] DB 스키마(`schema.sql`) 작성
- [ ] **사람 라벨 확정 + A/B 정합성** ← 1순위
- [ ] **DB 임포트(Supabase 적용 + xlsx 로더)** ← 1순위(병렬)
- [ ] **DL 코어 ① 학습 + 평가(미탐율)** ← 2순위
- [ ] 미탐 회수 캐스케이드(F19/F15) ← 3순위
- [ ] 웹앱(reviewer/admin) ← 4순위(착수)
- [ ] ② 이미지유형 CNN 라우터 ← 5순위
- [ ] 회피표기 정규화(⑤) / near-dup(pHash) / lazy-load 폴백 (옵션)

**한 줄 요약: 수집→전처리→VLM 라벨링→평가셋 빌드까지 완성됐고 레퍼런스·DB 스키마·모노레포 정비까지 끝났다. 남은 핵심은 "사람 라벨 확정 → DL 코어 학습·평가"와 "웹앱"이다.**
