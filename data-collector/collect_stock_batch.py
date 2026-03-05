#!/usr/bin/env python3
"""
分批采集成分股日K数据
"""

import tushare as ts
import sqlite3
import time
import sys

TOKEN = '75d5fb0d2da34ab076f1ab49eaecfac348aaf91faf06246bfcab9f68904c'
DB_PATH = 'quant_data.db'

def init_tushare():
    pro = ts.pro_api(TOKEN)
    pro._DataApi__token = TOKEN
    pro._DataApi__http_url = 'http://lianghua.nanyangqiankun.top'
    return pro

def collect_batch(stocks, pro, start_date, end_date):
    """采集一批股票"""
    success = 0
    for stock_code in stocks:
        try:
            df = pro.daily(ts_code=stock_code, start_date=start_date, end_date=end_date)
            
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
            time.sleep(0.02)
        except:
            pass
    return success

def main():
    pro = init_tushare()
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.execute('SELECT DISTINCT stock_code FROM ths_industry_members')
    all_stocks = [row[0] for row in cursor.fetchall()]
    conn.close()
    
    print(f"总共 {len(all_stocks)} 只成分股")
    print("日期: 20260227 ~ 20260304")
    
    # 分批采集
    batch_size = 500
    total_success = 0
    
    for i in range(0, len(all_stocks), batch_size):
        batch = all_stocks[i:i+batch_size]
        success = collect_batch(batch, pro, '20260227', '20260304')
        total_success += success
        
        print(f"  批次 {i//batch_size + 1}/{(len(all_stocks)+batch_size-1)//batch_size}: "
              f"完成 {success}/{len(batch)}, 累计成功 {total_success}")
    
    print(f"\n完成! 总成功: {total_success}/{len(all_stocks)}")

if __name__ == '__main__':
    main()
