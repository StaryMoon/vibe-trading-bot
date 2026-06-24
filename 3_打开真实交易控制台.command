#!/bin/zsh
set -e
cd "$(dirname "$0")"

if [ ! -d ".venv" ]; then
  echo "没有找到 .venv，先安装依赖。"
  python3 -m venv .venv
  .venv/bin/python -m pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org -i https://pypi.org/simple -e ".[dev,ai]"
fi

source .venv/bin/activate
mkdir -p logs

echo "正在打开真实交易控制台..."
echo "浏览器地址：http://127.0.0.1:8501"
echo "关闭这个终端窗口后，控制台也会停止。"

python -m streamlit run src/vibe_trader/dashboard/streamlit_app.py \
  --server.headless true \
  --server.address 127.0.0.1 \
  --server.port 8501 \
  -- \
  --config configs/live_binance_spot_small.yaml
