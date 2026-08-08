#!/usr/bin/env bash
# 프리뷰 런처. Claude.app 환경의 npm은 node 20.11(npm 11 미지원)에 묶여 있어
# Next 16이 안 뜬다. nvm으로 node 22를 강제하고 frontend에서 dev 서버를 띄운다.
# 런처 셸의 cwd가 접근 불가일 수 있어 맨 먼저 절대경로로 cd 한다.
cd /Users/hani/Desktop/project/vericops/frontend || exit 1
set -euo pipefail
export NVM_DIR="$HOME/.nvm"
# shellcheck disable=SC1091
. "$NVM_DIR/nvm.sh"
nvm use 22 >/dev/null
exec npm run dev
