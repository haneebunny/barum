# -*- coding: utf-8 -*-
"""1차 필터(prescreen)만 따로 재는 A/B 도구 — 양방향, 반복측정.

`eval_ragjudge.py`는 파이프라인 전체(규칙 + grounding + VLM)를 돌리므로 1차 필터
하나를 고칠 때 쓰기엔 비싸고, 뒤쪽 단계의 편차가 앞쪽 효과를 덮는다. 이 스크립트는
`RagJudge._prescreen`만 태운다(RAG 컨텍스트 없는 싼 호출).

**반드시 양방향으로 본다.** 통과해야 할 문장만 세면 "질문을 넓혀 전부 통과"가 개선처럼
보인다. 걸러야 할 문장의 차단율을 같이 봐야 필터가 무의미해졌는지 알 수 있다.
(2026-08-20 회고 규칙 6 — 한 방향만 재서 오탐을 냈던 이력이 있다.)

    ./venv/bin/python scripts/prescreen_ab.py --set probe --reps 3
    ./venv/bin/python scripts/prescreen_ab.py --set holdout --reps 3
    ./venv/bin/python scripts/prescreen_ab.py --set both --reps 3 --tag baseline

세트:
- `probe`   : tests/fixtures/prescreen_probe.json. 팩에서 도출한 [구조] 탐침(정답셋 밖).
- `holdout` : data/prompt_holdout.jsonl 119문장. 라벨을 prescreen 질문으로 옮겨 쓴다.
              위반·검토필요 = 통과해야 할 것 / 대상외 = 걸러야 할 것 /
              합법 = 중립(버려도 최종 판정은 미플래그로 같다. 기록만).
"""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for _p in (ROOT, ROOT / "src"):
    _sp = str(_p)
    if _sp not in sys.path:
        sys.path.insert(0, _sp)

from barum.judge import cosmetic  # noqa: E402
from barum.judge.cosmetic import RagJudge  # noqa: E402
from barum.vlm import get_vlm  # noqa: E402


# ── 프롬프트 변형 ─────────────────────────────────────────────────────────
# **변형을 코드에 남긴다.** 2026-08-20 프롬프트 A/B에서 결과 수치는 로그에 남았는데
# 변형 자체가 어디에도 안 남아, 이어받은 세션이 재실행이 아니라 재구현을 해야 했다.
# 채택된 안은 cosmetic.py로 옮기고, 기각된 안도 여기 남겨 재현 가능하게 둔다.
#
# A = 현행(운영 코드에서 그대로 가져온다. 복붙하면 원본과 어긋난다)
# B = 성분 갈래 정비. 팩 §1-84(기능성 고시원료 언급 → 검토필요),
#     §1-91(성분 함량 표시 광고)이 근거. [구조] 출처.
# C = B + 제품명 갈래. 팩 §1-90(광고 제목명도 판단 대상, 2025.1.21 지침 개정)이 근거.

_YES_INGREDIENT = """- 성분에 함량·비율 수치가 붙은 문구(N%, Nppm, IU, 고함량, 원액 N% 등)
- 기능성 고시원료를 내세운 문구(나이아신아마이드·알부틴·닥나무추출물·아데노신·
  레티놀·에칠헥실트리아존 등 미백·주름개선·자외선차단 고시원료)
- 성분과 효과를 연결한 문구(예: "OO추출물이 진정에 도움")"""

_NO_INGREDIENT = """함량 수치도 효능 연결도 없는 단순 성분 목록(전성분·표시성분 표기)"""

VARIANT_A = """아래 문장 각각이 화장품법 표시·광고 판정 대상인지 판단하라.

판정 대상(YES) = 아래 중 하나라도 해당:
- 피부·모발·체형에 대한 변화·개선·치료·예방을 표방하는 문구
- 의약품·의료기기·시술을 연상시키는 표현(약국·병원·니들·시술기기 등)
- 근거 없는 수치·최상급·순위·비교우위 주장(N배, 1위, 최고 등)
- 그 밖에 소비자를 오인시킬 소지가 있는 광고 문구

비대상(NO) = 성분명 나열, 용량·가격, 거래·배송 안내, 목차·번호·구획 표시,
단순 사용법 설명, 브랜드명 단독 표기.

**효능 주장이 아니어도 위 다른 항목에 해당하면 YES다.** 애매하면 YES(미탐 방지).

문장:
{items}

JSON으로만 답하라: {{"results": [{{"n": 1, "claim": true/false}}]}}
claim = true(판정 대상이다), false(아니다)."""

