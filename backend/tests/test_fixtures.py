"""샘플 픽스처가 CheckReport 계약을 지키는지 검증(외부 의존 없음).

픽스처는 프론트·디자이너의 계약 근거다. 모델이 바뀌어 픽스처가 어긋나면 여기서 잡는다.

    venv/bin/python -m pytest tests/test_fixtures.py -q
"""

import json
from pathlib import Path

import pytest

from barum.models import CheckReport

FIX_DIR = Path(__file__).resolve().parents[1] / "fixtures"
FIXTURES = sorted(FIX_DIR.glob("check_report_*.json"))


def test_fixtures_exist():
    assert FIXTURES, "픽스처가 없다. scripts/make_fixtures.py를 돌릴 것."


@pytest.mark.parametrize("path", FIXTURES, ids=lambda p: p.name)
def test_fixture_matches_contract(path: Path):
    """각 픽스처가 CheckReport로 파싱되고 요약 집계가 findings와 맞는다."""
    data = json.loads(path.read_text(encoding="utf-8"))
    report = CheckReport.model_validate(data)

    assert report.summary.n_findings == len(report.findings)
    assert report.summary.n_unjudged == len(report.unjudged)
    recount: dict[str, int] = {}
    for f in report.findings:
        recount[f.violation_type.value] = recount.get(f.violation_type.value, 0) + 1
    assert report.summary.counts_by_type == recount


def test_covers_both_input_modes():
    """이미지 케이스(tile 채움)와 텍스트 케이스(tile null) 둘 다 있다."""
    names = {p.name for p in FIXTURES}
    assert "check_report_image.json" in names
    assert "check_report_text.json" in names

    img = CheckReport.model_validate(
        json.loads((FIX_DIR / "check_report_image.json").read_text(encoding="utf-8"))
    )
    txt = CheckReport.model_validate(
        json.loads((FIX_DIR / "check_report_text.json").read_text(encoding="utf-8"))
    )
    assert all(f.location.tile for f in img.findings)  # 이미지: 타일 있음
    assert all(f.location.tile is None for f in txt.findings)  # 텍스트: 타일 없음
