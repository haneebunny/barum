# AGENTS.md: barum 협업 규칙

> 작업 규칙(코드 취향·인터뷰·디자인)은 [CLAUDE.md](CLAUDE.md), 진행상황은 [ROADMAP.md](ROADMAP.md), 프로젝트 정의는 [PROJECT.md](PROJECT.md). 이 문서는 **Git 협업 규칙**을 담는다.

@CLAUDE.md

> ⚠ 위 `@CLAUDE.md`는 이 문서의 스코프(Git 협업 규칙)를 넓히려는 게 아니다. `AGENTS.md`만 자동으로 읽는 에이전트 툴(예: 안티그래비티)도 `CLAUDE.md`의 작업 규칙(인터뷰 우선·코드 취향·디자인 규칙)을 같이 로드하게 하기 위한 import다. Claude Code는 `CLAUDE.md`를 별도로 직접 읽으므로 중복 로드된다.

## 🌿 협업 / Git 규칙 (항상 지킬 것)

> 이 규칙은 **코드를 커밋·푸시할 때마다 항상 적용**됩니다. 기능 종류와 상관없이 예외 없이 따릅니다.

### 브랜치 전략
- **`main`**: 배포·최종 완성본 브랜치. **직접 커밋/푸시 절대 금지.**
- **`feature/...`**: 기능 개발용 독립 브랜치. 모든 작업은 여기서 하고, PR을 거쳐 `main`에 합칩니다.
- **브랜치 생성 필수**: 새로운 개발 작업을 처음 시작할 때는 무조건 브랜치를 새로 따고 시작합니다.
- **단계별 브랜치 순환**: 한 단계 진행할 때마다 새로운 브랜치를 사용하며, 다음 단계 브랜치를 따기 전 기존 브랜치의 작업물은 반드시 **조장의 허락을 받아 원격 push 및 PR(Pull Request)까지 완료**해 둡니다.
- 새 작업 시작 전 항상 최신 `main`을 받은 상태에서 브랜치를 팝니다.
  ```bash
  git checkout main
  git pull origin main 
  git checkout -b feature/fe-review-queue   # 새 브랜치 만들고 이동
  ```

### 브랜치 이름 규칙
형식: `접두어/파트-작업내용` (소문자, 단어 구분은 하이픈 `-`)

| 용도 | 형식 | 예시 |
|---|---|---|
| 프론트 기능 | `feature/fe-기능명` | `feature/fe-report-screen`, `feature/fe-styleguide` |
| 백엔드 기능 | `feature/be-기능명` | `feature/be-api-skeleton`, `feature/be-reference-pack` |
| 버그 수정 | `fix/fe-버그명` / `fix/be-버그명` | `fix/be-prescreen-parse` |

### 커밋 컨벤션
형식: `Type: 요약` (요약은 한글 가능). 제목만 보고 무슨 변화인지 알 수 있게 씁니다.

| 타입 | 설명 |
|---|---|
| `feat` | 새로운 기능 추가 |
| `fix` | 버그 수정 |
| `docs` | 문서 수정 (README, 가이드 등) |
| `style` | 포맷팅·세미콜론 등 (로직 변경 없음) |
| `refactor` | 기능 변화 없는 구조 개선 |
| `chore` | 빌드·패키지 설정·`.gitignore` 등 |

예: `feat: 검토 큐 화면 UI 구현` / `fix: prescreen 라벨 파싱 에러 수정`

### 커밋 & 푸시 & PR 흐름

```bash
git status              # 변경 파일 확인
git add .
git commit -m "feat: 검토 큐 화면 UI 구현"
git push origin feature/fe-review-queue   # 내 브랜치로 푸시 (main 아님!)
```

그다음 GitHub에서 `Compare & pull request` → 리뷰어에 **`haneebunny`** 지정 → 작업 내용 요약 작성 → `Create pull request` → **조장에게 알립니다.**

### ⚠️ 필수 주의사항
- 🚫 **`main`에 직접 푸시 절대 금지.** 반드시 `feature/` 브랜치 → PR → merge 경로만 사용합니다.
- 🚫 **사용자 사전 승인 없는 원격 push 및 PR 금지.** 로컬 커밋 이후 `git push` 명령어나 PR 생성 동작은 **반드시 사용자의 명시적인 허락(허용 답변)을 채팅창에서 먼저 획득한 후 실행**해야 합니다. 에이전트 단독 판단으로 원격지에 변경 사항을 푸시하지 마십시오.
- 📦 **의존성 추가 시 매니페스트를 반드시 커밋에 포함합니다.**
  - 프론트(npm): `package.json` + `package-lock.json`
  - 백엔드(pip): `backend/requirements.txt` (의존성 추가하면 `pip freeze > requirements.txt`로 갱신해 커밋). (지금은 LLM+RAG 구조라 무거운 학습용 ML 의존성 없음. 나중에 생기면 그때 `requirements-ml.txt`로 분리 검토.)
  - (아나콘다/conda 사용자는 pull 받은 뒤 추가된 패키지를 수동 설치해야 합니다.)
