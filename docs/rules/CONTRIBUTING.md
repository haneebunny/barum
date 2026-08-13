# Barum Frontend Contribution Guide

바름 프론트엔드를 2명이 병렬 개발할 때 코드 충돌과
페이지 간 디자인 불일치를 최소화하기 위한 작업 규칙이다.

현재는 신규 프론트엔드를 처음부터 구축하는 단계가 아니라,
기존 구현을 기반으로 각 페이지를 고도화하고 QA하는 단계다.

담당자는 [PAGE_OWNERSHIP.md](./PAGE_OWNERSHIP.md)를 따른다.

---

## 1. 기본 원칙

### 1.1 담당 페이지 중심으로 작업한다

각 개발자는 `PAGE_OWNERSHIP.md`에 정의된 자신의 담당 페이지를
우선적으로 수정한다.

담당자가 아닌 페이지의 코드는 특별한 이유가 없다면 수정하지 않는다.

다른 페이지에서 문제를 발견한 경우 직접 수정하기보다 담당자에게 전달한다.

### 1.2 Shared 영역과 Page 영역을 구분한다

다음은 Shared 영역으로 취급한다.

- Global CSS (`app/globals.css`), 그 안의 `:root` 토큰 블록 포함
- Font 설정
- AppShell (`components/AppShell`)
- ThemeToggle (`components/ThemeToggle`)
- 공통 Button / Input / Badge / Card / Modal 등
- 전체 Layout / App Shell

Shared 영역에는 별도의 Owner를 둔다.

페이지 담당자가 Shared 영역 변경이 필요하다고 판단하면
가능하면 직접 수정하지 않고 Shared UI Owner에게 요청한다.

### 1.3 페이지 문제를 해결하기 위해 Global Style을 덮어쓰지 않는다

금지 예시:

```css
.card {
  padding: 24px;
}

h2 {
  font-size: 24px;
}

button {
  height: 48px;
}
```

특정 페이지에서만 필요한 경우 page scope를 사용한다.

권장 예시:

```css
.report-result-card {
  padding: var(--space-6);
}

.report-section-title {
  ...
}
```

공통 변경이 필요하다면 Shared UI 변경으로 처리한다.

---

## 2. Design Token 규칙

색상, Typography, Spacing, Radius 등 공통 값은
`app/globals.css`의 `:root` 토큰 블록(파일 상단 "토큰 단일 소스" 주석 참조)에 정의된
CSS 변수만 사용한다. 별도 `tokens.css` 파일은 두지 않는다. 값이 늘어나
파일이 나뉘면 그때 분리 여부를 다시 논의한다.

`:root` 블록의 색상 값은 [design/mockups/DESIGN.md](../design/mockups/DESIGN.md) §4 확정 팔레트와
항상 동일해야 한다. 둘이 어긋나면 DESIGN.md가 맞다.

페이지 내부에서 다음과 같은 값을 임의로 계속 추가하지 않는다.

- 새로운 Brand Color
- 새로운 Semantic Color
- 임의 Font Size
- 임의 Border Radius
- 임의 Shadow
- 기존 spacing scale과 관계없는 여백

필요한 Token이 없다면 임의 값을 추가하기 전에
공통 Token으로 추가할 가치가 있는지 확인한다. 새 색·새 상태색이 필요하면
루트 `CLAUDE.md` §F에 따라 혼자 정하지 않고 멈춰서 선택지를 제시하고 승인을 받는다.

---

## 3. Shared Component 수정 규칙

Shared Component를 수정하기 전에 다음을 확인한다.

1. 현재 문제는 특정 페이지에만 존재하는가?
2. 다른 페이지에서도 동일한 문제가 발생하는가?
3. 수정하면 다른 페이지에 어떤 영향을 주는가?

특정 페이지 문제라면 Page Component에서 해결한다.
제품 전체의 문제라면 Shared Component를 수정한다.
Shared Component 변경 시 관련된 모든 페이지를 확인한다.

---

## 4. Git 작업 규칙

작업 시작 전 최신 main을 기준으로 작업한다.

페이지별 작업 브랜치를 사용한다. 예:

- `feature/home`
- `feature/inspect`
- `feature/report`
- `feature/generate`
- `feature/mypage`

또는 담당 영역별 브랜치를 사용한다.

한 번에 지나치게 많은 변경을 하나의 commit에 넣지 않는다.

권장:

```text
[report] result card hierarchy 수정
[report] mobile layout 수정
[shared] primary button spacing 수정
```

비권장:

```text
UI 전체 수정
```

커밋 태그는 페이지명(`home`/`inspect`/`report`/`generate`/`mypage`) 또는 `shared`를 사용한다.

Shared 변경과 Page 변경은 가능하면 별도 commit으로 분리한다.

이 저장소는 여러 세션이 같은 워크트리를 공유하므로, 브랜치 작업은
루트 `CLAUDE.md` §G(공유 워크트리 협업 규칙)를 따른다. 메인 워크트리에서
`git checkout <다른 브랜치>`로 HEAD를 옮기지 않는다.

---

## 5. Merge 전 확인

담당 페이지 작업 완료 후 다음을 확인한다.

- 기능이 정상 동작하는가
- Console Error가 없는가
- 기존 기능이 깨지지 않았는가
- Design System(DESIGN.md)을 따르는가
- Desktop에서 정상인가
- Mobile에서 정상인가
- Shared Component를 불필요하게 수정하지 않았는가
- 다른 페이지에 영향을 줄 CSS를 추가하지 않았는가

자세한 항목은 [QA_CHECKLIST.md](./QA_CHECKLIST.md)를 따른다.

Shared 영역을 수정했다면 관련된 모든 페이지를 확인한다.

---

## 6. 기획 변경 금지

Frontend 구현 과정에서 다음을 임의로 변경하지 않는다.

- 서비스 기능 범위
- 사용자 Flow
- 규제 판정 로직
- 위반 / 검토필요 체계
- 위반유형 명칭 (1호 의약품 오인 / 2호 기능성 오인 / 5호 거짓·과장·기만 등, `reference/violation_types`에 정의된 값)
- 판정 카드에 표시되는 필드 (`span`, 위반유형, 근거 조항, 위험도, 설명 — 백엔드 `CheckReport`와 1:1)
- 요금제 정책
- 콘텐츠 생성 정책
- 법적 고지의 의미

기획 변경이 필요해 보이는 경우 구현과 분리하여 제안한다.

---

## 7. 충돌 발생 시 우선순위

판단 기준이 충돌하면 다음 순서를 따른다.

1. 최신 프로젝트 기획서 / 확정 요구사항 (`PROJECT.md`, `docs/기획서_v1.3_초안.md`)
2. `design/mockups/DESIGN.md` (확정 Brand / Design System)
3. Shared Component 규칙
4. 페이지별 확정 디자인
5. 개별 개발자의 판단

불명확한 경우 임의로 새로운 규칙을 만들지 않는다.
