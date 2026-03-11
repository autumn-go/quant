#!/usr/bin/env python3
"""
补充2024年沪深300数据到数据库
"""

import tushare as ts
import sqlite3
import pandas as pd
from datetime import datetime
import time

TOKEN = '75d5fb0d2da34ab076f1ab49eaecfac348aaf91faf06246bfcab9f68904c'
DB_PATH = 'csi300_data.db'

def init_tushare():
    ts.set_token(TOKEN)
    pro = ts.pro_api(TOKEN)
    pro._DataApi__token = TOKEN
    pro._DataApi__http_url = 'http://lianghua.nanyangqiankun.top'
    return pro

def main():
    pro = init_tushare()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    print("开始补充2024年沪深300数据...")
    print("="*60)
    
    # 1. 补充指数日线数据 (2024年)
    print("\n[1/2] 采集沪深300指数2024年日K线...")
    
    # 获取2024年数据
    df_index = pro.index_daily(ts_code='000300.SH', start_date='20240101', end_date='20241231')
    
    if df_index is not None and not df_index.empty:
        added_count = 0
        for _, row in df_index.iterrows():
            try:
                cursor.execute('''
                    INSERT OR IGNORE INTO csi300_index_daily 
                    (date, open, high, low, close, volume, amount)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (row['trade_date'], row['open'], row['high'], row['low'], 
                      row['close'], row['vol'], row['amount']))
                if cursor.rowcount > 0:
                    added_count += 1
            except Exception as e:
                pass
        conn.commit()
        print(f"  新增 {added_count} 条指数数据")
    
    # 2. 补充涨跌停数据 (2024年)
    print("\n[2/2] 采集2024年涨跌停数据...")
    
    # 生成2024年交易日
    trade_dates = pd.date_range(start='20240101', end='20241231', freq='B')
    trade_dates = [d.strftime('%Y%m%d') for d in trade_dates]
    
    total_added = 0
    for i, date in enumerate(trade_dates):
        try:
            # 检查是否已存在
            cursor.execute('SELECT COUNT(*) FROM limit_up_down WHERE date = ?', (date,))
            if cursor.fetchone()[0] > 0:
                continue
            
            # kpl_list - 涨停
            df_up = pro.kpl_list(trade_date=date, tag='涨停', fields='ts_code,name,trade_date,tag,theme,status')
            if df_up is not None and not df_up.empty:
                for _, row in df_up.iterrows():
                    cursor.execute('''
                        INSERT INTO limit_up_down (date, code, name, pct_change, limit_type, industry, source, status)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (date, row['ts_code'], row['name'], 0, 'up', row.get('theme', ''), 'kpl', row.get('status', '')))
                total_added += len(df_up)
            
            # kpl_list - 跌停
            df_down = pro.kpl_list(trade_date=date, tag='跌停', fields='ts_code,name,trade_date,tag,theme,status')
            if df_down is not None and not df_down.empty:
                for _, row in df_down.iterrows():
                    cursor.execute('''
                        INSERT INTO limit_up_down (date, code, name, pct_change, limit_type, industry, source, status)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (date, row['ts_code'], row['name'], 0, 'down', row.get('theme', ''), 'kpl', row.get('status', '')))
                total_added += len(df_down)
            
            conn.commit()
            
            if (i + 1) % 50 == 0:
                print(f"  进度: {i+1}/{len(trade_dates)} 天")
            
            time.sleep(0.05)
        except Exception as e:
            pass
    
    print(f"  新增 {total_added} 条涨跌停记录")
    
    # 统计
    print("\n" + "="*60)
    print("数据更新完成!")
    
    cursor.execute('SELECT COUNT(*), MIN(date), MAX(date) FROM csi300_index_daily')
    count, min_d, max_d = cursor.fetchone()
    print(f"\n指数日线: {count} 条 ({min_d} - {max_d})")
    
    cursor.execute('SELECT COUNT(*), COUNT(DISTINCT date) FROM limit_up_down')
    count, days = cursor.fetchone()
    print(f"涨跌停数据: {count} 条, {days} 个交易日")
    
    conn.close()

if __name__ == "__main__":
    main()
