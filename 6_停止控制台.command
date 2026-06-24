#!/bin/zsh
cd "$(dirname "$0")"

PIDS=$(lsof -tiTCP:8501 -sTCP:LISTEN)
if [ -n "$PIDS" ]; then
  echo "$PIDS" | xargs kill
  echo "已停止本地网页控制台。"
else
  echo "没有发现正在运行的控制台。"
fi
read -k 1 "?按任意键关闭这个窗口..."
