#!/usr/bin/env python3
"""
快速采集成分股日K数据（增量更新）
"""

import tushare as ts
import sqlite3
from datetime import datetime, timedelta
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
    cursor = conn.execute('SELECT DISTINCT stock_code FROM ths_industry_members')
    stocks = [row[0] for row in cursor.fetchall()]
    conn.close()
    
    end_date = '20260304'
    
    print(f"开始采集 {len(stocks)} 只成分股的日K数据...")
    print(f"目标日期: 更新到 {end_date}")
    
    success = 0
    total_records = 0
    start_time = time.time()
    
    for i, stock_code in enumerate(stocks, 1):
        try:
            # 检查最新日期
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.execute(
                'SELECT MAX(date) FROM daily_prices WHERE symbol = ?',
                (stock_code,)
            )
            last_date = cursor.fetchone()[0]
            conn.close()
            
            if last_date and last_date >= end_date:
                continue
            
            if last_date:
                start = (datetime.strptime(last_date, '%Y%m%d') + timedelta(days=1)).strftime('%Y%m%d')
            else:
                start = '20260101'
            
            if start > end_date:
                continue
            
            df = pro.daily(ts_code=stock_code, start_date=start, end_date=end_date)
            
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
                total_records += len(df)
                
                if success % 100 == 0:
                    elapsed = time.time() - start_time
                    print(f"  [{i}/{len(stocks)}] 成功:{success} 记录:{total_records} 用时:{elapsed/60:.1f}分")
            
            time.sleep(0.03)  # 限速
            
        except Exception as e:
            if i % 100 == 0:
                print(f"  [WARN] {stock_code} 失败: {e}")
            time.sleep(0.1)
    
    elapsed = time.time() - start_time
    print(f"\n完成! 成功:{success} 只股票, 共 {total_records} 条记录, 用时:{elapsed/60:.1f}分")

if __name__ == '__main__':
    main()
