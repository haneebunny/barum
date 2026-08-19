"""레이아웃 레퍼런스 로더·종류추측 유닛테스트 (순수 로직, 외부 의존 없음)."""

from barum.reference.layout_references import (
    infer_product_type,
    load_layout_references,
    load_layout_vocabulary,
    select_references,
)


def test_레퍼런스_전부_로드되고_스키마가_맞는다():
    refs = load_layout_references()
    assert len(refs) == 8
    for ref in refs:
        assert ref["source"]["brand"]
        assert ref["product_type"]
        assert ref["modules"]
        for module in ref["modules"]:
            assert module["kind"]
            assert module["purpose"]
            assert isinstance(module["has_claim_risk"], bool)


def test_상품명에서_종류를_추측한다():
    assert infer_product_type("아누아 어성초 77 수딩 토너") == "토너"
    assert infer_product_type("설화수 자정앰플세럼") == "세럼"
    assert infer_product_type("제로이드 인텐시브 크림") == "크림"


def test_앰플과_에센스는_세럼으로_묶인다():
    # 홀리추얼 앰플이 레퍼런스에 product_type="세럼"으로 적재돼 있는 근거를 따른다.
    assert infer_product_type("홀리추얼 리디파이닝 앰플") == "세럼"
    assert infer_product_type("어떤브랜드 에센스") == "세럼"


def test_종류를_못찾으면_None을_낸다():
    # 브랜드명만 있고 종류 단어가 없는 경우. 생성이 막히면 안 되고 폴백 신호여야 한다.
    assert infer_product_type("아누아") is None
    assert infer_product_type(None) is None
    assert infer_product_type("") is None


def test_매핑에_없는_종류는_억지로_끼워맞추지_않는다():
    assert infer_product_type("어떤브랜드 바디로션") is None


def test_종류가_맞는_레퍼런스만_고른다():
    refs = select_references("토너")
    assert refs
    assert all(r["product_type"] == "토너" for r in refs)


def test_모듈_많은_레퍼런스가_앞에_온다():
    # 미완결 레퍼런스(라로슈포제 1모듈)가 퓨샷 앞자리를 차지하면 안 된다.
    refs = select_references("크림")
    counts = [len(r["modules"]) for r in refs]
    assert counts == sorted(counts, reverse=True)


def test_종류를_못정해도_스킨케어_레퍼런스로_폴백한다():
    # 예시가 아예 없는 것보다 대충이라도 있는 편이 낫다(하니 확정).
    assert select_references(None)
    assert select_references("로션")


def test_폴백도_모듈_많은_레퍼런스가_앞에_온다():
    counts = [len(r["modules"]) for r in select_references(None)]
    assert counts == sorted(counts, reverse=True)


def test_limit으로_퓨샷_개수를_제한한다():
    assert len(select_references("세럼", limit=2)) == 2


# ── 공용 어휘집 (2026-08-19, PR #181) ──


def test_vocabulary_파일은_레퍼런스_로더에_안_섞인다():
    """_vocabulary.json은 modules가 없어서 섞이면 퓨샷 정렬·개수가 흔들린다."""
    refs = load_layout_references()
    assert all("modules" in r and r["modules"] for r in refs)


def test_vocabulary가_layout_type_12종_카탈로그를_담고_있다():
    vocab = load_layout_vocabulary()
    assert len(vocab["layout_types"]) == 12
    assert "hero_fullbleed" in vocab["layout_types"]
    assert "table_info" in vocab["layout_types"]


def test_vocabulary가_category_base_tone을_담고_있다():
    vocab = load_layout_vocabulary()
    for category in ("세럼", "토너", "크림", "앰플"):
        assert "hue_direction" in vocab["category_base_tone"][category]
