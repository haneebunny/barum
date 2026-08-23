"""대체표현 게이트 회귀 감사. **API 비용 0.**

우리가 사업자에게 **제안하는** 문구에 위반 표현이 섞이는 사고가 반복됐다. 그때마다
원인이 달랐다.

  2026-08-22 #250  `줄기세포`      규칙집에 있는 단어인데 게이트를 안 태워서
  2026-08-23       `깊숙이 침투`   규칙집에 없는 표현이라 게이트가 못 잡아서

두 번째가 중요하다. **"규칙집에 없어서 못 잡았다"는 답이 안 된다.** 판정에서 놓치면
"못 잡았다"지만, 제안에서 놓치면 **우리가 위반을 권하는 것**이다. 그래서 제안 경로엔
판정과 다른 기준의 층을 얹었고, 이 스크립트가 그 층들이 실제로 막는지 지킨다.

과거 사고를 회귀 목록으로 박아 두는 게 목적이다. 같은 클래스가 다시 나오면 여기서 걸린다.

사용:
    cd backend && venv/bin/python scripts/suggestion_gate_audit.py
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, "src")

from barum.generate.replace import _accept  # noqa: E402

# 절대 제안으로 나가면 안 되는 문구. **과거 사고와 팩 근거에서 뽑았다.**
_MUST_BLOCK = [
    # 2026-08-22 #250 — 규칙집에 있는데 게이트를 안 태워 나갔다.
    ("줄기세포 배양액 함유", "5호 인체유래성분 오인, judge_rules 등재"),
    ("줄기세포 엑소좀으로 통증없는 피부 재생", "cases.md 적발 사례"),
    # 2026-08-23 — 규칙집에 없어 게이트를 통과했다. 정작 cases.md엔 세 건 있었다.
    ("피부 깊숙이 침투하여 흡수되는 포뮬러", "cases.md:121 적발, 침투 메커니즘"),
    ("피부 깊숙한 층까지 침투해 턴오버를 앞당깁니다", "cases.md:50 적발"),
    ("표피층 깊숙이 앰플의 좋은 성분이 전달됩니다", "cases.md:69 적발"),
    ("진피층까지 전달되는 앰플", "type_1:18 생리구조 영향 표현"),
    # 규칙집 등재 위반 표현.
    ("손상된 피부 세포를 빠르게 재생합니다", "1호 세포재생"),
    ("아토피 개선에 도움을 줍니다", "1호 질병명"),
]

# 반대로 **막히면 안 되는** 문구. 게이트가 과하게 조이는 걸 잡는다.
# 특히 실증 수치는 지우면 안 된다 — 사업자가 실제로 측정한 값일 수 있다(팀 결정).
_MUST_PASS = [
    ("4주 사용 시 콜라겐 밀도 38% 증가 (인체적용시험 결과)", "실증 수치 보존"),
    ("건조한 피부에 수분을 채워 촉촉하게 가꿔줍니다.", "일반 보습 서술"),
    ("피부에 생기와 활력을 더해준다.", "조건표 계열 표현"),
    ("자극 완화", "조건표 후보"),
    ("산뜻하게 발리는 제형", "사용감 서술"),
]


def audit() -> dict:
    blocked_ok, leaked = [], []
    for text, why in _MUST_BLOCK:
        (blocked_ok if not _accept(text) else leaked).append({"text": text, "why": why})

    passed_ok, over_blocked = [], []
    for text, why in _MUST_PASS:
        (passed_ok if _accept(text) else over_blocked).append({"text": text, "why": why})

    return {
        "must_block_total": len(_MUST_BLOCK),
        "leaked": leaked,
        "must_pass_total": len(_MUST_PASS),
        "over_blocked": over_blocked,
        "ok": not leaked and not over_blocked,
    }


def main() -> int:
    r = audit()
    print(f"막아야 할 문구 {r['must_block_total']}건 중 새어나감: {len(r['leaked'])}건")
    for x in r["leaked"]:
        print(f"  ❌ {x['text']}  ({x['why']})")
    print(f"통과해야 할 문구 {r['must_pass_total']}건 중 과차단: {len(r['over_blocked'])}건")
    for x in r["over_blocked"]:
        print(f"  ❌ {x['text']}  ({x['why']})")
    print("\n결과:", "통과" if r["ok"] else "실패")
    if "--json" in sys.argv:
        print(json.dumps(r, ensure_ascii=False, indent=2))
    return 0 if r["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
