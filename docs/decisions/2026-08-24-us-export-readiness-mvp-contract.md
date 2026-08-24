# 미국 수출 준비도 MVP 계약

> 상태: 구현 전 확정안
> 작성일: 2026-08-24
> 범위: 미국 선스크린/자외선차단 제품 수출 준비사항을 한 화면에서 안내하는 데모

## 1. 제품 약속

이 MVP는 제품의 미국 수출 가능 여부를 법적으로 판정하지 않는다. 사용자가 제공한 광고 문구·제품 정보·성분·프로필을 바탕으로 **준비됨 / 준비 필요 / 확인 필요 / 미입력 / 별도 경로 검토 필요**를 항목별로 보여준다.

보고서의 문구는 “미국 수출 가능”이 아니라 “미국 수출 준비를 위해 다음 자료와 조치가 필요함”으로 통일한다.

## 2. 단계 게이트

구현 순서는 다음과 같으며, 앞 단계의 완료 확인 전 다음 세션을 시작하지 않는다.

1. 공식 자료 조사 — 완료
2. PM 계약·범위 동결 — 이 문서와 개발 세션 전달 내용으로 완료 처리
3. 백엔드 구현 및 테스트
4. 프론트 구현 및 화면 연결
5. 통합 QA·데모 리허설

## 3. MVP 입력

### 제품 입력

- 제품명
- 광고 문구 및 제품 이미지
- 전성분 문자열
- 의도 용도: `sunscreen` 또는 `other`
- SPF 표시값 또는 표시 여부
- Broad Spectrum 표시 여부
- Water Resistant 표시 및 지속 시간(40/80분 또는 미입력)
- SPF/Broad Spectrum/Water Resistance 시험자료 보유 여부
- Drug Facts 라벨 준비 여부
- 미국용 claim 검토 여부
- Drug Listing 준비 여부

기존 국내 검증의 OCR 결과를 공통 OCR 파이프라인으로 리팩터링하지 않는다. 기존 미국 프리플라이트 입력과 OCR 경로를 재사용하되, 공통화는 후속 과제로 남긴다.

### 재사용 프로필

MVP는 로그인·다중 조직·다중 시설을 구현하지 않고 브라우저의 단일 데모 프로필(`localStorage`)을 사용한다. 프로필은 다음 수출 제품에 다시 불러올 수 있어야 한다.

- 법인/제조사명
- 제조시설명 및 주소
- 미국 내 U.S. Agent 이름·연락처
- 수입자 이름·연락처
- FDA establishment registration 번호 또는 상태
- CGMP 자료 보유 여부
- 기본 Drug Listing 상태

준비도 요청 시 현재 프로필을 백엔드에 전달하고, 결과에는 `profile_snapshot`으로 복사한다. 이후 프로필을 수정해도 과거 보고서의 판단 근거가 바뀌지 않아야 한다.

## 4. API 계약

기존 `POST /check/us-sunscreen`와 `USPreflightReport`는 변경하지 않는다.

### `POST /export-readiness/us-sunscreen`

`multipart/form-data`로 기존 입력과 JSON 문자열 `product` 및 `profile`을 받는다.

- 기존 입력: `country`, `ad_text`, `image`, `ingredients`, `product_name`
- `product`: 제품별 준비도 입력 객체
- `profile`: 제조/수출 프로필 객체

응답은 `USExportReadinessReport`다. 기존 미국 리포트의 `result_id`가 있으면 연결하고, 없으면 새 결과 ID를 발급한다.

### `GET /reports/{result_id}/readiness`

저장된 `USExportReadinessReport`를 다시 조회한다. 기존 `GET /reports/{result_id}`의 국내/기존 미국 응답 계약은 깨지지 않아야 한다.

MVP 저장은 기존 checks JSON 저장 구조를 재사용한다. 별도 Supabase 테이블·인증·RLS 마이그레이션은 이번 범위에서 제외한다.

## 5. 응답 스키마

```text
USExportReadinessReport
  report_type: "us_export_readiness"
  result_id: string | null
  created_at: string
  product_name: string | null
  profile_snapshot: ExportProfile
  product_snapshot: ExportProduct
  summary: ReadinessSummary
  items: ReadinessItem[]
  disclaimer: string

ReadinessSummary
  overall_status: COMPLIANT | REQUIRED_CHANGE | VERIFICATION_REQUIRED
                   | NOT_ASSESSED | BLOCKER
  total: number
  counts_by_status: record<Status, number>

ReadinessItem
  id: string
  category: CLASSIFICATION | FORMULA | TESTING | LABELING | CLAIMS
           | ESTABLISHMENT | LISTING_IMPORT
  status: COMPLIANT | REQUIRED_CHANGE | VERIFICATION_REQUIRED
          | NOT_ASSESSED | BLOCKER
  title: string
  summary: string
  next_action: string
  evidence: string[]
  rule_id: string | null
  source_id: string | null
  profile_based: boolean
```

상태 우선순위는 `BLOCKER > REQUIRED_CHANGE > VERIFICATION_REQUIRED > NOT_ASSESSED > COMPLIANT`다. 전체 상태는 가장 높은 우선순위 항목으로 계산하며, 항목별 원인은 보존한다.

