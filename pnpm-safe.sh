#!/bin/bash
# pnpm のセキュリティラッパー。install 実行前に危険パッケージをチェックする。
# 使い方: alias pnpm='~/bin/pnpm-safe.sh' を .bashrc に追加

RED='\033[0;31m'
YELLOW='\033[1;33m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
NC='\033[0m'

show_results() {
  echo ""
  while IFS= read -r line; do
    if [[ "$line" == DANGER:* ]]; then
      echo -e "${RED}  ⚠ ${line#DANGER: }${NC}"
    elif [[ "$line" == WARN:* ]]; then
      echo -e "${YELLOW}  ? ${line#WARN: }${NC}"
    fi
  done <<< "$1"
  echo ""
}

confirm_unverified() {
  local result="$1"
  local warns=()
  while IFS= read -r line; do
    if [[ "$line" == WARN:* ]]; then
      warns+=("${line#WARN: }")
    fi
  done <<< "$result"

  if [ ${#warns[@]} -eq 0 ]; then return 0; fi

  echo -e "${YELLOW}未確認バージョンが見つかりました:${NC}"
  for i in "${!warns[@]}"; do
    echo -e "${YELLOW}  $((i+1)). ${warns[$i]}${NC}"
  done
  echo ""
  echo -e "${CYAN}どうしますか？${NC}"
  echo -e "  ${GREEN}[a]${NC} 全てインストール"
  echo -e "  ${RED}[n]${NC} 全て中止"
  echo -e "  ${CYAN}[o]${NC} 一つずつ確認"
  echo -ne "${CYAN}選択 [a/n/o]: ${NC}"
  read -r choice

  case "$choice" in
    a|A) return 0 ;;
    n|N|"") echo -e "${RED}中止しました。${NC}"; return 1 ;;
    o|O)
      for i in "${!warns[@]}"; do
        echo -ne "  ${warns[$i]} — ${CYAN}インストール？ [y/N]: ${NC}"
        read -r answer
        if [[ "$answer" != "y" && "$answer" != "Y" ]]; then
          echo -e "${RED}中止しました。${NC}"; return 1
        fi
      done
      return 0 ;;
    *) echo -e "${RED}中止しました。${NC}"; return 1 ;;
  esac
}

handle_check_result() {
  local result="$1"
  local exit_code="$2"
  local subcmd="$3"

  if [ "$exit_code" -eq 1 ]; then
    show_results "$result"
    echo -e "${RED}pnpm $subcmd を中止しました。${NC}"
    echo -e "${YELLOW}上記のパッケージを修正してから再実行してください。${NC}"
    return 1
  elif [ "$exit_code" -eq 2 ]; then
    if ! confirm_unverified "$result"; then
      return 1
    fi
  fi
  return 0
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
    handle_check_result "$result" $? "$subcmd" || exit 1
  fi

  # --- Step 2: 既存の package.json チェック ---
  result=$(python ~/bin/npm-safe-check.py 2>&1)
  handle_check_result "$result" $? "$subcmd" || exit 1

  # --- Step 3: 推移的依存チェック ---
  lockfile_backup=""
  if [ -f pnpm-lock.yaml ]; then
    lockfile_backup=$(mktemp)
    cp pnpm-lock.yaml "$lockfile_backup"
  fi

  echo -e "${YELLOW}[pnpm-safe] 推移的依存を解決中（--lockfile-only）...${NC}"
  command pnpm install --lockfile-only "${@:2}" 2>/dev/null

  result=$(python ~/bin/npm-safe-check.py 2>&1)
  exit_code=$?

  if [ $exit_code -eq 1 ] || { [ $exit_code -eq 2 ] && ! confirm_unverified "$result"; }; then
    if [ $exit_code -eq 1 ]; then show_results "$result"; fi
    if [ -n "$lockfile_backup" ]; then
      cp "$lockfile_backup" pnpm-lock.yaml
      rm -f "$lockfile_backup"
    elif [ -f pnpm-lock.yaml ]; then
      rm -f pnpm-lock.yaml
    fi
    echo -e "${RED}pnpm $subcmd を中止しました。${NC}"
    exit 1
  fi

  rm -f "$lockfile_backup"

  echo -e "${GREEN}✓ 危険パッケージなし。pnpm $subcmd を実行します。${NC}"
fi

command pnpm "$@"
