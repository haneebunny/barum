# -*- coding: utf-8 -*-
"""US 프리플라이트 OCR 전성분 폴백 배선 — 실제 파이프라인으로 스모크 확인.

VLM을 목킹하지 않는다(CLAUDE.md §E). 실제 이미지로 run_us_sunscreen_check()를
그대로 돌려서 "OCR로 뽑은 전성분이 진짜로 판정에 들어가는지" 확인한다.

    ./venv/bin/python scripts/us_ocr_ingredient_smoke.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for _p in (ROOT, ROOT / "src"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from barum.judge.us_sunscreen import USSunscreenJudge  # noqa: E402
from barum.pipeline import run_us_sunscreen_check  # noqa: E402
from barum.vlm import get_vlm  # noqa: E402

# 크롤 데이터는 gitignore라 이 워크트리엔 없다. 원본 트리 데이터를 그대로 읽는다.
IMAGE = (
    ROOT.parent.parent / "barum" / "backend"
    / "11st_probe_cosmetic" / "details" / "24500688" / "detail_010.jpg"
)


def main() -> None:
    vlm = get_vlm("gemini")
    image_bytes = IMAGE.read_bytes()

    print("=" * 70)
    print("케이스 1: 수동 입력 없음, 이미지에 전성분 패널 있음 → OCR 폴백 기대")
    print("=" * 70)
    report = run_us_sunscreen_check(
        ad_text="SPF50+ PA++++",
        image_bytes=image_bytes,
        image_filename="detail_010.jpg",
        vlm=vlm,
        judge=USSunscreenJudge(),
        ingredients=None,
        verbose=False,
    )
    for f in report.findings:
        print(f"  [{f.category.value}] {f.span!r}")
        print(f"    -> {f.explanation}")
    missing = [f for f in report.findings if f.category.value == "성분정보_확인불가"]
    print(f"\n'성분정보_확인불가' 지적 여부: {'있음 (폴백 실패)' if missing else '없음 (폴백 성공)'}")

    print("\n" + "=" * 70)
    print("케이스 2: 수동 입력 있음(드로메트리졸 포함) → 수동 입력이 이겨야 함")
    print("=" * 70)
    report2 = run_us_sunscreen_check(
        ad_text="SPF50+ PA++++",
        image_bytes=image_bytes,
        image_filename="detail_010.jpg",
        vlm=vlm,
        judge=USSunscreenJudge(),
        ingredients="정제수,드로메트리졸",
        verbose=False,
    )
    for f in report2.findings:
        print(f"  [{f.category.value}] {f.span!r}")
        print(f"    -> {f.explanation}")
    unapproved = [f for f in report2.findings if f.category.value == "미국_미승인_성분"]
    has_ocr_note = any("자동으로 읽어낸" in f.explanation for f in unapproved)
    print(f"\n미승인 성분(드로메트리졸) 지적: {'있음' if unapproved else '없음'}")
    print(f"OCR 자동추출 안내문 섞였는지: {'섞임 (버그, 수동입력인데 OCR 안내가 붙음)' if has_ocr_note else '안 섞임 (정상)'}")


if __name__ == "__main__":
    main()
