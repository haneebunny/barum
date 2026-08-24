# 미국 일반 화장품 기본 준비 및 국내 카테고리 기반 규제 경로 조사

> 조사 기준일: 2026-08-24  
> 목적: 사용자가 국내 유통 카테고리, 사용 목적, claim, 전성분과 제조사 프로필을 입력하면 미국 판매 준비사항과 추가 확인 경로를 안내하는 2차 프리플라이트 규칙 초안  
> 범위: 하루 MVP에 필요한 FDA 공통 화장품 요건과 대표 고위험 경로 선별. 법률 자문, FDA 승인 또는 실제 통관 가능 판정이 아니다.

## 1. 결론 요약

1. 국내 유통 카테고리는 입력 UX와 MoCRA 제품 카테고리 후보 생성에는 유용하지만 미국 규제 분류를 확정하지 못한다. 미국의 화장품, 의약품, 복합 분류는 `intended use`를 중심으로 판단되며, 라벨, 광고, 웹페이지 등 claim, 소비자 인식, 치료 용도가 널리 알려진 성분이 함께 근거가 된다.
2. 따라서 사용자가 `OTC`를 선택하게 하지 않고, `국내 카테고리 + 세부 제품형 + leave-on/rinse-off + 사용 부위 + claim 원문 + 전성분/함량`을 입력하게 한 뒤 내부적으로 규칙팩을 선택해야 한다.
3. 모든 제품에 `US_COSMETIC_BASIC`을 후보 적용하고, claim과 성분에 따라 `US_SUNSCREEN_OTC`, `US_ACNE_OTC_M006` 등 고위험 규칙팩을 추가한다. 화장품과 의약품의 정의를 모두 충족하면 양쪽 요건을 모두 안내한다.
4. 키워드 탐지는 최종 법적 분류가 아니라 경로 선별이다. `여드름 치료`, `비듬 치료`, `발한 억제`, `충치 예방`, `SPF`처럼 직접적인 claim도 MVP에서는 해당 규칙팩을 활성화하되 최종 분류 항목은 최소 `VERIFICATION_REQUIRED`로 둔다.
5. 일반 화장품의 라벨 필수 요소 존재 여부, 정확히 일치하는 금지 성분, 미입력 필드는 비교적 안전하게 자동 점검할 수 있다. 색소의 실제 사용 조건, 안전성 자료의 충분성, MoCRA 면제, 시설 등록과 listing의 유효성, claim의 전체 맥락은 사용자 증빙 또는 전문가 확인이 필요하다.
6. MoCRA 시설 등록과 제품 listing은 FDA 승인이나 인증서가 아니다. 일반 화장품은 원칙적으로 시설 등록 2년 주기 갱신, 책임 주체의 제품 listing 연간 갱신 대상이지만 소기업 면제, 의약품·의료기기 규정 적용 예외가 있으므로 적용 여부부터 확인해야 한다.
7. `FDA 등록번호 있음`, `ISO 22716 보유`, `성적서 있음` 같은 자기진술만으로 `COMPLIANT`를 만들지 않는다. 문서 식별자, 발급·갱신일, 대상 제품/시설, 검증일을 받으며, 외부 조회나 문서 검토가 없으면 `VERIFICATION_REQUIRED`가 적절하다.

## 2. 판정 모델과 입력 초안

### 2.1 규제 경로를 고르는 최소 입력

| 필드 | 형식/예시 | 용도 | 미입력 시 |
|---|---|---|---|
| `domestic_category` | skincare, suncare, cleansing, makeup, mask_pack, haircare, bodycare, fragrance | 사용자 탐색, FDA 카테고리 후보 생성 | `NOT_ASSESSED` |
| `product_subtype` | toner, serum, shampoo, deodorant, toothpaste | 세부 category와 사용법 확인 | `NOT_ASSESSED` |
| `use_site` | face, eye_area, scalp, oral_cavity, body, underarm | 색소, MoCRA 면제, 고위험 경로 확인 | `NOT_ASSESSED` |
| `application_mode` | leave_on, rinse_off, aerosol, spray, injected, internal | MoCRA 면제, 성분·경고 조건 확인 | `NOT_ASSESSED` |
| `intended_use` | cleansing, moisturizing, odor_control 등 | 화장품 정의와 의약품 정의 비교 | `VERIFICATION_REQUIRED` |
| `claims` | 포장, 상세페이지, 광고 원문 배열 | 경로 트리거의 주 근거 | 없으면 `NOT_ASSESSED` |
| `ingredients` | INCI명 전체 목록 | 제한 성분, 색소, 알려진 의약품 성분 탐지 | 없으면 `NOT_ASSESSED` |
| `ingredient_concentrations` | active 또는 제한 성분 함량 | OTC monograph 및 제한 조건 비교 | 필요 경로에서 없으면 `NOT_ASSESSED` 또는 `BLOCKER` |
| `label_text` | PDP와 information panel 텍스트 | 필수 라벨 요소 존재 확인 | `NOT_ASSESSED` |
| `market_roles` | manufacturer, packer, distributor, importer | responsible person과 등록 책임 확인 | `NOT_ASSESSED` |

`claims`에는 용기와 외포장뿐 아니라 미국 판매 상세페이지, 광고, SNS와 브로슈어를 포함하도록 안내한다. FDA는 intended use가 labeling, 광고, 인터넷 자료, 소비자 인식, 성분으로 나타날 수 있다고 설명한다.

### 2.2 내부 경로 후보

| 내부 경로 | 의미 | MVP 결과 표현 |
|---|---|---|
| `COSMETIC_ONLY_CANDIDATE` | cleansing, beautifying, attractiveness, appearance alteration 목적만 확인됨 | `US_COSMETIC_BASIC` 적용, 분류는 증빙 범위에 따라 `VERIFICATION_REQUIRED` 또는 사용자 확인 후 `COMPLIANT` |
| `DRUG_ONLY_CANDIDATE` | 질병의 진단·치료·완화·예방 또는 신체 구조·기능 영향 목적만 확인됨 | 관련 OTC monograph 또는 별도 승인 경로 활성화 |
| `DRUG_COSMETIC_CANDIDATE` | 미용 목적과 의약품 목적을 모두 가짐 | 양쪽 규칙팩 적용. 예: 비듬 샴푸, 불소 치약, 데오도란트 겸 안티퍼스퍼런트 |
| `NON_COSMETIC_BOUNDARY_REVIEW` | soap, device, food 등 다른 관할 가능성 | `VERIFICATION_REQUIRED`, 하루 MVP의 상세 판정 제외 |
| `INSUFFICIENT_INFORMATION` | claim, 사용 목적 또는 성분이 부족함 | `NOT_ASSESSED` |

