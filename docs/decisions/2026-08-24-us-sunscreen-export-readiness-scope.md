# 미국 선스크린 수출 준비도 서비스 — 확장 범위 제안

> 기록일: 2026-08-24  
> 상태: **목표 정의 제안 / 구현 미착수**  
> 성격: 현재 미국 프리플라이트 MVP를 대체하지 않는 확장 설계 메모

## 1. 핵심 방향

미국 수출 프리플라이트를 단순한 “이 자외선차단 성분이 미국에서 허용되는가?” 조회 서비스로 정의하지 않는다.

미국에서 선스크린은 일반 화장품이 아니라 OTC 의약품 규제 대상이 될 수 있으므로, 서비스가 답해야 할 질문은 다음으로 확장한다.

> 한국에서 판매 중인 이 선스크린을 미국에서 합법적으로 판매하려면 현재 무엇이 충족되어 있고, 무엇을 바꿔야 하며, 어떤 자료를 추가로 준비해야 하는가?

따라서 최종 제품의 이름은 현재의 “미국 자외선차단 프리플라이트”보다 **미국 선스크린 수출 준비도(US Sunscreen Export Readiness)**에 가깝다.

## 2. 규제 사실 확인

2026-08-24 FDA 공식 페이지 기준으로 다음 사실을 확인했다.

- 미국으로 수입되는 OTC 의약품은 FD&C Act와 21 CFR의 적용 요건을 충족해야 한다.
- 일반적인 수입 요건에는 해외 제조시설 등록, 의약품 Listing, 승인 신청 또는 적용 가능한 OTC monograph 경로, 의약품 표시, CGMP가 포함된다.
- FDA OTC Monographs@FDA에는 M020 행정명령과 관련 자료가 게시된다.
- FDA는 2026-06-10자 OTC000039를 통해 OTC Monograph M020에 Bemotrizinol을 추가했고, 농도·허용 조합·제형 조건도 함께 다룬다.
- 선스크린의 SPF·Broad Spectrum 시험과 Drug Facts·선스크린 전용 표시사항은 별도 규정 및 시험 절차의 적용을 받는다.
- Cosmetic 용도도 함께 가지는 제품은 Drug only / Drug + Cosmetic / Cosmetic only 분류를 별도로 검토해야 한다.

이 문서는 법률 자문이 아니며, 규칙을 코드화할 때 각 항목의 최신 원문·시행일·적용 조건을 다시 대조해야 한다.

## 3. 목표 검증 흐름

```text
한국 제품 자료 입력
  ↓
미국 규제 분류
  ↓
OTC Sunscreen Monograph M020 경로 적용 가능성
  ↓
Formula / Ingredient
  ↓
Testing
  ↓
Label / Drug Facts
  ↓
Marketing Claims
  ↓
Facility / CGMP / FDA Registration
  ↓
Drug Listing / NDC / Import
  ↓
미국 수출 준비도와 보완 항목
```

한국 식약처 적합 여부와 미국 FDA 적합 여부는 하나의 상태로 합치지 않고 별도로 관리한다.

## 4. 지식 도메인

| 도메인 | 우선 확인할 데이터 |
|---|---|
| Product Classification | Drug only / Drug + Cosmetic / Cosmetic only, intended use |
| Ingredient Compliance | INCI, 한국명, CAS/UNII, 기능, active 여부, 농도, M020 상태 |
| Formula Compliance | 제형, 농도 상한, active 조합, dosage form, skin protectant 조합 |
| Testing Compliance | SPF, Broad Spectrum, critical wavelength, water resistance, 시험법, 시험기관, 시험일 |
| Label Compliance | Statement of identity, Drug Facts, active ingredients, purposes, uses, warnings, directions, inactive ingredients |
| Claims Compliance | 패키지·상세페이지·웹사이트·마켓플레이스의 claim과 시험 근거 |
| Establishment Compliance | 제조시설, contract manufacturer, FDA establishment registration, U.S. Agent, importer, CGMP |
| Listing & Import | Drug Listing, NDC 또는 listing number, 라벨 최신본, 수입·통관 준비 |

