"""정답셋 v2 빌더 — 힌트 재채굴 + tile_text + 중복 제외.

Gemini 사전분류(lite)가 1·2호를 과소평가해 실제 위반이 '합법' 풀에 숨는다.
질병명·의약품명 패턴으로 후보를 재채굴해 위반 버킷에 올린다(최종 라벨은 사람).
그러면 Gemini의 미탐이 정답셋에 포함돼 recall 측정에 유리하다.

실행:
    venv/bin/python scripts/build_goldset.py
"""

import argparse
import json
import random
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import build_holdout as bh  # noqa: E402

# 1호(질병표방) 재채굴 — 질병명·특징 증상. 라목까지 넓게 후보로.
DISEASE = re.compile(
    r"당뇨|고혈압|혈압|관절염|류마티|지방간|간염|간경화|간경변|고지혈|동맥경화|"
    r"뇌졸중|심근경색|협심증|변비|위염|장염|역류성|식도염|위궤양|갱년기|전립선|"
    r"골다공|골감소|치매|인지장애|불면|수면장애|우울|천식|비염|축농증|아토피|"
    r"건선|치주|잇몸|풍치|통풍|요산|방광염|요실금|백내장|녹내장|황반변성|빈혈|"
    r"디스크|협착|신장질환|신부전|담석|결석|암\b|종양|비만\b|과민성|대장|"
    r"잔뇨|야간뇨|배뇨|소변\s*줄기|손발\s*저림|말초신경"
)
# 2호(의약품오인) 재채굴 — 의약품명·한약처방·"약" 표현.
DRUG = re.compile(
    r"위고비|삭센다|마운자로|오젬픽|젭바운드|제니칼|디에타민|펜터민|큐시미아|"
    r"GLP-?1|세마글루타이드|리라글루타이드|오르리스타트|메트포르민|"
    r"다이어트\s*약|살\s*빼는\s*약|지방\s*분해\s*약|식욕\s*억제\s*약|"
    r"간장약|관절약|위장약|변비약|눈\s*약|"
    r"방풍통성산|태음조위탕|방기황기탕|가미소요산|"
    r"약\s*대신|처방\s*없이|병원\s*안\s*가|의약품\s*대체|의약품과\s*동일"
)
# 4호(거짓과장) 재채굴 — 인정 기능성 밖의 신체조직 작용 표현.
BODY = re.compile(
    r"붓기|부기|탄력|주름|미백|셀룰라이트|노폐물|디톡스|흡수율|"
    r"재생|모발|탈모|피부\s*장벽|각질|모공|리프팅|콜라겐\s*합성|"
    r"지방\s*분해|지방\s*연소|군살|셀룰\s*라이트"
)
# 재채굴 오검 방지 — 법정 면책·주의문은 후보에서 뺀다.
SAFE = re.compile(r"아닙니다|의약품이\s*아|상담하십시오|상담\s*후|주의사항|관련\s*없는")


