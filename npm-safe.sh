#!/bin/bash
# npm のセキュリティラッパー。install 実行前に危険パッケージをチェックする。
# 使い方: alias npm='~/bin/npm-safe.sh' を .bashrc に追加

RED='\033[0;31m'
YELLOW='\033[1;33m'
GREEN='\033[0;32m'
NC='\033[0m'

if [[ "$1" == "install" || "$1" == "i" || "$1" == "add" || "$1" == "ci" ]]; then
  echo -e "${YELLOW}[npm-safe] 危険パッケージチェック中...${NC}"

  result=$(python ~/bin/npm-safe-check.py 2>&1)
  exit_code=$?

  if [ $exit_code -ne 0 ]; then
    echo ""
    while IFS= read -r line; do
      if [[ "$line" == DANGER:* ]]; then
        echo -e "${RED}⚠ ${line#DANGER: }${NC}"
      fi
    done <<< "$result"
    echo ""
    echo -e "${RED}npm install を中止しました。${NC}"
    echo -e "${YELLOW}上記のパッケージを修正してから再実行してください。${NC}"
    exit 1
  fi

  echo -e "${GREEN}✓ 危険パッケージなし。npm $1 を実行します。${NC}"
fi

command npm "$@"
