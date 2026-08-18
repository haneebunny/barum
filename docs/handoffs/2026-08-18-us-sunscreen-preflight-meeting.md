# 회의 자료: 미국 수출 프리플라이트 — 자외선차단 최소보장 (2026-08-18)

> 작성 목적: 수출 관련 백엔드 기능(미국 프리플라이트) 작업 현황을 팀과 공유하고, 남은 결정사항을 확인받기 위한 자료.
> 범위: 기획서 v1.9의 "2단계 미국 프리플라이트" 중 **자외선차단 최소보장** 스코프(v1.6, 2026-08-10 확정)에 한정.

---

## 0. 한 줄 요약

**한국에서 기능성화장품으로 표시·광고 가능한 자외선차단 표현이, 미국에서는 화장품이 아니라 OTC(일반의약품)로 분류됨을 수출 전에 알려주는 기능.** 데이터 조사부터 API 연결·실제 이미지 테스트까지 1~7단계 전부 완료했다.

---

## 1. 왜 이 기능인가 (기획서 근거)

`2조_최종프로젝트_기획서_v1.9.docx` §5 사용자 시나리오 원문:

> "[해외 검증 · 국가 전환] 수출을 준비하는 박기덕은 같은 제품의 검사에서 대상 국가를 미국으로 바꾼다. 리포트는 'SPF50' 표현과 자외선차단 성분이 미국에서는 화장품이 아니라 OTC 의약품에 해당함을 경고하고, 원료 중 미국 FDA 승인 목록에 없는 자외선차단 성분을 지목한다."

- 시장 근거: 한국 화장품 수출 1위 시장이 미국(22억 달러)인데, MoCRA 시행 등으로 한국과 규제 구조가 다름. "자외선차단·미백·주름 표현은 한국에서 기능성화장품이지만 미국에서는 OTC로 분류가 전환됨"
- 이번 스코프는 v1.6(2026-08-10)에서 **자외선차단만으로 좁혀 확정**됐다(미백·주름은 범위 밖).

---

## 2. 작업 흐름 (1~7단계)

```
1. 데이터 수집(원문 대조) → 2. 판정 규칙 문서 → 3. JSON 변환
  → 4. 조회 코드 → 5. 판정 로직 → 6. API 엔드포인트 → 7. 테스트
```

### 1단계 — 데이터 수집

웹서치 요약을 그대로 안 쓰고, **정본 원문을 직접 열람·대조**했다.

- **eCFR 21 CFR 352.10** (law.cornell.edu 미러) — 미국 승인 자외선차단 성분 베이스라인 16종
- **FDA 최종오더 OTC000039** (연방관보 PDF 원문 직접 다운로드) — 베모트리지놀 6% 신규 승인 확인
- **연방관보 공식 API로 오더 이력 전체 조회** — `OTC000006`(2020, 베이스라인) ~ `OTC000039`(2026) 사이 빠짐없이 확인. 그 사이 유일했던 `OTC000008`(2021년 제안, 16종 중 12종 GRASE 재검토 제안)은 **아직 최종화 안 됨** → 잠재 리스크로 기록만 하고 현재 목록엔 미반영
- INCI명(전성분표 표기) ↔ CFR 공식명 매핑표 작성 (일부는 Wikipedia로 재검증, 일부는 미검증 표시)

**결과물**: 미국 승인 자외선차단 성분 **17종** (16종 베이스라인 + 베모트리지놀)

### 2단계 — 판정 규칙 문서

[`reference/cosmetic_us/sunscreen_otc_classification.md`](../../reference/cosmetic_us/sunscreen_otc_classification.md)

**두 갈래 트리거**:
1. **표현 트리거**: "SPF"·"자외선차단" 등 문구가 있으면 성분과 무관하게 **항상** 경고 (미국 의약품 정의상 표현 자체가 트리거)
2. **성분 트리거**: 전성분을 승인 17종과 대조해서, 목록에 없는 성분만 지목

**실제 사례로 검증**: 한국 고시원료 27종(`functional_ingredients.md`) 중 "**드로메트리졸**"이 미국 승인 17종엔 없음 — 한국에선 합법, 미국에선 미승인인 실제 케이스.

### 3~7단계 — 코드화 + 검증

| 단계 | 결과물 | 테스트 |
|---|---|---|
| 3 | `data/us_sunscreen_ingredients.json`, `data/us_sunscreen_synonyms.json` | JSON 문법 검증 |
| 4 | `reference/us_ingredients.py` (성분 조회) | 유닛테스트 11개 |
| 5 | `judge/us_sunscreen.py` (`USSunscreenJudge`) | 유닛테스트 7개 |
| 6 | `POST /check/us-sunscreen` 엔드포인트 | 유닛테스트 6개 |
| 7 | (전체 통합) | **백엔드 전체 223개 테스트 통과** + 실제 이미지 OCR 스모크 테스트 2건 |

`citation_registry.json`에도 출처 2건(`us_fda_m020_sunscreen_baseline`, `us_fda_otc000039_bemotrizinol`) 공식 등록 완료.

---

## 3. 팀 확인 후 확정한 것 (이번 회의 전 사전 결정)

