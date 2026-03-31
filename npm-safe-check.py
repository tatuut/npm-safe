"""npm-safe チェッカー v2
全パッケージマネージャー対応（npm, pnpm, bun, yarn）
チェック・対話・推移的依存解決を全てPython内で処理。
シェルラッパーは薄いエントリポイントのみ。

使い方:
  python npm-safe-check.py                            # ファイルチェック（後方互換）
  python npm-safe-check.py --check-args pkg1 pkg2     # CLI引数チェック（後方互換）
  python npm-safe-check.py --full <pm> <subcmd> [args] # フルフロー（新）

前提: Python 3.8+、サードパーティパッケージ不要
"""
import json
import sys
import os
import re
import subprocess
import shutil
import tempfile

# === ANSI カラー ===

RED = '\033[0;31m'
YELLOW = '\033[1;33m'
GREEN = '\033[0;32m'
CYAN = '\033[0;36m'
NC = '\033[0m'


def _enable_ansi_windows():
    """Windows で ANSI エスケープシーケンスを有効化。"""
    if sys.platform == 'win32':
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
        except Exception:
            pass


# === PM 設定 ===

PM_CONFIG = {
    "npm": {
        "install_cmds": {"install", "i", "add", "ci"},
        "lockfile": "package-lock.json",
        "dry_install": ["npm", "install", "--package-lock-only"],
        "skip_dry_cmds": {"ci"},
        "list_cmd": ["npm", "list", "--all", "--json"],
        "value_flags": {"--registry", "--cache", "--prefix", "--tag"},
    },
    "pnpm": {
        "install_cmds": {"install", "i", "add"},
        "lockfile": "pnpm-lock.yaml",
        "dry_install": ["pnpm", "install", "--lockfile-only"],
        "skip_dry_cmds": set(),
        "list_cmd": ["pnpm", "list", "--json"],
        "value_flags": {"--registry", "--filter", "--dir"},
    },
    "bun": {
        "install_cmds": {"install", "i", "add"},
        "lockfile": "bun.lock",
        "dry_install": ["bun", "install", "--lockfile-only"],
        "skip_dry_cmds": set(),
        "list_cmd": None,
        "value_flags": {"--registry", "--cwd"},
    },
    "yarn": {
        "install_cmds": {"install", "add"},
        "lockfile": "yarn.lock",
        "dry_install": ["yarn", "install", "--mode", "update-lockfile"],
        "skip_dry_cmds": set(),
        "list_cmd": None,
        "value_flags": {"--registry", "--cwd"},
    },
}


# === vuls.json 読み込み ===

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


# === チェッカー ===

