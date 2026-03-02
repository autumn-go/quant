#!/bin/bash
# GitHub自动推送脚本

REPO_DIR="/root/.openclaw/workspace/quant-platform"
DB_FILE="$REPO_DIR/data-collector/quant_data_2024.db"
LOG_FILE="$REPO_DIR/data-collector/logs/push.log"

# 创建日志目录
mkdir -p "$REPO_DIR/data-collector/logs"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] 开始推送..." >> "$LOG_FILE"

cd "$REPO_DIR"

# 检查数据库文件是否存在
if [ ! -f "$DB_FILE" ]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] 错误: 数据库文件不存在" >> "$LOG_FILE"
    exit 1
fi

# 获取数据库大小
DB_SIZE=$(du -h "$DB_FILE" | cut -f1)
echo "[$(date '+%Y-%m-%d %H:%M:%S')] 数据库大小: $DB_SIZE" >> "$LOG_FILE"

# 配置Git
git config user.email "collector@quant.local" 2>/dev/null
git config user.name "Quant Collector" 2>/dev/null

# 添加数据库文件
git add data-collector/quant_data_2024.db

# 检查是否有变更
if git diff --cached --quiet; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] 没有变更，跳过推送" >> "$LOG_FILE"
    exit 0
fi

# 提交
git commit -m "Update quant data $(date '+%Y-%m-%d %H:%M:%S') - Size: $DB_SIZE"

# 推送到GitHub (带重试)
MAX_RETRIES=3
RETRY_COUNT=0

while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    if git push origin main; then
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] 推送成功" >> "$LOG_FILE"
        exit 0
    else
        RETRY_COUNT=$((RETRY_COUNT + 1))
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] 推送失败，重试 $RETRY_COUNT/$MAX_RETRIES..." >> "$LOG_FILE"
        sleep 5
    fi
done

echo "[$(date '+%Y-%m-%d %H:%M:%S')] 推送失败，已达最大重试次数" >> "$LOG_FILE"
exit 1
