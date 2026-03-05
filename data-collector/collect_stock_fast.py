#!/usr/bin/env python3
"""
快速采集成分股日K数据 - 简化版
直接采集2026-02-27到2026-03-04的数据
"""

import tushare as ts
import sqlite3
import time

TOKEN = '75d5fb0d2da34ab076f1ab49eaecfac348aaf91faf06246bfcab9f68904c'
DB_PATH = 'quant_data.db'
START_DATE = '20260227'
END_DATE = '20260304'

def init_tushare():
    pro = ts.pro_api(TOKEN)
    pro._DataApi__token = TOKEN
    pro._DataApi__http_url = 'http://lianghua.nanyangqiankun.top'
    return pro

def main():
    pro = init_tushare()
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.execute('SELECT DISTINCT stock_code FROM ths_industry_members')
    stocks = [row[0] for row in cursor.fetchall()]
    conn.close()
    
    print(f"开始采集 {len(stocks)} 只成分股...")
    print(f"日期范围: {START_DATE} ~ {END_DATE}")
    
    success = 0
    failed = 0
    
    for i, stock_code in enumerate(stocks, 1):
        try:
            df = pro.daily(ts_code=stock_code, start_date=START_DATE, end_date=END_DATE)
            
            if df is not None and not df.empty:
                conn = sqlite3.connect(DB_PATH)
                
                for _, row in df.iterrows():
                    try:
                        conn.execute('''
                            INSERT OR IGNORE INTO daily_prices 
                            (symbol, date, open, high, low, close, volume, amount, change, pct_chg)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ''', (row['ts_code'], row['trade_date'], float(row['open']),
                              float(row['high']), float(row['low']), float(row['close']),
                              float(row['vol']), float(row['amount']),
                              float(row.get('change', 0)), float(row.get('pct_chg', 0))))
                    except:
                        pass
                
                conn.commit()
                conn.close()
                success += 1
            
            if i % 100 == 0:
                print(f"  [{i}/{len(stocks)}] 成功:{success} 失败:{failed}")
            
            time.sleep(0.02)
            
        except Exception as e:
            failed += 1
            if i % 100 == 0:
                print(f"  [{i}/{len(stocks)}] 失败: {e}")
            time.sleep(0.1)
    
    print(f"\n完成! 成功:{success} 失败:{failed}")
    
    # 统计
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.execute('SELECT MAX(date) FROM daily_prices')
    max_date = cursor.fetchone()[0]
    print(f"数据最新日期: {max_date}")
    conn.close()

if __name__ == '__main__':
    main()
