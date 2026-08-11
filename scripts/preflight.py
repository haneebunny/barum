#!/usr/bin/env python3
"""푸시 전 검사(preflight): 유출 방지 스캔 + 품질 검사(lint/build/test).

검사만 한다. git add/commit/push 는 절대 대신 실행하지 않고,
모든 검사를 통과했을 때 복사해서 쓸 git 명령만 마지막에 출력한다.

실행:
  ./preflight.sh          (맥/리눅스)
  .\\preflight.ps1         (윈도우)
  옵션 --build 를 주면 프론트 next build 까지 검사한다.

심각도:
  차단(FAIL): 비밀 파일, 하드코딩 키, 민감 문서/대용량 데이터, 문법/lint/build/test 실패.
  경고(WARN): 이메일(PII), 추적 안 된 민감 파일, 대용량 파일, 도구 미설치로 건너뜀.
차단이 하나라도 있으면 종료코드 1 로 끝나고 git 안내를 출력하지 않는다.
"""
from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

# 이 스크립트는 scripts/ 아래에 있고, 그 부모의 부모가 저장소 루트다.
SCRIPT_ROOT = Path(__file__).resolve().parent.parent

# ── 스캔 대상에서 봐줄 경로(오탐 방지). 일부러 커밋하는 파일은 여기에 추가한다. ──
# 예) "docs/공개용_기획서.docx" 를 의도적으로 올릴 거면 아래 집합에 넣는다.
ALLOWLIST = {
    "scripts/preflight.py",  # 검사기 자신은 스캔하지 않는다.
}

# ── 파일명/확장자 기반 규칙 ──
ENV_ALLOW = {".env.example", ".env.sample", ".env.template", ".env.dist", ".env.defaults"}
SECRET_EXT = {".key", ".pem", ".p12", ".pfx", ".keystore", ".jks", ".ppk"}
SECRET_BASENAMES = {"id_rsa", "id_dsa", "id_ecdsa", "id_ed25519", "credentials.json"}
DOC_EXT = {".docx", ".doc", ".hwp", ".hwpx", ".pptx", ".ppt", ".xlsx", ".xls"}
DATA_EXT = {".csv", ".tsv", ".jsonl", ".ndjson", ".parquet", ".db",
            ".sqlite", ".sqlite3", ".zip", ".gz", ".7z", ".bz2", ".tar", ".rar"}

DATA_BLOCK_BYTES = 2 * 1024 * 1024   # 데이터 확장자가 이 크기를 넘으면 차단
BIG_WARN_BYTES = 5 * 1024 * 1024     # 그 외 파일이 이 크기를 넘으면 경고
MAX_CONTENT_BYTES = 1_500_000        # 이보다 큰 파일은 내용(키/이메일) 스캔에서 제외

# ── 내용 기반 규칙: 하드코딩된 비밀(차단) ──
SECRET_PATTERNS = [
    (re.compile(r"sk-(?:proj-)?[A-Za-z0-9_-]{20,}"), "OpenAI API 키"),
    (re.compile(r"AIza[0-9A-Za-z_\-]{35}"), "Google/Gemini API 키"),
    (re.compile(r"AKIA[0-9A-Z]{16}"), "AWS 액세스 키"),
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"), "개인키 블록"),
    (re.compile(r"gh[pousr]_[A-Za-z0-9]{30,}"), "GitHub 토큰"),
    (re.compile(r"github_pat_[A-Za-z0-9_]{20,}"), "GitHub 세분화 토큰"),
    (re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}"), "Slack 토큰"),
]

# ── 내용 기반 규칙: 이메일(PII, 경고) ──
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
IGNORE_EMAIL_DOMAINS = {
    "example.com", "example.org", "example.net", "test.com", "email.com",
    "domain.com", "sentry.io", "anthropic.com", "schema.org", "w3.org",
}
# 이메일 오탐이 많은 파일은 이메일 스캔에서만 제외한다(키 스캔은 유지).
EMAIL_SKIP_FILES = {"package-lock.json", "yarn.lock", "pnpm-lock.yaml"}

