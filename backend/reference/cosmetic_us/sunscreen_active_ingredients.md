# 미국 자외선차단(선크림) 승인성분표 (판정 지식, 미국 프리플라이트 전용)

> 무엇: "SPF·자외선차단을 표방했는데, 그 성분이 미국 FDA 기준으로도 승인된 성분인가"를 대조하는 표.
> 스코프: 기획서 v1.6(2026-08-10) "미국 프리플라이트 스코프를 자외선차단 최소보장으로 확정" — 미백·주름은 이 표의 범위 아님.
> 근거: FDA 「OTC Monograph M020: Sunscreen Drug Products for Over-the-Counter Human Use」— Final Order **OTC000006**(2020, 베이스라인) + Final Order **OTC000039**(2026, 베모트리지놀 추가).
> 메타: 확인일 [ 2026-08-18 ] · 확인 방법 [ eCFR 21 CFR 352.10 원문(law.cornell.edu 미러) + OTC000039 최종오더 PDF 원문 직접 대조, 연방관보 API로 오더 이력 전체 조회 ]
> 관련 문서: `backend/src/barum/reference/data/us_sunscreen_ingredients.json`(코드용 변환본) · `backend/src/barum/reference/data/us_sunscreen_synonyms.json`(INCI명 동의어) · `citation_registry.md`(출처 등록)

> ⚠️ **eCFR 표기 관련 주의**: 21 CFR Part 352는 절차상 "Stayed Indefinitely"(무기한 정지)로 표시되지만, 이는 CFR 개정 절차 자체가 더 이상 쓰이지 않는다는 뜻일 뿐이다. **내용 자체는 M020 베이스라인(OTC000006)과 동일**하다. 2020년 CARES Act 시행 이후 실제 개정은 CFR이 아니라 FDA 행정오더(Administrative Order) 체계로 이루어지므로, 최신성 확인은 반드시 `accessdata.fda.gov`의 오더 이력을 함께 봐야 한다(아래 §3 참고).

---

## 채운 상태

- [x] eCFR 21 CFR 352.10 원문 직접 대조 (16종, 공식 화학명·최대함량)
- [x] OTC000006~OTC000039 사이 개정오더 전체 이력 조회 (연방관보 API, 5건 확인)
- [x] 개정오더 반영 (베모트리지놀 6% 추가, OTC000039)
- [ ] `accessdata.fda.gov` 포털 직접 열람으로 재검증 (봇 차단으로 이번엔 연방관보 API 우회, 포털 원본 미대조)
- [ ] INCI명 전체 항목 1차 출처(INCI Dictionary·CosIng) 재검증 (현재 `us_sunscreen_synonyms.json`에 일부만 verified)

---

## 1. 미국 승인 자외선차단 활성성분 (17종)

| 성분명 (CFR 공식 화학명) | 최대 함량 | 근거 오더 |
|---|---|---|
| Aminobenzoic acid (PABA) | 15% | OTC000006 (베이스라인) |
| Avobenzone | 3% | OTC000006 (베이스라인) |
| Cinoxate | 3% | OTC000006 (베이스라인) |
| Dioxybenzone | 3% | OTC000006 (베이스라인) |
| Homosalate | 15% | OTC000006 (베이스라인) |
| Menthyl anthranilate | 5% | OTC000006 (베이스라인) |
| Octocrylene | 10% | OTC000006 (베이스라인) |
| Octyl methoxycinnamate | 7.5% | OTC000006 (베이스라인) |
| Octyl salicylate | 5% | OTC000006 (베이스라인) |
| Oxybenzone | 6% | OTC000006 (베이스라인) |
| Padimate O | 8% | OTC000006 (베이스라인) |
| Phenylbenzimidazole sulfonic acid | 4% | OTC000006 (베이스라인) |
| Sulisobenzone | 10% | OTC000006 (베이스라인) |
| Titanium dioxide | 25% | OTC000006 (베이스라인) |
| Trolamine salicylate | 12% | OTC000006 (베이스라인) |
| Zinc oxide | 25% | OTC000006 (베이스라인) |
| **Bemotrizinol** | **6%** | **OTC000039 (2026-06-10 신규 승인)** |

INCI명(전성분표 표기)이 위 CFR 공식명과 다른 성분은 `us_sunscreen_synonyms.json`에서 대조한다 (예: Octinoxate=Octyl methoxycinnamate, Padimate O의 이명은 OD-PABA 등).

---

## 2. 판정에 쓰는 법 (요약, 상세 판정 규칙은 2단계 문서에서 확정)

1. 광고 문구에 "SPF" 표현 또는 자외선차단 표방이 있는가? → 있으면 그 자체로 "미국에서는 화장품이 아니라 OTC 의약품 분류" 경고 대상 (표현 유무만으로 판단, 성분과 무관하게 항상 뜸)
2. 전성분에 자외선차단 성분이 있는가? → `us_sunscreen_synonyms.json`으로 INCI명을 CFR 공식명으로 정규화한 뒤, 위 표와 대조
   - 표에 있음 → 미국에서도 승인된 성분
   - 표에 없음 → 미국 FDA 미승인 성분으로 지목
   - 전성분 정보 자체가 없음 → 확인 불가, 성분 정보 추가 필요 안내

## 3. 잠재 리스크 (반영 안 함, 각주로만 기록)

**2021-09-27 제안오더 `OTC000008`**이 위 17종 중 12종(cinoxate·dioxybenzone·ensulizole(phenylbenzimidazole sulfonic acid)·homosalate·meradimate(menthyl anthranilate)·octinoxate(octyl methoxycinnamate)·octisalate(octyl salicylate)·octocrylene·padimate O·sulisobenzone·oxybenzone·avobenzone)에 대해 **GRASE 미인정(not GRASE)**을 제안했다. 자료 부족이 이유다.

- **2026-08-18 기준 아직 최종화 안 됨** (제안 단계에서 멈춤, 연방관보 API로 확인). 그래서 위 §1 표엔 반영하지 않는다.
- 이 오더가 통과되면 목록이 4종(PABA·Titanium dioxide·Trolamine salicylate·Zinc oxide, 이 중 PABA·Trolamine salicylate는 별도로 위해성 우려가 제기돼온 성분이라 함께 빠질 가능성도 있음)만 남을 수도 있다.
- **판정 로직에 이 리스크를 반영할지는 2단계(판정 규칙 문서)에서 별도 결정 필요.** (예: 안내 문구에 "이 목록은 2026-08 기준이며, 진행 중인 재검토가 있어 변동 가능"을 넣을지 등)

---

## 4. 아직 안 끝난 것

1. `accessdata.fda.gov` OTC Monographs@FDA 포털 직접 열람 재검증 — 봇 차단으로 이번엔 연방관보(federalregister.gov) API로 우회 확인함. 포털 자체 원문 대조는 못 함.
2. INCI명 동의어 매핑 중 일부(Dioxybenzone·Oxybenzone·Avobenzone의 벤조페논 계열명)는 1차 출처 재확인 안 됨 — `us_sunscreen_synonyms.json`의 `confidence: "unverified"` 항목 참고.
