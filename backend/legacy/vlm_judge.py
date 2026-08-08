"""
VLM 과대·부당광고 판정 스크립트
====================================================
상품별 타일 이미지를 VLM(Gemini/Claude)에 보내 식약처 기준 위반 여부를 판정한다.

판정 단위 = "상품" (타일이 아님). 한 상품의 모든 타일을 묶어서 판정.

사용:
    # 타일이 있는 상품 전체 판정
    ./venv/bin/python vlm_judge.py 11st_output/details

    # 특정 상품만
    ./venv/bin/python vlm_judge.py 11st_output/details/3458162245

    # 쿠팡 데이터
    ./venv/bin/python vlm_judge.py coupang_output/images

    # 모델 변경
    ./venv/bin/python vlm_judge.py 11st_output/details --model gemini-3.5-flash

    # 레퍼런스 파일 주입
    ./venv/bin/python vlm_judge.py 11st_output/details --reference data/mfds_reference.json

출력: {details_root}/judgments_{timestamp}.json
"""
import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

IMG_EXT = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"}


# ── 모델 어댑터 ──────────────────────────────────────

class VLMAdapter:
    """모델 교체를 위한 공통 인터페이스."""

    def judge(self, images: list[Path], prompt: str) -> dict:
        raise NotImplementedError


class GeminiAdapter(VLMAdapter):

    def __init__(self, model_name: str, api_key: str):
        from google import genai
        self.client = genai.Client(api_key=api_key)
        self.model_name = model_name

    def judge(self, images: list[Path], prompt: str) -> dict:
        from google.genai import types

        contents = [prompt]
        for img_path in images:
            img_bytes = img_path.read_bytes()
            suffix = img_path.suffix.lower()
            mime = {"jpg": "image/jpeg", "jpeg": "image/jpeg",
                    "png": "image/png", "gif": "image/gif",
                    "webp": "image/webp", "bmp": "image/bmp"}.get(
                suffix.lstrip("."), "image/jpeg")
            contents.append(types.Part.from_bytes(data=img_bytes, mime_type=mime))

        response = self.client.models.generate_content(
            model=self.model_name,
            contents=contents,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.1,
            ),
        )
        return json.loads(response.text)


class ClaudeAdapter(VLMAdapter):
    """Claude API 어댑터 (placeholder — API 키 있을 때 구현)."""

    def __init__(self, model_name: str, api_key: str):
        self.model_name = model_name
        self.api_key = api_key

    def judge(self, images: list[Path], prompt: str) -> dict:
        raise NotImplementedError("Claude 어댑터는 아직 미구현. Gemini를 사용하세요.")


def create_adapter(provider: str, model_name: str, api_key: str) -> VLMAdapter:
    if provider == "gemini":
        return GeminiAdapter(model_name, api_key)
    elif provider == "claude":
        return ClaudeAdapter(model_name, api_key)
    else:
        sys.exit(f"지원하지 않는 provider: {provider}")


# ── 프롬프트 ──────────────────────────────────────────

SYSTEM_PROMPT = """\
당신은 대한민국 식약처(MFDS) 기준에 따라 다이어트 보조제(건강기능식품) 광고의 \
과대·부당광고 위반 여부를 판정하는 전문 심사관입니다.

## 판정 기준

아래 이미지들은 하나의 상품 상세페이지를 타일로 분할한 것입니다.
모든 타일을 종합해서 **상품 단위로** 판정하세요.

### 위반 유형 (하나라도 해당되면 "위반")
1. **질병_예방_치료_표방**: 질병의 예방·치료에 효과가 있다고 표현 (예: "당뇨병 예방", "고혈압 치료", "암 억제")
2. **후기_효과보증**: 개인 체험·후기로 효과를 보증 (예: "3주만에 -12kg", 전후 사진 비교)
3. **비방_비교광고**: 다른 제품이나 성분을 비방·비교하여 자사 제품 우위 주장
4. **안전성_단정**: "부작용 없음", "100% 안전" 등 안전성을 단정적으로 표현
5. **근거없는_최상급**: "국내 최초", "세계 1위", "업계 유일" 등 객관적 근거 없는 최상급 표현

### 합법으로 분류해야 하는 것 (오판 주의!)
6. **인정_기능성_문구**: 식약처가 인정한 건강기능식품 기능성 원료의 승인 문구는 **합법**.
   - 예시 (합법): "체지방 감소에 도움을 줄 수 있음" (가르시니아/HCA)
   - 예시 (합법): "식후 혈당 상승 억제에 도움을 줄 수 있음" (바나바잎)
   - 예시 (합법): "체지방 감소에 도움을 줄 수 있음" (돌외잎/BNR17)
   - 이런 문구를 위반으로 잡으면 오판입니다.

{reference_section}

## 출력 형식 (JSON)

다음 JSON 구조로 출력하세요:
{{
  "verdict": "위반" 또는 "합법",
  "confidence": 0.0~1.0 (판정 확신도),
  "violations": [
    {{
      "type": "위반유형_코드",
      "evidence": "해당 문구나 장면을 직접 인용",
      "tile_index": 몇 번째 타일에서 발견했는지 (0부터)
    }}
  ],
  "legal_claims": [
    {{
      "text": "합법으로 판단한 기능성 문구",
      "reason": "왜 합법인지 (인정 원료명 등)"
    }}
  ],
  "summary": "한 줄 요약"
}}

위반 사항이 없으면 violations는 빈 배열, verdict는 "합법"으로 하세요.
"""

