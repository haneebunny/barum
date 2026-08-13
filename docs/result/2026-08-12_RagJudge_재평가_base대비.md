# RagJudge 재평가: base 제로샷 대비 개선폭 (2026-08-12)

> 이 문서가 다루는 시점: 2026-08-12, RagJudge(규칙집 우선 + VLM fallback) 구축 직후.
> 목적: 발표(8/27) 전/후 비교의 시작점 스냅샷. 이후 판정로직·프롬프트를 더 고도화하면
> 같은 형식으로 새 스냅샷을 이 문서에 이어 붙인다(소급 재현 불가하므로 매번 착수 전 기록).
> 원자료 위치: `PROGRESS_BE.md` §"2026-08-12 · 배포 파이프라인(RagJudge) 재평가 + base 대비 개선폭"
> (커밋 `4897931`), `backend/data/eval_compare.csv`(gitignore, 로컬 전용), 상세 `backend/data/eval_result_*.xlsx`.

## 비교 대상
- **base 제로샷 (`scripts/score_eval.py`)**: 규칙집·grounding·사례 없이 VLM에 문장만 던지는 판정기.
  실제 배포 파이프라인이 아니라 하한선 참고용.
- **배포 RagJudge (`scripts/eval_ragjudge.py`)**: 규칙집 우선 매칭 + 매칭 안 되면 VLM에 규정
  grounding을 붙여 판정. 실제 `/check`가 쓰는 판정기.
- 같은 라벨셋 40문장으로 동일 조건 비교.

## 결과

| 지표 | base 제로샷(score_eval) | 배포 RagJudge(eval_ragjudge) |
|---|---|---|
| 일치율 | 60.0% (24/40) | **65.0% (26/40)** |
| 미탐(위반을 합법으로 놓침, 1급) | 1건 | **0건** |
| 오탐(합법을 위반으로 flag) | 11건(전부 위반) | 11건(위반 6 + 검토필요 5) |

## 케이스 단위 관찰

**미탐 1→0**: #33 "약국 입점 화장품". base는 규칙집에 "약국전용"만 있고 "약국 입점"은 없어서
놓쳤다. RagJudge는 규칙이 아니라 규정 grounding LLM이 잡았다(규칙집 확장 후보로 기록해둠).

**하드오탐 11→6**: base가 위반으로 과잉판정하던 경계표현 5건(진정·미백니즈 등)이 RagJudge에서는
검토필요로 완화됐다(규칙+grounding 효과). 남은 위반 오탐 6건은 완벽·최적·파워 같은 일반 수식어다.
A1 결정으로 이런 수식어는 규칙에 안 넣고 VLM 판단에 맡기기로 했다. 5호(과장 수식어) 규칙이
확정되기 전까지는 이 6건이 유지될 것으로 본다.

## 발표용 한 줄 요약
"base 제로샷 60%/미탐1 → 배포 RagJudge 65%/미탐0/하드오탐 절감."

## 재현 방법
```bash
cd backend
./venv/bin/python scripts/score_eval.py       # base 제로샷
./venv/bin/python scripts/eval_ragjudge.py    # 배포 RagJudge
```
결과는 `data/eval_compare.csv`에 누적된다(모델/판정기별 한 줄씩).
