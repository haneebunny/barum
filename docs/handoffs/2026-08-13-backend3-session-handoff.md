# 백엔드 세션 인수인계 (2026-08-13, 백엔드3 → 다음 세션)

> 받는 사람: 다음 barum 백엔드 세션(백엔드4). 정리: 이전 백엔드 세션(백엔드3 베베, Claude). 결정권자: 하니. 조율: PM.
> 목적: 백엔드 담당 역할을 넘긴다. 이 문서 하나로 현 상태·다음 할 일·주의점을 파악할 수 있게.

## 0. 너의 역할
바름 **백엔드 세션 담당**. 판정 파이프라인·API·콘텐츠생성을 이어간다.
- 착수 규칙: `CLAUDE.md` (코드 전에 인터뷰·단계별 계획·승인 대기, **§G 공유 워크트리 규칙 필독**, em-dash 금지·한국어 짧게).
- Git 규칙: `AGENTS.md` + `CLAUDE.md §G`. `feature/be-...` 브랜치 → `git worktree add`로 격리 → push 후 `https://github.com/haneebunny/barum/pull/new/<브랜치>` 링크 전달(gh CLI 없음) → 하니가 GitHub 웹에서 머지. **main 직접 push 금지.**
- 전체 로드맵 `ROADMAP.md`, 확정 결정 `PROJECT.md`, 진행기록 `PROGRESS_BE.md`(이 세션이 최신화 완료, 상세는 여기 참조).
- 지시·질문은 **현재 PM**에게. 이 문서 작성 시점 현 PM = **PM 5대 루루**(`local_0d7e5be8-e27e-4737-8729-a1ac872da8e3`). 세션이 자주 바뀌므로 매번 `mcp__ccd_session_mgmt__list_sessions`로 "(현)"·최신 활동시각 재확인, 늦게 갱신되는 구세션에 속지 말 것.

## 1. 지금까지 만든 것 (전부 main 머지 완료, PR 다수)

백엔드2 인수인계 시점(`docs/handoffs/2026-08-12-backend2-session-handoff.md`) 이후 이 세션(백엔드3)이 추가한 것만 적는다. 그 이전 것(판정 파이프라인 기본골격·RagJudge·레퍼런스팩·Supabase·콘텐츠생성 improve 모드 등)은 그 문서 참조, 전부 안정 상태로 유지됨.

**콘텐츠생성 create 모드 (FR-11 신규 생성)** — `generate/content.py`, `models.py`, `reference/approved_claims.py`
- `POST /generate`가 `mode`(`improve`|`create`, 기본 improve)로 분기. create는 `content`(원본) 없이 제품정보만으로 성립.
- 효능표현(광고문구)은 **인증서-인정문구 매칭**으로만 나온다(자유창작 금지, improve의 조건표 치환과 같은 원칙). 카테고리(미백/주름개선/자외선차단)마다 ①인증서 매칭 ②성분명 있음 ③함량 명시 ④함량 기준 충족 **4개 다 통과**해야 문구 생성, 하나라도 실패하면 `skipped_claims`에 사유 명시(조용히 안 빠짐).
- 인정문구 데이터는 비비(DB담당)의 `reference/data/approved_efficacy_statements.json` — **카테고리별 `status`**(`confirmed`/`needs_confirmation`)로 게이트된다. 2026-08-13 기준 미백·주름개선·자외선차단 **셋 다 confirmed**라 실제로 문구가 나온다.
- 이 게이트는 원래 최상위 status로 짰다가, 비비가 스키마를 카테고리별로 바꾸면서 위험하게 무력화될 뻔한 걸 발견해서(비비 발견, PM4 전달) 카테고리 단위로 다시 짰다(커밋 `62237f8`). **다음에 이 파일 건드릴 때 최상위 status로 되돌리지 말 것.**

**2호(기능성오인) 판정에 함량 대조 추가** — `judge/cosmetic.py` `_functional_evidence`, `reference/ingredients.py`, `pipeline.py`, `api/app.py`
- `/check`에 새 폼 필드 `ingredient_amounts`(옵트인, `"성분:함량"` 콤마구분, 예 `"나이아신아마이드:3%,알부틴:10%"`) 추가.
- 로직: 이름 없음→위반(기존) / 이름 있음+함량 미입력→검토필요(기존과 동일 메시지, 회귀 없음) / 이름 있음+함량 기준 미달→**위반**(신규) / 이름+함량 다 맞음→검토필요 유지하되 "등록 확인되면 합법 전환 가능" 명시(신규 — 인증만으론 합법 확정 안 됨을 사용자에게 보여줌).
- `CosmeticJudge` 프로토콜·`StubJudge`·`PromptJudge`·`RagJudge` 전부 `ingredient_amounts` 파라미터가 추가됐다(기본값 `None`이라 회귀 없음). 새 판정기 만들 때 이 시그니처 맞출 것.

**보고서** — `docs/result/LLM_프롬프트_현황_보고서.md`
- 지금 LLM을 어디서 어떻게 부르는지(판정·콘텐츠생성·OCR), 실제 프롬프트 원문+실제 응답, RagJudge가 언제 그라운딩을 먹이는지 기록. 프롬프트 엔지니어링할 때 "개정 전" 기준점.

**테스트** — `backend/tests/`, **182 통과**(2026-08-13 기준, 백엔드2 시점 155에서 +27).