VARIANT_B = VARIANT_A.replace(
    "- 그 밖에 소비자를 오인시킬 소지가 있는 광고 문구",
    _YES_INGREDIENT + "\n- 그 밖에 소비자를 오인시킬 소지가 있는 광고 문구",
).replace(
    "비대상(NO) = 성분명 나열,",
    "비대상(NO) = " + _NO_INGREDIENT + ",",
).replace(
    "**효능 주장이 아니어도 위 다른 항목에 해당하면 YES다.**",
    "**성분 목록이어도 기능성 고시원료가 들어 있거나 함량 수치가 붙으면 YES다.**\n"
    "**효능 주장이 아니어도 위 다른 항목에 해당하면 YES다.**",
)

VARIANT_C = VARIANT_B.replace(
    "- 그 밖에 소비자를 오인시킬 소지가 있는 광고 문구",
    "- 제품명·상품명·제목에 효능 표현이 들어간 문구"
    '(예: "OO 안티링클 아이크림", "OO 화이트닝 크림")\n'
    "- 그 밖에 소비자를 오인시킬 소지가 있는 광고 문구",
).replace(
    "브랜드명 단독 표기.",
    "효능 표현이 없는 브랜드명·제품명 단독 표기.",
)

VARIANTS = {"A": VARIANT_A, "B": VARIANT_B, "C": VARIANT_C}

# 채택안(C)이 운영 코드와 같은지 확인한다. 프롬프트를 손보면서 여기 값이 어긋나면
# "측정한 것과 배포된 것이 다른" 상태가 되는데, 그건 실행해 봐도 안 보인다.
ADOPTED = "C"

PROBE = ROOT / "tests" / "fixtures" / "prescreen_probe.json"
HOLDOUT = ROOT / "data" / "prompt_holdout.jsonl"


def load_probe() -> list[dict]:
    """탐침셋을 (문장, 기대, 출처) 목록으로 읽는다."""
    d = json.loads(PROBE.read_text(encoding="utf-8"))
    rows = []
    for key, expect in (("must_pass", "pass"), ("must_drop", "drop"), ("borderline", "skip")):
        for item in d.get(key, []):
            rows.append({"text": item["text"], "expect": expect})
    return rows


def expect_for(flag: str, human: str) -> str | None:
    """판정 라벨을 1차 필터 질문("판정 대상인가")으로 옮긴다.

    위반·검토필요 → `pass`: 판정기가 반드시 봐야 할 문장이다. 여기서 버려지면 미탐이다.
    대상외 → `drop`: 광고 문구가 아니라 거르는 게 맞다.
    합법 → `skip`: 통과하든 탈락하든 최종 판정이 미플래그로 같다. 채점에 넣으면
    "합법을 많이 버렸다"가 개선처럼 보여 지표를 왜곡한다(비용 이득만 있다).
    그 밖(애매 등) → None: 채점 대상이 아니다.
    """
    flag, human = (flag or "").strip(), (human or "").strip()
    if flag in ("위반", "검토필요"):
        return "pass"
    if human == "대상외":
        return "drop"
    if human == "합법":
        return "skip"
    return None


def load_goldset() -> list[dict]:
    """ver2 골드셋 42문장을 prescreen 질문으로 옮긴다.

    원래 결함(#20 "콜라겐 추출물 1000ppm 함유"가 3회 내내 1차 필터에서 탈락)이
    실제로 해소됐는지 보는 확인용이다. **이 셋은 튜닝에 쓰여 왔으므로 in-sample이고,
    성능 수치로 인용하면 안 된다.** 고쳤는지 여부만 본다.
    """
    sys.path.insert(0, str(ROOT / "scripts"))
    import score_eval as se

    rows = []
    for r in se.load_labeled():
        expect = expect_for(r.get("flag"), r.get("human"))
        if expect is None:
            continue  # "애매"는 채점 대상이 아니다
        rows.append({"text": r["text"], "expect": expect})
    return rows


def load_holdout() -> list[dict]:
    """홀드아웃 라벨을 prescreen 질문(판정 대상인가)으로 옮긴다.

    위반·검토필요는 판정기가 반드시 봐야 할 문장이다(여기서 버려지면 미탐).
    대상외는 광고 문구가 아니라 걸러야 맞다. 합법은 통과·탈락 어느 쪽이든 최종 판정이
    미플래그로 같아 채점에서 뺀다(비용 관점의 이득만 있어 지표를 왜곡한다).
    """
    if not HOLDOUT.exists():
        sys.exit(f"[없음] {HOLDOUT}")
    rows = []
    for line in HOLDOUT.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        expect = expect_for(r.get("flag"), r.get("human"))
        if expect is None:
            continue
        rows.append({"text": r["text"], "expect": expect})
    return rows


def run_once(judge: RagJudge, rows: list[dict]) -> dict[str, bool]:
    """1차 필터를 한 번 돌려 문장별 통과 여부를 낸다."""
    sentences = [{"order": i, "tile": None, "text": r["text"]} for i, r in enumerate(rows)]
    kept = judge._prescreen(sentences)
    kept_orders = {s["order"] for s in kept}
    return {rows[i]["text"]: (i in kept_orders) for i in range(len(rows))}


