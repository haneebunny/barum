"""이미지 생성 사칭 필터(reference.impersonation) 유닛테스트 (순수, FR-13).

    ./venv/bin/python -m pytest tests/test_impersonation.py -q
"""

from barum.reference.impersonation import check_impersonation


def test_rejects_doctor_impersonation():
    allowed, reason = check_impersonation("흰 가운 입은 의사가 제품을 추천하는 이미지")
    assert allowed is False
    assert reason and "의사" in reason


def test_rejects_clinic_scene():
    allowed, reason = check_impersonation("피부과에서 전문가가 시술하는 장면")
    assert allowed is False
    assert reason


def test_allows_clean_product_shot():
    allowed, reason = check_impersonation("깨끗한 파스텔 배경에 놓인 화장품 용기 사진")
    assert allowed is True
    assert reason is None
