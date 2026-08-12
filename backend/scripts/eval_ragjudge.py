"""배포 파이프라인(RagJudge) 재평가 — base score_eval과 나란히 비교.

score_eval.py는 base PromptJudge(제로샷)를 재지만, 실제 /check는 RagJudge(규칙 +
규정 grounding + 사례 pgvector)를 쓴다. 같은 라벨셋을 RagJudge로 통과시켜 실제 배포
정확도를 잰다. 발표에서 "base 제로샷 → 배포 파이프라인" 개선폭을 보여주는 용도.

    ./venv/bin/python scripts/eval_ragjudge.py

채점 규칙(RagJudge는 문장당 라벨이 아니라 finding을 낸다):
- finding 있으면 그 violation_type이 라벨(플래그 위반/검토필요는 별도 집계).
- finding 없으면 '미플래그'(= 합법/대상외로 안 잡음). 미판정(VLM 실패)은 따로.
- 일치: human이 위반이면 finding의 유형이 일치해야 O. human이 합법·대상외면 미플래그가 O.
- 미탐(1급): human 위반인데 아무 finding도 없음(대상외/미판정 포함). 검토필요라도 finding이면 '잡음'.
- 오탐: human 합법인데 위반유형 finding. 플래그별(위반/검토필요)로 나눠 base와 비교 가능하게.
"""

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


def main() -> None:
    rows = se.load_labeled()
    scored = [r for r in rows if r["human"] in se.LABELS]
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
    result = judge.judge(sentences, "KR")

    by_order: dict[int, tuple[str, str]] = {
        f.location.order: (f.violation_type.value, f.flag.value) for f in result.findings
    }
    unjudged_orders = {u.location.order for u in result.unjudged}

    match = miss = fa_violation = fa_review = 0
    misses, false_alarms = [], []
    for i, r in enumerate(scored):
        human = r["human"]
        finding = by_order.get(i)
        ai_type = finding[0] if finding else None
        ai_flag = finding[1] if finding else ""

        if human in se.VIOLATION:
            ok = finding is not None and ai_type == human
            if finding is None or ai_type not in se.VIOLATION:
                miss += 1
                misses.append((r["n"], r["text"], human, ai_type or ("(미판정)" if i in unjudged_orders else "미플래그")))
        else:  # 합법·대상외
            ok = finding is None and i not in unjudged_orders
            if human == "합법" and finding is not None and ai_type in se.VIOLATION:
                if ai_flag == "위반":
                    fa_violation += 1
                else:
                    fa_review += 1
                false_alarms.append((r["n"], r["text"], ai_type, ai_flag))
        match += ok

    n = len(scored)
    acc = match / n * 100
    print("=" * 52)
    print(f"[RagJudge 파이프라인] 채점 {n}문장")
    print(f"전체 일치율: {match}/{n} = {acc:.1f}%")
    print(f"미탐(위반→미플래그/대상외, 1급): {miss}건  ← 낮을수록 좋음")
    print(f"오탐(합법→위반유형 finding): 위반 {fa_violation}건 + 검토필요 {fa_review}건 = {fa_violation + fa_review}건")
    print(f"미판정(VLM 실패): {len(unjudged_orders)}건")

    print("\n[미탐 목록]")
    for nn, text, human, ai in misses:
        print(f"  #{nn} 사람={human} AI={ai} | {text[:30]}")
    print("\n[오탐 목록]")
    for nn, text, ai, flag in false_alarms:
        print(f"  #{nn} AI={ai}/{flag} | {text[:34]}")

    # 비교표 누적(gitignore, 로컬). base와 나란히 남긴다.
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
    main()