`cosmeceutical`은 미국 법정 분류가 아니므로 입력 선택지나 결과 경로로 만들지 않는다.

## 3. 미국 일반 화장품 공통 준비 체크리스트

### 3.1 개발자용 규칙 후보

| rule_id | category | 최소 조건/입력 | 자동 판정 범위 | 권장 상태 | evidence 예시 | next_action |
|---|---|---|---|---|---|---|
| `US_BASIC_CLASSIFY_INTENDED_USE` | `CLASSIFICATION` | intended_use, claims, ingredients | 직접적인 치료·예방·구조기능 키워드로 고위험 pack 활성화 가능. 최종 법적 분류는 자동 확정하지 않음 | 탐지 시 `VERIFICATION_REQUIRED`, 정보 없음 `NOT_ASSESSED` | claim 원문, 탐지 구절, 입력 채널 | 미국용 전체 claim과 사용 목적을 검토하고 해당 의약품 경로를 확인한다. |
| `US_BASIC_LABEL_IDENTITY` | `LABELING` | PDP 텍스트 | statement of identity 존재 여부 | 없으면 `REQUIRED_CHANGE`, 있으면 문구 적절성 `VERIFICATION_REQUIRED` | 라벨 추출문, 위치 | PDP에 제품 정체성 표현을 추가·검토한다. |
| `US_BASIC_LABEL_NET_QUANTITY` | `LABELING` | PDP 텍스트 | 순내용량 표현 존재 여부 | 없으면 `REQUIRED_CHANGE` | 단위·수량 추출문 | 미국 표시 방식과 위치를 반영한다. |
| `US_BASIC_LABEL_BUSINESS` | `LABELING` | information panel | 제조자·포장자·유통자 명칭과 사업장소, 필요 시 `Manufactured for` 또는 `Distributed by` 존재 확인 | 누락 `REQUIRED_CHANGE`, 주소 적절성 `VERIFICATION_REQUIRED` | 사업자명, 주소, qualifier | 라벨 책임 표시 주체와 주소를 확정한다. |
| `US_BASIC_LABEL_INGREDIENTS` | `LABELING` | 전체 전성분, 라벨 텍스트 | ingredient declaration 존재와 목록 대조 | 누락 `REQUIRED_CHANGE`, 순서·예외·명칭은 `VERIFICATION_REQUIRED` | 라벨 성분문, 처방 목록 | 미국 화장품 성분명과 내림차순 원칙을 검토한다. |
| `US_BASIC_LABEL_LANGUAGE` | `LABELING` | 라벨 전체 텍스트 | 필수정보의 영어 존재 여부 | 없으면 `REQUIRED_CHANGE` | 탐지 언어, 필수 블록 | 모든 필수정보를 영어로 표시한다. 외국어를 쓰면 필요한 정보를 그 언어로도 갖춘다. |
| `US_BASIC_LABEL_MATERIAL_FACTS` | `LABELING` | 사용법, 경고, 사용 부위·제형 | material facts 및 필요한 directions/warnings의 존재 후보 탐지 | 맥락 의존 `VERIFICATION_REQUIRED` | 사용법·경고 원문 | 안전 사용에 필요한 사실과 개별 성분·제형 경고를 검토한다. |
| `US_MOCRA_LABEL_AE_CONTACT` | `LABELING` | 라벨 연락처 | 미국 내 주소, 미국 내 전화번호 또는 전자 연락처 존재 여부 | 누락 `REQUIRED_CHANGE`, 실제 수신 가능성 `VERIFICATION_REQUIRED` | 주소·전화·이메일·웹사이트 | 책임 주체가 부작용 보고를 받을 연락 수단을 라벨에 표시하고 운영한다. |
| `US_BASIC_PROHIBITED_RESTRICTED` | `FORMULA` | INCI 전체 목록, 함량·제형 | FDA 명시 금지 성분 정확 일치와 일부 제형 조건 비교 | 명백한 금지 일치 `REQUIRED_CHANGE`, 제한 조건 부족 `VERIFICATION_REQUIRED` | 성분명, 함량, 제형, CFR 항목 | 처방을 변경하거나 적용 조건과 예외를 전문가가 확인한다. |
| `US_BASIC_COLOR_USE` | `FORMULA` | 색소, use_site, 제품형 | 허용표와 eye area 등 명시적 범위 비교 후보 | 비허용이 명확하면 `REQUIRED_CHANGE`, 인증 lot·규격은 `VERIFICATION_REQUIRED` | 색소명, CFR, 사용 부위, CIN/lot | 용도별 허용, 규격, 제한, batch certification을 확인한다. |
| `US_MOCRA_APPLICABILITY` | `ESTABLISHMENT` | 매출·소기업 자료, 제품 특성, drug/device 적용 여부 | 면제 질문 누락 탐지. 면제 확정은 하지 않음 | `VERIFICATION_REQUIRED` | 제품 접촉 부위, injected/internal 여부, 24시간 초과, 매출 근거 | 소기업·drug/device 예외 적용 여부를 규제 전문가와 확인한다. |
| `US_MOCRA_FACILITY_REG` | `ESTABLISHMENT` | 제조·가공 시설, FEI, 등록일·갱신일 | 미입력, 만료 예정일 계산 | 필수 대상인데 없음 `BLOCKER`, 번호만 입력 `VERIFICATION_REQUIRED` | FEI, registration status, initial/renewal date | FDA 등록 상태를 확인하고 2년 주기 갱신을 관리한다. |
| `US_MOCRA_FOREIGN_US_AGENT` | `ESTABLISHMENT` | 해외 시설 여부, U.S. agent 연락처 | 해외 시설인데 agent 미입력 탐지 | 필수 대상인데 없음 `BLOCKER`, 입력됨 `VERIFICATION_REQUIRED` | agent 이름·전화·이메일 | 시설 등록용 U.S. agent를 지정하고 수락·연락 가능성을 확인한다. |
| `US_MOCRA_PRODUCT_LISTING` | `LISTING_IMPORT` | responsible person, listing ID/제출일, 성분, 시설 | 연간 갱신일과 필드 누락 계산 | 필수 대상인데 없음 `BLOCKER`, 제출 주장만 있음 `VERIFICATION_REQUIRED` | listing 식별자, 제출·갱신일, 제품·시설·성분 snapshot | 제품 listing과 연간 update를 제출·검증한다. |
| `US_MOCRA_RESPONSIBLE_PERSON` | `ESTABLISHMENT` | label business, 역할 | 라벨상 주체와 프로필 일치 비교 | 불일치 `REQUIRED_CHANGE`, 역할 적절성 `VERIFICATION_REQUIRED` | label name, manufacturer/packer/distributor role | responsible person과 라벨 표시 주체를 확정한다. |
| `US_MOCRA_SAFETY_SUBSTANTIATION` | `SAFETY` | safety report 목록, 대상 처방·버전 | 자료 존재와 제품·처방 버전 일치만 비교 | 없음 `BLOCKER` 또는 출시 전 `REQUIRED_CHANGE`, 충분성 `VERIFICATION_REQUIRED` | 문서명, 시험법, 기관, 날짜, formula version | 책임 주체가 적절한 안전성 입증 기록을 확보·유지하고 전문가가 충분성을 검토한다. |
| `US_MOCRA_SAE_PROCESS` | `SAFETY` | SOP, 담당자, intake channel, 기록 시스템 | SOP·담당자·연락처 누락 탐지 | 누락 `REQUIRED_CHANGE`, 운영성 `VERIFICATION_REQUIRED` | SOP ID/버전, 담당자, 연락채널 | 미국 내 serious adverse event를 15영업일 내 보고하고 후속정보를 처리할 절차를 마련한다. |
| `US_IMPORT_ENTRY_PREP` | `LISTING_IMPORT` | manufacturer, importer/consignee, product description, label, A of C 선택 | 필드 누락 탐지 | 미입력 `NOT_ASSESSED`, 핵심정보 누락 `REQUIRED_CHANGE` | 수입자, 제조자, 제품설명, 라벨 버전 | ACE 제출 정보와 미국 라벨·성분·색소 자료를 수입자와 대조한다. |

