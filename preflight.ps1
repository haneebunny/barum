# 윈도우용 런처. 검사 로직은 scripts\preflight.py 에 있다.
# 이 파일은 파이썬을 찾아 그 스크립트를 실행할 뿐이다. 인자(예: --build)는 그대로 넘긴다.
# 실행이 막히면(실행정책) 한 번만:  powershell -ExecutionPolicy Bypass -File .\preflight.ps1
$ErrorActionPreference = "Stop"

$here = Split-Path -Parent $MyInvocation.MyCommand.Path

# 파이썬 자동 탐색: venv 를 우선, 없으면 python / py 런처.
$candidates = @(
  (Join-Path $here "backend\venv\Scripts\python.exe"),
  (Join-Path $here "venv\Scripts\python.exe"),
  (Join-Path $here ".venv\Scripts\python.exe")
)

$py = $null
foreach ($c in $candidates) {
  if (Test-Path $c) { $py = $c; break }
}
if (-not $py) {
  $cmd = Get-Command python -ErrorAction SilentlyContinue
  if ($cmd) { $py = $cmd.Source }
  else {
    $cmd = Get-Command py -ErrorAction SilentlyContinue
    if ($cmd) { $py = "py" }
  }
}
if (-not $py) {
  Write-Error "python 을 찾을 수 없습니다. 파이썬을 설치한 뒤 다시 실행하세요."
  exit 1
}

& $py (Join-Path $here "scripts\preflight.py") @args
exit $LASTEXITCODE
