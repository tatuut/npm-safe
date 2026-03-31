"""npm-safe チェッカー本体。
package.json / package-lock.json / pnpm-lock.yaml をチェックして
危険パッケージが含まれていないか判定する。

危険パッケージの定義は vuls.json から読み込む。

3段階判定:
  - dangerous → DANGER（ブロック、exit 1）
  - safe → サイレント通過
  - それ以外 → WARN（未確認バージョン、exit 2 → シェルで対話プロンプト）

前提: Python 3.8+
サードパーティパッケージ不要（json, sys, os, re, subprocess のみ使用）

使い方:
  python npm-safe-check.py                          # ファイルチェック（既存依存）
  python npm-safe-check.py --check-args pkg1 pkg2   # CLI引数チェック
"""
import json
import sys
import os
import re
import subprocess

# === 危険パッケージ定義を vuls.json から読み込み ===

def _load_vuls():
    """vuls.json を読み込んで BLOCKED_EXACT, BLOCKED_ALL, SAFE_EXACT を構築する。"""
    vuls_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "vuls.json")
    if not os.path.exists(vuls_path):
        print(f"ERROR: {vuls_path} が見つかりません", file=sys.stderr)
        sys.exit(2)
    with open(vuls_path, encoding="utf-8") as f:
        vuls = json.load(f)

    blocked_exact = {}
    safe_exact = {}
    for name, info in vuls.get("exact", {}).items():
        blocked_exact[name] = set(info.get("dangerous", info.get("versions", [])))
        safe_exact[name] = set(info.get("safe", []))

    blocked_all = set(vuls.get("all", {}).keys())

    return blocked_exact, blocked_all, safe_exact


BLOCKED_EXACT, BLOCKED_ALL, SAFE_EXACT = _load_vuls()

found_danger = []
found_warn = []


def _check_entry(source, name, ver):
    if not name:
        return
    if name in BLOCKED_ALL:
        found_danger.append(f"[{source}] {name}@{ver} (全バージョン危険)")
        return
    if name in BLOCKED_EXACT:
        if ver in BLOCKED_EXACT[name]:
            found_danger.append(f"[{source}] {name}@{ver} (危険バージョン)")
        elif ver != "?" and ver != "*" and name in SAFE_EXACT:
            if ver not in SAFE_EXACT[name]:
                safe_list = ", ".join(sorted(SAFE_EXACT[name]))
                found_warn.append(
                    f"[{source}] {name}@{ver} (未確認バージョン。"
                    f"安全確認済み: {safe_list})"
                )


def check_args(args):
    """コマンドライン引数のパッケージ名をチェック。
    npm install foo bar@1.2.3 @scope/pkg@2.0.0 のような引数を解析する。
    """
    for arg in args:
        if arg.startswith("-"):
            continue
        # URL・ローカルパス・git依存はスキップ
        if arg.startswith((".", "/", "http:", "https:", "git:", "github:", "file:")):
            continue
        # name@version をパース
        if arg.startswith("@"):
            # スコープ付き: @scope/pkg または @scope/pkg@version
            if arg.count("@") >= 2:
                idx = arg.rindex("@")
                name, ver = arg[:idx], arg[idx + 1:]
            else:
                name, ver = arg, "*"
        elif "@" in arg:
            name, ver = arg.rsplit("@", 1)
        else:
            name, ver = arg, "*"
        _check_entry("引数", name, ver)


def check_package_json(path):
    """package.json の直接依存をチェック。"""
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as f:
        pkg = json.load(f)
    for section in ("dependencies", "devDependencies", "optionalDependencies"):
        for name, ver in pkg.get(section, {}).items():
            if name in BLOCKED_ALL:
                found_danger.append(f"[{path}] {name} (全バージョン危険)")
                continue
            if name in BLOCKED_EXACT:
                clean_ver = ver.lstrip("^~>=< ")
                _check_entry(path, name, clean_ver)


def check_package_lock(path):
    """package-lock.json の直接+間接依存をチェック。"""
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as f:
        lock = json.load(f)
    # npm v2+ packages 形式
    for pkg_path, info in lock.get("packages", {}).items():
        name = info.get("name", "")
        if not name and pkg_path:
            name = pkg_path.replace("node_modules/", "").split("node_modules/")[-1]
        _check_entry(path, name, info.get("version", ""))
    # npm v1 dependencies 形式
    def walk(deps):
        for name, info in deps.items():
            _check_entry(path, name, info.get("version", ""))
            if "dependencies" in info:
                walk(info["dependencies"])
    if "dependencies" in lock:
        walk(lock["dependencies"])


def check_pnpm_lock(path):
    """pnpm-lock.yaml をテキスト解析してチェック（PyYAML不要）。"""
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as f:
        content = f.read()
    pattern = re.compile(r"['\"]?/?(@?[a-zA-Z0-9._-]+(?:/@?[a-zA-Z0-9._-]+)?)@(\d+\.\d+\.\d+)")
    for match in pattern.finditer(content):
        _check_entry(path, match.group(1), match.group(2))


def check_installed():
    """インストール済みパッケージを npm list / pnpm list でチェック（1回実行）。"""
    if not os.path.exists("node_modules"):
        return
    pm = "pnpm" if os.path.exists("pnpm-lock.yaml") else "npm"
    try:
        r = subprocess.run([pm, "list", "--all", "--json"],
                           capture_output=True, text=True, timeout=30)
        if r.returncode not in (0, 1):  # npm list returns 1 for missing peers
            return
        tree = json.loads(r.stdout)
        _walk_installed(tree.get("dependencies", {}))
    except (subprocess.TimeoutExpired, FileNotFoundError, json.JSONDecodeError):
        pass


def _walk_installed(deps):
    """npm list --json の依存ツリーを再帰的にチェック。"""
    for name, info in deps.items():
        ver = info.get("version", "?")
        _check_entry("installed", name, ver)
        if "dependencies" in info:
            _walk_installed(info["dependencies"])


# === 実行 ===
if len(sys.argv) > 1 and sys.argv[1] == "--check-args":
    check_args(sys.argv[2:])
else:
    check_package_json("package.json")
    check_package_lock("package-lock.json")
    check_pnpm_lock("pnpm-lock.yaml")
    check_installed()

# 結果出力
# exit 0: 安全、exit 1: 危険（ブロック）、exit 2: 未確認あり（シェルで対話）
exit_code = 0

if found_danger:
    for f in sorted(set(found_danger)):
        print(f"DANGER: {f}")
    exit_code = 1

if found_warn:
    for w in sorted(set(found_warn)):
        print(f"WARN: {w}")
    if exit_code == 0:
        exit_code = 2  # DANGER がなく WARN だけの場合

if not found_danger and not found_warn:
    print("OK")

sys.exit(exit_code)