class Checker:
    """パッケージ安全性チェッカー。"""

    def __init__(self):
        self.blocked_exact, self.blocked_all, self.safe_exact = _load_vuls()
        self.dangers = []
        self.warns = []

    def reset(self):
        self.dangers = []
        self.warns = []

    @property
    def exit_code(self):
        if self.dangers:
            return 1
        if self.warns:
            return 2
        return 0

    def format_output(self):
        """後方互換テキスト出力（DANGER:/WARN:/OK）。"""
        lines = []
        for d in sorted(set(self.dangers)):
            lines.append(f"DANGER: {d}")
        for w in sorted(set(self.warns)):
            lines.append(f"WARN: {w}")
        if not lines:
            lines.append("OK")
        return "\n".join(lines)

    # --- コアチェック ---

    def _check_entry(self, source, name, ver):
        if not name:
            return
        if name in self.blocked_all:
            self.dangers.append(f"[{source}] {name}@{ver} (全バージョン危険)")
            return
        if name in self.blocked_exact:
            if ver in self.blocked_exact[name]:
                self.dangers.append(f"[{source}] {name}@{ver} (危険バージョン)")
            elif ver != "?" and ver != "*" and name in self.safe_exact:
                if ver not in self.safe_exact[name]:
                    safe_list = ", ".join(sorted(self.safe_exact[name]))
                    self.warns.append(
                        f"[{source}] {name}@{ver} (未確認バージョン。"
                        f"安全確認済み: {safe_list})"
                    )

    @staticmethod
    def _parse_name_version(ident):
        """'name@version' をパース。スコープ付きも対応。"""
        if ident.startswith('@'):
            idx = ident.rindex('@')
            if idx == 0:
                return ident, "?"
            return ident[:idx], ident[idx + 1:]
        elif '@' in ident:
            return ident.rsplit('@', 1)
        return ident, "?"

    # --- CLI 引数チェック ---

    def check_args(self, args):
        for arg in args:
            if arg.startswith("-"):
                continue
            if arg.startswith((".", "/", "http:", "https:", "git:", "github:", "file:")):
                continue
            if arg.startswith("@"):
                if arg.count("@") >= 2:
                    idx = arg.rindex("@")
                    name, ver = arg[:idx], arg[idx + 1:]
                else:
                    name, ver = arg, "*"
            elif "@" in arg:
                name, ver = arg.rsplit("@", 1)
            else:
                name, ver = arg, "*"
            self._check_entry("引数", name, ver)

    # --- package.json ---

    def check_package_json(self, path="package.json"):
        if not os.path.exists(path):
            return
        with open(path, encoding="utf-8") as f:
            pkg = json.load(f)
        for section in ("dependencies", "devDependencies", "optionalDependencies"):
            for name, ver in pkg.get(section, {}).items():
                if name in self.blocked_all:
                    self.dangers.append(f"[{path}] {name} (全バージョン危険)")
                    continue
                if name in self.blocked_exact:
                    clean_ver = ver.lstrip("^~>=< ")
                    self._check_entry(path, name, clean_ver)

    # --- package-lock.json ---

    def check_package_lock(self, path="package-lock.json"):
        if not os.path.exists(path):
            return
        with open(path, encoding="utf-8") as f:
            lock = json.load(f)
        # npm v2+ packages 形式
        for pkg_path, info in lock.get("packages", {}).items():
            name = info.get("name", "")
            if not name and pkg_path:
                name = pkg_path.replace("node_modules/", "").split("node_modules/")[-1]
            self._check_entry(path, name, info.get("version", ""))
        # npm v1 dependencies 形式
        def walk(deps):
            for name, info in deps.items():
                self._check_entry(path, name, info.get("version", ""))
                if "dependencies" in info:
                    walk(info["dependencies"])
        if "dependencies" in lock:
            walk(lock["dependencies"])

    # --- pnpm-lock.yaml ---

    def check_pnpm_lock(self, path="pnpm-lock.yaml"):
        if not os.path.exists(path):
            return
        with open(path, encoding="utf-8") as f:
            content = f.read()
        pattern = re.compile(
            r"['\"]?/?(@?[a-zA-Z0-9._-]+(?:/@?[a-zA-Z0-9._-]+)?)@(\d+\.\d+\.\d+)"
        )
        for match in pattern.finditer(content):
            self._check_entry(path, match.group(1), match.group(2))

    # --- bun.lock (JSONC, Bun 1.2+) ---

    def check_bun_lock(self, path="bun.lock"):
        if not os.path.exists(path):
            return
        with open(path, encoding="utf-8") as f:
            content = f.read()

        # JSONC → JSON: コメント除去 + 末尾カンマ除去
        cleaned = re.sub(r'//[^\n]*', '', content)
        cleaned = re.sub(r',(\s*[}\]])', r'\1', cleaned)

        try:
            lock = json.loads(cleaned)
        except json.JSONDecodeError:
            # フォールバック: 正規表現スキャン
            self._check_bun_lock_regex(path, content)
            return

        # packages セクション解析
        packages = lock.get("packages", {})
        for _key, value in packages.items():
            if isinstance(value, list) and len(value) > 0:
                ident = value[0]
                if isinstance(ident, str) and '@' in ident:
                    name, ver = self._parse_name_version(ident)
                    self._check_entry(path, name, ver)

    def _check_bun_lock_regex(self, path, content):
        """bun.lock フォールバック: 正規表現で name@version を抽出。"""
        pattern = re.compile(
            r'"(@?[a-zA-Z0-9._-]+(?:/@?[a-zA-Z0-9._-]+)?)@(\d+\.\d+\.\d+[^"]*)"'
        )
        for m in pattern.finditer(content):
            self._check_entry(path, m.group(1), m.group(2))

    # --- yarn.lock (v1 Classic / v2 Berry 両対応) ---

    def check_yarn_lock(self, path="yarn.lock"):
        if not os.path.exists(path):
            return
        with open(path, encoding="utf-8") as f:
            content = f.read()

        current_names = []
        for line in content.split('\n'):
            stripped = line.rstrip()

            # 空行・コメント → ブロック区切り
            if not stripped or stripped.startswith('#'):
                current_names = []
                continue

            # パッケージヘッダ行: インデントなし、末尾 ':'
            if not line.startswith(' ') and stripped.endswith(':'):
                current_names = []
                header = stripped[:-1]  # 末尾 ':' 除去
                for part in header.split(','):
                    name = self._extract_yarn_pkg_name(part.strip().strip('"'))
                    if name:
                        current_names.append(name)

            # version 行（インデントあり）
            elif line.startswith(' ') and current_names:
                s = line.strip()
                ver = None
                # v1: version "1.2.3"
                m = re.match(r'^version\s+"([^"]+)"', s)
                if m:
                    ver = m.group(1)
                else:
                    # v2: version: 1.2.3
                    m = re.match(r'^version:\s+(\S+)', s)
                    if m:
                        ver = m.group(1)
                if ver:
                    for name in set(current_names):
                        self._check_entry(path, name, ver)
                    current_names = []

    @staticmethod
    def _extract_yarn_pkg_name(entry):
        """yarn.lock パッケージ指定から名前を抽出。
        "axios@^1.0.0" → "axios"
        "@scope/pkg@npm:^1.0.0" → "@scope/pkg"
        """
        # Berry の npm: 指定を除去
        entry = entry.replace('@npm:', '@')

        if entry.startswith('@'):
            rest = entry[1:]
            at_idx = rest.find('@')
            if at_idx != -1:
                return '@' + rest[:at_idx]
            return entry
        else:
            at_idx = entry.find('@')
            if at_idx != -1:
                return entry[:at_idx]
            return entry

    # --- インストール済みチェック ---

    def check_installed(self, pm="npm"):
        if not os.path.exists("node_modules"):
            return
        config = PM_CONFIG.get(pm, PM_CONFIG["npm"])
        list_cmd = config.get("list_cmd")
        if not list_cmd:
            return
        try:
            r = subprocess.run(list_cmd, capture_output=True, text=True, timeout=30)
            if r.returncode not in (0, 1):
                return
            tree = json.loads(r.stdout)
            self._walk_installed(tree.get("dependencies", {}))
        except (subprocess.TimeoutExpired, FileNotFoundError, json.JSONDecodeError):
            pass

    def _walk_installed(self, deps):
        for name, info in deps.items():
            ver = info.get("version", "?")
            self._check_entry("installed", name, ver)
            if "dependencies" in info:
                self._walk_installed(info["dependencies"])

    # --- 全ファイルチェック（後方互換 / --full 共通） ---

    def check_all_files(self):
        """全ロックファイルをチェック（後方互換モード用）。"""
        self.check_package_json()
        self.check_package_lock()
        self.check_pnpm_lock()
        self.check_bun_lock()
        self.check_yarn_lock()
        self.check_installed()

    def check_files_for_pm(self, pm):
        """指定PMのロックファイルをチェック。"""
        self.check_package_json()
        config = PM_CONFIG.get(pm)
        if not config:
            return
        lockfile = config["lockfile"]
        # ロックファイル種別に応じたパーサーを呼ぶ
        parsers = {
            "package-lock.json": self.check_package_lock,
            "pnpm-lock.yaml": self.check_pnpm_lock,
            "bun.lock": self.check_bun_lock,
            "yarn.lock": self.check_yarn_lock,
        }
        parser = parsers.get(lockfile)
        if parser:
            parser()