`SAFETY` category를 현재 백엔드 enum에 바로 추가하지 않는다면 하루 MVP에서는 `US_MOCRA_SAFETY_SUBSTANTIATION`과 `US_MOCRA_SAE_PROCESS`를 임시로 `ESTABLISHMENT`에 매핑할 수 있다. 2차 스키마에서는 별도 `SAFETY_POSTMARKET` category가 더 명확하다.

### 3.2 라벨 최소 항목

| 영역 | 최소 확인 항목 | 근거 | 자동화 경계 |
|---|---|---|---|
| Principal Display Panel | statement of identity, 정확한 net quantity of contents | 21 CFR 701.11, 701.13 | 텍스트 존재는 자동, 정체성 표현의 적절성·배치·가독성은 확인 필요 |
| Information panel | 제조자·포장자·유통자 명칭과 사업장소, 제조자가 아니면 적절한 qualifier | 21 CFR 701.12 | 필드 존재는 자동, 주소의 법적 충분성은 확인 필요 |
| Ingredient declaration | 통상 1% 초과는 중량 내림차순, 1% 이하와 색소에는 예외가 있음 | 21 CFR 701.3 | 누락과 처방 대조는 자동 후보, 명칭·순서·trade secret·색소 예외는 확인 필요 |
| Language | 미국 판매 필수 정보는 영어. 외국어 표시를 사용하면 필수 정보를 해당 외국어로도 표시 | 21 CFR 701.2(b) | 언어 탐지는 자동, 완전성은 확인 필요 |
| Material facts | 안전한 사용에 중요한 사실, 필요한 directions와 warnings | FD&C Act 602(a), 21 CFR 1.21, part 700/740 | 개별 제품·성분·제형에 따라 달라 확인 필요 |
| Adverse event contact | 국내 주소, 국내 전화번호 또는 전자 연락처 중 하나 | FD&C Act 609(a), MoCRA guidance | 존재는 자동, 실제 수신·처리 가능성은 확인 필요 |
| Drug + cosmetic | 의약품 active를 먼저 표시하고 화장품 성분을 별도로 표시, drug labeling도 충족 | 21 CFR 701.3(d), 21 CFR 201.66 등 | dual route가 활성화되면 별도 drug label pack 필요 |

여기서 `domestic`은 FDA 문맥상 미국 내 주소 또는 미국 내 전화번호를 뜻한다. 전자 연락처는 이메일 또는 웹사이트가 될 수 있다. QR 코드만으로 충분하다고 가정하지 않는다.

### 3.3 성분, 색소, 안전성

- 일반 화장품과 대부분의 화장품 원료는 FDA 사전승인 대상이 아니다. 예외적으로 색소는 해당 intended use에 대해 허용되어야 하며, 일부는 FDA batch certification이 필요하다.
- 단순 blacklist 통과는 안전성 적합 판정이 아니다. 법에 개별 금지 규정이 없어도 customary or labeled use에서 유해한 화장품은 허용되지 않는다.
- MVP의 금지·제한 rule DB에는 최소한 FDA 공식 표의 bithionol, mercury compounds, vinyl chloride, halogenated salicylanilides, aerosol cosmetics의 zirconium complexes, chloroform, methylene chloride, CFC propellants, hexachlorophene과 각 CFR 조건을 저장한다.
- methyl methacrylate monomer는 FDA가 손톱 제품에 사용하지 말아야 할 유해 물질로 판단한 정책성 설명이므로, 단순 법정 금지 성분과 같은 `REQUIRED_CHANGE` 규칙으로 합치지 않고 `VERIFICATION_REQUIRED`로 둔다.
- 색소 rule은 `ingredient_name + CFR section + certification_required + allowed_use_site + product_type + maximum/constraining conditions`로 구성한다. eye area, lip, external use, hair dye, 전문용 등 범위를 구분한다.
- MoCRA상 responsible person은 적절한 안전성 입증을 보장하고 기록을 유지해야 한다. FDA가 특정 시험 한 가지를 모든 화장품에 의무화한 것으로 표현하지 않는다. MVP는 자료의 존재, 처방 버전 일치, 작성·시험 기관과 날짜를 확인하고 과학적 충분성은 `VERIFICATION_REQUIRED`로 둔다.

