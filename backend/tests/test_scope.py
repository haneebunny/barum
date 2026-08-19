"""상품 단위 대상외 판단(reference.scope) 유닛테스트. 순수 로직(키워드 매칭)."""

from barum.reference.scope import check_product_scope


def test_짜개_키워드가_있으면_대상외다():
    texts = ["편한생활연구소 화장품 1g도 안 남겨 키트", "구성 스쿱 3개 + 짜개 1개"]
    in_scope, kw = check_product_scope(texts)
    assert in_scope is False
    assert kw == "짜개"


def test_짜개_단어가_없는_문장만_있어도_상품_전체가_대상외로_잡힌다():
    """실제 사고 재현: "짜개"가 없는 문장("흠집이 생기지 않아요")만 봐도,
    같은 요청 안에 "짜개"가 든 다른 문장이 있으면 상품 전체가 대상외로 잡혀야 한다."""
    texts = ["아무리 긁어도 흠집이 생기지 않아요", "짜개를 튜브 끝에 끼우고 돌리기만 하면"]
    in_scope, kw = check_product_scope(texts)
    assert in_scope is False


def test_실리콘_퍼프_상품도_대상외다():
    texts = ["실리콘 퍼프", "손가락 스트랩으로 더 안정적이고 편안한 사용감"]
    in_scope, kw = check_product_scope(texts)
    assert in_scope is False
    assert kw == "실리콘 퍼프"


def test_상품명에_화장품이라는_단어가_있어도_도구면_대상외다():
    """제품명이 "...화장품 1g도 안 남겨 키트"라도(문자열에 "화장품" 포함) 도구면 대상외.

    상품명 문자열 매칭만으론 못 거른다는 cosmetic_scope.md의 경고를 코드로 확인한다.
    본문에 "짜개"·"스쿱"이 있어야 잡힌다 — 제목 문장 하나만으로는(도구 키워드가 없으면)
    안 잡힌다. `product_name` 자체를 "화장품"으로 문자열 매칭하는 방식이 아니라는 뜻이다.
    """
    in_scope, _ = check_product_scope([
        "제품명 편한생활연구소 화장품 1g도 안 남겨 키트",
        "구성 스쿱 3개 + 짜개 1개",
    ])
    assert in_scope is False


def test_상품명_문장_하나만으로는_도구_키워드가_없으면_안_잡힌다():
    """이미지15 실사례: 제품명·브랜드 소개 문장만 있고 "짜개"·"스쿱"이 그 안에 없으면
    이 게이트 단독으로는 못 잡는다(같은 상품의 다른 이미지엔 도구 키워드가 있지만,
    이 함수는 한 번의 요청에 들어온 텍스트만 본다). 놓치는 게 아니라 애초에 이
    게이트의 한계로 명시해 둔다(대신 짜개·스쿱이 실제로 언급되는 이미지는 잡힌다)."""
    in_scope, kw = check_product_scope(["편한생활연구소는 특허청에 상표 등록된 대한민국 브랜드입니다."])
    assert in_scope is True
    assert kw is None


def test_퍼프만_단독으로_있으면_대상외로_안_잡힌다():
    """정답셋 21번(진짜 화장품)의 실사례: "제품을... 퍼프에 적당히 덜어..."는 화장품이어야 한다.

    "퍼프" 단독은 오탐 위험이 확인돼(cosmetic_scope.md) 채택하지 않았고,
    "실리콘 퍼프"(2단어 붙임)만 썼다. 이 회귀를 고정한다.
    """
    in_scope, kw = check_product_scope(["제품을 손이나 천, 퍼프에 적당히 덜어 부드러운 거품으로"])
    assert in_scope is True
    assert kw is None


def test_일반_화장품_문장은_화장품으로_본다():
    texts = ["미백ㆍ주름개선 이중기능성 화장품", "피부 진정에 도움을 주는 세럼"]
    in_scope, kw = check_product_scope(texts)
    assert in_scope is True
    assert kw is None


def test_빈_텍스트는_화장품으로_본다():
    """모르면 화장품 쪽(recall 우선). 빈 요청 자체가 대상외로 오판되면 안 된다."""
    assert check_product_scope([]) == (True, None)
    assert check_product_scope(["", "   "]) == (True, None)


def test_공백이_있어도_스쿱_키워드가_잡힌다():
    # 정규화가 공백을 지우므로 띄어쓰기가 달라도 걸려야 한다.
    in_scope, kw = check_product_scope(["구성 스 쿱 3개"])
    assert in_scope is False
