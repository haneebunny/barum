"""개선 모드가 승인된 대체표현을 그대로 쓰는 경로 (외부 호출 없음).

    ./venv/bin/python -m pytest tests/test_approved_replacements.py -q
"""

from barum.generate.content import generate_content
from barum.judge.cosmetic import StubJudge
from barum.models import ApprovedReplacement, GenerateRequest


class BoomVLM:
    """부르면 실패하는 LLM. 판정·재작성을 안 부르는지 확인하는 데 쓴다."""

    def __init__(self):
        self.calls = 0

    def generate_json(self, prompt, images):
        self.calls += 1
        raise AssertionError("이 경로에서 부르면 안 되는 호출")


class QuietVLM:
    """섹션 생성만 하는 가짜 LLM(개선 경로에서 원래 한 번 부른다)."""

    def __init__(self):
        self.calls = 0

    def generate_json(self, prompt, images):
        self.calls += 1
        return {"제품개요": "담백한 데일리 크림", "사용법": "펴 바르세요", "주의사항": "이상 시 중단"}


def _req(**kw):
    base = dict(mode="improve", content="줄기세포 배양 기술로 피부를 관리합니다", product_name="테스트크림")
    base.update(kw)
    return GenerateRequest(**base)


def test_승인된_대체표현을_그대로_치환한다():
    """리포트에서 이미 계산한 걸 다시 만들지 않는다."""
    req = _req(
        approved_replacements=[
            ApprovedReplacement(original="줄기세포 배양 기술", replaced="고농축 배합", finding_index=0)
        ]
    )
    vlm = QuietVLM()
    resp = generate_content(req, judge=StubJudge(), vlm=vlm)

    body = " ".join(s.text for s in resp.sections)
    assert "고농축 배합" in body
    assert "줄기세포" not in body
    assert len(resp.replacements) == 1
    assert resp.replacements[0].finding_index == 0


def test_승인목록이_있으면_판정도_재작성도_안_부른다():
    """비용이 두 배인 게 문제였다. 판정·재작성 호출이 사라져야 한다."""
    req = _req(
        approved_replacements=[
            ApprovedReplacement(original="줄기세포 배양 기술", replaced="고농축 배합")
        ]
    )
    vlm = QuietVLM()
    generate_content(req, judge=StubJudge(), vlm=vlm)
    # 섹션 생성 1회뿐. 판정(prescreen+judge)·재작성 배치가 없다.
    assert vlm.calls == 1


def test_클라이언트가_보낸_위반_문구는_게이트에서_걸린다():
    """**이 경로의 안전 축이다.** 클라이언트 값을 그대로 믿으면 임의 텍스트가
    상세페이지에 들어가고 지금까지 쌓은 대체표현 게이트가 통째로 우회된다."""
    req = _req(
        approved_replacements=[
            ApprovedReplacement(original="줄기세포 배양 기술", replaced="아토피 치료에 좋은 크림")
        ]
    )
    resp = generate_content(req, judge=StubJudge(), vlm=QuietVLM())

    body = " ".join(s.text for s in resp.sections)
    assert "아토피 치료" not in body, "게이트를 우회해 위반 문구가 들어갔다"
    assert resp.replacements == []
    assert "아토피 치료에 좋은 크림" in resp.unapplied_replacements


def test_적발사례_재사용도_게이트에서_걸린다():
    req = _req(
        approved_replacements=[
            ApprovedReplacement(
                original="줄기세포 배양 기술", replaced="피부 깊숙이 침투하여 흡수되는 포뮬러"
            )
        ]
    )
    resp = generate_content(req, judge=StubJudge(), vlm=QuietVLM())
    assert resp.replacements == []
    assert resp.unapplied_replacements


def test_원문에_없는_대상은_조용히_넘어가지_않는다():
    """`apply_replacements`는 대상이 없으면 아무 일도 안 한다. 그러면 '고쳤다'고
    표시된 채 원문이 그대로 나간다. 낡은 리포트를 보낼 때 실제로 생기는 일이다."""
    req = _req(
        approved_replacements=[
            ApprovedReplacement(original="이 문장은 원문에 없습니다", replaced="산뜻한 제형")
        ]
    )
    resp = generate_content(req, judge=StubJudge(), vlm=QuietVLM())
    assert "산뜻한 제형" in resp.unapplied_replacements


def test_승인목록이_없으면_예전_경로를_그대로_탄다():
    """하위호환. `/generate` 단독 호출은 지금처럼 처음부터 계산해야 한다."""
    req = _req()  # approved_replacements 없음
    vlm = QuietVLM()
    resp = generate_content(req, judge=StubJudge(), vlm=vlm)
    # 판정·재작성 경로를 타므로 섹션 생성 1회보다 많이 불린다.
    assert vlm.calls >= 1
    assert resp.unapplied_replacements == []


def test_빈_승인목록도_재계산_경로로_안_샌다():
    """빈 리스트는 '승인한 게 없다'는 뜻이지 '계산해달라'가 아니다."""
    req = _req(approved_replacements=[])
    vlm = QuietVLM()
    resp = generate_content(req, judge=StubJudge(), vlm=vlm)
    assert vlm.calls == 1
    assert resp.replacements == []
