"""
数据更新调度器
每日自动更新股票数据
"""

import schedule
import time
import subprocess
import sys
from datetime import datetime
from loguru import logger

# 配置日志
logger.remove()
logger.add(sys.stderr, level="INFO")
logger.add("logs/scheduler.log", rotation="10 MB", level="INFO")

def run_update():
    """执行每日更新"""
    logger.info(f"Starting daily update at {datetime.now()}")
    
    try:
        # 增量更新所有数据
        result = subprocess.run(
            [sys.executable, "historical_collector.py", "--update"],
            capture_output=True,
            text=True,
            timeout=3600  # 1小时超时
        )
        
        if result.returncode == 0:
            logger.info("Daily update completed successfully")
        else:
            logger.error(f"Update failed: {result.stderr}")
            
    except Exception as e:
        logger.error(f"Update exception: {e}")

def run_full_collection():
    """执行全量采集（周末）"""
    logger.info(f"Starting full collection at {datetime.now()}")
    
    try:
        result = subprocess.run(
            [sys.executable, "historical_collector.py", "--full"],
            capture_output=True,
            text=True,
            timeout=7200  # 2小时超时
        )
        
        if result.returncode == 0:
            logger.info("Full collection completed successfully")
        else:
            logger.error(f"Collection failed: {result.stderr}")
            
    except Exception as e:
        logger.error(f"Collection exception: {e}")

# 设置定时任务
# 每日收盘后更新（15:30）
schedule.every().day.at("15:30").do(run_update)

# 每周六凌晨执行全量检查
schedule.every().saturday.at("02:00").do(run_full_collection)

logger.info("Scheduler started")
logger.info("Daily update: 15:30")
logger.info("Full collection: Saturday 02:00")

# 保持运行
while True:
    schedule.run_pending()
    time.sleep(60)
