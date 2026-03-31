"""npm-safe-check.py の動作テスト

exit code:
  0: 安全（OK）
  1: 危険（DANGER → ブロック）
  2: 未確認あり（WARN → シェルで対話プロンプト）
"""
import subprocess
import sys
import os

os.chdir(os.path.dirname(os.path.abspath(__file__)))
CHECK = [sys.executable, "npm-safe-check.py"]
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


# ============================================================
# exit 1: DANGER（ブロック）
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
# exit 0: OK（安全）
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
# exit 2: WARN（未確認 → 対話へ）
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
# 混合ケース
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

# === Summary ===
print(f"\n{'='*40}")
print(f"Passed: {passed}, Failed: {failed}")
if failed:
    sys.exit(1)
