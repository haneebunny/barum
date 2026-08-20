# -*- coding: utf-8 -*-
"""치환 품질 실측. 홀드아웃(119문장), 규칙 경로만, API 비용 0.

    ./venv/bin/python scripts/replacement_quality.py

**왜 규칙 경로만 재나**: 위반 span을 누가 만드느냐가 다르다. 규칙 경로(RagJudge)는
`span=match.span`이라 **걸린 키워드 한 단어**가 오고, VLM 경로(PromptJudge)는
`span=s["text"]`라 문장 전체가 온다. 문장 전체를 갈아끼우면 안 깨지므로 깨짐은
규칙 경로에서만 난다. 따라서 이 수치는 서비스 전체 비율이 아니라 **규칙 경로 한정**이다.

2026-08-20 실측: 규칙 경로로 잡힌 21문장 중 치환이 일어난 15문장, 그중 11문장이
치환 뒤에도 규칙집에 걸렸다. 단어 자리에 명사구를 넣어 문법이 깨지고, 문장에 남은
다른 위반 요소('상처', '연고')는 그대로 남는다. 분모가 작으니 퍼센트로 쓰지 말 것.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, "src")  # backend/에서 바로 실행할 수 있게(remediation_audit.py와 같은 방식)

from barum.generate.replace import apply_replacements, build_replacements
from barum.models import Finding, JudgmentFlag, Location, ViolationType
from barum.reference.rules import RuleOutcome, match_rule

HOLDOUT = Path(__file__).resolve().parents[1] / "data" / "prompt_holdout.jsonl"
if not HOLDOUT.exists():
    # 홀드아웃은 git 비추적이라 워크트리에는 없다. 원본 backend/에서 돌리거나 복사해서 쓴다.
    raise SystemExit(f"홀드아웃이 없다: {HOLDOUT}\n원본 backend/에서 실행하거나 그 파일을 복사할 것.")

lines = [json.loads(l) for l in HOLDOUT.read_text(encoding="utf-8").splitlines() if l.strip()]
print(f"홀드아웃 {len(lines)}문장\n")

rule_hit = 0          # 규칙 경로로 위반/검토필요로 잡힌 문장
replaced_n = 0        # 치환이 실제로 일어난 문장
still_flagged = 0     # 치환 후에도 규칙집에 걸리는 문장
keyword_remains = 0   # 치환 후에도 원래 걸린 키워드가 본문에 남은 문장
samples = []

for row in lines:
    text = row["text"]
    m = match_rule(text)
    if m is None or m.outcome not in (RuleOutcome.violation, RuleOutcome.needs_review):
        continue
    rule_hit += 1
    f = Finding(span=m.span, sentence=text,
                violation_type=m.violation_type or ViolationType.type_5_deception,
                legal_basis="화장품법 제13조",
                flag=m.flag or JudgmentFlag.violation,
                explanation="측정", location=Location(order=0))
    reps = build_replacements([f])
    if not reps:
        continue
    out = apply_replacements(text, reps)
    if out == text:
        continue
    replaced_n += 1
    after = match_rule(out)
    flagged = after is not None and after.outcome in (RuleOutcome.violation, RuleOutcome.needs_review)
    remains = m.span in out
    if flagged:
        still_flagged += 1
    if remains:
        keyword_remains += 1
    if (flagged or remains) and len(samples) < 6:
        samples.append((m.span, text, reps[0].replaced, out, after.outcome.name if after else "매칭없음"))

print(f"규칙 경로로 잡힌 문장        : {rule_hit} / {len(lines)}")
print(f"실제로 치환이 일어난 문장    : {replaced_n} / {rule_hit}")
print(f"치환 후에도 규칙집에 걸림    : {still_flagged} / {replaced_n}")
print(f"치환 후에도 원래 키워드 잔존 : {keyword_remains} / {replaced_n}")
print("\n=== 사례 ===")
for span, before, rep, after_text, outcome in samples:
    print(f"\n걸린 키워드: {span!r}  ->  대체표현: {rep!r}")
    print(f"  전: {before}")
    print(f"  후: {after_text}")
    print(f"  치환 후 규칙집 판정: {outcome}")
