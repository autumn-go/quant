#!/bin/bash
# 每日增量更新脚本 - 在每个交易日 15:35 执行
# 自动采集当日数据并推送到 Gitee

set -e

REPO_DIR="/root/.openclaw/workspace/quant-gitee"
COLLECTOR_DIR="$REPO_DIR/data-collector"
LOG_FILE="$COLLECTOR_DIR/logs/daily_update.log"

# 创建日志目录
mkdir -p "$COLLECTOR_DIR/logs"

echo "============================================" | tee -a "$LOG_FILE"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] 开始每日增量更新..." | tee -a "$LOG_FILE"

cd "$COLLECTOR_DIR"

# 激活虚拟环境
source venv/bin/activate

# 检查是否为交易日 (A股交易日判断)
WEEKDAY=$(date +%u)
if [ "$WEEKDAY" -gt 5 ]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] 今天是周末，跳过更新" | tee -a "$LOG_FILE"
    exit 0
fi

# 执行增量更新
echo "[$(date '+%Y-%m-%d %H:%M:%S')] 执行增量数据采集..." | tee -a "$LOG_FILE"
python3 collect_2026.py --update 2>&1 | tee -a "$LOG_FILE"
UPDATE_STATUS=${PIPESTATUS[0]}

if [ $UPDATE_STATUS -ne 0 ]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ❌ 采集失败，退出码: $UPDATE_STATUS" | tee -a "$LOG_FILE"
    exit 1
fi

# 查看统计
echo "[$(date '+%Y-%m-%d %H:%M:%S')] 当前数据统计:" | tee -a "$LOG_FILE"
python3 collect_2026.py --stats 2>&1 | tee -a "$LOG_FILE"

# 推送到 Gitee
echo "[$(date '+%Y-%m-%d %H:%M:%S')] 推送到 Gitee..." | tee -a "$LOG_FILE"
bash push_to_gitee.sh 2>&1 | tee -a "$LOG_FILE"

PUSH_STATUS=${PIPESTATUS[0]}
if [ $PUSH_STATUS -ne 0 ]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ❌ 推送失败" | tee -a "$LOG_FILE"
    exit 1
fi

echo "[$(date '+%Y-%m-%d %H:%M:%S')] ✅ 每日更新完成" | tee -a "$LOG_FILE"
echo "============================================" | tee -a "$LOG_FILE"
exit 0
