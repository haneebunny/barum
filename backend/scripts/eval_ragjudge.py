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
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for _p in (ROOT, ROOT / "src"):
    _sp = str(_p)
    if _sp not in sys.path:
        sys.path.insert(0, _sp)

import score_eval as se  # noqa: E402
from barum.judge.cosmetic import RagJudge  # noqa: E402
from barum.storage.cases_store import build_case_retriever  # noqa: E402
from barum.vlm import get_vlm  # noqa: E402

COMPARE = Path("data/eval_compare.csv")


def main(reps: int = 1) -> None:
    rows = se.load_labeled()
    # ver2는 검토필요 행의 유형 칸이 비어 있을 수 있다(963셋이 유형을 잘 안 매김).
    # `human in LABELS`만 보면 그 행들이 조용히 채점에서 빠진다 — 확정도가 있으면
    # 채점 대상이다. "애매"는 여기서도 제외된다(유형이 LABELS 밖, 확정도도 빈칸).
    scored = [r for r in rows if r["human"] in se.LABELS or r.get("flag")]
    print(f"채점대상 {len(scored)}문장 (RagJudge 파이프라인)")

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
    print(f"판정: RagJudge(provider=openai, model={get_vlm('openai').model})\n", flush=True)

    runs = [_score_once(judge, sentences, scored) for _ in range(reps)]
    if reps > 1:
        _report_repeats(runs, len(scored))
    _report_one(runs[-1], len(scored))
    _append_compare(runs[-1], len(scored))


def _score_once(judge, sentences: list[dict], scored: list[dict]) -> dict:
    """한 회차를 돌려 채점 결과를 dict로 낸다(출력은 안 한다).

    반복 측정을 위해 판정+채점만 떼어냈다. 문장별 판정(`verdicts`)도 같이 돌려주는데,
    회차 간 흔들림을 문장 단위로 보려면 그게 필요하다.
    """
    result = judge.judge(sentences, "KR")

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
    main(reps=ap.parse_args().reps)
