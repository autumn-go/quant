#!/usr/bin/env python3
"""
同花顺一级行业数据采集器
- 导入行业列表到数据库
- 采集2026年以来行业指数日K数据
"""

import sqlite3
import pandas as pd
from datetime import datetime
import time
import os
import sys
from loguru import logger

# 配置日志
logger.remove()
logger.add(sys.stderr, level="INFO")
logger.add("logs/industry_collect.log", rotation="50 MB", level="DEBUG")

DB_PATH = "quant_data_2026.db"
INDUSTRY_FILE = "../data/industries_ths_level1.csv"


def init_industry_tables(conn):
    """初始化行业相关表"""
    c = conn.cursor()
    
    # 行业列表表
    c.execute('''CREATE TABLE IF NOT EXISTS ths_industries (
        ts_code TEXT PRIMARY KEY,
        name TEXT,
        count INTEGER,
        exchange TEXT,
        list_date TEXT,
        type TEXT
    )''')
    
    # 行业日线数据表
    c.execute('''CREATE TABLE IF NOT EXISTS industry_daily (
        ts_code TEXT,
        trade_date TEXT,
        open REAL,
        high REAL,
        low REAL,
        close REAL,
        volume REAL,
        amount REAL,
        PRIMARY KEY (ts_code, trade_date)
    )''')
    
    # 行业采集进度表
    c.execute('''CREATE TABLE IF NOT EXISTS industry_progress (
        ts_code TEXT PRIMARY KEY,
        last_date TEXT,
        status TEXT,
        updated_at TEXT
    )''')
    
    conn.commit()
    logger.info("Industry tables initialized")


def import_industry_list(conn):
    """导入行业列表"""
    df = pd.read_csv(INDUSTRY_FILE, encoding='utf-8')
    
    c = conn.cursor()
    count = 0
    for _, row in df.iterrows():
        try:
            c.execute('''INSERT OR REPLACE INTO ths_industries 
                (ts_code, name, count, exchange, list_date, type)
                VALUES (?, ?, ?, ?, ?, ?)''',
                (row['ts_code'], row['name'], 
                 row['count'] if pd.notna(row['count']) else None,
                 row['exchange'], row['list_date'], row['type'])
            )
            count += 1
        except Exception as e:
            logger.error(f"Failed to import {row['ts_code']}: {e}")
    
    conn.commit()
    logger.info(f"Imported {count} industries")
    return count


def get_industry_stats(conn):
    """获取行业统计"""
    c = conn.cursor()
    
    c.execute('SELECT COUNT(*) FROM ths_industries')
    total = c.fetchone()[0]
    
    c.execute('SELECT COUNT(*) FROM industry_daily')
    daily_count = c.fetchone()[0]
    
    c.execute('SELECT COUNT(DISTINCT ts_code) FROM industry_daily')
    with_data = c.fetchone()[0]
    
    c.execute('SELECT MIN(trade_date), MAX(trade_date) FROM industry_daily')
    date_range = c.fetchone()
    
    return {
        'total_industries': total,
        'daily_records': daily_count,
        'industries_with_data': with_data,
        'date_range': date_range
    }


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='同花顺一级行业数据管理')
    parser.add_argument('--init', action='store_true', help='导入行业列表')
    parser.add_argument('--stats', action='store_true', help='查看统计')
    
    args = parser.parse_args()
    
    os.makedirs('logs', exist_ok=True)
    
    conn = sqlite3.connect(DB_PATH)
    init_industry_tables(conn)
    
    if args.init:
        count = import_industry_list(conn)
        print(f"\n成功导入 {count} 个一级行业")
        
        # 显示行业列表
        df = pd.read_sql('SELECT ts_code, name, count FROM ths_industries ORDER BY ts_code', conn)
        print("\n行业列表：")
        print(df.to_string(index=False))
    
    elif args.stats:
        stats = get_industry_stats(conn)
        print("\n" + "=" * 60)
        print("同花顺一级行业统计")
        print("=" * 60)
        print(f"行业总数: {stats['total_industries']}")
        print(f"日线记录: {stats['daily_records']}")
        print(f"有数据行业: {stats['industries_with_data']}")
        if stats['date_range'] and stats['date_range'][0]:
            print(f"数据范围: {stats['date_range'][0]} ~ {stats['date_range'][1]}")
        print("=" * 60)
    
    else:
        parser.print_help()
        print("\n示例:")
        print("  python3 industry_collector.py --init    # 导入行业列表")
        print("  python3 industry_collector.py --stats   # 查看统计")
    
    conn.close()


if __name__ == '__main__':
    main()