def remine(pool: list[dict]) -> Counter:
    """합법 힌트 문장 중 질병명·의약품명 패턴을 위반 후보로 승격한다.

    승격만 한다(위반→합법 강등 없음). 최종 라벨은 사람이 정하므로,
    합법으로 판명될 후보가 섞여도 안전하다(오히려 하드 네거티브).
    """
    promoted = Counter()
    for r in pool:
        if r["hint"] != "합법":
            continue
        s = r["sentence"]
        if SAFE.search(s):
            continue
        if DRUG.search(s):
            r["hint"] = "2호_의약품오인"; r["mined"] = True; promoted["2호"] += 1
        elif DISEASE.search(s):
            r["hint"] = "1호_질병표방"; r["mined"] = True; promoted["1호"] += 1
        elif BODY.search(s):
            r["hint"] = "4호_거짓과장"; r["mined"] = True; promoted["4호"] += 1
    return promoted


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--total", type=int, default=230)
    ap.add_argument("--shared", type=int, default=20)
    ap.add_argument("--per-product", type=int, default=10)
    ap.add_argument("--legal-cap", type=int, default=55,
                    help="합법 문장 상한(위반 대비 균형용)")
    ap.add_argument("--seed", type=int, default=20260806)
    ap.add_argument("--prefix", default="goldset")
    ap.add_argument("--exclude", nargs="*", default=[
        "data/holdout_master_v1.jsonl",
        "data/alignment_round3_master.jsonl",
        "data/alignment_round4_master.jsonl",
    ])
    args = ap.parse_args()
    random.seed(args.seed)

    used = set()
    for f in args.exclude:
        for line in open(f):
            if line.strip():
                used.add(bh.normalize(json.loads(line)["sentence"]))

    pool = [r for r in bh.build_pool() if bh.normalize(r["sentence"]) not in used]

    # build_pool은 상품 속성(certified_function·disclaimer)을 안 채운다 — 채워넣는다.
    ocr = bh.load_ocr()
    cert, disc = {}, {}
    for pid in {r["product_id"] for r in pool}:
        src = ocr.get(pid)
        texts = [s["text"] for s in src["sentences"]] if src else []
        cert[pid] = bh.extract_certified(texts)
        disc[pid] = "있음" if bh.has_disclaimer(texts) else "없음"
    for r in pool:
        r["certified_function"] = cert.get(r["product_id"], "")
        r["disclaimer"] = disc.get(r["product_id"], "없음")

    print(f"[제외] 이전 사용 {len(used)}개 → 잔여 풀 {len(pool)}개")

    promoted = remine(pool)
    print(f"[재채굴] 합법→위반 후보 승격: {dict(promoted)}")

    dist = Counter(r["hint"] for r in pool)
    print("재채굴 후 힌트 분포:", dict(dist.most_common()))

    picked = bh.allocate(pool, args.total, args.per_product)

    # 위반이 부족하면 allocate가 그 몫을 합법으로 채워 합법이 과다해진다.
    # 합법을 상한으로 잘라 위반 대비 균형을 맞춘다(하드 네거티브는 충분히 남김).
    by = defaultdict(list)
    for r in picked:
        by[r["hint"]].append(r)
    if len(by["합법"]) > args.legal_cap:
        random.shuffle(by["합법"])
        by["합법"] = by["합법"][:args.legal_cap]
    picked = [r for rows in by.values() for r in rows]
    random.shuffle(picked)
    print(f"\n→ {len(picked)}개 선택 (상품 {len({r['product_id'] for r in picked})}개)")

    sheet_a, sheet_b = bh.split_sheets(picked, args.shared)
    for sheet, tag in ((sheet_a, "A"), (sheet_b, "B")):
        for i, row in enumerate(sheet):
            shared = i < args.shared
            row["id"] = f"S{i+1:03d}" if shared else f"{tag}{i-args.shared+1:03d}"
            row["is_cross_check"] = "Y" if shared else "N"

    px = args.prefix
    bh.write_xlsx(sheet_a, Path(f"data/{px}_A.xlsx"), "A")
    bh.write_xlsx(sheet_b, Path(f"data/{px}_B.xlsx"), "B")
    with open(f"data/{px}_master.jsonl", "w") as f:
        for sheet, tag in ((sheet_a, "A"), (sheet_b, "B")):
            for row in sheet:
                f.write(json.dumps({**row, "sheet": tag}, ensure_ascii=False) + "\n")

    for tag, sheet in (("A", sheet_a), ("B", sheet_b)):
        d = Counter(r["hint"] for r in sheet)
        mix = " ".join(f"{k.split('_')[0]}:{v}" for k, v in sorted(d.items()))
        print(f"{tag}: {len(sheet)}행 (공통 {args.shared} + 고유 {len(sheet)-args.shared}) | {mix}")

    print(f"\n→ data/{px}_A.xlsx, data/{px}_B.xlsx / data/{px}_master.jsonl")
    bh._run_validation({"A": sheet_a, "B": sheet_b})


if __name__ == "__main__":
    main()