REFERENCE_PLACEHOLDER = """\
### 참고: 식약처 인정 기능성 원료 (레퍼런스)
(레퍼런스 미등록 — 기본 지식으로 판단. 레퍼런스 등록 후 정확도 향상 예정)\
"""


def build_prompt(reference_path: str | None = None) -> str:
    if reference_path and Path(reference_path).exists():
        ref_data = Path(reference_path).read_text(encoding="utf-8")
        ref_section = f"""\
### 참고: 식약처 인정 기능성 원료 레퍼런스
아래는 식약처가 인정한 기능성 원료·문구 목록입니다. 이 목록에 있는 문구는 합법입니다.

{ref_data}"""
    else:
        ref_section = REFERENCE_PLACEHOLDER
    return SYSTEM_PROMPT.format(reference_section=ref_section)


# ── 상품·타일 탐색 ────────────────────────────────────

def find_products(root: Path) -> list[dict]:
    """상품 디렉토리와 타일 파일을 탐색."""
    products = []
    if (root / "tiles").is_dir():
        tiles = sorted(
            f for f in (root / "tiles").iterdir()
            if f.is_file() and f.suffix.lower() in IMG_EXT
        )
        if tiles:
            products.append({"code": root.name, "dir": root, "tiles": tiles})
        return products

    for d in sorted(root.iterdir()):
        if not d.is_dir():
            continue
        tile_dir = d / "tiles"
        if tile_dir.is_dir():
            tiles = sorted(
                f for f in tile_dir.iterdir()
                if f.is_file() and f.suffix.lower() in IMG_EXT
            )
            if tiles:
                products.append({"code": d.name, "dir": d, "tiles": tiles})
        else:
            imgs = sorted(
                f for f in d.iterdir()
                if f.is_file() and f.suffix.lower() in IMG_EXT
            )
            if imgs:
                products.append({"code": d.name, "dir": d, "tiles": imgs})
    return products


# ── 메인 ──────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(description="VLM 과대·부당광고 판정")
    ap.add_argument("path", help="상품 폴더 또는 details 트리")
    ap.add_argument("--model", default=os.getenv("MODEL_NAME", "gemini-2.5-flash"))
    ap.add_argument("--provider", default="gemini", choices=["gemini", "claude"])
    ap.add_argument("--reference", default=None, help="식약처 레퍼런스 JSON 경로")
    ap.add_argument("--delay", type=float, default=2.0, help="상품 간 대기(초)")
    ap.add_argument("--max-tiles", type=int, default=20, help="상품당 최대 타일 수")
    ap.add_argument("--output-dir", default=None, help="결과 저장 위치 (기본: path와 동일)")
    args = ap.parse_args()

    root = Path(args.path)
    if not root.exists():
        sys.exit(f"경로 없음: {root}")

    api_key_env = "GOOGLE_API_KEY" if args.provider == "gemini" else "ANTHROPIC_API_KEY"
    api_key = os.getenv(api_key_env)
    if not api_key:
        sys.exit(f"API 키 없음: .env에 {api_key_env}를 설정하세요.")

    products = find_products(root)
    if not products:
        sys.exit("판정할 상품이 없습니다. 타일 분할을 먼저 실행하세요:\n"
                 "  ./venv/bin/python tile_split.py 11st_output/details --recursive")

    print(f"\n{'='*60}")
    print(f"  VLM 과대·부당광고 판정")
    print(f"  모델: {args.model} ({args.provider})")
    print(f"  상품: {len(products)}개")
    print(f"  레퍼런스: {args.reference or '없음 (placeholder)'}")
    print(f"{'='*60}\n")

    adapter = create_adapter(args.provider, args.model, api_key)
    prompt = build_prompt(args.reference)

    results = []
    for i, prod in enumerate(products, 1):
        code = prod["code"]
        tiles = prod["tiles"][:args.max_tiles]
        print(f"[{i}/{len(products)}] {code} — 타일 {len(tiles)}장 판정 중...", end=" ", flush=True)

        try:
            judgment = adapter.judge(tiles, prompt)
            verdict = judgment.get("verdict", "?")
            n_violations = len(judgment.get("violations", []))
            summary = judgment.get("summary", "")
            print(f"→ {verdict} (위반 {n_violations}건) — {summary}")

            results.append({
                "product_code": code,
                "tile_count": len(tiles),
                "tile_files": [str(t) for t in tiles],
                "judgment": judgment,
            })
        except Exception as e:
            print(f"✗ 실패: {e}")
            results.append({
                "product_code": code,
                "tile_count": len(tiles),
                "error": str(e),
            })

        if i < len(products):
            time.sleep(args.delay)

    out_dir = Path(args.output_dir) if args.output_dir else root
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = out_dir / f"judgments_{ts}.json"

    ok = sum(1 for r in results if "judgment" in r)
    violations = sum(1 for r in results if r.get("judgment", {}).get("verdict") == "위반")
    errors = sum(1 for r in results if "error" in r)

    report = {
        "model": args.model,
        "provider": args.provider,
        "reference": args.reference,
        "judged_at": datetime.now().isoformat(),
        "total_products": len(products),
        "verdicts": {"위반": violations, "합법": ok - violations, "오류": errors},
        "products": results,
    }
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n{'='*60}")
    print(f"  완료: {ok}/{len(products)}개 판정 성공")
    print(f"  결과: 위반 {violations} / 합법 {ok - violations} / 오류 {errors}")
    print(f"  리포트: {out_path}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
