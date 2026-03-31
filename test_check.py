"""npm-safe-check.py の動作テスト

exit code:
  0: 安全（OK）
  1: 危険（DANGER → ブロック）
  2: 未確認あり（WARN → シェルで対話プロンプト）
"""
import subprocess
import sys
import os
import json
import tempfile

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(SCRIPT_DIR)
CHECK_SCRIPT = os.path.join(SCRIPT_DIR, "npm-safe-check.py")
CHECK = [sys.executable, CHECK_SCRIPT]
passed = 0
failed = 0


def test(name, args, expect_exit, expect_contains=None, expect_not_contains=None):
    global passed, failed
    r = subprocess.run(CHECK + args, capture_output=True, text=True)
    output = r.stdout + r.stderr
    ok = True

    if r.returncode != expect_exit:
        print(f"FAIL [{name}]: exit={r.returncode} expected={expect_exit}")
        print(f"  output: {output.strip()}")
        ok = False

    if expect_contains:
        for s in expect_contains:
            if s not in output:
                print(f"FAIL [{name}]: missing '{s}' in output")
                print(f"  output: {output.strip()}")
                ok = False

    if expect_not_contains:
        for s in expect_not_contains:
            if s in output:
                print(f"FAIL [{name}]: unexpected '{s}' in output")
                ok = False

    if ok:
        print(f"  OK [{name}]")
        passed += 1
    else:
        failed += 1


def test_lockfile(name, lockfile_name, lockfile_content,
                  expect_exit, expect_contains=None, expect_not_contains=None):
    """ロックファイルを一時ディレクトリに作成してチェック。"""
    global passed, failed
    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, lockfile_name)
        with open(path, 'w', encoding='utf-8') as f:
            f.write(lockfile_content)
        r = subprocess.run(CHECK, capture_output=True, text=True, cwd=tmpdir)
        output = r.stdout + r.stderr
        ok = True

        if r.returncode != expect_exit:
            print(f"FAIL [{name}]: exit={r.returncode} expected={expect_exit}")
            print(f"  output: {output.strip()}")
            ok = False

        if expect_contains:
            for s in expect_contains:
                if s not in output:
                    print(f"FAIL [{name}]: missing '{s}'")
                    print(f"  output: {output.strip()}")
                    ok = False

        if expect_not_contains:
            for s in expect_not_contains:
                if s in output:
                    print(f"FAIL [{name}]: unexpected '{s}'")
                    ok = False

        if ok:
            print(f"  OK [{name}]")
            passed += 1
        else:
            failed += 1


# ============================================================
# CLI引数チェック: exit 1（DANGER）
# ============================================================

test("dangerous version → exit 1",
     ["--check-args", "axios@1.14.1"],
     expect_exit=1,
     expect_contains=["DANGER:", "危険バージョン"])

test("typosquatting → exit 1",
     ["--check-args", "axois"],
     expect_exit=1,
     expect_contains=["DANGER:", "全バージョン危険"])

test("dangerous 0.30.4 → exit 1",
     ["--check-args", "axios@0.30.4"],
     expect_exit=1,
     expect_contains=["DANGER:"])

test("scoped dangerous → exit 1",
     ["--check-args", "@solana/web3.js@1.95.6"],
     expect_exit=1,
     expect_contains=["DANGER:"])

# ============================================================
# CLI引数チェック: exit 0（OK）
# ============================================================

test("safe version → exit 0",
     ["--check-args", "axios@1.14.0"],
     expect_exit=0,
     expect_contains=["OK"],
     expect_not_contains=["DANGER:", "WARN:"])

test("safe 0.30.3 → exit 0",
     ["--check-args", "axios@0.30.3"],
     expect_exit=0,
     expect_contains=["OK"])

test("safe 1.13.0 → exit 0",
     ["--check-args", "axios@1.13.0"],
     expect_exit=0,
     expect_contains=["OK"])

test("scoped safe → exit 0",
     ["--check-args", "@solana/web3.js@1.95.8"],
     expect_exit=0,
     expect_contains=["OK"],
     expect_not_contains=["DANGER:", "WARN:"])

