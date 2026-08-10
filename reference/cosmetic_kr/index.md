# 화장품 레퍼런스 팩 · 한국 (cosmetic_kr)

> 무엇: 화장품 광고 컴플라이언스 판정에 쓰는 규제 지식 묶음(RAG 소스).
> 담당: 전대수. 상태: 뼈대만 있음, 자료 채우는 중.
> 출처 인덱스: `reference/cosmetic_sources.md` (링크·고시번호는 거기 있음. 여기선 중복 안 함).
> 국가 팩 구조: 이 폴더 = 한국 팩. 미국 팩(cosmetic_us)은 2단계에 별도.

## 이 팩이 채우는 판정 지식 (기획서 DB·RAG 3표 중 ①②)
- ① 금지·주의 표현 목록 → `prohibited_expressions.md`
- ② 기능성 고시원료표 → `functional_ingredients.md`
- (③ 미국 팩은 2단계, 별도 폴더)

## 파일 지도
```
statute/
  law_article_13.md               화장품법 제13조 조문
  enforcement_rule_appendix_5.md  시행규칙 별표5 세부 금지유형
  labeling_guideline.md           식약처 표시·광고 관리 지침 + 실증제 핵심
prohibited_expressions.md         금지·주의 표현 목록 (①)
functional_ingredients.md         기능성 고시원료표 (②, 미백/주름/자외선차단 + 함량)
violation_types/
  type_1_drug_misperception.md      1호 의약품 오인
  type_2_functional_misperception.md 2호 기능성 오인
  type_4_falsity_deception.md       4호 거짓·과장·기만
  (3호는 삭제된 조항 → 파일 없음)
cases.md                          실제 적발 사례 (식약처 공표)
```

## 채우는 법 (대수용)
1. 각 파일 안 "채울 것" 체크리스트를 따라간다.
2. 원문은 `cosmetic_sources.md`의 해당 링크(법 제13조·별표5·고시 2025-89호 등)에서 가져온다.
3. 모든 조문·목록·수치에 **시행일 + 출처**를 같이 적는다. 개정되면 판정이 틀려진다.
4. 판정 예시(어떤 문구가 몇 호인지)는 별도 "판정 가이드라인"이 확정되면 그걸 인용한다. 지금은 비워두거나 초안만.

## 채움 상태 체크
- [ ] 법 제13조 조문 (`statute/law_article_13.md`)
- [ ] 시행규칙 별표5 (`statute/enforcement_rule_appendix_5.md`)
- [ ] 표시·광고 지침 + 실증제 (`statute/labeling_guideline.md`)
- [ ] 금지표현 목록 (`prohibited_expressions.md`)
- [ ] 기능성 고시원료표 (`functional_ingredients.md`)
- [ ] 위반유형 1호 (`violation_types/type_1_drug_misperception.md`)
- [ ] 위반유형 2호 (`violation_types/type_2_functional_misperception.md`)
- [ ] 위반유형 4호 (`violation_types/type_4_falsity_deception.md`)
- [ ] 적발 사례 (`cases.md`)
