"""배포 파이프라인(RagJudge) 재평가 — base score_eval과 나란히 비교.

score_eval.py는 base PromptJudge(제로샷)를 재지만, 실제 /check는 RagJudge(규칙 +
규정 grounding + 사례 pgvector)를 쓴다. 같은 라벨셋을 RagJudge로 통과시켜 실제 배포
정확도를 잰다. 발표에서 "base 제로샷 → 배포 파이프라인" 개선폭을 보여주는 용도.

    ./venv/bin/python scripts/eval_ragjudge.py            # 1회
    ./venv/bin/python scripts/eval_ragjudge.py --reps 3   # 3회 + 범위·안정성

**A/B 비교는 반드시 `--reps 3` 이상으로 한다.** 이 평가셋의 실행 편차가 크다
(2026-08-20 실측: 42문장에서 31~36건, 폭 11.9%p). 1회씩 비교했다가 "2.4%p 하락"으로
잘못 보고한 적이 있는데, 기준선으로 쓴 값이 하필 범위 상단이었다. 두 조건의 **범위가
겹치면 효과 없음**으로 본다.

채점 규칙(RagJudge는 문장당 라벨이 아니라 finding을 낸다):
- finding 있으면 그 violation_type이 라벨(플래그 위반/검토필요는 별도 집계).
- finding 없으면 '미플래그'(= 합법/대상외로 안 잡음). 미판정(VLM 실패)은 따로.
- 일치: human이 위반이면 finding의 유형이 일치해야 O. human이 합법·대상외면 미플래그가 O.
- 미탐(1급): human 위반인데 아무 finding도 없음(대상외/미판정 포함). 검토필요라도 finding이면 '잡음'.
- 오탐: human 합법인데 위반유형 finding. 플래그별(위반/검토필요)로 나눠 base와 비교 가능하게.
"""

import argparse
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for _p in (ROOT, ROOT / "src"):
    _sp = str(_p)
    if _sp not in sys.path:
        sys.path.insert(0, _sp)

import score_eval as se  # noqa: E402
from barum.judge.cosmetic import JudgeResult, RagJudge  # noqa: E402
from barum.storage.cases_store import build_case_retriever  # noqa: E402
from barum.vlm import get_vlm  # noqa: E402

COMPARE = Path("data/eval_compare.csv")


HOLDOUT = Path("data/prompt_holdout.jsonl")
INGREDIENTS = Path("data/eval_ingredients.json")


def _load_ingredients() -> dict[str, dict]:
    """상품별 전성분·함량을 읽는다(`extract_eval_ingredients.py` 산출물).

    2호(기능성오인) 판정은 전성분을 대조해 합법/검토필요를 가르는데, 지금까지 평가셋에
    전성분이 안 붙어 그 경로가 한 번도 작동한 적이 없었다. 상세 이미지에 이미 들어 있던
    것을 읽어온 것이라 새 수집이 아니다(로그 ㉑-2).
    """
    if not INGREDIENTS.exists():
        sys.exit(f"[없음] {INGREDIENTS} — extract_eval_ingredients.py를 먼저 돌릴 것")
    raw = json.loads(INGREDIENTS.read_text(encoding="utf-8"))
    out = {}
    for code, v in raw.items():
        names = [n.strip() for n in (v.get("ingredients_raw") or "").split(",") if n.strip()]
        amounts = [(a.get("name", ""), a.get("amount", "")) for a in (v.get("amounts") or [])
                   if a.get("name")]
        out[code] = {"ingredients": names or None, "amounts": amounts or None}
    return out


def _judge_all(judge, sentences: list[dict], scored: list[dict],
               by_product: bool, ing_map: dict | None) -> JudgeResult:
    """판정을 돌린다. by_product면 상품 단위로 나눠 부른다.

    전성분은 상품마다 다르므로 한 배치에 여러 상품을 섞으면 넘길 수가 없다. 운영
    파이프라인도 상품 하나씩 판정하므로 이쪽이 실제와 더 가깝다. 다만 배치 구성이
    바뀌면 판정도 조금 달라지므로, 전성분 효과만 보려면 `--by-product`만 켠 조건과
    비교해야 한다(두 변경을 한꺼번에 재면 무엇 때문인지 못 가린다).
    """
    if not by_product:
        return judge.judge(sentences, "KR")

    groups: dict[str, list[int]] = {}
    for i, r in enumerate(scored):
        groups.setdefault(r.get("product") or "(미상)", []).append(i)

    merged = JudgeResult()
    for code, idxs in groups.items():
        ing = (ing_map or {}).get(code) or {}
        r = judge.judge([sentences[i] for i in idxs], "KR",
                        ingredients=ing.get("ingredients"),
                        ingredient_amounts=ing.get("amounts"))
        merged.findings.extend(r.findings)
        merged.unjudged.extend(r.unjudged)
    return merged


