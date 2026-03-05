#!/usr/bin/env python3
"""
批量采集2014年以来A股个股和指数日K数据
"""

import os
import sys
import time
from datetime import datetime
from loguru import logger

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data_collector.tushare_collector import TushareCollector
from shared.models import Stock, DailyPrice

# 配置日志
logger.add("logs/collect_{time}.log", rotation="500 MB", level="INFO")

# Tushare Token - 请替换为你的Token
TUSHARE_TOKEN = os.getenv("TUSHARE_TOKEN", "")

# 数据库配置
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://quant:quant@localhost:5432/quant_db")


def collect_all_data():
    """采集所有历史数据 (2014年至今)"""
    
    if not TUSHARE_TOKEN:
        logger.error("请设置 TUSHARE_TOKEN 环境变量")
        print("错误: 未设置 TUSHARE_TOKEN")
        print("请设置环境变量: export TUSHARE_TOKEN='your_token_here'")
        return
    
    collector = TushareCollector(db_url=DATABASE_URL, token=TUSHARE_TOKEN)
    
    try:
        # 1. 先同步股票列表
        logger.info("=" * 60)
        logger.info("Step 1: 同步股票和指数列表")
        logger.info("=" * 60)
        collector.sync_stock_list()
        
        # 查看统计
        stats = collector.get_data_stats()
        logger.info(f"股票总数: {stats['total_stocks']}")
        logger.info(f"市场分布: {stats['market_breakdown']}")
        
        # 2. 采集历史日线数据 (2014-01-01 至今)
        logger.info("=" * 60)
        logger.info("Step 2: 采集历史日线数据 (2014-01-01 至今)")
        logger.info("=" * 60)
        
        start_date = '20140101'
        end_date = datetime.now().strftime('%Y%m%d')
        
        logger.info(f"数据范围: {start_date} - {end_date}")
        logger.info("开始采集...")
        
        # 获取所有股票和指数
        stocks = collector.session.query(Stock).all()
        symbols = [s.symbol for s in stocks]
        
        logger.info(f"共 {len(symbols)} 个标的需要采集")
        
        # 分批采集
        collector.sync_daily_prices(
            symbols=symbols,
            start_date=start_date,
            end_date=end_date,
            batch_size=50  # 每批50个，避免API限流
        )
        
        # 3. 最终统计
        logger.info("=" * 60)
        logger.info("Step 3: 数据采集完成")
        logger.info("=" * 60)
        
        final_stats = collector.get_data_stats()
        logger.info(f"最终统计:")
        logger.info(f"  股票总数: {final_stats['total_stocks']}")
        logger.info(f"  价格记录: {final_stats['total_price_records']}")
        
        print("\n" + "=" * 60)
        print("数据采集完成!")
        print(f"股票总数: {final_stats['total_stocks']}")
        print(f"价格记录: {final_stats['total_price_records']}")
        print("=" * 60)
        
    except Exception as e:
        logger.error(f"采集过程中出错: {e}")
        raise
    finally:
        collector.close()


def collect_indices_only():
    """仅采集指数数据"""
    
    if not TUSHARE_TOKEN:
        print("错误: 未设置 TUSHARE_TOKEN")
        return
    
    collector = TushareCollector(db_url=DATABASE_URL, token=TUSHARE_TOKEN)
    
    try:
        # 只同步指数列表
        logger.info("同步指数列表...")
        index_df = collector.fetch_index_list()
        if not index_df.empty:
            collector._save_stock_list(index_df)
            collector.session.commit()
        
        # 获取指数symbol
        indices = collector.session.query(Stock).filter_by(market='指数').all()
        symbols = [s.symbol for s in indices]
        
        logger.info(f"共 {len(symbols)} 个指数")
        
        # 采集指数数据
        collector.sync_daily_prices(
            symbols=symbols,
            start_date='20140101',
            end_date=datetime.now().strftime('%Y%m%d'),
            batch_size=20
        )
        
        print("指数数据采集完成!")
        
    finally:
        collector.close()


def collect_single_stock(symbol: str):
    """采集单个股票数据"""
    
    if not TUSHARE_TOKEN:
        print("错误: 未设置 TUSHARE_TOKEN")
        return
    
    collector = TushareCollector(db_url=DATABASE_URL, token=TUSHARE_TOKEN)
    
    try:
        logger.info(f"采集 {symbol} 数据...")
        collector.sync_daily_prices(
            symbols=[symbol],
            start_date='20140101',
            end_date=datetime.now().strftime('%Y%m%d')
        )
        logger.info(f"{symbol} 采集完成")
        
    finally:
        collector.close()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="批量采集A股历史数据")
    parser.add_argument("--all", action="store_true", help="采集所有数据")
    parser.add_argument("--indices", action="store_true", help="仅采集指数")
    parser.add_argument("--symbol", type=str, help="采集单个股票")
    parser.add_argument("--token", type=str, help="Tushare Token")
    
    args = parser.parse_args()
    
    if args.token:
        TUSHARE_TOKEN = args.token
    
    # 创建日志目录
    os.makedirs("logs", exist_ok=True)
    
    if args.all:
        collect_all_data()
    elif args.indices:
        collect_indices_only()
    elif args.symbol:
        collect_single_stock(args.symbol)
    else:
        parser.print_help()
        print("\n示例:")
        print("  python collect_history.py --all              # 采集所有数据")
        print("  python collect_history.py --indices          # 仅采集指数")
        print("  python collect_history.py --symbol 000001.SZ # 采集单个股票")