# === 対話プロンプト（--full モード用） ===

def _show_colored(dangers, warns):
    """DANGER/WARN を色付きで表示。"""
    print()
    for d in sorted(set(dangers)):
        print(f"{RED}  ⚠ {d}{NC}")
    for w in sorted(set(warns)):
        print(f"{YELLOW}  ? {w}{NC}")
    print()


def _confirm_unverified(warns):
    """未確認バージョンの対話プロンプト。True=続行, False=中止。"""
    unique_warns = sorted(set(warns))
    if not unique_warns:
        return True

    print(f"{YELLOW}未確認バージョンが見つかりました:{NC}")
    for i, w in enumerate(unique_warns, 1):
        print(f"{YELLOW}  {i}. {w}{NC}")
    print()
    print(f"{CYAN}どうしますか？{NC}")
    print(f"  {GREEN}[a]{NC} 全てインストール")
    print(f"  {RED}[n]{NC} 全て中止")
    print(f"  {CYAN}[o]{NC} 一つずつ確認")

    try:
        choice = input(f"{CYAN}選択 [a/n/o]: {NC}").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print(f"\n{RED}中止しました。{NC}")
        return False

    if choice == 'a':
        return True
    elif choice == 'o':
        for w in unique_warns:
            try:
                answer = input(f"  {w} — {CYAN}インストール？ [y/N]: {NC}").strip().lower()
            except (EOFError, KeyboardInterrupt):
                print(f"\n{RED}中止しました。{NC}")
                return False
            if answer != 'y':
                print(f"{RED}中止しました。{NC}")
                return False
        return True
    else:
        print(f"{RED}中止しました。{NC}")
        return False


