#!/bin/bash
# Gitee 自动推送脚本 - 用于 2026 年数据
# 配合 Gitee 的 Github 镜像功能使用

REPO_DIR="/root/.openclaw/workspace/quant-gitee"
DB_FILE="$REPO_DIR/data-collector/quant_data_2026.db"
LOG_FILE="$REPO_DIR/data-collector/logs/push.log"

# 创建日志目录
mkdir -p "$REPO_DIR/data-collector/logs"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] 开始推送到 Gitee..." | tee -a "$LOG_FILE"

cd "$REPO_DIR"

# 检查数据库文件是否存在
if [ ! -f "$DB_FILE" ]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] 错误: 数据库文件不存在" | tee -a "$LOG_FILE"
    exit 1
fi

# 获取数据库大小
DB_SIZE=$(du -h "$DB_FILE" | cut -f1)
echo "[$(date '+%Y-%m-%d %H:%M:%S')] 数据库大小: $DB_SIZE" | tee -a "$LOG_FILE"

# 配置Git
git config user.email "collector@quant.local" 2>/dev/null
git config user.name "Quant Collector 2026" 2>/dev/null

# 添加数据库文件
git add data-collector/quant_data_2026.db

# 检查是否有变更
if git diff --cached --quiet; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] 没有变更，跳过推送" | tee -a "$LOG_FILE"
    exit 0
fi

# 提交
DATE_STR=$(date '+%Y-%m-%d %H:%M:%S')
git commit -m "Update 2026 quant data - $DATE_STR - Size: $DB_SIZE"

# 推送到 Gitee (带重试)
MAX_RETRIES=3
RETRY_COUNT=0

while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    if git push origin main; then
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] ✅ 推送到 Gitee 成功" | tee -a "$LOG_FILE"
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] 💡 Github 镜像会自动同步，约 5-10 分钟后生效" | tee -a "$LOG_FILE"
        exit 0
    else
        RETRY_COUNT=$((RETRY_COUNT + 1))
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] 推送失败，重试 $RETRY_COUNT/$MAX_RETRIES..." | tee -a "$LOG_FILE"
        sleep 5
    fi
done

echo "[$(date '+%Y-%m-%d %H:%M:%S')] ❌ 推送失败，已达最大重试次数" | tee -a "$LOG_FILE"
exit 1