# 한 줄에 이 표시가 있으면 그 줄은 비밀/이메일 스캔에서 봐준다.
SUPPRESS_MARKERS = ("preflight-allow", "preflight: allow")


# ── 색/출력 유틸 ──
if os.name == "nt":
    os.system("")  # 윈도우 10+ 콘솔에서 ANSI 색을 켠다.
_USE_COLOR = sys.stdout.isatty() and os.environ.get("NO_COLOR") is None


def _c(code: str, s: str) -> str:
    """ANSI 색 입히기. 색을 못 쓰는 환경이면 그대로 반환한다."""
    return f"\x1b[{code}m{s}\x1b[0m" if _USE_COLOR else s


def green(s): return _c("32", s)
def red(s): return _c("31", s)
def yellow(s): return _c("33", s)
def dim(s): return _c("2", s)
def bold(s): return _c("1", s)


def status(tag: str, name: str, detail: str = "") -> None:
    """검사 한 건의 결과를 한 줄로 출력한다. tag: OK/FAIL/WARN/SKIP."""
    marks = {
        "OK": green("[ OK ]"),
        "FAIL": red("[FAIL]"),
        "WARN": yellow("[WARN]"),
        "SKIP": dim("[SKIP]"),
    }
    line = f"{marks.get(tag, tag)} {name}"
    if detail:
        line += f": {detail}"
    print(line)


def human(n: float) -> str:
    """바이트 크기를 사람이 읽기 쉬운 단위로."""
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.0f}{unit}"
        n /= 1024
    return f"{n:.0f}TB"


# ── git 유틸 ──
def git_out(args, root: Path):
    """git 명령을 실행하고 CompletedProcess 를 돌려준다(출력 캡처)."""
    return subprocess.run(["git", *args], cwd=str(root), capture_output=True, text=True)


def run_streamed(cmd, cwd=None) -> int:
    """외부 명령을 실행하고 출력을 그대로 흘려보낸다. 종료코드를 반환한다.

    도구가 없으면(FileNotFoundError) 127 을 반환한다.
    """
    # 하위 프로세스가 stdout 을 직접 쓰기 전에 우리 버퍼를 비워, 출력 순서가 섞이지 않게 한다.
    sys.stdout.flush()
    sys.stderr.flush()
    try:
        return subprocess.run(cmd, cwd=str(cwd) if cwd else None).returncode
    except FileNotFoundError:
        return 127


def tracked_files(root: Path):
    """git 이 추적/스테이징 중인 파일 목록(저장소 루트 기준 상대경로)."""
    r = git_out(["ls-files"], root)
    return [line for line in r.stdout.splitlines() if line.strip()]


def find_python(root: Path, require_pytest: bool):
    """검사에 쓸 파이썬 인터프리터를 고른다. venv 를 우선한다.

    require_pytest=True 면 pytest 를 import 할 수 있는 것만 고르고,
    없으면 None 을 돌려준다(테스트는 건너뛰기 위함).
    """
    cands = []
    for d in ("backend/venv", "venv", ".venv", "backend/.venv"):
        base = root / d
        for sub in ("bin/python", "bin/python3", "Scripts/python.exe"):
            p = base / sub
            if p.is_file():
                cands.append(str(p))
    cands.append(sys.executable)  # 마지막 폴백: 지금 이 스크립트를 돌리는 파이썬.

    if not require_pytest:
        return cands[0]
    for py in cands:
        try:
            r = subprocess.run([py, "-c", "import pytest"], capture_output=True)
            if r.returncode == 0:
                return py
        except Exception:
            pass
    return None


def is_ignorable_email(addr: str) -> bool:
    """오탐이 뻔한 이메일(placeholder, noreply, 스키마 도메인)인지."""
    a = addr.lower()
    if a.startswith("noreply@") or a.startswith("no-reply@"):
        return True
    domain = a.split("@")[-1]
    return domain in IGNORE_EMAIL_DOMAINS