## 2. 다음 할 일 (우선순위, PM 확인 후 착수)

1. **`docs/api/README.md` 갱신** — 백엔드2 때부터 미반영 상태였는데 이번 세션에서도 손 못 댐. `/generate`(create 모드 포함)·`/check`(`ingredient_amounts`)·`/remediate`·`/reports/*` 계약이 프론트 문서에 최신 반영 안 됨.
2. **하니 결정 대기 항목** (PM에 먼저 확인):
   - 미국 프리플라이트(2단계) 착수 여부 — 계속 후순위로 밀려있음.
   - 콘텐츠생성 create 모드의 프론트 화면 자체가 아직 없음(백엔드는 완료). `Section.source="approved_claim"` 값을 프론트 `SRC_LABEL`에 추가해야 함 — 디디에게 전달은 해뒀지만 실제 반영 여부 미확인.
3. **콘텐츠생성 후속 개선** (안전엔 문제없음, 알려진 개선점, 백엔드2 때부터 이월):
   - 재검증(`/generate`)에서 남은 위반을 자동 재치환하는 루프(지금은 1패스 치환 후 재검증만).
   - `remediation_rules.json` 데이터 품질(일부 대체표현 자체가 위반 소지) — 팀원B 소관.
4. **create 모드 확장 후보**: `parse_amount`가 IU/g·%만 지원(다른 단위 표기는 안전하게 스킵). 필요해지면 확장.

## 3. 확정된 판정 기준 (변경 없음, 참고)
1호 경계표현(진정=검토필요/실증대상, 탄력=합법/일반허용, 민감·예민=합법/상태서술, 아토피·염증·재생·치료·소독·약국전용·MTS 시술묘사=위반) — `reference/cosmetic_kr/violation_types/type_1_drug_misperception.md` 참조. RagJudge 규칙에 이미 encode됨.

## 4. 확정 결정 (되돌리지 말 것)
백엔드2 인수인계 문서 §4 전부 유지. 추가:
- **create 모드 인정문구는 인증서-인정문구 매칭만.** LLM 자유생성 금지(improve와 같은 원칙). 매칭 실패 시 문구를 지어내지 않고 `skipped_claims`로 명시.
- **인정문구 게이트는 카테고리 단위**(`categories[category]["status"]=="confirmed"`). 최상위 status로 되돌리지 말 것(위 §1 참조).
- **`/check`의 `ingredient_amounts`는 완전 옵트인.** 안 보내면 기존 이름만 대조하는 동작 그대로.

## 5. 주의점 (안 지키면 사고남)
- **공유 워크트리 — CLAUDE.md §G 필독.** 여러 세션이 같은 디렉터리에서 동시 작업. `git add .` 절대 금지, `git checkout <다른 브랜치>`로 메인 워크트리 HEAD 옮기지 말 것. 브랜치 작업은 `git worktree add <임시경로> -b <브랜치> origin/main` → 끝나면 `git worktree remove`.
- **origin에서 브랜치가 갑자기 여러 개 사라져도 사고 아닐 수 있음.** 이 저장소는 "PR 머지 시 head 브랜치 자동삭제" 설정이라, 하니가 GitHub 웹에서 연달아 머지하면 그때마다 자동으로 지워진다(2026-08-12 실제 오탐 있었음, `git merge-base --is-ancestor`로 먼저 확인하고 재push하지 말 것). memory `barum-branch-auto-delete-on-merge` 참조.
- **보고서·분석 자료는 `docs/result/`에 쓸 것.** 2026-08-12부터 규칙(PM5 전달). CLAUDE.md·ROADMAP.md·PROGRESS_BE.md 같은 상시 갱신 문서는 해당 없음.
- **venv pip 깨짐**: `./venv/bin/pip` shebang 에러. `./venv/bin/python -m pip install ...`로 우회.
- **gh CLI 없음**: PR은 push 후 링크를 하니에게 전달.
- **VLM 등 과금 호출은 재시도 없이 실패 기록·스킵.** 큰 배치 재실행 금지.
- **팀원 실명 → 코드네임.** 커밋·문서에 실명 쓰지 않는다.
- **PM 라우팅**: 매번 `list_sessions`로 현재 PM 확인.

## 6. 실행
```bash
cd backend
./venv/bin/python scripts/run_api.py            # 서버 (localhost:8000, /docs)
./venv/bin/python -m pytest tests/ -q           # 테스트 (182 통과)
./venv/bin/python scripts/dump_openapi.py       # openapi.json 갱신
./venv/bin/python scripts/make_fixtures.py      # fixtures 갱신
./venv/bin/python scripts/load_cases.py         # 사례 재적재(cases.md 바뀌면)
./venv/bin/python scripts/eval_ragjudge.py      # 배포 파이프라인 재평가
```
- 키: `backend/.env`에 `GOOGLE_API_KEY`(OCR)·`OPENAI_API_KEY`(판정·임베딩)·`SUPABASE_URL`·`SUPABASE_KEY` 전부 있음. (worktree엔 `.env`가 안 딸려온다 — gitignore. 스모크 테스트할 땐 메인 워크트리 `backend/.env`를 임시 복사해서 쓰고, 끝나면 지울 것.)
- 오프라인/키없이 UI만 붙일 때: `JUDGE_KIND=stub`, `CHECKS_PERSIST=0`.