`COMPLIANT`는 OCR/LLM 추출만으로 만들지 않는다. 사용자 입력 또는 결정적 규칙으로 확인된 경우에만 사용한다.

## 6. MVP 체크리스트 규칙

### CLASSIFICATION

SPF, sunscreen, sun protection, sunburn protection 등 자외선차단 의도가 감지되면 미국 OTC 경로 검토 항목을 만든다. 이는 법적 최종판정이 아니라 OTC 의약품 라벨·제조·등록·listing 준비가 필요하다는 안내다.

### FORMULA

성분명을 정규화해 현재 M020 기준 데이터와 비교한다. 확인되지 않은 활성성분은 “금지”로 표현하지 않고 M020 경로 미확인으로 표시한다.

2026-08-09 발효된 OTC000039의 Bemotrizinol은 최대 6% 조건과 조합·제형 조건이 있으므로, MVP에서 자동 적합 처리하지 않는다. 사용자가 증빙을 제공하지 않으면 `VERIFICATION_REQUIRED`, 명백한 경로 불일치가 확인되면 `BLOCKER`다.

### TESTING

SPF, Broad Spectrum, Water Resistance 시험자료의 입력 여부를 표시한다. 자료가 없으면 `NOT_ASSESSED` 또는 필수 자료 미제출 상황에 따라 `REQUIRED_CHANGE`, 자료의 시험법·기관·원자료 검토가 필요한 경우 `VERIFICATION_REQUIRED`다.

### LABELING

Drug Facts 및 미국용 라벨 준비 여부를 표시한다. 텍스트 존재 여부는 자동 보조할 수 있지만, 실제 라벨 형식·배치·가독성은 `VERIFICATION_REQUIRED`로 남긴다.

### CLAIMS

광고 문구에서 자외선차단 관련 claim을 추출하고 OTC 경로와 연결한다. claim 문구 자체의 최종 적합성은 자동 확정하지 않고, 근거자료가 없거나 문구 맥락 검토가 필요하면 `VERIFICATION_REQUIRED`로 표시한다.

### ESTABLISHMENT

제조시설, 미국 내 U.S. Agent, CGMP 자료의 입력 여부를 프로필에서 확인한다. 값이 비어 있으면 `NOT_ASSESSED`, 등록/CGMP 확인이 필요한 값이면 `VERIFICATION_REQUIRED`다.

### LISTING_IMPORT

Drug Listing, 수입자, 시설 등록 상태를 확인한다. 상태가 미입력이면 `NOT_ASSESSED`; 제출 전 준비가 안 된 것으로 사용자가 명시하면 `REQUIRED_CHANGE`다.

## 7. 공식 근거 ID

룰과 보고서가 참조할 source ID는 다음으로 고정한다.

- `FDA_OTC_IMPORTS`: https://www.fda.gov/drugs/human-drug-imports/importing-over-counter-drugs
- `FDA_OTC_MONOGRAPHS`: https://www.accessdata.fda.gov/scripts/cder/omuf/index.cfm
- `FDA_OTC000039`: https://www.accessdata.fda.gov/scripts/cder/omuf/index.cfm?event=OrderDetail&orderid=OTC000039
- `FDA_SUNSCREEN_GUIDANCE`: https://www.fda.gov/regulatory-information/search-fda-guidance-documents/labeling-and-effectiveness-testing-sunscreen-drug-products-over-counter-human-use-small-entity
- `FDA_DRUG_FACTS`: https://www.fda.gov/drugs/drug-information-consumers/understanding-over-counter-medicines
- `FDA_ESTABLISHMENT_REGISTRATION`: https://www.fda.gov/drugs/guidance-compliance-regulatory-information/drug-registration-and-listing
- `FDA_DRUG_LISTING`: https://www.fda.gov/drugs/guidance-compliance-regulatory-information/drug-registration-and-listing

## 8. 제외 범위

- FDA 실시간 등록·listing 상태 조회
- NDC 제출 대행 또는 실제 FDA 제출
- 라벨 이미지의 완전한 법정 서식 판정
- 시험성적서 OCR 및 시험기관 검증
- M020 모든 조합·제형·SPF 기여도 자동 판정
- 공통 OCR 파이프라인 리팩터링
- 다중 사용자/조직/시설 프로필과 서버 계정 저장
- 미국 외 국가 확장

## 9. 완료 기준

- 기존 `/check/us-sunscreen`과 기존 미국 리포트가 그대로 동작한다.
- 한 번의 제출로 7개 카테고리의 준비도 항목과 다음 행동을 한 화면에서 볼 수 있다.
- 프로필을 저장한 뒤 다른 제품 제출에서 자동으로 재사용할 수 있다.
- 리포트에 프로필 스냅샷이 남는다.
- 5개 상태가 UI에 일관되게 표시된다.
- 법적 허가/적합 판정처럼 오해할 문구가 없다.
- 백엔드 단위 테스트와 프론트 타입/빌드 검증을 통과한다.
