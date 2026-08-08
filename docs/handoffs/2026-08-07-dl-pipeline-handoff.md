# 핸드오프: DL 코어 ① 문장 분류기 파이프라인 (학습·평가 준비)

> **받는 사람:** DL/ML 담당 Claude (backend/Python)
> **주는 사람:** PM
> **날짜:** 2026-08-07
> **목표 한 줄:** 사람 수동 라벨링(goldset/holdout)이 끝나는 순간 **평가셋 경로만 바꿔** 바로 DL 성능을 뽑을 수 있도록, 지금 학습·평가 파이프라인을 다 짜두고 **VLM 라벨로 드라이런까지** 돌려 버그를 잡아둔다.

---

## 0. 착수 전 반드시 읽을 것 (순서대로)

1. **`CLAUDE.md`** (repo 루트): 작업 규칙. 특히 §A(안 정한 결정은 대신 정하지 말고 선택지 제시)·§B(단계별 계획 먼저, "진행" 전엔 코드 X)·§E(얕은 패키지 `src/vericops/`, 영어 snake_case 식별자, 계층적 에러 처리, 순수 로직만 pytest).
2. **`PROJECT.md` §3 (DL 코어 ① 설계)**: 이 작업의 **설계 원본**. 입력 단위·출력 라벨·부트스트랩·백본·클래스 불균형이 여기서 확정됨. §3-2(미탐 회수 캐스케이드)도.
3. **`ROADMAP.md` §1·§3**: 전략(선생-학생) + 데이터 현황 수치.
4. 실제 데이터 파일을 직접 열어 스키마 확인: `backend/data/prescreen.jsonl`, `backend/data/goldset_master.jsonl`, `backend/data/holdout_master_v1.jsonl`.

---

## 1. 미션 (이번 컷의 범위)

`backend/`에 **DL 코어 ① (한국어 문장 다중분류기)**의 **데이터로더 → 학습 → 평가** 파이프라인을 짜고, **지금 있는 VLM 라벨로 드라이런**해 end-to-end 무결성을 검증한다.

**할 것:**
- 데이터로더: 학습 코퍼스(VLM 라벨) + 평가셋(goldset/holdout) 로딩, 문장+문맥 조립, 라벨 매핑, split.
- 학습 스크립트: KoELECTRA-base 파인튜닝, 클래스 불균형 처리, 체크포인트 저장.
- 평가 스크립트: 클래스별 정밀도/재현율/F1 + **미탐율(recall)** + 혼동행렬 + VLM 베이스라인 대비.
- **드라이런(Colab T4)**: VLM hint 라벨로 학습→평가를 1회 완주해 파이프라인 검증(성능 수치는 낮아도 무방, 목적은 버그 잡기).
- 로컬 CPU **마이크로 스모크**(few-shot, 1 step)로 GPU 없이 코드 경로 검증.

**하지 말 것 (후속 컷, YAGNI):**
- Phase 2(원료 메타 슬롯), ② 이미지유형 CNN 라우터, 미탐 회수 캐스케이드(F19/F15) 구현, F18 재학습 버튼.
- 회피표기 정규화(⑤) 사전.
- 백본 후보 대규모 비교(KLUE-RoBERTa 등)는 사람 라벨 확정 후. 지금은 KoELECTRA-base 하나로.
- 하이퍼파라미터 튜닝(드라이런은 기본값으로 완주만).

## 2. 확정된 결정 (PROJECT.md §3 소관 + PM 결정)

| 항목 | 결정 | 근거 |
|---|---|---|
| 판정/입력 단위 | **문장(span) + 주변 문맥 윈도우**(앞뒤 1~2문장) | PROJECT §3, §3-1 Phase 1 |
| 출력 | **다중클래스 1라벨** (7클래스, 아래 §3) | PROJECT §3 |
| 백본 | **KoELECTRA-base** (`monologg/koelectra-base-v3-discriminator`) 출발 | PROJECT §3 |
| 클래스 불균형 | **class weight** 등 (2호 극소·질병표방 편중) | PROJECT §3 |
| 정책 | **recall 우선**(미탐 비용 > 오탐). **미탐율이 1급 지표.** | PROJECT §2.5, §3-2 |
| 실행 타깃 | **backend `.py` 스크립트 + Colab T4 노트북 러너.** 로컬은 CPU 스모크만 | PM 2026-08-07 |
| 드라이런 라벨 | **VLM hint**(`prescreen.jsonl`의 `hint`)로 파이프라인 검증 | PM 2026-08-07 (Q1) |
| 코드 위치 | `backend/src/vericops/model/` (얕은 패키지) + `backend/scripts/` CLI + `backend/notebooks/` | CLAUDE.md §E |

