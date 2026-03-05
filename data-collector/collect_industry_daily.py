#!/usr/bin/env python3
"""
快速采集同花顺行业指数日线数据
"""

import tushare as ts
import sqlite3
import pandas as pd
from datetime import datetime
import time

TOKEN = '75d5fb0d2da34ab076f1ab49eaecfac348aaf91faf06246bfcab9f68904c'
DB_PATH = 'quant_data.db'

def init_tushare():
    pro = ts.pro_api(TOKEN)
    pro._DataApi__token = TOKEN
    pro._DataApi__http_url = 'http://lianghua.nanyangqiankun.top'
    return pro

def main():
    pro = init_tushare()
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.execute('SELECT ts_code, name FROM ths_industries')
    industries = cursor.fetchall()
    conn.close()
    
    print(f"开始采集 {len(industries)} 个行业指数日线数据...")
    
    success = 0
    total_records = 0
    
    for i, (ts_code, name) in enumerate(industries, 1):
        try:
            df = pro.ths_daily(ts_code=ts_code, start_date='20260101', end_date='20260304')
            
            if df is not None and not df.empty:
                conn = sqlite3.connect(DB_PATH)
                
                for _, row in df.iterrows():
                    try:
                        # 获取成交额（如果没有amount，用avg_price * vol估算）
                        amount = row.get('amount', 0)
                        if pd.isna(amount) or amount == 0:
                            amount = row['avg_price'] * row['vol'] if 'avg_price' in row else 0
                        
                        conn.execute('''
                            INSERT OR IGNORE INTO ths_industry_daily 
                            (ts_code, trade_date, open, high, low, close, volume, amount, pct_chg)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ''', (row['ts_code'], row['trade_date'], float(row['open']), 
                              float(row['high']), float(row['low']), float(row['close']),
                              float(row['vol']), float(amount), 
                              float(row.get('pct_change', 0))))
                    except Exception as e:
                        print(f"Insert error: {e}")
                        pass
                
                conn.commit()
                conn.close()
                
                success += 1
                total_records += len(df)
                
                if success % 10 == 0:
                    print(f"  [{i}/{len(industries)}] 已采集 {success} 个行业, 共 {total_records} 条记录")
            
            time.sleep(0.1)
            
        except Exception as e:
            if i % 20 == 0:
                print(f"  [WARN] {name} 失败: {e}")
            time.sleep(0.3)
    
    print(f"\n完成! 成功:{success} 个行业, 共 {total_records} 条记录")

if __name__ == '__main__':
    main()
