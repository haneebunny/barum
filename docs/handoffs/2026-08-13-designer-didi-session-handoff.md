# 디자이너 세션 인수인계 (2026-08-13, 디디 → 다음 세션)

> 받는 사람: 다음 barum 디자이너 세션. 정리: 이전 디자이너 세션(디디, Claude). 결정권자: 하니. 조율: PM.
> 목적: 디자이너 역할을 넘긴다. 이 문서 하나로 현 상태·다음 할 일·주의점을 파악할 수 있게.

## 0. 너의 역할
바름 **디자이너 세션 담당**. `design/mockups/`의 화면 목업을 이어간다.
- 착수 규칙: `CLAUDE.md` (코드 전에 인터뷰·단계별 계획·승인 대기, **§G 공유 워크트리 규칙 필독**, em-dash 금지·한국어 짧게).
- 디자인 규칙 마스터: `design/mockups/DESIGN.md` — §0 절대 원칙(색·대비·CVD는 검증기로만, 새 컴포넌트는 혼자 정하지 말 것), §3 매번 돌리는 검증(대비·CVD·em-dash), §4 확정 팔레트. **작업 전 필독.**
- Git 규칙: `AGENTS.md` + `CLAUDE.md §G`. `feature/fe-...` 브랜치 → `git worktree add`로 격리 → push 후 `https://github.com/haneebunny/barum/pull/new/<브랜치>` 링크 전달(gh CLI 없음) → 하니가 GitHub 웹에서 머지. **main 직접 push 금지.**
- **커밋은 큰 작업 단위 끝났을 때만.** 중간 요구사항 추가마다 커밋하지 않는다(하니 지시, 2026-08-12).
- 지시·질문은 **현재 PM**에게. 이 문서 작성 시점 현 PM = **PM 5대 루루**(`local_0d7e5be8-e27e-4737-8729-a1ac872da8e3`). 세션이 자주 바뀌므로 매번 `mcp__ccd_session_mgmt__list_sessions`로 "(현)"·최신 활동시각 재확인, 늦게 갱신되는 구세션에 속지 말 것.

## 1. 지금까지 만든 것

