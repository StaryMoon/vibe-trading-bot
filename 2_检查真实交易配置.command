#!/bin/zsh
set -e
cd "$(dirname "$0")"

if [ ! -d ".venv" ]; then
  echo "没有找到 .venv，先安装依赖。"
  python3 -m venv .venv
  .venv/bin/python -m pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org -i https://pypi.org/simple -e ".[dev,ai]"
fi

source .venv/bin/activate
echo "正在检查真实交易配置..."
vibe-trader --config configs/live_binance_spot_small.yaml doctor || true
echo ""
echo "如果上面显示 Doctor checks passed，就可以双击 3_打开真实交易控制台.command。"
echo "如果显示缺少 key 或确认文本，请回到 1_编辑API配置.command。"
read -k 1 "?按任意键关闭这个窗口..."
