#!/usr/bin/env python3
"""
数据就绪检查脚本
"""

import sqlite3
import sys

def check_data():
    conn = sqlite3.connect('quant_data.db')
    
    print("=" * 60)
    print("数据就绪检查")
    print("=" * 60)
    
    # 检查行业列表
    cursor = conn.execute('SELECT COUNT(*) FROM ths_industries')
    industries = cursor.fetchone()[0]
    print(f"✓ 行业列表: {industries} 个")
    
    # 检查成分股
    cursor = conn.execute('SELECT COUNT(*) FROM ths_industry_members')
    members = cursor.fetchone()[0]
    print(f"✓ 行业成分股: {members} 只")
    
    # 检查行业指数日线
    cursor = conn.execute('SELECT COUNT(*) FROM ths_industry_daily')
    industry_daily = cursor.fetchone()[0]
    cursor = conn.execute('SELECT MIN(trade_date), MAX(trade_date) FROM ths_industry_daily')
    industry_range = cursor.fetchone()
    print(f"✓ 行业指数日线: {industry_daily} 条 ({industry_range[0]} ~ {industry_range[1]})")
    
    # 检查个股日线
    cursor = conn.execute('SELECT COUNT(*) FROM daily_prices')
    stock_daily = cursor.fetchone()[0]
    cursor = conn.execute('SELECT MIN(date), MAX(date) FROM daily_prices')
    stock_range = cursor.fetchone()
    print(f"✓ 个股日K数据: {stock_daily:,} 条")
    if stock_range[0]:
        print(f"  日期范围: {stock_range[0]} ~ {stock_range[1]}")
    
    # 检查成分股覆盖度
    cursor = conn.execute('SELECT DISTINCT stock_code FROM ths_industry_members')
    member_stocks = set(row[0] for row in cursor.fetchall())
    cursor = conn.execute('SELECT DISTINCT symbol FROM daily_prices')
    daily_stocks = set(row[0] for row in cursor.fetchall())
    coverage = len(member_stocks & daily_stocks)
    print(f"✓ 成分股覆盖: {coverage}/{len(member_stocks)} ({coverage/len(member_stocks)*100:.1f}%)")
    
    print("=" * 60)
    
    # 判断是否可以运行策略
    if industries >= 90 and industry_daily > 3000 and coverage >= len(member_stocks) * 0.9:
        print("✅ 数据就绪，可以运行策略！")
        conn.close()
        return True
    else:
        print("⚠️ 数据尚未完全就绪，请等待采集完成")
        conn.close()
        return False

if __name__ == '__main__':
    if check_data():
        sys.exit(0)
    else:
        sys.exit(1)
