# -*- coding: utf-8 -*-
"""평가셋 채점: 사람 정답 라벨 vs LLM 판정 비교.

대수가 라벨링한 `data/cosmetic_eval_labeling.xlsx`(라벨 칸 D열)을 읽어,
같은 문장을 LLM(Gemini)에 판정시키고 정답과 대조해 점수를 낸다.

실행(backend/에서):
  ./venv/bin/python scripts/score_eval.py            # 실채점(Gemini 호출)
  ./venv/bin/python scripts/score_eval.py --dry       # 호출 없이 배선만 점검

미탐(위반을 합법/대상외로 놓침)이 1급 지표다.
"""
import argparse
import sys
from pathlib import Path

import openpyxl

sys.path.insert(0, "src")
from vericops.vlm import get_vlm  # noqa: E402

XLSX = Path("data/cosmetic_eval_labeling.xlsx")
OUT = Path("data/eval_result.xlsx")

LABELS = ["합법", "1호_의약품오인", "2호_기능성오인", "4호_거짓과장기만", "대상외"]
VIOLATION = {"1호_의약품오인", "2호_기능성오인", "4호_거짓과장기만"}

JUDGE_PROMPT = """너는 한국 화장품 광고 문구가 화장품법 표시·광고 규정을 위반하는지 판정한다.
아래 문장 각각에 라벨 하나와 짧은 근거를 매겨라.

라벨(정확히 이 중 하나만):
- 합법 : 일반 보습·사용감·제형 설명 등 위반 소지 없음
- 1호_의약품오인 : 질병·치료·재생·염증 등 의학적/의약품 같은 효능 암시
- 2호_기능성오인 : 미백·주름개선·자외선차단 기능성 효능을 주장
- 4호_거짓과장기만 : 근거 없는 수치·최상급·비교우위·후기 단정·경쟁사 비방
- 대상외 : 광고 문구가 아님(성분명 나열, 거래·배송 안내, 인증서 표시, 단순 제품정보·브랜드명)

규칙:
- 한 문장에 여러 개 해당하면 가장 무거운 것 하나. 우선순위 1호 > 2호 > 4호 > 합법.
- 미탐(위반을 합법으로 놓침)이 제일 나쁘다. 애매하면 위반 쪽으로 판단한다.

문장:
{items}

JSON으로만 답하라: {{"results": [{{"n": 1, "label": "...", "reason": "..."}}]}}"""


def load_labeled():
    """xlsx에서 (번호, 문장, 사람라벨) 중 사람라벨이 채워진 행만 읽는다."""
    if not XLSX.exists():
        sys.exit(f"[없음] {XLSX} 먼저 준비할 것")
    wb = openpyxl.load_workbook(XLSX)
    ws = wb["라벨링"]
    rows = []
    for r in range(2, ws.max_row + 1):
        n = ws.cell(r, 1).value
        text = ws.cell(r, 3).value
        human = (ws.cell(r, 4).value or "").strip()
        if not text:
            continue
        rows.append({"n": n, "text": text, "human": human})
    return rows


def judge_batch(vlm, batch):
    """문장 배치를 LLM에 판정시켜 번호→라벨 dict 반환."""
    items = "\n".join(f'{b["n"]}. {b["text"]}' for b in batch)
    res = vlm.generate_json(JUDGE_PROMPT.format(items=items), [])
    out = {}
    for item in res.get("results", []):
        try:
            out[int(item["n"])] = (item.get("label", "").strip(), item.get("reason", ""))
        except (KeyError, ValueError, TypeError):
            continue
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true", help="Gemini 호출 없이 배선만 점검")
    ap.add_argument("--batch", type=int, default=12)
    args = ap.parse_args()

    rows = load_labeled()
    scored = [r for r in rows if r["human"] in LABELS]      # 채점 대상(유효 라벨)
    pending = [r for r in rows if r["human"] == ""]          # 라벨 미완
    abstain = [r for r in rows if r["human"] and r["human"] not in LABELS]  # 애매 등

    print(f"전체 {len(rows)}문장 / 라벨 완료 {len(rows)-len(pending)} / 미완 {len(pending)} / "
          f"채점대상(유효라벨) {len(scored)} / 제외(애매 등) {len(abstain)}")

    if args.dry:
        print("\n[--dry] Gemini 호출 안 함. 첫 배치 판정 프롬프트 미리보기:\n")
        preview = scored[:args.batch] or rows[:args.batch]
        items = "\n".join(f'{b["n"]}. {b["text"]}' for b in preview)
        print(JUDGE_PROMPT.format(items=items)[:1200], "...")
        return

    if not scored:
        sys.exit("\n채점할 라벨이 없다. 대수 라벨링(D열) 후 다시 실행할 것.")

    vlm = get_vlm("gemini")
    print(f"모델: {vlm.model}\n", flush=True)
    ai = {}
    for i in range(0, len(scored), args.batch):
        batch = scored[i:i + args.batch]
        ai.update(judge_batch(vlm, batch))
        print(f"  판정 {min(i+args.batch, len(scored))}/{len(scored)}", flush=True)

    # 채점
    match = miss = false_alarm = 0
    misses, false_alarms, unknown = [], [], []
    wb = openpyxl.Workbook(); r_ws = wb.active; r_ws.title = "결과"
    r_ws.append(["번호", "문장", "사람", "AI", "AI근거", "일치"])
    for r in scored:
        human = r["human"]
        ai_label, reason = ai.get(r["n"], ("(없음)", ""))
        ok = (ai_label == human)
        match += ok
        if ai_label not in LABELS:
            unknown.append(r["n"])
        if human in VIOLATION and ai_label in {"합법", "대상외"}:
            miss += 1; misses.append((r["n"], r["text"], human, ai_label))
        if human == "합법" and ai_label in VIOLATION:
            false_alarm += 1; false_alarms.append((r["n"], r["text"], ai_label))
        r_ws.append([r["n"], r["text"], human, ai_label, reason, "O" if ok else "X"])
    wb.save(OUT)

    n = len(scored)
    print("\n" + "=" * 46)
    print(f"채점 대상: {n}문장")
    print(f"전체 일치율: {match}/{n} = {match/n*100:.1f}%")
    print(f"미탐(위반→합법/대상외, 1급): {miss}건  ← 낮을수록 좋음")
    print(f"오탐(합법→위반): {false_alarm}건")
    if unknown:
        print(f"AI가 규격 밖 라벨 뱉음: {len(unknown)}건 {unknown}")
    if misses:
        print("\n[미탐 목록 — 제일 중요]")
        for n_, t, h, a in misses:
            print(f"  #{n_} 사람={h} AI={a} | {t[:40]}")
    if false_alarms:
        print("\n[오탐 목록]")
        for n_, t, a in false_alarms:
            print(f"  #{n_} AI={a} | {t[:40]}")
    print("=" * 46)
    print(f"상세: {OUT}")
    print(f"누적 토큰: {vlm.total_tokens:,}")


if __name__ == "__main__":
    main()
