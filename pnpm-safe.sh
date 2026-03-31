#!/bin/bash
# pnpm のセキュリティラッパー。install 実行前に危険パッケージをチェックする。
# 使い方: alias pnpm='~/bin/pnpm-safe.sh' を .bashrc に追加
#
# 3段階チェック:
#   1. CLI引数のパッケージ名を直接チェック（pnpm add axois → 即ブロック）
#   2. --lockfile-only でロックファイルだけ更新（コード実行なし）
#   3. 更新されたロックファイルで推移的依存をチェック

RED='\033[0;31m'
YELLOW='\033[1;33m'
GREEN='\033[0;32m'
NC='\033[0m'

show_danger() {
  echo ""
  while IFS= read -r line; do
    if [[ "$line" == DANGER:* ]]; then
      echo -e "${RED}⚠ ${line#DANGER: }${NC}"
    fi
  done <<< "$1"
  echo ""
}

if [[ "$1" == "install" || "$1" == "i" || "$1" == "add" ]]; then
  subcmd="$1"
  echo -e "${YELLOW}[pnpm-safe] 危険パッケージチェック中...${NC}"

  # --- Step 1: CLI引数のパッケージ名をチェック ---
  pkg_args=()
  skip_next=false
  for arg in "${@:2}"; do
    if $skip_next; then skip_next=false; continue; fi
    case "$arg" in
      --registry|--filter|--dir) skip_next=true ;;
      -*) ;;
      *) pkg_args+=("$arg") ;;
    esac
  done

  if [ ${#pkg_args[@]} -gt 0 ]; then
    result=$(python ~/bin/npm-safe-check.py --check-args "${pkg_args[@]}" 2>&1)
    if [ $? -ne 0 ]; then
      show_danger "$result"
      echo -e "${RED}pnpm $subcmd を中止しました。${NC}"
      echo -e "${YELLOW}上記のパッケージを修正してから再実行してください。${NC}"
      exit 1
    fi
  fi

  # --- Step 2: 既存の package.json チェック ---
  result=$(python ~/bin/npm-safe-check.py 2>&1)
  if [ $? -ne 0 ]; then
    show_danger "$result"
    echo -e "${RED}pnpm $subcmd を中止しました。${NC}"
    echo -e "${YELLOW}上記のパッケージを修正してから再実行してください。${NC}"
    exit 1
  fi

  # --- Step 3: 推移的依存チェック ---
  # ロックファイルをバックアップ
  lockfile_backup=""
  if [ -f pnpm-lock.yaml ]; then
    lockfile_backup=$(mktemp)
    cp pnpm-lock.yaml "$lockfile_backup"
  fi

  echo -e "${YELLOW}[pnpm-safe] 推移的依存を解決中（--lockfile-only）...${NC}"
  command pnpm install --lockfile-only "${@:2}" 2>/dev/null

  result=$(python ~/bin/npm-safe-check.py 2>&1)
  exit_code=$?

  if [ $exit_code -ne 0 ]; then
    show_danger "$result"
    # ロックファイルを復元
    if [ -n "$lockfile_backup" ]; then
      cp "$lockfile_backup" pnpm-lock.yaml
      rm -f "$lockfile_backup"
    elif [ -f pnpm-lock.yaml ]; then
      rm -f pnpm-lock.yaml
    fi
    echo -e "${RED}pnpm $subcmd を中止しました（推移的依存に危険パッケージ検出）。${NC}"
    echo -e "${YELLOW}上記のパッケージを修正してから再実行してください。${NC}"
    exit 1
  fi

  rm -f "$lockfile_backup"

  echo -e "${GREEN}✓ 危険パッケージなし。pnpm $subcmd を実行します。${NC}"
fi

command pnpm "$@"
