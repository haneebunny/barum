"""상세페이지 생성 1건의 토큰·시간을 잰다. 이미지 생성 켬/끔 비교.

**금액은 내지 않는다.** 저장소에 텍스트 모델 단가표가 없다(`ocr_cost_probe.py`와 같은
이유). 토큰을 내면 단가가 정해질 때 곱하기만 하면 되지만, 단가를 지어내면 그 수치가
문서로 굳는다. 이미지는 `OpenAIImageGenerator.PRICE_PER_IMAGE`에만 단가가 있고
지금 쓰는 Gemini(나노 바나나)는 없어서 역시 장수만 낸다.

**과금 호출이다.** 이미지를 켜면 모듈 수만큼 이미지가 생성된다.

사용:
    cd backend && venv/bin/python scripts/generate_cost_probe.py          # 이미지 끔
    IMAGE_GENERATION_ENABLED=1 venv/bin/python scripts/generate_cost_probe.py
"""

import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, "src")

from barum.generate.content import generate_content  # noqa: E402
from barum.judge.cosmetic import RagJudge  # noqa: E402
from barum.models import GenerateRequest, IngredientAmount  # noqa: E402
from barum.vlm import get_image_generator, get_vlm  # noqa: E402


def _request() -> GenerateRequest:
    """시연에 쓰는 것과 같은 결의 create 요청."""
    return GenerateRequest(
        mode="create",
        product_name="유어베리 글로우 세럼",
        certifications=["미백 기능성 인증"],
        ingredient_amounts=[IngredientAmount(name="나이아신아마이드", amount="3%")],
        notes="20~30대 여성 타겟. 데일리 사용감 강조.",
        preset="clinical_neutral",
    )


def main() -> int:
    image_on = os.environ.get("IMAGE_GENERATION_ENABLED", "0") == "1"
    vlm = get_vlm("openai")
    judge = RagJudge(vlm)
    image_gen = get_image_generator() if image_on else None

    t0 = time.perf_counter()
    resp = generate_content(
        _request(), judge=judge, vlm=vlm, image_generator=image_gen
    )
    elapsed = time.perf_counter() - t0

    text = vlm.cache_report() if hasattr(vlm, "cache_report") else {}
    n_images = sum(1 for m in resp.image_plan.module_images if m.status == "generated")
    result = {
        "image_generation": "켬" if image_on else "끔",
        "elapsed_sec": round(elapsed, 1),
        "sections": len(resp.sections),
        "cards": len(resp.cards),
        "text_tokens": text,
        "images_generated": n_images,
        "image_tokens": getattr(image_gen, "total_tokens", None) if image_gen else 0,
        "recheck_findings": resp.recheck.n_findings if resp.recheck else None,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print("\n금액은 내지 않는다 — 저장소에 이 모델들의 단가표가 없다.")
    print("단가가 정해지면 위 토큰 수에 곱하면 된다.")
    out = Path(f"/tmp/generate_cost_{'on' if image_on else 'off'}.json")
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"저장: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
