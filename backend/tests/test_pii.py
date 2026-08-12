"""PII 제거(reference.pii) 유닛테스트 (순수 정규식, 외부 의존 없음).

    ./venv/bin/python -m pytest tests/test_pii.py -q
"""

from barum.reference.pii import remove_pii


def test_removes_email():
    cleaned, kinds = remove_pii("문의는 hello.user@example.co.kr 로 주세요")
    assert "hello.user@example.co.kr" not in cleaned
    assert "이메일" in kinds


def test_removes_phone():
    cleaned, kinds = remove_pii("연락처 010-1234-5678 입니다")
    assert "010-1234-5678" not in cleaned
    assert "전화번호" in kinds


def test_removes_rrn():
    cleaned, kinds = remove_pii("주민번호 901201-1234567 확인")
    assert "901201-1234567" not in cleaned
    assert "주민등록번호" in kinds


def test_clean_text_unchanged_no_pii():
    cleaned, kinds = remove_pii("촉촉한 보습감의 데일리 크림")
    assert cleaned == "촉촉한 보습감의 데일리 크림"
    assert kinds == []


def test_removes_multiple_kinds():
    cleaned, kinds = remove_pii("a@b.com / 02-123-4567 문의")
    assert "a@b.com" not in cleaned and "02-123-4567" not in cleaned
    assert set(kinds) == {"이메일", "전화번호"}