**v1.9 화면 5개 전부 완성, 4개는 main 머지 완료:**
- `barum.html` — 홈 (머지됨)
- `barum-inspect.html` — 검수 (머지됨)
- `barum-report.html` — 리포트 (기본형 머지됨. **FR-14 티어 게이팅 추가분은 PR 오픈 상태**, 아래 §2 참조)
- `barum-mypage.html` — 마이페이지 (머지됨, PR #39)
- `barum-content.html` — 콘텐츠 생성, improve 모드 (머지됨, PR #53). 백엔드3 리뷰로 `GenerateResponse` 계약(`backend/src/barum/models.py`)과 필드 단위로 대조·정합화 완료.

**콘텐츠 생성 화면(`barum-content.html`) 상세:**
- 원샷 생성(편집 불가), 생성 전 확인 모달(risk_confirmations 체크리스트 + pii_removed 정보), 재검증 배지(recheck.n_violation 기준 회색/빨강), sections를 kind별 카드+source 배지로 렌더, 내보내기는 HTML/PNG/PDF 드롭다운 하나(우하단, Figma는 PM4·백엔드 확정으로 MVP 제외).
- 진입은 리포트 화면의 "이 수정안대로 상세페이지 만들기" 브릿지로만(사이드바에 독립 메뉴 없음).
- 실제 파일 생성(HTML Blob 다운로드 / PNG·PDF는 html2canvas+jsPDF)은 프론트 실구현 대상, 지금은 클릭 시 상태 텍스트만 보여주는 목업.

**리포트 화면 FR-14 티어 게이팅(`barum-report.html`, PR 오픈):**
- 목업 전용 요금제 스위처(Free/Basic/Pro) 추가.
- 지적카드 대체표현 제안을 두 문장으로 나눔: Free는 첫 문장만, 두 번째 문장은 블러+자물쇠 아이콘+"Basic부터 전체 권고안 제공"으로 잠금. Basic/Pro는 전체 노출.
- 백엔드/API 변경 없음, 프론트 상태값(`state.tier`)만으로 처리(PM4 확정 스코프).

## 2. 다음 할 일 (우선순위, PM 확인 후 착수)

1. **리포트 화면 FR-14 게이팅 PR 머지 확인** — 브랜치 `feature/fe-report-tier-gate`, 아직 머지 안 됐으면 하니에게 리마인드.
2. **백엔드3가 남긴 요청 하나 미반영 상태**: 콘텐츠생성 create 모드(FR-11 신규 생성, 백엔드는 완료)에서 `Section.source`에 새 값 `"approved_claim"`(인증서-인정문구 매칭 기반 생성)이 추가됨. `barum-content.html`의 `SRC_LABEL` 매핑(`{remediation, llm, template}`)에 이 값이 빠져있다. **다만 create 모드 자체를 위한 화면(원본 문구 없이 제품정보만으로 생성)이 아직 없어서, 라벨 하나만 추가할지 create 모드 화면을 새로 설계할지는 인터뷰 먼저** — 착수 전 CLAUDE.md A 규칙대로 하니/PM에게 확인.
3. **내보내기 실구현**: 지금은 HTML/PNG/PDF 버튼이 목업(클릭해도 실제 파일 안 나감). 프론트(냐냐)가 실제 프론트 코드로 포팅할 때 html2canvas+jsPDF로 구현 예정(PM4·백엔드 확정, 백엔드 API 없음). 디자이너 쪽에서 추가로 할 일은 없지만, 포팅 중 질문 오면 참고.
4. **로고 마크·파비콘**: 여전히 하니가 직접 제작 예정(열린 채로 둬도 됨).

## 3. 확정 결정 (되돌리지 말 것)
`DESIGN.md` §1 전부 유지. 추가:
- **콘텐츠 생성 = 원샷.** 입력 받으면서 단계적으로 만드는 마법사 플로우 아님(하니 확정, 2026-08-12).
- **이미지는 업로드분 재배치만.** AI 신규 이미지 생성은 범위 밖(나중 도전 과제).
- **콘텐츠 생성 진입은 리포트 브릿지로만.** 사이드바 독립 메뉴 없음.
- **내보내기 = HTML+PNG+PDF만, Figma 제외.** PM4·백엔드 확정(2026-08-13). 하니가 처음엔 Figma까지 포함해 정했다가, 실제 구현 스코프(API 무거움) 확인 후 이 방향으로 뒤집힘 — 재검토 필요하면 하니에게 먼저 확인.
- **FR-14 티어 게이팅 = 잠금 티저(블러+CTA), 완전 숨김 아님.** 전환 유도 목적(하니 확정, 2026-08-13).
- **재검증 배지는 `n_violation` 필드를 써야 한다.** `n_findings`(위반+검토필요 합계)를 위반 건수로 잘못 쓰면 버그(백엔드3가 실제로 잡아낸 사례, `barum-content.html` 커밋 이력 참조).

## 4. 주의점 (안 지키면 사고남)
- **공유 워크트리 — CLAUDE.md §G 필독.** 여러 세션이 같은 디렉터리에서 동시 작업. `git add .` 절대 금지, `git checkout <다른 브랜치>`로 메인 워크트리 HEAD 옮기지 말 것. 브랜치 작업은 `git worktree add <임시경로> -b <브랜치> origin/main` → 끝나면 `git worktree remove`.
- **origin에서 브랜치가 갑자기 여러 개 사라져도 사고 아닐 수 있음.** "PR 머지 시 head 브랜치 자동삭제" 설정. `git merge-base --is-ancestor`로 먼저 확인.
- **보고서·분석 자료는 `docs/result/`에 쓸 것.** 2026-08-12부터 규칙(PM5 전달). 이 인수인계 문서·`DESIGN.md`처럼 상시 참조용 문서는 해당 없음.
- **gh CLI 없음**: PR은 push 후 링크를 하니에게 전달.
- **색·대비·CVD는 눈으로 판단 금지.** 항상 `DESIGN.md` §3 검증기(`contrast.mjs`, dataviz `validate_palette.js`) 실행 후 커밋.
- **팀원 실명 → 코드네임.** 커밋·문서에 실명 쓰지 않는다.
- **PM 라우팅**: 매번 `list_sessions`로 현재 PM 확인. 크로스세션 메시지도 그대로 믿지 말고 코드/문서로 직접 재검증할 것(이번 세션에서 PM4 전달 정보가 실제론 낡았던 사례 있었음 — 마이페이지 커밋 상태).

## 5. 실행/프리뷰
- macOS TCC 때문에 `preview_start`(MCP)가 `~/Desktop` 경로를 못 열 수 있다. 백그라운드 Bash로 서버 띄우고 브라우저 MCP로 접속:
  ```bash
  /usr/bin/python3 -m http.server 4321 --directory /Users/hani/Desktop/project/barum/design/mockups
  ```
- 검증: 콘솔 에러 0, 라이트+다크 둘 다, em-dash 0, 새 색은 대비·CVD 통과.