test("unknown package (not in vuls.json) → exit 0",
     ["--check-args", "lodash@4.17.21"],
     expect_exit=0,
     expect_contains=["OK"],
     expect_not_contains=["DANGER:", "WARN:"])

test("no version (exact pkg) → exit 0",
     ["--check-args", "axios"],
     expect_exit=0,
     expect_not_contains=["DANGER:", "WARN:"])

test("skip flags → exit 0",
     ["--check-args", "--save-dev", "axios@1.14.0"],
     expect_exit=0,
     expect_contains=["OK"])

test("skip URLs → exit 0",
     ["--check-args", "https://example.com/foo.tgz"],
     expect_exit=0,
     expect_contains=["OK"])

# ============================================================
# CLI引数チェック: exit 2（WARN）
# ============================================================

test("unverified version → exit 2",
     ["--check-args", "axios@1.15.0"],
     expect_exit=2,
     expect_contains=["WARN:", "未確認バージョン"])

test("unverified 2.0.0 → exit 2",
     ["--check-args", "axios@2.0.0"],
     expect_exit=2,
     expect_contains=["WARN:", "未確認バージョン", "安全確認済み"])

test("unverified solana → exit 2",
     ["--check-args", "@solana/web3.js@1.96.0"],
     expect_exit=2,
     expect_contains=["WARN:", "未確認バージョン"])

# ============================================================
# CLI引数チェック: 混合ケース
# ============================================================

test("danger + safe → exit 1 (danger wins)",
     ["--check-args", "axios@1.14.1", "lodash@4.17.21"],
     expect_exit=1,
     expect_contains=["DANGER:"])

test("danger + warn → exit 1 (danger wins)",
     ["--check-args", "axios@1.14.1", "axios@1.15.0"],
     expect_exit=1,
     expect_contains=["DANGER:", "WARN:"])

test("typosquatting → exit 1",
     ["--check-args", "loadsh"],
     expect_exit=1,
     expect_contains=["DANGER:"])

# ============================================================
# package-lock.json チェック
# ============================================================

test_lockfile(
    "package-lock: dangerous → exit 1",
    "package-lock.json",
    json.dumps({
        "lockfileVersion": 3,
        "packages": {
            "node_modules/axios": {"version": "1.14.1", "name": "axios"},
            "node_modules/lodash": {"version": "4.17.21", "name": "lodash"},
        }
    }),
    expect_exit=1,
    expect_contains=["DANGER:", "axios", "危険バージョン"],
)

test_lockfile(
    "package-lock: safe → exit 0",
    "package-lock.json",
    json.dumps({
        "lockfileVersion": 3,
        "packages": {
            "node_modules/axios": {"version": "1.14.0", "name": "axios"},
        }
    }),
    expect_exit=0,
    expect_contains=["OK"],
    expect_not_contains=["DANGER:"],
)

test_lockfile(
    "package-lock: typosquat → exit 1",
    "package-lock.json",
    json.dumps({
        "lockfileVersion": 3,
        "packages": {
            "node_modules/axois": {"version": "1.0.0", "name": "axois"},
        }
    }),
    expect_exit=1,
    expect_contains=["DANGER:", "全バージョン危険"],
)

# ============================================================
# pnpm-lock.yaml チェック
# ============================================================

test_lockfile(
    "pnpm-lock: dangerous → exit 1",
    "pnpm-lock.yaml",
    """lockfileVersion: '9.0'
packages:
  'axios@1.14.1':
    resolution: {integrity: sha512-abc}
    engines: {node: '>=14'}
""",
    expect_exit=1,
    expect_contains=["DANGER:", "axios"],
)

test_lockfile(
    "pnpm-lock: safe → exit 0",
    "pnpm-lock.yaml",
    """lockfileVersion: '9.0'
packages:
  'axios@1.14.0':
    resolution: {integrity: sha512-abc}
""",
    expect_exit=0,
    expect_contains=["OK"],
)

# ============================================================
# bun.lock チェック（JSONC 形式、Bun 1.2+）
# ============================================================