### 3.4 MoCRA, 책임 주체, 부작용

| 항목 | 공통 준비 내용 | 프로필 재사용 필드 | 판단 주의점 |
|---|---|---|---|
| responsible person | 라벨에 이름이 표시되는 manufacturer, packer 또는 distributor | 법인명, 역할, 주소, adverse event contact | 해외 회사도 가능하지만 라벨 연락 수단 요건과 실제 운영을 확인 |
| facility registration | 제조·가공 시설 등록, 최초 등록 후 2년마다 갱신 | 시설명·주소·전화·이메일, FEI, 등록 상태, 최초일, 갱신일 | 등록은 승인·인증서가 아님 |
| foreign facility U.S. agent | 해외 시설 등록에 U.S. agent 정보 | agent명, 전화, 이메일, 동의/검증일 | 제품 수입자와 동일 인물이라고 가정하지 않음 |
| product listing | responsible person이 판매 제품과 성분, 시설 등을 listing하고 매년 update | listing ID/상태, 제품명, category code, 시설 FEI, 성분 snapshot, 제출·갱신일 | 제품별 자료. 브랜드 변형 묶음 가능성은 guidance 조건 확인 필요 |
| serious adverse event | 미국에서 발생한 serious adverse event를 15영업일 내 FDA에 보고, retail label 사본 첨부 | SOP, 담당자, intake channel, 기록 위치, 마지막 점검일 | 초기 보고 후 1년 내 새 의료정보 수령 시 15영업일 내 추가 제출 |
| safety substantiation | 제품 안전성을 뒷받침하는 기록 확보·유지 | 안전성 보고서 index, 처방 버전, 검토자·검토일 | 단순 보유 여부만 자동, 충분성은 전문가 확인 |

소기업은 일부 GMP, facility registration, product listing 요건의 면제가 가능하지만, 통상 사용 시 눈 점막에 접촉하는 제품, 주입 제품, 내부 사용 제품, 24시간을 넘겨 외관을 변화시키며 소비자 제거가 통상 사용의 일부가 아닌 제품에는 그 면제가 적용되지 않는다. drug/device 규정을 받는 제품·시설에도 별도 예외가 있다. 매출과 관계기업 계산, 제품 특성, 다른 chapter 적용 여부가 필요하므로 `US_MOCRA_APPLICABILITY`는 자동 면제 판정 대신 `VERIFICATION_REQUIRED`로 둔다.

MoCRA cosmetic GMP는 FDA의 규칙 제정 대상이다. 조사 기준일 현재 프로젝트가 `CGMP 인증 보유`만으로 일반 화장품 법정 GMP 준수를 자동 판정하지 않도록 한다. 품질시스템 자료는 준비 증빙으로 받되 `VERIFICATION_REQUIRED`로 표시한다.

### 3.5 수입 준비

- 미국 수입 화장품은 미국 내 제조 제품과 같은 FDA 요건을 적용받는다.
- 최소 입력은 declared manufacturer, importer/consignee, product description, intended use, 미국 라벨 버전, 전체 성분, 색소 CIN/certification 관련 자료, MoCRA 적용·등록·listing 상태다.
- FDA는 entry 정보, 현장검사와 샘플링으로 라벨, claim, 성분, 색소 등을 확인할 수 있다. A of C 코드는 화장품에 자발적 정보이며 제출 자체를 의무로 표시하지 않는다.
- FDA `Importing Cosmetics` 페이지에는 종료된 VCRP 설명이 남아 있다. VCRP는 2023-03-27부터 제출을 받지 않으므로, 현재 의무 등록·listing 판단은 MoCRA section 607과 최신 등록·listing guidance를 우선한다.
- 통관 성공을 자동 보장하지 않는다. MVP는 수입자와 제출자료가 준비되었는지 안내하고, 실제 ACE 제출, import alert 조회, 세관·FDA 대응은 범위 밖으로 둔다.

## 4. 복합·고위험 사례

| 사례 | 규제 경로 트리거 | cosmetic only 가능 범위 | 활성화 pack | MVP 상태/자동화 경계 |
|---|---|---|---|---|
| 선스크린 | SPF, sunscreen, sunburn prevention, UV protection 등 미국에서 자외선 보호 intended use | sunless tanning처럼 피부 외관만 변화시키며 자외선 보호 claim이 없는 별도 사례 | `US_SUNSCREEN_OTC` | claim 탐지로 pack 자동 활성화. M020 상세 판정은 기존 pack 사용. 분류는 `VERIFICATION_REQUIRED` |
| 여드름 | treat/prevent acne, pimples, blackheads, whiteheads 등과 acne therapeutic active | 단순 세정·보습·외관 개선이며 acne 치료·예방 목적이 없는 경우 | `US_ACNE_OTC_M006` | 직접 claim은 자동 경로 선별. active·농도·제형·라벨은 M006 대조, 전체 적합은 확인 필요 |
| 비듬 | dandruff, seborrheic dermatitis, psoriasis의 control/relief/treatment | 일반 cleansing shampoo, hair conditioner | `US_DANDRUFF_OTC_M032` | anti-dandruff shampoo는 drug + cosmetic 후보. claim과 active·농도 필요 |
| 모발 성장·탈모 | restore/grow hair, prevent hair loss, hair regrowth 등 | 모발을 세정·정돈·윤기 있게 보이게 함 | `US_HAIR_GROWTH_DRUG_REVIEW` | 키워드로 자동 선별하되 단순 monograph 적합으로 처리하지 않음. 승인된 NDA/ANDA 제품과 조건 또는 별도 승인 경로 확인 필요 |
| 미백·색소침착 | skin bleaching/lightening, melanin 생성 증감, melasma·hyperpigmentation·dark spots 치료 | radiance, brightening, even-looking tone이 외관 표현에 그치고 생리적 작용을 주장하지 않는 경우가 있을 수 있음 | `US_SKIN_LIGHTENING_DRUG_REVIEW` | hydroquinone OTC skin-lightening 또는 명백한 치료 claim은 고위험. 표현 맥락은 `VERIFICATION_REQUIRED`; all OTC skin-lightening이 합법적 monograph 제품이라고 가정 금지 |
| 주름·안티에이징 | remove wrinkles, increase collagen, regenerate cells, 구조·기능 변화 | 보습 또는 메이크업으로 wrinkles를 덜 보이게 함 | `US_STRUCTURE_FUNCTION_CLAIMS_REVIEW` | `moisturizes to make fine lines look less noticeable`와 구조기능 claim을 구분. 맥락·증빙 전문가 확인 |
| 데오도란트·안티퍼스퍼런트 | reduces perspiration, antiperspirant | odor control, fragrance만 목적이면 cosmetic | `US_ANTIPERSPIRANT_OTC_M019` | antiperspirant + deodorant는 drug + cosmetic. claim으로 pack 활성화, active·농도·제형은 M019 대조 |
| 치약·구강제품 | anticavity, prevents cavities, fluoride의 알려진 therapeutic use | cleansing teeth, freshening breath만 목적 | `US_ANTICARIES_OTC_M021` | 불소 anticaries 치약은 drug + cosmetic 후보. fluoride 존재만으로 모든 구강제품을 자동 적합 판정하지 않음 |
| 향수·아로마 | sleep aid, quit smoking, pain relief 등 치료 목적 | fragrance, attractiveness 목적 | `US_STRUCTURE_FUNCTION_CLAIMS_REVIEW` | aromatherapy라는 명칭보다 실제 claim 문맥을 확인 |
| AHA peel | acne/scar removal, skin lightening, 피부층 제거를 통한 구조 영향 | 통상적 외관 개선 목적 화장품일 수 있음 | `US_STRUCTURE_FUNCTION_CLAIMS_REVIEW` | 산 종류·농도·pH·사용법과 claim 필요. 자동 확정 제외 |

