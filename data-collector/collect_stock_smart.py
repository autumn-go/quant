#!/usr/bin/env python3
"""
智能采集成分股日K数据 - 利用已有数据
1. 已有数据的股票：只更新缺失的日期
2. 没有数据的股票：从2026-01-01开始采集
"""

import tushare as ts
import sqlite3
import time
from datetime import datetime, timedelta

TOKEN = '75d5fb0d2da34ab076f1ab49eaecfac348aaf91faf06246bfcab9f68904c'
DB_PATH = 'quant_data.db'

def init_tushare():
    pro = ts.pro_api(TOKEN)
    pro._DataApi__token = TOKEN
    pro._DataApi__http_url = 'http://lianghua.nanyangqiankun.top'
    return pro

def get_last_date(conn, symbol):
    """获取某只股票的最后更新日期"""
    cursor = conn.execute('SELECT MAX(date) FROM daily_prices WHERE symbol = ?', (symbol,))
    result = cursor.fetchone()[0]
    return result

def collect_stock(pro, conn, stock_code, start_date, end_date):
    """采集单只股票的数据"""
    try:
        df = pro.daily(ts_code=stock_code, start_date=start_date, end_date=end_date)
        
        if df is not None and not df.empty:
            count = 0
            for _, row in df.iterrows():
                try:
                    conn.execute('''
                        INSERT OR IGNORE INTO daily_prices 
                        (symbol, date, open, high, low, close, volume, amount)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (row['ts_code'], row['trade_date'], float(row['open']),
                          float(row['high']), float(row['low']), float(row['close']),
                          float(row['vol']), float(row['amount'])))
                    count += 1
                except Exception as e:
                    print(f"Insert error: {e}")
                    pass
            conn.commit()
            return count
    except Exception as e:
        pass
    return 0

def main():
    pro = init_tushare()
    conn = sqlite3.connect(DB_PATH)
    
    # 获取所有成分股
    cursor = conn.execute('SELECT DISTINCT stock_code FROM ths_industry_members')
    all_stocks = [row[0] for row in cursor.fetchall()]
    
    # 获取已有数据的股票
    cursor = conn.execute('SELECT DISTINCT symbol FROM daily_prices')
    existing_stocks = set(row[0] for row in cursor.fetchall())
    
    # 分类
    stocks_to_update = []  # 有数据，需要更新
    stocks_to_collect = []  # 无数据，需要完整采集
    
    for stock in all_stocks:
        if stock in existing_stocks:
            last_date = get_last_date(conn, stock)
            if last_date and last_date < '20260304':
                stocks_to_update.append({
                    'code': stock,
                    'start': (datetime.strptime(last_date, '%Y%m%d') + timedelta(days=1)).strftime('%Y%m%d')
                })
        else:
            stocks_to_collect.append(stock)
    
    print(f"成分股总数: {len(all_stocks)}")
    print(f"已有数据需更新: {len(stocks_to_update)}")
    print(f"无数据需采集: {len(stocks_to_collect)}")
    
    # 第一步：更新已有数据
    if stocks_to_update:
        print(f"\n=== 更新已有数据 ===")
        success = 0
        for i, item in enumerate(stocks_to_update, 1):
            count = collect_stock(pro, conn, item['code'], item['start'], '20260304')
            if count > 0:
                success += 1
            if i % 20 == 0:
                print(f"  [{i}/{len(stocks_to_update)}] 成功:{success}")
            time.sleep(0.03)
        print(f"更新完成: {success}/{len(stocks_to_update)}")
    
    # 第二步：采集缺失的股票（从2026-01-01开始）
    if stocks_to_collect:
        print(f"\n=== 采集缺失股票 ===")
        success = 0
        total_records = 0
        for i, stock in enumerate(stocks_to_collect, 1):
            count = collect_stock(pro, conn, stock, '20260101', '20260304')
            if count > 0:
                success += 1
                total_records += count
            if i % 100 == 0:
                print(f"  [{i}/{len(stocks_to_collect)}] 成功:{success} 记录:{total_records}")
            time.sleep(0.03)
        print(f"采集完成: {success}/{len(stocks_to_collect)}, 共 {total_records} 条")
    
    # 统计
    cursor = conn.execute('SELECT MAX(date) FROM daily_prices')
    max_date = cursor.fetchone()[0]
    print(f"\n数据最新日期: {max_date}")
    
    conn.close()

if __name__ == '__main__':
    main()