def _load_holdout() -> list[dict]:
    """프롬프트 A/B용 홀드아웃(jsonl)을 읽는다.

    42문장 골드셋은 실행 편차(±2~3건)보다 작은 효과를 검출할 수 없고, 같은 셋으로
    여러 안을 비교하면 선택 편향이 생긴다. 이 셋은 963 정답셋 중 평가셋과 안 겹치는
    문장에서 층화표본으로 뽑았고 **프롬프트 실험에 한 번도 안 쓰였다**
    (`scripts/build_prompt_holdout.py`). 규칙 A/B에는 쓰면 안 된다.
    """
    if not HOLDOUT.exists():
        sys.exit(f"[없음] {HOLDOUT} — build_prompt_holdout.py를 먼저 돌릴 것")
    return [json.loads(line) for line in HOLDOUT.read_text(encoding="utf-8").splitlines() if line.strip()]


def main(reps: int = 1, holdout: bool = False, by_product: bool = False,
         ingredients: bool = False) -> None:
    rows = _load_holdout() if holdout else se.load_labeled()
    # ver2는 검토필요 행의 유형 칸이 비어 있을 수 있다(963셋이 유형을 잘 안 매김).
    # `human in LABELS`만 보면 그 행들이 조용히 채점에서 빠진다 — 확정도가 있으면
    # 채점 대상이다. "애매"는 여기서도 제외된다(유형이 LABELS 밖, 확정도도 빈칸).
    scored = [r for r in rows if r["human"] in se.LABELS or r.get("flag")]
    src = "홀드아웃(프롬프트 A/B 전용)" if holdout else "ver2 골드셋"
    print(f"채점대상 {len(scored)}문장 (RagJudge 파이프라인, {src})")

    sentences = [
        {"order": i, "tile": None, "text": r["text"]} for i, r in enumerate(scored)
    ]

    try:
        retriever = build_case_retriever()
        print("사례 pgvector 검색: 활성")
    except Exception as e:
        retriever = None
        print(f"사례 pgvector 검색: 비활성({type(e).__name__}) — 규정 grounding만")

    judge = RagJudge(get_vlm("openai"), case_retriever=retriever)
    print(f"판정: RagJudge(provider=openai, model={get_vlm('openai').model})")

    ing_map = None
    if ingredients:
        if not by_product:
            sys.exit("[중단] --ingredients는 --by-product가 있어야 한다(전성분은 상품 단위다)")
        ing_map = _load_ingredients()
        have = sum(1 for v in ing_map.values() if v["ingredients"])
        print(f"전성분: {have}/{len(ing_map)} 상품 투입")
    print(f"배치: {'상품 단위' if by_product else '전체 한 묶음'}\n", flush=True)

    runs = [_score_once(judge, sentences, scored, by_product, ing_map) for _ in range(reps)]
    if reps > 1:
        _report_repeats(runs, len(scored))
    _report_one(runs[-1], len(scored))
    _append_compare(runs[-1], len(scored))


