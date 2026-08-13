# Barum Frontend Page Ownership

## 목적

두 명이 동시에 Frontend를 수정하면서 발생할 수 있는
중복 작업, CSS 충돌, Shared Component 변경 충돌을 방지한다.

Ownership은 해당 개발자만 코드를 수정할 수 있다는 의미가 아니라
해당 영역의 최종 책임자를 의미한다.

---

# Developer A (GitHub: guruggurug)

## Page Ownership

- Home (`app/page.tsx`)
- Inspect / 새 검사 (`app/inspect`)
- MyPage (`app/mypage`)

## Shared UI Ownership

Developer A는 Shared UI Owner를 담당한다.

주요 책임:

- Global Style (`app/globals.css`), 그 안의 `:root` 토큰 블록 포함
  (`design/mockups/DESIGN.md` §4 값과 동기화)
- Typography
- AppShell (`components/AppShell`)
- ThemeToggle (`components/ThemeToggle`)
- Shared Button / Input / Badge / Card / Modal 등 공통 Component

Shared UI 변경 요청을 검토하고 전체 페이지에 적용할지 결정한다.

---

# Developer B (GitHub: haneebunny)

## Page Ownership

- Report (`app/report/[id]`)
- Generate / 콘텐츠 생성

주요 책임:

- 리포트 화면
- 판정 결과 표시
- 근거 표시
- 수정 권고안 UI
- 콘텐츠 생성 화면
- 생성 결과 Preview
- 해당 페이지의 Responsive UI

> **Generate 페이지는 아직 구현 전이다** (`frontend/app/`에 코드 없음, `design/mockups/barum-content.html` 목업만 존재).
> 착수 전에 CLAUDE.md §A 착수 규칙(인터뷰 먼저)을 따른다. 이 문서는 "누가 만들지"만 정하고
> "무엇을 만들지"는 정하지 않는다.

페이지 전용 Component와 Style은 자유롭게 수정할 수 있다.

Shared UI 변경이 필요한 경우 Developer A와 먼저 확인한다.

---

# Shared Area

다음 영역은 특정 페이지가 아닌 제품 전체에 영향을 미친다.

- Global CSS (`app/globals.css`), `:root` 토큰 블록 포함
- Font
- AppShell / Layout
- Shared Components

Shared Area는 Developer A가 최종 관리한다.

Developer B가 Shared Area에서 문제를 발견하면 다음 형태로 전달한다.

### Shared UI Change Request

**대상**

예: Primary Button

**발견 화면**

예: Report

**현재 문제**

문제를 구체적으로 설명

**제안**

필요한 변경 설명

**영향 예상**

다른 페이지에 영향을 줄 가능성 설명

---

# Cross QA

자신이 구현한 페이지를 자신만 QA하지 않는다.

Developer A 구현 페이지:
→ Developer B가 Cross QA

Developer B 구현 페이지:
→ Developer A가 Cross QA

Cross QA 이후 담당자가 수정한다.

---

# Integration QA

모든 페이지 작업 완료 후 두 사람이 함께 다음 사용자 흐름을 확인한다.

Home
→ Inspect
→ Report
→ 수정 / 재검사
→ Generate

그리고:

Home
→ MyPage
→ 검사 이력

흐름을 확인한다.

Integration QA에서는 개별 페이지보다
페이지 간 일관성과 연결을 중점적으로 확인한다.
