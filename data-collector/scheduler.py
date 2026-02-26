"""
定时任务调度器
负责每日定时更新数据
"""

import schedule
import time
import os
from datetime import datetime
from collector import DataCollector
from loguru import logger

# 数据库配置
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://quant:quant@localhost:5432/quant_db")


def job_update_stock_list():
    """每月更新一次股票列表（处理新股上市、退市）"""
    logger.info("[Scheduled] Updating stock list...")
    collector = DataCollector(DATABASE_URL)
    try:
        collector.sync_stock_list()
        logger.info("[Scheduled] Stock list updated")
    except Exception as e:
        logger.error(f"[Scheduled] Failed to update stock list: {e}")
    finally:
        collector.close()


def job_incremental_update():
    """每日收盘后增量更新"""
    logger.info("[Scheduled] Incremental price update...")
    collector = DataCollector(DATABASE_URL)
    try:
        collector.incremental_update()
        logger.info("[Scheduled] Incremental update completed")
    except Exception as e:
        logger.error(f"[Scheduled] Failed to update prices: {e}")
    finally:
        collector.close()


def job_full_update():
    """每周六全量更新（修复可能的数据缺失）"""
    logger.info("[Scheduled] Full price update...")
    collector = DataCollector(DATABASE_URL)
    try:
        # 更新最近30天
        from datetime import timedelta
        end_date = datetime.now().strftime('%Y%m%d')
        start_date = (datetime.now() - timedelta(days=30)).strftime('%Y%m%d')
        collector.sync_daily_prices(start_date=start_date, end_date=end_date)
        logger.info("[Scheduled] Full update completed")
    except Exception as e:
        logger.error(f"[Scheduled] Failed full update: {e}")
    finally:
        collector.close()


def main():
    """启动调度器"""
    logger.info("Starting Data Collector Scheduler...")
    
    # 每日收盘后更新 (A股15:30收盘，港股16:00收盘)
    # 17:00 执行增量更新
    schedule.every().day.at("17:00").do(job_incremental_update)
    
    # 每周六凌晨全量更新
    schedule.every().saturday.at("02:00").do(job_full_update)
    
    # 每月1号更新股票列表
    schedule.every().month.at("03:00").do(job_update_stock_list)
    
    logger.info("Scheduler started. Jobs:")
    logger.info("  - Daily incremental update at 17:00")
    logger.info("  - Weekly full update on Saturday 02:00")
    logger.info("  - Monthly stock list update on 1st 03:00")
    
    while True:
        schedule.run_pending()
        time.sleep(60)


if __name__ == "__main__":
    main()