def _score_once(judge, sentences: list[dict], scored: list[dict],
                by_product: bool = False, ing_map: dict | None = None) -> dict:
    """한 회차를 돌려 채점 결과를 dict로 낸다(출력은 안 한다).

    반복 측정을 위해 판정+채점만 떼어냈다. 문장별 판정(`verdicts`)도 같이 돌려주는데,
    회차 간 흔들림을 문장 단위로 보려면 그게 필요하다.
    """
    result = _judge_all(judge, sentences, scored, by_product, ing_map)

    by_order: dict[int, tuple[str, str]] = {
        f.location.order: (f.violation_type.value, f.flag.value) for f in result.findings
    }
    unjudged_orders = {u.location.order for u in result.unjudged}

    match = miss = fa_violation = fa_review = 0
    review_caught = review_total = 0
    misses, false_alarms = [], []
    verdicts: dict[int, str] = {}  # 문장별 AI 판정(회차 간 안정성 비교용)
    for i, r in enumerate(scored):
        human, human_flag = r["human"], r.get("flag", "")
        finding = by_order.get(i)
        ai_type = finding[0] if finding else None
        ai_flag = finding[1] if finding else ""

        if human_flag == "검토필요":
            # 검토필요는 "플래그를 달았는가"만 본다. 정답셋이 검토필요 행에 유형을 잘
            # 안 매기기 때문이다(963셋은 검토필요 160건 중 154건이 유형 빈칸) — 유형까지
            # 요구하면 정답에 없는 걸 요구하는 셈이 된다. 유형이 적혀 있으면 그것도
            # 맞아야 일치로 친다. AI가 위반으로 더 세게 부른 건 미탐이 아니라 정답이다.
            review_total += 1
            ok = finding is not None and (not human or ai_type == human)
            if finding is not None:
                review_caught += 1
            else:
                miss += 1
                misses.append((r["n"], r["text"], f"검토필요/{human or '유형미상'}",
                               "(미판정)" if i in unjudged_orders else "미플래그"))
        elif human in se.VIOLATION:
            ok = finding is not None and ai_type == human
            if finding is None or ai_type not in se.VIOLATION:
                miss += 1
                misses.append((r["n"], r["text"], human, ai_type or ("(미판정)" if i in unjudged_orders else "미플래그")))
        else:  # 합법·대상외·애매
            ok = finding is None and i not in unjudged_orders
            if human == "합법" and finding is not None and ai_type in se.VIOLATION:
                if ai_flag == "위반":
                    fa_violation += 1
                else:
                    fa_review += 1
                false_alarms.append((r["n"], r["text"], ai_type, ai_flag))
        match += ok
        verdicts[i] = f"{ai_type or '미플래그'}/{ai_flag}" if finding else "미플래그"

    return {
        "match": match, "miss": miss,
        "fa_violation": fa_violation, "fa_review": fa_review,
        "unjudged": len(unjudged_orders),
        "review_caught": review_caught, "review_total": review_total,
        "misses": misses, "false_alarms": false_alarms,
        "verdicts": verdicts, "scored": scored,
    }


def _report_repeats(runs: list[dict], n: int) -> None:
    """반복 실행의 평균·범위와 **문장 단위 안정성**을 보고한다.

    왜 필요한가: 이 평가셋의 실행 편차가 커서(2026-08-20 실측, 42문장에서 31~36건 =
    폭 11.9%p) 1회 결과로는 A/B를 판단할 수 없다. 실제로 1회씩만 비교해 "2.4%p 하락"
    이라고 잘못 보고한 적이 있다 — 알고 보니 기준선으로 쓴 값이 범위 상단이었다.
    그때 손으로 셸 스크립트를 짜서 3회씩 돌렸는데, 그걸 도구에 넣은 것이다.

    **문장 단위 안정성**은 새 지표다. 회차마다 판정이 바뀌는 문장이 몇 개인지 센다.
    같은 광고를 두 번 검사했을 때 결과가 달라지면 사용자는 시스템을 못 믿는다 —
    정확도와 별개 품질인데 지금까지 아무도 안 재고 있었다. 흔들리는 문장 목록은
    그 자체로 다음 개선 후보다(모델이 확신 없는 지점).
    """
    matches = [r["match"] for r in runs]
    lo, hi = min(matches), max(matches)
    avg = sum(matches) / len(matches)
    print("=" * 52)
    print(f"[반복 {len(runs)}회] 일치 건수: {', '.join(str(m) for m in matches)}")
    print(f"  평균 {avg:.1f}/{n} = {avg / n * 100:.1f}%"
          f" | 범위 {lo}~{hi}건 ({lo / n * 100:.1f}~{hi / n * 100:.1f}%, 폭 {(hi - lo) / n * 100:.1f}%p)")
    if lo != hi:
        print(f"  ※ A/B 비교 시 다른 조건의 범위가 이 범위와 겹치면 효과 없음으로 본다.")

    for label, k in (("미탐", "miss"), ("오탐", "fa_total"), ("검토필요 포착", "review_caught")):
        vals = [r["fa_violation"] + r["fa_review"] if k == "fa_total" else r[k] for r in runs]
        lo2, hi2 = min(vals), max(vals)
        rng = f" (범위 {lo2}~{hi2})" if lo2 != hi2 else ""
        print(f"  {label}: {', '.join(str(v) for v in vals)} | 평균 {sum(vals)/len(vals):.1f}{rng}")

    unstable = [
        i for i in runs[0]["verdicts"]
        if len({r["verdicts"].get(i) for r in runs}) > 1
    ]
    stable_n = n - len(unstable)
    print(f"  문장 단위 안정성: {stable_n}/{n} 문장이 {len(runs)}회 내내 같은 판정"
          f" ({stable_n / n * 100:.1f}%)")
    if unstable:
        print(f"  흔들린 문장 {len(unstable)}건 (모델이 확신 없는 지점 = 개선 후보):")
        for i in unstable:
            r = runs[0]["scored"][i]
            seen = " / ".join(str(run["verdicts"].get(i)) for run in runs)
            print(f"    #{r['n']} {r['text'][:30]} -> {seen}")
    print()


