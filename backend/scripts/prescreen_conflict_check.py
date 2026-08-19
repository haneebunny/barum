# -*- coding: utf-8 -*-
"""규칙 위반 확정 vs prescreen(효능주장 여부) 불일치율을 오프라인으로 잰다.

**라이브 `/check` API는 안 건드린다.** 정답셋을 대상으로, 규칙이 위반으로 확정한
문장만 모아 prescreen(효능/효과 주장인가 이진분류)을 한 번 더 돌려서 "규칙은
위반인데 prescreen은 효능주장이 아니라고 하는" 충돌이 실제로 얼마나 자주 나는지
잰다(팀장·PM 논의, 2026-08-18). 이 데이터를 보고 나중에 라이브 배선(veto 아니라
경고 로그) 여부를 판단한다 — 지금은 판단 자료만 모은다.

**왜 지금 구조에서 이 충돌이 원래 안 보이는가**: `RagJudge.judge()`는 규칙이 이미
매칭시킨 문장을 prescreen에 아예 안 보낸다(`remaining`만 봄). 그래서 이 스크립트가
규칙 확정 위반 문장을 prescreen에 "한 번 더" 보여주는 것 자체가 지금 파이프라인엔
없는 별도 관측이다.

**비용**: 정답셋(996문장) 기준 규칙 위반 확정 문장은 7건뿐이라(2026-08-18 확인)
배치 1회로 끝난다. 문장 수가 늘면 배치가 늘 수 있으니 실행 전 dry-run으로 개수부터
확인하는 걸 권한다.

사용법(backend/에서):
  python scripts/prescreen_conflict_check.py --dry-run   # 비용 0, 대상 문장 개수만 확인
  python scripts/prescreen_conflict_check.py              # 실제 실행(VLM 호출)
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, "src")

from barum.judge.cosmetic import PRESCREEN_PROMPT  # noqa: E402
from barum.reference.rules import match_rule  # noqa: E402
from barum.vlm import get_vlm  # noqa: E402

sys.path.insert(0, "scripts")
import compare_ocr  # noqa: E402

_DEFAULT_LABEL_XLSX = Path("11st_probe_cosmetic/read_test/label_worksheet_combined.xlsx")
_BATCH_SIZE = 12


def collect_rule_violations(label_xlsx: Path) -> list[dict]:
    """정답셋에서 규칙이 위반으로 확정한 문장만 모은다. VLM 호출 없음(무료)."""
    key = compare_ocr.load_answer_key(label_xlsx=label_xlsx)
    out: list[dict] = []
    for nn, rows in key.items():
        for row in rows:
            sentence = row["sentence"]
            if not sentence:
                continue
            m = match_rule(sentence)
            if m is not None and m.outcome.value == "violation":
                out.append({"nn": nn, "text": sentence, "span": m.span, "label": row["judgment"]})
    return out


def run_prescreen(vlm, sentences: list[dict]) -> list[dict]:
    """RagJudge._prescreen과 같은 프롬프트·배치 방식이되, YES/NO를 전부 보존한다.

    RagJudge._prescreen()은 YES만 리턴하고 NO는 버려서(그게 원래 목적) 충돌 관측에
    못 쓴다. 그래서 같은 프롬프트로 직접 호출해 문장마다 claim(true/false)을 남긴다.
    과금 호출이라 재시도 없이, 실패한 배치는 실패로 기록하고 계속 진행한다.
    """
    results: list[dict] = []
    for start in range(0, len(sentences), _BATCH_SIZE):
        batch = sentences[start : start + _BATCH_SIZE]
        numbered = "\n".join(f"{start + j}. {s['text']}" for j, s in enumerate(batch))
        try:
            res = vlm.generate_json(PRESCREEN_PROMPT.format(items=numbered), [])
            raw = res.get("results", [])
        except Exception as e:
            print(f"    [skip] 배치 {start}~{start + len(batch) - 1}: {type(e).__name__}: {e}")
            for s in batch:
                results.append({**s, "prescreen_claim": None, "prescreen_failed": True})
            continue

        by_n = {}
        for item in raw:
            try:
                by_n[int(item["n"])] = item
            except (KeyError, ValueError, TypeError):
                continue

        for j, s in enumerate(batch):
            item = by_n.get(start + j)
            if item is None and len(raw) == len(batch):
                item = raw[j]
            claim = (item or {}).get("claim")
            results.append({**s, "prescreen_claim": bool(claim) if claim is not None else None,
                             "prescreen_failed": item is None})
    return results


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--label-file", default=str(_DEFAULT_LABEL_XLSX))
    ap.add_argument("--dry-run", action="store_true", help="VLM 안 부름. 대상 문장 개수만 출력")
    ap.add_argument("--provider", default="gemini")
    args = ap.parse_args()

    violations = collect_rule_violations(Path(args.label_file))
    print(f"규칙 위반 확정 문장: {len(violations)}건 (배치 {_BATCH_SIZE}개씩, "
          f"{-(-len(violations) // _BATCH_SIZE)}회 호출 예상)")
    for v in violations:
        print(f"  [{v['nn']}] span={v['span']!r} | {v['text'][:60]}")

    if args.dry_run or not violations:
        return

    vlm = get_vlm(args.provider)
    results = run_prescreen(vlm, violations)

    conflicts = [r for r in results if r["prescreen_claim"] is False]
    failed = [r for r in results if r["prescreen_failed"]]
    print(f"\n=== 결과 ===")
    print(f"규칙=위반 확정 {len(results)}건 중 prescreen=효능주장아님(충돌) {len(conflicts)}건, "
          f"실패(미판정) {len(failed)}건")
    if conflicts:
        print("\n충돌 문장 목록:")
        for c in conflicts:
            print(f"  [{c['nn']}] 규칙 span={c['span']!r} | {c['text'][:70]}")

    rate = len(conflicts) / len(results) * 100 if results else 0.0
    print(f"\n불일치율: {rate:.1f}% ({len(conflicts)}/{len(results)})")


if __name__ == "__main__":
    main()