## 5. 성분 판정의 확장

현재의 미국 MVP는 승인 성분 목록에 있는지 여부만 확인한다. 확장 버전에서는 다음을 분리한다.

- `permitted`: M020 경로에서 조건을 충족할 가능성이 있는 성분
- `concentration_exceeded`: 허용 최대 농도 초과
- `combination_not_covered`: 허용 조합 조건 밖
- `dosage_form_not_covered`: 허용 제형 조건 밖
- `monograph_not_covered`: 현재 M020 경로로 확인되지 않는 active
- `approved_application_route_required`: 별도 NDA/ANDA 등 승인 경로 검토 필요
- `verification_required`: 원료 식별·농도·기능 자료 부족

`monograph_not_covered`를 곧바로 “금지 성분”이라고 표현하지 않는다. 현재 M020 monograph 경로로 판매할 수 없는 상태와, 미국에서 어떤 경로로도 사용할 수 없는 금지는 구분해야 한다.

또한 M020 데이터는 개별 성분 whitelist가 아니라 농도·조합·제형 조건을 포함한 규칙 집합으로 관리해야 한다.

## 6. 시험·표시·광고 검증

### 시험 자료

시험성적서에서 다음 필드를 구조화한다.

```text
test_type
test_method
testing_laboratory
spf_result
broad_spectrum_result
critical_wavelength
water_resistance_minutes
sample_formulation
test_date
```

“SPF 시험성적서가 있다”와 “FDA M020/21 CFR 201.327 방식으로 claim을 뒷받침한다”는 별도 상태로 표시한다.

### 표시 자료

한국 패키지 앞·뒤 이미지 또는 미국용 라벨 초안을 받아 다음을 확인한다.

- Statement of identity
- Active Ingredients / Purpose
- Uses
- Warnings
- Directions
- Other Information
- Inactive Ingredients
- Drug Facts 패널 존재와 필수 항목
- SPF·Broad Spectrum·Water Resistant 표현의 시험 근거
- PA++++ 등 한국 체계 표현의 미국 라벨 적합성

### 광고·마케팅 자료

패키지와 광고를 분리해 검사한다. 상세페이지·브랜드 웹사이트·Amazon 페이지 등의 표현도 별도 입력 자료로 취급한다.

예시로 `Waterproof`, `Sweatproof`, `All-day protection` 같은 표현은 단순 성분 조회가 아닌 claim 검증 대상으로 분류한다.

## 7. 제조시설·Listing·수입

제품 단위만으로는 수출 준비도를 완성할 수 없다. 회사·시설·제품·수입 주체를 별도 객체로 관리한다.

```text
Korean Brand
  → Manufacturer
  → Manufacturing Facility
  → U.S. Agent / Importer
  → Product
  → Drug Listing / NDC
  → Shipment
```

관리 후보 필드:

```text
legal_manufacturer
manufacturing_site
contract_manufacturer
fda_establishment_registration
u_s_agent
importer
registration_status
registration_renewal_date
cgmp_readiness
drug_listing_status
ndc_or_listing_number
```

이 영역은 제품 이미지 OCR만으로 판단할 수 없으므로 별도 회사·시설 입력 폼과 증빙 업로드가 필요하다.

## 8. 결과 상태 모델

모든 결과를 단순 `FAIL`로 표시하지 않는다.

| 상태 | 의미 | 예시 |
|---|---|---|
| `BLOCKER` | 현재 상태로 M020 또는 OTC 경로 진입이 어려움 | M020에 포함되지 않은 active |
| `REQUIRED_CHANGE` | 수출 전에 수정이 필요한 항목 | Drug Facts 누락 |
| `VERIFICATION_REQUIRED` | 자료는 있으나 방법·근거·조건 확인이 부족함 | SPF 시험법 불명 |
| `COMPLIANT` | 근거자료까지 확인되어 기준 충족 | 시험·표시·성분 조건 확인 |
| `NOT_ASSESSED` | 필요한 자료가 없어 아직 판단하지 않음 | 시설 등록 자료 미제출 |