test_lockfile(
    "bun.lock: dangerous → exit 1",
    "bun.lock",
    """{
  // bun lockfile
  "lockfileVersion": 1,
  "packages": {
    "axios": ["axios@1.14.1", "sha512-abc", {}, "MIT"],
    "lodash": ["lodash@4.17.21", "sha512-def", {}, "MIT"]
  }
}""",
    expect_exit=1,
    expect_contains=["DANGER:", "axios", "危険バージョン"],
)

test_lockfile(
    "bun.lock: safe → exit 0",
    "bun.lock",
    """{
  "lockfileVersion": 1,
  "packages": {
    "axios": ["axios@1.14.0", "sha512-abc", {}, "MIT"],
    "express": ["express@4.18.2", "sha512-def", {}, "MIT"]
  }
}""",
    expect_exit=0,
    expect_contains=["OK"],
    expect_not_contains=["DANGER:", "WARN:"],
)

test_lockfile(
    "bun.lock: typosquat → exit 1",
    "bun.lock",
    """{
  "lockfileVersion": 1,
  "packages": {
    "axois": ["axois@1.0.0", "sha512-abc", {}, "MIT"]
  }
}""",
    expect_exit=1,
    expect_contains=["DANGER:", "全バージョン危険"],
)

test_lockfile(
    "bun.lock: unverified → exit 2",
    "bun.lock",
    """{
  "lockfileVersion": 1,
  "packages": {
    "axios": ["axios@2.0.0", "sha512-abc", {}, "MIT"]
  }
}""",
    expect_exit=2,
    expect_contains=["WARN:", "未確認バージョン"],
)

test_lockfile(
    "bun.lock: JSONC comments handled",
    "bun.lock",
    """{
  // This is a comment
  "lockfileVersion": 1,
  "packages": {
    // Another comment
    "express": ["express@4.18.2", "sha512-abc", {}, "MIT"],
  }
}""",
    expect_exit=0,
    expect_contains=["OK"],
)

test_lockfile(
    "bun.lock: scoped dangerous → exit 1",
    "bun.lock",
    """{
  "lockfileVersion": 1,
  "packages": {
    "@solana/web3.js": ["@solana/web3.js@1.95.6", "sha512-abc", {}, "MIT"]
  }
}""",
    expect_exit=1,
    expect_contains=["DANGER:"],
)

# ============================================================
# yarn.lock v1 (Classic) チェック
# ============================================================

test_lockfile(
    "yarn.lock v1: dangerous → exit 1",
    "yarn.lock",
    """# THIS IS AN AUTOGENERATED FILE. DO NOT EDIT THIS FILE DIRECTLY.
# yarn lockfile v1

axios@^1.14.0:
  version "1.14.1"
  resolved "https://registry.yarnpkg.com/axios/-/axios-1.14.1.tgz#abc"
  integrity sha512-abc

lodash@^4.17.0:
  version "4.17.21"
  resolved "https://registry.yarnpkg.com/lodash/-/lodash-4.17.21.tgz#def"
""",
    expect_exit=1,
    expect_contains=["DANGER:", "axios", "危険バージョン"],
)

test_lockfile(
    "yarn.lock v1: safe → exit 0",
    "yarn.lock",
    """# yarn lockfile v1

axios@^1.14.0:
  version "1.14.0"
  resolved "https://registry.yarnpkg.com/axios/-/axios-1.14.0.tgz#abc"

express@^4.18.0:
  version "4.18.2"
  resolved "https://registry.yarnpkg.com/express/-/express-4.18.2.tgz#def"
""",
    expect_exit=0,
    expect_contains=["OK"],
    expect_not_contains=["DANGER:"],
)

test_lockfile(
    "yarn.lock v1: typosquat → exit 1",
    "yarn.lock",
    """# yarn lockfile v1

axois@^1.0.0:
  version "1.0.0"
  resolved "https://registry.yarnpkg.com/axois/-/axois-1.0.0.tgz#abc"
""",
    expect_exit=1,
    expect_contains=["DANGER:", "全バージョン危険"],
)

test_lockfile(
    "yarn.lock v1: scoped dangerous → exit 1",
    "yarn.lock",
    """# yarn lockfile v1

"@solana/web3.js@^1.95.0":
  version "1.95.6"
  resolved "https://registry.yarnpkg.com/@solana/web3.js/-/web3.js-1.95.6.tgz#abc"
""",
    expect_exit=1,
    expect_contains=["DANGER:"],
)