# ── 유출 방지 스캔 ──
def run_leak_scan(root: Path, blocks: list, warns: list) -> None:
    """추적 파일을 훑어 비밀/키/민감문서/이메일을 찾는다.

    blocks/warns 리스트에 사유 문자열을 채우고, 카테고리별 결과를 출력한다.
    """
    secret_files, docs, big_data, big_misc = [], [], [], []
    key_hits, email_hits = [], []

    for rel in tracked_files(root):
        if rel in ALLOWLIST:
            continue
        p = root / rel
        try:
            size = p.stat().st_size
        except OSError:
            continue
        name = rel.split("/")[-1]
        low = name.lower()
        ext = os.path.splitext(name)[1].lower()

        # 파일명/크기 기반(카테고리 ① ③)
        if name == ".env" or (name.startswith(".env.") and name not in ENV_ALLOW):
            secret_files.append(rel)
        if ext in SECRET_EXT or name in SECRET_BASENAMES or ("service-account" in low and ext == ".json"):
            secret_files.append(rel)
        if ext in DOC_EXT:
            docs.append(rel)
        if ext in DATA_EXT and size > DATA_BLOCK_BYTES:
            big_data.append((rel, size))
        elif ext not in DOC_EXT and size > BIG_WARN_BYTES:
            big_misc.append((rel, size))

        # 내용 기반(카테고리 ② ④)
        if size > MAX_CONTENT_BYTES:
            continue
        try:
            raw = p.read_bytes()
        except OSError:
            continue
        if b"\x00" in raw[:8192]:
            continue  # 바이너리로 판단, 내용 스캔 제외
        text = raw.decode("utf-8", "replace")
        scan_email = name not in EMAIL_SKIP_FILES
        for i, line in enumerate(text.splitlines(), 1):
            if any(m in line for m in SUPPRESS_MARKERS):
                continue
            for pat, kind in SECRET_PATTERNS:
                if pat.search(line):
                    key_hits.append((rel, i, kind))
            if scan_email:
                for m in EMAIL_RE.finditer(line):
                    addr = m.group(0)
                    if not is_ignorable_email(addr):
                        email_hits.append((rel, i, addr))

    secret_files = sorted(set(secret_files))
    docs = sorted(set(docs))

    # ① 비밀 파일(차단)
    if secret_files:
        status("FAIL", "비밀 파일 스캔", f"{len(secret_files)}건")
        for f in secret_files:
            print("        - " + f)
        blocks.append(f"비밀 파일이 추적됨 {len(secret_files)}건")
    else:
        status("OK", "비밀 파일 스캔")

    # ② 하드코딩 키(차단)
    if key_hits:
        status("FAIL", "하드코딩 키 스캔", f"{len(key_hits)}건")
        for f, i, k in key_hits[:30]:
            print(f"        - {f}:{i} ({k})")
        if len(key_hits) > 30:
            print(f"        ...외 {len(key_hits) - 30}건")
        blocks.append(f"하드코딩 키 의심 {len(key_hits)}건")
    else:
        status("OK", "하드코딩 키 스캔")

    # ③ 민감 문서 + 대용량 데이터(차단)
    doc_block = docs + [f for f, _ in big_data]
    if doc_block:
        status("FAIL", "민감 문서·대용량 데이터 스캔", f"{len(doc_block)}건")
        for f in docs:
            print("        - 문서: " + f)
        for f, s in big_data:
            print(f"        - 대용량데이터: {f} ({human(s)})")
        blocks.append(f"민감 문서/대용량 데이터 {len(doc_block)}건")
    else:
        status("OK", "민감 문서·대용량 데이터 스캔")

    # 추적 안 된 민감 파일(경고): 실수로 add 하기 전에 알려준다.
    unt = untracked_sensitive(root)
    if unt:
        status("WARN", "추적 안 된 민감 파일", f"{len(unt)}건 (실수로 add 하지 마세요)")
        for f in unt:
            print("        - " + f)
        warns.append(f"추적 안 된 민감 파일 {len(unt)}건")

    # 대용량 파일(경고)
    if big_misc:
        status("WARN", "대용량 파일", f"{len(big_misc)}건")
        for f, s in big_misc:
            print(f"        - {f} ({human(s)})")
        warns.append(f"대용량 파일 {len(big_misc)}건")

    # ④ 이메일 PII(경고)
    if email_hits:
        status("WARN", "이메일(PII) 스캔", f"{len(email_hits)}건 (경고, 차단 아님)")
        for f, i, a in email_hits[:20]:
            print(f"        - {f}:{i} {a}")
        if len(email_hits) > 20:
            print(f"        ...외 {len(email_hits) - 20}건")
        warns.append(f"이메일 노출 {len(email_hits)}건")
    else:
        status("OK", "이메일(PII) 스캔")


