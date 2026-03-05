#!/usr/bin/env python3
"""
智能采集成分股日K数据
利用已有daily_prices数据，只采集缺失的几天
"""

import tushare as ts
import sqlite3
from datetime import datetime, timedelta
import time

TOKEN = '75d5fb0d2da34ab076f1ab49eaecfac348aaf91faf06246bfcab9f68904c'
DB_PATH = 'quant_data.db'
TARGET_DATE = '20260304'

def init_tushare():
    pro = ts.pro_api(TOKEN)
    pro._DataApi__token = TOKEN
    pro._DataApi__http_url = 'http://lianghua.nanyangqiankun.top'
    return pro

def main():
    pro = init_tushare()
    
    conn = sqlite3.connect(DB_PATH)
    
    # 获取所有成分股
    cursor = conn.execute('SELECT DISTINCT stock_code FROM ths_industry_members')
    all_stocks = [row[0] for row in cursor.fetchall()]
    
    # 检查每个成分股的最新日期
    stocks_to_update = []
    for stock in all_stocks:
        cursor = conn.execute(
            'SELECT MAX(date) FROM daily_prices WHERE symbol = ?',
            (stock,)
        )
        last_date = cursor.fetchone()[0]
        
        if not last_date or last_date < TARGET_DATE:
            stocks_to_update.append({
                'code': stock,
                'last_date': last_date if last_date else '20260220'
            })
    
    conn.close()
    
    print(f"成分股总数: {len(all_stocks)}")
    print(f"需要更新的股票: {len(stocks_to_update)}")
    print(f"目标日期: {TARGET_DATE}")
    
    if not stocks_to_update:
        print("所有数据已是最新！")
        return
    
    # 批量采集
    success = 0
    total_records = 0
    start_time = time.time()
    
    for i, item in enumerate(stocks_to_update, 1):
        stock_code = item['code']
        start_date = (datetime.strptime(item['last_date'], '%Y%m%d') + timedelta(days=1)).strftime('%Y%m%d')
        
        if start_date > TARGET_DATE:
            continue
        
        try:
            df = pro.daily(ts_code=stock_code, start_date=start_date, end_date=TARGET_DATE)
            
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
                
                if success % 50 == 0:
                    elapsed = time.time() - start_time
                    print(f"  [{i}/{len(stocks_to_update)}] 成功:{success} 记录:{total_records} 用时:{elapsed/60:.1f}分")
            
            time.sleep(0.03)
            
        except Exception as e:
            if i % 100 == 0:
                print(f"  [WARN] {stock_code} 失败: {e}")
            time.sleep(0.1)
    
    elapsed = time.time() - start_time
    print(f"\n完成! 成功:{success} 只股票, 共 {total_records} 条记录, 用时:{elapsed/60:.1f}分")
    
    # 最终统计
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.execute('SELECT MAX(date) FROM daily_prices')
    max_date = cursor.fetchone()[0]
    print(f"数据最新日期: {max_date}")
    conn.close()

if __name__ == '__main__':
    main()