“자료 부족으로 판단하지 못함”과 “규정에 맞지 않음”은 반드시 다른 상태로 표현한다.

## 9. Rule DB와 RAG의 역할 분리

모든 FDA 문서를 LLM 프롬프트에 그대로 넣는 구조는 목표로 삼지 않는다.

### Rule DB로 구조화할 것

- 활성성분·최대 농도
- 허용 조합
- 허용 제형
- 필수 Drug Facts 항목
- 필수 경고·사용법 문구
- Water Resistant 시간값
- Broad Spectrum·SPF claim 조건
- 시설 등록·Listing 상태 필드
- 시행일·검증일·출처 URL

예상 규칙 레코드:

```text
rule_id: US-SUN-ACTIVE-AVO-001
domain: ingredient
jurisdiction: US
authority: FDA
regulation: OTC Monograph M020
target: Avobenzone
condition: concentration <= 3%
result: PASS
severity_if_violated: BLOCKER
effective_date: YYYY-MM-DD
last_verified: YYYY-MM-DD
source_url: ...
```

### RAG로 다룰 것

- 규정 원문과 해설
- 적용 조건의 문맥
- FDA guidance
- 사례·Warning Letter
- 자료 간 충돌을 설명하는 근거

### LLM/VLM으로 다룰 것

- 라벨·시험성적서·등록증 OCR
- 문서 필드 추출
- 광고 문맥의 claim 분류
- 사람이 읽는 보완 설명

최종 pass/block 판정은 가능한 한 구조화된 규칙과 근거 필드가 담당한다.

## 10. 현재 프로젝트와의 관계

현재 구현된 미국 MVP는 다음 범위다.

```text
SPF·자외선차단 표현
→ OTC 분류 전환 안내
→ 미국 자외선차단 active 목록 대조
→ 미승인 성분 또는 전성분 확인 불가 안내
```

확장 목표는 다음을 추가하는 것이다.

```text
Product Classification
→ Formula
→ Testing
→ Label
→ Claims
→ Facility
→ Listing
→ Import
```

따라서 현재의 `POST /check/us-sunscreen`을 즉시 폐기하지 않고, 향후 `USPreflightReport`를 도메인별 결과 묶음으로 확장하는 방향이 적절하다.

공통 OCR 재사용안은 별도 보류 문서로 남겨둔 상태이며, 확장 서비스에서 다시 필요해진다.

## 11. 단계적 구현 제안

전체 영역을 한 번에 구현하지 않는다.

### Phase 1 — 현재 데모 보강

- SPF·OTC 분류 전환
- M020 active 식별
- 농도 입력 및 최대 농도 대조
- 성분·함량·근거의 `BLOCKER / VERIFICATION_REQUIRED` 구분

### Phase 2 — 라벨·광고 준비도

- 패키지 OCR
- Drug Facts 체크리스트
- SPF / Broad Spectrum / Water Resistant claim 검증
- 상세페이지와 광고 claim 분리 검사

### Phase 3 — 시험·제품 자료

- 시험성적서 필드 추출
- 시험법·시험기관·시험일·제품 처방 연결
- M020 조합·제형 조건 확인

### Phase 4 — 회사·수입 준비도

- 시설 등록·U.S. Agent·Importer
- Drug Listing / NDC
- CGMP readiness
- Import readiness dashboard

## 12. 현재 결정

첨부 메모는 **미국 선스크린 수출 준비도 서비스의 확장 목표 정의**로 기록한다.

다만 이 문서의 전체 범위를 즉시 구현 범위로 확정하지 않는다. 현재 MVP는 그대로 유지하고, 다음 개발 단계에서 Phase 1부터 별도 우선순위를 정한다.