고위험 pack이 활성화되었다는 사실은 불법 판정이 아니다. 해당 OTC monograph를 모두 충족하거나 승인된 drug application 등 합법 경로가 있는지 추가 검토가 필요하다는 뜻이다.

## 5. 국내 카테고리에서 미국 확인 포인트로의 매핑

| 국내 입력 카테고리 | FDA cosmetic category 후보 | 기본 pack | 자주 확인할 추가 트리거 | 비고 |
|---|---|---|---|---|
| 스킨케어 | 14 Skin care preparations | `US_COSMETIC_BASIC` | sunscreen, acne, skin lightening, wrinkle/collagen, scar, cellulite | 토너·세럼·크림보다 claim과 active가 경로를 바꿈 |
| 선케어 | 15 Suntan preparations 또는 실제 claim에 따른 drug 경로 | `US_COSMETIC_BASIC` | SPF/UV protection이면 `US_SUNSCREEN_OTC`; sunless tanning은 색소 DHA 사용조건 | 선케어 선택만으로 sunscreen drug를 확정하지 않음 |
| 클렌징 | 14 Skin care, 12 Personal cleanliness, 02 Bath 등 | `US_COSMETIC_BASIC` | acne, antibacterial, antiseptic, eczema 치료 | soap 법정 정의 경계도 별도 확인 가능 |
| 메이크업 | 03 Eye makeup, 08 Makeup preparations 등 | `US_COSMETIC_BASIC` | SPF, acne treatment, eyelash growth, eye-area color | 눈 부위·입술 색소 허용 범위가 중요 |
| 마스크팩 | 14 Skin care, paste masks 또는 other leave-on/rinse-off | `US_COSMETIC_BASIC` | acne, whitening, wrinkle, transdermal/structure-function | sheet mask라는 국내 형태만으로 규제 경로 결정 불가 |
| 헤어케어 | 06 Hair non-coloring, 07 Hair coloring | `US_COSMETIC_BASIC` | dandruff, psoriasis, hair growth/loss prevention, coal-tar hair dye warnings | anti-dandruff shampoo는 dual, 염모제는 별도 경고·성분 확인 |
| 바디케어 | 12 Personal cleanliness, 14 Skin care, 02 Bath, 13 Shaving | `US_COSMETIC_BASIC` | antiperspirant, acne, eczema, pain relief, sunscreen | deodorant odor claim과 perspiration reduction을 구분 |
| 향수/퍼퓸 | 05 Fragrance preparations | `US_COSMETIC_BASIC` | sleep, anxiety, smoking cessation, pain relief | 향 자체보다 aromatherapy claim이 경로를 바꿈 |
| 구강케어 | 11 Oral hygiene products | `US_COSMETIC_BASIC` | anticavity/fluoride, sensitivity, gingivitis, plaque therapeutic claims | 하루 MVP는 anticaries만 별도 pack, 나머지는 확인 경로 |
| 네일 | 10 Manicure preparations | `US_COSMETIC_BASIC` | antifungal, nail disease 치료, MMA, 장기 외관변화 | MoCRA 소기업 면제 예외 및 사용 성분 확인 |

국내 카테고리와 FDA category code는 다대다다. `domestic_category`는 화면 탐색과 질문 분기용으로 유지하고, listing용 `fda_cosmetic_category_code_candidate`는 subtype과 leave-on/rinse-off를 받은 뒤 별도 산출한다. 제품 listing에는 하나의 tertiary category가 leave-on 또는 rinse-off 중 하나여야 하므로 이를 독립 필드로 받는 편이 안전하다.

## 6. Rule pack 초안

### 6.1 선택 순서

```text
국내 카테고리 선택
  -> 공통 최소 질문과 US_COSMETIC_BASIC 활성화
  -> intended use + 전체 claim + 성분 + 사용 부위/방법 분석
  -> 고위험 trigger가 있으면 해당 pack 추가
  -> cosmetic only / drug only / drug + cosmetic 후보 생성
  -> 각 pack의 자료 누락, 명백한 불일치, 확인 필요를 ReadinessItem으로 병합
```

### 6.2 pack registry 후보

