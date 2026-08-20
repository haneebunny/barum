# 백엔드 세션 인수인계 (2026-08-20, 백엔드5 → 다음 세션)

> 받는 사람: 다음 barum 백엔드 세션(백엔드6). 정리: 이전 백엔드 세션(백엔드5 베베, Claude). 결정권자: 하니(팀장). 조율: PM.
> 목적: 백엔드 담당 역할을 넘긴다. 이 문서 하나로 현 상태·다음 할 일·주의점을 파악할 수 있게.

## 0. 너의 역할
바름 **백엔드 세션 담당**. 판정 파이프라인·API·콘텐츠생성(create 모드 상세페이지)을 이어간다.
- 착수 규칙: `CLAUDE.md` (코드 전에 인터뷰·단계별 계획·승인 대기, **§G 공유 워크트리 규칙 필독**, em-dash 금지·한국어 짧게).
- Git 규칙: `AGENTS.md` + `CLAUDE.md §G`. `feature/be-...`/`fix/be-...` 브랜치 → `git worktree add`로 격리 → push 후 `gh pr create`로 직접 PR까지 연다(gh 인증 완료, 링크만 전달하지 말 것). **main 직접 push 금지.**
- 전체 로드맵 `ROADMAP.md`, 확정 결정 `PROJECT.md`.
- 지시·질문은 **현재 PM**에게. 이 문서 작성 시점 현 PM = **PM 7대 루루**(`local_84b1d5f5-6fd2-4030-95c1-c427d7b3b00e`). 세션이 자주 바뀌므로 매번 `mcp__ccd_session_mgmt__list_sessions`로 "(현)"·최신 활동시각 재확인, 늦게 갱신되는 구세션에 속지 말 것. `memory`의 `barum-session-roster`가 최신 매핑을 유지하니 먼저 확인.
- **memory를 꼭 읽을 것.** 이 세션(백엔드5)이 남긴 memory가 많다(아래 §7 목록). 특히 [[barum-fix-minor-issues-directly]](사소한 이슈는 PM한테도 안 물어보고 바로 고침, 머지 확인만 별개)와 [[barum-never-symlink-env]](`.env` 심볼릭 링크 절대 금지)는 실제 사고 이력이 있는 규칙이라 필독.

## 1. 지금까지 만든 것 (전부 main 머지 완료)

백엔드4 인수인계 시점(`docs/handoffs/2026-08-13-backend3-session-handoff.md`이 마지막 문서, 백엔드4 자체 핸드오프 문서는 못 찾음) 이후 이 세션(백엔드5)이 추가한 것만 적는다. 그 이전 것(판정 파이프라인·RagJudge·레퍼런스팩·콘텐츠생성 improve/create 기본골격 등)은 안정 상태로 유지됨.