def untracked_sensitive(root: Path):
    """아직 추적 안 됐지만(무시된 것 제외) 민감해 보이는 파일 목록."""
    r = git_out(["status", "--porcelain", "--untracked-files=all"], root)
    out = []
    for line in r.stdout.splitlines():
        if not line.startswith("??"):
            continue
        rel = line[3:].strip().strip('"')
        name = rel.split("/")[-1]
        low = name.lower()
        ext = os.path.splitext(name)[1].lower()
        sensitive = (
            name == ".env"
            or (name.startswith(".env.") and name not in ENV_ALLOW)
            or ext in SECRET_EXT
            or ext in DOC_EXT
            or name in SECRET_BASENAMES
            or ("service-account" in low and ext == ".json")
        )
        if sensitive:
            out.append(rel)
    return out


# ── 품질 검사 ──
def check_backend_compile(root: Path, blocks: list) -> None:
    """백엔드 파이썬 문법 검사(compileall). 실패하면 차단."""
    targets = [d for d in ("backend/src", "backend/scripts", "backend/tests") if (root / d).is_dir()]
    if not targets:
        status("SKIP", "backend 문법검사", "대상 디렉토리 없음")
        return
    py = find_python(root, require_pytest=False)
    print(dim(f"      · 실행: {py} -m compileall {' '.join(targets)}"))
    rc = run_streamed([py, "-m", "compileall", "-q", *targets], cwd=root)
    if rc == 0:
        status("OK", "backend 문법검사")
    else:
        status("FAIL", "backend 문법검사", "문법 오류(compileall)")
        blocks.append("backend 문법 오류")


def check_backend_pytest(root: Path, blocks: list, warns: list) -> None:
    """백엔드 pytest. pytest 를 못 찾으면 건너뛴다(차단 아님)."""
    if not (root / "backend" / "tests").is_dir():
        status("SKIP", "backend pytest", "tests 없음")
        return
    py = find_python(root, require_pytest=True)
    if not py:
        status("SKIP", "backend pytest", "pytest 설치된 파이썬 못 찾음(건너뜀, 차단 아님)")
        warns.append("pytest 미설치로 테스트 건너뜀")
        return
    print(dim(f"      · 실행: {py} -m pytest -q backend/tests"))
    rc = run_streamed([py, "-m", "pytest", "-q", "backend/tests"], cwd=root)
    if rc == 0:
        status("OK", "backend pytest")
    else:
        status("FAIL", "backend pytest", "테스트 실패")
        blocks.append("backend 테스트 실패")


def _frontend_ready(root: Path, warns: list, label: str):
    """프론트 검사 전 공통 점검. (npm 경로, frontend 경로) 또는 None 을 반환."""
    fe = root / "frontend"
    if not (fe / "package.json").is_file():
        status("SKIP", label, "frontend 없음")
        return None
    npm = shutil.which("npm")
    if not npm:
        status("SKIP", label, "npm 없음(건너뜀, 차단 아님)")
        warns.append("npm 미설치로 프론트 검사 건너뜀")
        return None
    if not (fe / "node_modules").is_dir():
        status("SKIP", label, "node_modules 없음. `cd frontend && npm install` 필요(건너뜀, 차단 아님)")
        warns.append("frontend node_modules 없음")
        return None
    return npm, fe


def check_frontend_lint(root: Path, blocks: list, warns: list) -> None:
    """프론트 eslint(npm run lint). 실패하면 차단."""
    ready = _frontend_ready(root, warns, "frontend lint")
    if not ready:
        return
    npm, fe = ready
    print(dim("      · 실행: npm run lint"))
    rc = run_streamed([npm, "run", "lint"], cwd=fe)
    if rc == 0:
        status("OK", "frontend lint")
    else:
        status("FAIL", "frontend lint", "eslint 오류")
        blocks.append("frontend lint 실패")


