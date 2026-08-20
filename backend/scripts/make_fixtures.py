"""프론트·디자이너용 샘플 CheckReport 픽스처 생성.

    ./venv/bin/python scripts/make_fixtures.py       # backend/fixtures/*.json 갱신

모델로 직접 조립해 덤프하므로 스키마 100% 유효하다. 실제 판정 호출(과금) 없이
계약 예시를 만든다. 값은 그럴듯한 화장품 광고 예시(실제 판정 결과 아님).
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for _p in (ROOT, ROOT / "src"):
    _sp = str(_p)
    if _sp not in sys.path:
        sys.path.insert(0, _sp)

from barum.models import (  # noqa: E402
    CheckReport,
    Finding,
    JudgmentFlag,
    Location,
    Summary,
    UnjudgedSentence,
    ViolationType,
)
from barum.reference.mapping import legal_basis_for, legal_basis_text_for  # noqa: E402

OUT_DIR = ROOT / "fixtures"


def _summary(region, n_sentences, findings, n_unjudged=0) -> Summary:
    """findings로부터 요약 집계를 만든다(파이프라인과 같은 규칙)."""
    counts: dict[str, int] = {}
    for f in findings:
        counts[f.violation_type.value] = counts.get(f.violation_type.value, 0) + 1
    n_violation = sum(1 for f in findings if f.flag == JudgmentFlag.violation)
    n_needs_review = sum(1 for f in findings if f.flag == JudgmentFlag.needs_review)
    return Summary(
        region=region,
        n_sentences=n_sentences,
        n_findings=len(findings),
        n_violation=n_violation,
        n_needs_review=n_needs_review,
        n_unjudged=n_unjudged,
        counts_by_type=counts,
    )


def image_case() -> CheckReport:
    """이미지 입력 케이스. location.tile·밴드 좌표 채워짐(원문 이미지 위 하이라이트용).

    문장 5개 중 3개 위반(1/2/5호), 1개 합법(finding 없음), 나머지도 합법.
    원본 1000x9000 상세페이지가 타일 2장(t00: y 0~1480, t01: y 1400~2900)으로 쪼개진 예시.
    같은 타일의 문장들은 같은 밴드를 공유한다(OCR이 문장 bbox를 안 주므로 타일 밴드가 최선).
    """
    findings = [
        Finding(
            span="멜라닌 생성을 억제해 미백에 도움",
            sentence="멜라닌 생성을 억제해 미백에 도움을 줍니다.",
            violation_type=ViolationType.type_2_functional_misperception,
            legal_basis=legal_basis_for(ViolationType.type_2_functional_misperception),
            legal_basis_text=legal_basis_text_for(ViolationType.type_2_functional_misperception),
            flag=JudgmentFlag.needs_review,  # 성분 정합 미확인 상태 시연
            explanation="미백은 기능성 심사·고시원료 확인이 필요한 표현이다. 심사 근거 없이 주장하면 기능성 오인. (전성분 미입력, 성분 정합 확인 못 함)",
            location=Location(
                tile="detail_000_t00.png", order=0,
                x_start=120, x_end=780,
                y_start=450, y_end=580, source_h=9000, source_w=1000,
            ),
        ),
        Finding(
            span="아토피 피부염을 완화하고 손상된 피부를 재생",
            sentence="아토피 피부염을 완화하고 손상된 피부를 재생합니다.",
            violation_type=ViolationType.type_1_drug_misperception,
            legal_basis=legal_basis_for(ViolationType.type_1_drug_misperception),
            legal_basis_text=legal_basis_text_for(ViolationType.type_1_drug_misperception),
            flag=JudgmentFlag.violation,
            explanation="질병(아토피)의 완화·재생은 의약품으로 오인될 수 있는 의학적 효능 표현이다.",
            location=Location(
                tile="detail_000_t01.png", order=2,
                x_start=80, x_end=920,
                y_start=1850, y_end=2020, source_h=9000, source_w=1000,
            ),
        ),
        Finding(
            span="시중 제품 대비 3배 빠른 흡수",
            sentence="시중 제품 대비 3배 빠른 흡수를 자랑합니다.",
            violation_type=ViolationType.type_5_deception,
            legal_basis=legal_basis_for(ViolationType.type_5_deception),
            legal_basis_text=legal_basis_text_for(ViolationType.type_5_deception),
            flag=JudgmentFlag.violation,
            explanation="객관적 근거 없는 비교 수치(3배)는 거짓·과장 광고에 해당할 소지가 있다.",
            location=Location(
                tile="detail_000_t01.png", order=3,
                x_start=220, x_end=780,
                y_start=2450, y_end=2600, source_h=9000, source_w=1000,
            ),
        ),
    ]
    # order 1, 4는 합법 문장(촉촉한 보습 등) = finding 없음. n_sentences=5.
    return CheckReport(
        findings=findings,
        unjudged=[],
        summary=_summary("KR", 5, findings),
    )


def text_case() -> CheckReport:
    """문구-only 입력 케이스. location.tile=null(붙여넣은 텍스트 스팬 하이라이트용)."""
    findings = [
        Finding(
            span="주름을 개선하는",
            sentence="매일 발라 주름을 개선하는 안티에이징 크림.",
            violation_type=ViolationType.type_2_functional_misperception,
            legal_basis=legal_basis_for(ViolationType.type_2_functional_misperception),
            legal_basis_text=legal_basis_text_for(ViolationType.type_2_functional_misperception),
            flag=JudgmentFlag.needs_review,
            explanation="주름개선은 기능성 화장품 심사가 필요한 표현이다. (전성분 미입력, 성분 정합 확인 못 함)",
            location=Location(tile=None, order=0),
        ),
        Finding(
            span="염증을 가라앉히고 상처를 치료",
            sentence="트러블로 인한 염증을 가라앉히고 상처를 치료합니다.",
            violation_type=ViolationType.type_1_drug_misperception,
            legal_basis=legal_basis_for(ViolationType.type_1_drug_misperception),
            legal_basis_text=legal_basis_text_for(ViolationType.type_1_drug_misperception),
            flag=JudgmentFlag.violation,
            explanation="염증 완화·상처 치료는 의약품으로 오인될 수 있는 의학적 효능 표현이다.",
            location=Location(tile=None, order=1),
        ),
    ]
    # order 2는 합법("가볍게 발리는 데일리 로션") = finding 없음. n_sentences=3.
    return CheckReport(
        findings=findings,
        unjudged=[],
        summary=_summary("KR", 3, findings),
    )


def unjudged_case() -> CheckReport:
    """미판정 모드. 일부 문장은 판정 실패로 unjudged에 남는다('재검사 필요' UI용)."""
    findings = [
        Finding(
            span="파워 수분 공급",
            sentence="콜라겐 함유로 파워 수분 공급.",
            violation_type=ViolationType.type_5_deception,
            legal_basis=legal_basis_for(ViolationType.type_5_deception),
            legal_basis_text=legal_basis_text_for(ViolationType.type_5_deception),
            flag=JudgmentFlag.violation,
            explanation="'파워'는 근거 없는 과장 수식으로 볼 소지가 있다.",
            location=Location(
                tile="detail_002_t00.png", order=0,
                y_start=0, y_end=1520, source_h=8000, source_w=1000,
            ),
        ),
    ]
    unjudged = [
        UnjudgedSentence(
            sentence="7가지 한방 추출물로 피부 진정에 탁월",
            location=Location(
                tile="detail_002_t00.png", order=1,
                y_start=0, y_end=1520, source_h=8000, source_w=1000,
            ),
        ),
        UnjudgedSentence(
            sentence="탄력 있는 피부로 가꿔주는 펩타이드 앰플",
            location=Location(
                tile="detail_002_t01.png", order=2,
                y_start=1440, y_end=2960, source_h=8000, source_w=1000,
            ),
        ),
    ]
    return CheckReport(
        findings=findings,
        unjudged=unjudged,
        summary=_summary("KR", 3, findings, n_unjudged=len(unjudged)),
    )


FIXTURES = {
    "check_report_image.json": image_case,
    "check_report_text.json": text_case,
    "check_report_with_unjudged.json": unjudged_case,
}


def main() -> None:
    OUT_DIR.mkdir(exist_ok=True)
    for name, builder in FIXTURES.items():
        report = builder()
        path = OUT_DIR / name
        path.write_text(
            json.dumps(report.model_dump(mode="json"), ensure_ascii=False, indent=2)
            + "\n",
            encoding="utf-8",
        )
        s = report.summary
        print(f"저장: {path.name}  (문장 {s.n_sentences}, 위반 {s.n_findings}, 미판정 {s.n_unjudged})")


if __name__ == "__main__":
    main()