| pack_id | trigger 후보 | 의존 source | 하루 MVP 역할 |
|---|---|---|---|
| `US_COSMETIC_BASIC` | 모든 미국 화장품 후보 | `FDA_CLASSIFICATION`, `FDA_COSMETIC_LABELING`, `FDA_MOCRA`, `FDA_MOCRA_REG_LIST`, `FDA_COSMETIC_INGREDIENTS`, `FDA_COLOR_COSMETICS`, `FDA_IMPORT_COSMETICS` | 포함 |
| `US_SUNSCREEN_OTC` | SPF, UV protection, sunscreen, sunburn prevention | 기존 M020/OTC000039 source | 기존 구현 재사용 |
| `US_ACNE_OTC_M006` | acne/pimple/blackhead/whitehead 치료·예방 | `FDA_M006` | 경로 선별과 필요 입력 안내만 포함, 상세 full monograph rule은 후속 |
| `US_DANDRUFF_OTC_M032` | dandruff/seborrheic dermatitis/psoriasis control | `FDA_M032` | 경로 선별과 dual 분류 안내 |
| `US_ANTIPERSPIRANT_OTC_M019` | antiperspirant, reduces perspiration | `FDA_M019` | deodorant cosmetic과 구분 안내 |
| `US_ANTICARIES_OTC_M021` | anticavity/caries prevention, fluoride toothpaste | `FDA_M021`, `FDA_CLASSIFICATION` | 경로 선별과 dual 분류 안내 |
| `US_HAIR_GROWTH_DRUG_REVIEW` | hair growth/restoration, hair loss prevention | `FDA_DRUG_CLAIM_WARNINGS`, `FDA_HAIR_GROWTH_310_527` | 자동 적합 금지, 승인 경로 확인 안내 |
| `US_SKIN_LIGHTENING_DRUG_REVIEW` | skin bleaching/lightening, melanin change, hyperpigmentation 치료, hydroquinone | `FDA_SKIN_LIGHTENING` | `VERIFICATION_REQUIRED`, hydroquinone OTC 합법 가정 금지 |
| `US_STRUCTURE_FUNCTION_CLAIMS_REVIEW` | collagen increase, wrinkle removal, cell regeneration, eyelash growth, sleep/pain claims 등 | `FDA_CLASSIFICATION`, `FDA_WRINKLE_PRODUCTS`, `FDA_DRUG_CLAIM_WARNINGS` | claim 맥락 검토 |

하루 MVP에서 신규 고위험 pack은 완전한 active·농도·라벨 적합 엔진으로 구현하지 않는다. trigger, required_inputs, source_id, next_action만 Rule DB에 두고 해당 경로 상세 검토는 `VERIFICATION_REQUIRED`로 반환한다. 선스크린만 기존 상세 pack을 유지한다.

### 6.3 ReadinessItem 필드 제안

```json
{
  "id": "us_basic_label_ingredients",
  "rule_pack": "US_COSMETIC_BASIC",
  "category": "LABELING",
  "status": "VERIFICATION_REQUIRED",
  "title": "미국 화장품 성분표시 순서 확인",
  "summary": "성분표시는 확인되었지만 처방 중량순과 색소 예외를 자동 검증할 자료가 부족합니다.",
  "evidence": [
    "label: Ingredients: Water, Glycerin, ...",
    "input: quantitative formula not provided",
    "source: FDA_COSMETIC_LABELING, 21 CFR 701.3"
  ],
  "next_action": "정량 처방과 미국 라벨 성분표를 대조하고 1% 이하 및 색소 예외를 검토하세요.",
  "source_id": "FDA_COSMETIC_LABELING",
  "profile_based": false
}
```

필수 필드는 기존 계약과 호환되는 `category`, `status`, `evidence`, `next_action`을 유지한다. 2차 개선에서는 어떤 pack이 항목을 생성했는지 추적하기 위해 `rule_pack`을 추가하는 것이 좋다.

상태 사용 원칙:

| status | 사용 조건 | 예시 |
|---|---|---|
| `COMPLIANT` | 결정 규칙과 충분한 입력·증빙으로 해당 항목만 확인됨. 전체 수출 승인 의미 아님 | 필수 라벨 연락처가 실제 라벨과 운영 프로필 양쪽에서 검증됨 |
| `REQUIRED_CHANGE` | 공식 규칙과 명백히 불일치 | 필수 statement of identity 누락, 정확히 일치하는 금지 성분 |
| `VERIFICATION_REQUIRED` | 맥락, 예외, 외부 유효성 또는 전문가 판단 필요 | intended use 최종 분류, 안전성 충분성, 색소 batch certification |
| `NOT_ASSESSED` | 필요한 입력·자료가 없음 | claim 원문, 전성분, 라벨 미입력 |
| `BLOCKER` | 출시 준비의 필수 경로가 적용됨이 확인됐고 핵심 절차·자료가 전혀 준비되지 않아 다음 단계 진행 불가 | 필수 대상 시설 등록 없음, 출시 전 안전성 substantiation 기록 없음 |

`자료 없음`은 기본적으로 `NOT_ASSESSED`, `규정 불일치`는 `REQUIRED_CHANGE`로 분리한다. 자료가 없다는 이유만으로 규정 위반을 추론하지 않는다. 다만 사용자가 미국 판매 직전 단계라고 명시하고 필수 절차가 적용됨도 확인된 경우에만 missing evidence를 `BLOCKER`로 승격할 수 있다.

### 6.4 자동 판정과 사람 확인의 분리

| 하루 MVP 자동 가능 | 사용자 입력·증빙 확인 필요 | 전문가 검토 필요 |
|---|---|---|
| 국내 category에서 질문 세트와 FDA category 후보 생성 | 미국용 전체 claim, 판매 채널, intended use 확인 | claim 전체 맥락에 따른 최종 drug/cosmetic 분류 |
| 명시적 claim keyword로 고위험 pack 활성화 | 전성분·함량·제형·사용 부위 입력 | OTC monograph 전체 조건 또는 NDA/ANDA 경로 적합성 |
| 필수 라벨 block의 텍스트 존재 탐지 | 실제 artwork, PDP/information panel 위치와 크기 | 가독성·prominence·material fact 충분성 |
| 공식명과 정확히 일치하는 금지 성분 탐지 | 처방 버전, impurity·오염 및 원료 규격 | 완제품 안전성과 substantiation 충분성 |
| 색소명과 use_site의 1차 테이블 비교 | CIN, certification lot, supplier certificate | 복합 색소, 규격·제한·특수 intended use |
| FEI/listing ID·갱신일 누락과 날짜 계산 | FDA 제출 receipt/status, U.S. agent 수락 | MoCRA 면제와 drug/device 예외 적용 |
| adverse event SOP·담당자·연락처 미입력 탐지 | 실제 접수·에스컬레이션 운영 증빙 | serious adverse event 해당 여부와 보고 내용 |
| 수입 준비 필드 누락 탐지 | importer/consignee, entry 정보, label snapshot | 실제 통관, import alert, CBP/FDA 대응 |