## 3. 라벨 체계 (7클래스, `reference/violation_types/` 기준)

`prescreen.py`의 `LABELS`와 **정확히 일치**시킬 것:
```
합법, 1호_질병표방, 2호_의약품오인, 3호_건기식오인, 4호_거짓과장, 5호_소비자기만, 대상외
```
- 근거: `reference/violation_types/type_1~5_*.md` + `certified_phrases.md`.
- ※ 옛 6종(후기 효과보증·안전성 단정 등)은 **폐기됨**. 쓰지 말 것.

## 4. 데이터 (경로는 `backend/` 기준 · 전부 gitignore, 로컬 존재)

**먼저 각 파일을 열어 실제 필드를 확인**하고 아래와 대조할 것.

| 용도 | 파일 | 규모 | 비고 |
|---|---|---|---|
| **학습 코퍼스**(VLM 라벨) | `data/prescreen.jsonl` | 132상품 / **4,225 keep 문장** | 각 문장에 `hint`(VLM 7클래스 라벨). `keep=true`만 들어있음 |
| **평가(goldset)** | `data/goldset_master.jsonl` | 48상품 / 215문장 | `sentence`·`context_before/after`·`tile_text`·`hint`·`certified_function`·`product_type` 필드 보유 |
| **평가(holdout)** | `data/holdout_master_v1.jsonl` | 65상품 / 331문장 | 미탐율 평가용 |
| **사람 정답 라벨(진행 중)** | `data/goldset_A.xlsx` · `goldset_B.xlsx` · `holdout_B.xlsx` | 라벨링 중 | A·B 두 라벨러 교차검증. **최종 gold 라벨 확정 방식은 §8 열린 항목** |
| A/B 정합성 자료 | `data/alignment_round3·4*.{jsonl,xlsx}` | | 불일치 리졸브 흐름 참고 |

- **문맥 윈도우:** goldset_master엔 `context_before/after`가 있음. 학습 코퍼스(`prescreen.jsonl`)에 문맥이 없으면, `data/ocr_sentences*.jsonl`의 문장 순서에서 앞뒤를 재구성하거나(권장) 드라이런은 문장-only로 먼저 돌리고 문맥 조립을 뒤에 붙인다. **어느 쪽이든 실제 스키마를 확인하고 결정 근거를 코드 주석/문서에 남길 것.**

## 5. 목표 산출물 구조

```
backend/
├─ src/vericops/model/
│  ├─ __init__.py
│  ├─ dataset.py       # jsonl 로딩, 문장+문맥 조립, 7클래스 라벨맵, train/val split, torch Dataset
│  ├─ train.py         # KoELECTRA-base 파인튜닝(config·class weight·체크포인트 저장)
│  └─ evaluate.py      # 클래스별 P/R/F1 + 미탐율 + 혼동행렬 + VLM 베이스라인 대비
├─ scripts/
│  ├─ train_classifier.py   # CLI: --train data/prescreen.jsonl 등
│  └─ eval_classifier.py    # CLI: --eval <labeled.jsonl> --ckpt <path>
├─ notebooks/
│  └─ colab_train.ipynb     # 얇은 러너: repo 접근 + pip + 위 스크립트 호출
└─ requirements-ml.txt      # torch·transformers·scikit-learn 등 (기본 requirements와 분리)
```
- **모델/토크나이저 로딩은 얇은 어댑터로** 격리(백본 교체 대비). VLM 어댑터(`src/vericops/vlm.py`) 패턴 참고.
- 무거운 ML 의존성은 `requirements-ml.txt`로 분리(기본 `requirements.txt` 가볍게 유지).

## 6. 평가 사양 (미탐율이 1급 지표)

- 클래스별 **정밀도·재현율·F1**, macro 평균, **혼동행렬**.
- **미탐율(누락율):** "실제 위반인데 `합법`으로 분류된 비율". recall 우선 정책의 핵심 수치이니 별도로 크게 보고.
- **VLM 베이스라인 대비:** 같은 평가셋에서 VLM hint의 성능과 나란히 표로. (학생이 선생을 얼마나 따라잡/넘었나)
- `eval_classifier.py`는 **아무 라벨 jsonl이나 받게** 설계 → 지금은 hint 라벨로, 나중엔 사람 gold로 경로만 교체.

