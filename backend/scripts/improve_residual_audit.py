"""개선(improve) 결과물에 위반이 얼마나 남는지 재고, 남은 이유를 분류한다.

왜 재나. `_recheck`가 "재검증 실패"를 보고만 하고 재생성은 안 한다. 그 층을 넣을지
정하려면 **실제로 몇 건이 남는지**부터 알아야 한다. 남는 게 0건이면 재시도 층 자체가
필요 없고, 남으면 그 성격(제품명·유통 채널처럼 구조적으로 못 고치는 것인지)에 따라
설계가 달라진다.

남은 위반을 세 갈래로 나눈다.
  구조적    제안 자체를 안 하는 문구(제품명·유통 채널). 재시도해도 안 고쳐진다
  후보없음  조건표에도 LLM에도 대체 문구가 없었다
  치환실패  대체표현은 만들었는데 원문에서 못 찾아 바뀌지 않았다

**과금 호출이다**(개선 1회 = 판정 + 대체표현 + 재검증).

사용:
    cd backend && venv/bin/python scripts/improve_residual_audit.py
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, "src")

from barum.generate.content import generate_content  # noqa: E402
from barum.generate.replace import apply_replacements, build_replacements  # noqa: E402
from barum.judge.cosmetic import RagJudge  # noqa: E402
from barum.models import GenerateRequest  # noqa: E402
from barum.pipeline import run_check  # noqa: E402
from barum.vlm import get_vlm  # noqa: E402

# 시연에서 위반이 그대로 남았던 본문(팀장 화면, 2026-08-23).
_DEMO = """YOURBERRY (유어베리) 유어베리 글로우 리제너레이션 세럼
줄기세포 배양 기술 안티에이징
세포재생의 시작 / 피부 재생 솔루션
손상된 피부 세포를 빠르게 재생하여
진피층까지 침투하여
콜라겐 밀도 38% 증가 (4주 사용시)
전국 약국 오프라인매장 입점!"""


def main() -> int:
    content = _DEMO if len(sys.argv) < 2 else Path(sys.argv[1]).read_text(encoding="utf-8")
    vlm = get_vlm("openai")
    judge = RagJudge(vlm)

    before = run_check("KR", content, None, None, None, judge)
    print(f"원본 지적 {len(before.findings)}건")
    for f in before.findings:
        print(f"  [{f.source}] {f.span} — {f.sentence[:44]}")

    reps = build_replacements(before.findings, rewriter=vlm)
    fixed = apply_replacements(content, reps)
    print(f"\n대체표현 {len(reps)}/{len(before.findings)}건 생성")

    after = run_check("KR", fixed, None, None, None, judge)
    print(f"\n개선 후 지적 {len(after.findings)}건")

    # 남은 위반의 원인 분류.
    rep_by_index = {r.finding_index: r for r in reps}
    residual = []
    for f in after.findings:
        cause = "새로 생김"
        for i, orig in enumerate(before.findings):
            if orig.span != f.span:
                continue
            if i not in rep_by_index:
                cause = "구조적/후보없음 (제안 자체를 안 함)"
            elif rep_by_index[i].original not in content:
                cause = "치환실패 (원문에서 못 찾음)"
            else:
                cause = "치환했는데 다시 걸림"
            break
        residual.append({"span": f.span, "sentence": f.sentence[:60], "cause": cause})
        print(f"  {f.span:10} ← {cause}")

    result = {
        "findings_before": len(before.findings),
        "replacements": len(reps),
        "findings_after": len(after.findings),
        "residual": residual,
        "improved_text": fixed,
    }
    Path("/tmp/improve_residual.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("\n저장: /tmp/improve_residual.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
