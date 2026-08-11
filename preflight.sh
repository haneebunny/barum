#!/usr/bin/env bash
# 맥/리눅스용 런처. 검사 로직은 scripts/preflight.py 에 있다.
# 이 파일은 파이썬을 찾아 그 스크립트를 실행할 뿐이다. 인자(예: --build)는 그대로 넘긴다.
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# 파이썬 자동 탐색: venv 를 우선, 없으면 시스템 python3/python.
pick_py() {
  for c in "$here/backend/venv/bin/python" "$here/venv/bin/python" "$here/.venv/bin/python"; do
    [ -x "$c" ] && { echo "$c"; return; }
  done
  if command -v python3 >/dev/null 2>&1; then echo "python3"; return; fi
  if command -v python  >/dev/null 2>&1; then echo "python"; return; fi
  echo ""
}

py="$(pick_py)"
if [ -z "$py" ]; then
  echo "python 을 찾을 수 없습니다. 파이썬을 설치한 뒤 다시 실행하세요."
  exit 1
fi

exec "$py" "$here/scripts/preflight.py" "$@"