def summarize(rows: list[dict], runs: list[dict[str, bool]], name: str) -> None:
    """양방향 지표 + 회차별 범위 + 문장 단위 안정성을 찍는다."""
    want_pass = [r for r in rows if r["expect"] == "pass"]
    want_drop = [r for r in rows if r["expect"] == "drop"]
    neutral = [r for r in rows if r["expect"] == "skip"]

    print(f"\n=== {name} ===")
    for label, group, ok in (
        ("통과해야 할 문장 통과", want_pass, True),
        ("걸러야 할 문장 차단", want_drop, False),
    ):
        counts = [sum(1 for r in group if run[r["text"]] is ok) for run in runs]
        n = len(group)
        if not n:
            continue
        pct = [f"{c / n * 100:.1f}%" for c in counts]
        print(f"{label}: {counts} / {n}  ({', '.join(pct)})  범위 {min(counts)}~{max(counts)}")

    if neutral:
        c = [sum(1 for r in neutral if run[r["text"]]) for run in runs]
        print(f"(중립·합법 통과: {c} / {len(neutral)} — 채점 밖, 비용 참고용)")

    # 문장 단위 안정성: 매회 같은 판정이 나온 문장 수. 편차와 결함을 가른다.
    stable = sum(1 for r in rows if len({run[r["text"]] for run in runs}) == 1)
    print(f"문장 단위 안정성: {stable}/{len(rows)} 문장이 {len(runs)}회 내내 같은 판정")

    # 누수: 통과해야 하는데 한 번이라도 탈락한 문장. 안정적 탈락이 진짜 결함이다.
    leaks = []
    for r in want_pass:
        drops = sum(1 for run in runs if not run[r["text"]])
        if drops:
            leaks.append((drops, r["text"]))
    if leaks:
        print(f"\n[누수] 판정기가 못 본 문장 {len(leaks)}건 (탈락횟수/{len(runs)})")
        for drops, text in sorted(leaks, reverse=True):
            kind = "안정적 탈락=결함" if drops == len(runs) else "흔들림=경계"
            print(f"  {drops}/{len(runs)} {kind}: {text[:60]}")

    # 반대 방향: 걸러야 하는데 통과한 문장. 필터가 무의미해졌는지 본다.
    passed = [(sum(1 for run in runs if run[r["text"]]), r["text"]) for r in want_drop]
    passed = [p for p in passed if p[0]]
    if passed:
        print(f"\n[필터 누락] 걸러야 할 문장이 통과 {len(passed)}건 (통과횟수/{len(runs)})")
        for c, text in sorted(passed, reverse=True):
            print(f"  {c}/{len(runs)}: {text[:60]}")


def main(which: str, reps: int, tag: str, variant: str) -> None:
    # 측정 중에만 프롬프트를 바꿔 낀다. 운영 코드는 안 건드린다(채택 시 별도 커밋).
    cosmetic.PRESCREEN_PROMPT = VARIANTS[variant]
    sets = []
    if which in ("probe", "both"):
        sets.append(("탐침셋(팩 도출, [구조])", load_probe()))
    if which in ("holdout", "both"):
        sets.append(("홀드아웃 119문장", load_holdout()))
    if which == "goldset":
        sets.append(("ver2 골드셋 42문장(확인용, in-sample)", load_goldset()))

    vlm = get_vlm("openai")
    judge = RagJudge(vlm)
    print(f"1차 필터 단독 측정 | 변형 {variant} | provider=openai model={vlm.model} | reps={reps}"
          + (f" | tag={tag}" if tag else ""))

    for name, rows in sets:
        n_pass = sum(1 for r in rows if r["expect"] == "pass")
        n_drop = sum(1 for r in rows if r["expect"] == "drop")
        print(f"\n{name}: {len(rows)}문장 (통과해야 {n_pass} / 걸러야 {n_drop} / 중립 "
              f"{len(rows) - n_pass - n_drop})", flush=True)
        runs = []
        for i in range(reps):
            print(f"  [{i + 1}/{reps}회]", flush=True)
            runs.append(run_once(judge, rows))
        summarize(rows, runs, name)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", dest="which", choices=["probe", "holdout", "both", "goldset"], default="probe")
    ap.add_argument("--reps", type=int, default=3,
                    help="반복 횟수. A/B 비교는 3회 이상. 범위가 겹치면 효과 없음으로 본다.")
    ap.add_argument("--variant", choices=["A", "B", "C"], default="A",
                    help="A=현행 / B=성분 갈래 정비 / C=B+제품명 갈래")
    ap.add_argument("--tag", default="", help="출력에 조건 이름을 붙인다(baseline/fix 등)")
    _a = ap.parse_args()
    main(which=_a.which, reps=_a.reps, tag=_a.tag, variant=_a.variant)
