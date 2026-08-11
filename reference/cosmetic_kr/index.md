# 화장품 레퍼런스 팩 · 한국 (cosmetic_kr)

> 무엇: 화장품 광고 컴플라이언스 판정에 쓰는 규제 지식 묶음(RAG 소스).
> 담당: 전대수. 상태: **핵심 판정표(①②) 채움 완료, 적발 사례 부분 채움**.
> 출처 인덱스: `reference/cosmetic_sources.md` (링크·고시번호). 국가 팩 구조: 이 폴더 = 한국 팩. 미국 팩(cosmetic_us)은 2단계 별도.

> ★ **정본(正本) 통합 소스**: `yourveri_레퍼런스팩_v1_0.md` (원문 대조 완료 통합본) + `YOURVE_1.XLS`(같은 내용 표 버전).
> 아래 개별 `.md`(금지표현·고시원료·사례)는 통합본에서 판정 엔진용으로 분리·정리한 것. **수치·조문이 어긋나면 통합본을 정본으로 함.**

## 이 팩이 채우는 판정 지식 (기획서 DB·RAG 3표 중 ①②)
- ① 금지·주의 표현 목록 → `prohibited_expressions.md` ✅
- ② 기능성 고시원료표 → `functional_ingredients.md` ✅
- (③ 미국 팩은 2단계, 별도 폴더 — 통합본 파트 B 참조)

## 파일 지도
```
statute/
  law_article_13.md               화장품법 제13조 조문        → 내용: 통합본 A-1 (현행+개정 전문)
  enforcement_rule_appendix_5.md  시행규칙 별표5 세부 금지유형  → 내용: 통합본 A-2 / prohibited §2
  labeling_guideline.md           표시·광고 관리 지침+실증제    → 내용: 통합본 A-3·A-4 / prohibited §1·§3
prohibited_expressions.md         금지·주의 표현 목록 (①)      ✅ 채움
functional_ingredients.md         기능성 고시원료표 (②)        ✅ 채움 (미백9·주름4·자외선27)
violation_types/
  type_1_drug_misperception.md      1호 의약품 오인            → 내용: 통합본 위반유형매핑 T1 / prohibited §1
  type_2_functional_misperception.md 2호 기능성 오인           → 내용: T2 / prohibited §1 + functional_ingredients
  type_5_deception.md               5호 거짓·과장·기만(개정법 기준, 현행 4호) → 내용: T5 / prohibited §1
  (3호는 삭제된 조항 2025.1.31 → 파일 없음)
cases.md                          실제 적발 사례              ◐ 부분(5건, 추가 수집 필요)
```

## 채우는 법 (대수용)
1. 각 파일 안 "채운 상태" 체크리스트를 따라간다.
2. 원문은 `cosmetic_sources.md`의 해당 링크(법 제13조·별표5·**심사규정 고시 제2023-61호 별표4** 등)에서 가져온다.
   - ⚠️ 기능성 고시원료의 근거는 **심사규정 고시 제2023-61호 [별표4]**(자료제출 생략 원료). 과거 초안이 적었던 "고시 2025-89호"는 성분·함량 근거가 아니므로 혼동 주의. 시험법은 「기준 및 시험방법」 고시 제2020-132호.
3. 모든 조문·목록·수치에 **시행일 + 출처**를 같이 적는다. 개정되면 판정이 틀려진다.
4. 판정 예시(어떤 문구가 몇 호인지)는 `cases.md`와 `prohibited_expressions.md` §1을 인용. 3축 판정 가이드라인 확정 시 축 라벨을 덧붙인다.

## 채운 상태 체크
- [x] 법 제13조 조문 — 통합본 A-1에 현행+개정(시행 2026.11.27) 전문 확보 *(개별 statute 파일 분리는 선택)*
- [x] 시행규칙 별표5 — 통합본 A-2 + `prohibited_expressions.md` §2 매핑 *(개별 파일 분리는 선택)*
- [x] 표시·광고 지침 + 실증제 — 통합본 A-3(금지표현)·A-4(실증대상) + `prohibited` §1·§3 *(개별 파일 분리는 선택)*
- [x] 금지표현 목록 (`prohibited_expressions.md`)
- [x] 기능성 고시원료표 (`functional_ingredients.md`)
- [x] 위반유형 1호 — 통합본 T1 + `prohibited` §1 *(개별 파일 분리는 선택)*
- [x] 위반유형 2호 — 통합본 T2 + `prohibited` §1 + `functional_ingredients` *(개별 파일 분리는 선택)*
- [x] 위반유형 5호 — 통합본 T5(현행 4호) + `prohibited` §1 *(개별 파일 분리는 선택)*
- [ ] 적발 사례 (`cases.md`) — **부분(5건)**. 10건+까지 식약처 보도자료에서 추가 수집 필요

> 남은 일 요약: ① `cases.md` 사례 5건 → 10건+ 보강, 개별 처분 수위 확정. ② 기능성 고시원료 함량 2025년 이후 개정본 1회 재대조. ③ (선택) statute/·violation_types/ 개별 파일이 필요하면 통합본에서 잘라 생성.
