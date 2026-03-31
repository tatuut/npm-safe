# npm-safe

npm / pnpm / bun / yarn の `install` 前に危険パッケージを自動検出・ブロックするセキュリティゲート。

## 対応パッケージマネージャー

| PM | ロックファイル | 推移的依存チェック |
|----|-------------|----------------|
| **npm** | package-lock.json | `--package-lock-only` |
| **pnpm** | pnpm-lock.yaml | `--lockfile-only` |
| **bun** | bun.lock (JSONC) | `--lockfile-only` |
| **yarn** (v2+) | yarn.lock | `--mode update-lockfile` |

> **yarn Classic (v1) は非対応。** lockfile-only モードがなく推移的依存の事前チェックが不可能なため、安全性を保証できない。

## クイックスタート

### bash (Git Bash / WSL / macOS / Linux)

```bash
mkdir -p ~/bin
cp safe.sh npm-safe-check.py vuls.json ~/bin/
chmod +x ~/bin/safe.sh

cat >> ~/.bashrc << 'EOF'
alias npm='~/bin/safe.sh npm'
alias pnpm='~/bin/safe.sh pnpm'
alias bun='~/bin/safe.sh bun'
alias yarn='~/bin/safe.sh yarn'
EOF
source ~/.bashrc
```

### PowerShell

```powershell
Copy-Item safe.ps1, npm-safe-check.py, vuls.json $HOME\bin\

Add-Content $PROFILE @'
function npm  { & $HOME\bin\safe.ps1 npm  @args }
function pnpm { & $HOME\bin\safe.ps1 pnpm @args }
function bun  { & $HOME\bin\safe.ps1 bun  @args }
function yarn { & $HOME\bin\safe.ps1 yarn @args }
'@
```

### 前提条件

- Python 3.8+（標準ライブラリのみ、依存パッケージなし）
- npm / pnpm / bun / yarn v2+ のいずれか

## 仕組み

`install` / `add` コマンドを3段階でチェックする:

**Step 1 &mdash; CLI引数** &ensp; コマンドで指定されたパッケージ名をブロックリストと照合。`axois`（axios のタイポ）等をここでキャッチ。

**Step 2 &mdash; 既存ファイル** &ensp; `package.json` と PM のロックファイルを解析。既に依存ツリーに含まれる危険パッケージを検出。

**Step 3 &mdash; 推移的依存** &ensp; lockfile-only install を実行（node_modules に触れず、スクリプトも実行しない）して完全な依存ツリーを解決。更新されたロックファイルをスキャンし、脅威があればロックファイルを復元。

### 判定

| 結果 | 条件 | 動作 |
|------|------|------|
| **DANGER** | `dangerous` リストに一致 / タイポスクワッティング | **インストール中止** |
| **OK** | `safe` リストに一致 / ブロックリスト未登録 | サイレント通過 |
| **未確認** | ブロックリストにあるがバージョン未確認 | **対話プロンプト**（全許可 / 全拒否 / 個別確認） |

## 脅威の例

ブロックリスト（`vuls.json`）は2カテゴリ。代表的なもの:

**正規パッケージの侵害版**（特定バージョンのみ危険）:

| パッケージ | 危険 | 安全 | 種別 |
|-----------|------|------|------|
| `axios` | 1.14.1, 0.30.4 | 1.14.0, 0.30.3 | RAT（リモートアクセストロイの木馬） |
| `@solana/web3.js` | 1.95.6, 1.95.7 | 1.95.8+ | 秘密鍵窃取 |

**タイポスクワッティング**（全バージョン危険）:

| パッケージ | 偽装先 | 種別 |
|-----------|--------|------|
| `axois` | axios | 情報窃取 |
| `loadsh` | lodash | 情報窃取 |
| `expres` | express | バックドア |

全リストは [`vuls.json`](vuls.json) を参照。

## 脅威の追加

`vuls.json` を編集するだけ（コード変更不要）:

```jsonc
{
  "exact": {
    "compromised-pkg": {
      "dangerous": ["3.2.1"],       // 危険バージョン → ブロック
      "safe": ["3.2.0", "3.1.0"],   // 安全確認済み → 通過
      "type": "バックドア",           // それ以外 → 対話プロンプト
      "added": "2026-04-01"
    }
  },
  "all": {
    "typo-pkg": { "type": "マルウェア", "added": "2026-04-01" }
  }
}
```

## パフォーマンス

ロックファイルのチェックは純粋なパースのみ &mdash; 体感ゼロ。唯一のコストは推移的依存の解決ステップ。

| チェック | 処理内容 | 実測値 |
|---------|---------|--------|
| package.json | JSON パース + dict lookup | **< 1ms** |
| package-lock.json (1,500件) | JSON パース + 全走査 | **~5ms** |
| pnpm-lock.yaml | テキスト全体に正規表現 | **~10ms** |
| bun.lock | JSONC パース + packages 走査 | **~5ms** |
| yarn.lock | 行単位解析 | **~10ms** |
| 推移的依存解決 | lockfile-only install | **~2-8秒** |

## アーキテクチャ

```
safe.sh / safe.ps1        <- 薄いエントリポイント（全PM共通、~20行）
  └─ npm-safe-check.py    <- 全ロジック: チェック・対話・推移的依存解決
       └─ vuls.json        <- ブロックリスト（コード変更不要で編集可能）
```

## テスト

```bash
python test_check.py
```

43テスト: CLI引数、package.json、package-lock.json、pnpm-lock.yaml、bun.lock (JSONC)、yarn.lock (v1/v2形式)、空ディレクトリ。

## コントリビュート

npm-safe はオープンソースです。**コミュニティの脅威情報がこのツールをより強くします。** 特に `vuls.json` への情報提供を歓迎します。

### 悪意あるパッケージを報告する

侵害されたnpmパッケージを発見・把握した場合、[Issue](../../issues) を開くか、`vuls.json` への追加PRを送ってください。以下の情報があると助かります:

- パッケージ名と危険なバージョン
- 安全なバージョン（分かれば）
- 脅威の種別（RAT、情報窃取、タイポスクワッティング等）
- 情報源のリンク（アドバイザリ、ブログ記事等）

### vuls.json への追加が安全な理由

`vuls.json` は**追加のみ（append-only）で安全性が設計されている**。誤検知（false positive）の最悪のケースはパッケージが一時的にブロックされることだけ &mdash; 不便にはなるが、セキュリティインシデントにはならない。これは:

- エントリの追加がプロジェクトを壊したり脆弱性を生んだりすることは絶対にない
- AI支援や自動化された脅威フィードが、個別のレビューなしに安全に `vuls.json` に追記できる
- セキュリティを低下させうるのは*削除*のみであり、それには慎重なレビューが必要

この性質により、npm-safe は**コミュニティ規模・自動化された脅威収集**に適している。

## 参考

- [Socket.dev Blog](https://socket.dev/blog) &mdash; サプライチェーン攻撃の最新情報
- [GitHub Advisory Database](https://github.com/advisories) &mdash; 脆弱性データベース
- [Phylum Blog](https://blog.phylum.io) &mdash; マルウェアパッケージの分析レポート

## License

MIT
