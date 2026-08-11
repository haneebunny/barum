"""cases.md 사례 추출(reference.cases) 유닛테스트 (순수 파싱).

    ./venv/bin/python -m pytest tests/test_cases_extract.py -q
"""

from barum.reference.cases import extract_cases


def test_extract_cases_parses_real_disposition_table():
    """§1 적발사례 표를 {text, violation, disposition, source} 리스트로 뽑는다."""
    cases = extract_cases()
    assert isinstance(cases, list) and len(cases) >= 8
    for c in cases:
        assert set(c) >= {"text", "violation", "disposition", "source"}
        assert c["text"]  # 문구는 비어 있지 않다

    # 실제 광고 카피가 담긴 사례가 있고, 위반유형·처분도 실린다.
    hit = next(c for c in cases if "트리플 특허" in c["text"])
    assert "T2" in hit["violation"]
    assert "광고업무정지" in hit["disposition"]
