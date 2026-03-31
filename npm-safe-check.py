"""npm-safe チェッカー本体。
package.json / package-lock.json / pnpm-lock.yaml をチェックして
危険パッケージが含まれていないか判定する。

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

# === 危険パッケージ定義 ===

# 特定バージョンが危険（正規パッケージの侵害版）
BLOCKED_EXACT = {
    "axios": {"1.14.1", "0.30.4"},
    "@solana/web3.js": {"1.95.6", "1.95.7"},
    "@lottiefiles/lottie-player": {"2.0.8"},
}

# 全バージョンが危険（タイポスクワッティング・完全偽装）
BLOCKED_ALL = {
    "axois", "axi0s", "solana-transaction-toolkit", "solana-stable-web-huks",
    "crypto-encrypt-ts", "lottie-plyer", "loadsh", "expres", "reactjs-core",
    "node-hide-console-windows", "eslint-plugin-prettier-format",
    "prettier-plugin-xml2", "jest-cov-reporter", "event-handle-package",
    "yolowide", "icloud-cod", "warbeast2000", "kodaborat", "bb-templates",
}

found = []


def _check_entry(source, name, ver):
    if not name:
        return
    if name in BLOCKED_ALL:
        found.append(f"[{source}] {name}@{ver} (全バージョン危険)")
    if name in BLOCKED_EXACT and ver in BLOCKED_EXACT[name]:
        found.append(f"[{source}] {name}@{ver} (危険バージョン)")


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
                found.append(f"[{path}] {name} (全バージョン危険)")
            if name in BLOCKED_EXACT:
                clean_ver = ver.lstrip("^~>=< ")
                if clean_ver in BLOCKED_EXACT[name]:
                    found.append(f"[{path}] {name}@{clean_ver} (危険バージョン)")


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

if found:
    for f in sorted(set(found)):
        print(f"DANGER: {f}")
    sys.exit(1)
else:
    print("OK")
    sys.exit(0)
