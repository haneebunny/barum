"""`/check` 단계별 소요시간 실측 (게이트 도입 전 베이스라인).

베베가 판정 경로에 근거 검증 게이트를 넣는 중이라, 그 전에 지금 값을 재둔다.
끝난 뒤에 재면 "게이트 때문에 느려진 건지 원래 느렸던 건지" 못 가린다(PM 지시,
2026-08-23). 실제 API 엔드포인트를 거치지 않고 `run_check()`를 직접 호출한다
(HTTP·이미지 캐시 레이어를 건너뛰어 파이프라인 자체 시간만 잰다 — 캐시를 거치면
같은 이미지 재실행이 순식간에 끝나 반복측정이 무의미해진다).

    ./venv/bin/python scripts/measure_check_latency.py --reps 3

barum 코드는 건드리지 않는다 — 단계 경계는 함수를 몽키패치해서 재고, 끝나면
그대로 버린다(디스크에 아무 변경도 안 남음). 베베가 같은 파일을 만지는 중이라
소스에 임시 로깅을 심는 것 자체를 피했다(PM 지시).
"""
import argparse
import functools
import statistics
import sys
import time
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for _p in (ROOT, ROOT / "src"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from barum.api.app import _build_judge, _replacement_rewriter  # noqa: E402
from barum.pipeline import run_check  # noqa: E402
from barum.vlm import get_vlm  # noqa: E402
import barum.pipeline as pipeline_mod  # noqa: E402
import barum.judge.cosmetic as cosmetic_mod  # noqa: E402
import os  # noqa: E402

IMAGES = {
    "세럼": ROOT / "data" / "demo" / "yourberry_serum_detail.png",
    "선크림": ROOT / "data" / "demo" / "yourberry_sunscreen_detail.png",
}

_stage_seconds: dict[str, float] = defaultdict(float)


def _timed(stage: str):
    """함수를 감싸 호출마다 걸린 시간을 `_stage_seconds[stage]`에 누적한다.

    한 실행(run_check 한 번) 안에서 여러 번 불리는 함수(예: 문장마다 도는 규칙
    매칭)는 합산된다 — run_check 호출 전에 `_stage_seconds.clear()`로 리셋한다.
    """

    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            t0 = time.perf_counter()
            try:
                return fn(*args, **kwargs)
            finally:
                _stage_seconds[stage] += time.perf_counter() - t0

        return wrapper

    return decorator


def _install_patches() -> None:
    """barum 소스는 그대로 두고, 이미 로드된 모듈 객체의 속성만 런타임에 바꿔친다.

    `_ocr_image`·`_verify_functional_evidence`·`_build_replacements_for_report`는
    pipeline.py 안에서 같은 모듈 전역으로 호출되므로 모듈 속성 패치가 그대로 먹는다.
    `match_all_rules`는 cosmetic.py가 `from ... import`로 자기 네임스페이스에 복사해 둔
    이름이라, 원본 모듈이 아니라 cosmetic 모듈 쪽 이름을 패치해야 한다.
    """
    pipeline_mod._ocr_image = _timed("OCR")(pipeline_mod._ocr_image)
    pipeline_mod._verify_functional_evidence = _timed("증빙검증")(
        pipeline_mod._verify_functional_evidence
    )
    pipeline_mod._build_replacements_for_report = _timed("대체표현배치")(
        pipeline_mod._build_replacements_for_report
    )
    cosmetic_mod.match_all_rules = _timed("규칙")(cosmetic_mod.match_all_rules)
    cosmetic_mod.RagJudge._prescreen = _timed("1차필터")(cosmetic_mod.RagJudge._prescreen)
    cosmetic_mod.PromptJudge.judge = _timed("RAG판정")(cosmetic_mod.PromptJudge.judge)


def _run_once(image_bytes: bytes, filename: str) -> tuple[float, dict[str, float], int]:
    """run_check 한 번을 실제 프로덕션과 같은 방식으로 구성해 돌리고 (총시간, 단계별시간, findings수)를 낸다."""
    _stage_seconds.clear()
    ocr_vlm = get_vlm(os.environ.get("OCR_PROVIDER", "gemini"))
    judge = _build_judge()
    rewriter = _replacement_rewriter()

    t0 = time.perf_counter()
    report = run_check(
        region="KR",
        ad_text=None,
        image_bytes=image_bytes,
        image_filename=filename,
        vlm=ocr_vlm,
        judge=judge,
        rewriter=rewriter,
    )
    total = time.perf_counter() - t0
    return total, dict(_stage_seconds), len(report.findings)


def _fmt_range(values: list[float]) -> str:
    if len(values) == 1:
        return f"{values[0]:.1f}초"
    return (
        f"평균 {statistics.mean(values):.1f}초 · "
        f"범위 {min(values):.1f}~{max(values):.1f}초 (개별: {', '.join(f'{v:.1f}' for v in values)})"
    )


def main(reps: int, out_path: Path, title: str) -> None:
    for label, path in IMAGES.items():
        if not path.exists():
            print(f"[경고] {label} 데모 이미지가 없다: {path}")
    _install_patches()

    all_runs: dict[str, list[dict]] = defaultdict(list)
    for label, path in IMAGES.items():
        if not path.exists():
            continue
        image_bytes = path.read_bytes()
        print(f"\n=== {label} ({path.name}) × {reps}회 ===", flush=True)
        for i in range(1, reps + 1):
            total, stages, n_findings = _run_once(image_bytes, path.name)
            stage_str = " / ".join(f"{k} {v:.1f}s" for k, v in stages.items())
            print(f"  [{i}/{reps}] 총 {total:.1f}초 (findings {n_findings}건) — {stage_str}", flush=True)
            all_runs[label].append({"total": total, "stages": stages, "n_findings": n_findings})

    print("\n\n=== 요약 ===")
    lines = [f"# {title}", ""]
    lines.append("PM 지시(2026-08-23): 베베가 판정 경로에 근거 검증 게이트를 넣기 전 값. "
                  "게이트 도입 후 재측정해 이 문서와 비교하는 게 목적.")
    lines.append("")
    lines.append("**방법**: `/check` HTTP 엔드포인트가 아니라 `run_check()`를 직접 호출(캐시·HTTP 오버헤드 배제, "
                  "실제 프로덕션과 동일하게 매 회 `_build_judge()`·`_replacement_rewriter()`를 새로 구성). "
                  "product_name·ingredients는 안 줌(단순 베이스라인). "
                  "실행 편차가 있어([[barum-vlm-run-variance]]) 이미지당 반복 측정, 1회 값 단정 안 함.")
    lines.append("")

    for label, runs in all_runs.items():
        totals = [r["total"] for r in runs]
        stage_keys = sorted({k for r in runs for k in r["stages"]})
        lines.append(f"## {label} ({IMAGES[label].name})")
        lines.append("")
        lines.append(f"- **총 소요**: {_fmt_range(totals)}")
        lines.append(f"- findings 개수(회차별): {', '.join(str(r['n_findings']) for r in runs)}건")
        lines.append("")
        lines.append("| 단계 | " + " | ".join(f"{i}회차" for i in range(1, len(runs) + 1)) + " | 평균 |")
        lines.append("|---|" + "---|" * (len(runs) + 1))
        for key in stage_keys:
            vals = [r["stages"].get(key, 0.0) for r in runs]
            row = " | ".join(f"{v:.1f}s" for v in vals)
            lines.append(f"| {key} | {row} | {statistics.mean(vals):.1f}s |")
        lines.append("")
        print(f"\n{label}: {_fmt_range(totals)}")
        for key in stage_keys:
            vals = [r["stages"].get(key, 0.0) for r in runs]
            print(f"  - {key}: {_fmt_range(vals)}")

    lines.append("## 한계 (측정 안 한 것)")
    lines.append("- HTTP·FastAPI 레이어 오버헤드는 포함 안 됨(VLM 호출이 절대다수라 무시 가능한 수준으로 봄, 별도 실측은 안 함).")
    lines.append("- product_name·ingredients·ingredient_amounts 미입력 — 실제 사용 패턴과 다를 수 있음.")
    lines.append("- 1회 실행값끼리 비교 금지, 여기 범위 자체가 다음 세션 판단 재료.")
    lines.append("")
    lines.append("관련: [[barum-check-latency-and-decision]], [[barum-vlm-run-variance]], [[barum-no-unverified-metrics-rule]]")

    out_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"\n결과 저장: {out_path}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--reps", type=int, default=3, help="이미지당 반복 횟수")
    ap.add_argument(
        "--out",
        type=Path,
        default=ROOT.parent / "docs" / "result" / "2026-08-23_check_지연_사전측정.md",
        help="결과 md 경로. 기본값은 8/23 사전측정 문서(덮어쓰니 주의)",
    )
    ap.add_argument(
        "--title",
        default="`/check` 단계별 지연 실측 (게이트 도입 전 베이스라인)",
        help="결과 md 제목",
    )
    args = ap.parse_args()
    main(reps=args.reps, out_path=args.out, title=args.title)
