"""검수기 순수 로직 유닛테스트 (외부 의존 없음).

    venv/bin/python -m pytest tests/test_validate.py -q
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import validate_holdout as V  # noqa: E402


def row(**kw):
    """검사에 필요한 최소 필드를 채운 행 하나."""
    base = dict(id="A001", product_id="p1", sentence="체지방 감소에 도움을 줍니다",
                product_type="일반식품", certified_function="", label="",
                is_cross_check="N", hint="3호_건기식오인")
    base.update(kw)
    return base


def run(check, rows, tag="A"):
    rep = V.Report()
    check(rows, tag, rep)
    return rep.items


# ── label 유출 ──
def test_label_blank_ok():
    assert run(V.check_label_blank, [row(label="")]) == []


def test_label_leak_is_error():
    items = run(V.check_label_blank, [row(label="1호_질병표방")])
    assert items and items[0][0] == V.ERROR and items[0][1] == "label-leak"


# ── 문장 품질 ──
def test_fragment_flagged():
    items = run(V.check_sentence_quality, [row(sentence="분자 구조가 커서 흡수되지")])
    assert any(c == "fragment" for _, c, _ in items)


def test_english_flagged():
    items = run(V.check_sentence_quality, [row(sentence="Qi deficiency obesity type")])
    assert any(c == "not-korean" for _, c, _ in items)


def test_too_short_flagged():
    items = run(V.check_sentence_quality, [row(sentence="0지방")])
    assert any(c == "too-short" for _, c, _ in items)


def test_clean_sentence_passes():
    assert run(V.check_sentence_quality, [row(sentence="체지방 감소에 도움을 줍니다")]) == []


# ── 필수칸 ──
def test_missing_required_is_error():
    items = run(V.check_required, [row(product_type="")])
    assert items and items[0][0] == V.ERROR


# ── id / 교차검증 ──
def test_shared_row_needs_cross_flag():
    items = run(V.check_id_scheme, [row(id="S001", is_cross_check="N")])
    assert any(c == "cross-flag" for _, c, _ in items)


def test_unique_row_must_not_be_cross():
    items = run(V.check_id_scheme, [row(id="A005", is_cross_check="Y")])
    assert any(c == "cross-flag" for _, c, _ in items)


def test_id_scheme_ok():
    assert run(V.check_id_scheme, [row(id="S001", is_cross_check="Y"),
                                   row(id="A001", is_cross_check="N")]) == []


# ── product_type 모순 ──
def test_certified_but_general_food_warns():
    items = run(V.check_product_type,
                [row(product_type="일반식품", certified_function="간 건강에 도움을 줄 수 있음")])
    assert any(c == "type-conflict" for _, c, _ in items)


# ── 중복 / 공통블록 (여러 시트) ──
def test_duplicate_non_shared_is_error():
    rep = V.Report()
    sheets = {"A": [row(id="A001", sentence="붓기 제거에 좋아요")],
              "B": [row(id="B001", sentence="붓기 제거에 좋아요")]}
    V.check_duplicates(sheets, rep)
    assert any(c == "dup-sentence" for _, c, _ in rep.items)


def test_shared_block_may_repeat():
    rep = V.Report()
    sheets = {"A": [row(id="S001", sentence="같은 문장", is_cross_check="Y")],
              "B": [row(id="S001", sentence="같은 문장", is_cross_check="Y")]}
    V.check_duplicates(sheets, rep)
    assert rep.items == []  # 공통행 중복은 정상


def test_shared_block_mismatch_is_error():
    rep = V.Report()
    sheets = {"A": [row(id="S001", sentence="문장 하나")],
              "B": [row(id="S001", sentence="다른 문장 둘")]}
    V.check_shared_block(sheets, rep)
    assert any(c == "shared-mismatch" for _, c, _ in rep.items)


# ── 쿼터 ──
def test_quota_shortfall_warns():
    rep = V.Report()
    sheets = {"A": [row(hint="2호_의약품오인")]}
    V.check_quota(sheets, rep)
    assert any(c == "quota" for _, c, _ in rep.items)
