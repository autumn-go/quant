"""
模拟数据生成器 - 用于演示回测系统
生成2014年以来的模拟日线数据
"""

import sqlite3
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import random

def generate_mock_data(db_path: str = "quant_data.db"):
    """生成模拟历史数据"""
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # 获取股票列表
    cursor.execute("SELECT symbol, name FROM stocks LIMIT 50")
    stocks = cursor.fetchall()
    
    if not stocks:
        print("[ERROR] 请先运行 --init 初始化股票列表")
        return
    
    print(f"[INFO] 为 {len(stocks)} 只股票生成模拟数据...")
    
    # 生成2014年以来的交易日
    start_date = datetime(2014, 1, 1)
    end_date = datetime.now()
    
    total_records = 0
    
    for symbol, name in stocks:
        # 生成随机 walk 数据
        np.random.seed(hash(symbol) % 2**32)
        
        # 初始价格
        base_price = random.uniform(10, 100)
        
        # 生成每日数据
        current_date = start_date
        records = []
        
        while current_date <= end_date:
            # 跳过周末
            if current_date.weekday() >= 5:
                current_date += timedelta(days=1)
                continue
            
            # 随机涨跌 (-3% ~ +3%)
            change_pct = np.random.normal(0, 0.02)
            
            # 计算价格
            if records:
                prev_close = records[-1]['close']
            else:
                prev_close = base_price
            
            close = prev_close * (1 + change_pct)
            high = close * (1 + abs(np.random.normal(0, 0.01)))
            low = close * (1 - abs(np.random.normal(0, 0.01)))
            open_price = prev_close * (1 + np.random.normal(0, 0.005))
            
            # 成交量 (随机)
            volume = int(random.uniform(1000000, 100000000))
            amount = volume * close
            
            records.append({
                'symbol': symbol,
                'date': current_date.strftime('%Y-%m-%d'),
                'open': round(open_price, 2),
                'high': round(high, 2),
                'low': round(low, 2),
                'close': round(close, 2),
                'volume': volume,
                'amount': round(amount, 2)
            })
            
            current_date += timedelta(days=1)
        
        # 批量插入
        for record in records:
            try:
                cursor.execute('''
                    INSERT OR IGNORE INTO daily_prices 
                    (symbol, date, open, high, low, close, volume, amount)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    record['symbol'], record['date'],
                    record['open'], record['high'], record['low'],
                    record['close'], record['volume'], record['amount']
                ))
                total_records += 1
            except Exception as e:
                print(f"[ERROR] {symbol} {record['date']}: {e}")
        
        if total_records % 10000 == 0:
            print(f"[INFO] 已生成 {total_records} 条记录...")
    
    conn.commit()
    conn.close()
    
    print(f"[INFO] 完成! 总计生成 {total_records} 条模拟数据")

if __name__ == '__main__':
    generate_mock_data()
