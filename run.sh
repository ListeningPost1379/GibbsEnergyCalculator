#!/bin/bash
# run.sh

# 1. 确保使用 uv 运行
if ! command -v uv &> /dev/null; then
    echo "Error: uv is not installed."
    exit 1
fi

# 2. 同步环境 (如果换了机器，这步会自动安装 pandas 等依赖)
echo "Syncing environment..."
uv sync

# 3. 启动主程序 (nohup 后台运行，防止断网中断)
echo "Starting Gibbs Workflow in background..."
nohup uv run gibbs-run > workflow.log 2>&1 &

echo "Workflow started! Check workflow.log for details."
echo "PID: $!"