**제품사진 업로드 → AI 배경 합성 (PR #169, 방식 A, 팀장 승인)**
- `POST /uploads/product-photo`(멀티파트) 신설. `GenerateRequest.product_photo_ids`로 참조.
- 참조 사진이 있으면 `OpenAIImageGenerator`의 `images.edit`(합성) 경로를 탄다. 프롬프트도 "제품을 그리지 마라"에서 "참조 사진 속 실제 제품을 유지하며 합성하라"로 분기.
- **⚠️ 충실도 문제 발견, 미해결.** 실제 제품사진으로 합성 테스트해보니 `gpt-image-1-mini`가 라벨 텍스트·브랜드명을 완전히 날리고 병 형태도 미묘하게 바꿈. low/medium 품질 둘 다 동일 문제(화질 문제 아님). 자세한 내용·후보 대안 4가지는 memory [[barum-photo-composite-fidelity-issue]] 참조. **다음 결정은 팀장 몫.**

**이미지 톤 통일 (PR #163)**
- `GenerateRequest.color_tone`/`mood` 필드 추가, 인터뷰 자유서술을 이미지 프롬프트에 반영.
- `_resolve_tone(req, product_type)`이 **같은 요청의 모든 모듈에 항상 같은 톤 문구**를 내도록 함(6장이 색감 제각각이던 문제 해결).

**모델샷 범위 확정 (PR #176)** — 손·팔·뒷모습 허용, 얼굴은 계속 금지. 실사용 후기 연출 금지 문구 별도 명시.

**layout_type 배선 (PR #186)**
- `LayoutModule.layout_type` 필드 추가(디디 어휘집 `_vocabulary.json`의 12종 카탈로그). 플래너 프롬프트도 이 카탈로그로 지시.
- `LayoutPlan.color_system`은 **일부러 안 만들었다.** 어휘집이 머지 직전 정정되어(`71b3ebb`) color_system은 템플릿 색이 아니라 `color_tone`/`mood` 기본값 후보로 확정됐음. `images.py`의 `_TONE_DEFAULTS`를 디디 확정값(세럼/토너/크림/앰플)으로 교체.
- 곁다리 버그 수정: `load_layout_references()`가 `_vocabulary.json`까지 글롭으로 읽어서 이미 깨져 있던 테스트도 같이 고침.

**이미지 구도가 손으로 쏠리던 버그 (PR #188)**
- "손으로 제품 바르는 장면" 예시가 모든 모듈에 조건 없이 들어가 있어서 6장이 전부 그리로 수렴했었다. `layout_type`(hero_fullbleed·step_list만 손 허용)으로 분기.

**table_info 상품 스펙표 지원 (PR #190, #195)**
- 범위는 **제형·용량만**(팀장 확정, 전성분·함량은 기존 `ingredients`/`ingredient_amounts` 재활용).
- `GenerateRequest.formulation_type`/`volume` 추가, `Section.table_rows: [{label, value}]`, `ensure_product_spec_module()`이 값 있으면 `product_spec`(kind)/`table_info`(layout_type) 모듈을 결정적으로 끼워넣음(LLM은 이 kind를 모름). 둘 다 없으면 모듈 자체를 안 넣음(빈 테이블 방지).
- PR #195: product_spec 섹션이 항상 페이지 맨 앞에 렌더되던 순서 버그 수정(계획상 맨 뒤인데 sections 배열 조립 순서가 안 맞았음).
- **실제 브라우저로 end-to-end 검증 완료**(격리 워크트리에 백엔드+프론트 둘 다 띄워서 실제 `/generate` → 실제 "HTML로 내보내기"까지 확인, 표가 정확히 렌더됨).

**이미지 구도 구체화 + 사진성 없는 유형 스킵 (PR #198, 가장 최근)**
- 팀장이 실제 생성 결과(6장 이어붙임)를 보고 "너무 추상적", "전체적으로 뿌옇다" 지적.
- `layout_type`별로 "무엇을 그릴지"를 구체화(그라데이션만 옵션 제거, 제형별 구체적 질감 강제). 모든 프롬프트에 "선명하고 또렷하게, 흐림 금지" 지시 추가.
- `icon_grid`·`table_info`·`banner_strip`은 어휘집 정의상 사진 배경이 필요없는 유형이라 **이미지 생성 자체를 스킵**(그동안 만들어놓고 프론트가 버리고 있었음, 과금 낭비였음).
- 실제 재생성으로 전/후 비교 확인(과금 발생, 팀장 승인). 결과가 나아졌다는 것까지 확인함.

**기타**
- 이미지 모델 가격 조사(코드 변경 없음): `gpt-image-1-mini`/low가 최저가($0.005/장). 상위 모델 교체는 **보류**, 프롬프트 개선을 먼저 하기로 함(PR #198이 그 결과). 다음 세션에서 모델 교체 여부를 다시 판단할 수 있음 — PR #198 결과를 팀장이 보고 만족하면 안 해도 됨.
- `.env` 파일 소실 사고 있었음(다른 세션, 심볼릭 링크 자기참조). 지금은 복구됨(직접 확인함, 키 길이로 검증). memory [[barum-never-symlink-env]] 참고, 워크트리에선 **cp로 복사**만 쓸 것.

**테스트**: **468 통과**(2026-08-20 기준, 백엔드4 인수 시점 이후 대략 250개 이상 늘어남).

## 2. 다음 할 일 (우선순위 미정, PM 확인 후 착수)

1. **PR #198 결과에 대한 팀장 반응 확인.** 이미지가 여전히 부족하면 모델 교체(gpt-image-1 등 mini 아닌 상위 모델)로 넘어갈 수 있음 — 보류 중이었던 항목.
2. **톤 alternation(명도 교차)** — 어휘집의 "섹션마다 배경 톤을 진하게/연하게 교차" 패턴을 실제로 반영할지. table_info 끝나면 하기로 미뤄뒀던 것, 이제 착수 가능. 색 계열(hue)은 고정하고 명도만 모듈 순서대로 교차하는 방향으로 PM이 이미 정리해줌(memory [[barum-tone-alternation-resolved]] 참고, 급하지 않음).
3. **제품사진 합성 충실도 문제** — 팀장 판단 대기(§1 참고, memory [[barum-photo-composite-fidelity-issue]]).
4. **구조화 콘텐츠 갭(B안)** — `Section`에 headline/subcopy 분리, 임상모듈 구조화 수치(`clinical_bar_compare`의 `bars[]`) 지원. 지금은 프론트가 첫 문장을 헤드라인으로 잘라 쓰는 휴리스틱으로 임시 처리 중. 급하지 않음, memory [[barum-structured-section-content-gap]] 참고. 여기 딸린 이슈: `clinical_bar_compare`가 `has_claim_risk` 모듈과 자주 겹쳐서, 실증자료 없어 스킵되면 제일 화려한 자리가 통째로 빌 위험 있음 — B안 작업 시 대체 레이아웃(폴백)도 같이 정할 것.
5. **`docs/api/README.md` 갱신** — 백엔드3 때부터 미반영 상태가 계속 이어지고 있음(`/uploads/product-photo`·`formulation_type`/`volume`·`layout_type` 등 전부 미반영). 손 못 댐.

## 3. 확정 결정 (되돌리지 말 것)

백엔드4 이전 확정사항 전부 유지(이 문서에서 반복 안 함, 이전 handoff 문서들 참고). 이 세션에서 추가된 것:

- **`LayoutPlan.color_system` 필드는 안 만든다.** color_system/category_base_tone은 템플릿 색이 아니라 `color_tone`/`mood`(이미지 생성 프롬프트) 기본값 후보다. 프론트 스키마엔 optional로 있지만 렌더링에 안 씀(냐냐 PR #183 확인).
- **`_TONE_DEFAULTS`는 세럼/토너/크림/앰플 4종만 디디 확정값, 그 외 product_type은 중립 기본값(`None` 키)으로 폴백.** 어휘집 밖 종류를 억지로 끼워맞추지 않는다.
- **table_info 지원 범위는 제형·용량만.** 전성분·함량은 기존 필드 재활용, 새로 안 만든다.
- **`icon_grid`·`table_info`·`banner_strip`은 이미지 생성 안 함.** 상한(`max_images`)도 안 소모한다.
- **layout_type별 구도(무엇을 그릴지)는 사진성 유형에서 "그라데이션만" 옵션이 없다.** 구체적 질감을 강제한다(추상으로 도피 금지).
- **content.py는 저장소를 모른다.** `image_sink`·`photo_resolver` 등은 전부 `api/app.py`가 주입(오프라인 테스트 유지 원칙, 계속 지킬 것).
- **product_spec 등 결정적 조립 섹션(LLM이 안 쓰는 것)은 `generate_module_sections` 호출 뒤에 붙인다.** `ensure_product_spec_module`이 plan.modules 맨 뒤에 붙이는 것과 순서를 맞추기 위함(PR #195).

## 4. 주의점 (안 지키면 사고남)

- **공유 워크트리 — CLAUDE.md §G 필독.** `git add .` 절대 금지, `git checkout <다른 브랜치>`로 메인 워크트리 HEAD 옮기지 말 것. 브랜치 작업은 `git worktree add <임시경로> -b <브랜치> origin/main` → 끝나면 `git worktree remove`.
- **`.env`에 `ln -s`/`ln -sf` 쓰지 말 것.** 실제 사고 있었음(다른 세션, 원본 키 파일 소실). 워크트리에서 필요하면 `cp`로 복사, 작업 후 지우거나 그냥 둬도 됨(gitignore라 커밋 위험은 없음). `venv`·`node_modules`는 심볼릭 링크 괜찮음(단, 프론트 Turbopack은 워크트리 밖을 가리키는 `node_modules` 심볼릭 링크를 거부한다 — 프론트까지 같이 띄워야 하면 `cp -R`로 복사할 것, 실측함).
- **사소한 이슈는 PM한테도 안 물어보고 바로 고친다(2026-08-19 팀장 지시).** 렌더 순서·문구 다듬기 같은 것. 단 **머지 확인은 별개** — PR 올리고 코드 고치는 건 안 물어봐도 되지만, main 머지는 여전히 하니(팀장) 확인 받고 진행(직접 채팅으로 물어볼 것, PM 경유로 대체 안 됨). 최근엔 하니가 PR 올라오면 스스로 빠르게 머지해주는 경우가 많았음(응답 기다리는 동안 다른 작업 이어가도 됨).
- **실제 생성 결과를 눈으로 확인할 땐 격리 워크트리에 백엔드+프론트를 별도 포트로 띄워서 진짜 브라우저로 확인하는 게 제일 확실하다.** `curl`로 JSON만 보는 것보다 팀장이 보는 것과 똑같은 걸 보는 게 낫다(2026-08-19/20 여러 번 이 방법으로 실제 버그를 잡음). 브라우저 뷰포트가 0x0으로 깨지는 경우가 있었는데 `resize_window`로 복구됨(도구 자체 버그로 보임, 재현되면 이 방법 시도).
- **과금 호출(이미지 생성 등)은 재시도 없이 실패 기록·스킵.** 실제 생성 검증은 소량(1건 상품, 필요한 모듈만)으로 하고 팀장께 결과를 직접 보여드릴 것(SendUserFile 등).
- **팀원 실명 → 코드네임.** 커밋·문서에 실명(하니 포함) 쓰지 않는다.
- **PM 라우팅**: 매번 `list_sessions`로 현재 PM 확인. PM도 자주 교체된다(PM6→PM7, 2026-08-19).

## 5. 실행

```bash
cd backend
./venv/bin/python scripts/run_api.py            # 서버 (localhost:8000, /docs)
./venv/bin/python -m pytest tests/ -q           # 테스트 (468 통과)
```
- 오프라인/키없이 테스트만: `JUDGE_KIND=stub CHECKS_PERSIST=0`.
- 실제 이미지 생성 확인하려면 `IMAGE_GENERATION_ENABLED=1` 추가(기본 비활성, 과금 발생).
- 키: `backend/.env`에 `OPENAI_API_KEY`(판정·임베딩·이미지생성)·`GOOGLE_API_KEY`(OCR)·`SUPABASE_URL`·`SUPABASE_KEY` 전부 있음(2026-08-20 확인). 워크트리엔 `.env`가 안 딸려온다(gitignore) — **반드시 `cp`로 복사**해서 쓸 것(`ln -s` 금지, §4 참고).

## 6. memory 목록 (이 세션이 새로 남긴 것, 읽어볼 것)

- `barum-photo-composite-fidelity-issue` — 제품사진 합성 충실도 문제, 팀장 판단 대기
- `barum-tone-alternation-resolved` — 명도 교차 방향 정리됨, table_info 이후 착수 가능
- `barum-structured-section-content-gap` — headline/subcopy·임상수치 구조화 B안, clinical_bar_compare 대체 레이아웃 필요
- `barum-export-html-color-architecture` — export HTML 색 구조 확정 배경
- `barum-fix-minor-issues-directly` — 사소한 이슈 즉시 수정 방침(머지 확인은 별개)
- `barum-never-symlink-env` — `.env` 심볼릭 링크 금지 (다른 세션 작성, 필독)

관련: `docs/handoffs/2026-08-13-backend3-session-handoff.md`(그 이전 상태)
