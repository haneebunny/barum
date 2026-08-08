# reference/ — 식품 표시·광고 규제 레퍼런스 (문서 지도)

이 디렉토리는 **식품·건강기능식품 부당광고 판정**의 근거를 두 층으로 정리한다.

- `statute/` — **법령 원문**(법률·시행령·별표1·시행규칙·고시). 위임·근거 체계를 보존한다. → OpenCrab 팩 `statute_source`의 소스.
- `violation_types/` — **위반유형(별표1 1~5호) 인덱스**. 각 호에 대해 법조문·합법 인정문구·해석(기준서)·실제 사례를 묶는다. → OpenCrab 팩 `violation_type_index`의 소스.

두 층은 OpenCrab `ingest_text`로 적재되며, 관계(위임·근거·"이 문구는 몇 호")를 **본문에 명시적으로 서술**해 자동추출이 그래프 엣지로 뽑게 한다.

## 표기 규약

- `[원문]` — 법령·별표·고시의 **원문 인용**. 되돌리지 말 것.
- `[해석 v1.2.4]` — `라벨링_기준서.md` v1.2.4에 근거한 **프로젝트 해석·판정규칙**. 법령이 아니라 우리 팀의 운용 기준이다.
- `[사례]` — 식약처 적발/보도자료 기반 **실제 사례**.

## 법령 스택과 위임 체계

```
법 제8조①(부당광고 금지, 1~11호)
  └ 제8조② → 대통령령
       └ 시행령 제3조① → [별표 1] 부당한 표시·광고의 내용 (1~8호)   ← 판정의 뼈대
       └ 시행령 제3조② → 고시(제2025-79호) 세부기준(예시)
법 제4·5·6·7조(표시·광고 기준) → 총리령(시행규칙)
제재: 제14조 시정명령 · 제16조 영업정지 · 제17조 제조정지 · 제19·20조 과징금 · 제21조 공표
벌칙: 제26조(제8조①1~3호: 10년/1억) · 제27조(제8조①4~11호: 5년/5천만원)
```

## 파일 목록

| 파일 | 내용 | 근거 버전 |
|---|---|---|
| [statute/law.md](statute/law.md) | 식품표시광고법(법률) — 제8조 금지, 제재·벌칙 | 법률 제21707호 (시행 2026-11-27) |
| [statute/enforcement_decree.md](statute/enforcement_decree.md) | 시행령 — 제2·3조(별표1·고시 위임), 과징금·공표 | 대통령령 제35734호 (시행 2025-09-19) |
| [statute/appendix_1_prohibited_ads.md](statute/appendix_1_prohibited_ads.md) | **[별표 1]** 부당한 표시·광고의 내용 (1~8호+비고) 전문 | 별표1 개정 2023-12-26 (현행) |
| [statute/enforcement_rule.md](statute/enforcement_rule.md) | 시행규칙(총리령) — 마약류 명칭, 기능성표시식품, 행정처분 | 총리령 제2004호 (시행 2026-01-01) |
| [statute/notice_2025_79.md](statute/notice_2025_79.md) | 고시 「부당한 표시·광고의 내용 기준」 세부 예시 | 식약처고시 제2025-79호 (시행 2025-12-04) |
| [violation_types/type_1_disease.md](violation_types/type_1_disease.md) | 1호 질병 예방·치료 표방 | — |
| [violation_types/type_2_drug_misperception.md](violation_types/type_2_drug_misperception.md) | 2호 의약품 오인 | — |
| [violation_types/type_3_hf_misperception.md](violation_types/type_3_hf_misperception.md) | 3호 건강기능식품 오인 | — |
| [violation_types/type_4_falsity.md](violation_types/type_4_falsity.md) | 4호 거짓·과장 | — |
| [violation_types/type_5_deception.md](violation_types/type_5_deception.md) | 5호 소비자 기만 | — |
| [violation_types/certified_phrases.md](violation_types/certified_phrases.md) | 합법 인정문구·법정 의무표기 목록 | — |
| [violation_types/cases.md](violation_types/cases.md) | 식약처 적발 사례(유형 태깅) | 보도자료 40건 (2023~2026) |

## 원 자료 출처 (로컬)

- 법령 5종·고시: 국가법령정보센터 PDF (`~/Downloads`)
- 사례: `식약처_식품부당광고_위반사례_요약.md` / `식약처_식품부당광고_위반사례_최신기준분류.xlsx` (보도자료 40건 정리)
- 해석: `라벨링_기준서.md` v1.2.4 (2026-08-06) · `판정카드.md`