def check_frontend_build(root: Path, blocks: list, warns: list, enabled: bool) -> None:
    """프론트 next build. --build 를 줬을 때만 실행한다."""
    if not (root / "frontend" / "package.json").is_file():
        return
    if not enabled:
        status("SKIP", "frontend build", "기본 생략. 필요할 때 --build 로 실행")
        return
    ready = _frontend_ready(root, warns, "frontend build")
    if not ready:
        return
    npm, fe = ready
    print(dim("      · 실행: npm run build (시간이 걸립니다)"))
    rc = run_streamed([npm, "run", "build"], cwd=fe)
    if rc == 0:
        status("OK", "frontend build")
    else:
        status("FAIL", "frontend build", "next build 실패")
        blocks.append("frontend build 실패")


# ── 마지막 안내 ──
def print_git_instructions(root: Path) -> None:
    """모든 검사 통과 시, 복사해서 쓸 git 명령을 출력한다. 실행은 하지 않는다."""
    branch = (git_out(["rev-parse", "--abbrev-ref", "HEAD"], root).stdout.strip() or "HEAD")
    up = git_out(["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"], root)
    has_upstream = up.returncode == 0 and up.stdout.strip()
    push_cmd = "git push" if has_upstream else f"git push -u origin {branch}"

    print()
    print(bold(green("모든 검사 통과. 아래 명령을 복사해서 쓰세요.")))
    print(dim("(이 스크립트는 git 명령을 대신 실행하지 않습니다.)"))
    print()
    print("  git status")
    print("  git add -A                       # 전체 스테이징. 특정 파일만: git add <경로>")
    print('  git commit -m "타입: 한 줄 설명"')
    print(f"  {push_cmd}")
    print()
    print(dim("커밋 규칙: 한국어로, 접두어 feat/fix/docs/chore/refactor 중 하나, em-dash(—) 쓰지 않기."))
    print(dim('예:  git commit -m "feat: 푸시 전 검사 스크립트 추가"'))


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="preflight",
        description="푸시 전 검사: 유출 방지 스캔 + lint/test(+선택 build). 통과 시 git 명령을 안내한다.",
    )
    parser.add_argument("--build", action="store_true", help="프론트 next build 까지 검사한다(느림).")
    args = parser.parse_args()

    # 파이프/파일로 리다이렉트해도(비 tty) print 가 줄 단위로 나와 하위 프로세스 출력과 순서가 맞도록.
    try:
        sys.stdout.reconfigure(line_buffering=True)
    except (AttributeError, ValueError):
        pass

    root = SCRIPT_ROOT
    if git_out(["rev-parse", "--show-toplevel"], root).returncode != 0:
        print(red("git 저장소가 아닙니다. 저장소 안에서 실행하세요."))
        return 2

    print(bold("preflight: 푸시 전 검사"))
    print(dim(f"repo: {root}"))
    print()

    blocks: list = []
    warns: list = []

    print(bold("[1] 유출 방지 스캔"))
    run_leak_scan(root, blocks, warns)
    print()

    print(bold("[2] 품질 검사"))
    check_backend_compile(root, blocks)
    check_backend_pytest(root, blocks, warns)
    check_frontend_lint(root, blocks, warns)
    check_frontend_build(root, blocks, warns, enabled=args.build)

    build_hint = "빌드 검사는 건너뜀. 배포 전이나 프론트 변경이 크면:  ./preflight.sh --build   (윈도우: .\\preflight.ps1 --build)"

    print()
    print(dim("─" * 60))
    if blocks:
        print(bold(red(f"차단: {len(blocks)}건. 아래를 해결하고 다시 실행하세요.")))
        for b in blocks:
            print("  - " + b)
        if warns:
            print(yellow(f"경고 {len(warns)}건도 확인하세요."))
        if not args.build:
            print(dim(build_hint))
        return 1

    if warns:
        print(yellow(f"경고 {len(warns)}건 (차단 아님). 위 내용을 확인하세요."))
    if not args.build:
        print(dim(build_hint))
    print_git_instructions(root)
    return 0


if __name__ == "__main__":
    sys.exit(main())
