"""npm-safe のパッケージチェッカー。
package.json と package-lock.json をJSONパースして
危険パッケージが含まれていないか正確に判定する。
"""
import json
import sys
import os

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


def check_package_json(path):
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as f:
        pkg = json.load(f)
    for section in ("dependencies", "devDependencies", "optionalDependencies"):
        deps = pkg.get(section, {})
        for name, ver in deps.items():
            if name in BLOCKED_ALL:
                found.append(f"[{path}] {name} (全バージョン危険 - マルウェア)")
            if name in BLOCKED_EXACT:
                clean_ver = ver.lstrip("^~>=< ")
                if clean_ver in BLOCKED_EXACT[name]:
                    found.append(f"[{path}] {name}@{clean_ver} (RATが仕込まれたバージョン)")


def check_package_lock(path):
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as f:
        lock = json.load(f)

    # npm v2+ の packages 形式
    packages = lock.get("packages", {})
    for pkg_path, info in packages.items():
        name = info.get("name", "")
        if not name and pkg_path:
            name = pkg_path.replace("node_modules/", "").split("node_modules/")[-1]
        ver = info.get("version", "")
        if name in BLOCKED_ALL:
            found.append(f"[{path}] {name}@{ver} (全バージョン危険 - マルウェア)")
        if name in BLOCKED_EXACT and ver in BLOCKED_EXACT[name]:
            found.append(f"[{path}] {name}@{ver} (RATが仕込まれたバージョン)")

    # npm v1 の dependencies 形式
    def walk_deps(deps):
        for name, info in deps.items():
            ver = info.get("version", "")
            if name in BLOCKED_ALL:
                found.append(f"[{path}] {name}@{ver} (全バージョン危険 - マルウェア)")
            if name in BLOCKED_EXACT and ver in BLOCKED_EXACT[name]:
                found.append(f"[{path}] {name}@{ver} (RATが仕込まれたバージョン)")
            if "dependencies" in info:
                walk_deps(info["dependencies"])

    if "dependencies" in lock:
        walk_deps(lock["dependencies"])


check_package_json("package.json")
check_package_lock("package-lock.json")

if found:
    for f in found:
        print(f"DANGER: {f}")
    sys.exit(1)
else:
    print("OK")
    sys.exit(0)