| 항목 | 결정 |
|---|---|
| 판정 성격 | **새 카테고리** — 국내 `ViolationType`/`JudgmentFlag`(위반/검토필요) 재사용 안 함. 미국판은 "위반"이 아니라 "규제 카테고리 전환 안내"라 `USPreflightCategory`(3갈래: OTC의약품_분류전환 / 미국_미승인_성분 / 성분정보_확인불가)를 새로 만듦 |
| 엔드포인트 구조 | 국내 `/check`와 **별도** 엔드포인트(`/check/us-sunscreen`) |
| 국가 파라미터 | 프론트에서 값은 넘기되 **기본값 = 미국**. 다른 값 보내면 400(현재 미국만 지원) |
| `OTC000008` 리스크 노출 방식 | 개별 지적(finding) 아닌 **리포트 하단 각주**로만. 확정 안 된 제안을 경고로 띄우면 사용자가 오해하고, 사용자가 할 수 있는 행동도 없어서 |

---

## 4. 아키텍처: "엔진 하나, 레퍼런스 팩만 교체" 원칙 확인됨

기획서 §3 차별성 "국가는 교체형 레퍼런스 팩" 원칙이 실제로 그대로 구현됐다.

- **OCR(이미지→텍스트)**: 국내·미국 **공용 로직** 그대로 재사용 (국가 무관)
- **판정 로직만 교체**: 국내는 `RagJudge`(VLM 호출), 미국은 `USSunscreenJudge`

### 예상 밖 소득: 미국판은 AI 호출이 아예 필요 없다

SPF/자외선차단 표현은 애매할 여지가 없는 명확한 단어라, 국내 미백·주름과 달리 **판정 자체가 100% 코드만으로 끝난다.** 텍스트만 입력하면 완전히 오프라인·무비용으로 검사가 끝난다(이미지 입력 시 OCR만 AI 사용).

---

## 5. 실제 동작 확인 (스모크 테스트)

합성 테스트 이미지("SPF50+ PA++++ 자외선차단 / 전성분: 정제수, 글리세린, 드로메트리졸, 나이아신아마이드")로 실제 Gemini OCR을 태워 검증.

**결과**: OCR이 문장을 정확히 추출 → "SPF" 감지 → OTC 분류전환 경고 발생. 전성분 중 "드로메트리졸"을 정확히 미승인 성분으로 지목.

```json
{
  "findings": [
    {"span": "SPF", "category": "OTC의약품_분류전환", ...},
    {"span": "드로메트리졸", "category": "미국_미승인_성분",
     "explanation": "'드로메트리졸'은(는) 미국 FDA 승인 자외선차단 성분 목록에 없습니다."}
  ],
  "disclaimer": "본 결과는 법적 자문이 아니며 전문가 확인이 필요합니다. 미국 자외선차단 규정(OTC Monograph M020)은 검토 중인 개정안(OTC000008)이 있어 향후 승인성분 목록이 변동될 수 있습니다."
}
```

---

## 6. 아직 안 끝난 것 / 회의에서 정할 것

1. **INCI 매핑 일부 미검증** — Dioxybenzone·Oxybenzone·Avobenzone의 벤조페논 계열명은 1차 출처 재확인 필요 (`us_sunscreen_synonyms.json`의 `confidence: "unverified"` 항목)
2. **FDA 포털 직접 열람 재검증** — `accessdata.fda.gov` 포털이 봇 차단이라 연방관보 API로 우회 확인함. 포털 원본 대조는 못함
3. **프론트 연동** — 리포트 화면에서 이 새 카테고리(3갈래)를 어떤 UI로 보여줄지 디자인 필요. 국내 리포트(위반/검토필요 배지)와는 다른 톤이 필요
4. **검사 이력 저장 여부** — 지금은 `/check`처럼 Supabase에 저장하지 않음(스코프 밖으로 판단, 필요시 추가 논의)
5. **한국 27종 vs 미국 17종 전수 교차표** — 드로메트리졸 외에 또 어떤 성분이 "한국은 되는데 미국은 안 되는지" 미리 표로 만들어둘지, 아니면 지금처럼 자동 대조로 충분한지

---

## 7. 관련 파일 전체 목록

**레퍼런스(사람이 읽는 정본)**
- `reference/cosmetic_us/sunscreen_active_ingredients.md`
- `reference/cosmetic_us/sunscreen_otc_classification.md`

**백엔드 코드**
- `backend/src/barum/reference/data/us_sunscreen_ingredients.json`
- `backend/src/barum/reference/data/us_sunscreen_synonyms.json`
- `backend/src/barum/reference/data/citation_registry.json` (항목 추가)
- `backend/src/barum/reference/us_ingredients.py`
- `backend/src/barum/judge/us_sunscreen.py`
- `backend/src/barum/models.py` (USPreflightCategory 등 추가)
- `backend/src/barum/pipeline.py` (`run_us_sunscreen_check` 추가)
- `backend/src/barum/api/app.py` (`POST /check/us-sunscreen` 추가)

**테스트**
- `backend/tests/test_reference_us_ingredients.py`
- `backend/tests/test_judge_us_sunscreen.py`
- `backend/tests/test_api_us_sunscreen.py`

**작업 가이드(참고용)**
- `docs/guide_us_sunscreen_preflight.md`
