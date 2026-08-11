# barum 수집 메타데이터 명세 (MVP)

> 팀 공유·문서용. 우리가 **수집하는 메타데이터**만 정리한다.
> 문장(`sentences`)·라벨(`labels`)은 상세이미지에서 **생성·라벨링하는 내부 데이터**라 이 명세에서 제외한다.
> 작성 기준일: 2026-08-07

---

## 원칙

- **연구목적 소량 수집.** 수십~수백 상품, `crawl-delay ≥ 1초` 준수, 저부하.
- **개인정보 최소수집.** 대표자명 등 개인정보는 수집하지 않는다(슬롯도 두지 않음).
- **증거의 실체는 원본 이미지 파일과 해시.** DB엔 메타만 두고, 실제 증거는 다운로드해 보관한 파일이다.
- **정식 경로 우선.** 11번가 Open API로 얻을 수 있는 건 API로 얻는다.

## 획득 경로 범례

| 코드 | 의미 |
|---|---|
| `API` | 11번가 Open API (정식 허가 경로) |
| `WEB` | 상품페이지 소량 크롤 (연구목적) |
| `OCR` | 상세이미지 텍스트 추출 (OCR/DL 단계에서) |
| `GEN` | 수집 시 자동 생성 (URL·시각·해시 등) |

## 수집 상태 범례

| 표시 | 의미 |
|---|---|
| ✅ | 지금 채워짐 |
| ⏳ | 해당 로직(크롤러 확장·상태체크·조치)이 붙을 때 채움 |
| ⬜ | 슬롯만, MVP에선 미수집 |

---

## 1. 판매자 `sellers` (누가 광고했나, 주체)

| 필드 | 의미 | 경로 | 상태 |
|---|---|---|---|
| `biz_name` | 상호명(판매업체) | API | ✅ |
| `seller_no` | 판매자 식별자 | WEB | ✅ |
| `return_address` | 반품/교환지 주소(소재지 근사) | WEB | ⏳ |
| `biz_reg_no` | 사업자등록번호 | - | ⬜ |
| `telesale_no` | 통신판매업신고번호 | - | ⬜ |
| `biz_address` | 사업장 소재지 | - | ⬜ |

> 대표자명(`ceo_name`)은 개인정보라 **의도적으로 제외**한다. `biz_reg_no`·`biz_address`는 셀러 사업자정보 페이지를 추가로 크롤해야 해서 MVP 범위 밖이다(슬롯만).

## 2. 제품 `products` (무슨 제품인가, 중복 식별)

| 필드 | 의미 | 경로 | 상태 |
|---|---|---|---|
| `hf_report_no` | 품목제조신고번호(제품 고유키) | OCR | ⏳ |
| `manufacturer` | 제조사 | OCR | ⏳ |
| `brand` | 브랜드 | OCR | ⏳ |
| `name_raw` | 원본 제품명(셀러 표기) | API | ✅ |
| `name_norm` | 정규화 제품명 | GEN | ⏳ |
| `primary_ingredient` | 지표성분/주요 원료 | OCR | ⏳ |
| `review_cert_no` | 광고심의필 번호 | OCR | ⏳ |
| `barcode` | 바코드/GTIN | OCR | ⬜ |

> 중복 제거의 결정타는 `hf_report_no`이다. 같은 번호면 같은 제품이고 플랫폼을 넘나들어도 묶인다. 번호가 없으면 `manufacturer + name_norm`으로 보조 매칭한다.
> **재분석 스킵의 안전 단위는 광고물(이미지 해시)이다.** 같은 제품이라도 광고 문구가 다르면 재분석한다(recall 우선).

## 3. 리스팅 `listings` (판매글, 증거·출처·상태)

| 필드 | 의미 | 경로 | 상태 |
|---|---|---|---|
| `platform` | 플랫폼(11st 등) | GEN | ✅ |
| `platform_product_id` | 상품번호(11st prdNo) | API | ✅ |
| `product_url` | 원본 상품 URL(사라져도 기록) | GEN | ✅ |
| `crawled_at` | 수집 시각("이 시점에 이랬다") | GEN | ✅ |
| `first_seen_at` / `last_seen_at` | 관측 기간 | GEN | ⏳ |
| `status` + `status_checked_at` | 현재 상태(active/removed/changed) | WEB | ⏳ |
| `takedown_requested_at` / `takedown_confirmed_at` | 조치 이력 | GEN | ⏳ |

> `seller_id`로 판매자, `product_id`로 제품과 연결한다. 조치(상품 내림 요청)의 단위는 리스팅이다.

## 4. 상세이미지 `detail_images` (증거의 본체)

| 필드 | 의미 | 경로 | 상태 |
|---|---|---|---|
| `image_url` | 원본 이미지 URL(외부호스트 포함) | WEB | ✅ |
| `local_path` | 보관한 원본 파일 위치 | GEN | ✅ |
| `sha256` | 무결성(변조 없음 입증), 판정 단위 | GEN | ✅ |

> 판정은 이미지(광고물) 단위로 한다. `sha256`이 같은 이미지는 재분석하지 않고 스킵한다(dedup).

---

## 지금 당장 채워지는 메타데이터 (요약)

`biz_name` · `name_raw` · `platform` · `platform_product_id` · `product_url` · `crawled_at` · `image_url` · `local_path` · `sha256`

나머지는 크롤러 확장(판매자 주소·상태), OCR/DL 단계(제품 식별 필드), 조치 순환(F단계)에서 채워지는 슬롯이다.
