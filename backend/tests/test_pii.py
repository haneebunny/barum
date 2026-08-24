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


# ── 구조화 필드까지 훑는지 (2026-08-24) ─────────────────────────────────────
#
# `_strip_pii`가 `Section.text`만 훑던 시절엔 사업자 입력이 전부 문장으로 합쳐져서
# 그걸로 충분했다. 표 행(2026-08-23)·실증자료(2026-08-24)를 구조화해 싣기 시작하면서
# 마스킹을 안 거치는 샛길이 생겼다. 자유입력 필드라 연락처가 실제로 들어올 수 있다.


def _strip(sections):
    from barum.generate.content import _strip_pii

    return _strip_pii(sections)


def test_실증자료_note의_연락처도_마스킹된다():
    from barum.models import ClinicalEvidence, Section

    sec = Section(
        kind="실증자료",
        text="다크스팟 개선 87%",
        source="clinical_evidence",
        clinical_stat=ClinicalEvidence(
            claim="다크스팟 개선",
            value="87%",
            institution="유어랩",
            note="피험자 20명, 문의 lab@yourlab.co.kr",
        ),
    )
    cleaned, kinds = _strip([sec])
    assert "lab@yourlab.co.kr" not in cleaned[0].clinical_stat.note
    assert "이메일" in kinds


def test_전성분_표_행의_전화번호도_마스킹된다():
    from barum.models import Section, TableRow

    sec = Section(
        kind="전성분",
        text="",
        source="full_ingredient",
        table_rows=[
            TableRow(label="", value="나이아신아마이드"),
            TableRow(label="문의", value="010-9876-5432"),
        ],
    )
    cleaned, kinds = _strip([sec])
    values = [r.value for r in cleaned[0].table_rows]
    assert "010-9876-5432" not in values
    assert "나이아신아마이드" in values, "PII가 아닌 값은 그대로 둬야 한다"
    assert "전화번호" in kinds


def test_수치는_마스킹에_안_걸린다():
    """claim·value까지 훑지만 PII 패턴에 걸릴 수 없는 값이라 그대로 남아야 한다."""
    from barum.models import ClinicalEvidence, Section

    sec = Section(
        kind="실증자료",
        text="x",
        source="clinical_evidence",
        clinical_stat=ClinicalEvidence(claim="피부결 개선", value="4주 후 2.1배"),
    )
    cleaned, _ = _strip([sec])
    assert cleaned[0].clinical_stat.value == "4주 후 2.1배"
    assert cleaned[0].clinical_stat.claim == "피부결 개선"


def test_원본_섹션을_바꾸지_않는다():
    """호출자가 원본을 계속 들고 있다. 제자리 수정하면 조용히 새는 곳이 생긴다."""
    from barum.models import ClinicalEvidence, Section

    stat = ClinicalEvidence(claim="개선", value="1%", note="문의 lab@yourlab.co.kr")
    sec = Section(kind="실증자료", text="x", source="clinical_evidence", clinical_stat=stat)
    _strip([sec])
    assert sec.clinical_stat.note == "문의 lab@yourlab.co.kr"


def test_구조화_필드가_없으면_같은_객체를_그대로_쓴다():
    """PII가 없는 섹션까지 매번 복사본을 만들 이유가 없다."""
    from barum.models import Section

    sec = Section(kind="제품개요", text="산뜻한 사용감", source="llm")
    cleaned, kinds = _strip([sec])
    assert cleaned[0] is sec
    assert not kinds