def _report_one(res: dict, n: int) -> None:
    """한 회차 상세 보고(반복 실행이면 마지막 회차)."""
    match, acc = res["match"], res["match"] / n * 100
    print("=" * 52)
    print(f"[RagJudge 파이프라인] 채점 {n}문장")
    print(f"전체 일치율: {match}/{n} = {acc:.1f}%")
    print(f"미탐(위반·검토필요→미플래그, 1급): {res['miss']}건  ← 낮을수록 좋음")
    print(f"오탐(합법→위반유형 finding): 위반 {res['fa_violation']}건 + 검토필요 {res['fa_review']}건 = {res['fa_violation'] + res['fa_review']}건")
    print(f"미판정(VLM 실패): {res['unjudged']}건")
    if res["review_total"]:
        # 검토필요 해소율은 위반탐지율과 별개 지표다(합산 금지, 모집단이 다르다).
        print(f"검토필요 포착: {res['review_caught']}/{res['review_total']}건")

    print("\n[미탐 목록]")
    for nn, text, human, ai in res["misses"]:
        print(f"  #{nn} 사람={human} AI={ai} | {text[:30]}")
    print("\n[오탐 목록]")
    for nn, text, ai, flag in res["false_alarms"]:
        print(f"  #{nn} AI={ai}/{flag} | {text[:34]}")


def _append_compare(res: dict, n: int) -> None:
    """비교표 누적(gitignore, 로컬). base와 나란히 남긴다."""
    match = res["match"]
    acc = match / n * 100
    miss = res["miss"]
    fa_violation, fa_review = res["fa_violation"], res["fa_review"]
    new = not COMPARE.exists()
    with COMPARE.open("a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["시각", "provider", "판정기", "채점수", "일치율%", "미탐", "오탐", "비고"])
        w.writerow([
            "08-12", "openai", "RagJudge", n, f"{acc:.1f}",
            miss, fa_violation + fa_review,
            f"오탐내역 위반{fa_violation}/검토{fa_review}",
        ])
    print(f"\n비교표 누적: {COMPARE}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--reps", type=int, default=1,
                    help="반복 실행 횟수(기본 1). A/B 비교는 2~3 이상을 쓴다 — "
                         "이 평가셋은 실행 편차가 커서 1회 결과로는 판단할 수 없다.")
    ap.add_argument("--by-product", action="store_true",
                    help="상품 단위로 나눠 판정한다(운영 파이프라인과 같은 구성).")
    ap.add_argument("--ingredients", action="store_true",
                    help="상품별 전성분을 판정에 넘긴다. --by-product 필요.")
    ap.add_argument("--holdout", action="store_true",
                    help="ver2 골드셋 대신 프롬프트 A/B 홀드아웃(data/prompt_holdout.jsonl)을 쓴다. "
                         "표본이 크고 프롬프트 실험에 안 쓰인 셋이라 A/B 판단은 이쪽으로 한다.")
    _a = ap.parse_args()
    main(reps=_a.reps, holdout=_a.holdout, by_product=_a.by_product,
         ingredients=_a.ingredients)
