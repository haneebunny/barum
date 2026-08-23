# 개발 환경 메모

barum 코드 버그가 아니라 Claude Code 세션 환경/도구 쪽 문제라, 어느 세션에서든 다시 겪을 수 있는
것만 짧게 남긴다. 코드로 고칠 수 있는 게 아니라 재현 조건과 우회법 위주.

## 프론트 dev 서버 프리뷰 launcher가 getcwd 오류로 죽는다 (2026-08-23)

`.claude/launch.json`의 `frontend` named launcher(`preview_start({name: "frontend"})`)가
아래 오류로 시작 직후 죽는 경우가 있다.

```
shell-init: error retrieving current directory: getcwd: cannot access parent directories: Operation not permitted
/bin/bash: /Users/hani/Desktop/project/barum/frontend/scripts/dev.sh: Operation not permitted
```

`frontend/scripts/dev.sh`는 이미 "런처 셸의 cwd가 접근 불가일 수 있다"는 걸 알고 첫 줄에서
절대경로로 `cd`하는데, 이 오류는 그보다 먼저 bash 자체의 shell-init 단계에서 난다. 즉 스크립트
본문이 실행되기도 전에 실패한다 — 스크립트를 고쳐도 해결 안 된다.

**같은 스크립트를 Claude Code의 Bash 도구로 직접 돌리면 문제없이 실행된다.** 즉 dev.sh나 barum
코드 문제가 아니라, `preview_start`가 named launcher의 자식 프로세스를 스폰하는 방식 쪽에서
생기는 것으로 보인다(세션마다 재현 여부가 다를 수 있음, 원인 규명은 여기서 안 함 — harness 영역).

### 우회법
1. Bash 도구로 dev 서버를 직접 띄운다(백그라운드로):
   ```bash
   cd frontend && export NVM_DIR="$HOME/.nvm" && . "$NVM_DIR/nvm.sh" && nvm use 22 && npm run dev
   ```
2. 서버가 뜬 뒤(`✓ Ready in ...` 로그 확인), `preview_start`를 **`name`이 아니라 `url` 모드**로
   붙인다: `preview_start({url: "http://localhost:3000"})`.
3. **확인이 끝나면 백그라운드 Bash 작업을 반드시 정리한다**(`TaskStop` 등). 안 그러면 포트 3000이
   계속 점유돼서, 다음에 다른 세션이 정상적인 named launcher로 `frontend`를 띄우려 할 때 충돌한다.

관련: 팀 메모리 `barum-bug-lead-role`(그그, 2026-08-23 재현).