## 7. 완료 기준 (Acceptance)

1. `dataset.py`가 `prescreen.jsonl`을 (문장[+문맥], 라벨) 샘플로 로딩, 7클래스 매핑, train/val split.
2. `train.py`가 KoELECTRA-base를 VLM hint 라벨로 파인튜닝, 체크포인트 저장 (Colab T4에서 완주).
3. `evaluate.py`가 goldset/holdout 경로를 받아 클래스별 P/R/F1 + 미탐율 + 혼동행렬 출력.
4. **드라이런 완주**(Colab): 학습→평가가 에러 없이 끝나고 수치가 나온다(성능 무관).
5. **로컬 CPU 마이크로 스모크** 통과: 소량 샘플·1 step로 코드 경로 검증(GPU 없이).
6. 클래스 불균형 처리(class weight 등) 적용됨.
7. 사람 gold 확정 시 **코드 변경 없이** `eval_classifier.py --eval` 경로 교체만으로 진짜 수치 산출 가능.
8. 순수 로직(라벨맵·split·문맥 조립)은 pytest 유닛테스트(CLAUDE.md §E).

## 8. 🔴 PM 확인 대기 항목 (진행 전/평가 전 확인, 대신 정하지 말 것)

1. **학습 데이터 출처 (방법론 핵심):** PROJECT.md에 해석 여지가 있음.
   - §2.2 "사람 승인 라벨만 학습(자동 라벨 자기학습 금지)"은 **F18 재학습 루프**의 오염 방지 가드레일로 읽힘.
   - §2.2·§3 "VLM=선생/자동 라벨러, 우리 DL=학생"은 **초기 부트스트랩은 VLM 라벨로 증류**한다는 뜻으로 읽힘.
   - **이번 드라이런은 VLM 라벨 사용이 PM 승인됨**(파이프라인 검증 목적). 그러나 **"진짜 초기 모델"의 학습 라벨 = VLM 증류인가 / 사람승인만인가**는 확정 안 됨 → PM에게 확인 후 학습 코퍼스 소스를 확정.
2. **A/B 사람 라벨의 최종 gold 확정 방식:** xlsx에 조정된 단일 정답 컬럼이 있는가, 아니면 DL 담당이 A/B를 병합/조정해야 하는가? (라벨링 담당자에게 확인. `alignment_round*` 흐름 참고.) 드라이런은 안 막지만 **진짜 평가 전 필수.**
3. **문맥 윈도우 크기**(앞뒤 1 vs 2문장): 기본 ±1로 시작하되 확정은 PM/실측.

## 9. 작업 방식 (CLAUDE.md 준수)

- 착수 전 **단계별 구현 계획을 먼저 제시**하고 승인받은 뒤 코드(§B). 스펙에서 안 정한 게 나오면 **멈추고 PM에게 선택지 제시**(§A).
- 에러 처리(§E): 예상된 실패(빈 문장·깨진 레코드)는 스킵+기록하고 배치 계속, 예상 못 한 실패(스키마 위반)는 삼키지 말고 예외. 로깅은 `print`.
- **VLM 과금 호출은 이 작업에 없음**(라벨은 이미 `prescreen.jsonl`에 있음). 새로 VLM을 돌릴 필요 생기면 멈추고 PM에게.
- 커밋: repo **git 미초기화**. 커밋하지 말고 완료 후 PM에게 알림.
- secret 하드코딩 금지(public repo). 키는 `backend/.env`.

---

## 부록: DL 담당 Claude에게 붙여넣을 착수 프롬프트(예시)

> vericops 모노레포에서 DL 코어 ① 문장 분류기의 학습·평가 파이프라인을 준비하는 작업이야. 먼저 `docs/handoffs/2026-08-07-dl-pipeline-handoff.md`를 읽고, §0의 참조 파일들(`CLAUDE.md`, `PROJECT.md` §3, 데이터 jsonl)을 직접 확인해. §8의 열린 항목은 나(PM)에게 확인하고, 그 전까지는 드라이런(VLM 라벨) 범위로만 진행해. CLAUDE.md §B대로 구현 계획을 먼저 제시하고, 승인 전엔 코드를 쓰지 마.