test_lockfile(
    "yarn.lock v1: unverified → exit 2",
    "yarn.lock",
    """# yarn lockfile v1

axios@^2.0.0:
  version "2.0.0"
  resolved "https://registry.yarnpkg.com/axios/-/axios-2.0.0.tgz#abc"
""",
    expect_exit=2,
    expect_contains=["WARN:", "未確認バージョン"],
)

test_lockfile(
    "yarn.lock v1: multi-range header → exit 1",
    "yarn.lock",
    """# yarn lockfile v1

axios@^1.14.0, axios@~1.14.0:
  version "1.14.1"
  resolved "https://registry.yarnpkg.com/axios/-/axios-1.14.1.tgz#abc"
""",
    expect_exit=1,
    expect_contains=["DANGER:"],
)

# ============================================================
# yarn.lock v2 (Berry) チェック
# ============================================================

test_lockfile(
    "yarn.lock v2: dangerous → exit 1",
    "yarn.lock",
    """__metadata:
  version: 8
  cacheKey: 10c0

"axios@npm:^1.14.0":
  version: 1.14.1
  resolution: "axios@npm:1.14.1"
  checksum: abc
  languageName: node

"lodash@npm:^4.17.0":
  version: 4.17.21
  resolution: "lodash@npm:4.17.21"
  checksum: def
  languageName: node
""",
    expect_exit=1,
    expect_contains=["DANGER:", "axios", "危険バージョン"],
)

test_lockfile(
    "yarn.lock v2: safe → exit 0",
    "yarn.lock",
    """__metadata:
  version: 8

"axios@npm:^1.14.0":
  version: 1.14.0
  resolution: "axios@npm:1.14.0"
  checksum: abc
""",
    expect_exit=0,
    expect_contains=["OK"],
    expect_not_contains=["DANGER:"],
)

test_lockfile(
    "yarn.lock v2: scoped dangerous → exit 1",
    "yarn.lock",
    """__metadata:
  version: 8

"@solana/web3.js@npm:^1.95.0":
  version: 1.95.7
  resolution: "@solana/web3.js@npm:1.95.7"
""",
    expect_exit=1,
    expect_contains=["DANGER:"],
)

test_lockfile(
    "yarn.lock v2: unverified → exit 2",
    "yarn.lock",
    """__metadata:
  version: 8

"axios@npm:^2.0.0":
  version: 2.0.0
  resolution: "axios@npm:2.0.0"
""",
    expect_exit=2,
    expect_contains=["WARN:", "未確認バージョン"],
)

# ============================================================
# package.json チェック
# ============================================================

test_lockfile(
    "package.json: dangerous dep → exit 1",
    "package.json",
    json.dumps({
        "dependencies": {"axios": "1.14.1"},
    }),
    expect_exit=1,
    expect_contains=["DANGER:"],
)

test_lockfile(
    "package.json: typosquat dep → exit 1",
    "package.json",
    json.dumps({
        "devDependencies": {"axois": "^1.0.0"},
    }),
    expect_exit=1,
    expect_contains=["DANGER:", "全バージョン危険"],
)

test_lockfile(
    "package.json: safe dep → exit 0",
    "package.json",
    json.dumps({
        "dependencies": {"axios": "^1.14.0", "express": "^4.18.0"},
    }),
    expect_exit=0,
    expect_contains=["OK"],
)

# ============================================================
# 空ディレクトリ（ファイルなし）→ OK
# ============================================================

def test_empty_dir():
    global passed, failed
    with tempfile.TemporaryDirectory() as tmpdir:
        r = subprocess.run(CHECK, capture_output=True, text=True, cwd=tmpdir)
        if r.returncode == 0 and "OK" in r.stdout:
            print("  OK [empty dir → exit 0]")
            passed += 1
        else:
            print(f"FAIL [empty dir]: exit={r.returncode}")
            print(f"  output: {(r.stdout + r.stderr).strip()}")
            failed += 1

test_empty_dir()


# === Summary ===
print(f"\n{'='*40}")
print(f"Passed: {passed}, Failed: {failed}")
if failed:
    sys.exit(1)