LLM이 claim을 요약하거나 OCR/VLM이 라벨을 읽은 결과만으로 `COMPLIANT`를 부여하지 않는다. 추출 근거 원문과 위치를 `evidence`에 남기고, 결정 규칙이 없는 해석은 `VERIFICATION_REQUIRED`로 제한한다.

## 7. 시스템 역할 분리

| 계층 | 저장·수행할 내용 | 하면 안 되는 일 |
|---|---|---|
| Rule DB | source_id, 유효일, 규칙 상태, 정확한 금지·제한 성분, 색소 용도, claim trigger, required input, status·next_action template, pack dependency | 법령 전체 원문을 넣고 의미를 매 호출마다 재해석 |
| RAG | FDA guidance, FAQ, monograph와 CFR의 관련 문단 검색, 사용자에게 근거 문맥 제공 | 검색 결과만으로 최종 적합 판정 |
| LLM | claim·intended use 후보 추출, 동의어 정규화, 누락 질문 생성, 근거 기반 설명 | 규칙에 없는 허용 조건 생성, `COMPLIANT` 확정 |
| OCR/VLM | 라벨의 텍스트·구역·성분표·연락처 후보 추출과 위치 evidence 생성 | 실제 등록 상태, 안전성 충분성, 법적 분류 확정 |

Rule DB 레코드에는 최소 `rule_id`, `pack_id`, `source_id`, `source_section`, `effective_from`, `checked_at`, `applies_when`, `required_inputs`, `outcome`, `human_review_reason`을 둔다. 최신성 변경이 잦은 guidance와 portal 정보에는 `checked_at`과 재검토 주기를 둔다.

## 8. MVP 포함·제외 범위

### 하루 MVP 포함

- 국내 카테고리와 subtype, claim, intended use, use_site, leave-on/rinse-off, 전성분을 받는 입력 구조
- `US_COSMETIC_BASIC` 공통 체크리스트 생성
- 분류 trigger와 8개 고위험 pack 후보 활성화
- 화장품 라벨 필수 block 존재, 성분 미입력, FDA 명시 금지 성분 exact match, 색소·사용부위 1차 확인
- MoCRA facility, U.S. agent, responsible person, product listing, safety substantiation, adverse event process의 준비 여부 입력과 갱신일 계산
- `NOT_ASSESSED`, `REQUIRED_CHANGE`, `VERIFICATION_REQUIRED`, `BLOCKER`, `COMPLIANT`의 근거 분리
- 모든 항목에 source_id, evidence, next_action 제공

### 하루 MVP 제외, 후속 조사

1. M006, M032, M019, M021의 전체 active·농도·조합·제형·시험·Drug Facts를 실행 규칙으로 전환
2. hair regrowth의 승인 제품·application별 조건, skin-lightening의 승인 경로, sensitivity·gingivitis 치약 등 추가 구강 drug monograph 조사
3. soap와 CPSC, medical device, combination product, professional-use peel 및 injectable의 관할 경계
4. 21 CFR part 700/740의 제품·성분별 경고 문구 전체 Rule DB화, coal-tar hair dye와 aerosol 상세 규칙
5. 색소 전 목록의 CFR 규격, 최대치, batch certification, lake와 혼합색소 데이터셋
6. MoCRA 소기업 매출 계산, 관계기업, drug/device facility 예외의 상세 의사결정표
7. 실제 Cosmetics Direct/FEI/listing 상태 조회 연동, ACE 제출과 import alert 자동 조회
8. 안전성 substantiation 문서 유형·제품별 시험 matrix, 오염·미생물·중금속·안정성 평가 기준
9. 주별 요건, 예를 들어 California Proposition 65, 주별 PFAS·포장·환경 규정. 이번 FDA 연방 MVP 범위에서 제외
10. 향료 알레르겐, talc/asbestos, cosmetic GMP 등 FDA의 진행 중 규칙 제정 최종 상태 모니터링

## 9. 공식 출처 목록

모든 링크는 2026-08-24에 확인했다. `적용 범위`는 이 프로젝트의 사용 범위이며, 페이지 자체의 법적 효력을 과장하지 않는다.