# === --full モード: フルフロー ===

def _extract_pkg_args(pm, args):
    """サブコマンド以降の引数からパッケージ名を抽出。"""
    config = PM_CONFIG.get(pm, {})
    value_flags = config.get("value_flags", set())
    pkg_args = []
    skip_next = False

    for arg in args[1:]:  # args[0] はサブコマンド
        if skip_next:
            skip_next = False
            continue
        if arg in value_flags:
            skip_next = True
            continue
        if arg.startswith("-"):
            # --flag=value 形式はスキップ
            continue
        pkg_args.append(arg)

    return pkg_args


def run_full(pm, args):
    """フルフロー: チェック → 対話 → exit code で結果を返す。
    シェル側で exit code を見て、0 なら実際の pm コマンドを実行する。
    """
    _enable_ansi_windows()

    config = PM_CONFIG.get(pm)
    if not config:
        print(f"{RED}ERROR: 未対応のパッケージマネージャー: {pm}{NC}", file=sys.stderr)
        sys.exit(1)

    subcmd = args[0] if args else ""
    if subcmd not in config["install_cmds"]:
        sys.exit(0)  # install系以外はスルー

    print(f"{YELLOW}[{pm}-safe] 危険パッケージチェック中...{NC}")

    checker = Checker()

    # --- Phase 1: CLI引数チェック ---
    pkg_args = _extract_pkg_args(pm, args)
    if pkg_args:
        checker.check_args(pkg_args)
        if checker.dangers:
            _show_colored(checker.dangers, checker.warns)
            print(f"{RED}{pm} {subcmd} を中止しました。{NC}")
            print(f"{YELLOW}上記のパッケージを修正してから再実行してください。{NC}")
            sys.exit(1)

    # --- Phase 2: 既存ファイルチェック ---
    checker.check_files_for_pm(pm)
    if checker.dangers:
        _show_colored(checker.dangers, checker.warns)
        print(f"{RED}{pm} {subcmd} を中止しました。{NC}")
        print(f"{YELLOW}上記のパッケージを修正してから再実行してください。{NC}")
        sys.exit(1)

    # --- Phase 3: 推移的依存チェック ---
    dry_cmd = config.get("dry_install")
    skip_dry = subcmd in config.get("skip_dry_cmds", set())

    if dry_cmd and not skip_dry:
        lockfile = config["lockfile"]
        lockfile_backup = None

        if os.path.exists(lockfile):
            lockfile_backup = tempfile.mktemp()
            shutil.copy2(lockfile, lockfile_backup)

        print(f"{YELLOW}[{pm}-safe] 推移的依存を解決中...{NC}")

        # dry-install 実行（ロックファイルだけ更新）
        full_cmd = dry_cmd + args[1:]  # サブコマンド以降のフラグ・パッケージ名
        try:
            subprocess.run(
                full_cmd, capture_output=True, text=True, timeout=60
            )
        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            # dry-install が失敗（yarn v1 等）→ スキップ
            if lockfile_backup:
                shutil.copy2(lockfile_backup, lockfile)
                os.remove(lockfile_backup)
            if isinstance(e, FileNotFoundError):
                pass  # PM未インストール、既存ファイルチェックだけで進む
            else:
                print(f"{YELLOW}[{pm}-safe] 推移的依存の解決がタイムアウト。既存チェックのみで続行。{NC}")
            # Phase 2 の結果で判定を続行
            dry_cmd = None  # 以降の復元処理をスキップ

        if dry_cmd:
            # 更新されたロックファイルを再チェック
            trans_checker = Checker()
            parsers = {
                "package-lock.json": trans_checker.check_package_lock,
                "pnpm-lock.yaml": trans_checker.check_pnpm_lock,
                "bun.lock": trans_checker.check_bun_lock,
                "yarn.lock": trans_checker.check_yarn_lock,
            }
            parser = parsers.get(lockfile)
            if parser:
                parser()

            if trans_checker.dangers:
                # ロックファイル復元
                if lockfile_backup:
                    shutil.copy2(lockfile_backup, lockfile)
                    os.remove(lockfile_backup)
                elif os.path.exists(lockfile):
                    os.remove(lockfile)

                # Phase 1-2 の結果とマージして表示
                all_dangers = checker.dangers + trans_checker.dangers
                all_warns = checker.warns + trans_checker.warns
                _show_colored(all_dangers, all_warns)
                print(f"{RED}{pm} {subcmd} を中止しました。{NC}")
                sys.exit(1)

            # 推移的チェックの WARN をマージ
            checker.warns.extend(trans_checker.warns)

            if lockfile_backup:
                os.remove(lockfile_backup)

    # --- Phase 4: WARN の対話処理 ---
    if checker.warns:
        if not _confirm_unverified(checker.warns):
            # dry-install でロックファイルが変わっている場合は復元不可能
            # （Phase 3 で backup は既に削除済み）
            # → ユーザーに手動復元を促す
            sys.exit(1)

    print(f"{GREEN}✓ 危険パッケージなし。{pm} {subcmd} を実行します。{NC}")
    sys.exit(0)


# === エントリポイント ===

if __name__ == "__main__":
    if len(sys.argv) > 2 and sys.argv[1] == "--full":
        # 新モード: --full <pm> <subcmd> [args...]
        run_full(sys.argv[2], sys.argv[3:])

    elif len(sys.argv) > 1 and sys.argv[1] == "--check-args":
        # 後方互換: CLI引数チェック
        checker = Checker()
        checker.check_args(sys.argv[2:])
        print(checker.format_output())
        sys.exit(checker.exit_code)

    else:
        # 後方互換: 全ファイルチェック
        checker = Checker()
        checker.check_all_files()
        print(checker.format_output())
        sys.exit(checker.exit_code)