| source_id | 문서명/조항 | URL | 적용 범위 |
|---|---|---|---|
| `FDA_CLASSIFICATION` | Is It a Cosmetic, a Drug, or Both? (Or Is It Soap?), FD&C Act 201(g)(1), 201(i), 509 | https://www.fda.gov/cosmetics/cosmetics-laws-regulations/it-cosmetic-drug-or-both-or-it-soap | intended use, claim, drug + cosmetic, soap 경계 |
| `FDA_COSMETIC_LABELING` | Cosmetics Labeling Regulations, 21 CFR 701.2, 701.3, 701.11, 701.12, 701.13 | https://www.fda.gov/cosmetics/cosmetics-labeling/cosmetics-labeling-regulations | 화장품 라벨 기본 항목 |
| `FDA_LABELING_SUMMARY` | Summary of Cosmetics Labeling Requirements | https://www.fda.gov/cosmetics/cosmetics-labeling-regulations/summary-cosmetics-labeling-requirements | 성분 순서, dual 제품, 라벨 요약 |
| `FDA_MOCRA` | Modernization of Cosmetics Regulation Act of 2022, FD&C Act Chapter VI sections 604-612 | https://www.fda.gov/cosmetics/cosmetics-laws-regulations/modernization-cosmetics-regulation-act-2022-mocra | facility, listing, responsible person, safety, adverse event, exemption |
| `FDA_MOCRA_REG_LIST` | Registration & Listing of Cosmetic Product Facilities and Products, section 607 | https://www.fda.gov/cosmetics/registration-listing-cosmetic-product-facilities-and-products | 2년 시설 갱신, 제품 listing 운영 |
| `FDA_MOCRA_REG_GUIDANCE` | Registration and Listing of Cosmetic Product Facilities and Products: Guidance for Industry, December 2024 | https://www.fda.gov/media/170732/download | 제출 필드, U.S. agent, responsible person, label adverse-event contact |
| `FDA_COSMETIC_CATEGORIES` | Cosmetic Product Categories and Codes | https://www.fda.gov/cosmetics/registration-listing-cosmetic-product-facilities-and-products/cosmetic-product-categories-and-codes | 국내 category에서 FDA listing category 후보 매핑 |
| `FDA_COSMETIC_ADVERSE_EVENTS` | How to Report a Cosmetic Product Related Complaint, section 605 | https://www.fda.gov/cosmetics/resources-consumers-cosmetics/what-should-i-do-if-i-have-reaction-side-effect-cosmetic-product | serious adverse event, 15영업일, 후속 보고 |
| `FDA_COSMETIC_INGREDIENTS` | Prohibited & Restricted Ingredients in Cosmetics, 21 CFR part 700 | https://www.fda.gov/cosmetics/cosmetics-laws-regulations/prohibited-restricted-ingredients-cosmetics | 금지·제한 성분과 안전 책임 |
| `FDA_COLOR_COSMETICS` | Color Additives and Cosmetics: Fact Sheet | https://www.fda.gov/industry/color-additives/color-additives-and-cosmetics-fact-sheet | intended use, eye area, certification 원칙 |
| `FDA_COLOR_TABLE` | Color Additives Permitted for Use in Cosmetics | https://www.fda.gov/cosmetics/cosmetic-ingredient-names/color-additives-permitted-use-cosmetics | 색소별 허용 부위·조건·CFR |
| `FDA_IMPORT_COSMETICS` | Importing Cosmetics | https://www.fda.gov/industry/importing-fda-regulated-products/importing-cosmetics | 수입 entry, 라벨·claim·색소, A of C |
| `FDA_VCRP_ENDED` | FDA Has Stopped Accepting Submissions to the Voluntary Cosmetic Registration Program, 2023-03-27 | https://www.fda.gov/food/hfp-constituent-updates/fda-has-stopped-accepting-submissions-voluntary-cosmetic-registration-program-vcrp | 과거 VCRP와 현재 MoCRA 의무 등록·listing 구분 |
| `FDA_M006` | OTC Monograph M006, Topical Acne Drug Products for OTC Human Use | https://www.accessdata.fda.gov/drugsatfda_docs/omuf/OTC%20Monograph_M006-Topical%20Acne%20drug%20products%20for%20OTC%20Human%20Use%2011.23.2021.pdf | 여드름 OTC 경로 |
| `FDA_M032` | OTC Monograph M032, Drug Products for the Control of Dandruff, Seborrheic Dermatitis, and Psoriasis | https://www.accessdata.fda.gov/drugsatfda_docs/omuf/monographs/OTC%20Monograph_M032-Drug%20Products%20for%20the%20Control%20of%20Dandruff%20Seborrheic%20Dermatitis%20and%20Psoriasis%2012.16.2021.pdf | 비듬·지루성 피부염·건선 OTC 경로 |
| `FDA_M019` | OTC Monograph M019, Antiperspirant Drug Products for OTC Human Use | https://www.accessdata.fda.gov/drugsatfda_docs/omuf/monographs/OTC%20Monograph_M019-Antiperspirant%20Drug%20Products%20for%20OTC%20Human%20Use%2011.23.2021.pdf | 안티퍼스퍼런트 OTC 경로 |
| `FDA_M021` | OTC Monograph M021, Anticaries Drug Products for OTC Human Use, posted 2023-05-02 | https://www.accessdata.fda.gov/drugsatfda_docs/omuf/monographs/OTC%20Monograph%20M021-Anticaries%20Drug%20Products%20for%20OTC%20Human%20Use%2005.02.2023.pdf | 불소 치약 등 anticaries OTC 경로 |
| `FDA_DRUG_CLAIM_WARNINGS` | Warning Letters Address Drug Claims Made for Products Marketed as Cosmetics | https://www.fda.gov/cosmetics/warning-letters-related-cosmetics/warning-letters-address-drug-claims-made-products-marketed-cosmetics | hair restoration, wrinkle removal, eyelash growth 등 claim 사례 |
| `FDA_HAIR_GROWTH_310_527` | Rulemaking History for OTC Hair Growth and Loss Drug Products, 21 CFR 310.527 | https://www.fda.gov/drugs/historical-status-otc-rulemakings/rulemaking-history-otc-hair-growth-and-loss-drug-products | hair grower·hair loss prevention 제품의 별도 승인 경로 확인 |
| `FDA_WRINKLE_PRODUCTS` | Wrinkle Treatments and Other Anti-aging Products | https://www.fda.gov/cosmetics/cosmetic-products/wrinkle-treatments-and-other-anti-aging-products | 보습·conceal과 구조기능 claim 경계 |
| `FDA_SKIN_LIGHTENING` | FDA Warns Consumers About Skin Products Containing Mercury and/or Hydroquinone | https://www.fda.gov/consumers/health-fraud-scams/fda-warns-consumers-skin-products-containing-mercury-andor-hydroquinone | OTC skin-lightening, hydroquinone·mercury 위험 및 승인 경로 |
| `FDA_AHA` | Alpha Hydroxy Acids | https://www.fda.gov/cosmetics/cosmetic-ingredients/alpha-hydroxy-acids | AHA cosmetic/drug 경계와 사용 조건 확인 |
| `FDA_OTC_MONOGRAPH_PORTAL` | OTC Monographs@FDA | https://www.accessdata.fda.gov/scripts/cder/omuf/index.cfm | monograph와 administrative order 최신 상태 확인 |

## 10. MVP 안내 문구

> 이 결과는 입력한 제품 정보와 FDA 공개 자료를 바탕으로 미국 판매 준비 항목과 추가 확인 경로를 안내합니다. FDA 승인, 법률 자문 또는 통관 가능 판정이 아닙니다. `확인 필요` 항목은 미국용 전체 라벨·광고, 정량 처방, 시험·안전성 자료, 시설 및 listing 증빙을 규제 전문가와 검토하세요.
